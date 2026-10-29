"""
MODULE: unit_tests/commit_guardian/test_bo_2500a_8_i_reason_required.py
GOAL: BO-2500a-8-i - the commit-time record check (check_ac_schema.py) refuses a test_required-false
    record that carries no stated reason (test_rationale), at every readiness and change_target.
BUSINESS CONTEXT: The authoring side produced test-free records the done gate later refuses; the refusal
    moves to authoring time. The JSON schema stays permissive (a conditional rule would also refuse the
    99 stored reasonless records), so the rule lives in the commit-time check alone.
ARCHITECTURE: The real check_ac_schema.py runs as a subprocess (HOOK_ROOT + HOOK_TEST_STAGED_FILES, or the
    git-staged path) over records written with yaml.safe_dump; helpers in _bo2500a8_support.
"""

from __future__ import annotations

import itertools
import subprocess
import tempfile
import unittest
from pathlib import Path

from unit_tests.commit_guardian import _bo2500a8_support as S

REASONLESS = [("absent", S.ABSENT), ("null", None), ("empty", ""), ("whitespace", "  \t ")]
READINESS = ("draft", "reviewed", "approved")
TARGETS = ("docs", "prompt", "code", "schema")


def _verdict(rec: dict) -> "subprocess.CompletedProcess[str]":
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        return S.run_authoring(root, [S.write_record(root, rec)])


class TestReasonRequired(unittest.TestCase):
    def test_staged_test_free_record_without_a_reason_is_refused(self) -> None:
        # covers: BO-2500a-8-i
        # angle: failure
        """The hook exits 1, naming test_rationale, for each reasonless variant."""
        for label, value in REASONLESS:
            with self.subTest(reason=label):
                result = _verdict(S.record("ZZ-810a-1", rationale=value))
                self.assertEqual(result.returncode, 1, f"{label}: exit {result.returncode}, stderr={result.stderr!r}")
                self.assertIn("test_rationale", result.stderr)

    def test_refusal_names_the_record_the_field_and_the_stated_reason(self) -> None:
        # covers: BO-2500a-8-i
        # angle: criterion
        """The line refusing the record carries its id, the field test_rationale and 'stated reason'."""
        result = _verdict(S.record("ZZ-810a-2"))
        lines = [ln for ln in result.stderr.splitlines() if "stated reason" in ln]
        self.assertTrue(lines, f"no refusal line says 'stated reason': {result.stderr!r}")
        self.assertTrue(any("test_rationale" in ln for ln in lines), f"refusal does not name the field: {lines}")
        self.assertTrue(any("ZZ-810a-2" in m for m in S.messages(result.stderr)),
                        f"the refusal message itself must name the record id: {result.stderr!r}")

    def test_refusal_applies_at_every_readiness_and_change_target(self) -> None:
        # covers: BO-2500a-8-i
        # angle: boundary
        """Every readiness x change_target cell refuses a reasonless test-free record with the new message."""
        for readiness, target in itertools.product(READINESS, TARGETS):
            with self.subTest(readiness=readiness, change_target=target):
                result = _verdict(S.record("ZZ-810a-3", readiness=readiness, change_target=target))
                self.assertEqual(result.returncode, 1, f"{readiness}/{target}: {result.stderr!r}")
                self.assertIn("test_rationale", result.stderr, f"{readiness}/{target}: not the new refusal")

    def test_same_test_free_record_with_a_reason_is_accepted(self) -> None:
        # covers: BO-2500a-8-i
        # angle: criterion
        """The matrix with a non-empty test_rationale passes (code cells may meet the older rule only)."""
        for readiness, target in itertools.product(READINESS, TARGETS):
            with self.subTest(readiness=readiness, change_target=target):
                result = _verdict(S.record("ZZ-810a-4", rationale="x", readiness=readiness, change_target=target))
                if target in ("code", "schema") and result.returncode != 0:
                    # only the older approved-leaf-code rule may refuse; it never mentions test_rationale
                    self.assertEqual(readiness, "approved", f"{readiness}/{target}: {result.stderr!r}")
                    self.assertNotIn("test_rationale", result.stderr)
                else:
                    self.assertEqual(result.returncode, 0, f"{readiness}/{target}: {result.stderr!r}")

    def test_records_with_test_required_true_or_absent_are_checked_as_before(self) -> None:
        # covers: BO-2500a-8-i
        # angle: boundary
        """test_required true (with or without a rationale) and test_required absent exit 0, rationale optional."""
        spec = [{"name": "t", "target_dir": "unit_tests/"}]
        cases = {
            "true_spec_no_rationale": S.record("ZZ-810a-5", test_required=True, test_spec=spec),
            "true_spec_with_rationale": S.record("ZZ-810a-5", test_required=True, test_spec=spec, rationale="why"),
            "absent_no_rationale": S.record("ZZ-810a-5", test_required=S.ABSENT),
        }
        for label, rec in cases.items():
            with self.subTest(case=label):
                result = _verdict(rec)
                self.assertEqual(result.returncode, 0, f"{label}: {result.stderr!r}")

    def test_authoring_check_and_done_gate_use_one_reason_present_rule(self) -> None:
        # covers: BO-2500a-8-i
        # angle: seam
        """The reasons the authoring check refuses are exactly those the done gate refuses."""
        refused_authoring, refused_done = set(), set()
        for label, value in S.REASON_CASES:
            with tempfile.TemporaryDirectory() as tmp:
                authoring, done = S.authoring_and_done_verdicts(Path(tmp), "ZZ-810a-6", value)
            if authoring:
                refused_authoring.add(label)
            if done:
                refused_done.add(label)
        expected = {label for label, value in S.REASON_CASES if not S.reason_present(value)}
        self.assertEqual(refused_done, expected, "the done gate drifted from the reason-present rule")
        self.assertEqual(refused_authoring, refused_done, "authoring and done gate refuse different reasons")

    def test_stored_reasonless_record_is_refused_only_when_it_is_itself_changed(self) -> None:
        # covers: BO-2500a-8-i
        # angle: criterion
        """Staging only an unrelated record exits 0; staging the stored reasonless record exits 1 naming it."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stored = S.write_record(root, S.record("ZZ-810a-7"))
            other = S.write_record(root, S.record("ZZ-810a-8", rationale="a real reason"))
            unrelated = S.run_authoring(root, [other])
            self.assertEqual(unrelated.returncode, 0, f"a commit that does not change it was refused: {unrelated.stderr!r}")
            changed = S.run_authoring(root, [stored])
            self.assertEqual(changed.returncode, 1, changed.stderr)
            self.assertIn("ZZ-810a-7", changed.stderr)

    def test_commit_time_hook_refuses_a_reasonless_test_free_record_through_the_git_staged_path(self) -> None:
        # covers: BO-2500a-8-i
        # angle: reachability
        """check_ac_schema.py as the pre-commit hook runs it: exit 1 with the refusal; with a reason, exit 0."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            S.git_init(root)
            S.git_add(root, S.write_record(root, S.record("ZZ-810a-9")))
            refused = S.run_authoring_git(root)
            self.assertEqual(refused.returncode, 1, refused.stderr)
            self.assertIn("test_rationale", refused.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            S.git_init(root)
            S.git_add(root, S.write_record(root, S.record("ZZ-810a-9", rationale="a real reason")))
            self.assertEqual(S.run_authoring_git(root).returncode, 0)


if __name__ == "__main__":
    unittest.main()
