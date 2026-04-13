from __future__ import annotations

import json
import shlex
from collections.abc import Callable
from datetime import datetime
from typing import Any

from sudo_request.lib.constants import EXIT_DAEMON_FAILURE, EXIT_POLICY_BLOCK

IPCRequest = Callable[[dict[str, Any]], dict[str, Any]]


def command_status(ipc_request: IPCRequest, *, json_output: bool = False) -> int:
    try:
        response = ipc_request({"type": "status"})
    except Exception as exc:
        print(f"sudo-request: daemon request failed: {exc}")
        return EXIT_DAEMON_FAILURE

    if json_output:
        print(json.dumps(response, indent=2, sort_keys=True))
    else:
        print(format_status(response))
    return 0 if response.get("ok") else int(response.get("exit_code", EXIT_POLICY_BLOCK))


def format_status(response: dict[str, Any]) -> str:
    lines: list[str] = []
    daemon_pid = response.get("daemon_pid")
    lines.append(f"daemon: {'ok' if response.get('ok') else 'error'}" + (f" pid={daemon_pid}" if daemon_pid is not None else ""))

    active_request = response.get("active_request")
    dropin_exists = bool(response.get("dropin_exists"))
    if active_request:
        lines.extend(format_active_request(active_request))
    else:
        lines.append("state: idle")

    lines.append(f"broad sudo rule: {'installed' if dropin_exists else 'not installed'}")
    if dropin_exists:
        lines.append("WARNING: broad sudo rule is currently installed")
    if dropin_exists and not active_request:
        lines.append("WARNING: broad sudo rule exists but daemon reports no active request")

    if not response.get("ok"):
        status = response.get("status", "unknown")
        error = response.get("error")
        lines.append(f"error: {status}" + (f": {error}" if error else ""))
    return "\n".join(lines)


def format_active_request(active_request: dict[str, Any]) -> list[str]:
    lines = [
        "state: active",
        f"request id: {active_request.get('request_id', '')}",
        f"phase: {active_request.get('phase', '')}",
        f"user: {active_request.get('user', '')}",
        f"command: {format_command(active_request.get('argv'))}",
        f"cwd: {active_request.get('cwd', '')}",
        f"requested window: {active_request.get('requested_window_seconds', '')}s",
    ]
    expires_at = active_request.get("expires_at")
    if expires_at is not None:
        lines.append(f"approval expires: {format_local_timestamp(expires_at)}")
    window_expires_at = active_request.get("window_expires_at")
    if window_expires_at is not None:
        lines.append(f"window expires: {format_local_timestamp(window_expires_at)}")
    exit_code = active_request.get("exit_code")
    if exit_code is not None:
        lines.append(f"exit code: {exit_code}")
    return lines


def format_command(argv: Any) -> str:
    if not isinstance(argv, list):
        return ""
    return shlex.join(str(part) for part in argv)


def format_local_timestamp(value: Any) -> str:
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return str(value)
    return datetime.fromtimestamp(timestamp).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
