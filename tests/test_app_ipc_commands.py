from __future__ import annotations

import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest.mock import patch

from sudo_request.app.cli.ipc_commands import command_cancel, command_cleanup, print_ipc


class IpcCommandTests(unittest.TestCase):
    def test_print_ipc_prints_raw_response_and_returns_exit_code(self) -> None:
        response = {"ok": False, "status": "busy", "exit_code": 125}

        with redirect_stdout(StringIO()) as stdout:
            self.assertEqual(print_ipc({"type": "status"}, lambda _message: response), 125)

        self.assertEqual(json.loads(stdout.getvalue()), response)

    def test_print_ipc_reports_daemon_unreachable_to_stderr(self) -> None:
        def failing_ipc(_message):
            raise ConnectionRefusedError("socket refused")

        with redirect_stderr(StringIO()) as stderr:
            self.assertEqual(print_ipc({"type": "cancel"}, failing_ipc), 127)

        output = stderr.getvalue()
        self.assertIn("status=daemon_unreachable", output)
        self.assertIn("action=cancel", output)

    def test_command_cancel_sends_cancel_request(self) -> None:
        messages = []

        def fake_ipc(message):
            messages.append(message)
            return {"ok": True, "status": "cancelled"}

        with redirect_stdout(StringIO()):
            self.assertEqual(command_cancel("req-1", fake_ipc), 0)

        self.assertEqual(messages, [{"type": "cancel", "request_id": "req-1"}])

    def test_command_cleanup_uses_ipc_when_not_root(self) -> None:
        messages = []

        def fake_ipc(message):
            messages.append(message)
            return {"ok": True, "status": "clean"}

        with patch("sudo_request.app.cli.ipc_commands.os.geteuid", return_value=501):
            with redirect_stdout(StringIO()):
                self.assertEqual(command_cleanup(fake_ipc), 0)

        self.assertEqual(messages, [{"type": "cleanup"}])


if __name__ == "__main__":
    unittest.main()
