from __future__ import annotations

import unittest
from unittest.mock import Mock

from sudo_request import daemon as legacy_daemon
from sudo_request.app.daemon.server import DaemonState, peer_uid


class DaemonStateTests(unittest.TestCase):
    def test_legacy_daemon_module_reexports_app_entrypoints(self) -> None:
        self.assertIs(legacy_daemon.DaemonState, DaemonState)

    def test_single_active_request(self) -> None:
        state = DaemonState()
        self.assertTrue(state.begin("one", "epikem"))
        self.assertFalse(state.begin("two", "epikem"))
        state.clear("one")
        self.assertTrue(state.begin("two", "epikem"))

    def test_peer_uid_uses_darwin_local_peercred_fallback(self) -> None:
        sock = Mock()
        del sock.getpeereid
        sock.getsockopt.return_value = b"\x00\x00\x00\x00\xf5\x01\x00\x00\x01\x00"
        self.assertEqual(peer_uid(sock), 501)


if __name__ == "__main__":
    unittest.main()
