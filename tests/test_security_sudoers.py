from __future__ import annotations

import unittest

from sudo_request.lib.security.sudoers import render_broad_rule


class SudoersTests(unittest.TestCase):
    def test_render_broad_rule(self) -> None:
        rule = render_broad_rule("epikem")
        self.assertIn("epikem ALL=(ALL) NOPASSWD: ALL", rule)
        self.assertIn("intentionally broad", rule)

    def test_render_broad_rule_rejects_unsafe_user(self) -> None:
        with self.assertRaises(ValueError):
            render_broad_rule("bad user")


if __name__ == "__main__":
    unittest.main()
