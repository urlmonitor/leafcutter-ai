"""
MODULE: unit_tests/ac_driven_dev/test_design_stage/test_acd_300c_3.py
COVERS: ACD-300c-3
GOAL: Red-first specification of the final gate that now follows the test-design stage: it shows every
    batch record with its enriched fields and test design, asks for one batch priority, and offers
    approve (applied by the approval step of ACD-300c-4 to the released ids only), edit (the test-design
    stage re-runs with the user's feedback) and defer (nothing written); approve reports the counts.
ARCHITECTURE: The REAL plan-feature.js under run_workflow_under_e2 on the technical route with 4 ids
    (_approval_step_support.py). The gate payload is the pause record persisted at final-gate (the
    headless gate never calls its live closure). Approval-step replies are the REAL approve_acs.py output
    on a tmp store (ACD-9990a-3 held), routed by command; the old hold report's reply holds nothing.
RED STATE: the persisted question names neither the enriched fields nor the priorities; approve runs the
    status-checker apply-approval edit; edit re-dispatches the designer without the feedback.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _approval_step_support import (  # noqa: E402
    BATCH, RELEASED, apply_calls, approve_calls, calls, gate_record, ids_of, names, position, prepass_for,
    priority_of, readiness_editing_prompts, resume, route_approval_step, run, step_replies, table,
)

FEEDBACK = "Split test_spec entry two by clause; it proves two outcomes at once."


@pytest.fixture
def prepass(tmp_path):
    return prepass_for(tmp_path, BATCH)


def _approve(tmp_path, monkeypatch, prepass, priority: str = "high"):
    route_approval_step(monkeypatch)
    dry, applied = step_replies(tmp_path)
    return run(table(prepass, BATCH, dry, applied), resume("approve", priority))


def test_final_gate_shows_enriched_fields_and_test_design(prepass):
    # covers: ACD-300c-3
    # angle: criterion
    """Run to the final-gate pause: the persisted question names assigned_agent, estimated_complexity,
    delivers_to, expects_from and the test design (test_spec) for the batch, and its context lists every
    batch id."""
    result = run(table(prepass, BATCH))

    record = gate_record(result)
    assert record is not None, f"the run never paused at the final gate; dispatched: {names(result)}"
    question = str((record.get("question") or {}).get("prompt", ""))
    missing = [f for f in ("assigned_agent", "estimated_complexity", "delivers_to", "expects_from", "test_spec") if f not in question]
    assert missing == [], f"the final-gate question does not name {missing}: {question[:600]!r}"
    assert sorted((record.get("context") or {}).get("acs", [])) == BATCH, record.get("context")


def test_final_gate_asks_for_one_batch_priority(tmp_path, monkeypatch, prepass):
    # covers: ACD-300c-3
    # angle: criterion
    """The persisted final-gate question is a priority choice naming critical, high, medium and low, and
    the approve answer's priority (low here, not the medium fallback) is the one passed to the step."""
    paused = run(table(prepass, BATCH))
    question = (gate_record(paused) or {}).get("question") or {}
    assert question.get("type") == "priority_choice", question
    words = [p for p in ("critical", "high", "medium", "low") if not re.search(rf"\b{p}\b", str(question.get("prompt", "")))]
    assert words == [], f"the question does not name {words}: {question.get('prompt')!r}"

    result = _approve(tmp_path, monkeypatch, prepass, priority="low")

    applies = apply_calls(result)
    assert len(applies) == 1, f"expected one approval-step run; dispatched: {names(result)}"
    assert priority_of(applies[0]) == "low", applies[0].prompt[:600]


def test_final_gate_approve_runs_the_approval_step_with_released_ids(tmp_path, monkeypatch, prepass):
    # covers: ACD-300c-3
    # angle: reachability
    """A run resumed with a person's approve (priority high) on a batch whose hold report holds one id
    dispatches the approval-step command (approve_acs.py with the released ids and --priority high) and
    returns status ok; no status-checker apply-approval dispatch happens."""
    result = _approve(tmp_path, monkeypatch, prepass)

    applies = apply_calls(result)
    assert len(applies) == 1, f"expected one approval-step run; dispatched: {names(result)}"
    assert sorted(ids_of(applies[0])) == RELEASED and priority_of(applies[0]) == "high", applies[0].prompt[:600]
    assert calls(result, "apply-approval") == [], names(result)
    assert (result.result or {}).get("status") == "ok", result.result


def test_final_gate_approve_never_lets_an_agent_write_readiness(tmp_path, monkeypatch, prepass):
    # covers: ACD-300c-3
    # angle: discrimination
    """Same approve run: the only approval dispatch is the deterministic approval-step command; its --ids
    list is exactly the released ids, and no agent prompt asks to set readiness or priority.

    Wrong versions caught: the approve branch still dispatches the status-checker apply-approval agent; the
    step is given every batch id, including the held one; the chosen priority is dropped and the step is
    run with medium.
    """
    result = _approve(tmp_path, monkeypatch, prepass)

    assert readiness_editing_prompts(result) == [], names(result)
    applies = apply_calls(result)
    assert len(applies) == 1 and len(approve_calls(result)) >= 2, names(result)  # dry run + one apply
    assert sorted(ids_of(applies[0])) == RELEASED, applies[0].prompt[:600]
    assert priority_of(applies[0]) == "high", applies[0].prompt[:600]


def test_final_gate_edit_redispatches_the_test_designer_with_feedback(prepass):
    # covers: ACD-300c-3
    # angle: discrimination
    """A person's edit answer with feedback at the final gate re-dispatches stage-test-design-author whose
    prompt carries that feedback text; stage-itpo-author is not dispatched again after the gate.

    Wrong versions caught: edit re-dispatches the test designer but drops the user's feedback; edit
    re-dispatches the technical planner instead of the test-design stage.
    """
    result = run(table(prepass, BATCH), resume("edit", feedback=FEEDBACK))

    answered = position(result, "read-pause-record")
    after = result.agent_calls[answered:]
    designers = [c for c in after if c.label == "stage-test-design-author"]
    assert designers, f"the test-design stage was not re-run after the gate; dispatched: {names(result)}"
    assert FEEDBACK in designers[0].prompt, designers[0].prompt[:900]
    assert [c.label for c in after if c.label == "stage-itpo-author"] == [], names(result)


def test_final_gate_defer_leaves_records_untouched(prepass):
    # covers: ACD-300c-3
    # angle: criterion
    """A defer answer returns status ok with acs_as_reviewed equal to the batch; no approval-step dispatch
    and no commit-stage-output dispatch follow the gate."""
    result = run(table(prepass, BATCH), resume("defer"))

    outcome = result.result or {}
    assert outcome.get("status") == "ok", outcome
    assert sorted(outcome.get("acs_as_reviewed") or []) == BATCH, outcome
    assert approve_calls(result) == [], names(result)
    answered = position(result, "read-pause-record")
    assert [c.label for c in result.agent_calls[answered:] if c.label == "commit-stage-output"] == [], names(result)


def test_final_gate_reports_approved_and_held_counts(tmp_path, monkeypatch, prepass):
    # covers: ACD-300c-3
    # angle: discrimination
    """With an approval-step report of 3 approved and 1 held, the closing message states 3 approved and
    1 held.

    Wrong versions caught: the approved count is the size of the batch (4) instead of the step report's
    approved list; the held count is taken from the pre-gate (old) hold list, which here holds nothing.
    """
    result = _approve(tmp_path, monkeypatch, prepass)

    message = str((result.result or {}).get("message", ""))
    assert re.search(r"\b3 (?:AC\(s\) )?approved\b", message), message[:600]
    assert re.search(r"\b1 held\b", message), message[:600]
