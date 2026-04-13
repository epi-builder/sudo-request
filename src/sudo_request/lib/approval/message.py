from __future__ import annotations

from datetime import datetime
from typing import Any


def approval_message_text(payload: dict[str, Any], status: str) -> str:
    title = f"sudo-request [{status}]"
    return "\n".join([
        title,
        "=" * len(title),
        "",
        "Request",
        f"  Host: {payload['host']}",
        f"  User: {payload['user']} (uid={payload['uid']})",
        f"  Cwd:  {payload['cwd']}",
        "",
        "Command",
        f"  {format_argv(payload['argv'])}",
        f"  Resolved: {payload['resolved_executable']}",
        f"  Parent:   {format_parent_process(payload['parent_process'])}",
        "",
        "Approval",
        f"  Window:  {payload['requested_window_seconds']}s (max {payload['max_window_seconds']}s)",
        f"  Expires: {format_local_timestamp(payload['expires_at'])}",
        f"  Hash:    {payload['payload_hash']}",
        "",
        "Security",
        "  Broad mode opens passwordless sudo for this local user.",
        "  Any same-user process can use sudo while the window is open.",
    ])


def cleanup_critical_message_text(payload: dict[str, Any] | None, source: str, dropin_path: str) -> str:
    title = "sudo-request [CRITICAL cleanup_failed]"
    lines = [
        title,
        "=" * len(title),
        "",
        "Cleanup",
        f"  Source:  {source}",
        f"  Drop-in: {dropin_path}",
        "  Status:  cleanup failed; broad sudo rule may still be installed.",
        "",
    ]
    if payload is None:
        lines.extend([
            "Request",
            "  Active request details are unavailable.",
            "",
        ])
    else:
        lines.extend([
            "Request",
            f"  Host: {payload['host']}",
            f"  User: {payload['user']} (uid={payload['uid']})",
            f"  Cwd:  {payload['cwd']}",
            "",
            "Command",
            f"  {format_argv(payload['argv'])}",
            f"  Resolved: {payload['resolved_executable']}",
            "",
            "Approval",
            f"  Window:  {payload['requested_window_seconds']}s (max {payload['max_window_seconds']}s)",
            f"  Expires: {format_local_timestamp(payload['expires_at'])}",
            f"  Hash:    {payload['payload_hash']}",
            "",
        ])
    lines.extend([
        "Action",
        "  Run sudo-request status and remove the drop-in if it is stale.",
        "  Passwordless sudo may remain available for this local user.",
    ])
    return "\n".join(lines)


def format_parent_process(parent_process: Any) -> str:
    if isinstance(parent_process, dict) and "pid" in parent_process:
        return f"pid={parent_process['pid']}"
    return str(parent_process)


def format_argv(argv: list[str]) -> str:
    return " ".join(_quote_arg(arg) for arg in argv)


def _quote_arg(arg: str) -> str:
    if arg and all(ch.isalnum() or ch in "._-/:=+" for ch in arg):
        return arg
    return "'" + arg.replace("'", "'\\''") + "'"


def format_local_timestamp(epoch_seconds: int | float | str) -> str:
    epoch = int(epoch_seconds)
    dt = datetime.fromtimestamp(epoch).astimezone()
    return f"{dt.strftime('%Y-%m-%d %H:%M:%S %Z %z')} ({epoch})"
