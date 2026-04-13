from __future__ import annotations

import html
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .constants import BIN_PATH, EXIT_DAEMON_FAILURE, INSTALL_PREFIX, LAUNCHD_PLIST
from .sudoers import cleanup_broad_rule


def install_tool() -> int:
    if os.geteuid() != 0:
        print("install must be run with sudo/root", file=sys.stderr)
        return EXIT_DAEMON_FAILURE
    source_root = Path(__file__).resolve().parents[2]
    if INSTALL_PREFIX.exists():
        shutil.rmtree(INSTALL_PREFIX)
    shutil.copytree(
        source_root,
        INSTALL_PREFIX,
        ignore=shutil.ignore_patterns(".venv", "__pycache__", "*.pyc", ".pytest_cache", ".ruff_cache", "dist", "build", "*.egg-info"),
    )
    os.chown(INSTALL_PREFIX, 0, 0)
    for path in INSTALL_PREFIX.rglob("*"):
        try:
            os.chown(path, 0, 0)
        except PermissionError:
            pass
    BIN_PATH.parent.mkdir(parents=True, exist_ok=True)
    python_path = installed_python_path()
    wrapper = (
        "#!/bin/sh\n"
        f"export PYTHONPATH={INSTALL_PREFIX / 'src'}${{PYTHONPATH:+:$PYTHONPATH}}\n"
        f"exec {python_path} -m sudo_request \"$@\"\n"
    )
    BIN_PATH.write_text(wrapper, encoding="utf-8")
    os.chown(BIN_PATH, 0, 0)
    os.chmod(BIN_PATH, 0o755)
    daemon_code = install_daemon(BIN_PATH)
    if daemon_code != 0:
        return daemon_code
    print(f"installed sudo-request files: {INSTALL_PREFIX}")
    print(f"installed PATH wrapper: {BIN_PATH}")
    print("ensure /usr/local/bin is in PATH, then use: sudo-request run -- <command>")
    return 0


def install_daemon(executable: Path | None = None) -> int:
    if os.geteuid() != 0:
        print("install-daemon must be run with sudo/root", file=sys.stderr)
        return EXIT_DAEMON_FAILURE
    executable = executable or Path(sys.argv[0]).resolve(strict=False)
    Path("/Library/Logs/sudo-request").mkdir(parents=True, exist_ok=True)
    LAUNCHD_PLIST.write_text(render_launchd_plist(executable), encoding="utf-8")
    os.chown(LAUNCHD_PLIST, 0, 0)
    os.chmod(LAUNCHD_PLIST, 0o644)
    subprocess.run(["/bin/launchctl", "bootout", "system", str(LAUNCHD_PLIST)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    subprocess.run(["/bin/launchctl", "bootstrap", "system", str(LAUNCHD_PLIST)], check=False)
    print(f"installed {LAUNCHD_PLIST}")
    return 0


def render_launchd_plist(executable: Path) -> str:
    program = html.escape(str(executable), quote=True)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>dev.sudo-request.daemon</string>
  <key>ProgramArguments</key>
  <array>
    <string>{program}</string>
    <string>daemon</string>
    <string>--foreground</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/Library/Logs/sudo-request/stdout.log</string>
  <key>StandardErrorPath</key>
  <string>/Library/Logs/sudo-request/stderr.log</string>
</dict>
</plist>
"""


def uninstall_daemon() -> int:
    if os.geteuid() != 0:
        print("uninstall-daemon must be run with sudo/root", file=sys.stderr)
        return EXIT_DAEMON_FAILURE
    subprocess.run(["/bin/launchctl", "bootout", "system", str(LAUNCHD_PLIST)], check=False)
    LAUNCHD_PLIST.unlink(missing_ok=True)
    cleanup_broad_rule()
    print("uninstalled sudo-request daemon")
    return 0


def installed_python_path() -> str:
    for candidate in (Path("/opt/homebrew/bin/python3"), Path("/usr/local/bin/python3"), Path("/usr/bin/python3")):
        if candidate.exists():
            return str(candidate)
    found = shutil.which("python3")
    return found or sys.executable


def uninstall_tool() -> int:
    if os.geteuid() != 0:
        print("uninstall must be run with sudo/root", file=sys.stderr)
        return EXIT_DAEMON_FAILURE
    uninstall_daemon()
    BIN_PATH.unlink(missing_ok=True)
    if INSTALL_PREFIX.exists():
        shutil.rmtree(INSTALL_PREFIX)
    print("removed sudo-request installed files and PATH wrapper")
    return 0
