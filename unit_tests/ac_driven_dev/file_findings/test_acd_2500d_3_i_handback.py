"""
MODULE: unit_tests/ac_driven_dev/file_findings/test_acd_2500d_3_i_handback.py
COVERS: ACD-2500d-3-i
GOAL: Red-first specification of the workflow hand-back (ticket 39): before the final approval gate is
    shown, /plan-feature hands every requirement held with "file finding undecided" back to the
    technical planner (it-po, label `it-po-findings-round-N`), at most 2 rounds, re-running the rule
    check and the hold report after each round; whatever is still undecided after round 2 is shown at
    the gate as held, never approved. Records held for another reason are never handed back.
BUSINESS CONTEXT: G4 architect note, section 2.5. The workflow has no file access: which requirements
    are undecided comes from the hold report (approval_hold_report.py through the shell agent), which
    reads the records on disk; the planner's returned text is never the evidence.
ARCHITECTURE: See _handback_support.py (real plan-feature.js under the E2 harness, "technical" route).
    R = undecided finding, S = decided (approvable), T = held "test design pending".

DEPENDENCY ON TICKET 31 (flagged): the hand-back sits inside the `test-design` pipeline stage that
    ticket 31 adds. Until it lands the run ends at the old itpo final gate, so every test here fails on
    its first assertion, "the test-design stage ran" (absence of the stage, NOT of the hand-back).
    Once 31 is in, the same tests fail only on the hand-back itself. Each test asserts the stage
    precondition first and says so in its message.

RED STATE (today): no `stage-test-design-author` / `approval-holds` dispatch exists, and no
    `it-po-findings-round-*` dispatch exists.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _handback_support import (  # noqa: E402
    IDS, PENDING, R, S, T, UNDECIDED, by_round, calls, gate_context, holds_reply, labels, names, planner_reply,
    position, prepass_reply, run,
)

_MISSING_STAGE = "precondition: ticket 31's test-design stage did not run (no designer dispatch)"


@pytest.fixture
def prepass(tmp_path):
    return prepass_reply(tmp_path)


def _stage_ran(result) -> None:
    assert calls(result, "stage-test-design-author"), f"{_MISSING_STAGE}; dispatched: {names(result)}"


def _holds(*, undecided: bool) -> dict:
    """T is always held for its design; R is held for its finding only while `undecided`."""
    held = {T: PENDING}
    if undecided:
        held[R] = UNDECIDED
    return holds_reply(held)


def test_workflow_hands_undecided_finding_to_planner(prepass, monkeypatch):
    # covers: ACD-2500d-3-i
    # angle: reachability
    """R's undecided finding is handed to the technical planner's next pass before the final gate.

    Entry point: the plan-feature.js workflow dispatch (harness). The hold report says R is undecided
    until the planner has run once, then clean. Exact: one `it-po-findings-round-1`, no round 2; the
    prompt names R and neither S (decided) nor T (held for its design); the dispatch comes after the
    design step's rule check and before the gate; the check is re-run once after the round, as the
    hand-back stage (`rule-check-itpo-handback`, ACD-2500a-2-ix), and the hold report is re-read after the planner; the gate then holds only T and offers R and S.
    """
    by_round(monkeypatch)
    result = run(labels(prepass, {"__by_round__": [_holds(undecided=True), _holds(undecided=False)]}))
    _stage_ran(result)

    rounds = calls(result, "it-po-findings-round-1")
    assert len(rounds) == 1, f"expected exactly one hand-back round; dispatched: {names(result)}"
    assert not calls(result, "it-po-findings-round-2"), names(result)
    prompt = rounds[0].prompt
    assert R in prompt and S not in prompt and T not in prompt, prompt[:600]
    assert position(result, "rule-check-test-design") < position(result, "it-po-findings-round-1") < position(result, "pause-persist")
    assert len(calls(result, "rule-check-test-design")) == 1, names(result)
    assert len(calls(result, "rule-check-itpo-handback")) == 1, names(result)
    assert position(result, "rule-check-itpo-handback") > position(result, "it-po-findings-round-1")
    assert position(result, "approval-holds", 1) > position(result, "it-po-findings-round-1")

    context = gate_context(result)
    assert [h["id"] for h in context["held"]] == [T], context
    assert sorted(context["approvable"]) == sorted([R, S]), context


def test_handback_prompt_asks_for_a_decision_per_finding_and_nothing_else(prepass, monkeypatch):
    # covers: ACD-2500d-3-i
    # angle: criterion
    """The planner is told to record a decision per undecided finding and to touch nothing else.

    The prompt carries the three choices (`reassign`, `split`, `assignment stands`), the one-sentence
    reason, `by: it-po`, the instruction to return `acs_written`, and "touch nothing else". The dispatch
    is made to the `it-po` agent (agentType), not to the designer or the status checker.
    """
    by_round(monkeypatch)
    result = run(labels(prepass, {"__by_round__": [_holds(undecided=True), _holds(undecided=False)]}))
    _stage_ran(result)

    call = calls(result, "it-po-findings-round-1")[0]
    assert call.agent_type == "it-po", call.agent_type
    for needle in ("reassign", "split", "assignment stands", "one-sentence", "by: it-po", "acs_written", "touch nothing else"):
        assert needle in call.prompt, (needle, call.prompt[:800])


def test_handback_stops_after_two_rounds_and_shows_the_record_held(prepass, monkeypatch):
    # covers: ACD-2500d-3-i
    # angle: boundary
    """If R is still undecided after round 2, the gate shows R as held; there is no round 3.

    The planner never records a decision (the hold report keeps saying so). Exact: rounds 1 and 2 are
    dispatched once each, round 3 never; the check runs 3 times (the design step's, then one itpo-handback
    check per round, ACD-2500a-2-ix); the
    gate context lists R held with the reason, and R is NOT approvable (never silently approved).
    """
    by_round(monkeypatch)
    result = run(labels(prepass, {"__by_round__": [_holds(undecided=True)]}))
    _stage_ran(result)

    assert [len(calls(result, f"it-po-findings-round-{n}")) for n in (1, 2, 3)] == [1, 1, 0], names(result)
    assert len(calls(result, "rule-check-test-design")) == 1, names(result)
    assert len(calls(result, "rule-check-itpo-handback")) == 2, names(result)
    assert position(result, "it-po-findings-round-2") < position(result, "pause-persist")
    context = gate_context(result)
    held = {h["id"]: h["reason"] for h in context["held"]}
    assert held == {R: UNDECIDED, T: PENDING}, context
    assert R not in context["approvable"] and sorted(context["approvable"]) == [S], context


def test_handback_never_fires_for_a_record_held_for_another_reason(prepass, monkeypatch):
    # covers: ACD-2500d-3-i
    # angle: failure
    """With no "file finding undecided" hold (only T, held for its design) the planner is not dispatched.

    Control run first (so the test cannot pass because no hand-back exists at all): R undecided gives
    exactly one planner dispatch. Then the run under test: only T is held, for its design. Wrong version
    caught: the hand-back fires for any held record, or whenever the stage ran. Exact counts: 1 then 0
    planner dispatches; the designer ran once and the gate was reached with T held and R, S approvable.
    """
    by_round(monkeypatch)
    control = run(labels(prepass, {"__by_round__": [_holds(undecided=True), _holds(undecided=False)]}))
    _stage_ran(control)
    assert len(calls(control, "it-po-findings-round-1")) == 1, names(control)

    result = run(labels(prepass, _holds(undecided=False)))
    _stage_ran(result)

    handbacks = [n for n in names(result) if n.startswith("it-po-findings-round-")]
    assert handbacks == [], handbacks
    assert len(calls(result, "stage-test-design-author")) == 1
    assert len(calls(result, "rule-check-test-design")) == 1
    context = gate_context(result)
    assert [h["id"] for h in context["held"]] == [T] and sorted(context["approvable"]) == sorted([R, S]), context


def test_records_returned_by_the_planner_join_the_run(prepass, monkeypatch):
    # covers: ACD-2500d-3-i
    # angle: seam
    """A requirement the planner creates while deciding (a `split`) is checked and held-checked too.

    Producer: the `it-po-findings-round-1` reply lists `acs_written: [R, FFH-1b]`. Consumer: the hold
    report dispatched after the round must be asked about the new id (it is added to the ids of the run),
    so a split record with intent and no design reads "test design pending" instead of being skipped.
    """
    new_id = "FFH-1b"
    by_round(monkeypatch)
    table = labels(
        prepass, {"__by_round__": [_holds(undecided=True), _holds(undecided=False)]},
        **{"it-po-findings-round-1": planner_reply(R, new_id)},
    )
    result = run(table)
    _stage_ran(result)

    after = [c for c in calls(result, "approval-holds") if c.call_index > calls(result, "it-po-findings-round-1")[0].call_index]
    assert after, names(result)
    assert all(new_id in c.prompt for c in after), [c.prompt[:300] for c in after]
    assert all(rid in after[0].prompt for rid in IDS)
