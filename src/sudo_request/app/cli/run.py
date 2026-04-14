from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from sudo_request.app.cli.cleanup import close_request_with_diagnostics
from sudo_request.app.cli.ipc_commands import IPCRequest, ipc_request
from sudo_request.app.cli.output import print_daemon_unreachable, print_error, print_error_response
from sudo_request.lib.audit import append_jsonl_best_effort, user_audit_path
from sudo_request.lib.config import Config, load_config
from sudo_request.lib.constants import EXIT_DAEMON_FAILURE, EXIT_POLICY_BLOCK


def command_run(cmd: list[str], window_seconds: int | None = None, ipc_request_func: IPCRequest = ipc_request) -> int:
    if not cmd:
        print_error("policy_block", exit_code=EXIT_POLICY_BLOCK, action="run", message="sudo-request run requires a command after --")
        return EXIT_POLICY_BLOCK
    if window_seconds is not None and window_seconds <= 0:
        print_error("policy_block", exit_code=EXIT_POLICY_BLOCK, action="run", message="--window-seconds must be positive")
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
        response = ipc_request_with_heartbeat(request, cfg, ipc_request_func)
    except Exception as exc:
        return print_daemon_unreachable(exc, action="run_request")

    if not response.get("ok"):
        return print_error_response(response, fallback_exit_code=EXIT_DAEMON_FAILURE, action="run_request")

    request_id = str(response["request_id"])
    payload_hash = str(response["payload_hash"])
    print(f"sudo-request: approved; broad sudo window open for up to {response.get('window_seconds')}s", file=sys.stderr)
    append_jsonl_best_effort(user_audit_path(Path.home()), "command_started", {"request_id": request_id, "argv": cmd})
    print("sudo-request: running command...", file=sys.stderr)
    send_lifecycle_event_best_effort(request_id, payload_hash, "running", ipc_request_func=ipc_request_func)
    returncode = EXIT_DAEMON_FAILURE
    command_completed = False
    try:
        proc = subprocess.run(cmd)
        returncode = int(proc.returncode)
        command_completed = True
        return returncode
    finally:
        print(f"sudo-request: command exited with code {returncode}", file=sys.stderr)
        send_lifecycle_event_best_effort(
            request_id,
            payload_hash,
            "done" if command_completed else "failed",
            returncode,
            ipc_request_func=ipc_request_func,
        )
        close_request_with_diagnostics(request_id, ipc_request_func)
        subprocess.run(["/usr/bin/sudo", "-k"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        append_jsonl_best_effort(user_audit_path(Path.home()), "command_finished", {"request_id": request_id, "exit_code": returncode})


def send_lifecycle_event_best_effort(
    request_id: str,
    payload_hash: str,
    phase: str,
    exit_code: int | None = None,
    ipc_request_func: IPCRequest = ipc_request,
) -> None:
    message: dict[str, Any] = {
        "type": "lifecycle_event",
        "request_id": request_id,
        "payload_hash": payload_hash,
        "phase": phase,
    }
    if exit_code is not None:
        message["exit_code"] = exit_code
    try:
        ipc_request_func(message)
    except Exception:
        return


def ipc_request_with_heartbeat(message: dict[str, Any], cfg: Config, ipc_request_func: IPCRequest = ipc_request) -> dict[str, Any]:
    done = threading.Event()
    result: dict[str, Any] = {}
    error: list[BaseException] = []

    def worker() -> None:
        try:
            result.update(ipc_request_func(message))
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
