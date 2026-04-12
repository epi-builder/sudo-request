from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from sudo_request.payload import build_payload, payload_hash, resolve_executable, validate_username


class PayloadTests(unittest.TestCase):
    def test_payload_hash_is_stable_for_canonical_json(self) -> None:
        left = {"b": 2, "a": ["x", "y"]}
        right = {"a": ["x", "y"], "b": 2}
        self.assertEqual(payload_hash(left), payload_hash(right))

    def test_validate_username(self) -> None:
        validate_username("epikem")
        validate_username("user.name-1")
        with self.assertRaises(ValueError):
            validate_username("bad user")
        with self.assertRaises(ValueError):
            validate_username("../root")

    def test_resolve_executable_from_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "tool"
            exe.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            exe.chmod(0o755)
            self.assertEqual(resolve_executable(["tool"], tmp), str(exe.resolve()))

    def test_resolve_relative_executable_against_supplied_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "tool"
            exe.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            exe.chmod(0o755)
            self.assertEqual(resolve_executable(["./tool"], os.defpath, tmp), str(exe.resolve()))

    def test_build_payload_preserves_argv_and_hashes(self) -> None:
        payload = build_payload(501, "epikem", "/Users/epikem", "/tmp", ["/bin/echo", "ok"], os.defpath, 90)
        self.assertEqual(payload["argv"], ["/bin/echo", "ok"])
        digest_input = {k: v for k, v in payload.items() if k != "payload_hash"}
        self.assertEqual(payload["payload_hash"], payload_hash(digest_input))


if __name__ == "__main__":
    unittest.main()
