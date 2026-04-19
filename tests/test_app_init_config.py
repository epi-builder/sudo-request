from __future__ import annotations

import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sudo_request.app.cli.init_config import command_init, format_config_path, parse_allowed_user_ids
from sudo_request.lib.config import load_config


class InitConfigTests(unittest.TestCase):
    def test_command_init_creates_user_config_and_token_file(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            with patch("sudo_request.app.cli.init_config.Path.home", return_value=home):
                with patch("sudo_request.app.cli.init_config.getpass.getpass", return_value="secret-token"):
                    with patch("builtins.input", return_value="123456789"):
                        with redirect_stdout(StringIO()) as stdout:
                            self.assertEqual(command_init(), 0)

            cfg_path = home / ".config" / "sudo-request" / "config.toml"
            token_path = home / ".config" / "sudo-request" / "telegram_bot_token"
            cfg = load_config(home)

            self.assertEqual(cfg.telegram_bot_token_file, token_path)
            self.assertEqual(cfg.telegram_allowed_user_ids, [123456789])
            self.assertEqual(token_path.read_text(encoding="utf-8"), "secret-token\n")
            self.assertEqual(cfg_path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(token_path.stat().st_mode & 0o777, 0o600)
            self.assertIn("Wrote config.", stdout.getvalue())
            self.assertNotIn("secret-token", stdout.getvalue())

    def test_command_init_rejects_non_integer_allowed_user_id(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            with patch("sudo_request.app.cli.init_config.Path.home", return_value=home):
                with patch("sudo_request.app.cli.init_config.getpass.getpass", return_value="secret-token"):
                    with patch("builtins.input", return_value="not-an-int"):
                        with redirect_stdout(StringIO()) as stdout:
                            self.assertEqual(command_init(), 1)

        self.assertIn("Allowed Telegram user id must be an integer.", stdout.getvalue())

    def test_command_init_existing_config_can_keep_existing_values(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            cfg_dir = home / ".config" / "sudo-request"
            cfg_dir.mkdir(parents=True)
            token_path = cfg_dir / "telegram_bot_token"
            token_path.write_text("existing-token\n", encoding="utf-8")
            token_path.chmod(0o644)
            (cfg_dir / "config.toml").write_text(
                'telegram_bot_token_file = "~/.config/sudo-request/telegram_bot_token"\n'
                "telegram_allowed_user_ids = [123]\n",
                encoding="utf-8",
            )

            with patch("sudo_request.app.cli.init_config.Path.home", return_value=home):
                with patch("sudo_request.app.cli.init_config.getpass.getpass", return_value=""):
                    with patch("builtins.input", return_value=""):
                        with redirect_stdout(StringIO()) as stdout:
                            self.assertEqual(command_init(), 0)

            cfg = load_config(home)
            self.assertEqual(cfg.telegram_allowed_user_ids, [123])
            self.assertEqual(token_path.read_text(encoding="utf-8"), "existing-token\n")
            self.assertEqual(token_path.stat().st_mode & 0o777, 0o600)
            self.assertIn("Existing config found:", stdout.getvalue())
            self.assertIn("configured", stdout.getvalue())

    def test_command_init_existing_config_can_overwrite_values(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            cfg_dir = home / ".config" / "sudo-request"
            cfg_dir.mkdir(parents=True)
            token_path = cfg_dir / "telegram_bot_token"
            token_path.write_text("existing-token\n", encoding="utf-8")
            token_path.chmod(0o600)
            (cfg_dir / "config.toml").write_text(
                'telegram_bot_token_file = "~/.config/sudo-request/telegram_bot_token"\n'
                "telegram_allowed_user_ids = [123]\n",
                encoding="utf-8",
            )

            with patch("sudo_request.app.cli.init_config.Path.home", return_value=home):
                with patch("sudo_request.app.cli.init_config.getpass.getpass", return_value="new-token"):
                    with patch("builtins.input", return_value="456, 789"):
                        with redirect_stdout(StringIO()):
                            self.assertEqual(command_init(), 0)

            cfg = load_config(home)
            self.assertEqual(cfg.telegram_allowed_user_ids, [456, 789])
            self.assertEqual(token_path.read_text(encoding="utf-8"), "new-token\n")

    def test_parse_allowed_user_ids_accepts_comma_separated_values(self) -> None:
        self.assertEqual(parse_allowed_user_ids("123, 456"), [123, 456])

    def test_format_config_path_uses_home_relative_path(self) -> None:
        home = Path("/Users/example")
        self.assertEqual(format_config_path(home / ".config" / "sudo-request" / "token", home), "~/.config/sudo-request/token")


if __name__ == "__main__":
    unittest.main()
