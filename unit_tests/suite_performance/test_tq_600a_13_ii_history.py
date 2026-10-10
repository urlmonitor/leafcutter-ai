"""
Tests for TQ-600a-13-ii, run-history half -- "successive merges never cancel the run in progress":
which run of the post-merge workflow is the settled verdict run.

Split out of ``test_tq_600a_13_ii.py`` (file-size limit); the production contract for
``scripts/ci/_run_history.py`` (``select_verdict_run`` -> Selection with ``.kind``, ``.run``,
``.skipped``) is documented in that file's header. Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-ii.yaml
"""

from __future__ import annotations

import json
import unittest

from .test_tq_600a_13_ii import _field, _import


# --------------------------------------------------------------------------- run history
def _served(runs):
    """Runs as the REST API serves them: through a real JSON round trip."""
    return json.loads(json.dumps({"workflow_runs": runs}))["workflow_runs"]


def _run(number, status="completed", conclusion="success", event="push", branch="main"):
    return {
        "id": 9000 + number,
        "run_number": number,
        "status": status,
        "conclusion": conclusion if status == "completed" else None,
        "event": event,
        "head_branch": branch,
    }


class TestTq600a13iiSettledRun(unittest.TestCase):
    def _select(self, runs):
        return _import("scripts.ci._run_history").select_verdict_run(_served(runs))

    def _reasons(self, selection):
        return {_field(s, "id"): _field(s, "reason") for s in _field(selection, "skipped")}

    def test_tq600a_13_ii_successive_merges_never_cancel_the_run_in_progress(self):
        # covers: TQ-600a-13-ii
        # angle: criterion
        """AC-ii must_catch (run history): superseded cancellations carry no verdict, a lone newest
        cancellation does, order comes from run_number not list position, PR-branch runs never count.
        """
        control = self._select([_run(1)])
        self.assertEqual("settled", _field(control, "kind"))
        self.assertEqual(9001, _field(_field(control, "run"), "id"))
        self.assertEqual([], list(_field(control, "skipped")))

        # a burst: #5 was displaced by #6, which is still running -> the verdict run is #3
        burst = self._select([_run(3), _run(5, conclusion="cancelled"), _run(6, status="in_progress")])
        self.assertEqual(9003, _field(_field(burst, "run"), "id"), "a superseded cancellation must not be the verdict")
        self.assertEqual({9005: "superseded_cancellation", 9006: "not_completed"}, self._reasons(burst))

        # a lone newest cancellation (nothing newer) is settled, and is not green
        lone = self._select([_run(7), _run(8, conclusion="cancelled")])
        self.assertEqual(9008, _field(_field(lone, "run"), "id"), "a lone cancellation must not be skipped")
        self.assertEqual("cancelled", _field(_field(lone, "run"), "conclusion"))

        # a list deliberately NOT newest-first
        scrambled = self._select([_run(2), _run(9, conclusion="failure"), _run(4)])
        self.assertEqual(9009, _field(_field(scrambled, "run"), "id"), "ordering must come from run_number")

        # runs of the same workflow on a pull-request branch are never a main-branch verdict
        pr_runs = [
            _run(10, conclusion="failure", event="pull_request", branch="feat/x"),
            _run(11, conclusion="failure", event="pull_request", branch="main"),
            _run(9),
        ]
        picked = self._select(pr_runs)
        self.assertEqual(9009, _field(_field(picked, "run"), "id"))
        self.assertEqual("not_main", self._reasons(picked)[9010])
        self.assertEqual("not_main", self._reasons(picked)[9011])

        # a cancelled main run whose only "newer" run is a PR-branch run is NOT superseded
        not_superseded = self._select([_run(5, conclusion="cancelled"), _run(6, event="pull_request", branch="feat/x")])
        self.assertEqual(9005, _field(_field(not_superseded, "run"), "id"))
        self.assertEqual("cancelled", _field(_field(not_superseded, "run"), "conclusion"))


if __name__ == "__main__":
    unittest.main()
