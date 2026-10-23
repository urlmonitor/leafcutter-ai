"""
MODULE: unit_tests/workflows/test_acd_300c_5.py
COVERS: ACD-300c-5
GOAL: Red-first specification that every final-gate message names the test-design stage that now owns
    the final gate: the gate's question and its no-answer failure, the final-gate cancel message
    ("final gate (test design)") and the final commit failure ("Commit of test-design AC output failed"),
    while the product owner, business analyst and technical planner messages stay character for character.
ARCHITECTURE: The REAL plan-feature.js under run_workflow_under_e2 (label tables and the routed
    approval-step replies of unit_tests/ac_driven_dev/test_design_stage/_approval_step_support.py). The
    no-answer failure is reached with the forced-null-gate technique of test_acd_2100c_5.py: a temp copy
    whose resolveGate() returns null for "final-gate" only, every other line real.
RED STATE: the no-answer message says "The final gate (IT PO v3 review)", the cancel label is
    "final gate (IT-PO)", and the final commit failure is formatted with "it-po".
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

_STAGE_DIR = Path(__file__).resolve().parents[1] / "ac_driven_dev" / "test_design_stage"
sys.path.insert(0, str(_STAGE_DIR))

from _approval_step_support import (  # noqa: E402
    BATCH, calls, gate_record, names, prepass_for, resume, route_approval_step, run, step_replies, table,
)
from _design_stage_support import PLAN_FEATURE_JS, sequenced  # noqa: E402
from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402

_TEST_DESIGN = re.compile(r"test[- ]design", re.IGNORECASE)
_RESOLVE_GATE_SIGNATURE = "async function resolveGate(gateId, liveGateFn, args, context, descriptor, runId) {"
_HOOK_FAILURE = {
    "status": "error", "message": "pre-commit hook rejected staged files", "hook_name": "check-ac-schema",
    "failing_files": ["docs/acceptance-criteria/x/ACD-9990a-1.yaml"], "is_conflict": False,
}
_WT = "/tmp/harness-default-ac-worktree"
_STORE = f"{_WT}/docs/acceptance-criteria"


def _cancel_text(agent: str, draft: str) -> str:
    """buildCancelMessage's exact text for a mid-gate cancel with one uncommitted draft (no prior commits)."""
    return (
        f"Pipeline cancelled at gate after {agent}.\n\n"
        f"Uncommitted draft AC files from the cancelled stage ({draft}):\n"
        f"  {_STORE}/{draft}.yaml\n"
        f"You can inspect these files, manually commit them with `git -C \"{_WT}\" add` + `git -C \"{_WT}\" commit`,"
        f"or discard tracked files with `git -C \"{_WT}\" checkout -- {_STORE}/` and delete any untracked new files "
        f"explicitly (e.g. `rm {_STORE}/<AC_ID>.yaml`). Note: `git checkout --` alone will NOT remove untracked "
        "files — both steps are required if a prior session created new AC files that were never staged."
    )


_ITPO_COMMIT_FAILURE = (
    "Commit of it-po AC output failed. Hook \"check-ac-schema\" rejected the staged files.\n"
    "  Conflicting/failing files:\n    - docs/acceptance-criteria/x/ACD-9990a-1.yaml\n"
    "Fix the validation errors listed above, then re-run /plan-feature. "
    "All AC files from this stage remain on disk as uncommitted changes so you can inspect and correct them."
)


@pytest.fixture
def prepass(tmp_path):
    return prepass_for(tmp_path, BATCH)


def _forced_null_final_gate(tmp_path: Path) -> Path:
    source = PLAN_FEATURE_JS.read_text(encoding="utf-8")
    assert _RESOLVE_GATE_SIGNATURE in source, "resolveGate()'s signature changed; update _RESOLVE_GATE_SIGNATURE"
    patched = source.replace(
        _RESOLVE_GATE_SIGNATURE,
        _RESOLVE_GATE_SIGNATURE + '\n  if (gateId === "final-gate") { return null; } // TEST-ONLY (ACD-300c-5)', 1,
    )
    target = tmp_path / "acd_300c_5_forced_null_final_gate.js"
    target.write_text(patched, encoding="utf-8")
    return target


def _message(result) -> str:
    return str((result.result or {}).get("message", ""))


def test_final_gate_heading_names_the_test_design_stage(tmp_path, prepass):
    # covers: ACD-300c-5
    # angle: reachability
    """Technical route to the final-gate pause: the persisted question names the test-design stage and not
    IT PO v3; with the gate yielding no answer, the gate-failure message names the test-design stage and
    not IT PO v3."""
    paused = run(table(prepass, BATCH))
    question = str(((gate_record(paused) or {}).get("question") or {}).get("prompt", ""))
    assert _TEST_DESIGN.search(question) and "IT PO v3" not in question, question[:600]

    forced = run_workflow_under_e2(
        _forced_null_final_gate(tmp_path), label_responses=table(prepass, BATCH), timeout=90,
        # The temp copy is not named plan-feature.js, so the harness gives it no pre-flight default (test_acd_2100c_5 _PERMITTED).
        args={"run_id": "acd-300c-5", "workspace_setup_permission": {"permits": True}},
    )
    assert not forced.error, forced.error
    assert (forced.result or {}).get("status") == "undetermined", forced.result
    message = _message(forced)
    assert _TEST_DESIGN.search(message) and "IT PO v3" not in message, message[:600]


def test_final_gate_cancel_names_the_test_design_gate(prepass):
    # covers: ACD-300c-5
    # angle: discrimination
    """Resumed with a person's cancel at final-gate: the message contains "final gate (test design)" and
    contains neither "IT-PO" nor "IT PO v3".

    Wrong versions caught: the cancel label stays "final gate (IT-PO)"; only the label changes while the
    message still names IT PO v3 elsewhere.
    """
    result = run(table(prepass, BATCH), resume("cancel"))

    message = _message(result)
    assert (result.result or {}).get("status") == "cancelled", result.result
    assert "final gate (test design)" in message, message[:600]
    assert "IT-PO" not in message and "IT PO v3" not in message, message[:600]


def test_final_commit_failure_names_the_test_design_stage(tmp_path, monkeypatch, prepass):
    # covers: ACD-300c-5
    # angle: discrimination
    """Resumed with approve while the second commit-stage-output reply is a hook failure: the error message
    reads "Commit of test-design AC output failed" and does not contain "it-po".

    Wrong versions caught: formatCommitError at the final commit is still passed "it-po"; the stage name
    comes from the last authoring agent instead of the final stage.
    """
    sequenced(monkeypatch)
    route_approval_step(monkeypatch)
    dry, applied = step_replies(tmp_path)
    commits = {"__sequence__": [{"status": "ok", "message": "committed successfully"}, _HOOK_FAILURE]}

    result = run(table(prepass, BATCH, dry, applied, **{"commit-stage-output": commits}), resume("approve", "high"))

    assert len(calls(result, "commit-stage-output")) >= 2, names(result)
    message = _message(result)
    assert (result.result or {}).get("status") == "error", result.result
    assert "Commit of test-design AC output failed" in message, message[:600]
    assert "it-po" not in message, message[:600]


def _mid_gate_cancel(route: str, gate: str, author: str):
    ids = ["ACD-9990a-1"]
    record = {"exists": True, "stale": False, "record": {"gate_id": gate, "context": {"stage": gate[5:], "acs": ids}}}
    passed = {"output": json.dumps({"verdict": "passed", "records_checked": 1, "findings": [], "records_to_commit": []}), "exit_code": 0}
    labels = {
        "stage-0-triage": {"route": route, "existing_acs": [], "parent_l1_id": None, "rationale": "forced"},
        author: {"status": "ok", "acs_written": ids, "message": "done"},
        "peek-pause-record": record, "read-pause-record": record, "pause-persist-verify": record,
        "clear-pause-record": {"ok": True}, "clear-pause-record-verify": {"exists": False},
        "rule-check-po": passed, "rule-check-ba": passed,
    }
    answer = {"gate_id": gate, "type": "single_choice", "action": "cancel", "channel": "person"}
    result = run_workflow_under_e2(PLAN_FEATURE_JS, label_responses=labels, args={"run_id": "acd-300c-5", "resume_answer": answer}, timeout=90)
    assert not result.error, result.error
    return result


def test_other_gate_messages_are_unchanged(prepass):
    # covers: ACD-300c-5
    # angle: discrimination
    """Pins the other gates character for character: a cancel at gate-po and at gate-ba gives "Pipeline
    cancelled at gate after product-owner" / "... business-analyst" (the whole message), and an itpo-stage
    commit failure still reads "Commit of it-po AC output failed" (the whole message).

    Wrong versions caught: buildCancelMessage or formatCommitError changed globally, so every gate names
    test design; the itpo stage's own commit failure relabelled test-design.
    """
    po = _mid_gate_cancel("strategic", "gate-po", "stage-po-author")
    assert _message(po) == _cancel_text("product-owner", "ACD-9990a-1"), _message(po)

    ba = _mid_gate_cancel("behavioral", "gate-ba", "stage-ba-author")
    assert _message(ba) == _cancel_text("business-analyst", "ACD-9990a-1"), _message(ba)

    itpo = run(table(prepass, BATCH, **{"commit-stage-output": _HOOK_FAILURE}))
    assert len(calls(itpo, "commit-stage-output")) == 1, names(itpo)
    assert _message(itpo) == _ITPO_COMMIT_FAILURE, _message(itpo)
