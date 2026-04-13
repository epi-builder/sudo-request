from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from typing import Any

from .decision import ApprovalResult, approval_callback_data, evaluate_callback, timeout_result
from .message import approval_message_text


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
        reply_markup = {
            "inline_keyboard": [[
                {"text": "Approve once", "callback_data": approval_callback_data("a", payload)},
                {"text": "Deny", "callback_data": approval_callback_data("d", payload)},
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
        self._post(
            "editMessageText",
            {"chat_id": chat_id, "message_id": message_id, "text": approval_message_text(payload, status), "reply_markup": {"inline_keyboard": []}},
            timeout=10,
        )

    def wait_for_approval_decision(self, payload: dict[str, Any], allowed_user_ids: list[int], timeout_seconds: int) -> ApprovalResult:
        deadline = time.time() + timeout_seconds
        offset = 0
        while time.time() < deadline:
            wait = max(1, min(20, int(deadline - time.time())))
            raw = self._get("getUpdates", {"timeout": wait, "offset": offset, "allowed_updates": json.dumps(["callback_query"])}, timeout=wait + 5)
            for update in raw.get("result", []):
                update_id = int(update["update_id"])
                offset = max(offset, update_id + 1)
                callback = update.get("callback_query")
                if not callback:
                    continue
                decision = evaluate_callback(callback, payload, allowed_user_ids)
                if decision.status == "ignored":
                    continue
                if decision.answer_text is not None and decision.callback_id is not None:
                    self.answer_callback(decision.callback_id, decision.answer_text)
                if decision.message_status is not None and decision.callback is not None:
                    try:
                        self.mark_callback_status(decision.callback, payload, decision.message_status)
                    except Exception:
                        pass
                if decision.is_terminal:
                    return ApprovalResult(decision.status, decision.approver_id)
        for message in payload.get("approval_messages", []):
            chat_id = message.get("chat_id")
            message_id = message.get("message_id")
            if chat_id is not None and message_id is not None:
                try:
                    self.mark_status(int(chat_id), int(message_id), payload, "EXPIRED")
                except Exception:
                    pass
        return timeout_result()
