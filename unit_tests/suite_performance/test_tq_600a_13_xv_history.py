"""
Tests for TQ-600a-13-xv (history half) -- ``_run_history.verdict_changed`` and the fail-loud reads of the re-evaluation.

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xv.yaml
(and the delivers_to of TQ-600a-13-v: ``verdict_changed(runs, triggering_run_id) -> bool | None``).

ASSUMED PRODUCTION CONTRACT (written by test-writer; python-coder builds this).

``verdict_changed`` does NOT exist on main yet (TQ-600a-13-v did not deliver it); it is added to
scripts/ci/_run_history.py, pure and stdlib-only, on the single settled-run rule (``select_verdict_run`` /
``_skip_reason``), NOT a second one:
  * the TRIGGERING run is the run in ``runs`` with ``id == triggering_run_id``. It must be settled (tested main, completed,
    not a superseded cancellation); otherwise the answer is None (the fan-out then does nothing). An id that is not in
    ``runs`` is also None.
  * the PREVIOUS run is the settled run with the highest ``run_number`` below the triggering run's; a superseded
    cancellation, a run of another event or branch and a run still in progress are passed over, never "the previous run".
  * the answer is True when exactly one of the two is green (conclusion ``success``) and False when both are green or both
    are not green (red, did-not-complete, timed out, cancelled alike: both are held). No previous settled run: not True.
  * order comes from ``run_number``, never from list position; no jobs are read (green versus not-green needs none).
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ._ending_harness import CHECK, Cases
from ._notice_fakes import import_production, run_record
from ._reeval_harness import SHAS, SUITE_NAME, ReevalService, run_reeval, seed_world, suite_history


def _history(*rows):
    """Run N of the history has id 100 + N; a row is a conclusion, or ``(conclusion, status)``, or a ready record."""
    runs = []
    for number, row in enumerate(rows, start=1):
        if isinstance(row, dict):
            runs.append(row)
            continue
        conclusion, status = row if isinstance(row, tuple) else (row, "completed")
        runs.append(run_record(number, conclusion, status=status))
    return runs


def _verdict_changed():
    history = import_production("scripts.ci._run_history")
    found = getattr(history, "verdict_changed", None)
    CHECK.assertTrue(callable(found), "scripts.ci._run_history.verdict_changed is not implemented yet")
    return found


class TestTq600a13XvVerdictChanged(unittest.TestCase):
    def test_tq600a_13_xv_verdict_changed_follows_the_settled_run_rule(self):
        # covers: TQ-600a-13-xv
        # angle: boundary
        """Each row: (history, triggering run id, expected answer). Green versus not-green decides; unsettled runs answer None."""
        pr_event = run_record(2, "failure", event="pull_request")
        rows = {
            "green then red": (_history("success", "failure"), 102, True),
            "red then green": (_history("failure", "success"), 102, True),
            "red then red": (_history("failure", "failure"), 102, False),
            "green then green": (_history("success", "success"), 102, False),
            "did not complete then red (both held)": (_history("timed_out", "failure"), 102, False),
            "red then a lone cancellation (both held)": (_history("failure", "cancelled"), 102, False),
            "green then a lone cancellation": (_history("success", "cancelled"), 102, True),
            "previous skips a superseded cancellation, same verdict": (_history("success", "cancelled", "success"), 103, False),
            "previous skips a superseded cancellation, other verdict": (_history("success", "cancelled", "failure"), 103, True),
            "an event-pull_request run between is not the previous run": (_history("success", pr_event, "success"), 103, False),
            "triggering run superseded by a newer one": (_history("success", "cancelled", ("", "in_progress")), 102, None),
            "triggering run not completed": (_history("success", ("", "in_progress")), 102, None),
            "triggering run is not a main run": (_history("success", pr_event), 102, None),
            "triggering run unknown": (_history("success", "failure"), 999, None),
        }
        checked, rows_failed = _verdict_changed(), Cases()
        for label, (runs, trigger, expected) in rows.items():
            with rows_failed.case(label):
                self.assertIs(expected, checked(runs, trigger))
            with rows_failed.case(f"{label} (list order reversed)"):
                self.assertIs(expected, checked(list(reversed(runs)), trigger), "order comes from run_number, not list position")
        with rows_failed.case("no previous settled run is not a change"):
            self.assertIsNot(True, checked(_history("failure"), 101))
            self.assertFalse(checked(_history("failure"), 101))
        rows_failed.check()


class TestTq600a13XvReadsFailLoud(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.svc = ReevalService()

    @classmethod
    def tearDownClass(cls):
        cls.svc.close()

    def test_tq600a_13_xv_an_unreadable_history_or_pull_request_list_re_runs_nothing_and_fails_loudly(self):
        # covers: TQ-600a-13-xv
        # angle: failure
        """A 500 on the suite history, or on the pull request list after a changed verdict: non-zero exit, no re-run request.

        A silent exit 0 here would read as "nothing changed" while held pull requests stay held (or passed ones stay mergeable).
        Control: with the same world and nothing failing the same history re-runs the three completed holds.
        """
        rows = Cases()
        with tempfile.TemporaryDirectory() as raw:
            for label, failing in {"history unreadable": ["/actions/workflows/post-merge-suite.yml/runs"], "pull request list unreadable": ["/pulls"]}.items():
                self.svc.reset()
                seed_world(self.svc)
                suite_history(self.svc, "success", "failure")
                self.svc.failing = failing
                result = run_reeval(self.svc, Path(raw), SUITE_NAME, 102, SHAS["A"])
                with rows.case(label):
                    self.assertNotEqual(0, result.code, f"{label}: must not exit 0\n{result.log}")
                    self.assertEqual([], self.svc.rerun_ids(), f"{label}: nothing may be re-run on a partial read")
            self.svc.reset()
            seed_world(self.svc)
            suite_history(self.svc, "success", "failure")
            with rows.case("control: nothing failing"):
                self.assertEqual(0, run_reeval(self.svc, Path(raw), SUITE_NAME, 102, SHAS["A"]).code)
                self.assertEqual([1005, 1009, 1011], self.svc.rerun_ids())
        rows.check()
