from __future__ import annotations

import unittest

from sudo_request.lib.approval.decision import (
    approval_callback_data,
    callback_matches_payload,
    evaluate_callback,
    parse_callback_data,
    timeout_result,
)
from tests.helpers import sample_approval_payload


class ApprovalDecisionTests(unittest.TestCase):
    def payload(self):
        return sample_approval_payload()

    def callback(self, data: str, user_id: int = 123):
        return {"id": "callback-id", "from": {"id": user_id}, "data": data}

    def test_approval_callback_data_is_compact_and_bound_to_payload(self) -> None:
        data = approval_callback_data("a", self.payload())
        self.assertEqual(data, f"a:{'r' * 24}:{'a' * 16}:{'n' * 8}")
        self.assertLessEqual(len(data.encode("utf-8")), 64)

    def test_parse_callback_data_rejects_malformed_or_unknown_action(self) -> None:
        self.assertIsNone(parse_callback_data("bad"))
        self.assertIsNone(parse_callback_data(f"x:{'r' * 24}:{'a' * 16}:{'n' * 8}"))
        self.assertIsNone(parse_callback_data(f"a:{'r' * 24}::{'n' * 8}"))

    def test_callback_matches_payload_checks_request_hash_and_nonce(self) -> None:
        parsed = parse_callback_data(approval_callback_data("a", self.payload()))
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertTrue(callback_matches_payload(parsed, self.payload()))

        other = dict(self.payload())
        other["nonce"] = "z" * 24
        self.assertFalse(callback_matches_payload(parsed, other))

    def test_evaluate_callback_ignores_unrelated_callback(self) -> None:
        unrelated = self.callback(f"a:other:{'a' * 16}:{'n' * 8}")
        decision = evaluate_callback(unrelated, self.payload(), [123])
        self.assertEqual(decision.status, "ignored")
        self.assertFalse(decision.is_terminal)

    def test_evaluate_callback_rejects_unallowed_user_without_terminal_decision(self) -> None:
        decision = evaluate_callback(self.callback(approval_callback_data("a", self.payload()), 999), self.payload(), [123])
        self.assertEqual(decision.status, "not_allowed")
        self.assertEqual(decision.approver_id, 999)
        self.assertEqual(decision.answer_text, "Not allowed")
        self.assertFalse(decision.is_terminal)

    def test_evaluate_callback_accepts_approve_and_deny_decisions(self) -> None:
        approved = evaluate_callback(self.callback(approval_callback_data("a", self.payload())), self.payload(), [123])
        self.assertEqual(approved.status, "approved")
        self.assertEqual(approved.message_status, "APPROVED")
        self.assertTrue(approved.is_terminal)

        denied = evaluate_callback(self.callback(approval_callback_data("d", self.payload())), self.payload(), [123])
        self.assertEqual(denied.status, "denied")
        self.assertEqual(denied.message_status, "DENIED")
        self.assertTrue(denied.is_terminal)

    def test_timeout_result_uses_agent_readable_message(self) -> None:
        result = timeout_result()
        self.assertEqual(result.status, "timeout")
        self.assertEqual(result.message, "request expired by timeout")


if __name__ == "__main__":
    unittest.main()
