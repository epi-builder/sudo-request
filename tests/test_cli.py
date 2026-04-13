from __future__ import annotations

import unittest
import time
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from sudo_request.config import Config
from sudo_request.cli import command_run, ipc_request_with_heartbeat


class CliTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
