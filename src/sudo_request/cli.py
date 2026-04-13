from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from .audit import append_jsonl_best_effort, user_audit_path
from .config import Config, config_path, load_config
from .constants import BIN_PATH, DROPIN_PATH, EXIT_DAEMON_FAILURE, EXIT_POLICY_BLOCK, INSTALL_PREFIX, LAUNCHD_PLIST, SOCKET_PATH
from .daemon import run_foreground
from .ipc import recv_json_line, send_json_line
from .sudoers import cleanup_broad_rule


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
        close_request_with_diagnostics(request_id)
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


def close_request_with_diagnostics(request_id: str) -> None:
    try:
        close_response = ipc_request({"type": "close_request", "request_id": request_id})
    except Exception as exc:
        if DROPIN_PATH.exists():
            print(
                f"sudo-request: cleanup request failed and broad sudo rule still exists at {DROPIN_PATH}: {exc}",
                file=sys.stderr,
            )
        else:
            print(
                "sudo-request: cleanup request could not reach daemon, but broad sudo rule is not installed",
                file=sys.stderr,
            )
        return

    if close_response.get("ok"):
        return
    if DROPIN_PATH.exists():
        print(f"sudo-request: cleanup warning: {close_response}; broad sudo rule still exists at {DROPIN_PATH}", file=sys.stderr)
    else:
        print(f"sudo-request: cleanup warning: {close_response}; broad sudo rule is not installed", file=sys.stderr)


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
