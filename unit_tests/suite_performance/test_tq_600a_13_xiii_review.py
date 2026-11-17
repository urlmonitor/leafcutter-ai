"""
Tests for TQ-600a-13-xiii, review follow-ups -- a short read never closes the flaky notice, the step summary names a repeated
pass-on-retry and a short history, an id counts once per run, the newest of several verdict artifacts is the one read, a
candidate alone writes the notice, and ``post_merge_previous_run --lane correctness`` reads the correctness history.

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xiii.yaml
Production contract: see test_tq_600a_13_xiii.py and test_tq_600a_13_xiii_notice.py.
"""

from __future__ import annotations

import contextlib
import io
import os
import tempfile
from pathlib import Path
from unittest import mock

from ._ending_harness import Cases
from ._flaky_harness import FLAKY_LABEL, Earlier, FlakyCase, build, lane_id, run_id_of, verdict_zip
from ._notice_fakes import REPO, import_production, make_verdict, run_record
from .test_tq_600a_13_xiii import earlier_runs
from .test_tq_600a_13_xiii_notice import SAME_HEAD, line_for, windowed

A, B = lane_id("a"), lane_id("b")
SHORT = "short pass-on-retry history"


class _StubClient:
    """Serves one artifact list and records which zip was downloaded."""

    def __init__(self, artifacts):
        self.artifacts, self.downloaded = artifacts, []

    def get(self, path, query=None):
        return {"artifacts": self.artifacts}

    def get_bytes(self, path):
        self.downloaded.append(path)
        return verdict_zip(build((B,), run_id=105))


def _artifact(number, created):
    return {"id": number, "name": "post-merge-verdict", "expired": False, "created_at": created}


class TestTq600a13XiiiReviewFollowUps(FlakyCase):
    def _summary_of(self, retried, earlier):
        self.svc.reset()
        self.seed(6, earlier)
        path = Path(tempfile.mkdtemp(dir=self.tmp)) / "summary.md"
        self.run_verdict(retried, 6, environ={"GITHUB_STEP_SUMMARY": str(path)})
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def test_tq600a_13_xiii_a_clean_window_with_a_short_read_never_closes_the_notice(self):
        # covers: TQ-600a-13-xiii
        # angle: failure
        """A clean window of 3 of 5 runs read says nothing about the other two: the open flaky notice stays open, no write.

        Wrong versions caught: closing on an empty window without checking how much of it was read.
        """
        short = windowed((), {})
        short["window_runs_read"] = 3
        self.svc.reset()
        self.svc.add_issue(1, title="Flaky", body="old", labels=[FLAKY_LABEL])
        applied = self.apply_notice(short, 7, "success")
        self.assertEqual(0, applied.code, applied.log)
        self.assertEqual([], self.svc.writes())
        self.assertEqual("open", self.svc.issues[1]["state"])

    def test_tq600a_13_xiii_the_step_summary_names_a_repeat_and_a_short_history(self):
        # covers: TQ-600a-13-xiii
        # angle: discrimination
        """Repeated pass-on-retry ids are named; a short history is warned about, but not on a repository's first runs.

        Wrong versions caught: no repeated line; no warning for an unreadable earlier artifact; a warning on the first
        runs of a repository; a warning when the whole window was read.
        """
        rows = Cases()
        with rows.case("a repeated pass-on-retry id is named"):
            text = self._summary_of((B,), earlier_runs((B,), (), (), ()))
            self.assertTrue(any("repeated pass-on-retry:" in ln and B in ln for ln in text.splitlines()), text)
        with rows.case("one unreadable earlier artifact of four: a short-history warning"):
            text = self._summary_of((), [Earlier(5, (), "corrupt"), Earlier(4), Earlier(3), Earlier(2)])
            warning = [ln for ln in text.splitlines() if SHORT in ln]
            self.assertTrue(warning and "4 of 5" in warning[0], text)
        with rows.case("only two settled runs exist yet: no warning"):
            self.assertNotIn(SHORT, self._summary_of((), [Earlier(5)]))
        with rows.case("the whole window was read: no warning"):
            self.assertNotIn(SHORT, self._summary_of((), earlier_runs((), (), (), ())))
        rows.check()

    def test_tq600a_13_xiii_an_id_counts_once_per_run(self):
        # covers: TQ-600a-13-xiii
        # angle: boundary
        """An earlier verdict that lists B twice is one run of B, not two.

        Wrong versions caught: a count that adds an earlier run's duplicate ids (threshold 3 would then be reached).
        """
        earlier = build((B,), run_id=run_id_of(5))
        earlier["passed_on_retry"] = [B, B]
        verdict = build((B,), run_id=run_id_of(6), history=[earlier], tunables={"flaky_window_runs": 5, "flaky_red_threshold": 3})
        self.assertEqual(("green", {B: 2}), (verdict["verdict"], verdict["pass_on_retry_window"]))

    def test_tq600a_13_xiii_the_newest_of_several_verdict_artifacts_is_read(self):
        # covers: TQ-600a-13-xiii
        # angle: discrimination
        """A re-run leaves two ``post-merge-verdict`` artifacts: the one with the newest ``created_at`` is downloaded.

        Wrong versions caught: the first listed, or the last listed, whichever the service happens to order first.
        """
        window = import_production("scripts.ci._flaky_window")
        old, new, other = _artifact(1, "2026-10-01T00:00:00Z"), _artifact(2, "2026-10-02T00:00:00Z"), {**_artifact(3, "2026-10-09T00:00:00Z"), "name": "other"}
        for order in ((old, new, other), (new, old, other)):
            client = _StubClient(list(order))
            self.assertIsNotNone(window._read_one(client, REPO, 105))
            self.assertEqual([f"/repos/{REPO}/actions/artifacts/2/zip"], client.downloaded)

    def test_tq600a_13_xiii_a_timing_candidate_alone_creates_the_notice_and_keeps_it_open(self):
        # covers: TQ-600a-13-xiii
        # angle: discrimination
        """A clean window and no retry this run, but a red at X then green at X: the notice is created (or edited), never closed.

        Wrong versions caught: a candidate that is dropped because nothing passed on retry; a notice closed on the empty window.
        """
        current = windowed((), {}, head_sha=SAME_HEAD)
        red = make_verdict("red", run_id=run_id_of(6), head_sha=SAME_HEAD, failing=[A])
        self.svc.reset()
        self.assertEqual(0, self.apply_notice(current, 7, "success", previous=red).code)
        created = self.created(FLAKY_LABEL)
        self.assertEqual(1, len(created), self.svc.writes())
        self.assertIn("timing", line_for(created[0]["body"], A).lower())
        self.svc.reset()
        self.svc.add_issue(1, title="Flaky", body="old", labels=[FLAKY_LABEL])
        self.assertEqual(0, self.apply_notice(current, 7, "success", previous=red).code)
        self.assertEqual([("edit", 1)], self.svc.writes())
        self.assertEqual("open", self.svc.issues[1]["state"])

    def test_tq600a_13_xiii_previous_run_reads_the_lane_it_is_asked_for(self):
        # covers: TQ-600a-13-xiii
        # angle: seam
        """``--lane correctness`` names the previous CORRECTNESS run; the default (timing) still reads the timing history.

        Wrong versions caught: a ``--lane`` that is accepted and ignored.
        """
        previous = import_production("scripts.ci.post_merge_previous_run")
        self.svc.reset()
        self.svc.runs = [run_record(6, status="in_progress"), run_record(5)]
        self.svc.timing_runs = [run_record(16, status="in_progress"), run_record(15)]

        def printed(*argv):
            out = io.StringIO()
            env = {"GITHUB_TOKEN": "fake-token"}
            with mock.patch.dict(os.environ, env), contextlib.redirect_stdout(out):
                code = previous.main(["--api-url", self.svc.url, "--repo", REPO, *argv])
            self.assertEqual(0, code)
            return out.getvalue().strip()

        rows = Cases()
        with rows.case("--lane correctness, a correctness run id"):
            self.assertEqual(str(run_id_of(5)), printed("--lane", "correctness", "--run-id", str(run_id_of(6))))
        with rows.case("the default lane is timing: a correctness run id is not in its history"):
            self.assertEqual("", printed("--run-id", str(run_id_of(6))))
        with rows.case("the default lane still finds the timing predecessor"):
            self.assertEqual(str(run_id_of(15)), printed("--run-id", str(run_id_of(16))))
        rows.check()
