from __future__ import annotations

import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest.mock import patch

from sudo_request.app.cli.status import command_status, format_status


class StatusTests(unittest.TestCase):
    def test_format_status_reports_idle(self) -> None:
        text = format_status({"ok": True, "status": "ok", "daemon_pid": 123, "active_request": None, "dropin_exists": False})

        self.assertIn("daemon: ok pid=123", text)
        self.assertIn("state: idle", text)
        self.assertIn("broad sudo rule: not installed", text)

    def test_format_status_reports_active_request(self) -> None:
        response = {
            "ok": True,
            "status": "ok",
            "daemon_pid": 123,
            "dropin_exists": False,
            "active_request": {
                "request_id": "req-1",
                "phase": "running",
                "user": "epikem",
                "argv": ["/usr/bin/sudo", "/usr/bin/id", "-u"],
                "cwd": "/tmp",
                "requested_window_seconds": 30,
                "expires_at": 1_776_000_000,
                "window_expires_at": 1_776_000_030,
            },
        }

        with patch("sudo_request.app.cli.status.format_local_timestamp", side_effect=["2026-04-14 12:00:00 KST", "2026-04-14 12:00:30 KST"]):
            text = format_status(response)

        self.assertIn("state: active", text)
        self.assertIn("phase: running", text)
        self.assertIn("user: epikem", text)
        self.assertIn("command: /usr/bin/sudo /usr/bin/id -u", text)
        self.assertIn("cwd: /tmp", text)
        self.assertIn("requested window: 30s", text)
        self.assertIn("approval expires: 2026-04-14 12:00:00 KST", text)
        self.assertIn("window expires: 2026-04-14 12:00:30 KST", text)

    def test_format_status_warns_on_orphaned_dropin(self) -> None:
        text = format_status({"ok": True, "status": "ok", "daemon_pid": 123, "active_request": None, "dropin_exists": True})

        self.assertIn("broad sudo rule: installed", text)
        self.assertIn("WARNING: broad sudo rule is currently installed", text)
        self.assertIn("WARNING: broad sudo rule exists but daemon reports no active request", text)

    def test_command_status_json_preserves_raw_response(self) -> None:
        response = {"ok": True, "status": "ok", "daemon_pid": 123, "active_request": None, "dropin_exists": False}

        with redirect_stdout(StringIO()) as stdout:
            self.assertEqual(command_status(lambda _message: response, json_output=True), 0)

        self.assertEqual(json.loads(stdout.getvalue()), response)

    def test_command_status_prints_agent_readable_daemon_unreachable_to_stderr(self) -> None:
        def failing_ipc(_message):
            raise FileNotFoundError("socket missing")

        with redirect_stderr(StringIO()) as stderr:
            self.assertEqual(command_status(failing_ipc), 127)

        output = stderr.getvalue()
        self.assertIn("status=daemon_unreachable", output)
        self.assertIn("exit_code=127", output)
        self.assertIn("action=status", output)
        self.assertIn("error_type=FileNotFoundError", output)


if __name__ == "__main__":
    unittest.main()
