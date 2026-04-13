from __future__ import annotations

import threading
from typing import Any, Callable

from sudo_request.app.daemon.lifecycle import RequestPhase
from sudo_request.app.daemon.state import DaemonState
from sudo_request.app.daemon.sudo_window import close_broad_window
from sudo_request.lib.audit import append_jsonl
from sudo_request.lib.constants import DAEMON_LOG

CleanupFailureNotifier = Callable[[tuple[int, dict[str, Any]] | None, str, str], None]


def schedule_watchdog(
    state: DaemonState,
    request_id: str,
    window_seconds: int,
    notify_cleanup_failed: CleanupFailureNotifier,
) -> threading.Timer:
    timer = threading.Timer(window_seconds, watchdog_cleanup, args=(state, request_id, notify_cleanup_failed))
    timer.daemon = True
    state.set_cleanup_timer(request_id, timer)
    timer.start()
    return timer


def watchdog_cleanup(
    state: DaemonState,
    request_id: str,
    notify_cleanup_failed: CleanupFailureNotifier,
) -> None:
    notification = state.notification_payload(request_id)
    cleanup_ok = close_broad_window(retries=10, delay_seconds=0.5)
    state.set_phase(request_id, RequestPhase.EXPIRED if cleanup_ok else RequestPhase.FAILED)
    if not cleanup_ok:
        notify_cleanup_failed(notification, "watchdog", request_id)
    state.clear(request_id)
    append_jsonl(DAEMON_LOG, "window_watchdog_cleanup", {"request_id": request_id, "cleanup_ok": cleanup_ok})
