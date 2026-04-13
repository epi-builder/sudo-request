from __future__ import annotations

import unittest
import time
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

from sudo_request.lib.config import Config
from sudo_request.app.cli.main import command_run, command_update_itself, ipc_request_with_heartbeat


class CliTests(unittest.TestCase):
    def test_command_run_rejects_non_positive_window(self) -> None:
        with redirect_stderr(StringIO()):
            self.assertEqual(command_run(["/bin/echo", "ok"], 0), 125)

    def test_command_run_prints_running_and_exit_status(self) -> None:
        response = {"ok": True, "request_id": "req-1", "window_seconds": 5}
        calls = []

        def fake_run(cmd, stdout=None, stderr=None):
            calls.append(cmd)
            if cmd == ["/bin/false"]:
                return Mock(returncode=7)
            return Mock(returncode=0)

        with patch("sudo_request.app.cli.main.load_config", return_value=Config(Path("/tmp/token"), [1])):
            with patch("sudo_request.app.cli.main.ipc_request_with_heartbeat", return_value=response):
                with patch("sudo_request.app.cli.main.close_request_with_diagnostics"):
                    with patch("sudo_request.app.cli.main.append_jsonl_best_effort"):
                        with patch("sudo_request.app.cli.main.subprocess.run", side_effect=fake_run):
                            with redirect_stderr(StringIO()) as stderr:
                                self.assertEqual(command_run(["/bin/false"], 3), 7)

        self.assertIn(["/usr/bin/sudo", "-k"], calls)
        self.assertIn(["/bin/false"], calls)
        self.assertIn("sudo-request: running command...", stderr.getvalue())
        self.assertIn("sudo-request: command exited with code 7", stderr.getvalue())

    def test_command_update_itself_wraps_install_command(self) -> None:
        with patch("sudo_request.app.cli.main.update_itself_command", return_value=["/usr/bin/sudo", "/usr/bin/python3", "-m", "sudo_request", "install"]):
            with patch("sudo_request.app.cli.main.command_run", return_value=0) as run:
                self.assertEqual(command_update_itself("/src", 12), 0)
        run.assert_called_once_with(["/usr/bin/sudo", "/usr/bin/python3", "-m", "sudo_request", "install"], 12)

    def test_ipc_request_with_heartbeat_prints_waiting_message(self) -> None:
        def slow_ipc(_message):
            time.sleep(0.2)
            return {"ok": True}

        cfg = Config(Path("/tmp/token"), [1], approval_wait_heartbeat_seconds=0.01)
        with patch("sudo_request.app.cli.main.ipc_request", side_effect=slow_ipc):
            with redirect_stderr(StringIO()) as stderr:
                self.assertEqual(ipc_request_with_heartbeat({"type": "status"}, cfg), {"ok": True})
        self.assertIn("still waiting for Telegram approval", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
