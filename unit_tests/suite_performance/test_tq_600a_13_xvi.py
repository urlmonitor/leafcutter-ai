"""
Tests for TQ-600a-13-xvi -- "A pull request that declares a fix runs the current red run's failing tests against
its own head, and only a pass is evidence" -- the selection and the judgement.

Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xvi.yaml

======================================================================
ASSUMED PRODUCTION CONTRACT (written by test-writer; python-coder builds it)

FILES   .github/workflows/post-merge-fix-proof.yml   scripts/ci/post_merge_fix_proof.py (default-branch code only)

TWO JOBS, executed VERBATIM by the shared workflow-step executor (unit_tests/suite_performance/_workflow_jobs.py,
whose checkout emulation _proof_harness.ProofRun extends with a second source: a checkout WITHOUT ``ref`` is the
default branch, ``ref: <head sha>`` is the pull request head).

`Prepare fix proof` (any job id; found by its exact ``name:``)
  * reads the pull request description from GITHUB_EVENT_PATH, calls TQ-600a-13-viii's ``match_declaration`` with the
    open ``post-merge-red`` issue numbers, reads the newest settled correctness run (REST: GITHUB_API_URL,
    GITHUB_TOKEN, GITHUB_REPOSITORY) and classifies it (scripts/ci/_run_history.py);
  * when the run is red or did-not-complete AND a fix is declared: downloads that run's ``post-merge-verdict`` artifact
    with ``actions/download-artifact`` (the executor serves the artifact store, whatever ``run-id`` says);
  * JOB OUTPUTS (exact names): ``run_proof`` ("true" | "false"), ``red_run_id`` (the run's id), ``whole_lane``
    ("true" for a did-not-complete run, else "false"), ``failing_ids`` (the red run's ``failing`` node ids, one per
    line; read from the verdict ARTIFACT, never from the notice body) -- the last three set only when run_proof is true.
`Post-merge fix proof` (``needs:`` the prepare job, ``if:`` its ``run_proof`` output is 'true')
  * checkout without ``ref`` (default branch harness, workspace root) and ``ref: <head sha>`` at ``path: head``, both
    ``persist-credentials: false``; runs main's pytest.ini via ``-c``, ``PYTEST_DISABLE_PLUGIN_AUTOLOAD=1``, the lane
    selection ``-m "manual and not timing_ratio"``; executes exactly ``failing_ids`` (the whole lane when
    ``whole_lane`` is true); exits non-zero unless every selected id passed (exit 5, an empty selection and a collection
    error are failures); PRINTS the red run's id (it records which red run it proved against); downloads no artifact.
======================================================================
"""

from __future__ import annotations

import unittest

from ._hold_harness import HoldService
from ._proof_harness import MODULE, WORKFLOW, X_ID, Y_ID, driven

LANE_ALL = ["a", "other", "x", "y"]


def expect_prepared(case, proof, *, whole_lane):
    """The prepare job decided a proof runs, against the served red run, for the right selection."""
    case.assertEqual("success", proof.prepare.conclusion, proof.prepare.log_text()[-1500:])
    out = proof.prepare.outputs
    case.assertEqual("true", out.get("run_proof"), f"the prepare job did not start a proof: {out}\n{proof.prepare.log_text()[-1500:]}")
    case.assertEqual(str(proof.red["id"]), out.get("red_run_id"), "the proof must name the current red run")
    case.assertEqual("true" if whole_lane else "false", out.get("whole_lane"))
    ids = out.get("failing_ids", "")
    if whole_lane:
        case.assertNotIn(X_ID, ids)
    else:
        case.assertEqual([X_ID, Y_ID], sorted(ids.split()), "the failing ids come from the verdict artifact, exactly")
    case.assertEqual(["post-merge-verdict"], proof.prepare.downloaded)


class TestTq600a13xviProofSelection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.svc = HoldService()

    @classmethod
    def tearDownClass(cls):
        cls.svc.close()

    def test_tq600a_13_xvi_the_proof_runs_exactly_the_red_runs_failures(self):
        # covers: TQ-600a-13-xvi
        # angle: seam
        """AC-xvi: a served red run whose verdict artifact names two failing tests; the head's lane (real child pytest).

        Head fixes both -> the prove job succeeds, names the red run, executes exactly those two tests (a third lane test
        that still fails at the head is NOT run, so is irrelevant). Head fixes one -> failure, both executed. A
        did-not-complete red run -> the whole lane runs (and no test outside the lane), failing on one red test and passing
        when all pass. A head whose two tests left the lane (no marker) -> nothing runs -> failure, never a pass.

        Wrong versions caught: the proof runs a selection of the PR's choosing or the whole lane for a red run; drops the
        lane selection (the unmarked head then passes); an exit-5/empty run reported as passed; a did-not-complete run that
        runs nothing and passes; ids read from the notice instead of the artifact.
        """
        self.assertTrue(WORKFLOW.is_file(), "not implemented: .github/workflows/post-merge-fix-proof.yml")
        self.assertTrue(MODULE.is_file(), "not implemented: scripts/ci/post_merge_fix_proof.py")
        with driven(self.svc) as proof:  # head fixes both; the third lane test still fails there
            expect_prepared(self, proof, whole_lane=False)
            self.assertEqual("success", proof.prove.conclusion, proof.prove.log_text()[-1800:])
            self.assertEqual(["x", "y"], proof.ran(), "exactly the red run's failures execute, once each")
            self.assertIn(str(proof.red["id"]), proof.prove.log_text(), "the proof must record which red run it proved against")
            self.assertEqual([], proof.prove.downloaded, "the prove job reads no artifact")
        with driven(self.svc, head={"y_ok": False}) as proof:  # head fixes one
            expect_prepared(self, proof, whole_lane=False)
            self.assertEqual("failure", proof.prove.conclusion, "one failure still failing at the head is not a proof")
            self.assertEqual(["x", "y"], proof.ran(), "both tests ran; one failed")
        with driven(self.svc, kind="dnc", head={"x_ok": True, "y_ok": True}) as proof:  # whole lane, one lane test red
            expect_prepared(self, proof, whole_lane=True)
            self.assertEqual("failure", proof.prove.conclusion, "a did-not-complete proof passes only on a green lane")
            self.assertEqual(LANE_ALL, proof.ran(), "the whole lane runs: the lane's tests, not the unmarked or timing ones")
        with driven(self.svc, kind="dnc", head={"other_ok": True}) as proof:  # whole lane green
            expect_prepared(self, proof, whole_lane=True)
            self.assertEqual("success", proof.prove.conclusion, proof.prove.log_text()[-1800:])
            self.assertEqual(LANE_ALL, proof.ran())
            self.assertIn(str(proof.red["id"]), proof.prove.log_text())
        with driven(self.svc, head={"lane_marked": False}) as proof:  # the tests left the lane: nothing is selected
            expect_prepared(self, proof, whole_lane=False)
            self.assertEqual("failure", proof.prove.conclusion, "nothing executed must never read as passed")
            self.assertEqual([], proof.ran())


if __name__ == "__main__":
    unittest.main()
