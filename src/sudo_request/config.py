from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    telegram_bot_token_file: Path
    telegram_allowed_user_ids: list[int]
    approval_timeout_seconds: int = 90
    broad_window_seconds_default: int = 30
    broad_window_seconds_max: int = 300

    @property
    def broad_window_seconds(self) -> int:
        return self.broad_window_seconds_default


def config_path(home: Path) -> Path:
    return home / ".config" / "sudo-request" / "config.toml"


def default_config(home: Path) -> Config:
    return Config(
        telegram_bot_token_file=home / ".config" / "sudo-request" / "telegram_bot_token",
        telegram_allowed_user_ids=[],
    )


def _expand_path(value: str, home: Path) -> Path:
    if value.startswith("~/"):
        return home / value[2:]
    return Path(os.path.expandvars(value)).expanduser()


def load_config(home: Path) -> Config:
    path = config_path(home)
    if not path.exists():
        return default_config(home)
    with path.open("rb") as f:
        raw = tomllib.load(f)
    base = default_config(home)
    token_file = _expand_path(str(raw.get("telegram_bot_token_file", base.telegram_bot_token_file)), home)
    allowed = raw.get("telegram_allowed_user_ids", base.telegram_allowed_user_ids)
    if not isinstance(allowed, list) or not all(isinstance(v, int) for v in allowed):
        raise ValueError("telegram_allowed_user_ids must be a list of integers")
    approval_timeout = int(raw.get("approval_timeout_seconds", base.approval_timeout_seconds))
    legacy_window = raw.get("broad_window_seconds")
    window_default = int(raw.get("broad_window_seconds_default", legacy_window if legacy_window is not None else base.broad_window_seconds_default))
    window_max = int(raw.get("broad_window_seconds_max", max(window_default, base.broad_window_seconds_max)))
    if approval_timeout <= 0:
        raise ValueError("approval_timeout_seconds must be positive")
    if window_default <= 0:
        raise ValueError("broad_window_seconds_default must be positive")
    if window_max <= 0:
        raise ValueError("broad_window_seconds_max must be positive")
    if window_default > window_max:
        raise ValueError("broad_window_seconds_default must be <= broad_window_seconds_max")
    return Config(token_file, allowed, approval_timeout, window_default, window_max)


def read_token(path: Path) -> str:
    token = path.read_text(encoding="utf-8").strip()
    if not token:
        raise ValueError(f"empty Telegram token file: {path}")
    return token
