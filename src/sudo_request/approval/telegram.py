from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from .message import approval_message_text


@dataclass(frozen=True)
class ApprovalResult:
    status: str
    approver_id: int | None = None
    message: str | None = None


class TelegramClient:
    def __init__(self, token: str) -> None:
        self.token = token
        self.base = f"https://api.telegram.org/bot{token}"

    def _post(self, method: str, payload: dict[str, Any], timeout: int = 30) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(f"{self.base}/{method}", data=data, method="POST")
        request.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = json.loads(response.read().decode("utf-8"))
        if not raw.get("ok"):
            raise RuntimeError(f"Telegram {method} failed: {raw}")
        result = raw.get("result")
        return result if isinstance(result, dict) else {"result": result}

    def _get(self, method: str, params: dict[str, Any], timeout: int = 35) -> dict[str, Any]:
        query = urllib.parse.urlencode(params)
        with urllib.request.urlopen(f"{self.base}/{method}?{query}", timeout=timeout) as response:
            raw = json.loads(response.read().decode("utf-8"))
        if not raw.get("ok"):
            raise RuntimeError(f"Telegram {method} failed: {raw}")
        return raw

    def send_approval_request(self, chat_id: int, payload: dict[str, Any]) -> int:
        text = approval_message_text(payload, "PENDING")
        nonce = payload["nonce"]
        request_id = payload["request_id"]
        digest = payload["payload_hash"]
        digest_prefix = digest[:16]
        nonce_prefix = nonce[:8]
        reply_markup = {
            "inline_keyboard": [[
                {"text": "Approve once", "callback_data": f"a:{request_id}:{digest_prefix}:{nonce_prefix}"},
                {"text": "Deny", "callback_data": f"d:{request_id}:{digest_prefix}:{nonce_prefix}"},
            ]]
        }
        result = self._post("sendMessage", {"chat_id": chat_id, "text": text, "reply_markup": reply_markup})
        return int(result["message_id"])

    def answer_callback(self, callback_id: str, text: str) -> None:
        self._post("answerCallbackQuery", {"callback_query_id": callback_id, "text": text}, timeout=10)

    def mark_callback_status(self, callback: dict[str, Any], payload: dict[str, Any], status: str) -> None:
        message = callback.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        message_id = message.get("message_id")
        if chat_id is None or message_id is None:
            return
        self.mark_status(int(chat_id), int(message_id), payload, status)

    def mark_status(self, chat_id: int, message_id: int, payload: dict[str, Any], status: str) -> None:
        try:
            self._post(
                "editMessageText",
                {"chat_id": chat_id, "message_id": message_id, "text": approval_message_text(payload, status), "reply_markup": {"inline_keyboard": []}},
                timeout=10,
            )
        except Exception:
            return

    def wait_for_approval_decision(self, payload: dict[str, Any], allowed_user_ids: list[int], timeout_seconds: int) -> ApprovalResult:
        deadline = time.time() + timeout_seconds
        offset = 0
        expected_request_id = payload["request_id"]
        expected_hash = payload["payload_hash"]
        expected_nonce = payload["nonce"]
        while time.time() < deadline:
            wait = max(1, min(20, int(deadline - time.time())))
            raw = self._get("getUpdates", {"timeout": wait, "offset": offset, "allowed_updates": json.dumps(["callback_query"])}, timeout=wait + 5)
            for update in raw.get("result", []):
                update_id = int(update["update_id"])
                offset = max(offset, update_id + 1)
                callback = update.get("callback_query")
                if not callback:
                    continue
                user = callback.get("from", {})
                user_id = int(user.get("id", 0))
                data = str(callback.get("data", ""))
                parts = data.split(":")
                if len(parts) != 4:
                    continue
                action, request_id, digest, nonce = parts
                if request_id != expected_request_id or digest != expected_hash[:16] or nonce != expected_nonce[:8]:
                    continue
                if user_id not in allowed_user_ids:
                    self.answer_callback(str(callback["id"]), "Not allowed")
                    continue
                if action == "a":
                    self.answer_callback(str(callback["id"]), "Approved")
                    self.mark_callback_status(callback, payload, "APPROVED")
                    return ApprovalResult("approved", user_id)
                if action == "d":
                    self.answer_callback(str(callback["id"]), "Denied")
                    self.mark_callback_status(callback, payload, "DENIED")
                    return ApprovalResult("denied", user_id)
        for message in payload.get("approval_messages", []):
            chat_id = message.get("chat_id")
            message_id = message.get("message_id")
            if chat_id is not None and message_id is not None:
                self.mark_status(int(chat_id), int(message_id), payload, "EXPIRED")
        return ApprovalResult("timeout", None, "request expired by timeout")
