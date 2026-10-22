"""
MODULE: unit_tests/ac_driven_dev/test_design_stage/test_acd_2500c_2.py
COVERS: ACD-2500c-2 (and ACD-2500d-5-i's fifth test, moved here by the G4 architect note, conflict 3)
GOAL: Red-first specification of the new test-design stage in /plan-feature: it runs after the
    technical planner and before the final approval gate, the gate shows each approvable
    requirement's design next to its criteria, a record the designer could not design is held and
    not offered, and a skipped or failed step for the whole batch offers nothing.
BUSINESS CONTEXT: Approval must never release a requirement with intent but no test design. The
    workflow cannot read records (its body has no file access); the held set comes from the
    deterministic `approval_hold_report.py` run through the shell-permitted agent, and success is
    never read from the designer's text.
ARCHITECTURE: The REAL plan-feature.js under run_workflow_under_e2 on the "technical" route
    (see _design_stage_support.py). New labels (architect note, section 2.6): design-prepass,
    stage-test-design-author, rule-check-test-design, approval-holds. The gate payload is the pause
    record persisted at final-gate (`context.acs`, `held`, `approvable`), because the headless gate
    never calls its live-gate closure. The failure-mode tests are in test_acd_2500c_2_failures.py.
RED STATE: HEAD has no test-design stage: the pipeline ends at itpo with the final gate, so no
    design-prepass / stage-test-design-author / approval-holds dispatch exists.
WRONG VERSIONS the tests catch: itpo keeps the final gate (a pause before the design step); the
    gate payload carries ids only; a held record is offered or approved; `written` at the final
    commit is only the designer's own records; a rewrite after approval is committed unseen.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts" / "ac_store"))

from _approval_holds import build_report  # noqa: E402
from _design_stage_support import (  # noqa: E402
    GATE, IDS, NO_RECORD, PAUSE, PENDING, calls, check_reply, designer_reply, gate_context,
    gate_record, holds_reply, labels, names, position, prepass_paths, prepass_reply, resume_args,
    run, sequenced,
)


@pytest.fixture
def prepass(tmp_path):
    return prepass_reply(tmp_path)


def test_code_aware_step_runs_before_final_gate(prepass):
    # covers: ACD-2500c-2
    # angle: reachability
    """AC-1: on a 4-requirement batch the workflow runs the itpo stage (author, check, commit), then
    the pre-pass script, the designer, the rule check and the hold report, and only then pauses at the
    final gate. The designer is dispatched once, as `test-designer`, with all four ids and the pre-pass
    facts (every declared path of the real report) in its prompt."""
    result = run(labels(prepass, holds_reply()))

    order = ["stage-itpo-author", "rule-check-itpo", "commit-stage-output", "design-prepass",
             "stage-test-design-author", "rule-check-test-design", "approval-holds", "pause-persist"]
    spots = [position(result, label) for label in order]
    assert spots == sorted(spots), f"stage order wrong: {[n for n in names(result) if n in order]}"
    assert len(calls(result, "stage-test-design-author")) == 1, names(result)
    prepass_cmd = calls(result, "design-prepass")[0].prompt
    assert "design_prepass.py" in prepass_cmd and f"--ids {','.join(IDS)}" in prepass_cmd, prepass_cmd[:600]
    designer = calls(result, "stage-test-design-author")[0]
    assert designer.agent_type == "test-designer", designer.opts
    for needle in [*IDS, *prepass_paths(prepass)]:
        assert needle in designer.prompt, f"the designer prompt lacks {needle!r}:\n{designer.prompt[:900]}"
    assert gate_record(result)["gate_id"] == GATE


def test_itpo_stage_is_auto_approved_and_committed_before_the_design_step(prepass):
    # covers: ACD-2500c-2
    # angle: discrimination
    """AC-1 (stage order): the itpo stage is committed without a person's gate, so HEAD is the designer's
    before-state. No pause is persisted before the pre-pass runs. Wrong version caught: itpo keeps
    gate "final" and the run stops for approval before the design step ever starts."""
    result = run(labels(prepass, holds_reply()))

    pre_pass_at = position(result, "design-prepass")
    commit_at = position(result, "commit-stage-output")
    assert position(result, "rule-check-itpo") < commit_at < pre_pass_at, names(result)
    early = [i for i, c in enumerate(result.agent_calls) if c.label == "pause-persist" and i < pre_pass_at]
    assert early == [], f"the run paused before the design step: {names(result)}"
    assert len(calls(result, "pause-persist")) == 1, names(result)  # exactly one gate: the final one


def test_stage_rule_check_runs_after_the_designer_against_head(prepass):
    # covers: ACD-2500c-2
    # angle: criterion
    """AC-1 (order: pre-pass, designer, then the requirement rule check): the rule-check command is the real
    script for the `test-design` stage, scoped to what changed since the committed itpo output (HEAD), with
    HEAD as the before-state."""
    result = run(labels(prepass, holds_reply()))

    designer_at = position(result, "stage-test-design-author")
    check = calls(result, "rule-check-test-design")
    assert len(check) == 1 and position(result, "rule-check-test-design") > designer_at, names(result)
    cmd = check[0].prompt
    for flag in ("requirement_rule_check.py", "--stage test-design", "--changed-since HEAD", "--before-ref HEAD"):
        assert flag in cmd, f"{flag!r} missing from the rule-check command:\n{cmd[:700]}"


def test_gate_shows_design_next_to_criteria(prepass):
    # covers: ACD-2500c-2
    # angle: criterion
    """AC-2: with no hold, the final-gate payload names all four requirements as approvable, carries every
    id of the run in `acs` (the final commit stages `acs`), an empty `held` list, and tells the presenter to
    show each requirement's `test_spec` next to its `criteria`. Wrong version caught: a gate payload that
    carries only ids and the rule-check summary (the pre-G4 shape)."""
    result = run(labels(prepass, holds_reply()))

    position(result, "design-prepass")  # the stage ran; otherwise the payload below is itpo's
    context = gate_context(result)
    assert sorted(context.get("acs", [])) == IDS, context
    assert sorted(context.get("approvable", [])) == IDS, context
    assert context.get("held") == [], context
    payload = json.dumps(gate_record(result))
    assert "criteria" in payload and "test_spec" in payload, payload[:900]


def test_undesignable_record_shown_pending_not_offered(prepass):
    # covers: ACD-2500c-2
    # angle: failure
    """AC-3: TDG-3's declared files could not be opened (the designer reports it pending; the hold report
    reads it `test design pending`). The final gate lists TDG-3 separately with that reason and does not
    offer it; the other three stay approvable (control rows) and the stage still reaches the gate."""
    held = {"TDG-3": PENDING}
    result = run(labels(prepass, holds_reply(held), designer=designer_reply(pending=("TDG-3",))))

    position(result, "design-prepass")
    context = gate_context(result)
    assert [(h["id"], h["reason"]) for h in context.get("held", [])] == [("TDG-3", PENDING)], context
    assert sorted(context.get("approvable", [])) == ["TDG-1", "TDG-2", "TDG-4"], context
    assert "TDG-3" not in context["approvable"]
    assert sorted(context.get("acs", [])) == IDS, "the held record's design is still committed with the run"
    assert PENDING in json.dumps(gate_record(result))


def _step_reply(approved: list[str], held: dict[str, str]) -> dict:
    """An approve_acs.py --ids ... --json reply (its real shape): approved, held entries, already_approved."""
    entries = [{"id": rid, "file": f"docs/acceptance-criteria/x/{rid}.yaml", "reason": why} for rid, why in held.items()]
    report = {**build_report(approved, entries), "already_approved": []}
    return {"output": json.dumps(report), "exit_code": 0, "stderr": ""}


def test_resumed_approval_applies_only_to_approvable_records(prepass):
    # covers: ACD-2500c-2
    # angle: failure
    """AC-3 (not offered for approval): a resumed `approve` takes the hold report from the approval step's
    dry run (ACD-300c-4) right before the approval write, then runs that step with the three approvable ids
    only; held TDG-3 is never named in the approval command and is not reported approved, yet the final
    commit still stages all four ids. Wrong versions caught: approve-all (the pre-G4 behaviour), the old
    status-checker apply-approval agent edit, and a final commit that stages only approved ids."""
    ok = ["TDG-1", "TDG-2", "TDG-4"]
    labs = labels(
        prepass, holds_reply({"TDG-3": PENDING}), designer=designer_reply(pending=("TDG-3",)),
        **{"approval-holds": _step_reply(ok, {"TDG-3": PENDING}), "approval-apply": _step_reply(ok, {})},
    )
    result = run(labs, resume_args())

    dry_at = position(result, "approval-holds")
    assert "approve_acs.py" in result.agent_calls[dry_at].prompt and "--dry-run" in result.agent_calls[dry_at].prompt
    apply_calls = calls(result, "approval-apply")
    assert len(apply_calls) == 1 and position(result, "approval-apply") > dry_at, names(result)
    assert calls(result, "apply-approval") == [], f"an agent edited readiness: {names(result)}"
    assert "approve_acs.py" in apply_calls[0].prompt and "--dry-run" not in apply_calls[0].prompt, apply_calls[0].prompt
    for rid in ok:
        assert rid in apply_calls[0].prompt, apply_calls[0].prompt
    assert "TDG-3" not in apply_calls[0].prompt, apply_calls[0].prompt
    assert sorted((result.result or {}).get("acs_approved", [])) == ok, result.result
    final_commit = calls(result, "commit-stage-output")[-1].prompt
    assert all(rid in final_commit for rid in IDS), f"the final commit must stage all four ids:\n{final_commit[:900]}"


def test_rewrite_after_approval_pauses_again_instead_of_approving(prepass, monkeypatch):
    # covers: ACD-2500c-2
    # angle: discrimination
    """The user's re-approval rule holds for the new stage: a resumed `approve` whose post-gate rule check
    fails makes the designer rewrite once; the re-check now passes, but the person never saw the rewrite, so
    the run pauses at the final gate again. No approval write, and no commit after the design step began.
    Wrong version caught: reusing the consumed approval for the rewritten designs."""
    sequenced(monkeypatch)
    labs = labels(
        prepass, holds_reply(),
        check={"__sequence__": [check_reply(False), check_reply(True)]},
        **{"read-pause-record": {"__sequence__": [PAUSE, NO_RECORD]}},
    )
    result = run(labs, resume_args())

    assert len(calls(result, "stage-test-design-author")) == 1, names(result)  # re-dispatched once
    assert len(calls(result, "rule-check-test-design")) == 2, names(result)  # and re-checked
    assert calls(result, "approval-apply") == [], f"the rewrite was approved unseen: {names(result)}"
    last_check = position(result, "rule-check-test-design", 1)
    assert [i for i, c in enumerate(result.agent_calls) if c.label == "commit-stage-output" and i > last_check] == []
    assert position(result, "pause-persist") > last_check, names(result)
    assert gate_record(result)["gate_id"] == GATE
