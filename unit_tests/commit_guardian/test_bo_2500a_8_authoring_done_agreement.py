"""
MODULE: unit_tests/commit_guardian/test_bo_2500a_8_authoring_done_agreement.py
GOAL: Roll-up seam tests of BO-2500a-8: for any record, the authoring check (check-ac-schema) and the
    done gate (check-done-proof, BO-2500a-1-ii) agree on whether its test-free declaration is complete.
BUSINESS CONTEXT: Today the authoring side accepts a reasonless test_required-false record that the done
    gate refuses at mark time, so a record can be authored that can never be marked done.
ARCHITECTURE: Both hooks run as real subprocesses over records written with yaml.safe_dump.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from unit_tests.commit_guardian import _bo2500a8_support as S


class TestAuthoringAndDoneGateAgree(unittest.TestCase):
    def test_authoring_check_and_done_gate_agree_on_every_reason_boundary(self) -> None:
        # covers: BO-2500a-8
        # angle: boundary
        """AC-8: both hooks give the same verdict, equal to the reason-present rule, for every reason."""
        for label, value in S.REASON_CASES:
            with self.subTest(reason=label), tempfile.TemporaryDirectory() as tmp:
                authoring, done = S.authoring_and_done_verdicts(Path(tmp), "ZZ-800a-1", value)
                self.assertEqual(
                    authoring == 0, done == 0,
                    f"{label}: authoring exit {authoring} but done-gate exit {done} - the two layers disagree")
                self.assertEqual(
                    done == 0, S.reason_present(value),
                    f"{label}: the done gate answered exit {done}, the reason-present rule says "
                    f"{S.reason_present(value)}")
                self.assertEqual(authoring == 0, S.reason_present(value), f"{label}: authoring verdict wrong")

    def test_a_record_the_authoring_hook_accepts_is_never_refused_at_done_for_a_missing_reason(self) -> None:
        # covers: BO-2500a-8
        # angle: reachability
        """AC-8: through the git-staged hook path, authoring exit 0 implies done-gate exit 0."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            S.git_init(root)
            reasonless = S.write_record(root, S.record("ZZ-800a-2"))
            S.git_add(root, reasonless)
            refused = S.run_authoring_git(root)
            self.assertNotEqual(
                refused.returncode, 0,
                "a test-free record with no reason must be refused by the authoring hook, so none reaches done; "
                f"stderr={refused.stderr!r}")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            S.git_init(root)
            reasoned = S.write_record(root, S.record("ZZ-800a-3", rationale=S.SENTENCE))
            S.git_add(root, reasoned)
            accepted = S.run_authoring_git(root)
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            reasoned = S.write_record(root, S.record("ZZ-800a-3", rationale=S.SENTENCE, work_status="done"))
            S.git_add(root, reasoned)
            done = S.run_done_gate(root)
            self.assertEqual(done.returncode, 0, f"accepted at authoring but refused at done: {done.stdout!r}")


if __name__ == "__main__":
    unittest.main()
