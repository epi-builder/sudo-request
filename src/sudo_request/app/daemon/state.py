from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from sudo_request.app.daemon.lifecycle import RequestLifecycle, RequestPhase


class DaemonState:
    def __init__(self, state_path: Path | None = None) -> None:
        self.lock = threading.Lock()
        self.active_request: RequestLifecycle | None = None
        self.cleanup_timer: threading.Timer | None = None
        self.state_path = state_path

    @property
    def active_request_id(self) -> str | None:
        return self.active_request.request_id if self.active_request is not None else None

    @property
    def active_user(self) -> str | None:
        return self.active_request.user if self.active_request is not None else None

    def begin(self, request: RequestLifecycle) -> bool:
        with self.lock:
            if self.active_request is not None:
                return False
            self.active_request = request
            self._persist_locked()
            return True

    def set_phase(self, request_id: str, phase: RequestPhase, exit_code: int | None = None) -> bool:
        with self.lock:
            if self.active_request is None or self.active_request.request_id != request_id:
                return False
            self.active_request.phase = phase
            if exit_code is not None:
                self.active_request.exit_code = exit_code
            self._persist_locked()
            return True

    def set_window_expires_at(self, request_id: str, window_expires_at: int) -> bool:
        with self.lock:
            if self.active_request is None or self.active_request.request_id != request_id:
                return False
            self.active_request.window_expires_at = window_expires_at
            self._persist_locked()
            return True

    def set_approval_messages(self, request_id: str, approval_messages: list[dict[str, int]]) -> bool:
        with self.lock:
            if self.active_request is None or self.active_request.request_id != request_id:
                return False
            self.active_request.approval_messages = approval_messages
            self._persist_locked()
            return True

    def set_cleanup_timer(self, request_id: str, timer: threading.Timer) -> bool:
        with self.lock:
            if self.active_request is None or self.active_request.request_id != request_id:
                return False
            self.cleanup_timer = timer
            return True

    def clear(self, request_id: str | None = None) -> None:
        with self.lock:
            if request_id is not None and self.active_request_id != request_id:
                return
            self.active_request = None
            if self.cleanup_timer is not None:
                self.cleanup_timer.cancel()
                self.cleanup_timer = None
            self._persist_locked()

    def status(self) -> dict[str, Any]:
        with self.lock:
            request = self.active_request
            return {
                "active_request_id": request.request_id if request is not None else None,
                "active_user": request.user if request is not None else None,
                "active_request": request.to_status_dict() if request is not None else None,
            }

    def notification_payload(self, request_id: str | None = None) -> tuple[int, dict[str, Any]] | None:
        with self.lock:
            request = self.active_request
            if request is None:
                return None
            if request_id is not None and request.request_id != request_id:
                return None
            return request.uid, request.to_approval_payload()

    def load(self) -> RequestLifecycle | None:
        if self.state_path is None:
            return None
        try:
            with self.state_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            request = RequestLifecycle.from_dict(data)
        except FileNotFoundError:
            return None
        except (OSError, ValueError, TypeError, KeyError):
            self._remove_state_file()
            return None
        with self.lock:
            self.active_request = request
        return request

    def _persist_locked(self) -> None:
        if self.state_path is None:
            return
        if self.active_request is None:
            self._remove_state_file()
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.state_path.with_name(f".{self.state_path.name}.{os.getpid()}.tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(self.active_request.to_dict(), f, sort_keys=True, separators=(",", ":"))
            f.write("\n")
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, self.state_path)

    def _remove_state_file(self) -> None:
        if self.state_path is None:
            return
        try:
            self.state_path.unlink()
        except FileNotFoundError:
            pass
