"""
MODULE: unit_tests/ac_driven_dev/test_design_stage/test_acd_300c_4.py
COVERS: ACD-300c-4
GOAL: Red-first specification of the workflow half of ACD-300c-4: on a person's "approve" at the final
    gate, /plan-feature takes the hold report from the store's one approval step (approve_acs.py
    --dry-run --json) and runs that same step, as a deterministic dispatch, with exactly the released ids
    and the chosen priority; no agent edits readiness or priority; the closing summary states the counts
    and names each held record with its reason.
ARCHITECTURE: The REAL plan-feature.js under run_workflow_under_e2, resumed at final-gate
    (_approval_step_support.py): the approval-step replies are the REAL approve_acs.py output on a tmp
    store (ACD-9990a-3 held for "file finding undecided"), routed by command; the old
    approval_hold_report.py reply disagrees (holds nothing). The store half lives in
    unit_tests/ac_store/test_acd_300c_4.py.
RED STATE: the approve branch dispatches the status-checker `apply-approval` agent edit with the ids the
    old hold report releases; no approve_acs.py dispatch exists.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _approval_step_support import (  # noqa: E402
    BATCH, HELD, RELEASED, UNDECIDED, apply_calls, calls, dry_calls, ids_of, names, prepass_for, priority_of,
    readiness_editing_prompts, resume, route_approval_step, run, step_replies, table,
)


def _approve_run(tmp_path, monkeypatch):
    route_approval_step(monkeypatch)
    dry, applied = step_replies(tmp_path)
    return run(table(prepass_for(tmp_path, BATCH), BATCH, dry, applied), resume("approve", "high"))


def test_workflow_approves_through_the_step_with_exactly_the_released_ids(tmp_path, monkeypatch):
    # covers: ACD-300c-4
    # angle: reachability
    """Resumed with approve and priority high: the workflow runs the step's dry run on the batch, then the
    approve_acs.py command with --ids exactly ACD-9990a-1,ACD-9990a-2,ACD-9990a-4 and --priority high, and
    no agent prompt asks to set readiness or priority.

    Wrong versions caught: the workflow keeps the status-checker apply-approval agent edit; it takes its
    hold list from approval_hold_report.py (whose reply here holds nothing) while approving with the step.
    """
    result = _approve_run(tmp_path, monkeypatch)

    applies = apply_calls(result)
    assert len(applies) == 1, f"expected one approval-step run; dispatched: {names(result)}"
    assert dry_calls(result) and dry_calls(result)[-1].call_index < applies[0].call_index, names(result)
    assert sorted(ids_of(dry_calls(result)[-1])) == BATCH
    assert sorted(ids_of(applies[0])) == RELEASED, applies[0].prompt[:600]
    assert priority_of(applies[0]) == "high", applies[0].prompt[:600]
    assert calls(result, "apply-approval") == [], names(result)
    assert readiness_editing_prompts(result) == [], names(result)


def test_closing_summary_states_three_approved_one_held(tmp_path, monkeypatch):
    # covers: ACD-300c-4
    # angle: criterion
    """With the step's real --json report (3 approved, ACD-9990a-3 held for "file finding undecided"), the
    run's closing message states "3 approved, 1 held" and names ACD-9990a-3 with that reason."""
    result = _approve_run(tmp_path, monkeypatch)

    outcome = result.result or {}
    message = str(outcome.get("message", ""))
    assert outcome.get("status") == "ok", outcome
    assert "3 approved, 1 held" in message, message[:600]
    assert HELD in message and UNDECIDED in message, message[:600]


# --------------------------------------------------------------------------
# review fixes: H-1 (draft records are approved), L-1 (hold found at apply time)
# --------------------------------------------------------------------------
import json  # noqa: E402

from _acd_300c_4_fixtures import PRIOR_PRIORITY, records_store, reviewed_intent, reviewed_no_tests, run_ids  # noqa: E402
from _approval_step_support import _reply  # noqa: E402


def test_draft_l1_reviewed_leaf_and_held_leaf_end_with_two_approved_one_held(tmp_path, monkeypatch):
    # covers: ACD-300c-4
    # angle: failure
    """A strategic-run batch: a draft L1 (the PO's record), a reviewed leaf and a leaf held for its missing
    test design. With the step's REAL replies, the run ends status ok with "2 approved, 1 held" and no
    error: a non-held draft record is approved like a reviewed one."""
    route_approval_step(monkeypatch)
    l1, leaf, held = "ACD-9990a", "ACD-9990a-1", "ACD-9990a-2"
    ids = [l1, leaf, held]
    store = records_store(tmp_path / "approval-store", [
        reviewed_no_tests(l1, level="L1", readiness="draft", covered_by=[leaf, held], priority=PRIOR_PRIORITY),
        reviewed_no_tests(leaf, depends_on=[l1], priority=PRIOR_PRIORITY),
        reviewed_intent(held, depends_on=[l1], priority=PRIOR_PRIORITY),
    ])
    dry = _reply(run_ids(store, ids, "--dry-run", priority="high"))
    released = json.loads(dry["output"])["approved"] if dry["output"] else []
    applied = _reply(run_ids(store, released or ids, priority="high"))

    result = run(table(prepass_for(tmp_path, ids), ids, dry, applied), resume("approve", "high"))

    outcome = result.result or {}
    assert outcome.get("status") == "ok", outcome
    assert "2 approved, 1 held" in str(outcome.get("message", "")), outcome.get("message")
    assert sorted(outcome.get("acs_approved", [])) == sorted([l1, leaf]), outcome
    assert store.read(l1)["readiness"] == "approved" and store.read(held)["readiness"] == "reviewed"


def test_a_hold_found_at_apply_time_is_reported_held(tmp_path, monkeypatch):
    # covers: ACD-300c-4
    # angle: discrimination
    """The dry run releases three ids, but the apply run's own report holds one of them (the step checks
    every hold again): the closing summary counts it held and names it, and does not count it approved."""
    route_approval_step(monkeypatch)
    dry, _applied = step_replies(tmp_path)
    late = RELEASED[2]
    applied = {"output": json.dumps({"approved": RELEASED[:2], "already_approved": [], "held": [
        {"id": late, "file": "docs/acceptance-criteria/x/late.yaml", "reason": UNDECIDED}]}), "exit_code": 0, "stderr": ""}

    result = run(table(prepass_for(tmp_path, BATCH), BATCH, dry, applied), resume("approve", "high"))

    outcome = result.result or {}
    message = str(outcome.get("message", ""))
    assert outcome.get("status") == "ok" and "2 approved, 2 held" in message, message[:600]
    assert late in message and late not in (outcome.get("acs_approved") or []), outcome
