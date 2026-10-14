"""
Tests for the TQ-600a-13-xv hotfix (2026-10-12) -- re-run requests are opt-in, and a proof run that proved nothing re-runs nothing.

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xv.yaml (notes).
Live defect: the GITHUB_TOKEN re-run POST was accepted but the re-run hit startup_failure, overwriting every hold run's
visible conclusion. Re-runs are therefore requested only when ``REEVAL_RERUN_ENABLED`` is ``true`` (the workflow passes it from
the repo variable ``POST_MERGE_REEVAL_RERUN``), and a fix-proof completion re-runs a hold only when its ``Post-merge fix proof``
job actually ran (concluded success or failure).
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ._ending_harness import Cases
from ._hold_harness import scratch_default_branch
from ._reeval_harness import PROOF_NAME, SHAS, SUITE_NAME, ReevalService, app_secrets_env, run_reeval, seed_world, suite_history, write_event
from ._workflow_jobs import REPO_ROOT, WorkflowRun

FOLLOWUP = REPO_ROOT / ".github" / "workflows" / "post-merge-followup.yml"
WOULD_RERUN = [(11, "A"), (14, "D"), (16, "F")]  # the completed holds the fan-out re-runs when enabled (1005, 1009, 1011)


def _disabled_entries():
    """Every PR the fan-out names when re-runs are off: the three it would have re-run, plus C and E as always, ordered by number."""
    named = {13: (SHAS["C"], "older_than_30_days"), 15: (SHAS["E"], "no_hold_run")}
    named.update({pr: (SHAS[key], "rerun_disabled") for pr, key in WOULD_RERUN})
    return [{"pr": pr, "head_sha": sha, "reason": reason} for pr, (sha, reason) in sorted(named.items())]


class _Case(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.svc = ReevalService()

    @classmethod
    def tearDownClass(cls):
        cls.svc.close()

    def _run(self, name, run_id, head_sha, *, rerun_enabled, history=("success", "failure"), proof_job="success"):
        self.svc.reset()
        seed_world(self.svc)
        suite_history(self.svc, *history)
        self.svc.proof_job = proof_job
        with tempfile.TemporaryDirectory() as raw:
            return run_reeval(self.svc, Path(raw), name, run_id, head_sha, rerun_enabled=rerun_enabled)


class TestRerunIsOptIn(_Case):
    def test_tq600a_13_xv_rerun_disabled_names_every_pull_request_and_posts_nothing(self):
        # covers: TQ-600a-13-xv
        # angle: discrimination
        """With the flag off the fan-out still reads everything but makes zero POSTs, and names each PR it would have re-run.

        Rows: green-then-red and red-then-green. The control (flag on) re-runs 1005, 1009, 1011 and names only C and E.
        """
        rows = Cases()
        for label, history in {"green then red": ("success", "failure"), "red then green": ("failure", "success")}.items():
            result = self._run(SUITE_NAME, 102, SHAS["A"], rerun_enabled=False, history=history)
            with rows.case(f"{label}: disabled"):
                self.assertEqual(0, result.code, result.log)
                self.assertEqual([], self.svc.write_attempts, "not one write of any kind (no credential exchange: with the gate off nothing is minted)")
                self.assertEqual([], self.svc.minted, "no installation token minted")
                self.assertNotEqual([], self.svc.reads_of("/pulls"), "every read is still done")
                self.assertEqual(_disabled_entries(), sorted(result.unrerunnable or [], key=lambda e: e["pr"]))
        result = self._run(SUITE_NAME, 102, SHAS["A"], rerun_enabled=True)
        with rows.case("control: enabled"):
            self.assertEqual([1005, 1009, 1011], self.svc.rerun_ids())
            self.assertNotIn("rerun_disabled", json.dumps(result.unrerunnable))
            self.assertEqual({13, 15}, {e["pr"] for e in result.unrerunnable})
        rows.check()

    def test_tq600a_13_xv_an_unset_or_non_true_flag_is_off(self):
        # covers: TQ-600a-13-xv
        # angle: failure
        """Only the exact string `true` enables re-runs; the proof branch honours the same switch."""
        rows = Cases()
        self.svc.reset()
        for label, value in {"empty": "", "false": "false", "True (wrong case)": "True", "1": "1"}.items():
            result = self._run(SUITE_NAME, 102, SHAS["A"], rerun_enabled=value)
            with rows.case(label):
                self.assertEqual(0, result.code, result.log)
                self.assertEqual([], self.svc.write_attempts)
        proof = self._run(PROOF_NAME, 700, SHAS["A"], rerun_enabled=False)
        with rows.case("proof branch, disabled"):
            self.assertEqual([], self.svc.write_attempts)
            self.assertEqual([{"pr": None, "head_sha": SHAS["A"], "reason": "rerun_disabled"}], proof.unrerunnable)
        rows.check()


class TestProofThatProvedNothingReRunsNothing(_Case):
    def test_tq600a_13_xv_a_proof_run_with_prove_skipped_causes_no_rerun(self):
        # covers: TQ-600a-13-xv
        # angle: discrimination
        """Rows: `Post-merge fix proof` job skipped, cancelled or absent -> no POST, output `[]`; success and failure -> re-run 1005.

        The proof run's jobs are read (GET only) before anything is decided.
        """
        rows = Cases()
        for label, conclusion in {"skipped": "skipped", "cancelled": "cancelled", "absent": None}.items():
            result = self._run(PROOF_NAME, 700, SHAS["A"], rerun_enabled=True, proof_job=conclusion)
            with rows.case(f"job {label}"):
                self.assertEqual(0, result.code, result.log)
                self.assertEqual([], self.svc.write_attempts)
                self.assertEqual([], result.unrerunnable)
                self.assertEqual(1, len(self.svc.reads_of("/actions/runs/700/jobs")), "the proof run's jobs are read")
        for label, conclusion in {"success": "success", "failure": "failure"}.items():
            result = self._run(PROOF_NAME, 700, SHAS["A"], rerun_enabled=True, proof_job=conclusion)
            with rows.case(f"job {label}"):
                self.assertEqual(0, result.code, result.log)
                self.assertEqual([1005], self.svc.rerun_ids())
        rows.check()

    def test_tq600a_13_xv_an_unreadable_jobs_list_fails_loud_without_a_rerun(self):
        # covers: TQ-600a-13-xv
        # angle: failure
        """If the proof run's jobs cannot be read, the job exits non-zero and requests no re-run."""
        self.svc.reset()
        seed_world(self.svc)
        self.svc.failing = ["/jobs"]
        with tempfile.TemporaryDirectory() as raw:
            result = run_reeval(self.svc, Path(raw), PROOF_NAME, 700, SHAS["A"])
        self.assertNotEqual(0, result.code, result.log)
        self.assertEqual([], self.svc.write_attempts)


class TestWorkflowPassesTheVariable(unittest.TestCase):
    def _execute(self, extra_env):
        svc = ReevalService()
        self.addCleanup(svc.close)
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            seed_world(svc)
            suite_history(svc, "success", "failure")
            event = write_event(base, SUITE_NAME, 102, SHAS["A"])
            run = WorkflowRun(FOLLOWUP, scratch_default_branch(base), base / "scratch", {"GITHUB_EVENT_PATH": str(event), **extra_env}, svc.url)
            result = run.execute_job("reevaluate")
        return svc, result

    def test_tq600a_13_xv_the_executed_job_posts_only_when_the_repo_variable_is_true(self):
        # covers: TQ-600a-13-xv
        # angle: reachability
        """Execute `reevaluate` verbatim: variable unset -> zero POSTs and `rerun_disabled` in the job output; `true` -> the re-runs."""
        rows = Cases()
        svc, off = self._execute(app_secrets_env())  # the secrets are there; the gate is what decides
        with rows.case("variable unset"):
            self.assertEqual("success", off.conclusion, off.log_text()[-1500:])
            self.assertEqual([], svc.write_attempts, "not one write of any kind, the credential exchange included: nothing is minted")
            self.assertEqual([], svc.bearers, "the App's JWT is not even presented")
            self.assertEqual(_disabled_entries(), sorted(json.loads(off.outputs["unrerunnable"]), key=lambda e: e["pr"]))
        svc, on = self._execute({"VARS_POST_MERGE_REEVAL_RERUN": "true", **app_secrets_env()})
        with rows.case("variable true"):
            self.assertEqual("success", on.conclusion, on.log_text()[-1500:])
            self.assertEqual([1005, 1009, 1011], svc.rerun_ids())
            self.assertEqual(1, len(svc.exchange_writes()), "one token is minted for the whole fan-out")
        rows.check()


if __name__ == "__main__":
    unittest.main()
