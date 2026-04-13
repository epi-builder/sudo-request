from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


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

    def send_approval(self, chat_id: int, payload: dict[str, Any]) -> int:
        text = (
            "sudo-request broad sudo window\n\n"
            f"Host: {payload['host']}\n"
            f"User: {payload['user']} uid={payload['uid']}\n"
            f"Working directory: {payload['cwd']}\n"
            f"Requested command: {format_argv(payload['argv'])}\n"
            f"Resolved executable: {payload['resolved_executable']}\n"
            f"Parent process: {payload['parent_process']}\n"
            f"Requested sudo window: {payload['requested_window_seconds']}s (max {payload['max_window_seconds']}s)\n"
            f"Expires at: {payload['expires_at']}\n"
            f"SHA256 payload hash: {payload['payload_hash']}\n\n"
            "WARNING: while approved, this local user can run passwordless sudo from any process."
        )
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

    def wait_for_decision(self, payload: dict[str, Any], allowed_user_ids: list[int], timeout_seconds: int) -> ApprovalResult:
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
                    return ApprovalResult("approved", user_id)
                if action == "d":
                    self.answer_callback(str(callback["id"]), "Denied")
                    return ApprovalResult("denied", user_id)
        return ApprovalResult("timeout", None, "approval timed out")


def format_argv(argv: list[str]) -> str:
    return " ".join(_quote_arg(arg) for arg in argv)


def _quote_arg(arg: str) -> str:
    if arg and all(ch.isalnum() or ch in "._-/:=+" for ch in arg):
        return arg
    return "'" + arg.replace("'", "'\\''") + "'"
