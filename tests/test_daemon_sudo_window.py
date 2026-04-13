from __future__ import annotations

import unittest
from unittest.mock import patch

from sudo_request.app.daemon import sudo_window


class DaemonSudoWindowTests(unittest.TestCase):
    def test_open_broad_window_installs_rule_and_returns_expiry(self) -> None:
        with patch.object(sudo_window, "install_broad_rule") as install:
            with patch.object(sudo_window.time, "time", return_value=1000.4):
                expires_at = sudo_window.open_broad_window("epikem", 30)

        install.assert_called_once_with("epikem")
        self.assertEqual(expires_at, 1030)

    def test_close_broad_window_uses_requested_retry_policy(self) -> None:
        with patch.object(sudo_window, "cleanup_broad_rule", return_value=True) as cleanup:
            result = sudo_window.close_broad_window(retries=10, delay_seconds=0.5)

        self.assertTrue(result)
        cleanup.assert_called_once_with(retries=10, delay_seconds=0.5)


if __name__ == "__main__":
    unittest.main()
