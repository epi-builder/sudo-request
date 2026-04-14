from __future__ import annotations

import subprocess
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sudo_request.app.cli.doctor import command_doctor, format_path_check, passwordless_sudo_status
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

        cfg = sample_config("/tmp/sudo-request-token", [123])
        with patch("sudo_request.app.cli.doctor.load_config", return_value=cfg):
            with redirect_stdout(StringIO()) as stdout:
                self.assertEqual(command_doctor(ipc_request, sudo_runner), 0)

        output = stdout.getvalue()
        self.assertIn("daemon status:", output)
        self.assertIn("WARNING: broad sudo rule is currently installed", output)
        self.assertIn("WARNING: broad sudo rule exists but daemon reports no active request", output)


if __name__ == "__main__":
    unittest.main()
