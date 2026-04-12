from __future__ import annotations

from pathlib import Path

APP_NAME = "sudo-request"
SOCKET_DIR = Path("/var/run/sudo-request")
SOCKET_PATH = SOCKET_DIR / "sudo-request.sock"
DROPIN_DIR = Path("/private/etc/sudoers.d")
DROPIN_PATH = DROPIN_DIR / "sudo-request-broad"
DAEMON_LOG = Path("/Library/Logs/sudo-request/daemon-audit.jsonl")
LAUNCHD_PLIST = Path("/Library/LaunchDaemons/dev.sudo-request.daemon.plist")
INSTALL_PREFIX = Path("/usr/local/libexec/sudo-request")
BIN_PATH = Path("/usr/local/bin/sudo-request")

EXIT_TIMEOUT = 124
EXIT_POLICY_BLOCK = 125
EXIT_DENIED = 126
EXIT_DAEMON_FAILURE = 127
