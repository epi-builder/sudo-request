from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sudo_request.lib.constants import DROPIN_PATH


IpcRequest = Callable[[dict[str, Any]], dict[str, Any]]


def close_request_with_diagnostics(request_id: str, ipc_request: IpcRequest, dropin_path: Path = DROPIN_PATH) -> None:
    try:
        close_response = ipc_request({"type": "close_request", "request_id": request_id})
    except Exception as exc:
        if dropin_path.exists():
            print(
                f"sudo-request: cleanup request failed and broad sudo rule still exists at {dropin_path}: {exc}",
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
    if dropin_path.exists():
        print(f"sudo-request: cleanup warning: {close_response}; broad sudo rule still exists at {dropin_path}", file=sys.stderr)
    else:
        print(f"sudo-request: cleanup warning: {close_response}; broad sudo rule is not installed", file=sys.stderr)
