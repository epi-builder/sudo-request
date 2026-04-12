from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import socket
import time
from pathlib import Path
from typing import Any

SAFE_USER_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")


def validate_username(user: str) -> None:
    if not user or any(ch not in SAFE_USER_CHARS for ch in user):
        raise ValueError(f"unsafe user name: {user!r}")


def resolve_executable(argv: list[str], path_value: str | None = None, cwd: str | None = None) -> str:
    if not argv:
        raise ValueError("empty command argv")
    exe = argv[0]
    if "/" in exe:
        candidate = Path(exe)
        if not candidate.is_absolute():
            candidate = Path(cwd or os.getcwd()) / candidate
        resolved = candidate.resolve(strict=False)
        if not resolved.exists():
            raise ValueError(f"executable does not exist: {exe}")
        if not os.access(resolved, os.X_OK):
            raise ValueError(f"executable is not executable: {resolved}")
        return str(resolved)
    found = shutil.which(exe, path=path_value)
    if not found:
        raise ValueError(f"command not found: {exe}")
    return str(Path(found).resolve(strict=False))


def reject_recursive_command(argv: list[str], resolved_executable: str) -> None:
    names = {Path(argv[0]).name if argv else "", Path(resolved_executable).name}
    if "sudo-request" in names:
        raise ValueError("refusing to run sudo-request through sudo-request")


def canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def payload_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def build_payload(uid: int, user: str, home: str, cwd: str, argv: list[str], path_value: str, timeout_seconds: int) -> dict[str, Any]:
    resolved = resolve_executable(argv, path_value, cwd)
    reject_recursive_command(argv, resolved)
    expires_at = int(time.time()) + timeout_seconds
    payload: dict[str, Any] = {
        "request_id": secrets.token_urlsafe(18),
        "nonce": secrets.token_urlsafe(18),
        "uid": uid,
        "user": user,
        "home": home,
        "host": socket.gethostname(),
        "cwd": str(Path(cwd).resolve(strict=False)),
        "argv": argv,
        "resolved_executable": resolved,
        "path": path_value,
        "parent_process": {"pid": os.getppid()},
        "expires_at": expires_at,
    }
    payload["payload_hash"] = payload_hash({k: v for k, v in payload.items() if k != "payload_hash"})
    return payload
