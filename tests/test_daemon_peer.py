from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from sudo_request.app.daemon import peer


class DaemonPeerTests(unittest.TestCase):
    def test_peer_uid_uses_getpeereid_when_available(self) -> None:
        sock = Mock()
        sock.getpeereid.return_value = (501, 20)

        self.assertEqual(peer.peer_uid(sock), 501)

    def test_peer_uid_uses_darwin_local_peercred_fallback(self) -> None:
        sock = Mock()
        del sock.getpeereid
        sock.getsockopt.return_value = b"\x00\x00\x00\x00\xf5\x01\x00\x00\x01\x00"

        self.assertEqual(peer.peer_uid(sock), 501)

    def test_user_lookup_helpers_use_pwd_database(self) -> None:
        entry = Mock()
        entry.pw_name = "epikem"
        entry.pw_dir = "/Users/epikem"

        with patch.object(peer.pwd, "getpwuid", return_value=entry):
            self.assertEqual(peer.user_for_uid(501), "epikem")
            self.assertEqual(peer.home_for_uid(501), Path("/Users/epikem"))


if __name__ == "__main__":
    unittest.main()
