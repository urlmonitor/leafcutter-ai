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

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _approval_step_support import (  # noqa: E402
    BATCH, HELD, RELEASED, UNDECIDED, _reply, apply_calls, approve_calls, calls, gate_record, ids_of, names,
    position, prepass_for, priority_of, readiness_editing_prompts, resume, route_approval_step, run, step_replies,
    table,
)
from _acd_300c_4_fixtures import PRIOR_PRIORITY, records_store, reviewed_no_tests, run_ids  # noqa: E402
from _approval_holds import build_report  # noqa: E402
from _design_stage_support import sequenced  # noqa: E402

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
    assert re.search(r"criteria\b[\s\S]{0,60}\btest_spec", question), f"the question puts no criteria next to the test design: {question[:600]!r}"


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


# --------------------------------------------------------------------------
# held records, priority fallback, dispatch order, edit/cancel/defer, closing report, failures
# --------------------------------------------------------------------------
TRIO = ["ACD-9990a-1", "ACD-9990a-2", "ACD-9990a-3"]
_HOOK_FAILURE = {  # BO-4500a-5-ii: the commit agent relays the shared step's failed answer
    "status": "hook_failed",
    "commit_answer": {
        "status": "hook_failed", "reason_code": "check_failed", "reason": "pre-commit hook rejected staged files",
        "hook_name": "check-ac-schema", "failing_files": ["docs/acceptance-criteria/x/ACD-9990a-1.yaml"], "sha": None,
    },
}


def _held_report() -> dict:
    """The pre-gate approval-hold report: ACD-9990a-3 held for an undecided file finding, the rest released."""
    entry = {"id": HELD, "file": f"docs/acceptance-criteria/x/{HELD}.yaml", "reason": UNDECIDED}
    report = build_report([rid for rid in BATCH if rid != HELD], [entry])
    return {"output": json.dumps(report), "exit_code": 0, "stderr": ""}


def _after_answer(result) -> list:
    """The dispatches made after the gate's answer was read."""
    return result.agent_calls[position(result, "read-pause-record") + 1:]


def _final_pauses(result) -> list:
    return [c for c in calls(result, "pause-persist") if "final-gate" in c.prompt]


def test_final_gate_lists_held_acs_apart_with_reason_and_no_approve_option(tmp_path, monkeypatch, prepass):
    # covers: ACD-300c-3
    # angle: discrimination
    """The pre-gate hold report holds ACD-9990a-3 for "file finding undecided". The final-gate question lists
    it with that reason on a line of its own, apart from the released ids; the held id is not among the
    released ids of the gate context; and an approve answer passes the approval step only the released ids.

    Wrong versions caught: the held AC is shown among the released ACs as if it could be approved; the held AC
    is listed without its hold reason.
    """
    route_approval_step(monkeypatch)
    dry, applied = step_replies(tmp_path)

    paused = run(table(prepass, BATCH, dry, applied, **{"approval-holds": _held_report()}))

    record = gate_record(paused)
    assert record is not None, f"the run never paused at the final gate; dispatched: {names(paused)}"
    lines = str((record.get("question") or {}).get("prompt", "")).splitlines()
    held_lines = [line for line in lines if HELD in line]
    assert any(UNDECIDED in line for line in held_lines), f"the held AC is listed without its reason: {lines}"
    assert [line for line in held_lines if any(rid in line for rid in RELEASED)] == [], f"held and released ids share a line: {held_lines}"
    assert [rid for rid in RELEASED if not any(rid in line for line in lines)] == [], f"released ids are not listed: {lines}"
    assert sorted((record.get("context") or {}).get("approvable", [])) == RELEASED, record.get("context")

    approved = run(table(prepass, BATCH, dry, applied, **{"approval-holds": _held_report()}), resume("approve", "high"))
    assert [sorted(ids_of(c)) for c in apply_calls(approved)] == [RELEASED], names(approved)


def test_final_gate_invalid_priority_is_taken_as_medium(tmp_path, monkeypatch, prepass):
    # covers: ACD-300c-3
    # angle: discrimination
    """An approve run whose answer carries priority "urgent" (present but not one of the four values) runs the
    approval step once with --priority medium and returns status ok. The no-priority answer is the boundary
    test below.

    Wrong versions caught: an invalid priority is passed on to the approval step unchanged; an invalid
    priority is treated like a missing one, so the run stays paused instead of applying medium.
    """
    route_approval_step(monkeypatch)
    dry, applied = step_replies(tmp_path)

    result = run(table(prepass, BATCH, dry, applied), resume("approve", "urgent"))

    applies = apply_calls(result)
    assert len(applies) == 1, names(result)
    assert priority_of(applies[0]) == "medium", applies[0].prompt[:600]
    assert (result.result or {}).get("status") == "ok", result.result


def test_final_gate_approve_without_priority_stays_paused(tmp_path, monkeypatch, prepass):
    # covers: ACD-300c-3
    # angle: boundary
    """Mirrors test_bo_2300d_1_iii.py::test_priority_choice_approve_still_requires_priority on this file's
    4-id table. An approve answer with no priority key is not applied: no approve_acs.py dispatch, no
    commit-stage-output or deliver-authoring-branch after the answer, and the run stays paused at final-gate.

    Wrong version caught: a missing priority falls back to medium and approves.
    """
    route_approval_step(monkeypatch)
    dry, applied = step_replies(tmp_path)
    no_priority = resume("approve")
    del no_priority["resume_answer"]["priority"]

    result = run(table(prepass, BATCH, dry, applied), no_priority)

    assert approve_calls(result) == [], names(result)
    read_at = [i for i, c in enumerate(result.agent_calls) if c.label == "read-pause-record"]  # absent: answer never read
    later = [c.label for c in result.agent_calls[read_at[0] + 1:] if c.label in ("commit-stage-output", "deliver-authoring-branch")] if read_at else []
    assert later == [] and calls(result, "deliver-authoring-branch") == [], names(result)
    outcome = result.result or {}
    assert outcome.get("status") == "paused_awaiting_input", outcome
    assert outcome.get("gate_id") == "final-gate", outcome


def test_final_gate_approve_commits_after_the_approval_step_then_delivers(tmp_path, monkeypatch, prepass):
    # covers: ACD-300c-3
    # angle: discrimination
    """The same approve run: after the gate answer the order is the approval-step apply, then exactly one
    final commit-stage-output (the final commit of the run), then deliver-authoring-branch; no
    commit-stage-output comes between the answer and the apply.

    Wrong versions caught: the final commit is made before the approval step runs; the branch is not
    delivered after a successful approve.
    """
    result = _approve(tmp_path, monkeypatch, prepass)

    after = _after_answer(result)
    apply_at = next(i for i, c in enumerate(after) if c in apply_calls(result))
    commits = [i for i, c in enumerate(after) if c.label == "commit-stage-output"]
    delivered = [i for i, c in enumerate(after) if c.label == "deliver-authoring-branch"]
    assert len(commits) == 1 and commits[0] > apply_at, f"expected one commit after the apply: {[c.label for c in after]}"
    assert ", final" in after[commits[0]].prompt, after[commits[0]].prompt[:400]
    assert len(delivered) == 1 and delivered[0] > commits[0], [c.label for c in after]


def test_final_gate_edit_reruns_test_design_once_then_shows_the_gate_again(prepass):
    # covers: ACD-300c-3
    # angle: discrimination
    """The same edit run as the feedback test: exactly one stage-test-design-author dispatch follows the
    answer, the run then pauses at final-gate again (a new final-gate pause record), and no approval-step or
    commit-stage-output dispatch follows the answer.

    Wrong versions caught: edit re-runs the test designer and then ends the run without showing the final
    gate again; edit re-runs the test designer more than once for one answer.
    """
    result = run(table(prepass, BATCH), resume("edit", feedback=FEEDBACK))

    after = _after_answer(result)
    designers = [i for i, c in enumerate(after) if c.label == "stage-test-design-author"]
    assert len(designers) == 1, f"expected one re-run of the designer: {[c.label for c in after]}"
    pauses = [i for i, c in enumerate(after) if c in _final_pauses(result)]
    assert pauses and pauses[0] > designers[0], f"no new final-gate pause after the re-run: {[c.label for c in after]}"
    assert [c.label for c in after if c in approve_calls(result) or c.label == "commit-stage-output"] == [], names(result)


def test_final_gate_cancel_leaves_the_test_design_output_uncommitted(prepass):
    # covers: ACD-300c-3
    # angle: discrimination
    """A person's cancel at final-gate returns a cancelled status, not ok; no approval-step,
    commit-stage-output or deliver-authoring-branch dispatch follows the answer. The cancel message text is
    ACD-300c-5's contract and is not asserted here.

    Wrong versions caught: cancel commits the test-design output before aborting; cancel at the final gate
    returns status ok.
    """
    result = run(table(prepass, BATCH), resume("cancel"))

    assert (result.result or {}).get("status") == "cancelled", result.result
    later = [c.label for c in _after_answer(result) if c in approve_calls(result) or c.label in ("commit-stage-output", "deliver-authoring-branch")]
    assert later == [], names(result)


def test_final_gate_closing_report_names_priority_held_reasons_and_already_approved(tmp_path, monkeypatch, prepass):
    # covers: ACD-300c-3
    # angle: discrimination
    """Approve with priority low. With a step report of 3 approved and ACD-9990a-3 held for "file finding
    undecided", the closing message names priority low and ACD-9990a-3 with that reason, and says nothing
    about already approved ACs. With the repeat-run report (3 already approved) the message also states
    3 already approved.

    Wrong versions caught: the closing report omits the chosen priority; an already-approved count of zero is
    still reported; held ACs are counted but their ids and reasons are not named.
    """
    route_approval_step(monkeypatch)
    dry, applied = step_replies(tmp_path / "first")
    first = str((run(table(prepass, BATCH, dry, applied), resume("approve", "low")).result or {}).get("message", ""))

    assert re.search(r"priority:?\s*low\b", first), first[:600]
    assert re.search(rf"{HELD}\b[^\n]*{UNDECIDED}", first), first[:600]
    assert not re.search(r"already approved", first, re.IGNORECASE), first[:600]

    dry_again, applied_again = step_replies(tmp_path / "again", already_applied=True)
    again = str((run(table(prepass, BATCH, dry_again, applied_again), resume("approve", "low")).result or {}).get("message", ""))
    assert re.search(r"\b3 already approved\b", again), again[:600]


def test_final_gate_approval_failure_states_nothing_committed_and_each_id_state(tmp_path, monkeypatch, prepass):
    # covers: ACD-300c-3
    # angle: discrimination
    """Approve on three released ids where the step approves ACD-9990a-1, fails ACD-9990a-2 and leaves
    ACD-9990a-3 untouched (exit code 1). The run returns status error and its message states that nothing was
    committed and names ACD-9990a-1 as approved before the failure, ACD-9990a-2 as failed and ACD-9990a-3 as
    untouched.

    Wrong versions caught: the failure message does not say that nothing was committed; the untouched ids are
    dropped from the failure message.
    """
    route_approval_step(monkeypatch)
    store = records_store(tmp_path / "trio-store", [reviewed_no_tests(rid, priority=PRIOR_PRIORITY) for rid in TRIO])
    dry = _reply(run_ids(store, TRIO, "--dry-run", priority="high"))
    failed = {"output": json.dumps({"approved": [TRIO[0]], "held": [], "already_approved": [], "failed": [TRIO[1]]}),
              "exit_code": 1, "stderr": f"ERROR: {TRIO[1]} write did not re-parse as YAML\n"}

    result = run(table(prepass_for(tmp_path, TRIO), TRIO, dry, failed), resume("approve", "high"))

    outcome = result.result or {}
    message = str(outcome.get("message", ""))
    assert outcome.get("status") == "error", outcome
    assert re.search(r"nothing was committed", message, re.IGNORECASE), message[:600]
    by_state = {key: next((line for line in message.splitlines() if line.startswith(key)), "") for key in ("Approved", "Failed", "Untouched")}
    for key, rid in (("Approved", TRIO[0]), ("Failed", TRIO[1]), ("Untouched", TRIO[2])):
        others = [other for other in TRIO if other != rid]
        assert rid in by_state[key] and not any(other in by_state[key] for other in others), (key, by_state, message[:600])


def test_final_commit_failure_ends_in_error_without_delivery(tmp_path, monkeypatch, prepass):
    # covers: ACD-300c-3
    # angle: discrimination
    """Approve where the approval step succeeds and the final commit-stage-output reply is a hook failure: the
    run returns status error and no deliver-authoring-branch dispatch follows. The stage name in the message is
    ACD-300c-5's contract and is not asserted here.

    Wrong versions caught: the branch is delivered although the final commit failed; the commit failure is
    reported as a completed run.
    """
    sequenced(monkeypatch)
    route_approval_step(monkeypatch)
    dry, applied = step_replies(tmp_path)
    commits = {"__sequence__": [{"status": "committed", "commit_answer": {"status": "committed", "reason_code": None, "reason": None, "sha": "abc1234"}}, _HOOK_FAILURE]}

    result = run(table(prepass, BATCH, dry, applied, **{"commit-stage-output": commits}), resume("approve", "high"))

    assert len(apply_calls(result)) == 1 and len(calls(result, "commit-stage-output")) >= 2, names(result)
    assert (result.result or {}).get("status") == "error", result.result
    assert calls(result, "deliver-authoring-branch") == [], names(result)
