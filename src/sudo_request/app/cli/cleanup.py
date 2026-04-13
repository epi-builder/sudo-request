from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from sudo_request.app.cli.output import print_error
from sudo_request.lib.constants import DROPIN_PATH


IpcRequest = Callable[[dict[str, Any]], dict[str, Any]]


def close_request_with_diagnostics(request_id: str, ipc_request: IpcRequest, dropin_path: Path = DROPIN_PATH) -> None:
    try:
        close_response = ipc_request({"type": "close_request", "request_id": request_id})
    except Exception as exc:
        if dropin_path.exists():
            print_error(
                "cleanup_failed",
                action="close_request",
                request_id=request_id,
                broad_rule="installed",
                dropin_path=str(dropin_path),
                error_type=type(exc).__name__,
                message=str(exc),
            )
        else:
            print_error(
                "daemon_unreachable",
                action="close_request",
                request_id=request_id,
                broad_rule="not_installed",
                error_type=type(exc).__name__,
                message=str(exc),
            )
        return

    if close_response.get("ok"):
        return
    if dropin_path.exists():
        print_error(
            str(close_response.get("status") or "cleanup_failed"),
            action="close_request",
            request_id=request_id,
            broad_rule="installed",
            dropin_path=str(dropin_path),
            message=str(close_response.get("error") or close_response),
        )
    else:
        print_error(
            str(close_response.get("status") or "cleanup_failed"),
            action="close_request",
            request_id=request_id,
            broad_rule="not_installed",
            message=str(close_response.get("error") or close_response),
        )
