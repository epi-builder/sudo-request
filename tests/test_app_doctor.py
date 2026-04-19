from __future__ import annotations

import subprocess
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sudo_request.app.cli.doctor import command_doctor, format_path_check, passwordless_sudo_status, telegram_token_status
from tests.helpers import sample_config


class DoctorTests(unittest.TestCase):
    def test_format_path_check_reports_missing_required_path(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing"
            line = format_path_check("sudoers.d", path, required=True, expected_uid=0, max_mode=0o755, kind="dir")
        self.assertIn("exists=False", line)
        self.assertIn("status=ERROR missing", line)

    def test_format_path_check_warns_on_overly_open_mode(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "wrapper"
            path.write_text("#!/bin/sh\n", encoding="utf-8")
            path.chmod(0o777)
            line = format_path_check("PATH wrapper", path, required=True, max_mode=0o755, kind="file")
        self.assertIn("status=WARNING", line)
        self.assertIn("mode=0777 max=0755", line)

    def test_format_path_check_accepts_stricter_mode(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "wrapper"
            path.write_text("#!/bin/sh\n", encoding="utf-8")
            path.chmod(0o700)
            line = format_path_check("PATH wrapper", path, required=True, max_mode=0o755, kind="file")
        self.assertIn("status=ok", line)
        self.assertIn("mode=0700", line)

    def test_passwordless_sudo_status_warns_when_sudo_is_open(self) -> None:
        def runner(*_args, **_kwargs):
            return subprocess.CompletedProcess(["/usr/bin/sudo"], 0, "0\n", "")

        self.assertIn("WARNING open", passwordless_sudo_status(runner))

    def test_passwordless_sudo_status_reports_closed_window(self) -> None:
        def runner(*_args, **_kwargs):
            return subprocess.CompletedProcess(["/usr/bin/sudo"], 1, "", "sudo: a password is required\n")

        self.assertIn("closed: sudo: a password is required", passwordless_sudo_status(runner))

    def test_command_doctor_warns_on_orphaned_dropin_status(self) -> None:
        def ipc_request(_message):
            return {"ok": True, "status": "ok", "active_request": None, "dropin_exists": True}

        def sudo_runner(*_args, **_kwargs):
            return subprocess.CompletedProcess(["/usr/bin/sudo"], 1, "", "sudo: a password is required\n")

        with TemporaryDirectory() as tmp:
            token_path = Path(tmp) / "sudo-request-token"
            token_path.write_text("secret\n", encoding="utf-8")
            token_path.chmod(0o600)
            cfg = sample_config(str(token_path), [123])
            with patch("sudo_request.app.cli.doctor.config_path", return_value=Path(tmp) / "config.toml"):
                with patch("sudo_request.app.cli.doctor.load_config", return_value=cfg):
                    with redirect_stdout(StringIO()) as stdout:
                        self.assertEqual(command_doctor(ipc_request, sudo_runner), 1)

        output = stdout.getvalue()
        self.assertIn("daemon status:", output)
        self.assertIn("WARNING: broad sudo rule is currently installed", output)
        self.assertIn("WARNING: broad sudo rule exists but daemon reports no active request", output)
        self.assertIn("Next:", output)

    def test_command_doctor_reports_missing_config_as_incomplete(self) -> None:
        def ipc_request(_message):
            return {"ok": True, "status": "ok", "active_request": None, "dropin_exists": False}

        def sudo_runner(*_args, **_kwargs):
            return subprocess.CompletedProcess(["/usr/bin/sudo"], 1, "", "sudo: a password is required\n")

        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            with patch("sudo_request.app.cli.doctor.Path.home", return_value=home):
                with redirect_stdout(StringIO()) as stdout:
                    self.assertEqual(command_doctor(ipc_request, sudo_runner), 1)

        output = stdout.getvalue()
        self.assertIn("config: missing:", output)
        self.assertIn("config: using defaults", output)
        self.assertIn("telegram token file: missing", output)
        self.assertIn("telegram allowed users: ERROR none configured", output)
        self.assertIn("sudo-request init", output)

    def test_command_doctor_returns_daemon_failure_when_status_unavailable(self) -> None:
        def ipc_request(_message):
            raise ConnectionRefusedError("socket refused")

        def sudo_runner(*_args, **_kwargs):
            return subprocess.CompletedProcess(["/usr/bin/sudo"], 1, "", "sudo: a password is required\n")

        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            cfg_dir = home / ".config" / "sudo-request"
            cfg_dir.mkdir(parents=True)
            token_path = cfg_dir / "telegram_bot_token"
            token_path.write_text("secret\n", encoding="utf-8")
            token_path.chmod(0o600)
            (cfg_dir / "config.toml").write_text(
                'telegram_bot_token_file = "~/.config/sudo-request/telegram_bot_token"\n'
                "telegram_allowed_user_ids = [123]\n",
                encoding="utf-8",
            )
            with patch("sudo_request.app.cli.doctor.Path.home", return_value=home):
                with redirect_stdout(StringIO()) as stdout:
                    self.assertEqual(command_doctor(ipc_request, sudo_runner), 2)

        self.assertIn("daemon status: unavailable: socket refused", stdout.getvalue())

    def test_telegram_token_status_warns_on_open_permissions(self) -> None:
        with TemporaryDirectory() as tmp:
            token_path = Path(tmp) / "token"
            token_path.write_text("secret\n", encoding="utf-8")
            token_path.chmod(0o644)
            line, code = telegram_token_status(token_path)

        self.assertEqual(code, 1)
        self.assertIn("WARNING too_open", line)


if __name__ == "__main__":
    unittest.main()
