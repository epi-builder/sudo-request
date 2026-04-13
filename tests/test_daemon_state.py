from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from sudo_request.app.daemon import server
from sudo_request.app.daemon.lifecycle import RequestLifecycle, RequestPhase
from sudo_request.app.daemon.server import DaemonState
from sudo_request.lib.config import Config


def lifecycle(request_id: str, user: str = "epikem") -> RequestLifecycle:
    return RequestLifecycle(
        request_id=request_id,
        payload_hash=f"hash-{request_id}",
        uid=501,
        user=user,
        host="host",
        argv=["/bin/echo", "ok"],
        cwd="/tmp",
        resolved_executable="/bin/echo",
        parent_process={"pid": 1},
        expires_at=1_776_000_000,
        requested_window_seconds=30,
        max_window_seconds=300,
    )


class DaemonStateTests(unittest.TestCase):
    def test_single_active_request(self) -> None:
        state = DaemonState()
        self.assertTrue(state.begin(lifecycle("one")))
        self.assertFalse(state.begin(lifecycle("two")))
        state.clear("one")
        self.assertTrue(state.begin(lifecycle("two")))

    def test_status_snapshot_includes_lifecycle_details(self) -> None:
        state = DaemonState()
        self.assertTrue(state.begin(lifecycle("one")))
        self.assertTrue(state.set_phase("one", RequestPhase.WINDOW_OPEN))

        status = state.status()

        self.assertEqual(status["active_request_id"], "one")
        self.assertEqual(status["active_user"], "epikem")
        self.assertEqual(status["active_request"]["phase"], "window_open")
        self.assertEqual(status["active_request"]["argv"], ["/bin/echo", "ok"])
        self.assertEqual(status["active_request"]["expires_at"], 1_776_000_000)
        self.assertIsNone(status["active_request"]["window_expires_at"])

    def test_window_expiry_updates_status_snapshot(self) -> None:
        state = DaemonState()
        self.assertTrue(state.begin(lifecycle("one")))

        self.assertTrue(state.set_window_expires_at("one", 1_776_000_030))

        status = state.status()
        self.assertEqual(status["active_request"]["window_expires_at"], 1_776_000_030)

    def test_handle_status_includes_daemon_pid(self) -> None:
        state = DaemonState()
        handler = server.RequestHandler.__new__(server.RequestHandler)

        with patch.object(server, "STATE", state):
            with patch.object(server, "DROPIN_PATH") as dropin_path:
                with patch.object(server.os, "getpid", return_value=123):
                    dropin_path.exists.return_value = False
                    result = server.RequestHandler.handle_status(handler)

        self.assertEqual(result["daemon_pid"], 123)
        self.assertFalse(result["dropin_exists"])

    def test_notification_payload_returns_active_request_payload(self) -> None:
        state = DaemonState()
        self.assertTrue(state.begin(lifecycle("one")))

        snapshot = state.notification_payload("one")

        self.assertIsNotNone(snapshot)
        uid, payload = snapshot
        self.assertEqual(uid, 501)
        self.assertEqual(payload["request_id"], "one")
        self.assertIsNone(state.notification_payload("other"))

    def test_lifecycle_event_updates_active_request_and_marks_telegram(self) -> None:
        state = DaemonState()
        active = lifecycle("one")
        active.approval_messages = [{"chat_id": 123, "message_id": 456}]
        self.assertTrue(state.begin(active))
        handler = server.RequestHandler.__new__(server.RequestHandler)
        handler.request = Mock()
        handler.mark_approval_messages = Mock()

        with patch.object(server, "STATE", state):
            with patch.object(server, "peer_uid", return_value=501):
                with patch.object(server, "append_jsonl"):
                    result = server.RequestHandler.handle_lifecycle_event(
                        handler,
                        {"type": "lifecycle_event", "request_id": "one", "payload_hash": "hash-one", "phase": "done", "exit_code": 7},
                    )

        self.assertEqual(result, {"ok": True, "status": "updated"})
        self.assertEqual(state.active_request.phase, RequestPhase.DONE)
        self.assertEqual(state.active_request.exit_code, 7)
        handler.mark_approval_messages.assert_called_once()
        self.assertEqual(handler.mark_approval_messages.call_args.args[2], "DONE exit=7")

    def test_lifecycle_event_rejects_mismatched_hash(self) -> None:
        state = DaemonState()
        self.assertTrue(state.begin(lifecycle("one")))
        handler = server.RequestHandler.__new__(server.RequestHandler)
        handler.request = Mock()

        with patch.object(server, "STATE", state):
            with patch.object(server, "peer_uid", return_value=501):
                result = server.RequestHandler.handle_lifecycle_event(
                    handler,
                    {"type": "lifecycle_event", "request_id": "one", "payload_hash": "wrong", "phase": "running"},
                )

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "request_mismatch")
        self.assertEqual(state.active_request.phase, RequestPhase.PENDING_APPROVAL)

    def test_mark_failed_request_best_effort_updates_existing_approval_messages(self) -> None:
        handler = server.RequestHandler.__new__(server.RequestHandler)
        telegram = Mock()
        payload = lifecycle("one").to_approval_payload()
        payload["approval_messages"] = [{"chat_id": 123, "message_id": 456}]

        server.RequestHandler.mark_failed_request_best_effort(handler, telegram, payload, "network down")

        telegram.mark_status.assert_called_once_with(123, 456, payload, "FAILED")

    def test_mark_failed_request_best_effort_audits_update_failure(self) -> None:
        handler = server.RequestHandler.__new__(server.RequestHandler)
        telegram = Mock()
        telegram.mark_status.side_effect = RuntimeError("edit failed")
        payload = lifecycle("one").to_approval_payload()
        payload["approval_messages"] = [{"chat_id": 123, "message_id": 456}]

        with patch.object(server, "append_jsonl") as audit:
            server.RequestHandler.mark_failed_request_best_effort(handler, telegram, payload, "network down")

        audit.assert_called_once()
        self.assertEqual(audit.call_args.args[1], "telegram_status_update_failed")
        self.assertEqual(audit.call_args.args[2]["request_id"], "one")
        self.assertEqual(audit.call_args.args[2]["status"], "FAILED")
        self.assertIn("edit failed", audit.call_args.args[2]["error"])
        self.assertEqual(audit.call_args.args[2]["request_error"], "network down")

    def test_cleanup_critical_alert_sends_to_configured_chats(self) -> None:
        handler = server.RequestHandler.__new__(server.RequestHandler)
        telegram = Mock()
        telegram.send_cleanup_critical_alert.side_effect = [11, 22]
        payload = lifecycle("one").to_approval_payload()
        cfg = Config(Path("/token"), [123, 456])

        with patch.object(server, "home_for_uid", return_value=Path("/Users/epikem")):
            with patch.object(server, "load_config", return_value=cfg):
                with patch.object(server, "read_token", return_value="token"):
                    with patch.object(server, "TelegramClient", return_value=telegram):
                        with patch.object(server, "append_jsonl") as audit:
                            server.RequestHandler.send_cleanup_critical_alert_best_effort(handler, 501, payload, "close_request")

        self.assertEqual(telegram.send_cleanup_critical_alert.call_count, 2)
        self.assertEqual(telegram.send_cleanup_critical_alert.call_args_list[0].args[0], 123)
        self.assertEqual(telegram.send_cleanup_critical_alert.call_args_list[1].args[0], 456)
        self.assertEqual(audit.call_count, 2)
        self.assertEqual(audit.call_args_list[0].args[1], "cleanup_critical_alert_sent")

    def test_cleanup_critical_alert_audits_send_failure(self) -> None:
        handler = server.RequestHandler.__new__(server.RequestHandler)
        telegram = Mock()
        telegram.send_cleanup_critical_alert.side_effect = RuntimeError("send failed")
        payload = lifecycle("one").to_approval_payload()
        cfg = Config(Path("/token"), [123])

        with patch.object(server, "home_for_uid", return_value=Path("/Users/epikem")):
            with patch.object(server, "load_config", return_value=cfg):
                with patch.object(server, "read_token", return_value="token"):
                    with patch.object(server, "TelegramClient", return_value=telegram):
                        with patch.object(server, "append_jsonl") as audit:
                            server.RequestHandler.send_cleanup_critical_alert_best_effort(handler, 501, payload, "close_request")

        audit.assert_called_once()
        self.assertEqual(audit.call_args.args[1], "cleanup_critical_alert_failed")
        self.assertEqual(audit.call_args.args[2]["request_id"], "one")
        self.assertEqual(audit.call_args.args[2]["chat_id"], 123)
        self.assertIn("send failed", audit.call_args.args[2]["error"])

    def test_close_request_cleanup_failure_sends_critical_alert_before_clearing(self) -> None:
        state = DaemonState()
        self.assertTrue(state.begin(lifecycle("one")))
        handler = server.RequestHandler.__new__(server.RequestHandler)
        handler.request = Mock()
        handler.send_cleanup_critical_alert_best_effort_from_snapshot = Mock()

        with patch.object(server, "STATE", state):
            with patch.object(server, "peer_uid", return_value=501):
                with patch.object(server, "cleanup_broad_rule", return_value=False):
                    with patch.object(server, "append_jsonl"):
                        result = server.RequestHandler.handle_close_request(handler, {"type": "close_request", "request_id": "one"})

        self.assertEqual(result, {"ok": False, "status": "cleanup_failed"})
        handler.send_cleanup_critical_alert_best_effort_from_snapshot.assert_called_once()
        self.assertEqual(handler.send_cleanup_critical_alert_best_effort_from_snapshot.call_args.args[1], "close_request")
        self.assertIsNone(state.active_request)

    def test_cleanup_failure_without_active_request_sends_generic_alert_to_peer_user(self) -> None:
        state = DaemonState()
        handler = server.RequestHandler.__new__(server.RequestHandler)
        handler.request = Mock()
        handler.send_cleanup_critical_alert_best_effort = Mock()

        with patch.object(server, "STATE", state):
            with patch.object(server, "peer_uid", return_value=501):
                with patch.object(server, "cleanup_broad_rule", return_value=False):
                    with patch.object(server, "append_jsonl"):
                        result = server.RequestHandler.handle_cleanup(handler)

        self.assertEqual(result, {"ok": False, "status": "cleanup_failed"})
        handler.send_cleanup_critical_alert_best_effort.assert_called_once_with(501, None, "cleanup")

    def test_watchdog_cleanup_failure_sends_critical_alert(self) -> None:
        state = DaemonState()
        self.assertTrue(state.begin(lifecycle("one")))

        with patch.object(server, "STATE", state):
            with patch.object(server, "cleanup_broad_rule", return_value=False):
                with patch.object(server.RequestHandler, "send_cleanup_critical_alert_best_effort_from_snapshot") as alert:
                    with patch.object(server, "append_jsonl"):
                        server.watchdog_cleanup("one")

        alert.assert_called_once()
        self.assertEqual(alert.call_args.args[1], "watchdog")
        self.assertIsNone(state.active_request)

if __name__ == "__main__":
    unittest.main()
