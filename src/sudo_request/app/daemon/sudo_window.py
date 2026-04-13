from __future__ import annotations

import time

from sudo_request.lib.constants import DROPIN_PATH
from sudo_request.lib.security.sudoers import cleanup_broad_rule, install_broad_rule


def open_broad_window(user: str, window_seconds: int) -> int:
    install_broad_rule(user)
    return int(time.time()) + window_seconds


def close_broad_window(retries: int = 3, delay_seconds: float = 0.2) -> bool:
    return cleanup_broad_rule(retries=retries, delay_seconds=delay_seconds)


def broad_window_exists() -> bool:
    return DROPIN_PATH.exists()
