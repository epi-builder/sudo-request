from __future__ import annotations

import pwd
import socket
import struct
from pathlib import Path


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
