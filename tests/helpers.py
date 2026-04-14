from __future__ import annotations

from pathlib import Path

from sudo_request.app.daemon.lifecycle import RequestLifecycle
from sudo_request.lib.config import Config


def sample_config(token_path: str = "/tmp/token", allowed_user_ids: list[int] | None = None, **overrides) -> Config:
    values = {
        "telegram_bot_token_file": Path(token_path),
        "telegram_allowed_user_ids": allowed_user_ids if allowed_user_ids is not None else [1],
        **overrides,
    }
    return Config(**values)


def sample_lifecycle(request_id: str = "one", user: str = "epikem", **overrides) -> RequestLifecycle:
    values = {
        "request_id": request_id,
        "payload_hash": f"hash-{request_id}",
        "uid": 501,
        "user": user,
        "host": "host",
        "argv": ["/bin/echo", "ok"],
        "cwd": "/tmp",
        "resolved_executable": "/bin/echo",
        "parent_process": {"pid": 1},
        "expires_at": 1_776_000_000,
        "requested_window_seconds": 30,
        "max_window_seconds": 300,
        **overrides,
    }
    return RequestLifecycle(**values)


def sample_approval_payload(**overrides) -> dict:
    payload = sample_lifecycle("r" * 24).to_approval_payload()
    payload.update(
        {
            "payload_hash": "a" * 64,
            "nonce": "n" * 24,
            "expires_at": 1,
        }
    )
    payload.update(overrides)
    return payload


def make_source_checkout(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    (root / "src" / "sudo_request").mkdir(parents=True)
    return root
