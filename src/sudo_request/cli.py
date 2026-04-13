from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from .audit import append_jsonl_best_effort, user_audit_path
from .app.cleanup import close_request_with_diagnostics
from .config import Config, config_path, load_config
from .constants import BIN_PATH, EXIT_DAEMON_FAILURE, EXIT_POLICY_BLOCK, INSTALL_PREFIX, LAUNCHD_PLIST, SOCKET_PATH
from .daemon import run_foreground
from .app.install import install_daemon, install_tool, uninstall_daemon, uninstall_tool
from .ipc import recv_json_line, send_json_line
from .security.sudoers import cleanup_broad_rule


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sudo-request")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run")
    run_p.add_argument("--window-seconds", type=int, help="requested broad sudo window length; daemon enforces configured max")
    run_p.add_argument("cmd", nargs=argparse.REMAINDER)

    sub.add_parser("status")
    cancel_p = sub.add_parser("cancel")
    cancel_p.add_argument("request_id")
    sub.add_parser("doctor")
    daemon_p = sub.add_parser("daemon")
    daemon_p.add_argument("--foreground", action="store_true")
    sub.add_parser("install")
    sub.add_parser("uninstall")
    sub.add_parser("install-daemon")
    sub.add_parser("uninstall-daemon")
    sub.add_parser("cleanup")

    args = parser.parse_args(argv)
    if args.command == "run":
        cmd = list(args.cmd)
        if cmd and cmd[0] == "--":
            cmd = cmd[1:]
        return command_run(cmd, args.window_seconds)
    if args.command == "status":
        return print_ipc({"type": "status"})
    if args.command == "cancel":
        return print_ipc({"type": "cancel", "request_id": args.request_id})
    if args.command == "doctor":
        return command_doctor()
    if args.command == "daemon":
        if not args.foreground:
            print("daemon currently supports --foreground only", file=sys.stderr)
            return 2
        return run_foreground()
    if args.command == "install":
        return install_tool()
    if args.command == "uninstall":
        return uninstall_tool()
    if args.command == "install-daemon":
        return install_daemon(BIN_PATH if BIN_PATH.exists() else Path(sys.argv[0]).resolve(strict=False))
    if args.command == "uninstall-daemon":
        return uninstall_daemon()
    if args.command == "cleanup":
        if os.geteuid() == 0:
            cleanup_broad_rule()
            print("cleanup complete")
            return 0
        return print_ipc({"type": "cleanup"})
    return 2


def command_run(cmd: list[str], window_seconds: int | None = None) -> int:
    if not cmd:
        print("sudo-request run requires a command after --", file=sys.stderr)
        return EXIT_POLICY_BLOCK
    if window_seconds is not None and window_seconds <= 0:
        print("sudo-request: --window-seconds must be positive", file=sys.stderr)
        return EXIT_POLICY_BLOCK
    subprocess.run(["/usr/bin/sudo", "-k"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    cfg = load_config(Path.home())
    request = {
        "type": "run_request",
        "argv": cmd,
        "cwd": os.getcwd(),
        "path": os.environ.get("PATH", os.defpath),
    }
    if window_seconds is not None:
        request["window_seconds"] = window_seconds
    print("sudo-request: approval requested; waiting for Telegram approval...", file=sys.stderr)
    try:
        response = ipc_request_with_heartbeat(request, cfg)
    except Exception as exc:
        print(f"sudo-request: daemon request failed: {exc}", file=sys.stderr)
        return EXIT_DAEMON_FAILURE

    if not response.get("ok"):
        print(f"sudo-request: {response.get('status')}: {response.get('error', '')}", file=sys.stderr)
        return int(response.get("exit_code", EXIT_DAEMON_FAILURE))

    request_id = str(response["request_id"])
    print(f"sudo-request: approved; broad sudo window open for up to {response.get('window_seconds')}s", file=sys.stderr)
    append_jsonl_best_effort(user_audit_path(Path.home()), "command_started", {"request_id": request_id, "argv": cmd})
    try:
        proc = subprocess.run(cmd)
        return int(proc.returncode)
    finally:
        close_request_with_diagnostics(request_id, ipc_request)
        subprocess.run(["/usr/bin/sudo", "-k"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        append_jsonl_best_effort(user_audit_path(Path.home()), "command_finished", {"request_id": request_id})


def ipc_request(message: dict[str, Any]) -> dict[str, Any]:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.connect(str(SOCKET_PATH))
        send_json_line(sock, message)
        return recv_json_line(sock.makefile("r", encoding="utf-8"))


def ipc_request_with_heartbeat(message: dict[str, Any], cfg: Config) -> dict[str, Any]:
    done = threading.Event()
    result: dict[str, Any] = {}
    error: list[BaseException] = []

    def worker() -> None:
        try:
            result.update(ipc_request(message))
        except BaseException as exc:
            error.append(exc)
        finally:
            done.set()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    while not done.wait(cfg.approval_wait_heartbeat_seconds):
        print("sudo-request: still waiting for Telegram approval...", file=sys.stderr)
    thread.join()
    if error:
        raise error[0]
    return result


def print_ipc(message: dict[str, Any]) -> int:
    try:
        response = ipc_request(message)
    except Exception as exc:
        print(f"sudo-request: daemon request failed: {exc}", file=sys.stderr)
        return EXIT_DAEMON_FAILURE
    print(json.dumps(response, indent=2, sort_keys=True))
    return 0 if response.get("ok") else int(response.get("exit_code", EXIT_POLICY_BLOCK))


def command_doctor() -> int:
    home = Path.home()
    print(f"config: {config_path(home)}")
    try:
        cfg = load_config(home)
        print("config: ok")
        print(f"telegram token file: {cfg.telegram_bot_token_file} exists={cfg.telegram_bot_token_file.exists()}")
        print(f"telegram allowed users: {len(cfg.telegram_allowed_user_ids)} configured")
        print(f"approval timeout: {cfg.approval_timeout_seconds}s")
        print(f"approval wait heartbeat: {cfg.approval_wait_heartbeat_seconds}s")
        print(f"broad window default: {cfg.broad_window_seconds_default}s")
        print(f"broad window max: {cfg.broad_window_seconds_max}s")
    except Exception as exc:
        print(f"config: error: {exc}")
    print(f"daemon socket: {SOCKET_PATH} exists={SOCKET_PATH.exists()}")
    print(f"launchd plist: {LAUNCHD_PLIST} exists={LAUNCHD_PLIST.exists()}")
    print(f"installed prefix: {INSTALL_PREFIX} exists={INSTALL_PREFIX.exists()}")
    print(f"PATH wrapper: {BIN_PATH} exists={BIN_PATH.exists()}")
    print(f"PATH contains /usr/local/bin: {'/usr/local/bin' in os.environ.get('PATH', '').split(os.pathsep)}")
    print(f"sudoers.d: /private/etc/sudoers.d exists={Path('/private/etc/sudoers.d').exists()}")
    try:
        response = ipc_request({"type": "status"})
        print(f"daemon status: {json.dumps(response, sort_keys=True)}")
    except Exception as exc:
        print(f"daemon status: unavailable: {exc}")
    return 0
