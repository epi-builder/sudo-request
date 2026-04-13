from __future__ import annotations

import json
import socket
from typing import Any


def send_json_line(sock: socket.socket, message: dict[str, Any]) -> None:
    data = json.dumps(message, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    sock.sendall(data)


def recv_json_line(sock_file) -> dict[str, Any]:
    line = sock_file.readline()
    if not line:
        raise EOFError("socket closed")
    if isinstance(line, bytes):
        line = line.decode("utf-8")
    value = json.loads(line)
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return value
