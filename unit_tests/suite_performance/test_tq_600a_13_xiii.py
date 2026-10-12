"""
Tests for TQ-600a-13-xiii -- a correctness test that passes only on retry is tracked on a non-holding notice, and one that
does so in two of the last five settled runs makes the run red.

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xiii.yaml

ASSUMED PRODUCTION CONTRACT (written by test-writer; python-coder builds this). Extends existing entry points only.

1. ``post_merge_suite.py verdict`` gains ``--api-url URL --repo OWNER/NAME --run-id N`` (token in GITHUB_TOKEN). Given them
   it reads, through ``_github_rest.GitHubClient``, ONE page of the lane's run history (``post-merge-suite.yml`` for
   ``--lane correctness``), takes the settled main runs numbered below ``--run-id`` (``_run_history.select_verdict_run``'s
   rule: a superseded cancellation is skipped and never fills a slot), at most ``flaky_window_runs - 1`` of them newest
   first, and for each one ``GET /actions/runs/{id}/artifacts`` plus ONE download of its ``post-merge-verdict`` artifact
   (``GET /actions/artifacts/{artifact id}/zip``, a zip holding ``post-merge-verdict.json``; new ``GitHubClient`` byte
   download). Never the issues API. Without the three options no history is read (window of one run).
   ``--lane timing`` never escalates.
2. ``build_verdict_file(..., history=None, tunables=None)``: ``history`` is the earlier runs' parsed verdict files, newest
   first, ``None`` for an unreadable one; ``tunables`` defaults to scripts/ci/post_merge_tunables.json and carries
   ``flaky_window_runs`` / ``flaky_red_threshold``. ``pass_on_retry_window`` maps every id that passed on retry in the
   current run or in the first ``window - 1`` history entries to its occurrence count (taken from each entry's
   ``passed_on_retry``); ``window_runs_read`` is 1 + the readable entries used; ``repeated_pass_on_retry`` is the sorted ids
   of the CURRENT run's ``passed_on_retry`` whose count reaches the threshold (correctness lane only), and a non-empty
   list makes ``verdict`` red (``suite.exit_status`` non-zero).
"""

from __future__ import annotations

from ._ending_harness import Cases
from ._flaky_harness import Earlier, FlakyCase, build, lane_id, run_id_of
from ._notice_fakes import REPO, SERVER, import_production
from ._workflow_jobs import REPO_ROOT, find_job, load_workflow

B, C = lane_id("b"), lane_id("c")
SUITE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "post-merge-suite.yml"
FOLLOWUP_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "post-merge-followup.yml"


def earlier_runs(*per_run_ids, start=5):
    """Earlier settled runs numbered ``start`` downwards, newest first, each with its passed-on-retry ids."""
    return [Earlier(start - index, tuple(ids)) for index, ids in enumerate(per_run_ids)]


class TestTq600a13XiiiRepeatedPassOnRetry(FlakyCase):
    def _verdict(self, retried, earlier, number=6):
        self.svc.reset()
        self.seed(number, earlier)
        return self.run_verdict(retried, number)

    def test_tq600a_13_xiii_repeated_pass_on_retry_is_red(self):
        # covers: TQ-600a-13-xiii
        # angle: criterion
        """B passed on retry in 0 / 1 / 2 of the last five settled runs: green, green and listed with count 1, red.

        The verdict comes from the real ``verdict`` command over served earlier artifacts; the one-of-five verdict is
        then applied by the real notice job. Wrong versions caught: a threshold of 1 (row one), of 3 (row two), a
        window that stops at the third earlier run, a window that reads a fifth earlier run, a count that includes
        a test that passed on retry only once.
        """
        suite = import_production("scripts.ci.post_merge_suite")
        rows = Cases()
        with rows.case("zero of five: green, nothing listed, five runs read"):
            verdict = self._verdict((), earlier_runs((), (), (), ()))
            self.assertEqual(("green", [], [], {}, 5), self._shape(verdict))
        with rows.case("one of five: green, B counted once, and written to the flaky notice"):
            verdict = self._verdict((B,), earlier_runs((), (), (), ()))
            self.assertEqual(("green", [B], [], {B: 1}, 5), self._shape(verdict))
            self.settle(6, "success")
            applied = self.apply_notice(verdict, 6, "success")
            self.assertEqual(0, applied.code, applied.log)
            self.assertEqual([("create", None)], self.svc.writes())
            body = self.flaky_create()["body"]
            line = [ln for ln in body.splitlines() if f"`{B}`" in ln]
            self.assertTrue(line and "1 of 5" in line[0], f"B is listed with its count:\n{body}")
            self.assertIn(f"{SERVER}/{REPO}/actions/runs/{run_id_of(6)}", body, "the run's link is named")
        with rows.case("two of five: red, B repeated"):
            verdict = self._verdict((B, C), earlier_runs((B,), (), (), ()))
            self.assertEqual(("red", [B, C], [B], {B: 2, C: 1}, 5), self._shape(verdict))
            self.assertEqual(1, suite.exit_status(verdict), "the run's exit status is non-zero")
        with rows.case("two of five, the earlier one at the far edge of the window"):
            verdict = self._verdict((B,), earlier_runs((), (), (), (B,)))
            self.assertEqual(("red", [B], [B], {B: 2}, 5), self._shape(verdict))
        with rows.case("the fifth earlier run is outside the window and is not even read"):
            verdict = self._verdict((B,), earlier_runs((), (), (), (), (B,)))
            self.assertEqual(("green", [B], [], {B: 1}, 5), self._shape(verdict))
            self.assertEqual([], self.svc.artifact_reads(1), "at most window - 1 earlier runs are read")
        rows.check()

    @staticmethod
    def _shape(verdict):
        return (verdict["verdict"], verdict["passed_on_retry"], verdict["repeated_pass_on_retry"], verdict["pass_on_retry_window"], verdict["window_runs_read"])



class TestTq600a13XiiiTunables(FlakyCase):
    def test_tq600a_13_xiii_the_window_and_threshold_come_from_the_tunables(self):
        # covers: TQ-600a-13-xiii
        # angle: boundary
        """The same history is red or green by ``flaky_red_threshold`` and counts three or five runs by ``flaky_window_runs``.

        Wrong versions caught: a literal 2 and a literal 5 in the verdict builder.
        """
        history = [build((B,), run_id=105), build((B,), run_id=104), build((), run_id=103), build((), run_id=102)]
        rows = Cases()
        for threshold, expected in ((3, "red"), (4, "green"), (1, "red")):
            with rows.case(f"threshold {threshold}"):
                verdict = build((B,), run_id=106, history=history, tunables={"flaky_window_runs": 5, "flaky_red_threshold": threshold})
                self.assertEqual((expected, {B: 3}), (verdict["verdict"], verdict["pass_on_retry_window"]))
        with rows.case("a window of three reads two earlier runs"):
            tail_history = [build((), run_id=105), build((), run_id=104), build((B,), run_id=103), build((B,), run_id=102)]
            verdict = build((B,), run_id=106, history=tail_history, tunables={"flaky_window_runs": 3, "flaky_red_threshold": 2})
            self.assertEqual(("green", {B: 1}, 3), (verdict["verdict"], verdict["pass_on_retry_window"], verdict["window_runs_read"]))
        with rows.case("a threshold that is not reached leaves the repeated list empty"):
            verdict = build((B,), run_id=106, history=history, tunables={"flaky_window_runs": 5, "flaky_red_threshold": 4})
            self.assertEqual([], verdict["repeated_pass_on_retry"])
        rows.check()


class TestTq600a13XiiiWiring(FlakyCase):
    def test_tq600a_13_xiii_the_workflows_hand_the_history_inputs_to_the_jobs(self):
        # covers: TQ-600a-13-xiii
        # angle: seam
        """Structural by necessity (a workflow's permissions and step wiring cannot be exercised offline).

        The verdict job may read run history (``actions: read``) and hands the run, repository, API root and token to
        the verdict command through ``env:``; the correctness notice job downloads the previous run's verdict and passes it.
        """
        suite = find_job(load_workflow(SUITE_WORKFLOW), "verdict")[1]
        self.assertEqual("read", (suite.get("permissions") or {}).get("actions"), "the verdict job reads run history")
        classify = next(step for step in suite["steps"] if step.get("id") == "classify")
        self.assertIn("GITHUB_TOKEN", classify.get("env") or {}, "the token reaches the command through env:")
        for option in ("--api-url", "--repo", "--run-id"):
            self.assertIn(option, classify["run"])
        self.assertNotIn("${{", classify["run"], "context reaches the command through env:")
        notice = find_job(load_workflow(FOLLOWUP_WORKFLOW), "notice")[1]
        runs = " ".join(step.get("run", "") for step in notice["steps"])
        self.assertIn("--previous-verdict-file", runs, "the correctness notice job names a not-reproduced red")
        self.assertNotIn("--lane timing", runs)
