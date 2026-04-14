from __future__ import annotations

import unittest
from unittest.mock import patch

from sudo_request.lib.approval.decision import approval_callback_data
from sudo_request.lib.approval.message import approval_message_text, cleanup_critical_message_text, format_local_timestamp
from sudo_request.lib.approval.telegram import TelegramClient
from tests.helpers import sample_approval_payload


class TelegramTests(unittest.TestCase):
    def payload(self):
        return sample_approval_payload()

    def test_callback_data_fits_telegram_limit(self) -> None:
        payload = self.payload()
        captured = {}

        def fake_post(_method, body, timeout=30):
            captured.update(body)
            return {"message_id": 1}

        client = TelegramClient("token")
        with patch.object(client, "_post", side_effect=fake_post):
            client.send_approval_request(123, payload)
        buttons = captured["reply_markup"]["inline_keyboard"][0]
        self.assertLessEqual(len(buttons[0]["callback_data"].encode("utf-8")), 64)
        self.assertLessEqual(len(buttons[1]["callback_data"].encode("utf-8")), 64)

    def test_approval_message_text_includes_status(self) -> None:
        self.assertIn("[APPROVED]", approval_message_text(self.payload(), "APPROVED"))
        self.assertIn("Window:  30s (max 300s)", approval_message_text(self.payload(), "APPROVED"))
        self.assertRegex(approval_message_text(self.payload(), "APPROVED"), r"Expires: \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} .+ \+\d{4} \(1\)")
        self.assertIn("(1)", approval_message_text(self.payload(), "APPROVED"))
        self.assertIn("Broad mode opens passwordless sudo", approval_message_text(self.payload(), "APPROVED"))

    def test_cleanup_critical_message_includes_residual_rule_warning(self) -> None:
        text = cleanup_critical_message_text(self.payload(), "watchdog", "/private/etc/sudoers.d/sudo-request-broad")
        self.assertIn("[CRITICAL cleanup_failed]", text)
        self.assertIn("Source:  watchdog", text)
        self.assertIn("Drop-in: /private/etc/sudoers.d/sudo-request-broad", text)
        self.assertIn("broad sudo rule may still be installed", text)
        self.assertIn("Passwordless sudo may remain available", text)

    def test_cleanup_critical_message_handles_missing_request_payload(self) -> None:
        text = cleanup_critical_message_text(None, "cleanup", "/private/etc/sudoers.d/sudo-request-broad")
        self.assertIn("[CRITICAL cleanup_failed]", text)
        self.assertIn("Active request details are unavailable", text)

    def test_format_local_timestamp_keeps_epoch_for_auditability(self) -> None:
        formatted = format_local_timestamp(1)
        self.assertRegex(formatted, r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} .+ \+\d{4} \(1\)")
        self.assertIn("(1)", formatted)

    def test_mark_callback_status_edits_message_and_removes_buttons(self) -> None:
        calls = []

        def fake_post(method, body, timeout=30):
            calls.append((method, body))
            return {"ok": True}

        callback = {"message": {"chat": {"id": 123}, "message_id": 456}}
        client = TelegramClient("token")
        with patch.object(client, "_post", side_effect=fake_post):
            client.mark_callback_status(callback, self.payload(), "DENIED")
        self.assertEqual(calls[0][0], "editMessageText")
        self.assertEqual(calls[0][1]["chat_id"], 123)
        self.assertEqual(calls[0][1]["message_id"], 456)
        self.assertIn("[DENIED]", calls[0][1]["text"])
        self.assertEqual(calls[0][1]["reply_markup"], {"inline_keyboard": []})

    def test_send_cleanup_critical_alert_sends_plain_message(self) -> None:
        calls = []

        def fake_post(method, body, timeout=30):
            calls.append((method, body, timeout))
            return {"message_id": 99}

        client = TelegramClient("token")
        with patch.object(client, "_post", side_effect=fake_post):
            message_id = client.send_cleanup_critical_alert(123, self.payload(), "close_request", "/dropin")

        self.assertEqual(message_id, 99)
        self.assertEqual(calls[0][0], "sendMessage")
        self.assertEqual(calls[0][1]["chat_id"], 123)
        self.assertIn("[CRITICAL cleanup_failed]", calls[0][1]["text"])
        self.assertEqual(calls[0][2], 10)

    def test_mark_status_raises_when_telegram_edit_fails(self) -> None:
        client = TelegramClient("token")
        with patch.object(client, "_post", side_effect=RuntimeError("edit failed")):
            with self.assertRaisesRegex(RuntimeError, "edit failed"):
                client.mark_status(123, 456, self.payload(), "FAILED")

    def test_wait_for_approval_decision_marks_timeout_expired(self) -> None:
        payload = self.payload()
        payload["approval_messages"] = [{"chat_id": 123, "message_id": 456}]
        calls = []

        def fake_post(method, body, timeout=30):
            calls.append((method, body))
            return {"ok": True}

        client = TelegramClient("token")
        with patch.object(client, "_post", side_effect=fake_post):
            result = client.wait_for_approval_decision(payload, [1], 0)
        self.assertEqual(result.status, "timeout")
        self.assertEqual(result.message, "request expired by timeout")
        self.assertEqual(calls[0][0], "editMessageText")
        self.assertIn("[EXPIRED]", calls[0][1]["text"])

    def test_wait_for_approval_decision_ignores_status_edit_failure_after_approval(self) -> None:
        payload = self.payload()
        callback = {
            "id": "callback-1",
            "from": {"id": 123},
            "data": approval_callback_data("a", payload),
            "message": {"chat": {"id": 123}, "message_id": 456},
        }
        update = {"update_id": 1, "callback_query": callback}
        calls = []

        def fake_post(method, _body, timeout=30):
            calls.append(method)
            if method == "editMessageText":
                raise RuntimeError("edit failed")
            return {"ok": True}

        client = TelegramClient("token")
        with patch.object(client, "_get", return_value={"ok": True, "result": [update]}):
            with patch.object(client, "_post", side_effect=fake_post):
                result = client.wait_for_approval_decision(payload, [123], 10)

        self.assertEqual(result.status, "approved")
        self.assertIn("answerCallbackQuery", calls)
        self.assertIn("editMessageText", calls)


if __name__ == "__main__":
    unittest.main()
