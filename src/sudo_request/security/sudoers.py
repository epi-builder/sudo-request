from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path

from ..constants import DROPIN_DIR, DROPIN_PATH
from .payload import validate_username


def render_broad_rule(user: str) -> str:
    validate_username(user)
    return (
        "# sudo-request broad NOPASSWD window. Remove if stale.\n"
        f"# Created for local user {user}. This rule is intentionally broad.\n"
        f"{user} ALL=(ALL) NOPASSWD: ALL\n"
    )


def _run_checked(args: list[str]) -> None:
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)


def install_broad_rule(user: str, dropin_path: Path = DROPIN_PATH) -> None:
    if os.geteuid() != 0:
        raise PermissionError("install_broad_rule requires root")
    DROPIN_DIR.mkdir(parents=True, exist_ok=True)
    content = render_broad_rule(user)
    fd, tmp_name = tempfile.mkstemp(prefix=dropin_path.name + ".", suffix=".tmp", dir=str(dropin_path.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.chown(tmp, 0, 0)
        os.chmod(tmp, 0o440)
        _run_checked(["/usr/sbin/visudo", "-c", "-f", str(tmp)])
        os.replace(tmp, dropin_path)
        os.chown(dropin_path, 0, 0)
        os.chmod(dropin_path, 0o440)
        _run_checked(["/usr/sbin/visudo", "-c"])
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        finally:
            raise


def cleanup_broad_rule(dropin_path: Path = DROPIN_PATH, retries: int = 3, delay_seconds: float = 0.2) -> bool:
    ok = False
    for _ in range(max(1, retries)):
        try:
            dropin_path.unlink(missing_ok=True)
            ok = True
            break
        except Exception:
            time.sleep(delay_seconds)
    return ok and not dropin_path.exists()
