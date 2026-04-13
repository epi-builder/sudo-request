from __future__ import annotations

import unittest
from pathlib import Path

from sudo_request.install import render_launchd_plist


class InstallTests(unittest.TestCase):
    def test_render_launchd_plist_contains_program_arguments(self) -> None:
        plist = render_launchd_plist(Path("/usr/local/bin/sudo-request"))
        self.assertIn("<string>/usr/local/bin/sudo-request</string>", plist)
        self.assertIn("<string>daemon</string>", plist)
        self.assertIn("<string>--foreground</string>", plist)
        self.assertIn("<key>KeepAlive</key>", plist)


if __name__ == "__main__":
    unittest.main()
