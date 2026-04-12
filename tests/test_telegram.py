from __future__ import annotations

import unittest
from unittest.mock import patch

from sudo_request.telegram import TelegramClient


class TelegramTests(unittest.TestCase):
    def test_callback_data_fits_telegram_limit(self) -> None:
        payload = {
            "host": "host",
            "user": "epikem",
            "uid": 501,
            "cwd": "/tmp",
            "argv": ["/bin/echo", "ok"],
            "resolved_executable": "/bin/echo",
            "parent_process": {"pid": 1},
            "expires_at": 1,
            "payload_hash": "a" * 64,
            "request_id": "r" * 24,
            "nonce": "n" * 24,
        }
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


if __name__ == "__main__":
    unittest.main()
