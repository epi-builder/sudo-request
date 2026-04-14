from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from sudo_request.app.daemon import watchdog
from sudo_request.app.daemon.state import DaemonState
from tests.helpers import sample_lifecycle


class DaemonWatchdogTests(unittest.TestCase):
    def test_watchdog_cleanup_failure_sends_critical_alert(self) -> None:
        state = DaemonState()
        self.assertTrue(state.begin(sample_lifecycle("one")))
        alert = Mock()

        with patch.object(watchdog, "close_broad_window", return_value=False):
            with patch.object(watchdog, "append_jsonl"):
                watchdog.watchdog_cleanup(state, "one", alert)

        alert.assert_called_once()
        self.assertEqual(alert.call_args.args[1], "watchdog")
        self.assertEqual(alert.call_args.args[2], "one")
        self.assertIsNone(state.active_request)

    def test_watchdog_cleanup_success_expires_and_clears_request(self) -> None:
        state = DaemonState()
        self.assertTrue(state.begin(sample_lifecycle("one")))
        alert = Mock()

        with patch.object(watchdog, "close_broad_window", return_value=True):
            with patch.object(watchdog, "append_jsonl") as audit:
                watchdog.watchdog_cleanup(state, "one", alert)

        alert.assert_not_called()
        audit.assert_called_once()
        self.assertEqual(audit.call_args.args[1], "window_watchdog_cleanup")
        self.assertIsNone(state.active_request)


if __name__ == "__main__":
    unittest.main()
