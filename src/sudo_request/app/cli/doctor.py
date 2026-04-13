from __future__ import annotations

import json
import os
import stat
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sudo_request.lib.config import config_path, load_config
from sudo_request.lib.constants import BIN_PATH, DROPIN_DIR, DROPIN_PATH, INSTALL_PREFIX, LAUNCHD_PLIST, SOCKET_DIR, SOCKET_PATH

IPCRequest = Callable[[dict[str, Any]], dict[str, Any]]
SubprocessRun = Callable[..., subprocess.CompletedProcess[str]]


def command_doctor(ipc_request: IPCRequest, sudo_runner: SubprocessRun = subprocess.run) -> int:
    home = Path.home()
    print(f"config: {config_path(home)}")
    try:
        cfg = load_config(home)
        print("config: ok")
        print(f"telegram token file: {cfg.telegram_bot_token_file} exists={cfg.telegram_bot_token_file.exists()}")
        print(f"telegram allowed users: {len(cfg.telegram_allowed_user_ids)} configured")
        print(f"approval timeout: {cfg.approval_timeout_seconds}s")
        print(f"approval wait heartbeat: {cfg.approval_wait_heartbeat_seconds}s")
        print(f"broad window default: {cfg.broad_window_seconds_default}s")
        print(f"broad window max: {cfg.broad_window_seconds_max}s")
    except Exception as exc:
        print(f"config: error: {exc}")

    print_path_check("daemon socket", SOCKET_PATH, required=False, expected_uid=0, exact_mode=0o666, kind="socket")
    print_path_check("daemon socket dir", SOCKET_DIR, required=False, expected_uid=0, max_mode=0o755, kind="dir")
    print_path_check("launchd plist", LAUNCHD_PLIST, required=False, expected_uid=0, max_mode=0o644, kind="file")
    print_path_check("installed prefix", INSTALL_PREFIX, required=False, expected_uid=0, max_mode=0o755, kind="dir")
    print_path_check("PATH wrapper", BIN_PATH, required=False, expected_uid=0, max_mode=0o755, kind="file")
    print(f"PATH contains /usr/local/bin: {'/usr/local/bin' in os.environ.get('PATH', '').split(os.pathsep)}")
    print_path_check("sudoers.d", DROPIN_DIR, required=True, expected_uid=0, max_mode=0o755, kind="dir")
    print_path_check("broad sudo rule", DROPIN_PATH, required=False, expected_uid=0, exact_mode=0o440, kind="file")

    sudo_status = passwordless_sudo_status(sudo_runner)
    print(f"passwordless sudo: {sudo_status}")

    try:
        response = ipc_request({"type": "status"})
        print(f"daemon status: {json.dumps(response, sort_keys=True)}")
        if response.get("dropin_exists"):
            print("WARNING: broad sudo rule is currently installed")
        if response.get("dropin_exists") and not response.get("active_request"):
            print("WARNING: broad sudo rule exists but daemon reports no active request")
    except Exception as exc:
        print(f"daemon status: unavailable: {exc}")
    return 0


def print_path_check(
    label: str,
    path: Path,
    *,
    required: bool,
    expected_uid: int | None = None,
    exact_mode: int | None = None,
    max_mode: int | None = None,
    kind: str | None = None,
) -> None:
    print(format_path_check(label, path, required=required, expected_uid=expected_uid, exact_mode=exact_mode, max_mode=max_mode, kind=kind))


def format_path_check(
    label: str,
    path: Path,
    *,
    required: bool,
    expected_uid: int | None = None,
    exact_mode: int | None = None,
    max_mode: int | None = None,
    kind: str | None = None,
) -> str:
    try:
        st = path.lstat()
    except FileNotFoundError:
        status = "ERROR missing" if required else "missing"
        return f"{label}: {path} exists=False status={status}"
    except OSError as exc:
        return f"{label}: {path} exists=unknown status=ERROR stat_failed error={exc}"

    mode = stat.S_IMODE(st.st_mode)
    problems: list[str] = []
    if expected_uid is not None and st.st_uid != expected_uid:
        problems.append(f"owner_uid={st.st_uid} expected={expected_uid}")
    if exact_mode is not None and mode != exact_mode:
        problems.append(f"mode={format_octal(mode)} expected={format_octal(exact_mode)}")
    if max_mode is not None and mode_has_extra_bits(mode, max_mode):
        problems.append(f"mode={format_octal(mode)} max={format_octal(max_mode)}")
    if kind is not None and path_kind(st.st_mode) != kind:
        problems.append(f"kind={path_kind(st.st_mode)} expected={kind}")

    status = "ok" if not problems else "WARNING " + ", ".join(problems)
    return f"{label}: {path} exists=True owner_uid={st.st_uid} mode={format_octal(mode)} kind={path_kind(st.st_mode)} status={status}"


def passwordless_sudo_status(sudo_runner: SubprocessRun = subprocess.run) -> str:
    try:
        result = sudo_runner(
            ["/usr/bin/sudo", "-n", "/usr/bin/id", "-u"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        return f"unknown: {exc}"
    except OSError as exc:
        return f"unknown: {exc}"

    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    if result.returncode == 0 and stdout == "0":
        return "WARNING open: /usr/bin/sudo -n /usr/bin/id -u returned 0"
    if result.returncode == 0:
        return f"WARNING unexpected success: stdout={stdout!r}"
    if stderr:
        return f"closed: {stderr}"
    return f"closed: sudo exited with code {result.returncode}"


def format_octal(mode: int) -> str:
    return f"0{mode:o}"


def mode_has_extra_bits(mode: int, allowed_mode: int) -> bool:
    return bool(mode & ~allowed_mode)


def path_kind(mode: int) -> str:
    if stat.S_ISSOCK(mode):
        return "socket"
    if stat.S_ISDIR(mode):
        return "dir"
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISLNK(mode):
        return "symlink"
    return "other"
