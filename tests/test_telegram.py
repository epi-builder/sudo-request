from __future__ import annotations

import unittest
from unittest.mock import patch

from sudo_request.telegram import TelegramClient, approval_message_text, format_local_timestamp


class TelegramTests(unittest.TestCase):
    def payload(self):
        return {
            "host": "host",
            "user": "epikem",
            "uid": 501,
            "cwd": "/tmp",
            "argv": ["/bin/echo", "ok"],
            "resolved_executable": "/bin/echo",
            "parent_process": {"pid": 1},
            "requested_window_seconds": 30,
            "max_window_seconds": 300,
            "expires_at": 1,
            "payload_hash": "a" * 64,
            "request_id": "r" * 24,
            "nonce": "n" * 24,
        }

    def test_callback_data_fits_telegram_limit(self) -> None:
        payload = self.payload()
        captured = {}

        def fake_post(_method, body, timeout=30):
            captured.update(body)
            return {"message_id": 1}

        client = TelegramClient("token")
        with patch.object(client, "_post", side_effect=fake_post):
            client.send_approval(123, payload)
        buttons = captured["reply_markup"]["inline_keyboard"][0]
        self.assertLessEqual(len(buttons[0]["callback_data"].encode("utf-8")), 64)
        self.assertLessEqual(len(buttons[1]["callback_data"].encode("utf-8")), 64)

    def test_approval_message_text_includes_status(self) -> None:
        self.assertIn("[APPROVED]", approval_message_text(self.payload(), "APPROVED"))
        self.assertIn("Requested sudo window: 30s (max 300s)", approval_message_text(self.payload(), "APPROVED"))
        self.assertRegex(approval_message_text(self.payload(), "APPROVED"), r"Expires at: \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} .+ \+\d{4} \(1\)")
        self.assertIn("(1)", approval_message_text(self.payload(), "APPROVED"))

    def test_format_local_timestamp_keeps_epoch_for_auditability(self) -> None:
        formatted = format_local_timestamp(1)
        self.assertRegex(formatted, r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} .+ \+\d{4} \(1\)")
        self.assertIn("(1)", formatted)

    def test_mark_decision_edits_message_and_removes_buttons(self) -> None:
        calls = []

        def fake_post(method, body, timeout=30):
            calls.append((method, body))
            return {"ok": True}

        callback = {"message": {"chat": {"id": 123}, "message_id": 456}}
        client = TelegramClient("token")
        with patch.object(client, "_post", side_effect=fake_post):
            client.mark_decision(callback, self.payload(), "DENIED")
        self.assertEqual(calls[0][0], "editMessageText")
        self.assertEqual(calls[0][1]["chat_id"], 123)
        self.assertEqual(calls[0][1]["message_id"], 456)
        self.assertIn("[DENIED]", calls[0][1]["text"])
        self.assertEqual(calls[0][1]["reply_markup"], {"inline_keyboard": []})


if __name__ == "__main__":
    unittest.main()
