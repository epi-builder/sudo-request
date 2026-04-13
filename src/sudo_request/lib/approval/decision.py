from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ApprovalResult:
    status: str
    approver_id: int | None = None
    message: str | None = None


@dataclass(frozen=True)
class CallbackData:
    action: str
    request_id: str
    payload_hash_prefix: str
    nonce_prefix: str


@dataclass(frozen=True)
class CallbackDecision:
    status: str
    callback_id: str | None = None
    approver_id: int | None = None
    answer_text: str | None = None
    message_status: str | None = None
    callback: dict[str, Any] | None = None

    @property
    def is_terminal(self) -> bool:
        return self.status in {"approved", "denied"}


def approval_callback_data(action: str, payload: dict[str, Any]) -> str:
    if action not in {"a", "d"}:
        raise ValueError(f"unknown approval callback action: {action}")
    return f"{action}:{payload['request_id']}:{payload['payload_hash'][:16]}:{payload['nonce'][:8]}"


def parse_callback_data(data: str) -> CallbackData | None:
    parts = data.split(":")
    if len(parts) != 4:
        return None
    action, request_id, payload_hash_prefix, nonce_prefix = parts
    if action not in {"a", "d"}:
        return None
    if not request_id or not payload_hash_prefix or not nonce_prefix:
        return None
    return CallbackData(action, request_id, payload_hash_prefix, nonce_prefix)


def callback_matches_payload(callback_data: CallbackData, payload: dict[str, Any]) -> bool:
    return (
        callback_data.request_id == payload["request_id"]
        and callback_data.payload_hash_prefix == payload["payload_hash"][:16]
        and callback_data.nonce_prefix == payload["nonce"][:8]
    )


def evaluate_callback(
    callback: dict[str, Any],
    payload: dict[str, Any],
    allowed_user_ids: list[int],
) -> CallbackDecision:
    callback_id = str(callback.get("id", ""))
    user = callback.get("from") or {}
    try:
        user_id = int(user.get("id", 0))
    except (TypeError, ValueError):
        user_id = 0

    data = parse_callback_data(str(callback.get("data", "")))
    if data is None or not callback_matches_payload(data, payload):
        return CallbackDecision("ignored")

    if user_id not in allowed_user_ids:
        return CallbackDecision(
            "not_allowed",
            callback_id=callback_id,
            approver_id=user_id,
            answer_text="Not allowed",
            callback=callback,
        )

    if data.action == "a":
        return CallbackDecision(
            "approved",
            callback_id=callback_id,
            approver_id=user_id,
            answer_text="Approved",
            message_status="APPROVED",
            callback=callback,
        )

    return CallbackDecision(
        "denied",
        callback_id=callback_id,
        approver_id=user_id,
        answer_text="Denied",
        message_status="DENIED",
        callback=callback,
    )


def timeout_result() -> ApprovalResult:
    return ApprovalResult("timeout", None, "request expired by timeout")
