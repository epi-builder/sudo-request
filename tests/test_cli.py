from __future__ import annotations

import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path

from sudo_request.cli import command_run, render_launchd_plist


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


if __name__ == "__main__":
    unittest.main()
