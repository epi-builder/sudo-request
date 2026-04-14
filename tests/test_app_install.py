from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sudo_request.app.cli.install_commands import copy_install_tree, project_root, render_launchd_plist, resolve_update_source, update_itself_command
from sudo_request.lib.constants import INSTALL_PREFIX
from tests.helpers import make_source_checkout


class InstallTests(unittest.TestCase):
    def test_project_root_points_to_repository_root(self) -> None:
        self.assertTrue((project_root() / "pyproject.toml").exists())
        self.assertTrue((project_root() / "src" / "sudo_request").exists())

    def test_resolve_update_source_accepts_source_checkout(self) -> None:
        with TemporaryDirectory() as tmp:
            root = make_source_checkout(Path(tmp))
            self.assertEqual(resolve_update_source(str(root)), root.resolve(strict=False))

    def test_resolve_update_source_rejects_installed_prefix_without_source(self) -> None:
        with self.assertRaises(ValueError):
            resolve_update_source(str(INSTALL_PREFIX))

    def test_update_itself_command_uses_source_pythonpath(self) -> None:
        with TemporaryDirectory() as tmp:
            root = make_source_checkout(Path(tmp))
            cmd = update_itself_command(str(root), python="/usr/bin/python3")
            resolved_root = root.resolve(strict=False)
        self.assertEqual(cmd[:3], ["/usr/bin/sudo", "/usr/bin/env", f"PYTHONPATH={resolved_root / 'src'}"])
        self.assertEqual(cmd[3:], ["/usr/bin/python3", "-m", "sudo_request", "install"])

    def test_render_launchd_plist_contains_program_arguments(self) -> None:
        plist = render_launchd_plist(Path("/usr/local/bin/sudo-request"))
        self.assertIn("<string>/usr/local/bin/sudo-request</string>", plist)
        self.assertIn("<string>daemon</string>", plist)
        self.assertIn("<string>--foreground</string>", plist)
        self.assertIn("<key>KeepAlive</key>", plist)

    def test_copy_install_tree_copies_source_checkout(self) -> None:
        with TemporaryDirectory() as tmp:
            root = make_source_checkout(Path(tmp) / "source")
            destination = Path(tmp) / "install"
            with patch("sudo_request.app.cli.install_commands.project_root", return_value=root):
                copy_install_tree(destination)
            self.assertTrue((destination / "pyproject.toml").exists())
            self.assertTrue((destination / "src" / "sudo_request").is_dir())

    def test_copy_install_tree_copies_imported_package_without_checkout(self) -> None:
        with TemporaryDirectory() as tmp:
            package = Path(tmp) / "site-packages" / "sudo_request"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text('__version__ = "0.1.0"\n', encoding="utf-8")
            destination = Path(tmp) / "install"
            with patch("sudo_request.app.cli.install_commands.project_root", return_value=Path(tmp) / "venv"):
                with patch("sudo_request.app.cli.install_commands.package_root", return_value=package):
                    copy_install_tree(destination)
            self.assertTrue((destination / "src" / "sudo_request" / "__init__.py").exists())


if __name__ == "__main__":
    unittest.main()
