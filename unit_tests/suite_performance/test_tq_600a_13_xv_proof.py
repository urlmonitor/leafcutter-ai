"""
Tests for TQ-600a-13-xv (proof trigger hardening) -- a `Post-merge fix proof` completion re-runs a hold only when the
proof run was a `pull_request_target` run of THIS repository, and a malformed event file fails loudly.

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xv.yaml
Contract: see test_tq_600a_13_xv.py. Added by the review (M-1, L-3): a same-named workflow run from a pull request
branch (event `pull_request`) or from a fork (another `head_repository.full_name`) must cause no re-run.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ._ending_harness import Cases
from ._reeval_harness import PROOF_NAME, SHAS, ReevalService, run_reeval, seed_world, suite_history
from ._notice_fakes import import_production


class TestTq600a13XvProofTrigger(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.svc = ReevalService()

    @classmethod
    def tearDownClass(cls):
        cls.svc.close()

    def _proof(self, overrides=None):
        self.svc.reset()
        seed_world(self.svc)
        suite_history(self.svc, "success", "failure")
        with tempfile.TemporaryDirectory() as raw:
            return run_reeval(self.svc, Path(raw), PROOF_NAME, 700, SHAS["A"], overrides)

    def test_tq600a_13_xv_only_a_pull_request_target_proof_of_this_repository_reruns(self):
        # covers: TQ-600a-13-xv
        # angle: discrimination
        """Rows: a `pull_request` proof, a fork's proof and a proof with no head repository re-run nothing and name nothing.

        Control: a `pull_request_target` proof of this repository re-runs exactly A's latest hold (1005).
        """
        rows = Cases()
        refused = {
            "event pull_request (a PR branch's copy of the workflow)": {"event": "pull_request"},
            "event push": {"event": "push"},
            "no event": {"event": None},
            "fork head repository": {"head_repository": {"full_name": "someone-else/leafcutter-ai"}},
            "no head repository": {"head_repository": None},
            "head repository without a name": {"head_repository": {}},
        }
        for label, overrides in refused.items():
            result = self._proof(overrides)
            with rows.case(label):
                self.assertEqual(0, result.code, result.log)
                self.assertEqual([], self.svc.write_attempts, f"{label}: no write of any kind")
                self.assertEqual([], result.unrerunnable, f"{label}: nothing named")
        result = self._proof()
        with rows.case("control: pull_request_target of this repository"):
            self.assertEqual(0, result.code, result.log)
            self.assertEqual([1005], self.svc.rerun_ids())
        rows.check()


class TestTq600a13XvReadTriggerFailsLoud(unittest.TestCase):
    def test_tq600a_13_xv_read_trigger_raises_value_error_for_malformed_input(self):
        # covers: TQ-600a-13-xv
        # angle: failure
        """Unreadable, non-JSON, non-object and workflow_run-less event files all raise ValueError (never TypeError/AttributeError)."""
        module = import_production("scripts.ci.post_merge_reeval")
        rows = Cases()
        with tempfile.TemporaryDirectory() as raw:
            cases = {"missing file": None, "not json": "nope", "a list": "[]", "no workflow_run": "{}", "workflow_run is a string": '{"workflow_run": "x"}'}
            for label, text in cases.items():
                path = Path(raw) / "event.json"
                if text is not None:
                    path.write_text(text, encoding="utf-8")
                elif path.exists():
                    path.unlink()
                with rows.case(label):
                    with self.assertRaises(ValueError):
                        module.read_trigger(str(path))
        rows.check()


if __name__ == "__main__":
    unittest.main()
