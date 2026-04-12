from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


def user_audit_path(home: Path) -> Path:
    return home / "Library" / "Logs" / "sudo-request" / "audit.jsonl"


def append_jsonl(path: Path, event: str, fields: dict[str, Any]) -> None:
    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": event,
        **fields,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    try:
        os.chmod(path, 0o600)
    except PermissionError:
        pass


def append_jsonl_best_effort(path: Path, event: str, fields: dict[str, Any]) -> bool:
    try:
        append_jsonl(path, event, fields)
        return True
    except OSError:
        return False
