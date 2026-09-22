"""
MODULE: test_acd_2100c_4
GOAL: Behavioral, RED-baseline tests for ACD-2100c-4 -- "An answer that did
    not come from the person is refused even when it is well formed."

BACKGROUND: ACD-2100c-1 closed the "an agent can answer a gate directly"
    loophole by removing resolveGate()'s live-dispatch attempt entirely: the
    ONLY channel that can resolve any of the five decision points today is
    `args.resume_answer`. Its own pr-reviewer sign-off (13_TICKET-20260826-
    ACD-2100c-1.md, 2026-09-08 09:30) noted this closes the python-coder
    "Delivers To" contract ("an answer carries the channel it arrived on")
    "trivially by design (only one channel ... can now resolve any gate, so
    there is no provenance ambiguity left to encode)" -- but this ticket's
    own architect-review (2026-09-09 19:07) found that claim does not survive
    contact with the actual defect this AC targets: nothing on disk
    distinguishes a `resume_answer` object the real person's CLI reply
    produced from one any other caller (an automated agent, a stale replay,
    a test) could construct with the exact same shape and hand to the SAME
    `args.resume_answer` channel. `args.resume_answer` narrowed WHERE an
    answer can arrive from five call sites to one; it never established WHO
    put it there. A well-formed, validly-shaped, enum-valid answer naming a
    real choice -- exactly the shape `validateAnswerShape()` already accepts
    today -- can still be handed to the workflow by something that is not
    the person running the route, and today's `resolveGate()` cannot tell
    the difference: it applies the answer regardless.

DESIGN DECISION (this ticket's test contract; no test_spec was authored, so
    per the Implementation Notes the discriminator must be provenance, never
    content): `args.resume_answer` must carry a `channel` field, and
    `resolveGate()` must accept the answer ONLY when `channel === "person"`.
    Any other value, or the field's absence, must be treated exactly like an
    unanswered gate -- the run stays at `status: "paused_awaiting_input"` for
    the SAME `gate_id` -- except the terminal payload must ALSO carry a
    `reason` string that names provenance ("did not come from the person")
    and must NOT read as a shape/parse failure ("could not understand",
    "unparseable", "malformed"), per the AC's own Then-clause: "the reason it
    records is that the answer did not come from the person -- not that the
    answer could not be understood." This is a test-authoring decision, not
    an implementation one: python-coder is free to choose a different field
    name only if it also updates these tests (Source-of-Truth Discipline
    Rule 5 -- the test is the contract until intentionally renegotiated).

    `channel` is deliberately the ONLY thing that differs between the
    accepted and refused fixtures in every test below (see the
    Implementation Notes: "If accepting an answer requires it to carry
    anything the refused answer could not also carry, the pair is not a
    controlled comparison"). Content (`action`, `priority`) is byte-identical
    in both halves of every comparison.

WHY final-gate: mirrors `unit_tests/workflows/test_acd_2100c_1.py`'s own
    `final_gate` SCENARIOS entry -- the ONE decision point reachable with
    completely empty `label_responses` (no stage-0-triage / pt-classify
    overrides needed), and its accept path dispatches a single, unambiguous
    "apply-approval" advance marker (verified in that file's own red_baseline
    and again directly against this branch's HEAD while authoring these
    tests). Every test below drives `args.resume_answer.gate_id ==
    "final-gate"` directly, with `label_responses={"read-pause-record":
    {"exists": True, "stale": False}}` -- the exact fail-closed mock pattern
    `unit_tests/workflows/test_bo_2300_pause_resume.py`'s own
    `test_ac2_pt_gate_cancel_status_is_distinct_from_ok`-style tests already
    use to drive a resume decision in a SINGLE `run_workflow_under_e2()` call
    (no separate headless "discover the pause" call is required first).

TEST STRATEGY / REACHABILITY (BP-1100g-2 Step 1): this ticket's own change is
    confined to `templates/workflows-js/plan-feature.js`'s single, internal
    `resolveGate()` mechanism -- a Node/E2 workflow script, not a Python
    module. It has no CLI wrapper of its own, is not a registered
    pre-commit hook, and exposes no `main(argv)`. It IS invoked by the real
    `/plan-feature` slash command (`templates/commands/plan-feature.md`:
    ``Workflow("plan-feature", { userInput: $ARGUMENTS })``), which is a
    Claude-Code-only primitive with no Python-invocable surface -- exactly
    the situation `unit_tests/workflows/test_acd_2100c_1.py`'s own red-
    baseline sign-off (2026-09-07 15:10) already resolved, for this SAME
    file, the SAME way: `run_workflow_under_e2()` drives the real, on-disk
    `plan-feature.js` through a real Node subprocess built to the ADR-030
    injected-globals contract (`agent`, `args`, etc.) -- the closest
    behavioral stand-in this repo has for the Workflow-tool dispatch surface
    `/plan-feature` itself uses, and the one every sibling test in this
    directory already treats as this script's reachability entry point.
    `completion_manifest.reachability_entry_point_answer` in this ticket's
    sign-off records this resolution verbatim.

TICKET: 17_TICKET-20260826-ACD-2100c-4.md
AC: ACD-2100c-4
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# unit_tests/ must be on sys.path so _workflow_engine_harness is importable
# from this sub-package (unit_tests/workflows/), mirroring every other file
# in this directory.
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_PLAN_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "plan-feature.js"

_TIMEOUT = 30  # seconds; all agent() calls are synchronous mocks.

# Fail-closed mock: `resolveGate()`'s resume-check dispatches a
# "read-pause-record" agent() call and requires exists=True/stale=False
# before it will even consider applying a resume_answer -- same pattern
# `test_bo_2300_pause_resume.py` and `test_bo_2300a_2_cancel_status_distinct
# .py` already use to drive a resume decision in ONE `run_workflow_under_e2`
# call, without a separate prior headless "discover the pause" run.
_READ_PAUSE_RECORD_OK = {"read-pause-record": {"exists": True, "stale": False}}

_GATE_ID = "final-gate"

# Content is BYTE-IDENTICAL across the accepted/refused pair in every test
# below -- only `channel` differs. `priority` is required because final-gate's
# descriptor declares `type: "priority_choice"`
# (validateAnswerShape's priority_choice branch requires `answer.priority !=
# null`); `action` mirrors every other final-gate fixture in this directory
# (test_acd_2100c_1.py's SCENARIOS, test_bo_2300_pause_resume.py).
_BASE_ANSWER_CONTENT = {"gate_id": _GATE_ID, "action": "approve", "priority": "high"}


def _answer_with_channel(channel):
    """A final-gate resume_answer identical to `_BASE_ANSWER_CONTENT` except
    for its `channel` value. `channel=None` omits the key entirely (the
    "absent" variant of "did not come from the person").
    """
    answer = dict(_BASE_ANSWER_CONTENT)
    if channel is not None:
        answer["channel"] = channel
    return answer


# The one dispatch that only ever fires once the final-gate decision has
# actually been APPLIED (see plan-feature.js's "approve" branch) -- the
# observable "the run moved past the decision point" marker used throughout
# this directory (test_acd_2100c_1.py's `advance_markers`).
_ADVANCE_MARKER = "apply-approval"


class TestWellFormedAnswerNotFromThePersonIsRefused(unittest.TestCase):

    def test_well_formed_answer_not_from_the_person_is_refused(self):
        # covers: ACD-2100c-4
        # angle: criterion
        """AC: "an answer that is well formed and names one of the choices
        the decision offers but that did not originate from the person ...
        is not treated as the person's decision and the choice it names is
        not carried out."

        `refused_answer` is shape-valid (passes validateAnswerShape: has a
        string `action` in the gate's declared options, and a non-null
        `priority` for this priority_choice gate) and names a real choice
        ("approve") -- it fails ONLY on provenance (`channel` is absent).

        RED today: resolveGate() has no provenance check at all, so this
        well-formed answer is applied exactly like a genuine one -- the run
        advances past final-gate and "apply-approval" is dispatched.
        """
        refused_answer = _answer_with_channel(None)  # no channel at all

        result = run_workflow_under_e2(
            _PLAN_FEATURE_JS,
            timeout=_TIMEOUT,
            label_responses=dict(_READ_PAUSE_RECORD_OK),
            args={"run_id": "acd2100c4-refused-no-channel", "resume_answer": refused_answer},
        )
        self.assertEqual(result.error, "", f"Harness error: {result.error}")

        labels = [c.label for c in result.agent_calls]
        self.assertNotIn(
            _ADVANCE_MARKER,
            labels,
            f"A well-formed answer naming 'approve' for '{_GATE_ID}' was carried "
            f"out (dispatched '{_ADVANCE_MARKER}') even though it carried no "
            f"'channel' marking it as having come from the person running the "
            f"route. Provenance, not shape, must gate whether an answer is "
            f"acted on. Dispatched labels: {labels}",
        )

        terminal = result.result
        self.assertIsInstance(
            terminal,
            dict,
            f"Refusing an unattributable answer must still leave a structured "
            f"terminal payload naming the decision point it is still awaiting "
            f"an answer for -- got {terminal!r}.",
        )
        self.assertEqual(
            terminal.get("status"),
            "paused_awaiting_input",
            f"An answer that did not come from the person must not be treated "
            f"as the person's decision -- the run must stay at the decision "
            f"point exactly as if no answer had arrived. terminal={terminal!r}",
        )
        self.assertEqual(
            terminal.get("gate_id"),
            _GATE_ID,
            f"Terminal payload does not name the decision point the run is "
            f"still waiting on. terminal={terminal!r}",
        )


class TestIdenticalAnswersDifferingOnlyInOriginProduceOppositeOutcomes(unittest.TestCase):

    def test_identical_answers_differing_only_in_origin_produce_opposite_outcomes(self):
        # covers: ACD-2100c-4
        # angle: seam
        """AC: "an answer identical in every respect except that it did come
        from the person is accepted and carried out."

        This is the controlled comparison the Implementation Notes require:
        `accepted_answer` and `refused_answer` share IDENTICAL content
        (`gate_id`, `action`, `priority`) -- the only difference is
        `channel`. Feeds each one, via the REAL `args.resume_answer` seam,
        into the REAL `resolveGate()`/`pauseAtGate()` machinery running
        inside the real, on-disk `plan-feature.js`, and asserts the
        consumer's two observable outcomes are opposite: one dispatches the
        real "apply-approval" advance marker, the other does not.

        RED today: resolveGate() applies BOTH answers identically (no
        `channel` field is read anywhere), so `refused_answer` ALSO
        dispatches "apply-approval" -- the two halves of this comparison are
        not actually distinguishable yet, which is exactly the defect this
        AC exists to fix.
        """
        accepted_answer = _answer_with_channel("person")
        refused_answer = _answer_with_channel("agent")

        # Sanity-check the fixture pair really is a controlled comparison:
        # identical except for `channel`.
        accepted_minus_channel = {k: v for k, v in accepted_answer.items() if k != "channel"}
        refused_minus_channel = {k: v for k, v in refused_answer.items() if k != "channel"}
        self.assertEqual(
            accepted_minus_channel,
            refused_minus_channel,
            "Test fixture bug: the accepted/refused answer pair must be "
            "byte-identical except for 'channel', or this is not a "
            "controlled comparison of origin alone.",
        )
        self.assertNotEqual(accepted_answer.get("channel"), refused_answer.get("channel"))

        accepted_result = run_workflow_under_e2(
            _PLAN_FEATURE_JS,
            timeout=_TIMEOUT,
            label_responses=dict(_READ_PAUSE_RECORD_OK),
            args={"run_id": "acd2100c4-accepted-person", "resume_answer": accepted_answer},
        )
        self.assertEqual(accepted_result.error, "", f"Harness error (accepted): {accepted_result.error}")
        accepted_labels = [c.label for c in accepted_result.agent_calls]
        self.assertIn(
            _ADVANCE_MARKER,
            accepted_labels,
            f"An answer whose channel IS 'person' must be carried out. "
            f"Dispatched labels: {accepted_labels}",
        )

        refused_result = run_workflow_under_e2(
            _PLAN_FEATURE_JS,
            timeout=_TIMEOUT,
            label_responses=dict(_READ_PAUSE_RECORD_OK),
            args={"run_id": "acd2100c4-refused-agent", "resume_answer": refused_answer},
        )
        self.assertEqual(refused_result.error, "", f"Harness error (refused): {refused_result.error}")
        refused_labels = [c.label for c in refused_result.agent_calls]
        self.assertNotIn(
            _ADVANCE_MARKER,
            refused_labels,
            f"An answer identical in content but whose channel is NOT "
            f"'person' must not be carried out -- content alone must never "
            f"be the discriminator. Dispatched labels: {refused_labels}",
        )


class TestRefusalRecordsProvenanceAsTheReasonNotUnparseable(unittest.TestCase):

    def test_refusal_records_provenance_as_the_reason_not_unparseable(self):
        # covers: ACD-2100c-4
        # angle: criterion
        """AC: "the reason it records is that the answer did not come from
        the person -- not that the answer could not be understood."

        The refused answer here is fully well-formed (same content as the
        accepted half of the seam test) -- so a correct implementation
        cannot legitimately record a shape/parse failure as the reason; only
        a provenance-worded reason is honest about what actually happened.

        RED today: resolveGate()/pauseAtGate() never build a `reason` field
        at all for this path (today it does not even refuse -- it applies
        the well-formed answer), so no such string exists to inspect.
        """
        refused_answer = _answer_with_channel("agent")

        result = run_workflow_under_e2(
            _PLAN_FEATURE_JS,
            timeout=_TIMEOUT,
            label_responses=dict(_READ_PAUSE_RECORD_OK),
            args={"run_id": "acd2100c4-reason-check", "resume_answer": refused_answer},
        )
        self.assertEqual(result.error, "", f"Harness error: {result.error}")

        terminal = result.result
        self.assertIsInstance(terminal, dict, f"terminal={terminal!r}")
        self.assertEqual(
            terminal.get("status"),
            "paused_awaiting_input",
            f"terminal={terminal!r}",
        )

        reason = terminal.get("reason")
        self.assertIsInstance(
            reason,
            str,
            f"Refusing a well-formed-but-unattributable answer must record a "
            f"'reason' string in the terminal payload naming WHY it was "
            f"refused. terminal={terminal!r}",
        )
        self.assertTrue(reason.strip(), "reason must be non-empty.")

        reason_lower = reason.lower()
        self.assertIn(
            "did not come from the person",
            reason_lower,
            f"The recorded reason must name provenance explicitly -- "
            f"'{reason}' does not say the answer did not come from the "
            f"person.",
        )

        forbidden_phrases = (
            "could not understand",
            "could not be understood",
            "unparseable",
            "malformed",
            "invalid shape",
            "wrong shape",
        )
        for phrase in forbidden_phrases:
            self.assertNotIn(
                phrase,
                reason_lower,
                f"The recorded reason must NOT read as a shape/parse "
                f"failure -- this answer was perfectly well formed. Found "
                f"forbidden phrase {phrase!r} in reason={reason!r}. This is "
                f"exactly the KI-ACD-005-adjacent defect ('the journal "
                f"showed a clean decision') this AC exists to prevent.",
            )


class TestRefusedAnswerLeavesTheRunWaitingWithItsRecordOnDisk(unittest.TestCase):

    def test_refused_answer_leaves_the_run_waiting_with_its_record_on_disk(self):
        # covers: ACD-2100c-4
        # angle: failure
        """AC: "the run stays at the decision point and stays waiting with
        its record on disk" -- and, from the sibling Test Requirements
        entry: "the drafted work is byte-identical."

        Feeds a known-bad-provenance (but well-formed) answer through the
        same real entry point and asserts the refusal degrades fail-closed:
        - the run is still at '{gate_id}', still 'paused_awaiting_input'
          (not 'failed', not any terminal success/cancel status);
        - the pause record is never cleared (resolveGate()'s own
          'clear-pause-record' dispatch, gated on `decision.action !==
          "edit"` today, must not fire for a refused answer -- clearing it
          would mean the record NO LONGER reflects that a real decision is
          still owed);
        - no downstream, drafted-work-mutating step (the 'apply-approval'
          advance marker, which writes readiness/priority to AC files and
          commits them) ever runs -- the strongest observable proxy this
          sandboxed harness has for "the drafted work is byte-identical"
          (nothing capable of touching it executed at all).

        RED today: none of this machinery exists -- the well-formed refused
        answer is simply applied, 'apply-approval' fires, and (per
        resolveGate()'s existing, unconditional `if (decision.action !==
        "edit")` clear) 'clear-pause-record' also fires, both of which this
        AC forbids for an answer that did not come from the person.
        """
        refused_answer = _answer_with_channel("agent")

        result = run_workflow_under_e2(
            _PLAN_FEATURE_JS,
            timeout=_TIMEOUT,
            label_responses=dict(_READ_PAUSE_RECORD_OK),
            args={"run_id": "acd2100c4-disk-record-intact", "resume_answer": refused_answer},
        )
        self.assertEqual(result.error, "", f"Harness error: {result.error}")

        terminal = result.result
        self.assertIsInstance(terminal, dict, f"terminal={terminal!r}")
        self.assertEqual(
            terminal.get("gate_id"),
            _GATE_ID,
            f"The run must still be at '{_GATE_ID}' after a refused answer. "
            f"terminal={terminal!r}",
        )
        self.assertEqual(
            terminal.get("status"),
            "paused_awaiting_input",
            f"A refused answer must leave the run WAITING, never failed and "
            f"never resolved as a decision. terminal={terminal!r}",
        )

        labels = [c.label for c in result.agent_calls]
        self.assertNotIn(
            "clear-pause-record",
            labels,
            f"The pause record must remain on disk after a refusal -- the "
            f"person is still owed the question. resolveGate() must not "
            f"dispatch its 'clear-pause-record' command for an answer that "
            f"did not come from the person. Dispatched labels: {labels}",
        )
        self.assertNotIn(
            _ADVANCE_MARKER,
            labels,
            f"No step capable of mutating the drafted work (writing "
            f"readiness/priority and committing) may run for a refused "
            f"answer. Dispatched labels: {labels}",
        )


class TestAcd2100c4ReachableFromEntryPoint(unittest.TestCase):

    def test_acd_2100c_4_reachable_from_entry_point(self):
        # covers: ACD-2100c-4
        # angle: reachability
        """Invokes the REAL, on-disk `plan-feature.js` through
        `run_workflow_under_e2()` -- the real Node-subprocess workflow-runner
        entry point this repository's own test suite already treats as this
        script's reachability surface (see this module's docstring
        "TEST STRATEGY / REACHABILITY" section, and
        `unit_tests/workflows/test_acd_2100c_1.py`'s identical resolution for
        this same file). This is NOT an import-and-call-the-function test:
        no Python code in this repo imports `resolveGate` directly (it is JS,
        never transpiled), so the ONLY way to exercise it at all is through
        this real subprocess dispatch of the real script.

        Distinct from the criterion/seam tests above in what it asserts on:
        this test additionally proves the refusal's effect is CONSUMED in
        control flow, not merely computed and discarded -- an accepted
        (channel=person) answer's decision is consumed all the way through
        to a real downstream dispatch ('apply-approval'), while a refused
        (channel=agent) answer's rejection is consumed by the SAME run
        never making that dispatch and instead returning control to the
        (real) caller with 'paused_awaiting_input' -- the terminal payload
        `/plan-feature`'s own real caller (the skill, running in the human's
        session) actually reads to decide what to show the user next.

        RED today: identical to the seam test above -- resolveGate() has no
        provenance branch, so the refused answer's rejection is never
        computed at all, let alone consumed; both answers are carried out.
        """
        accepted_answer = _answer_with_channel("person")
        refused_answer = _answer_with_channel("agent")

        accepted_result = run_workflow_under_e2(
            _PLAN_FEATURE_JS,
            timeout=_TIMEOUT,
            label_responses=dict(_READ_PAUSE_RECORD_OK),
            args={"run_id": "acd2100c4-reach-accepted", "resume_answer": accepted_answer},
        )
        self.assertEqual(accepted_result.error, "", f"Harness error (accepted): {accepted_result.error}")
        accepted_terminal = accepted_result.result
        self.assertIsInstance(accepted_terminal, dict, f"terminal={accepted_terminal!r}")
        # Consumed-in-control-flow proof (accepted): the real downstream step
        # actually ran, AND the run's own terminal payload no longer reports
        # the gate as pending -- both facts are read from the RUN'S OWN
        # observable output, never asserted by inspecting resolveGate() in
        # isolation.
        self.assertIn(
            _ADVANCE_MARKER,
            [c.label for c in accepted_result.agent_calls],
            "An accepted (channel=person) decision must be consumed all the "
            "way to the real downstream dispatch, not merely computed.",
        )
        self.assertNotEqual(
            accepted_terminal.get("status"),
            "paused_awaiting_input",
            f"An accepted decision must actually move the run's own "
            f"reported state past the gate. terminal={accepted_terminal!r}",
        )

        refused_result = run_workflow_under_e2(
            _PLAN_FEATURE_JS,
            timeout=_TIMEOUT,
            label_responses=dict(_READ_PAUSE_RECORD_OK),
            args={"run_id": "acd2100c4-reach-refused", "resume_answer": refused_answer},
        )
        self.assertEqual(refused_result.error, "", f"Harness error (refused): {refused_result.error}")
        refused_terminal = refused_result.result
        self.assertIsInstance(refused_terminal, dict, f"terminal={refused_terminal!r}")
        # Consumed-in-control-flow proof (refused): the real downstream step
        # never ran, AND the run's own terminal payload still reports the
        # gate as pending, read back from the SAME real subprocess run.
        self.assertNotIn(
            _ADVANCE_MARKER,
            [c.label for c in refused_result.agent_calls],
            "A refused (channel!=person) decision's rejection must be "
            "consumed by suppressing the real downstream dispatch.",
        )
        self.assertEqual(
            refused_terminal.get("status"),
            "paused_awaiting_input",
            f"A refused decision's rejection must be consumed by leaving "
            f"the run's own reported state at the decision point. "
            f"terminal={refused_terminal!r}",
        )


class TestSkillDocumentsChannelPersonObligation(unittest.TestCase):
    """Documentation-presence guard, NOT a behavioural test.

    This test does not exercise resolveGate() or any production code path at
    all -- it only greps templates/skills/plan-feature/SKILL.md for the
    resume-contract prose. Its sole job is to stop the PRODUCER side of this
    AC's contract (the skill instructing the person's own CLI reply to carry
    `channel: "person"` on `args.resume_answer`) from being silently deleted
    while resolveGate()'s CONSUMER-side gate (this file's other four tests)
    stays in place and green. A green resolveGate() with no producer telling
    anyone to set `channel` would be a contract that only ever refuses --
    nothing upstream would ever legitimately satisfy it.

    Per this ticket's own task instructions: this test may be RED until the
    concurrent agent adding the producer-side skill documentation lands its
    change -- that is expected and must not be weakened into passing by
    loosening the assertion below.
    """

    def test_skill_documents_channel_person_resume_obligation(self):
        # covers: ACD-2100c-4
        # angle: reachability
        """Doc-contract presence check (not behavioural): asserts
        templates/skills/plan-feature/SKILL.md names both `resume_answer` and
        the `channel`/`person` provenance obligation this AC's consumer-side
        gate (resolveGate()) depends on a real producer actually setting.
        """
        skill_path = (
            _WORKTREE_ROOT / "templates" / "skills" / "plan-feature" / "SKILL.md"
        )
        self.assertTrue(
            skill_path.is_file(),
            f"Expected the plan-feature skill doc at {skill_path}, but it is "
            f"missing entirely -- there is no producer-side documentation of "
            f"the resume_answer contract at all.",
        )

        content = skill_path.read_text(encoding="utf-8")

        self.assertIn(
            "resume_answer",
            content,
            "templates/skills/plan-feature/SKILL.md must document the "
            "resume_answer contract -- this is the ONLY channel that can "
            "resolve a decision point (ACD-2100c-1), so a skill silent on it "
            "cannot tell the person how to answer a paused run at all.",
        )
        self.assertIn(
            "channel",
            content,
            "templates/skills/plan-feature/SKILL.md must document the "
            "'channel' field on resume_answer -- the provenance marker "
            "resolveGate() (ACD-2100c-4) requires before it will ever honour "
            "an answer. Without this in the skill, no real producer sets it, "
            "and resolveGate()'s consumer-side gate refuses every real "
            "person's reply too.",
        )
        self.assertIn(
            "person",
            content,
            "templates/skills/plan-feature/SKILL.md must name 'person' as "
            "the required channel value -- the only value resolveGate() "
            "treats as the person's own decision (ACD-2100c-4).",
        )
        self.assertIn(
            '"person"',
            content,
            "templates/skills/plan-feature/SKILL.md must show the LITERAL "
            "channel value the person's own CLI reply must carry "
            "(`channel: \"person\"`) -- naming 'person' in prose alone, "
            "without the literal value a real producer would emit, is not "
            "enough to prove a real producer sets exactly the string "
            "resolveGate() checks for.",
        )


if __name__ == "__main__":
    unittest.main()
