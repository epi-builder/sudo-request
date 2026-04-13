from __future__ import annotations

import unittest
import time
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sudo_request.config import Config
from sudo_request.cli import close_request_with_diagnostics, command_run, ipc_request_with_heartbeat, render_launchd_plist


class CliTests(unittest.TestCase):
    def test_render_launchd_plist_contains_program_arguments(self) -> None:
        plist = render_launchd_plist(Path("/usr/local/bin/sudo-request"))
        self.assertIn("<string>/usr/local/bin/sudo-request</string>", plist)
        self.assertIn("<string>daemon</string>", plist)
        self.assertIn("<string>--foreground</string>", plist)
        self.assertIn("<key>KeepAlive</key>", plist)

    def test_command_run_rejects_non_positive_window(self) -> None:
        with redirect_stderr(StringIO()):
            self.assertEqual(command_run(["/bin/echo", "ok"], 0), 125)

    def test_ipc_request_with_heartbeat_prints_waiting_message(self) -> None:
        def slow_ipc(_message):
            time.sleep(0.03)
            return {"ok": True}

        cfg = Config(Path("/tmp/token"), [1], approval_wait_heartbeat_seconds=0.01)
        with patch("sudo_request.cli.ipc_request", side_effect=slow_ipc):
            with redirect_stderr(StringIO()) as stderr:
                self.assertEqual(ipc_request_with_heartbeat({"type": "status"}, cfg), {"ok": True})
        self.assertIn("still waiting for Telegram approval", stderr.getvalue())

    def test_cleanup_diagnostics_downgrades_restart_disconnect_when_rule_is_gone(self) -> None:
        with TemporaryDirectory() as tmp:
            dropin = Path(tmp) / "sudo-request-broad"
            with patch("sudo_request.cli.DROPIN_PATH", dropin):
                with patch("sudo_request.cli.ipc_request", side_effect=FileNotFoundError("socket missing")):
                    with redirect_stderr(StringIO()) as stderr:
                        close_request_with_diagnostics("req")
        self.assertIn("could not reach daemon, but broad sudo rule is not installed", stderr.getvalue())

    def test_cleanup_diagnostics_warns_when_rule_remains_after_disconnect(self) -> None:
        with TemporaryDirectory() as tmp:
            dropin = Path(tmp) / "sudo-request-broad"
            dropin.write_text("epikem ALL=(ALL) NOPASSWD: ALL\n", encoding="utf-8")
            with patch("sudo_request.cli.DROPIN_PATH", dropin):
                with patch("sudo_request.cli.ipc_request", side_effect=FileNotFoundError("socket missing")):
                    with redirect_stderr(StringIO()) as stderr:
                        close_request_with_diagnostics("req")
        output = stderr.getvalue()
        self.assertIn("cleanup request failed", output)
        self.assertIn("broad sudo rule still exists", output)


if __name__ == "__main__":
    unittest.main()
