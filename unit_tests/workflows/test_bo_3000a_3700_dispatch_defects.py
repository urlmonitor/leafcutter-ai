"""Behavioral tests for two build-feature.js dispatch defects found by driving a real epic.

Covers:
  BO-3000a — "A handoff that names its target the way the agent template
              prescribes is honoured, not refused for omitting a field the
              template never mentions."
  BO-3700  — "Work that becomes necessary while a ticket is being driven is
              still done, instead of being decided against before it was known
              about."

WHERE THESE CAME FROM. One /build-feature run on
EPIC-TheNumberingGuaranteeHoldsAtEveryStage (2026-09-01, 73 agents, 0 of 12
tickets completed). Three of the four tickets in batch 1 died on these two
defects; the fourth halted correctly for an unrelated reason.

THE TWO DEFECTS, AND WHY THEY LOOK LIKE ONE.

  BO-3700 — driveTicketPhases() computes `neededPhases` ONCE, before any phase
  runs, then iterates that captured array. `architect-review` decides whether an
  ADR is required and sets `agents.adr-author: needed` when it is. That
  promotion lands in the record, the driver's own read-back reports it back in
  `needed_phases`, and nothing consumes it: the read-back feeds the COMPLETION
  decision, never the DISPATCH decision. Compounding it, phaseOrder puts
  adr-author at priority 2 and architect-review — its decider — at 4, so even a
  live pending set walked forward-only is already past the slot.

  BO-3000a — templates/agents/python-coder.md §"Test Delegation" defines a
  handoff as: write a `### <agent>` block under `## Implementation Tasks`, and
  return `(status: handoff)`. It never mentions a `handoff_target` JSON field.
  The driver reads only that field and refuses on `undefined`. The agent
  complied with its template and was rejected for it.

WHAT MUST NOT REGRESS. BO-3000 requires an UNRESOLVABLE handoff to fail closed,
and that is correct — guessing a re-dispatch target is worse than refusing.
test_two_candidate_agents_in_implementation_tasks_still_refuses and
unit_tests/workflows/test_bo_3000_handoff_routing.py (5 tests, green before this
change) are the guards on that. BO-3000a narrows what "unresolvable" means; it
does not relax the refusal.

REAL-ARTIFACT NOTE. `## Agent Contracts` also carries `### <agent>` subsections
— `### documentation-expert` is routine — so a heading scan not scoped to
`## Implementation Tasks` resolves the WRONG agent on an ordinary ticket. That
is not hypothetical: it is the on-disk shape of GE-122d-1, the very ticket this
defect was found on. test_agent_contracts_subsection_is_not_read_as_a_handoff_target
pins the scoping.

Every test EXECUTES build-feature.js's own top-level body through the driver
harness and asserts on the observed dispatch sequence — never on source text.
Per CLAUDE.md "Gate / Workflow ACs — Verify Behaviorally, Not by Grep".
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prompt_assembly")
)

import _driver_harness as H  # noqa: E402

TICKET = "01_ticket.md"


class _DriveCase(unittest.TestCase):
    """Drives one ticket through build-feature.js with a controlled phase set."""

    def setUp(self):
        if not H.node_available():
            self.skipTest("node is not available on PATH")
        self._tmpdirs = []

    def tearDown(self):
        for path in self._tmpdirs:
            shutil.rmtree(path, ignore_errors=True)

    def _worktree(self) -> str:
        path = tempfile.mkdtemp(prefix="bf-dispatch-")
        self._tmpdirs.append(path)
        return path

    def _drive(self, phases, results, *, agent_statuses=None, body_extra=None):
        """Write a real record, run the real driver, return (observation, ticket_path)."""
        worktree = self._worktree()
        ticket_path = H.write_ticket_record(
            worktree,
            TICKET,
            phases,
            agent_statuses=agent_statuses,
            # A key AFTER the agents: map — without it the harness's parseRecord
            # lookahead never matches the map and the driver is told the record
            # names no needed phase at all. Real tickets always carry trailing
            # keys, so this is authentic rather than a workaround artifact.
            extra_frontmatter={"component": "build-orchestration"},
        )
        if body_extra:
            with open(ticket_path, "a", encoding="utf-8") as handle:
                handle.write(body_extra)
        scenario = H.single_ticket_scenario(
            worktree,
            ticket_path,
            {
                "title": "Dispatch-defect case",
                # `phases` is what the ticket-planner stub turns into the
                # driver's opening ordered_phases. Omitting it makes the planner
                # name nothing and the drive dispatches zero agents — which
                # looks like a red baseline and measures nothing at all.
                "phases": phases,
                "has_test_requirements": True,
                "results": results,
            },
        )
        observation = H.run_driver(H.BUILD_FEATURE_JS, scenario)
        return observation, ticket_path


class TestMidDrivePromotionIsDispatched(_DriveCase):
    """BO-3700 — a phase promoted to `needed` mid-drive must still run."""

    def test_agent_promoted_mid_drive_is_dispatched_before_the_ticket_concludes(self):
        # covers: BO-3700
        # angle: criterion
        observation, _ = self._drive(
            ["architect-review", "test-writer", "python-coder"],
            {
                # architect-review does what it really does: decides an ADR is
                # required and writes adr-author: needed into the record.
                "architect-review": {"status": "ok", "promotes": ["adr-author"]},
                "test-writer": {"status": "ok"},
                "python-coder": {"status": "ok"},
            },
        )
        dispatched = H.phase_dispatch_labels(observation)
        self.assertIn(
            "adr-author",
            dispatched,
            "architect-review promoted adr-author to needed and the driver never "
            f"dispatched it. Dispatched: {dispatched}",
        )

    def test_promoted_agent_with_earlier_priority_runs_next_not_never(self):
        # covers: BO-3700
        # angle: boundary
        observation, _ = self._drive(
            ["architect-review", "test-writer", "python-coder"],
            {
                "architect-review": {"status": "ok", "promotes": ["adr-author"]},
                "test-writer": {"status": "ok"},
                "python-coder": {"status": "ok"},
            },
        )
        dispatched = H.phase_dispatch_labels(observation)
        self.assertIn("adr-author", dispatched, f"adr-author never ran: {dispatched}")
        # adr-author is priority 2; it was promoted by architect-review at 4.
        # It must land BEFORE python-coder, which depends on the ADR existing.
        self.assertLess(
            dispatched.index("adr-author"),
            dispatched.index("python-coder"),
            "adr-author ran after python-coder — the coder was made to work "
            f"against a contract that had not been recorded yet: {dispatched}",
        )

    def test_the_driver_was_told_adr_author_was_needed(self):
        # covers: BO-3700
        # angle: seam
        #
        # Not a duplicate of the two above: this asserts the SIGNAL exists in the
        # reply the driver received. If this passes while they fail, the defect is
        # provably "computed and discarded" rather than "never observed" — which
        # is the difference between a wiring fix and new machinery.
        observation, _ = self._drive(
            ["architect-review", "test-writer", "python-coder"],
            {
                "architect-review": {"status": "ok", "promotes": ["adr-author"]},
                "test-writer": {"status": "ok"},
                "python-coder": {"status": "ok"},
            },
        )
        reported = [
            entry
            for entry in observation.get("readbacks", [])
            if "adr-author" in (entry.get("needed_phases") or [])
        ]
        self.assertTrue(
            reported,
            "no read-back reported adr-author as needed — the promotion never "
            "reached the driver, so this is not the computed-and-discarded shape",
        )

    def test_drive_with_no_promotion_dispatches_the_identical_sequence(self):
        # covers: BO-3700
        # angle: criterion
        #
        # The regression guard: re-deriving the pending set must not widen
        # dispatch on an ordinary drive.
        observation, _ = self._drive(
            ["architect-review", "test-writer", "python-coder"],
            {
                "architect-review": {"status": "ok"},
                "test-writer": {"status": "ok"},
                "python-coder": {"status": "ok"},
            },
        )
        dispatched = H.phase_dispatch_labels(observation)
        self.assertEqual(
            ["architect-review", "test-writer", "python-coder"],
            dispatched,
            f"an ordinary drive changed its dispatch sequence: {dispatched}",
        )

    def test_already_signed_off_agent_named_as_needed_is_not_redispatched(self):
        # covers: BO-3700
        # angle: boundary
        observation, _ = self._drive(
            ["architect-review", "test-writer", "python-coder"],
            {
                # Promote an agent that has ALREADY signed off. Re-deriving the
                # pending set from the record must not resurrect it.
                "architect-review": {"status": "ok", "promotes": ["test-writer"]},
                "test-writer": {"status": "ok"},
                "python-coder": {"status": "ok"},
            },
        )
        dispatched = H.phase_dispatch_labels(observation)
        self.assertEqual(
            1,
            dispatched.count("test-writer"),
            f"test-writer was dispatched more than once: {dispatched}",
        )

    def test_unknown_agent_name_in_needed_phases_is_ignored_not_dispatched(self):
        # covers: BO-3700
        # angle: failure
        observation, _ = self._drive(
            ["architect-review", "test-writer", "python-coder"],
            {
                "architect-review": {"status": "ok", "promotes": ["not-a-real-agent"]},
                "test-writer": {"status": "ok"},
                "python-coder": {"status": "ok"},
            },
        )
        dispatched = H.phase_dispatch_labels(observation)
        self.assertNotIn(
            "not-a-real-agent",
            dispatched,
            f"an unrecognised agent name became a dispatch: {dispatched}",
        )


class TestHandoffTargetResolvedFromRecord(_DriveCase):
    """BO-3000a — a handoff named through the template's channel is honoured."""

    def test_handoff_without_target_field_resolves_target_from_implementation_tasks(self):
        # covers: BO-3000a
        # angle: criterion
        observation, _ = self._drive(
            ["test-writer", "python-coder"],
            {
                "test-writer": {"status": "ok"},
                # Exactly the real shape: writes the ### test-writer block, then
                # returns status: handoff with NO handoff_target field.
                "python-coder": {
                    "status": "handoff",
                    "adds_implementation_task": "test-writer",
                    "message": "4 of 6 red-baseline tests need a fixture-path fix",
                },
            },
        )
        dispatched = H.phase_dispatch_labels(observation)
        self.assertEqual(
            2,
            dispatched.count("test-writer"),
            "python-coder handed off to test-writer through the channel its own "
            "template prescribes, and test-writer was not re-dispatched. "
            f"Dispatched: {dispatched}",
        )

    def test_agent_contracts_subsection_is_not_read_as_a_handoff_target(self):
        # covers: BO-3000a
        # angle: real_artifact
        #
        # The record carries ### documentation-expert under ## Agent Contracts
        # and NOTHING under ## Implementation Tasks — the ordinary shape of a
        # real ticket. There is no handoff target, so the drive must refuse
        # rather than re-dispatch documentation-expert.
        observation, _ = self._drive(
            ["test-writer", "python-coder"],
            {
                "test-writer": {"status": "ok"},
                "python-coder": {"status": "handoff"},
            },
            body_extra=(
                "\n## Agent Contracts\n\n### documentation-expert\n\n"
                "Existing docs to update / cross-link:\n\n"
                "- docs/architecture/components/commit-guardian.md\n"
            ),
        )
        dispatched = H.phase_dispatch_labels(observation)
        self.assertNotIn(
            "documentation-expert",
            dispatched,
            "a ### documentation-expert heading under ## Agent Contracts was "
            f"mistaken for a handoff target: {dispatched}",
        )
        self.assertEqual(
            "blocked",
            (observation.get("result") or {}).get("status"),
            "a handoff naming no resolvable target must still fail closed",
        )

    def test_two_candidate_agents_in_implementation_tasks_still_refuses(self):
        # covers: BO-3000a
        # angle: boundary
        #
        # BO-3000's fail-closed promise: the fallback resolves, it does not guess.
        observation, _ = self._drive(
            ["test-writer", "python-coder"],
            {
                "test-writer": {"status": "ok"},
                "python-coder": {"status": "handoff"},
            },
            body_extra=(
                "\n## Implementation Tasks\n\n"
                "### test-writer\n\n- [ ] one thing\n\n"
                "### documentation-expert\n\n- [ ] another thing\n"
            ),
        )
        self.assertEqual(
            "blocked",
            (observation.get("result") or {}).get("status"),
            "two candidate agents under ## Implementation Tasks is ambiguous and "
            "must refuse, not pick one",
        )

    def test_explicit_handoff_target_field_takes_precedence_over_the_record(self):
        # covers: BO-3000a
        # angle: criterion
        observation, _ = self._drive(
            ["test-writer", "python-coder"],
            {
                "test-writer": {"status": "ok"},
                "python-coder": {
                    "status": "handoff",
                    "handoff_target": "test-writer",
                    # A DIFFERENT agent named in the record. The explicit field
                    # must win, so this drive must not dispatch architect-review.
                    "adds_implementation_task": "architect-review",
                },
            },
        )
        dispatched = H.phase_dispatch_labels(observation)
        self.assertEqual(
            2,
            dispatched.count("test-writer"),
            f"the explicit handoff_target was not honoured: {dispatched}",
        )
        self.assertNotIn(
            "architect-review",
            dispatched,
            f"the record overrode an explicit handoff_target: {dispatched}",
        )

    def test_handoff_fallback_is_reachable_from_the_workflow_top_level_body(self):
        # covers: BO-3000a
        # angle: reachability
        observation, _ = self._drive(
            ["test-writer", "python-coder"],
            {
                "test-writer": {"status": "ok"},
                "python-coder": {
                    "status": "handoff",
                    "adds_implementation_task": "test-writer",
                },
            },
        )
        self.assertIsNone(
            observation.get("error"),
            f"the driver threw instead of running: {observation.get('error')}",
        )
        handed = [
            entry
            for entry in observation.get("readbacks", [])
            if "test-writer" in (entry.get("implementation_task_agents") or [])
        ]
        self.assertTrue(
            handed,
            "no read-back carried the ### test-writer subsection — the driver was "
            "never handed a resolvable target, so a pass here would prove nothing",
        )


if __name__ == "__main__":
    unittest.main()
