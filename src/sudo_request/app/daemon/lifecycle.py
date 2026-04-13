from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RequestPhase(str, Enum):
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    WINDOW_OPEN = "window_open"
    RUNNING = "running"
    DONE = "done"
    DENIED = "denied"
    EXPIRED = "expired"
    FAILED = "failed"
    CANCELLED = "cancelled"
    CLOSED = "closed"


@dataclass
class RequestLifecycle:
    request_id: str
    payload_hash: str
    uid: int
    user: str
    host: str
    argv: list[str]
    cwd: str
    resolved_executable: str
    parent_process: dict[str, Any]
    expires_at: int
    requested_window_seconds: int
    max_window_seconds: int
    window_expires_at: int | None = None
    phase: RequestPhase = RequestPhase.PENDING_APPROVAL
    approval_messages: list[dict[str, int]] = field(default_factory=list)
    exit_code: int | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> RequestLifecycle:
        return cls(
            request_id=str(payload["request_id"]),
            payload_hash=str(payload["payload_hash"]),
            uid=int(payload["uid"]),
            user=str(payload["user"]),
            host=str(payload["host"]),
            argv=list(payload["argv"]),
            cwd=str(payload["cwd"]),
            resolved_executable=str(payload["resolved_executable"]),
            parent_process=dict(payload["parent_process"]),
            expires_at=int(payload["expires_at"]),
            requested_window_seconds=int(payload["requested_window_seconds"]),
            max_window_seconds=int(payload["max_window_seconds"]),
            approval_messages=[dict(item) for item in payload.get("approval_messages", [])],
        )

    def to_status_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "payload_hash": self.payload_hash,
            "phase": self.phase.value,
            "uid": self.uid,
            "user": self.user,
            "host": self.host,
            "argv": self.argv,
            "cwd": self.cwd,
            "resolved_executable": self.resolved_executable,
            "parent_process": self.parent_process,
            "expires_at": self.expires_at,
            "requested_window_seconds": self.requested_window_seconds,
            "max_window_seconds": self.max_window_seconds,
            "window_expires_at": self.window_expires_at,
            "approval_messages": self.approval_messages,
            "exit_code": self.exit_code,
        }

    def to_approval_payload(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "payload_hash": self.payload_hash,
            "uid": self.uid,
            "user": self.user,
            "host": self.host,
            "argv": self.argv,
            "cwd": self.cwd,
            "resolved_executable": self.resolved_executable,
            "parent_process": self.parent_process,
            "expires_at": self.expires_at,
            "requested_window_seconds": self.requested_window_seconds,
            "max_window_seconds": self.max_window_seconds,
            "approval_messages": self.approval_messages,
        }
