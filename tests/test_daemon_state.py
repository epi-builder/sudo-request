from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from sudo_request.app.daemon import server
from sudo_request.app.daemon.lifecycle import RequestLifecycle, RequestPhase
from sudo_request.app.daemon.server import DaemonState, peer_uid


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

    def test_peer_uid_uses_darwin_local_peercred_fallback(self) -> None:
        sock = Mock()
        del sock.getpeereid
        sock.getsockopt.return_value = b"\x00\x00\x00\x00\xf5\x01\x00\x00\x01\x00"
        self.assertEqual(peer_uid(sock), 501)


if __name__ == "__main__":
    unittest.main()
