"""
MODULE: unit_tests/ac_driven_dev/test_design_stage/test_acd_2500c_2_failures.py
COVERS: ACD-2500c-2, ACD-2500d-5-i (fifth test)
GOAL: Red-first specification of the fail-closed side of the test-design stage: a skipped or failed
    step for the whole batch offers none of the records for approval, no pre-pass report means the
    designer is never dispatched, an empty batch is a passed skip (not a failure), and a hold report
    the workflow cannot read means nothing is approved.
BUSINESS CONTEXT: AC-4 of ACD-2500c-2 and the last clause of ACD-2500d-5-i. Success is judged from
    the records' on-disk state (the hold report and the rule check), never from the designer's text.
ARCHITECTURE: Same harness and replies as test_acd_2500c_2.py (see _design_stage_support.py).
    Whole-batch failure kinds: the pre-pass exits non-zero with no report; the designer answers
    `blocked`; the designer's reply is not JSON.
    Two views of "none offered": (A) a first run, whose disk says every record reads `test design
    pending`, pauses with an empty `approvable`; (B) a resumed `approve` whose first post-gate check
    fails re-dispatches the step, the step fails again, and the run ends `error` with no approval
    write, even though this scenario's hold report (deliberately wrong) says every record is
    approvable, so the step's own failure is what blocks.
WRONG VERSIONS the tests catch: the designer is dispatched without a pre-pass report; a failed step is
    ignored and the rewrite approved; an empty pre-pass batch fails the stage; an unreadable hold
    report is read as "nothing held".
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _design_stage_support import (  # noqa: E402
    IDS, NO_RECORD, PAUSE, PENDING, calls, check_reply, empty_prepass_reply, gate_context,
    gate_record, holds_reply, labels, names, position, prepass_reply, resume_args, run, sequenced,
)

_NO_REPORT = {"output": "", "exit_code": 1, "stderr": "ERROR: unreadable record TDG-2"}
_BLOCKED = {"status": "blocked", "records": [], "anomalies": ["declared files could not be opened"]}
_NOT_JSON = "I could not design the tests for this batch."

#: whole-batch failure kinds: (pre-pass reply or None for the real one, designer reply or None)
_FAILURES = {
    "prepass_no_report": (_NO_REPORT, None),
    "designer_blocked": (None, _BLOCKED),
    "designer_not_json": (None, _NOT_JSON),
}


@pytest.mark.parametrize("kind", sorted(_FAILURES))
def test_batch_skip_or_failure_offers_none(kind, tmp_path, monkeypatch):
    # covers: ACD-2500c-2
    # angle: failure
    """AC-4: when the step is skipped or fails for the whole batch, none of the 4 is offered. (A) First
    run, disk reads every record pending: if the gate is reached its payload offers nothing and holds all
    four. (B) Resumed `approve` with a hold report that WRONGLY says all four are approvable: the first
    post-gate check fails, the step is re-dispatched, fails again, and the run ends `error` without any
    approval write; the step's own failure blocks, not the (lying) disk report."""
    real = prepass_reply(tmp_path)
    prepass, designer = _FAILURES[kind][0] or real, _FAILURES[kind][1]
    all_held = holds_reply({rid: PENDING for rid in IDS})

    first = run(labels(prepass, all_held, designer=designer))
    position(first, "design-prepass")  # control: the step was attempted
    assert calls(first, "apply-approval") == [] and "acs_approved" not in (first.result or {}), names(first)
    if gate_record(first) is not None:
        context = gate_context(first)
        assert context.get("approvable") == [], f"a failed batch was offered for approval: {context}"
        assert sorted(h["id"] for h in context.get("held", [])) == IDS, context

    sequenced(monkeypatch)
    resumed = run(
        labels(
            prepass, holds_reply(), designer=designer,
            check={"__sequence__": [check_reply(False), check_reply(True)]},
            **{"read-pause-record": {"__sequence__": [PAUSE, NO_RECORD]}},
        ),
        resume_args(),
    )
    position(resumed, "design-prepass")  # the re-dispatch reached the step
    assert calls(resumed, "apply-approval") == [], f"a failed batch was approved: {names(resumed)}"
    assert (resumed.result or {}).get("status") == "error", resumed.result
    assert not (resumed.result or {}).get("acs_approved"), resumed.result


@pytest.mark.parametrize(
    "report",
    [
        {"output": "", "exit_code": 1, "stderr": "ERROR: unknown id"},
        {"output": "not a json document", "exit_code": 0, "stderr": ""},
        {"output": "", "exit_code": 0, "stderr": ""},
    ],
    ids=["non_zero_exit", "unparseable_output", "empty_output"],
)
def test_no_report_blocks_agent_dispatch(report, tmp_path):
    # covers: ACD-2500d-5-i
    # angle: failure
    """ACD-2500d-5-i (last clause, moved here): when the pre-pass script exits non-zero, or exits 0 with no
    usable report, the code-aware agent is not dispatched for the batch, and nothing is approved. Control:
    the pre-pass itself was dispatched exactly once. Wrong version caught: dispatching the designer anyway
    and trusting whatever it returns."""
    result = run(labels(report, holds_reply({rid: PENDING for rid in IDS})))

    assert len(calls(result, "design-prepass")) == 1, names(result)
    assert calls(result, "stage-test-design-author") == [], f"the agent ran without a report: {names(result)}"
    assert calls(result, "apply-approval") == [], names(result)


def test_empty_prepass_batch_skips_the_designer_and_still_reaches_the_gate():
    # covers: ACD-2500c-2
    # angle: boundary
    """Boundary of AC-4: a pre-pass that ran and found no record in scope (no code requirement in the batch)
    is a passed, skipped step, not a failed one: the designer is not dispatched, the gate is reached, its
    summary does not read as a failed check, and the records stay offerable. Wrong version caught: treating
    an empty batch as a whole-batch failure (a docs-only run could never be approved)."""
    result = run(labels(empty_prepass_reply(), holds_reply()))

    assert len(calls(result, "design-prepass")) == 1, names(result)
    assert calls(result, "stage-test-design-author") == [], names(result)
    context = gate_context(result)
    assert "failed" not in str(context.get("rule_check", "")).lower(), context
    assert sorted(context.get("approvable", [])) == IDS, context


@pytest.mark.parametrize(
    "reply",
    [{"output": "", "exit_code": 1, "stderr": "ERROR: unreadable record"},
     {"output": "not a json document", "exit_code": 0, "stderr": ""}],
    ids=["non_zero_exit", "unparseable_output"],
)
def test_unreadable_hold_report_approves_nothing(reply, tmp_path):
    # covers: ACD-2500c-2
    # angle: failure
    """Fail-closed hold oracle: the workflow runs `approval_hold_report.py --ids <all four> --store-root ...`
    right before the approval write, and when that report is missing or unreadable it treats every record as
    held. No approval write is dispatched and nothing is reported approved. Wrong version caught: an
    unreadable report read as "nothing is held" (approve all)."""
    result = run(labels(prepass_reply(tmp_path), reply), resume_args())

    holds = calls(result, "approval-holds")
    assert holds, f"the approval-hold report was never run: {names(result)}"
    cmd = holds[0].prompt
    assert "approval_hold_report.py" in cmd and "--store-root" in cmd, cmd[:700]
    assert f"--ids {','.join(IDS)}" in cmd, cmd[:700]
    assert calls(result, "apply-approval") == [], f"records were approved without a hold report: {names(result)}"
    assert not (result.result or {}).get("acs_approved"), result.result
