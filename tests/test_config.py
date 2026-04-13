from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sudo_request.lib.config import load_config


class ConfigTests(unittest.TestCase):
    def test_load_config_expands_home_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cfg_dir = home / ".config" / "sudo-request"
            cfg_dir.mkdir(parents=True)
            (cfg_dir / "config.toml").write_text(
                "\n".join([
                    'telegram_bot_token_file = "~/.config/sudo-request/token"',
                    "telegram_allowed_user_ids = [123, 456]",
                    "approval_timeout_seconds = 12",
                    "approval_wait_heartbeat_seconds = 3",
                    "broad_window_seconds_default = 7",
                    "broad_window_seconds_max = 20",
                ]),
                encoding="utf-8",
            )
            cfg = load_config(home)
            self.assertEqual(cfg.telegram_bot_token_file, cfg_dir / "token")
            self.assertEqual(cfg.telegram_allowed_user_ids, [123, 456])
            self.assertEqual(cfg.approval_timeout_seconds, 12)
            self.assertEqual(cfg.approval_wait_heartbeat_seconds, 3)
            self.assertEqual(cfg.broad_window_seconds_default, 7)
            self.assertEqual(cfg.broad_window_seconds_max, 20)


if __name__ == "__main__":
    unittest.main()
