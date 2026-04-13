from __future__ import annotations

import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from sudo_request.app.cli.cleanup import close_request_with_diagnostics


class CleanupTests(unittest.TestCase):
    def test_cleanup_diagnostics_downgrades_restart_disconnect_when_rule_is_gone(self) -> None:
        with TemporaryDirectory() as tmp:
            dropin = Path(tmp) / "sudo-request-broad"

            def failing_ipc(_message):
                raise FileNotFoundError("socket missing")

            with redirect_stderr(StringIO()) as stderr:
                close_request_with_diagnostics("req", failing_ipc, dropin)
        self.assertIn("status=daemon_unreachable", stderr.getvalue())
        self.assertIn("broad_rule=not_installed", stderr.getvalue())

    def test_cleanup_diagnostics_warns_when_rule_remains_after_disconnect(self) -> None:
        with TemporaryDirectory() as tmp:
            dropin = Path(tmp) / "sudo-request-broad"
            dropin.write_text("epikem ALL=(ALL) NOPASSWD: ALL\n", encoding="utf-8")

            def failing_ipc(_message):
                raise FileNotFoundError("socket missing")

            with redirect_stderr(StringIO()) as stderr:
                close_request_with_diagnostics("req", failing_ipc, dropin)
        output = stderr.getvalue()
        self.assertIn("status=cleanup_failed", output)
        self.assertIn("broad_rule=installed", output)
        self.assertIn("dropin_path=", output)


if __name__ == "__main__":
    unittest.main()
