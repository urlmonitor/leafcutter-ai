"""
MODULE: test_bo_2300a_1_refusal_not_decision
GOAL: RED-baseline behavioral tests proving BO-2300a-1's own coverage does not
    test what the AC actually requires.

BACKGROUND (KI-ACD-005, docs/known-issues/ac-driven-dev.md; AC notes on
BO-2300a-1, reopened 2026-08-25): `resolveGate()` in
templates/workflows-js/plan-feature.js (line ~1577) treats ANY object carrying
a string `action` field returned from the LIVE gate dispatch as a genuine user
decision — including a well-formed REFUSAL from the `status-checker` agent the
gate is dispatched to. Because no human is ever attached to that dispatch when
running headless/background, a status-checker refusal such as:

    {"action": "cancel", "feedback": "This request is outside status-checker's
     defined scope ... Recommend routing this approval gate to the agent/role
     actually responsible for review ... not status-checker."}

is indistinguishable, in the current implementation, from a real user typing
"cancel". `pauseAtGate()` (line ~1582) — the correct response to "no reachable
human answerer" per this AC's own criteria ("the run does NOT cancel ... and
enters a paused state") — is reached ONLY when the live-gate reply is null or
not an object carrying a string action/choice. A well-formed refusal never
satisfies that condition, so it sails straight through as if approved by the
run's own author, and the pipeline reports success while discarding all
uncommitted work.

The existing covering test (test_paused_state_distinct_from_cancelled in
test_bo_2300_pause_resume.py) never feeds this shape — it only ever supplies
either NO gate response (headless/null, which correctly pauses) or an explicit
plain `{"action": "cancel"}` with no refusal language (modeling a genuine
user's own cancel choice). Neither exercises the actual defect: a REFUSAL,
which is what a real headless run receives from a status-checker dispatch.

TEST STRATEGY: drive the REAL JS engine via run_workflow_under_e2() exactly as
the existing BO-2300 suite does (see test_bo_2300_pause_resume.py). Verified
empirically (2026-08-26, this branch, HEAD) via ad-hoc harness runs before
writing these assertions:
  - Default headless run (no label response) reaches "final-gate" and
    dispatches "pause-persist" — the null-case control (§3), confirmed still
    correct today.
  - Feeding "final-gate" the KI-ACD-005-shaped refusal returns
    {"status": "ok", "message": "Pipeline cancelled at final gate (IT-PO). ...",
     ...} with ZERO "pause-persist" dispatches — the live defect (§1), RED.
  - Feeding "final-gate" a genuine, non-refusal "approve" answer dispatches
    "apply-approval" — the control proving a correct fix must not reject every
    live-gate answer (§2), confirmed still correct today.

TICKET: none (ad-hoc RED-baseline authoring task, worktree
test/red-baseline-falsified-acs). AC: BO-2300a-1 (work_status: todo).
"""

from __future__ import annotations

import sys
from pathlib import Path

# unit_tests/ must be on sys.path so _workflow_engine_harness is importable
# from this sub-package (unit_tests/workflows/), mirroring
# test_bo_2300_pause_resume.py's own sys.path setup.
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import HarnessResult, run_workflow_under_e2  # noqa: E402

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_PLAN_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "plan-feature.js"

_TIMEOUT = 30  # seconds; all agent() calls are synchronous mocks

# The real refusal payload a status-checker agent produces when handed a
# gate-approval role outside its charter. Verbatim in shape and register to
# the evidence quoted in KI-ACD-005 (docs/known-issues/ac-driven-dev.md:296-304,
# captured from run journal wf_1969bd0b-43f) — NOT a synthetic string invented
# for this test. This is a well-formed object: `action` is a real string in
# the gate's own valid-option enum, so resolveGate's current shape check
# ("typeof gateAnswer.action === 'string'") accepts it without reservation.
_STATUS_CHECKER_REFUSAL = {
    "action": "cancel",
    "feedback": (
        "This request is outside status-checker's defined scope (ticket-state "
        "verification and closing per docs/agents/conventions.md). "
        "status-checker has no defined process for reviewing or approving "
        "it-po's enriched acceptance criteria, and no ticket_path or sign-off "
        "context was provided for this dispatch. Recommend routing this "
        "approval gate to the agent/role actually responsible for final "
        "review of the authored ACs — not status-checker."
    ),
}

# A genuine, non-refusal decision — the control case. Nothing in its shape
# distinguishes it structurally from the refusal above (both are objects with
# a string `action` in the gate's valid-option set); the only difference is
# that this one is not refusal-shaped. Any correct fix must keep accepting
# this while rejecting/pausing on the refusal above.
_GENUINE_APPROVE_ANSWER = {"action": "approve", "priority": "high"}


def _pause_calls(result: HarnessResult) -> list:
    """Return all agent() calls whose label is 'pause-persist'."""
    return [c for c in result.agent_calls if c.label == "pause-persist"]


# ---------------------------------------------------------------------------
# 1 — THE DEFECT: a well-formed refusal must not be accepted as a decision.
# ---------------------------------------------------------------------------


def test_ac1_status_checker_refusal_is_not_treated_as_user_decision():
    # covers: BO-2300a-1
    """
    AC-1 (BO-2300a-1): "the run does NOT cancel and does NOT discard the work
    completed so far, And the run enters a paused state ..." when it cannot
    obtain an immediate answer from a human.

    A status-checker refusal at the live gate IS exactly the "cannot obtain an
    immediate answer" case — no human is attached to that dispatch. The run
    must therefore pause (dispatch pause-persist) rather than resolve the
    refusal as if it were the user's own "cancel" choice.

    RED today: resolveGate()'s shape check (plan-feature.js ~1577-1579) treats
    any object with a string `action` as a valid decision, with no refusal
    detection. The refusal above is accepted verbatim, `pauseAtGate()` is
    never reached, and the workflow returns a cancelled-but-"status":"ok"
    result while discarding the run.
    """
    result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses={"final-gate": _STATUS_CHECKER_REFUSAL},
    )
    assert result.error == "", f"Harness error: {result.error}"

    pauses = _pause_calls(result)
    assert len(pauses) > 0, (
        "A status-checker REFUSAL at the live gate must be treated as 'no "
        "reachable human answerer' and pause the run (dispatch pause-persist), "
        "exactly like the headless/null case — never accepted as the user's own "
        "decision. Got ZERO pause-persist dispatches: the refusal was accepted "
        "as a real answer instead. "
        f"Dispatched labels: {[c.label for c in result.agent_calls]}. "
        f"Terminal result: {result.result!r}."
    )

    # Defense in depth: even setting the pause-dispatch question aside, the
    # run must never report a clean "ok" for a decision no human made.
    if result.result is not None and isinstance(result.result, dict):
        assert result.result.get("status") != "ok", (
            "A status-checker refusal must never resolve to a clean "
            f"'status: ok' outcome. Got: {result.result!r}"
        )


# ---------------------------------------------------------------------------
# 2 — CONTROL: a genuine, non-refusal answer must still be honoured.
# ---------------------------------------------------------------------------


def test_ac1_genuine_approve_answer_still_accepted():
    # covers: BO-2300a-1
    """
    Control case for AC-1. Without this test, a fix for the refusal defect
    above could over-correct into rejecting (or always pausing on) EVERY
    live-gate answer — which would silently break the interactive path for
    real users. A genuine, non-refusal "approve" decision must still advance
    the workflow past the gate (apply-approval dispatched), exactly as it does
    today.

    Expected to PASS today (this is deliberately not a red assertion): the
    current implementation already honours a genuine live-gate answer. This
    test exists so a fix for test_ac1_status_checker_refusal_is_not_treated_as_user_decision
    cannot regress this path — any refusal-detection mechanism must key off
    something that distinguishes a refusal from a genuine answer, not merely
    "does the live gate ever answer at all". Verified empirically
    (2026-08-26, this branch, HEAD) via an ad-hoc harness run before writing
    this assertion.
    """
    result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses={"final-gate": _GENUINE_APPROVE_ANSWER},
    )
    assert result.error == "", f"Harness error: {result.error}"

    labels = [c.label for c in result.agent_calls]
    assert "apply-approval" in labels, (
        "A genuine, non-refusal approve answer at the live gate must still "
        f"advance the workflow to apply-approval. Got labels: {labels}"
    )

    # And it must NOT have been diverted into a pause (that would mean the
    # fix over-corrected into distrusting every live-gate answer).
    pauses = _pause_calls(result)
    assert len(pauses) == 0, (
        "A genuine approve answer must not be paused — only a refusal-shaped "
        f"reply should pause. Got {len(pauses)} pause-persist dispatch(es)."
    )


# ---------------------------------------------------------------------------
# 3 — Null-case control: already correct today (explicitly documented, not a
#     broken test — see the module docstring's TEST STRATEGY section).
# ---------------------------------------------------------------------------


def test_ac1_headless_null_reply_already_pauses():
    # covers: BO-2300a-1
    """
    Control case for AC-1's "no reachable human answerer" clause, restricted
    to the NULL/unparseable-reply shape (as opposed to the well-formed-refusal
    shape covered above). When the live gate dispatch returns no gate
    response at all (the harness default stub, which carries no `action` or
    `choice` field), resolveGate already correctly falls through to
    pauseAtGate() (plan-feature.js line ~1582) rather than treating the
    unparseable reply as a decision.

    EXPECTED TO PASS TODAY — this is deliberate, not an oversight. Per this
    task's own instructions: "cover the null case, which should already
    pass ... a test that passes here is evidence about the mitigation
    [committed for the null-reply path], not a broken test." Its purpose is
    to pin down that the EXISTING null-path behavior is not accidentally
    broken by a future fix to the refusal-shaped case above — a correct fix
    must add refusal detection WITHOUT touching this already-working branch.

    This deliberately does NOT assert on the exact terminal `status` string
    (e.g. "paused_awaiting_input" vs "pause_persist_failed") — that
    distinction belongs to a different, unrelated persist-verification
    concern (pauseAtGate's own write/read-back check) and is out of scope for
    this AC. The only property AC-1 requires here is: the run must not have
    resolved the null/unparseable reply as a cancel decision, which the
    presence of a pause-persist dispatch proves.
    """
    result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses={},  # no gate response at all — headless/null path
    )
    assert result.error == "", f"Harness error: {result.error}"

    pauses = _pause_calls(result)
    assert len(pauses) > 0, (
        "A headless run whose live gate returns no usable reply must pause "
        "(dispatch pause-persist), not resolve as a decision. "
        f"Dispatched labels: {[c.label for c in result.agent_calls]}"
    )
