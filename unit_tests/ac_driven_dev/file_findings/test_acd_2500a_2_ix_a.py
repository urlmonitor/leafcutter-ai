"""
MODULE: unit_tests/ac_driven_dev/file_findings/test_acd_2500a_2_ix_a.py
COVERS: ACD-2500a-2-ix-a
GOAL: Red-first specification of the resume of the hand-back: a run started again on a branch that carries the
    hand-back design commit (plan-feature(TEST-DESIGN-HANDBACK)) and no final test-design commit does not
    dispatch the test designer again, makes no second hand-back commit, continues with the planner's hand-back
    round and then the itpo-handback rule check (before-state HEAD), and reaches the final gate with the batch.
    A final test-design commit alone starts no hand-back round; a hand-back commit alone leaves the final gate
    and the final commit ahead.
ARCHITECTURE: The REAL plan-feature.js under run_workflow_under_e2 on the technical route with the label table
    of _handback_support.py (mirrors test_handback_commit_subject_is_not_read_as_the_final_test_design_stage).
    scan-committed-stages and resume-log are scripted with the commit subjects and bodies of run pf-demo-1;
    approval-holds is served by_round (ACD-9990a-2 undecided before round 1, nothing held after).
RED STATE: the resume scan ignores the hand-back subject, so the test-design stage runs again and round 1
    commits the hand-back design a second time, and the hand-back check is checked after a design re-check.
    The two ordering guards (final commit alone, hand-back commit alone) are green-today guards.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _handback_support import (  # noqa: E402
    PLAN_FEATURE_JS, UNDECIDED, by_round, calls, check_reply, gate_context, holds_reply, labels, names, position,
    prepass_reply,
)
from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402

S, R, T = "ACD-9990a-1", "ACD-9990a-2", "ACD-9990a-3"
IDS = [S, R, T]
RUN = "pf-demo-1"
HANDBACK = "rule-check-itpo-handback"
ROUND_1 = "it-po-findings-round-1"
_HANDBACK_COMMIT = re.compile(r"plan-feature\(TEST-DESIGN-HANDBACK\)", re.IGNORECASE)
_FINAL_COMMIT = re.compile(r"plan-feature\(TEST-DESIGN, final\)", re.IGNORECASE)
_SCAN_ITPO = "b2c3d4e plan-feature(IT-PO): comp\n"
_SCAN_HANDBACK = "a1b2c3d plan-feature(TEST-DESIGN-HANDBACK): comp\n"
_BODY_ITPO = f"plan-feature(IT-PO): comp\n\nAC IDs: {', '.join(IDS)}\nrun-id: {RUN}\nmid-pipeline commit\n"
_BODY_HANDBACK = f"plan-feature(TEST-DESIGN-HANDBACK): comp\n\nAC IDs: {', '.join(IDS)}\nrun-id: {RUN}\nmid-pipeline commit\n"


@pytest.fixture
def prepass(tmp_path):
    return prepass_reply(tmp_path)


@pytest.fixture(autouse=True)
def _served_by_round(monkeypatch):
    by_round(monkeypatch)


def _table(prepass, scan: str, log: str, holds: dict | None = None, handback: dict | None = None) -> dict:
    """The technical-route table with the commit scan and resume log of run pf-demo-1 scripted."""
    served = holds or {"__by_round__": [holds_reply({R: UNDECIDED}, ids=IDS), holds_reply({}, ids=IDS)]}
    designer = {"status": "ok", "anomalies": [],
                "records": [{"id": rid, "test_design": "written", "file_findings": "written", "reason": None} for rid in IDS]}
    return labels(
        prepass, served,
        **{"scan-committed-stages": {"output": scan, "exit_code": 0}, "resume-log": {"output": log, "exit_code": 0},
           "stage-itpo-author": {"status": "ok", "acs_written": IDS, "message": "done"},
           "stage-test-design-author": designer,
           "it-po-findings-round-1": {"status": "ok", "acs_written": [R], "message": "decisions recorded"},
           HANDBACK: handback or check_reply()},
    )


def _failed_check() -> dict:
    """A rule-check reply with verdict failed and exit 1, shaped like requirement_rule_check.py output."""
    finding = {"file": "docs/acceptance-criteria/x/ACD-9990a-1.yaml", "record_id": S, "rule_family": "protected fields",
               "disposition": "needs a decision", "line": None, "detail": {"field": "criteria", "stage": "itpo-handback"},
               "message": "ACD-9990a-1: field criteria was changed during stage itpo-handback, which does not own it"}
    report = {"verdict": "failed", "location": "docs/acceptance-criteria", "records_checked": 3,
              "findings": [finding], "records_to_commit": []}
    return {"output": json.dumps(report), "exit_code": 1, "stderr": ""}


def _resume_table(prepass, **kwargs) -> dict:
    """Only the hand-back design commit and the technical planner's commit are on the branch."""
    return _table(prepass, _SCAN_HANDBACK + _SCAN_ITPO, _BODY_HANDBACK + "\n" + _BODY_ITPO, **kwargs)


def _run(table: dict):
    result = run_workflow_under_e2(PLAN_FEATURE_JS, label_responses=table, args={"run_id": RUN}, timeout=90)
    assert not result.error, result.error
    return result


def _commit_subjects(result, pattern) -> list[str]:
    return [str(c.prompt) for c in calls(result, "commit-stage-output") if pattern.search(str(c.prompt))]


def _final_pause_at(result) -> int | None:
    for i, c in enumerate(result.agent_calls):
        if c.label == "pause-persist" and "final-gate" in str(c.prompt):
            return i
    return None


def test_resume_after_handback_commit_does_not_redispatch_test_designer(prepass):
    # covers: ACD-2500a-2-ix-a
    # angle: reachability
    """Entry point: the workflow dispatch. With plan-feature(TEST-DESIGN-HANDBACK) and plan-feature(IT-PO) on
    the branch and no TEST-DESIGN commit, no stage-test-design-author dispatch happens.

    Wrong version caught: the resume scan ignores the hand-back subject and the whole test-design step runs
    again, as today.
    """
    result = _run(_resume_table(prepass))

    assert calls(result, "stage-test-design-author") == [], names(result)


def test_resume_makes_no_second_handback_commit(prepass):
    # covers: ACD-2500a-2-ix-a
    # angle: discrimination
    """The same resume, run twice with the same table: in each run no commit-stage-output dispatch carries the
    subject plan-feature(TEST-DESIGN-HANDBACK), so the branch keeps its one hand-back design commit.

    Control (so the subject check cannot pass vacuously): a fresh run of the same batch with no commit on the
    branch does make that commit, and the pattern finds it.
    Wrong version caught: the round-1 hand-back commit is made again on resume, as today.
    """
    fresh = _run(_table(prepass, "", ""))
    assert len(_commit_subjects(fresh, _HANDBACK_COMMIT)) == 1, names(fresh)

    for _ in range(2):
        result = _run(_resume_table(prepass))
        assert _commit_subjects(result, _HANDBACK_COMMIT) == [], names(result)


def test_resume_runs_handback_round_then_itpo_handback_check_on_head(prepass):
    # covers: ACD-2500a-2-ix-a
    # angle: criterion
    """The same resume: it-po-findings-round-1 is dispatched and names ACD-9990a-2, then
    rule-check-itpo-handback with --stage itpo-handback and --before-ref HEAD; no rule-check-test-design and
    no commit-stage-output dispatch happens between scan-committed-stages and that check."""
    result = _run(_resume_table(prepass))

    round_at = position(result, ROUND_1)
    assert R in result.agent_calls[round_at].prompt, result.agent_calls[round_at].prompt[:500]
    check_at = position(result, HANDBACK)
    assert round_at < check_at, names(result)
    command = result.agent_calls[check_at].prompt
    assert "--stage itpo-handback" in command and "--before-ref HEAD" in command, command[:700]
    between = [c.label for c in result.agent_calls[position(result, "scan-committed-stages"):check_at]]
    assert [label for label in between if label in ("rule-check-test-design", "commit-stage-output")] == [], between


def test_resume_with_no_undecided_finding_still_runs_itpo_handback_check(prepass):
    # covers: ACD-2500a-2-ix-a
    # angle: discrimination
    """The same resume, but approval-holds reports nothing undecided (the planner had decided every finding
    before the process ended): rule-check-itpo-handback is still dispatched before any final-gate pause, and
    when it replies verdict failed the run does not pause at final-gate.

    Wrong version caught: the hand-back check is skipped when no finding is left undecided, so edits made
    after the hand-back commit reach the final gate unchecked.
    """
    nothing_held = holds_reply({}, ids=IDS)
    passed = _run(_resume_table(prepass, holds=nothing_held))
    check_at = position(passed, HANDBACK)
    pause_at = _final_pause_at(passed)
    assert pause_at is not None and check_at < pause_at, names(passed)

    failing = _failed_check()
    failed = _run(_resume_table(prepass, holds=nothing_held, handback=failing))
    assert calls(failed, HANDBACK), names(failed)
    assert _final_pause_at(failed) is None, f"the run reached the final gate after a failed check: {names(failed)}"


def test_resume_after_handback_commit_reaches_final_gate_with_batch(prepass):
    # covers: ACD-2500a-2-ix-a
    # angle: criterion
    """The same resume with rule-check-itpo-handback passing: the run pauses at final-gate and the persisted
    gate context has all_acs and approvable equal to ACD-9990a-1, ACD-9990a-2 and ACD-9990a-3."""
    result = _run(_resume_table(prepass))

    context = gate_context(result)
    assert sorted(context.get("all_acs", [])) == sorted(IDS), context
    assert sorted(context.get("approvable", [])) == sorted(IDS), context


def test_final_test_design_commit_alone_starts_no_handback_round(prepass):
    # covers: ACD-2500a-2-ix-a
    # angle: discrimination
    """scan-committed-stages lists plan-feature(TEST-DESIGN, final) and plan-feature(IT-PO) and no hand-back
    commit: no it-po-findings-round-* dispatch, no rule-check-itpo-handback and no stage-test-design-author
    dispatch happens, and the ids recovered for the run are the final commit ids.

    Wrong version caught: a prefix label match reads the final TEST-DESIGN commit as the hand-back design and
    starts a hand-back round.
    """
    scan = "abc1234 plan-feature(TEST-DESIGN, final): comp\n" + _SCAN_ITPO
    log = (
        "plan-feature(TEST-DESIGN, final): comp\n\nAC IDs: TD-1, TD-2\nrun-id: pf-demo-1\nfinal commit of run\n\n"
        "plan-feature(IT-PO): comp\n\nAC IDs: IT-1\nrun-id: pf-demo-1\nmid-pipeline commit\n"
    )
    result = _run(_table(prepass, scan, log))

    started = [n for n in names(result) if n.startswith("it-po-findings-round-") or n in (HANDBACK, "stage-test-design-author")]
    assert started == [], names(result)
    assert sorted((result.result or {}).get("acs_written") or []) == ["IT-1", "TD-1", "TD-2"], (result.result, names(result))


def test_handback_commit_alone_leaves_final_gate_and_final_commit_ahead(prepass):
    # covers: ACD-2500a-2-ix-a
    # angle: discrimination
    """scan-committed-stages lists only plan-feature(IT-PO) and plan-feature(TEST-DESIGN-HANDBACK): the run
    returns paused_awaiting_input at final-gate (never the Pipeline complete fall-through), and no
    commit-stage-output dispatch carries plan-feature(TEST-DESIGN, final) before that pause.

    Wrong version caught: the hand-back subject is mapped to the test-design stage key, so the step is
    skipped and the run ends without a final gate or final commit.
    """
    result = _run(_resume_table(prepass))

    outcome = result.result or {}
    assert (outcome.get("status"), outcome.get("gate_id")) == ("paused_awaiting_input", "final-gate"), outcome
    pause_at = _final_pause_at(result)
    assert pause_at is not None, names(result)
    early = [c for c in result.agent_calls[:pause_at] if c.label == "commit-stage-output" and _FINAL_COMMIT.search(str(c.prompt))]
    assert early == [], names(result)
