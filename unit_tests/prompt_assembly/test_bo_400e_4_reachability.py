"""
MODULE: test_bo_400e_4_reachability
GOAL: Provide the REQUIRED reachability test for the BO-400e-4 AC -- prove
    the one-answer-per-condition property is reached by actually executing
    the real production workflow script, not by calling an in-process helper
    directly.
BUSINESS CONTEXT: Covers ADR-048 (docs/architecture/adrs/ADR-048-order-
    independent-per-ticket-completion.md), Section 11. See
    test_bo_400e_4_fixtures for the full fixture-shape rationale. AUTHORED
    DELIBERATELY (it-po): because this record carries an authored
    test_spec, the ticket generator's own reachability floor would otherwise
    append a generic sentinel whose text asserts "the AC authored no
    test_spec, so the entry point is not declared" -- false here, and
    misleading on precisely the record whose entry point and run shape are
    load-bearing.
ARCHITECTURE: Carried out of test_bo_400e_4.py (GE-127a-1 / GE-127b-1
    file-size split, no behaviour change). Subclasses
    test_bo_400e_4_fixtures._FourTicketOneRunCase and reuses its
    _assert_three_refused_one_written() shared assertion, plus the
    harness's H.phase_dispatches() / H.writes_for() observation surfaces to
    prove real per-ticket dispatch and a real subprocess write occurred.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _driver_harness as H  # noqa: E402
from test_bo_400e_4_fixtures import (  # noqa: E402
    ALL_LABELS,
    IDENTICAL_LABELS,
    OUTSTANDING_PHASE,
    _FourTicketOneRunCase,
)

# ---------------------------------------------------------------------------
# 4 -- REQUIRED reachability: a real workflow run, carrying all four tickets
# ---------------------------------------------------------------------------


class TestOneAnswerPerConditionIsReachableFromARealWorkflowRun(_FourTicketOneRunCase):
    def test_one_answer_per_condition_is_reachable_from_a_real_workflow_run(self):
        # covers: BO-400e-4
        # angle: reachability
        """REQUIRED -- invoke the production entry point: load and execute
        the real workflow script via
        unit_tests/prompt_assembly/harness_build_ticket_guard.mjs, carrying
        all four tickets in one run, and assert the per-ticket record writes
        the run actually performed. Do NOT satisfy this by importing the
        completion helper and calling it four times: that is the
        single-ticket shape the record's own rationale rules out (ADR-048
        Section 11), and it passes on the broken driver. AUTHORED
        DELIBERATELY (it-po): because this record carries an authored
        test_spec, the ticket generator's own reachability floor would
        otherwise append a generic sentinel whose text asserts 'the AC
        authored no test_spec, so the entry point is not declared' -- false
        here, and misleading on precisely the record whose entry point and
        run shape are load-bearing."""
        worktree = self._worktree()
        observation, paths = self._drive(worktree, order=list(ALL_LABELS))
        self.assertIsNone(observation["error"], observation.get("error"))

        # PROOF OF REAL EXECUTION, not an in-process helper call: a real
        # dispatch was observed for the outstanding phase of EACH identical
        # ticket, and that dispatch's own prompt names THAT ticket's own real
        # on-disk path -- something only a real per-ticket dispatch loop
        # inside the executed script can produce.
        dispatches = H.phase_dispatches(observation)
        for label in IDENTICAL_LABELS:
            path = paths[label]
            matching = [
                d
                for d in dispatches
                if d.get("ticket_path") == path and d.get("label") == OUTSTANDING_PHASE
            ]
            self.assertTrue(
                matching,
                f"ticket {label}: no real {OUTSTANDING_PHASE} dispatch was "
                f"observed against its own on-disk record path ({path}) during "
                f"the executed run. dispatches observed: {dispatches}",
            )

        # A real completion write was dispatched and applied for the control
        # ticket DURING this same executed run -- and it went through a REAL
        # subprocess of scripts/set_ticket_status.py (the checking mechanism
        # BO-400e-3 established as the single door), not an in-process stub.
        # This is the cross-layer seam this suite touches: the JS driver's
        # own dispatch text is the producer, and a genuinely executed Python
        # subprocess is the consumer.
        control_writes = H.writes_for(observation, paths["D"])
        self.assertTrue(
            control_writes,
            "no completion write was observed for the control ticket during "
            "the real workflow run.",
        )
        self.assertTrue(
            all(w["applied"] for w in control_writes),
            f"the control ticket's completion write was dispatched but not "
            f"applied: {control_writes}",
        )
        self.assertTrue(
            all(w["mechanism"] == "script" for w in control_writes),
            f"the control ticket's completion write did not go through a "
            f"real scripts/set_ticket_status.py subprocess: {control_writes}",
        )
        self.assertTrue(
            all(w["script_exit_code"] == 0 for w in control_writes),
            f"the real set_ticket_status.py subprocess did not exit 0 for "
            f"the control ticket: {control_writes}",
        )

        # And the per-ticket record writes the run performed really do
        # disagree correctly between the refused trio and the written
        # control -- the whole content of this AC, reached by executing the
        # real script rather than by calling a helper directly.
        self._assert_three_refused_one_written("reachability", observation, paths)
