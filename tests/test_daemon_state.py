from __future__ import annotations

import unittest
from unittest.mock import Mock

from sudo_request.app.daemon.lifecycle import RequestLifecycle, RequestPhase
from sudo_request.app.daemon.server import DaemonState, peer_uid


def lifecycle(request_id: str, user: str = "epikem") -> RequestLifecycle:
    return RequestLifecycle(
        request_id=request_id,
        payload_hash=f"hash-{request_id}",
        uid=501,
        user=user,
        argv=["/bin/echo", "ok"],
        cwd="/tmp",
        resolved_executable="/bin/echo",
        expires_at=1_776_000_000,
        requested_window_seconds=30,
        max_window_seconds=300,
    )


class DaemonStateTests(unittest.TestCase):
    def test_single_active_request(self) -> None:
        state = DaemonState()
        self.assertTrue(state.begin(lifecycle("one")))
        self.assertFalse(state.begin(lifecycle("two")))
        state.clear("one")
        self.assertTrue(state.begin(lifecycle("two")))

    def test_status_snapshot_includes_lifecycle_details(self) -> None:
        state = DaemonState()
        self.assertTrue(state.begin(lifecycle("one")))
        self.assertTrue(state.set_phase("one", RequestPhase.WINDOW_OPEN))

        status = state.status()

        self.assertEqual(status["active_request_id"], "one")
        self.assertEqual(status["active_user"], "epikem")
        self.assertEqual(status["active_request"]["phase"], "window_open")
        self.assertEqual(status["active_request"]["argv"], ["/bin/echo", "ok"])
        self.assertEqual(status["active_request"]["expires_at"], 1_776_000_000)

    def test_peer_uid_uses_darwin_local_peercred_fallback(self) -> None:
        sock = Mock()
        del sock.getpeereid
        sock.getsockopt.return_value = b"\x00\x00\x00\x00\xf5\x01\x00\x00\x01\x00"
        self.assertEqual(peer_uid(sock), 501)


if __name__ == "__main__":
    unittest.main()
