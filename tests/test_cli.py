from __future__ import annotations

import unittest
import time
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest.mock import ANY, Mock, patch

from sudo_request import __version__
from sudo_request.app.cli.main import main
from sudo_request.app.cli.install_commands import command_update_itself
from sudo_request.app.cli.run import command_run, ipc_request_with_heartbeat
from tests.helpers import sample_config


class CliTests(unittest.TestCase):
    def test_main_prints_version(self) -> None:
        with redirect_stdout(StringIO()) as stdout:
            with self.assertRaises(SystemExit) as ctx:
                main(["--version"])
        self.assertEqual(ctx.exception.code, 0)
        self.assertEqual(stdout.getvalue(), f"sudo-request {__version__}\n")

    def test_command_run_rejects_non_positive_window(self) -> None:
        with redirect_stderr(StringIO()) as stderr:
            self.assertEqual(command_run(["/bin/echo", "ok"], 0), 125)
        self.assertIn("status=policy_block", stderr.getvalue())
        self.assertIn("exit_code=125", stderr.getvalue())
        self.assertIn("action=run", stderr.getvalue())

    def test_command_run_prints_running_and_exit_status(self) -> None:
        response = {"ok": True, "request_id": "req-1", "payload_hash": "hash-1", "window_seconds": 5}
        calls = []

        def fake_run(cmd, stdout=None, stderr=None):
            calls.append(cmd)
            if cmd == ["/bin/false"]:
                return Mock(returncode=7)
            return Mock(returncode=0)

        with patch("sudo_request.app.cli.run.load_config", return_value=sample_config()):
            with patch("sudo_request.app.cli.run.ipc_request_with_heartbeat", return_value=response):
                with patch("sudo_request.app.cli.run.close_request_with_diagnostics"):
                    with patch("sudo_request.app.cli.run.append_jsonl_best_effort"):
                        with patch("sudo_request.app.cli.run.send_lifecycle_event_best_effort") as lifecycle:
                            with patch("sudo_request.app.cli.run.subprocess.run", side_effect=fake_run):
                                with redirect_stderr(StringIO()) as stderr:
                                    self.assertEqual(command_run(["/bin/false"], 3), 7)

        self.assertIn(["/usr/bin/sudo", "-k"], calls)
        self.assertIn(["/bin/false"], calls)
        self.assertIn("sudo-request: running command...", stderr.getvalue())
        self.assertIn("sudo-request: command exited with code 7", stderr.getvalue())
        self.assertEqual(lifecycle.call_args_list[0].args, ("req-1", "hash-1", "running"))
        self.assertEqual(lifecycle.call_args_list[1].args, ("req-1", "hash-1", "done", 7))

    def test_command_update_itself_wraps_install_command(self) -> None:
        with patch("sudo_request.app.cli.install_commands.update_itself_command", return_value=["/usr/bin/sudo", "/usr/bin/python3", "-m", "sudo_request", "install"]):
            with patch("sudo_request.app.cli.install_commands.command_run", return_value=0) as run:
                self.assertEqual(command_update_itself("/src", 12), 0)
        run.assert_called_once_with(["/usr/bin/sudo", "/usr/bin/python3", "-m", "sudo_request", "install"], 12, ANY)

    def test_command_run_prints_agent_readable_denied_error(self) -> None:
        response = {"ok": False, "status": "denied", "exit_code": 126, "request_id": "req-1", "error": "approval denied"}

        with patch("sudo_request.app.cli.run.load_config", return_value=sample_config()):
            with patch("sudo_request.app.cli.run.ipc_request_with_heartbeat", return_value=response):
                with patch("sudo_request.app.cli.run.subprocess.run", return_value=Mock(returncode=0)):
                    with redirect_stderr(StringIO()) as stderr:
                        self.assertEqual(command_run(["/bin/echo", "ok"], 3), 126)

        output = stderr.getvalue()
        self.assertIn("sudo-request: error", output)
        self.assertIn("status=denied", output)
        self.assertIn("exit_code=126", output)
        self.assertIn("request_id=req-1", output)
        self.assertIn("action=run_request", output)
        self.assertIn("message='approval denied'", output)

    def test_command_run_prints_agent_readable_timeout_error(self) -> None:
        response = {"ok": False, "status": "timeout", "exit_code": 124, "request_id": "req-1", "error": "request expired by timeout"}

        with patch("sudo_request.app.cli.run.load_config", return_value=sample_config()):
            with patch("sudo_request.app.cli.run.ipc_request_with_heartbeat", return_value=response):
                with patch("sudo_request.app.cli.run.subprocess.run", return_value=Mock(returncode=0)):
                    with redirect_stderr(StringIO()) as stderr:
                        self.assertEqual(command_run(["/bin/echo", "ok"], 3), 124)

        output = stderr.getvalue()
        self.assertIn("status=timeout", output)
        self.assertIn("exit_code=124", output)
        self.assertIn("request_id=req-1", output)
        self.assertIn("message='request expired by timeout'", output)

    def test_command_run_prints_agent_readable_daemon_unreachable_error(self) -> None:
        with patch("sudo_request.app.cli.run.load_config", return_value=sample_config()):
            with patch("sudo_request.app.cli.run.ipc_request_with_heartbeat", side_effect=ConnectionRefusedError("socket refused")):
                with patch("sudo_request.app.cli.run.subprocess.run", return_value=Mock(returncode=0)):
                    with redirect_stderr(StringIO()) as stderr:
                        self.assertEqual(command_run(["/bin/echo", "ok"], 3), 127)

        output = stderr.getvalue()
        self.assertIn("status=daemon_unreachable", output)
        self.assertIn("exit_code=127", output)
        self.assertIn("action=run_request", output)
        self.assertIn("error_type=ConnectionRefusedError", output)
        self.assertIn("message='socket refused'", output)

    def test_ipc_request_with_heartbeat_prints_waiting_message(self) -> None:
        def slow_ipc(_message):
            time.sleep(0.2)
            return {"ok": True}

        cfg = sample_config(approval_wait_heartbeat_seconds=0.01)
        with redirect_stderr(StringIO()) as stderr:
            self.assertEqual(ipc_request_with_heartbeat({"type": "status"}, cfg, slow_ipc), {"ok": True})
        self.assertIn("still waiting for Telegram approval", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
