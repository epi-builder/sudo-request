from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sudo_request.app.cli.doctor import command_doctor
from sudo_request.app.cli.init_config import command_init
from sudo_request.app.cli.install_commands import command_update_itself, install_daemon, install_tool, uninstall_daemon, uninstall_tool
from sudo_request.app.cli.ipc_commands import command_cancel, command_cleanup, ipc_request
from sudo_request.app.cli.run import command_run
from sudo_request.app.cli.status import command_status
from sudo_request import __version__
from sudo_request.lib.constants import BIN_PATH


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sudo-request")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run")
    run_p.add_argument("--window-seconds", type=int, help="requested broad sudo window length; daemon enforces configured max")
    run_p.add_argument("cmd", nargs=argparse.REMAINDER)

    status_p = sub.add_parser("status")
    status_p.add_argument("--json", action="store_true", help="print raw daemon status JSON")
    cancel_p = sub.add_parser("cancel")
    cancel_p.add_argument("request_id")
    sub.add_parser("doctor")
    daemon_p = sub.add_parser("daemon")
    daemon_p.add_argument("--foreground", action="store_true")
    sub.add_parser("init", help="create user-level Telegram approval config")
    sub.add_parser("install", help="root-only install files and daemon from this checkout or installed package")
    sub.add_parser("uninstall", help="root-only remove installed files and daemon")
    sub.add_parser("install-daemon", help="root-only install or reload the launchd daemon")
    sub.add_parser("uninstall-daemon", help="root-only remove the launchd daemon")
    update_p = sub.add_parser("update-itself", help="update installed copy from a source checkout via Telegram approval")
    update_p.add_argument("--source", help="source checkout to install from; required when running from an installed copy")
    update_p.add_argument("--window-seconds", type=int, default=30, help="requested broad sudo window length for the self-update")
    sub.add_parser("cleanup")

    args = parser.parse_args(argv)
    if args.command == "run":
        cmd = list(args.cmd)
        if cmd and cmd[0] == "--":
            cmd = cmd[1:]
        return command_run(cmd, args.window_seconds)
    if args.command == "status":
        return command_status(ipc_request, json_output=args.json)
    if args.command == "cancel":
        return command_cancel(args.request_id, ipc_request)
    if args.command == "doctor":
        return command_doctor(ipc_request)
    if args.command == "daemon":
        if not args.foreground:
            print("daemon currently supports --foreground only", file=sys.stderr)
            return 2
        from sudo_request.app.daemon.server import run_foreground

        return run_foreground()
    if args.command == "init":
        return command_init()
    if args.command == "install":
        return install_tool()
    if args.command == "uninstall":
        return uninstall_tool()
    if args.command == "install-daemon":
        return install_daemon(BIN_PATH if BIN_PATH.exists() else Path(sys.argv[0]).resolve(strict=False))
    if args.command == "uninstall-daemon":
        return uninstall_daemon()
    if args.command == "update-itself":
        return command_update_itself(args.source, args.window_seconds)
    if args.command == "cleanup":
        return command_cleanup(ipc_request)
    return 2
