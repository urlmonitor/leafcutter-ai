"""
Tests for TQ-600a-13-xvi -- a pull request cannot rewrite its own proof.

Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xvi.yaml

The proof job runs under the default branch's workflow, so the selection and the judgement are main's. The head here
rewrites the harness three ways at once -- its own ``scripts/ci/post_merge_fix_proof.py`` always passes, its own copy of
the lane report plugin calls every test passed, and its ``pytest.ini`` addopts collect only (exit 0, nothing executed) --
while the two failing tests still fail. See test_tq_600a_13_xvi.py for the assumed contract (job outputs, checkouts).
"""

from __future__ import annotations

import unittest

from ._hold_harness import HoldService
from ._proof_harness import FORGED_MARK, MODULE, WORKFLOW, driven


class TestTq600a13xviProofIsNotTheHeads(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.svc = HoldService()

    @classmethod
    def tearDownClass(cls):
        cls.svc.close()

    def test_tq600a_13_xvi_a_pr_cannot_rewrite_its_own_proof(self):
        # covers: TQ-600a-13-xvi
        # angle: discrimination
        """AC-xvi: the failing tests still fail at a head that also replaces the proof module with an always-pass one,
        swaps in a report plugin that calls everything passed, and edits pytest.ini's addopts to collect only.

        The proof is failed, the head's module never ran, and -- the evidence that main's selection and judgement were
        used -- the two failing tests REALLY executed (the witness shows both, once each). With the head's pytest.ini
        honoured, nothing would execute and the witness would be empty.

        Wrong versions caught: the proof imports its harness (module or report plugin) from the head, so an always-pass
        harness yields a passing proof; the prove step runs pytest with the head's pytest.ini, so a head that edits
        addopts selects nothing and passes.
        """
        self.assertTrue(WORKFLOW.is_file(), "not implemented: .github/workflows/post-merge-fix-proof.yml")
        self.assertTrue(MODULE.is_file(), "not implemented: scripts/ci/post_merge_fix_proof.py (the harness the head replaces)")
        with driven(self.svc, head={"x_ok": False, "y_ok": False, "forged": True}) as proof:
            self.assertEqual("success", proof.prepare.conclusion, proof.prepare.log_text()[-1500:])
            self.assertEqual("true", proof.prepare.outputs.get("run_proof"), proof.prepare.log_text()[-1500:])
            log = proof.prove.log_text()
            self.assertNotEqual("skipped", proof.prove.conclusion, "the proof must run for a declared fix")
            self.assertNotIn(FORGED_MARK, log, "the head's own proof module must never run")
            self.assertEqual(["x", "y"], proof.ran(), "main's selection and pytest.ini must govern: both failing tests executed, once each")
            self.assertEqual("failure", proof.prove.conclusion, "tests still failing at the head must fail the proof whatever the head's harness says")
            self.assertIn(str(proof.red["id"]), log)

    def test_tq_600a_13_xvi_a_head_cannot_replace_the_plugins_main_s_ini_names(self):
        # covers: TQ-600a-13-xvi
        # angle: discrimination
        """AC-xvi: main's pytest.ini names ``-p scripts.suite_performance.pytest_manual_deselect``; the head ships a
        forging copy of that module (every failure xfailed, or the failing test dropped from the selection) while
        the whole lane runs and one lane test still fails at the head.

        The proof fails and the failing test really executed (the witness shows ``x``): the selection plugins are
        main's, never the head's, even though the head is first on the test session's import path.

        Wrong versions caught: the child resolves main's ``-p scripts.*`` plugins from the head, so a failure turns
        into xfailed (reads as not failed in a whole-lane proof) or the lane shrinks to a green remainder.
        """
        self.assertTrue(WORKFLOW.is_file(), "not implemented: .github/workflows/post-merge-fix-proof.yml")
        for forging in ("xfail", "shrink"):
            with self.subTest(forging), driven(self.svc, kind="dnc", head={"other_ok": True, "x_ok": False, "forged_plugin": forging}) as proof:
                self.assertEqual("true", proof.prepare.outputs.get("run_proof"), proof.prepare.log_text()[-1500:])
                self.assertEqual(["a", "other", "x", "y"], proof.ran(), f"{forging}: main's plugins must govern the whole lane")
                self.assertEqual("failure", proof.prove.conclusion, f"{forging}: a failing lane test must fail the proof\n{proof.prove.log_text()[-1500:]}")


if __name__ == "__main__":
    unittest.main()
