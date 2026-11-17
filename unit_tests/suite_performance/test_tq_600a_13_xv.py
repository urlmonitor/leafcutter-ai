"""
Tests for TQ-600a-13-xv -- when the post-merge verdict changes, every open pull request's hold is re-evaluated
without anyone pushing, in both directions.

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xv.yaml
Wiring tests (workflow shape, end-to-end job execution) are in test_tq_600a_13_xv_workflow.py; the notice carrying
`unrerunnable` and the `verdict_changed` rule are in test_tq_600a_13_xv_notice.py / test_tq_600a_13_xv_history.py.

ASSUMED PRODUCTION CONTRACT (written by test-writer; python-coder builds this).

NEW  scripts/ci/post_merge_reeval.py   (stdlib only; uses scripts/ci/_github_rest.GitHubClient)
  ``python scripts/ci/post_merge_reeval.py --api-url URL --repo OWNER/NAME --event-path PATH --output-file PATH``
  ``post_merge_reeval.main(argv) -> int``; token from env GITHUB_TOKEN.
  * ``--event-path``: the ``workflow_run`` event file; it carries ``workflow_run.name`` / ``.id`` / ``.head_sha``.
  * ``--output-file``: ``GITHUB_OUTPUT``. On every run that reaches a decision exactly ONE line
    ``unrerunnable=<single-line JSON list of {"pr": int, "head_sha": 40-hex, "reason": str}>`` is appended (``[]`` when
    none); the same JSON is also printed. reason is ``older_than_30_days`` | ``rerun_refused_<http status>`` | ``no_hold_run``.
  * name == "Post-merge suite": read the suite's run history exactly as the notice does
    (``GET /actions/workflows/post-merge-suite.yml/runs?branch=main&exclude_pull_requests=true&per_page=...``) and call
    ``_run_history.verdict_changed(runs, workflow_run.id)``. Anything but True: no request beyond that read, output ``[]``.
    True: ``GET /pulls?state=open&base=main&per_page=100`` following every ``Link: rel="next"`` (same-origin only, as
    ``_hold_comment.list_comments`` does); per pull request ``GET /actions/workflows/post-merge-hold.yml/runs?head_sha=<sha>
    &event=pull_request_target&per_page=5``; the run with the highest ``run_number`` is the latest (list order is not
    trusted). Completed: ``POST /actions/runs/{id}/rerun``, and a refusal (any HTTP error) is named
    ``rerun_refused_<status>``. Not completed: no request, not named. None, or ``created_at`` more than 30 days before
    now: named (``no_hold_run`` / ``older_than_30_days``), no re-run request.
  * name == "Post-merge fix proof": exactly one re-run, of the latest ``pull_request_target`` run of
    ``post-merge-hold.yml`` for ``workflow_run.head_sha``; no pull request list, no fan-out.
  * The only write the module ever makes is ``POST /actions/runs/{id}/rerun`` on a run of ``post-merge-hold.yml``.
  * Exit 0 whenever the decision ran, whatever it named; non-zero, with no re-run requested, when the history or the
    pull request list cannot be read (a fail-loud, never a silent no-op).
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ._ending_harness import Cases
from ._reeval_harness import (
    PROOF_NAME,
    SHAS,
    SUITE_NAME,
    ReevalService,
    expected_named,
    run_reeval,
    seed_world,
    suite_history,
)

ALL_COMPLETED_HOLDS = [1005, 1009, 1011]  # A's latest, D's, F's (29 days: inside the window); never B (in progress), C (31 days), E (none)
TRIGGER = 102


class ReevalCase(unittest.TestCase):
    """One fake server per class; its state and a scratch directory per test."""

    @classmethod
    def setUpClass(cls):
        cls.svc = ReevalService()

    @classmethod
    def tearDownClass(cls):
        cls.svc.close()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.svc.reset()

    def reevaluate(self, history, *, refuse=(), name=SUITE_NAME, run_id=TRIGGER, head_sha=SHAS["A"]):
        self.svc.reset()
        seed_world(self.svc, refuse=refuse)
        suite_history(self.svc, *history)
        return run_reeval(self.svc, self.tmp, name, run_id, head_sha)


class TestTq600a13XvFanOut(ReevalCase):
    def test_tq600a_13_xv_a_verdict_change_reruns_every_open_hold_both_ways(self):
        # covers: TQ-600a-13-xv
        # angle: criterion
        """A settled run whose verdict differs from the previous settled run's re-runs each open pull request's latest hold.

        Rows: green then red, red then green (both: re-run exactly the completed latest holds of the open PRs on base main,
        across all three pages of the list); red then red, green then green, did-not-complete then red, red then
        did-not-complete (an unchanged held/not-held state) and a superseded cancellation (the triggering run tested
        nothing): no re-run, no write at all, and nothing named (naming PRs nobody re-ran would be a false alarm).
        """
        rows = Cases()
        changed = {"green then red": ["success", "failure"], "red then green": ["failure", "success"]}
        for label, history in changed.items():
            result = self.reevaluate(history)
            with rows.case(label):
                self.assertEqual(0, result.code, result.log)
                self.assertEqual(ALL_COMPLETED_HOLDS, self.svc.rerun_ids(), f"{label}: re-run requests the server saw")
                self.assertEqual([], self.svc.other_writes(), "the only write is a re-run request")
        unchanged = {
            "red then red": ["failure", "failure"],
            "green then green": ["success", "success"],
            "did not complete then red": ["timed_out", "failure"],
            "red then did not complete": ["failure", "timed_out"],
            "superseded cancellation": ["success", "cancelled", ("", "queued")],
        }
        for label, history in unchanged.items():
            result = self.reevaluate(history)
            with rows.case(label):
                self.assertEqual(0, result.code, result.log)
                self.assertEqual([], self.svc.rerun_ids(), f"{label}: nothing is re-evaluated")
                self.assertEqual([], self.svc.write_attempts, f"{label}: no write of any kind")
                self.assertEqual([], self.svc.reads_of("/pulls"), f"{label}: the pull requests are not even listed")
                self.assertEqual([], result.unrerunnable, f"{label}: nothing re-evaluated, so nothing is named")
        rows.check()

    def test_tq600a_13_xv_unrerunnable_holds_are_named(self):
        # covers: TQ-600a-13-xv
        # angle: discrimination
        """The too-old, refused and never-evaluated pull requests are named with reasons; the in-progress one gets no request.

        Wrong versions this catches: only the red transition re-evaluates (the red-to-green row would re-run nothing); a
        31-day-old hold run or a refused re-run (403 on D's run) is skipped silently (the named list would be short); an
        in-progress hold run is re-run, cancelling it (a request for 1006, or for B's older completed 1004 instead of the
        latest); the fan-out reads the history before the run settled (the superseded row in the criterion test).
        Controls: F, 29 days old and completed, IS re-run (a cutoff of a week would drop it); A's older run and A's
        event-``pull_request`` run are not; PR G (other base) and PR H (closed) are never touched.
        """
        rows = Cases()
        refused = [(14, "D", 403)]
        expected = expected_named(refused=refused)
        for label, history in {"green then red": ["success", "failure"], "red then green": ["failure", "success"]}.items():
            result = self.reevaluate(history, refuse={1009})
            with rows.case(f"{label}: named exactly"):
                self.assertEqual(0, result.code, "naming a pull request is not a failure of the job:\n" + result.log)
                self.assertEqual(expected, sorted(result.unrerunnable or [], key=lambda e: e["pr"]))
            with rows.case(f"{label}: the output is written once and printed to the log"):
                self.assertEqual(1, len(result.unrerunnable_lines), result.lines)
                for reason in ("older_than_30_days", "rerun_refused_403", "no_hold_run"):
                    self.assertIn(reason, result.log, "the output is also printed to the job log")
            with rows.case(f"{label}: requests"):
                requested = self.svc.rerun_ids()
                self.assertEqual(ALL_COMPLETED_HOLDS, requested, "the refused run is attempted once; C, E and the in-progress B are not")
                self.assertTrue({1004, 1006, 1008, 1003, 1007, 1010, 1012, 1013, 2020}.isdisjoint(requested), requested)
                self.assertEqual([], self.svc.other_writes())
        rows.check()

    def test_tq600a_13_xv_a_completed_proof_reruns_only_that_prs_hold(self):
        # covers: TQ-600a-13-xv
        # angle: discrimination
        """A `Post-merge fix proof` completion re-runs exactly the latest pull_request_target hold run of the proof's head SHA.

        Wrong versions this catches: a proof completion triggers the whole fan-out (more than one request, or a read of
        the pull request list); a hold run with event ``pull_request`` (1007, the highest number for that head) is
        re-run; a run of any other workflow (ci.yml's 2020, the highest-numbered run of that head) is re-run; the
        first or an older run is picked instead of the highest ``run_number`` (1003).
        """
        # The suite history is a changed verdict on purpose: a fan-out would have every reason to run.
        result = self.reevaluate(["success", "failure"], name=PROOF_NAME, run_id=700, head_sha=SHAS["A"])
        self.assertEqual(0, result.code, result.log)
        self.assertEqual([1005], self.svc.rerun_ids(), "exactly one re-run, of A's latest pull_request_target hold run")
        self.assertEqual([], self.svc.other_writes())
        self.assertEqual([], self.svc.reads_of("/pulls"), "a proof completion lists no pull requests")
        self.assertEqual([], result.unrerunnable or [], "nothing was left un-re-run")
