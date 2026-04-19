from __future__ import annotations

import getpass
import os
from pathlib import Path

from sudo_request.lib.config import Config, config_path, load_config


def command_init() -> int:
    home = Path.home()
    path = config_path(home)
    cfg_dir = path.parent
    cfg_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(cfg_dir, 0o700)

    if path.exists():
        print(f"Existing config found: {path}")

    try:
        existing = load_config(home)
    except Exception as exc:
        print(f"config: error: {exc}")
        print(f"Fix or remove {path}, then run sudo-request init again.")
        return 1

    token_file = existing.telegram_bot_token_file
    token_file.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(token_file.parent, 0o700)

    token_is_configured = token_file.exists() and bool(token_file.read_text(encoding="utf-8").strip())
    print(f"Telegram bot token file: {token_file}")
    if token_is_configured:
        print("Telegram bot token: configured")
        token = getpass.getpass("Enter Telegram bot token [configured, press Enter to keep]: ").strip()
        if not token:
            os.chmod(token_file, 0o600)
        else:
            token_file.write_text(token + "\n", encoding="utf-8")
            os.chmod(token_file, 0o600)
    else:
        token = getpass.getpass("Enter Telegram bot token: ").strip()
        if not token:
            print("Telegram bot token is required.")
            return 1
        token_file.write_text(token + "\n", encoding="utf-8")
        os.chmod(token_file, 0o600)

    allowed_user_ids = existing.telegram_allowed_user_ids
    if allowed_user_ids:
        default_ids = ",".join(str(user_id) for user_id in allowed_user_ids)
        raw_allowed_ids = input(f"Enter allowed Telegram user ids [{default_ids}]: ").strip()
        if raw_allowed_ids:
            try:
                allowed_user_ids = parse_allowed_user_ids(raw_allowed_ids)
            except ValueError:
                print("Allowed Telegram user ids must be comma-separated integers.")
                return 1
    else:
        raw_allowed_ids = input("Enter allowed Telegram user id: ").strip()
        try:
            allowed_user_ids = parse_allowed_user_ids(raw_allowed_ids)
        except ValueError:
            print("Allowed Telegram user id must be an integer.")
            return 1

    cfg = Config(
        telegram_bot_token_file=token_file,
        telegram_allowed_user_ids=allowed_user_ids,
        approval_timeout_seconds=existing.approval_timeout_seconds,
        approval_wait_heartbeat_seconds=existing.approval_wait_heartbeat_seconds,
        broad_window_seconds_default=existing.broad_window_seconds_default,
        broad_window_seconds_max=existing.broad_window_seconds_max,
    )

    if path.exists():
        print(f"Updating {path}")
    else:
        print(f"Creating {path}")
    path.write_text(render_config(cfg, home), encoding="utf-8")
    os.chmod(path, 0o600)
    print("Wrote config.")
    print("Run: sudo-request doctor")
    return 0


def parse_allowed_user_ids(raw: str) -> list[int]:
    values = [part.strip() for part in raw.split(",")]
    if not values or any(not value for value in values):
        raise ValueError("empty Telegram user id")
    return [int(value) for value in values]


def render_config(cfg: Config, home: Path) -> str:
    token_file = format_config_path(cfg.telegram_bot_token_file, home)
    allowed = ", ".join(str(user_id) for user_id in cfg.telegram_allowed_user_ids)
    lines = [
        f'telegram_bot_token_file = "{token_file}"',
        f"telegram_allowed_user_ids = [{allowed}]",
        f"approval_timeout_seconds = {cfg.approval_timeout_seconds}",
        f"approval_wait_heartbeat_seconds = {cfg.approval_wait_heartbeat_seconds}",
        f"broad_window_seconds_default = {cfg.broad_window_seconds_default}",
        f"broad_window_seconds_max = {cfg.broad_window_seconds_max}",
    ]
    return "\n".join(lines) + "\n"


def format_config_path(path: Path, home: Path) -> str:
    try:
        relative = path.resolve(strict=False).relative_to(home.resolve(strict=False))
    except ValueError:
        return str(path)
    return "~/" + str(relative)
