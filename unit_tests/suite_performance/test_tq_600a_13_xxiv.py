"""
Tests for TQ-600a-13-xxiv -- the pull request's Proof-of-done check is unchanged by the post-merge live-database lane.

Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xxiv.yaml

Every comparison is against a RECORDED baseline (``tests/fixtures/tq_600a_13_xxiv/baseline.json``): the selector, the
``check_done_proof.py --mode ci-changed`` command and the ``done-proof`` job of ci.yml as they stood at origin/main before
the post-merge live lane (TQ-600a-13-xxi) was added, run once on three recorded pull requests of a synthetic repository
(see ``_xxiv_support.py``) and kept as fixed evidence. None compares the current selector with itself.

The databases themselves start on the hosting service, which the unit layer cannot produce, so the one clause about them is
structural by necessity: the parsed job is compared with the recorded job, and the judgement half is executed.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from . import _xxiv_support as support
from ._workflow_jobs import find_job, load_workflow

BASELINE = json.loads((support.REPO_ROOT / "tests" / "fixtures" / "tq_600a_13_xxiv" / "baseline.json").read_text(encoding="utf-8"))
CI_WORKFLOW = support.REPO_ROOT / ".github" / "workflows" / "ci.yml"
VERDICT_STATES = ("absent", "green", "red", "did_not_complete")
VERDICT_DIRS = ("post-merge-verdict.json", "verdict", "artifacts")


class TestTq600a13xxivProofOfDoneUnchanged(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="xxiv-")
        cls.repo = support.build_pr_repo(cls.tmp)
        cls.cli_runs = {}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def cli(self, branch):
        """The real ``check_done_proof.py --mode ci-changed`` on ``branch``, once per class."""
        if branch not in self.cli_runs:
            self.cli_runs[branch] = support.run_cli(support.SCRIPTS_DIR, self.repo, branch)
        return self.cli_runs[branch]

    def test_tq_600a_13_xxiv_proof_of_done_selects_the_same_tests_as_the_recorded_baseline(self):
        # covers: TQ-600a-13-xxiv
        # angle: criterion
        """AC-xxiv: the selector, in-process, on the recorded live-criterion pull request and the one changing none.

        The criteria evaluated, the covering tests selected and the violations returned equal the baseline recorded at
        origin/main. The live criterion's covering test is selected, and neither the done-at-base SYN-200 (whose covering
        test fails) nor any other unrelated test is.

        Wrong versions caught: the selection is widened to the whole live-database folder (SYN-200's failing test would be
        selected and reported); the selection drops the covers-tag scoping (the same); the test compares the post-change
        selector with itself (the baseline is a file recorded from origin/main, with its commit named in it).
        """
        self.assertIn("origin/main", BASELINE["recorded_from"])
        selector = support.load_selector(support.SCRIPTS_DIR)
        for branch in ("pr-live", "pr-none"):
            actual = support.select_in_process(selector, self.repo, branch)
            self.assertEqual(BASELINE["in_process"][branch], actual, f"{branch}: the selection differs from the recorded baseline")
        live = support.select_in_process(selector, self.repo, "pr-live")
        self.assertEqual(["SYN-100"], [e["ac_id"] for e in live["evaluated"]])
        self.assertEqual(["tests/knowledge_live/test_syn_100.py::test_100_live_proof"], live["evaluated"][0]["tests"])
        none = support.select_in_process(selector, self.repo, "pr-none")
        self.assertEqual([], none["evaluated"], "a pull request that changes no done criterion selects no test")
        self.assertNotIn("SYN-200", json.dumps([live, none]), "a criterion no pull request changed was selected")

    def test_tq_600a_13_xxiv_a_failing_live_proof_still_blocks_the_pull_request(self):
        # covers: TQ-600a-13-xxiv
        # angle: discrimination
        """AC-xxiv: the real command, as a child process, on the pull request marking SYN-400 done whose covering test fails.

        It exits non-zero naming SYN-400 and the failing test, exactly as the baseline recorded; on the pull request whose
        covering test passes it exits zero, as recorded.

        Wrong versions caught: a refactor turns a failing live proof into a skip (exit 0, no SYN-400 line); a refactor
        turns a failing live proof into a pass (the same).
        """
        failing = self.cli("pr-fail")
        self.assertEqual(BASELINE["cli"]["pr-fail"], failing)
        self.assertEqual(1, failing["exit"], failing)
        self.assertTrue(any("SYN-400" in line and "test_400_live_proof" in line for line in failing["lines"]), failing)
        passing = self.cli("pr-live")
        self.assertEqual(BASELINE["cli"]["pr-live"], passing)
        self.assertEqual(0, passing["exit"], passing)
        self.assertFalse(any("SYN-" in line for line in passing["lines"]), passing)

    def test_tq_600a_13_xxiv_proof_of_done_never_reads_the_post_merge_verdict(self):
        # covers: TQ-600a-13-xxiv
        # angle: discrimination
        """AC-xxiv: the real command on the same pull request under four states of the post-merge verdict file.

        Absent, green, red with a live-database failure, and did_not_complete (the file is placed at the places a reader
        of the ``post-merge-verdict`` artifact would look). On the failing pull request (SYN-400) and on the one changing no
        criterion, the exit status and the output are identical across the four and equal the baseline.

        Wrong versions caught: the selector consults the verdict and waives a live criterion's proof when the lane is green
        (pr-fail would exit 0 under green); the selector fails an unrelated pull request when the live lane is red (pr-none
        would exit non-zero under red).
        """
        try:
            for state in VERDICT_STATES:
                self._place_verdict(state)
                for branch in ("pr-fail", "pr-none"):
                    run = support.run_cli(support.SCRIPTS_DIR, self.repo, branch)
                    self.assertEqual(BASELINE["cli"][branch], run, f"{branch} under a {state} verdict differs from the baseline")
        finally:
            self._clear_verdicts()
        self.assertEqual(1, BASELINE["cli"]["pr-fail"]["exit"])
        self.assertEqual(0, BASELINE["cli"]["pr-none"]["exit"])

    def _place_verdict(self, state):
        self._clear_verdicts()
        if state != "absent":
            support.write_verdict(self.repo, state)
            self.assertTrue((self.repo / "post-merge-verdict.json").is_file())

    def _clear_verdicts(self):
        for name in VERDICT_DIRS:
            target = self.repo / name
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()

    def test_tq_600a_13_xxiv_the_done_proof_job_still_declares_its_three_databases_unconditionally(self):
        # covers: TQ-600a-13-xxiv
        # angle: seam
        """AC-xxiv: ci.yml loaded as data through the shared workflow loader, compared with the job recorded at origin/main.

        The job's name, runner, services (image, ports, credentials, memory settings, health checks) and absence of a
        job-level condition equal the baseline, so the three databases start on every pull request; the job's own command,
        taken from its step, is then executed on the pull request that changes no live-database criterion and judges it as
        recorded. Structural by necessity for the start-up (service containers are an event of the hosting service); the
        judgement half is executed.

        Wrong versions caught: the database start-up is made conditional on a changed live-database criterion (an ``if``
        appears on the job); a shared definition changes a port, image tag, credential or heap setting (the services differ).
        """
        job_id, job = find_job(load_workflow(CI_WORKFLOW), "done-proof")
        shape = support.job_shape({"jobs": {job_id: job}})
        self.assertEqual(BASELINE["done_proof_job"]["job"], shape["job"])
        self.assertNotIn("if", shape["job"], "the done-proof job became conditional")
        self.assertEqual(["knowledge-domain", "knowledge-native", "knowledge-retrieval"], sorted(shape["job"]["services"]))
        self.assertEqual(BASELINE["done_proof_job"]["proof_step_argv"], shape["proof_step_argv"])
        self.assertEqual(1, shape["proof_steps"])
        argv = " ".join(shape["proof_step_argv"]).replace("origin/${{ github.base_ref }}", "base").split()
        self.assertNotIn("${{", argv)
        run = support.run_cli(support.SCRIPTS_DIR, self.repo, "pr-none", argv)
        self.assertEqual(BASELINE["cli"]["pr-none"], run)

    def test_tq_600a_13_xxiv_the_ci_changed_command_runs_end_to_end_on_the_two_recorded_pull_requests(self):
        # covers: TQ-600a-13-xxiv
        # angle: reachability
        """AC-xxiv: ``python scripts/commit_guardian/check_done_proof.py --mode ci-changed --base <ref> --test-root .``.

        Run as a subprocess exactly as the done-proof job runs it, in the synthetic repository: it exits non-zero for the
        pull request whose done criterion has no passing covering test and zero for the one that changes no criterion,
        matching the baseline; the exit status is the process's own (consumed by the job's step), not a value read back
        from an importable function.
        """
        blocked = self.cli("pr-fail")
        clean = self.cli("pr-none")
        self.assertNotEqual(0, blocked["exit"], blocked)
        self.assertEqual(0, clean["exit"], clean)
        self.assertEqual(BASELINE["cli"]["pr-fail"]["exit"], blocked["exit"])
        self.assertEqual(BASELINE["cli"]["pr-none"]["exit"], clean["exit"])
        self.assertEqual(BASELINE["cli"]["pr-fail"]["lines"], blocked["lines"])
        self.assertTrue(Path(support.SCRIPTS_DIR / "commit_guardian" / "check_done_proof.py").is_file())


if __name__ == "__main__":
    unittest.main()
