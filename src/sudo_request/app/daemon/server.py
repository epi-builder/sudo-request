from __future__ import annotations

import os
import pwd
import signal
import socket
import socketserver
import struct
import threading
import time
from pathlib import Path
from typing import Any

from sudo_request.app.daemon.lifecycle import RequestLifecycle, RequestPhase
from sudo_request.lib.audit import append_jsonl
from sudo_request.lib.approval.telegram import TelegramClient
from sudo_request.lib.config import load_config, read_token
from sudo_request.lib.constants import DAEMON_LOG, DROPIN_PATH, EXIT_DAEMON_FAILURE, SOCKET_DIR, SOCKET_PATH
from sudo_request.lib.ipc import recv_json_line, send_json_line
from sudo_request.lib.security.payload import build_payload, payload_hash, validate_username
from sudo_request.lib.security.sudoers import cleanup_broad_rule, install_broad_rule


class DaemonState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.active_request: RequestLifecycle | None = None
        self.cleanup_timer: threading.Timer | None = None

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
            return True

    def set_phase(self, request_id: str, phase: RequestPhase, exit_code: int | None = None) -> bool:
        with self.lock:
            if self.active_request is None or self.active_request.request_id != request_id:
                return False
            self.active_request.phase = phase
            if exit_code is not None:
                self.active_request.exit_code = exit_code
            return True

    def set_approval_messages(self, request_id: str, approval_messages: list[dict[str, int]]) -> bool:
        with self.lock:
            if self.active_request is None or self.active_request.request_id != request_id:
                return False
            self.active_request.approval_messages = approval_messages
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

    def status(self) -> dict[str, Any]:
        with self.lock:
            request = self.active_request
            return {
                "active_request_id": request.request_id if request is not None else None,
                "active_user": request.user if request is not None else None,
                "active_request": request.to_status_dict() if request is not None else None,
            }


STATE = DaemonState()


def peer_uid(sock: socket.socket) -> int:
    if hasattr(sock, "getpeereid"):
        uid, _gid = sock.getpeereid()
        return int(uid)
    if hasattr(socket, "LOCAL_PEERCRED"):
        raw = sock.getsockopt(0, socket.LOCAL_PEERCRED, 256)
        if len(raw) >= struct.calcsize("IIh"):
            _version, uid, _ngroups = struct.unpack_from("IIh", raw)
            return int(uid)
    raise RuntimeError("getpeereid is required on this platform")


def home_for_uid(uid: int) -> Path:
    return Path(pwd.getpwuid(uid).pw_dir)


def user_for_uid(uid: int) -> str:
    return pwd.getpwuid(uid).pw_name


class RequestHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        try:
            message = recv_json_line(self.rfile)
            response = self.dispatch(message)
        except Exception as exc:
            append_jsonl(DAEMON_LOG, "ipc_error", {"error": str(exc)})
            response = {"ok": False, "status": "daemon_error", "exit_code": EXIT_DAEMON_FAILURE, "error": str(exc)}
        send_json_line(self.request, response)

    def dispatch(self, message: dict[str, Any]) -> dict[str, Any]:
        kind = message.get("type")
        if kind == "run_request":
            return self.handle_run_request(message)
        if kind == "close_request":
            return self.handle_close_request(message)
        if kind == "status":
            return self.handle_status()
        if kind == "cancel":
            return self.handle_cancel(message)
        if kind == "cleanup":
            return self.handle_cleanup()
        return {"ok": False, "status": "bad_request", "exit_code": 125, "error": f"unknown request type: {kind}"}

    def handle_run_request(self, message: dict[str, Any]) -> dict[str, Any]:
        uid = peer_uid(self.request)
        user = user_for_uid(uid)
        home = home_for_uid(uid)
        validate_username(user)
        argv = list(message.get("argv") or [])
        cwd = str(message.get("cwd") or home)
        path_value = str(message.get("path") or os.defpath)
        cfg = load_config(home)
        requested_window_seconds = message.get("window_seconds")
        if requested_window_seconds is None:
            window_seconds = cfg.broad_window_seconds_default
        else:
            window_seconds = int(requested_window_seconds)
        if window_seconds <= 0:
            return {"ok": False, "status": "policy_block", "exit_code": 125, "error": "window_seconds must be positive"}
        if window_seconds > cfg.broad_window_seconds_max:
            return {
                "ok": False,
                "status": "policy_block",
                "exit_code": 125,
                "error": f"requested window_seconds {window_seconds}s exceeds max {cfg.broad_window_seconds_max}s",
            }
        payload = build_payload(uid, user, str(home), cwd, argv, path_value, cfg.approval_timeout_seconds)
        payload["requested_window_seconds"] = window_seconds
        payload["max_window_seconds"] = cfg.broad_window_seconds_max
        payload["payload_hash"] = payload_hash({k: v for k, v in payload.items() if k != "payload_hash"})
        request_id = payload["request_id"]
        lifecycle = RequestLifecycle.from_payload(payload)

        if not STATE.begin(lifecycle):
            return {"ok": False, "status": "busy", "exit_code": 125, "error": "another request is active"}

        append_jsonl(DAEMON_LOG, "request_created", payload)
        try:
            token = read_token(cfg.telegram_bot_token_file)
            if not cfg.telegram_allowed_user_ids:
                raise ValueError("telegram_allowed_user_ids is empty")
            telegram = TelegramClient(token)
            approval_messages = []
            for chat_id in cfg.telegram_allowed_user_ids:
                message_id = telegram.send_approval_request(chat_id, payload)
                approval_messages.append({"chat_id": chat_id, "message_id": message_id})
            payload["approval_messages"] = approval_messages
            STATE.set_approval_messages(request_id, approval_messages)
            payload["payload_hash"] = payload_hash({k: v for k, v in payload.items() if k not in {"payload_hash", "approval_messages"}})
            decision = telegram.wait_for_approval_decision(payload, cfg.telegram_allowed_user_ids, cfg.approval_timeout_seconds)
            append_jsonl(DAEMON_LOG, "approval_decision", {"request_id": request_id, "status": decision.status, "approver_id": decision.approver_id})

            if decision.status == "timeout":
                STATE.set_phase(request_id, RequestPhase.EXPIRED)
                STATE.clear(request_id)
                return {"ok": False, "status": "timeout", "exit_code": 124, "request_id": request_id, "error": decision.message}
            if decision.status == "denied":
                STATE.set_phase(request_id, RequestPhase.DENIED)
                STATE.clear(request_id)
                return {"ok": False, "status": "denied", "exit_code": 126, "request_id": request_id}

            STATE.set_phase(request_id, RequestPhase.APPROVED)
            install_broad_rule(user)
            STATE.set_phase(request_id, RequestPhase.WINDOW_OPEN)
            timer = threading.Timer(window_seconds, watchdog_cleanup, args=(request_id,))
            timer.daemon = True
            STATE.set_cleanup_timer(request_id, timer)
            timer.start()
            append_jsonl(DAEMON_LOG, "window_opened", {"request_id": request_id, "user": user, "dropin": str(DROPIN_PATH), "seconds": window_seconds})
            return {"ok": True, "status": "approved", "request_id": request_id, "payload_hash": payload["payload_hash"], "window_seconds": window_seconds}
        except Exception as exc:
            cleanup_broad_rule()
            STATE.set_phase(request_id, RequestPhase.FAILED)
            STATE.clear(request_id)
            append_jsonl(DAEMON_LOG, "request_failed", {"request_id": request_id, "error": str(exc)})
            return {"ok": False, "status": "daemon_error", "exit_code": 127, "request_id": request_id, "error": str(exc)}

    def handle_close_request(self, message: dict[str, Any]) -> dict[str, Any]:
        request_id = str(message.get("request_id") or "")
        cleanup_ok = cleanup_broad_rule()
        STATE.set_phase(request_id, RequestPhase.CLOSED if cleanup_ok else RequestPhase.FAILED)
        STATE.clear(request_id or None)
        append_jsonl(DAEMON_LOG, "window_closed", {"request_id": request_id, "cleanup_ok": cleanup_ok})
        return {"ok": cleanup_ok, "status": "closed" if cleanup_ok else "cleanup_failed"}

    def handle_status(self) -> dict[str, Any]:
        return {"ok": True, "status": "ok", **STATE.status(), "dropin_exists": DROPIN_PATH.exists()}

    def handle_cancel(self, message: dict[str, Any]) -> dict[str, Any]:
        request_id = str(message.get("request_id") or "")
        cleanup_ok = cleanup_broad_rule()
        STATE.set_phase(request_id, RequestPhase.CANCELLED if cleanup_ok else RequestPhase.FAILED)
        STATE.clear(request_id or None)
        append_jsonl(DAEMON_LOG, "request_cancelled", {"request_id": request_id, "cleanup_ok": cleanup_ok})
        return {"ok": cleanup_ok, "status": "cancelled" if cleanup_ok else "cleanup_failed"}

    def handle_cleanup(self) -> dict[str, Any]:
        cleanup_ok = cleanup_broad_rule()
        STATE.clear(None)
        append_jsonl(DAEMON_LOG, "cleanup", {"cleanup_ok": cleanup_ok})
        return {"ok": cleanup_ok, "status": "clean" if cleanup_ok else "cleanup_failed"}


def watchdog_cleanup(request_id: str) -> None:
    cleanup_ok = cleanup_broad_rule(retries=10, delay_seconds=0.5)
    STATE.set_phase(request_id, RequestPhase.EXPIRED if cleanup_ok else RequestPhase.FAILED)
    STATE.clear(request_id)
    append_jsonl(DAEMON_LOG, "window_watchdog_cleanup", {"request_id": request_id, "cleanup_ok": cleanup_ok})


class UnixServer(socketserver.ThreadingUnixStreamServer):
    allow_reuse_address = True
    daemon_threads = True


def run_foreground(socket_path: Path = SOCKET_PATH) -> int:
    if os.geteuid() != 0:
        raise PermissionError("daemon must run as root")
    cleanup_broad_rule()
    SOCKET_DIR.mkdir(parents=True, exist_ok=True)
    try:
        socket_path.unlink()
    except FileNotFoundError:
        pass
    server = UnixServer(str(socket_path), RequestHandler)
    os.chmod(socket_path, 0o666)

    def stop(_signum, _frame) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    append_jsonl(DAEMON_LOG, "daemon_started", {"socket": str(socket_path)})
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        cleanup_broad_rule()
        server.server_close()
        socket_path.unlink(missing_ok=True)
        append_jsonl(DAEMON_LOG, "daemon_stopped", {})
    return 0
