from __future__ import annotations

import json
import os
import socket
from collections.abc import Callable
from typing import Any

from sudo_request.app.cli.output import print_daemon_unreachable
from sudo_request.lib.constants import EXIT_POLICY_BLOCK, SOCKET_PATH
from sudo_request.lib.ipc import recv_json_line, send_json_line


IPCRequest = Callable[[dict[str, Any]], dict[str, Any]]


def ipc_request(message: dict[str, Any]) -> dict[str, Any]:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.connect(str(SOCKET_PATH))
        send_json_line(sock, message)
        return recv_json_line(sock.makefile("r", encoding="utf-8"))


def command_cancel(request_id: str, ipc_request_func: IPCRequest = ipc_request) -> int:
    return print_ipc({"type": "cancel", "request_id": request_id}, ipc_request_func)


def command_cleanup(ipc_request_func: IPCRequest = ipc_request) -> int:
    if os.geteuid() == 0:
        from sudo_request.lib.security.sudoers import cleanup_broad_rule

        cleanup_broad_rule()
        print("cleanup complete")
        return 0
    return print_ipc({"type": "cleanup"}, ipc_request_func)


def print_ipc(message: dict[str, Any], ipc_request_func: IPCRequest = ipc_request) -> int:
    try:
        response = ipc_request_func(message)
    except Exception as exc:
        return print_daemon_unreachable(exc, action=str(message.get("type") or "ipc"))
    print(json.dumps(response, indent=2, sort_keys=True))
    return 0 if response.get("ok") else int(response.get("exit_code", EXIT_POLICY_BLOCK))
