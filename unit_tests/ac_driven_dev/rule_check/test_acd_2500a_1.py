"""
MODULE: test_acd_2500a_1 (workflow half, unit_tests/ac_driven_dev/rule_check/)
GOAL: Red-first specification of ACD-2500a-1's workflow behaviour: templates/
    workflows-js/plan-feature.js runs the requirement rule check at the end of an
    authoring stage and does not report that stage complete while the check failed.
BUSINESS CONTEXT: The stage agent's own word that it is done is not evidence; the
    check's exit status and JSON report decide (architect note, section 4). A failed
    check must keep the stage uncommitted, keep the next stage's author from running,
    and never end in status "ok".
ARCHITECTURE: Drives the REAL plan-feature.js through the E2 harness
    (unit_tests/_workflow_engine_harness.run_workflow_under_e2) on the "behavioral"
    route (ba -> itpo), resuming at gate-ba with a person-attributed `approve`
    answer. The check's dispatch is the label `rule-check-ba` (note section 4); its
    reply is the CLI's stdout/exit code. One test feeds the REAL CLI's own report
    into the workflow (producer -> consumer seam).

    Placed in the `rule_check` sub-package because unit_tests/ac_driven_dev/ is at the
    folder-density limit; with the extra directory level the repo root is
    `Path(__file__).resolve().parents[3]`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "unit_tests"))
sys.path.insert(0, str(REPO_ROOT / "unit_tests" / "ac_store"))

from _rule_check_fixtures import (  # noqa: E402
    cli_argv,
    hierarchy,
    make_store,
    run_cli_subprocess,
)
from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402

PLAN_FEATURE_JS = REPO_ROOT / "templates" / "workflows-js" / "plan-feature.js"
_STAGE_AC = "RC-1"
_FAILING_FILE = "docs/acceptance-criteria/ac-driven-dev/rule-check-demo/RC-1.yaml"
_CHECK_LABEL = "rule-check-ba"
_PAUSE_RECORD = {
    "exists": True,
    "stale": False,
    "record": {"gate_id": "gate-ba", "context": {"stage": "ba", "acs": [_STAGE_AC]}},
}


def _contract_report(verdict: str, findings: list[dict]) -> dict:
    """A report shaped exactly like the ACD-2500a-1 contract (additive keys omitted)."""
    return {
        "verdict": verdict,
        "location": "docs/acceptance-criteria/ac-driven-dev/rule-check-demo",
        "records_checked": 4,
        "findings": findings,
    }


_FINDING = {
    "file": _FAILING_FILE,
    "record_id": _STAGE_AC,
    "rule_family": "producer/consumer contract symmetry",
    "disposition": "needs a decision",
    "message": "RC-1 expects a contract from RC-0, which declares no delivery",
    "line": None,
    "detail": None,
}


def _reply(report: dict, exit_code: int) -> dict:
    """The agent reply the workflow reads: the command's stdout and exit code."""
    return {"output": json.dumps(report), "exit_code": exit_code, "stderr": ""}


def _run_ba_stage(check_reply: dict):
    """Resume the behavioral route at gate-ba with `approve`; return the harness result."""
    labels = {
        "stage-0-triage": {
            "route": "behavioral", "existing_acs": [], "parent_l1_id": "RC-L1",
            "rationale": "forced for the rule-check workflow test",
        },
        # The stage agent claims success in prose: the check must not believe it.
        "stage-ba-author": {"status": "ok", "acs_written": [_STAGE_AC],
                            "message": "All checks passed, nothing to fix."},
        "peek-pause-record": _PAUSE_RECORD,
        "read-pause-record": _PAUSE_RECORD,
        "clear-pause-record": {"ok": True},
        "clear-pause-record-verify": {"exists": False},
        "branch-check": {"output": "ac-authoring/rule-check-test", "exit_code": 0},
        "commit-stage-output": {"status": "ok", "message": "committed successfully"},
        _CHECK_LABEL: check_reply,
    }
    args = {
        "run_id": "rule-check-run",
        "resume_answer": {
            "gate_id": "gate-ba", "type": "single_choice", "action": "approve", "channel": "person",
        },
    }
    result = run_workflow_under_e2(PLAN_FEATURE_JS, label_responses=labels, args=args, timeout=90)
    assert not result.error, result.error
    return result


def _labels(result) -> list[str]:
    return [call.label for call in result.agent_calls]


def _assert_stage_blocked(result) -> None:
    labels = _labels(result)
    assert _CHECK_LABEL in labels, f"the check was never dispatched for the stage: {labels}"
    assert "commit-stage-output" not in labels, f"a failed stage was committed: {labels}"
    assert "stage-itpo-author" not in labels, f"the next stage was started: {labels}"
    status = (result.result or {}).get("status")
    assert status != "ok", f"stage reported complete while the check failed: {result.result!r}"


def test_stage_not_reported_complete_while_check_failed():
    # covers: ACD-2500a-1
    # covers: ACD-2500a
    # angle: reachability
    """plan-feature workflow harness: a failed check at stage end keeps the stage from
    being reported complete -- no stage commit, no next-stage author, status not ok --
    even though the stage agent's own reply claims success."""
    result = _run_ba_stage(_reply(_contract_report("failed", [_FINDING]), 1))

    _assert_stage_blocked(result)
    check = next(call for call in result.agent_calls if call.label == _CHECK_LABEL)
    assert check.agent_type == "worktree-agent"  # a shell-permitted agent runs the script
    assert "requirement_rule_check.py" in check.prompt
    assert "--stage ba" in check.prompt and "--changed-since HEAD" in check.prompt
    assert _FAILING_FILE in json.dumps(result.result), (
        "the failing report must be shown at the gate/result, not swallowed"
    )


def test_passed_check_lets_the_stage_complete():
    # covers: ACD-2500a-1
    # angle: criterion
    """Control: with a passed report (exit 0, records_checked > 0) the same stage is
    committed once and the pipeline moves on to the next stage's author -- so the
    blocking above is the check's doing, not a blanket refusal."""
    result = _run_ba_stage(_reply(_contract_report("passed", []), 0))

    labels = _labels(result)
    assert _CHECK_LABEL in labels, labels
    # the BA stage is committed once (itpo is auto-approved and committed too: ACD-2500c-2)
    ba_commits = [c for c in result.agent_calls if c.label == "commit-stage-output" and "plan-feature(BA)" in c.prompt]
    assert len(ba_commits) == 1, labels
    assert labels.count("stage-itpo-author") == 1, labels


def test_exit_status_and_report_verdict_disagreement_blocks_the_stage():
    # covers: ACD-2500a-1
    # angle: failure
    """A report claiming `passed` with a non-zero exit status (or the reverse) is not
    trusted: the stage is blocked exactly as for a failed check."""
    contradiction = _reply(_contract_report("passed", []), 1)

    result = _run_ba_stage(contradiction)

    _assert_stage_blocked(result)


def test_unreadable_check_reply_blocks_the_stage():
    # covers: ACD-2500a-1
    # angle: failure
    """A reply that is not the report (prose, empty output) is a failed check, never a
    pass: the stage is blocked."""
    prose = {"output": "Looks good to me, all rules satisfied.", "exit_code": 0, "stderr": ""}

    result = _run_ba_stage(prose)

    _assert_stage_blocked(result)


def test_real_cli_report_blocks_the_stage(tmp_path):
    # covers: ACD-2500a-1
    # angle: seam
    """Producer -> consumer: the REAL CLI's own stdout and exit status for a folder with
    a one-sided contract are fed to plan-feature.js, which must block the stage."""
    records = hierarchy(
        "ACD-9990", 2,
        child={2: {"expects_from": {"ac_id": "ACD-9990a-1", "contract": "A report."}}},
    )
    store = make_store(tmp_path, records)
    run = run_cli_subprocess(cli_argv(store), cwd=store.repo_root)
    assert run.exit_code == 1 and run.report["verdict"] == "failed", run.stderr

    result = _run_ba_stage({"output": run.stdout, "exit_code": run.exit_code, "stderr": run.stderr})

    _assert_stage_blocked(result)
