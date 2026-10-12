"""
Tests for TQ-600a-13-xiv, discrimination half -- staleness and the workflow state cost no extra read, and the age
is measured from ``run_started_at``.

Source of truth:
docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xiv.yaml

======================================================================
ASSUMED PRODUCTION CONTRACT (written by test-writer; python-coder builds it)

scripts/ci/post_merge_hold.py evaluate(client, repo, *, now=...). Reads counted on the recording fake via
``HoldService.read_kinds()``: a verdict that needs no held-path detail (pass, stale, never_run) makes exactly
``["runs", "workflow"]``. A disabled workflow makes exactly one workflow-state read and at most one run-history read
(whether it also reads the history is the coder's choice: "no extra request" bounds it, it does not require it).
No jobs read, no notice read, no request of any other kind, for any of them.
Age = ``now - run_started_at``; ``created_at`` is never consulted for it.
======================================================================
"""

from __future__ import annotations

from ._ending_harness import CHECK, Cases
from ._hold_harness import make_run, tunables
from ._xiv_support import XivTestCase

VERDICT_READS = ["runs", "workflow"]


class TestTq600a13xivCost(XivTestCase):
    def test_tq600a_13_xiv_staleness_costs_no_extra_read(self):
        # covers: TQ-600a-13-xiv
        # angle: discrimination
        """Every evaluation makes exactly the workflow-state read and the run-history read: fresh green, stale green,
        never run and no-settled-in-page each give `["runs", "workflow"]`; a disabled workflow with a 1 h green run is
        disabled (fails), with one workflow read and at most one history read and nothing else.

        Wrong versions caught: the disabled state read only on the stale path (a workflow disabled an hour after a
        green run keeps passing); a stale green run passing; a third request (jobs, notices, a second state read) added
        for the new states.
        """
        bound = tunables()["staleness_hours"]
        cases = Cases()
        rows = (
            ("fresh green", [make_run(7, "success", hours_ago=1)], "pass"),
            ("stale green", [make_run(7, "success", hours_ago=bound + 1)], "stale"),
            ("never run", [], "never_run"),
            ("thirty unsettled", [make_run(n, status="in_progress", hours_ago=1) for n in range(1, 31)], "stale"),
        )
        for label, runs, state in rows:
            with cases.case(label):
                CHECK.assertEqual(state, self.verdict(runs)["state"])
                CHECK.assertEqual(VERDICT_READS, self.svc.read_kinds())
        with cases.case("disabled an hour after a green run"):
            verdict = self.verdict([make_run(7, "success", hours_ago=1)], workflow_state="disabled_manually")
            kinds = self.svc.read_kinds()
            CHECK.assertEqual("disabled", verdict["state"], "a disabled workflow must fail whatever the last run was")
            CHECK.assertEqual(1, kinds.count("workflow"), "the workflow state is read on every evaluation")
            CHECK.assertLessEqual(kinds.count("runs"), 1)
            CHECK.assertEqual([], [k for k in kinds if k not in ("workflow", "runs")])
        with cases.case("the workflow state is read on a fresh green evaluation too"):
            self.verdict([make_run(7, "success", hours_ago=1)])
            CHECK.assertEqual(1, self.svc.read_kinds().count("workflow"))
        cases.check()

    def test_tq600a_13_xiv_age_is_measured_from_run_started_at_not_created_at(self):
        # covers: TQ-600a-13-xiv
        # angle: discrimination
        """A re-run keeps its old ``created_at`` and gets a new ``run_started_at``: a green re-run created 60 h ago that
        started 1 h ago passes; a green run created 1 h ago that started 31 h ago is stale; a run without a
        ``run_started_at`` never passes on the strength of a fresh ``created_at``.

        Wrong versions caught: age taken from `created_at` (a re-run looks older than it is, and an old run looks
        younger); `created_at` as a fallback for a missing start time.
        """
        bound = tunables()["staleness_hours"]
        cases = Cases()
        with cases.case("re-run: old created_at, fresh run_started_at"):
            rerun = make_run(7, "success", hours_ago=1)
            rerun["created_at"] = make_run(7, "success", hours_ago=bound * 2)["run_started_at"]
            verdict = self.verdict([rerun])
            CHECK.assertEqual("pass", verdict["state"], verdict["reason"])
        with cases.case("old run_started_at, fresh created_at"):
            run = make_run(7, "success", hours_ago=bound + 1)
            run["created_at"] = make_run(7, "success", hours_ago=1)["run_started_at"]
            CHECK.assertEqual("stale", self.verdict([run])["state"])
        with cases.case("no run_started_at, fresh created_at"):
            run = make_run(7, "success", hours_ago=1)
            run["created_at"] = run.pop("run_started_at")
            CHECK.assertNotEqual("pass", self.verdict([run])["state"])
        cases.check()
