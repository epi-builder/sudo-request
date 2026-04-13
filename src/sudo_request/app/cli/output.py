from __future__ import annotations

import shlex
import sys
from typing import Any, TextIO

from sudo_request.lib.constants import EXIT_DAEMON_FAILURE, EXIT_POLICY_BLOCK


def print_error(
    status: str,
    *,
    exit_code: int | None = None,
    request_id: str | None = None,
    action: str | None = None,
    message: str | None = None,
    file: TextIO | None = None,
    **fields: Any,
) -> None:
    if file is None:
        file = sys.stderr
    parts = ["sudo-request: error", _field("status", status)]
    if exit_code is not None:
        parts.append(_field("exit_code", exit_code))
    if request_id:
        parts.append(_field("request_id", request_id))
    if action:
        parts.append(_field("action", action))
    for key, value in fields.items():
        if value is not None:
            parts.append(_field(key, value))
    if message:
        parts.append(_field("message", message))
    print(" ".join(parts), file=file)


def print_error_response(
    response: dict[str, Any],
    *,
    fallback_exit_code: int = EXIT_POLICY_BLOCK,
    action: str | None = None,
    file: TextIO | None = None,
) -> int:
    exit_code = int(response.get("exit_code", fallback_exit_code))
    print_error(
        str(response.get("status") or "unknown"),
        exit_code=exit_code,
        request_id=_optional_str(response.get("request_id")),
        action=action,
        message=_optional_str(response.get("error") or response.get("message")),
        file=file,
    )
    return exit_code


def print_daemon_unreachable(exc: BaseException, *, action: str | None = None, file: TextIO | None = None) -> int:
    print_error(
        "daemon_unreachable",
        exit_code=EXIT_DAEMON_FAILURE,
        action=action,
        error_type=type(exc).__name__,
        message=str(exc),
        file=file,
    )
    return EXIT_DAEMON_FAILURE


def _field(key: str, value: Any) -> str:
    return f"{key}={shlex.quote(str(value))}"


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None
