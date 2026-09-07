"""Behavioral tests for two build-feature.js dispatch defects found by driving a real epic.

Covers:
  BO-3000a — "A handoff is routed by the target the handing-off agent named in
              its own result, and is refused diagnosably — never inferred from
              the ticket body — when that target is absent or unknown."
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

  BO-3000a — the field evidence (see BO-3000a.yaml notes) showed a coder that
  wrote the `### test-writer` block templates/agents/python-coder.md
  §"Test Delegation" prescribes, returned `(status: handoff)`, and was refused
  because its result named no `handoff_target`. The FIRST fix tried taught the
  driver to infer a target from that same `### <agent>` heading when the field
  was missing. That inference was REJECTED on review and has been REMOVED from
  the driver, not merely left unused: the `## Implementation Tasks` section is
  a general per-agent task breakdown carried by 13 agents and is ambiguous by
  construction (real tickets routinely name more than one), and inference would
  silently re-dispatch an agent on a DELIBERATE targetless halt — the exact
  shape python-coder's contract-shrinkage guard and test-writer's test-drift
  rule use to mean "blocked, needs user authorization, naming nobody on
  purpose." The shipped fix instead makes `handoff_target` a REQUIRED field on
  the handing-off agent's own result (enforced by PHASE_RESULT_SCHEMA's
  conditional `required` when `status: "handoff"`), and makes the two ways a
  handoff can fail to resolve — no target at all, and an unrecognised target —
  diagnosably distinct in the refusal.

WHAT MUST NOT REGRESS. BO-3000 requires an UNRESOLVABLE handoff to fail closed,
and that is correct — guessing a re-dispatch target is worse than refusing.
unit_tests/workflows/test_bo_3000_handoff_routing.py (5 tests, green before this
change and unaffected by it) is the guard on that; this file's
test_unknown_target_is_reproduced_in_the_refusal_and_never_substituted extends
it to the "named but unrecognised" case BO-3000a adds.

NO-INFERENCE NOTE. `## Agent Contracts` also carries `### <agent>` subsections
— `### documentation-expert` is routine — so a heading scan not scoped to
`## Implementation Tasks` would resolve the WRONG agent on an ordinary ticket.
That is not hypothetical: it is the on-disk shape of GE-122d-1, the very ticket
BO-3000a's field evidence was found on. The driver reads NEITHER section for a
handoff target; test_ticket_body_agent_sections_do_not_supply_a_handoff_target
and test_deliberate_targetless_halt_does_not_respawn_a_body_named_agent pin
that absence behaviorally, on tickets that carry both sections populated.

Every test EXECUTES build-feature.js's own top-level body through the driver
harness and asserts on the observed dispatch sequence — never on source text.
Per CLAUDE.md "Gate / Workflow ACs — Verify Behaviorally, Not by Grep".
"""

from __future__ import annotations

import json
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

    def test_mid_drive_promotion_is_reachable_from_the_workflow_top_level_body(self):
        # covers: BO-3700
        # angle: reachability
        #
        # Proof that the re-derivation is exercised by build-feature.js's own
        # top-level driveTicketPhases() body — not by calling
        # absorbPromotedPhases() (or an equivalent extracted helper) directly.
        #
        # The criterion test above (test_agent_promoted_mid_drive_...) only
        # asserts that "adr-author" ends up in the final dispatched-labels
        # list. That alone is not proof of WHERE the promotion logic ran: a
        # "fix" that re-derives the pending set through some other mechanism
        # (a post-hoc cleanup pass after the main loop, or a helper exercised
        # only by a unit test and never wired into the real dispatch loop)
        # could still leave "adr-author" in `dispatched`, for the wrong
        # reason, and the criterion test would stay green.
        #
        # This test instead requires the exact log line the production code
        # emits INLINE, immediately after its own real call to
        # absorbPromotedPhases() inside driveTicketPhases()'s dispatch loop
        # (build-feature.js ~1707-1721, tagged "(BO-3700)" in its own text).
        # That line is built from the live loop's own `phaseName` and
        # `worktreeTicketPath` variables at that exact call site — a
        # standalone test of absorbPromotedPhases() in isolation, or any
        # alternate re-derivation path, could never produce this string,
        # because nothing outside that call site interpolates the real
        # on-disk ticket path into that exact sentence. So this test can go
        # red in a case where the criterion test above stays green — which is
        # what distinguishes a reachability proof from a criterion proof.
        observation, ticket_path = self._drive(
            ["architect-review", "test-writer", "python-coder"],
            {
                "architect-review": {"status": "ok", "promotes": ["adr-author"]},
                "test-writer": {"status": "ok"},
                "python-coder": {"status": "ok"},
            },
        )
        self.assertIsNone(
            observation.get("error"),
            f"the driver threw instead of running: {observation.get('error')}",
        )
        dispatched = H.phase_dispatch_labels(observation)
        self.assertIn(
            "adr-author",
            dispatched,
            f"architect-review promoted adr-author but it was never dispatched: {dispatched}",
        )

        logs = observation.get("logs") or []
        expected_fragment = (
            f"'architect-review' promoted {json.dumps(['adr-author'])} "
            f"to needed in {ticket_path}"
        )
        matching = [
            line for line in logs if expected_fragment in line and "(BO-3700)" in line
        ]
        self.assertTrue(
            matching,
            "did not find the production log line that only the real "
            "driveTicketPhases() top-level body, at its own "
            "absorbPromotedPhases() call site, can emit. Expected a log "
            f"containing {expected_fragment!r} and '(BO-3700)'. This is the "
            "evidence that the promotion path was reached from the workflow's "
            f"own top-level body, not from an extracted helper. Logs observed: "
            f"{logs}",
        )


#: Sentinel meaning "omit this key from the phase result entirely" — distinct
#: from passing None (which serializes to JSON null, a real present-but-not-a-
#: string value the schema and driver must also refuse).
_OMIT = object()


def _latest_signoff_status(records, ticket_path, agent):
    """The status of the LAST sign-off entry a ticket record carries for
    ``agent``, or None if it carries none at all. Used to prove a handing-off
    phase was not recorded as completed: a completed phase's latest entry
    reads 'ok' or 'signed_off' (POSITIVE_SIGNOFF_STATUSES); a phase that
    handed off leaves its own '(status: handoff)' entry instead.
    """
    entries = [
        s
        for s in (records.get(ticket_path) or {}).get("signoffs", [])
        if s.get("agent") == agent
    ]
    return entries[-1]["status"] if entries else None


def _signoff_count(records, ticket_path, agent):
    return sum(
        1
        for s in (records.get(ticket_path) or {}).get("signoffs", [])
        if s.get("agent") == agent
    )


def _implementation_task_agents_after_run(observation, ticket_path):
    """The `implementation_task_agents` the LAST read-back for this ticket
    carried — i.e. what the driver was told after every phase had run,
    including any `### <agent>` block a phase wrote during its own dispatch.
    """
    entries = [
        rb
        for rb in observation.get("readbacks") or []
        if rb.get("ticket_path") == ticket_path
    ]
    return entries[-1].get("implementation_task_agents") or [] if entries else []


class TestHandoffTargetResolvedFromRecord(_DriveCase):
    """BO-3000a — a handoff is routed by handoff_target alone, never by the
    ticket body, and is refused diagnosably when handoff_target cannot be
    used.
    """

    def test_handoff_naming_a_known_agent_redispatches_exactly_that_agent(self):
        # covers: BO-3000a
        # angle: criterion
        observation, ticket_path = self._drive(
            ["test-writer", "python-coder", "sql-coder"],
            {
                "test-writer": {"status": "ok"},
                "python-coder": {
                    "status": "handoff",
                    "handoff_target": "test-writer",
                    "message": "4 of 6 red-baseline tests need a fixture-path fix",
                    # A DIFFERENT agent named in the ticket body. The explicit
                    # field is the driver's ONLY source for the target, so this
                    # must be ignored, not raced against handoff_target.
                    "adds_implementation_task": "architect-review",
                },
                "sql-coder": {"status": "ok"},
            },
        )
        dispatched = H.phase_dispatch_labels(observation)
        self.assertEqual(
            ["test-writer", "python-coder", "test-writer"],
            dispatched,
            "python-coder handed off to test-writer via handoff_target, and "
            f"test-writer was not re-dispatched next: {dispatched}",
        )
        self.assertNotIn(
            "architect-review",
            dispatched,
            f"a body-named agent was dispatched instead of handoff_target: {dispatched}",
        )
        self.assertNotIn(
            "sql-coder",
            dispatched,
            f"a later phase ran after an unresolved handoff: {dispatched}",
        )
        records = observation.get("records") or {}
        self.assertEqual(
            "handoff",
            _latest_signoff_status(records, ticket_path, "python-coder"),
            "the handing-off phase's own record entry must not read as a "
            "completed ('ok' / 'signed_off') outcome",
        )
        result = observation.get("result") or {}
        self.assertEqual("blocked", result.get("status"))
        self.assertEqual("cross_agent", result.get("classification"))
        self.assertEqual("test-writer", result.get("handoff_target"))

    def test_handoff_with_no_target_refuses_and_dispatches_no_agent(self):
        # covers: BO-3000a
        # angle: failure
        #
        # "the key absent, empty, blank, or not a name" (BO-3000a criteria) —
        # each sub-case must refuse identically.
        cases = [
            ("absent", _OMIT),
            ("empty_string", ""),
            ("blank_whitespace", "   "),
            ("json_null", None),
            ("non_string_type", 123),
        ]
        for label, value in cases:
            with self.subTest(case=label):
                python_coder_result = {"status": "handoff"}
                if value is not _OMIT:
                    python_coder_result["handoff_target"] = value
                observation, _ = self._drive(
                    ["test-writer", "python-coder"],
                    {
                        "test-writer": {"status": "ok"},
                        "python-coder": python_coder_result,
                    },
                )
                dispatched = H.phase_dispatch_labels(observation)
                self.assertEqual(
                    ["test-writer", "python-coder"],
                    dispatched,
                    f"case {label!r}: a targetless handoff dispatched an agent: "
                    f"{dispatched}",
                )
                result = observation.get("result") or {}
                self.assertEqual(
                    "blocked", result.get("status"), f"case {label!r}"
                )
                self.assertIn(
                    "named no handoff target",
                    result.get("message") or "",
                    f"case {label!r}: refusal did not state the result was read "
                    f"and named nothing: {result.get('message')!r}",
                )

    def test_unknown_target_is_reproduced_in_the_refusal_and_never_substituted(self):
        # covers: BO-3000a
        # angle: boundary
        observation, _ = self._drive(
            ["test-writer", "python-coder"],
            {
                "test-writer": {"status": "ok"},
                "python-coder": {
                    "status": "handoff",
                    "handoff_target": "not-a-real-phase-agent-xyz",
                },
            },
        )
        dispatched = H.phase_dispatch_labels(observation)
        self.assertEqual(
            ["test-writer", "python-coder"],
            dispatched,
            f"an unrecognised handoff_target caused a dispatch: {dispatched}",
        )
        result = observation.get("result") or {}
        self.assertEqual("blocked", result.get("status"))
        message = result.get("message") or ""
        self.assertIn(
            "not-a-real-phase-agent-xyz",
            message,
            f"the refusal did not reproduce the unrecognised value verbatim: {message!r}",
        )
        self.assertIn(
            "not an agent this driver recognises",
            message,
            f"the refusal did not state the value was unrecognised: {message!r}",
        )

    def test_ticket_body_agent_sections_do_not_supply_a_handoff_target(self):
        # covers: BO-3000a
        # angle: real_artifact
        #
        # IDENTICAL-REFUSAL test. Ticket A's body names SEVERAL agents, across
        # BOTH sections BO-3000a's criteria calls out — the per-agent task
        # breakdown (## Implementation Tasks, one pre-existing, one added by
        # python-coder's own handoff dispatch) and ## Agent Contracts. Ticket B
        # names nobody anywhere. Both get a targetless handoff. Asserting both
        # merely "blocked" would be weaker than this: two DIFFERENT blocked
        # results would still permit the prose to be influencing something.
        observation_a, ticket_a = self._drive(
            ["test-writer", "python-coder"],
            {
                "test-writer": {"status": "ok"},
                "python-coder": {
                    "status": "handoff",
                    "adds_implementation_task": "test-writer",
                },
            },
            body_extra=(
                "\n## Implementation Tasks\n\n"
                "### documentation-expert\n\n- [ ] pre-existing task\n\n"
                "\n## Agent Contracts\n\n### documentation-expert\n\n"
                "Existing docs to update / cross-link:\n\n"
                "- docs/architecture/components/commit-guardian.md\n"
            ),
        )
        observation_b, ticket_b = self._drive(
            ["test-writer", "python-coder"],
            {
                "test-writer": {"status": "ok"},
                "python-coder": {"status": "handoff"},
            },
        )

        # Prove ticket A really did carry resolvable candidates — several of
        # them — before asserting the driver ignored them. Without this half
        # the drive could be "correctly ignoring" a target that never existed.
        task_agents_a = _implementation_task_agents_after_run(observation_a, ticket_a)
        self.assertEqual(
            {"documentation-expert", "test-writer"},
            set(task_agents_a),
            "ticket A's body did not end up naming several candidate agents — "
            f"the fixture does not exercise what this test claims: {task_agents_a}",
        )
        task_agents_b = _implementation_task_agents_after_run(observation_b, ticket_b)
        self.assertEqual(
            [],
            task_agents_b,
            f"ticket B's body was supposed to name nobody: {task_agents_b}",
        )

        dispatched_a = H.phase_dispatch_labels(observation_a)
        dispatched_b = H.phase_dispatch_labels(observation_b)
        self.assertEqual(["test-writer", "python-coder"], dispatched_a)
        self.assertEqual(["test-writer", "python-coder"], dispatched_b)

        result_a = observation_a.get("result") or {}
        result_b = observation_b.get("result") or {}
        self.assertEqual("blocked", result_a.get("status"))
        self.assertEqual("blocked", result_b.get("status"))
        self.assertEqual(
            result_a.get("message"),
            result_b.get("message"),
            "the ticket's prose changed which refusal the driver reported:\n"
            f"A (names several agents): {result_a.get('message')!r}\n"
            f"B (names nobody):         {result_b.get('message')!r}",
        )
        self.assertEqual(
            result_a.get("blocker_detail"),
            result_b.get("blocker_detail"),
            "the two runs' own phase results should be identical — the body "
            "content is the only thing that differs between A and B",
        )

    def test_deliberate_targetless_halt_does_not_respawn_a_body_named_agent(self):
        # covers: BO-3000a
        # angle: failure
        #
        # The field-evidence shape (BO-3000a.yaml notes): a ticket already
        # carries a `### test-writer` task section from an EARLIER delegation
        # — not one added by THIS phase's own dispatch — and python-coder's
        # contract-shrinkage guard now emits a targetless handoff on purpose,
        # meaning "stop, do not proceed without authorization." The drive must
        # halt, not re-run test-writer because its heading is sitting right there.
        observation, ticket_path = self._drive(
            ["test-writer", "python-coder"],
            {
                "test-writer": {"status": "ok"},
                "python-coder": {"status": "handoff"},
            },
            body_extra="\n## Implementation Tasks\n\n### test-writer\n\n- [ ] one thing\n",
        )
        task_agents = _implementation_task_agents_after_run(observation, ticket_path)
        self.assertEqual(
            ["test-writer"],
            task_agents,
            "the ticket did not end up naming a resolvable body agent — the "
            f"fixture does not exercise the deliberate-halt shape: {task_agents}",
        )
        dispatched = H.phase_dispatch_labels(observation)
        self.assertEqual(
            1,
            dispatched.count("test-writer"),
            "test-writer was re-dispatched from its ### heading despite the "
            f"handoff naming no target: {dispatched}",
        )
        self.assertEqual(["test-writer", "python-coder"], dispatched)
        result = observation.get("result") or {}
        self.assertEqual("blocked", result.get("status"))
        self.assertIn("named no handoff target", result.get("message") or "")

    def test_unobtainable_result_and_targetless_result_refuse_distinguishably(self):
        # covers: BO-3000a
        # angle: boundary
        #
        # Phase A returns a result the driver cannot use AT ALL (an
        # unrecognised status — PHASE_STATUS_VALUES guard, upstream of the
        # handoff branch). Phase B returns a result the driver reads intact,
        # which itself names no handoff target. Both stop the ticket; the two
        # refusals must be told apart in what the run reports.
        observation_unobtainable, _ = self._drive(
            ["test-writer", "python-coder"],
            {
                "test-writer": {"status": "ok"},
                "python-coder": {"status": "not-a-real-phase-status"},
            },
        )
        observation_targetless, _ = self._drive(
            ["test-writer", "python-coder"],
            {
                "test-writer": {"status": "ok"},
                "python-coder": {"status": "handoff"},
            },
        )

        result_unobtainable = observation_unobtainable.get("result") or {}
        result_targetless = observation_targetless.get("result") or {}

        self.assertEqual("blocked", result_unobtainable.get("status"))
        self.assertEqual("blocked", result_targetless.get("status"))

        message_unobtainable = result_unobtainable.get("message") or ""
        message_targetless = result_targetless.get("message") or ""

        self.assertIn("no usable result", message_unobtainable)
        self.assertNotIn("no usable result", message_targetless)

        self.assertIn("named no handoff target", message_targetless)
        self.assertNotIn("named no handoff target", message_unobtainable)

        self.assertNotEqual(
            message_unobtainable,
            message_targetless,
            "an agent that never reported usably and an agent that reported "
            "and named nothing produced the SAME refusal text — a reader "
            "cannot tell a dead agent from a non-conformant one",
        )

        for observation in (observation_unobtainable, observation_targetless):
            dispatched = H.phase_dispatch_labels(observation)
            self.assertEqual(["test-writer", "python-coder"], dispatched)

    def test_handoff_routing_is_reachable_from_the_workflow_top_level_body(self):
        # covers: BO-3000a
        # angle: reachability
        #
        # Proof that the routing above is executed by build-feature.js's own
        # top-level body via the real harness — not by calling an extracted
        # helper function directly. The re-dispatch of test-writer performs a
        # REAL second write to the REAL ticket file (a second '(status: ok)'
        # sign-off entry); that side-effect can only exist if the actual
        # driver script ran the actual agent() dispatch a second time.
        observation, ticket_path = self._drive(
            ["test-writer", "python-coder", "sql-coder"],
            {
                "test-writer": {"status": "ok"},
                "python-coder": {
                    "status": "handoff",
                    "handoff_target": "test-writer",
                },
                "sql-coder": {"status": "ok"},
            },
        )
        self.assertIsNone(
            observation.get("error"),
            f"the driver threw instead of running: {observation.get('error')}",
        )
        dispatched = H.phase_dispatch_labels(observation)
        self.assertEqual(["test-writer", "python-coder", "test-writer"], dispatched)
        records = observation.get("records") or {}
        self.assertEqual(
            2,
            _signoff_count(records, ticket_path, "test-writer"),
            "the re-dispatch did not produce a second real sign-off entry in "
            "the real ticket file, so this did not prove genuine execution "
            f"through the top-level body: {records.get(ticket_path)}",
        )
        result = observation.get("result") or {}
        self.assertEqual("blocked", result.get("status"))
        self.assertEqual("cross_agent", result.get("classification"))
        self.assertEqual("test-writer", result.get("handoff_target"))


if __name__ == "__main__":
    unittest.main()
