"""
MODULE: unit_tests/ac_driven_dev/test_design_stage/_approval_step_support.py
GOAL: Label tables, real approval-step replies and dispatch readers for the /plan-feature final-gate
    approval tests (ACD-300c-3, ACD-300c-4, -4-i, -4-ii, -4-iii, ACD-300c-5). Not collected: no tests here.
BUSINESS CONTEXT: ACD-300c-4: on "approve" the workflow takes the hold report from the store's one
    approval step (approve_acs.py --dry-run --json) and runs that same step, as a deterministic dispatch,
    with exactly the ids the report releases and the chosen priority. No agent edits readiness/priority.
ARCHITECTURE: Drives the REAL templates/workflows-js/plan-feature.js through run_workflow_under_e2 on the
    "technical" route (itpo, then the test-design stage that owns the final gate), resumed at final-gate.
    - The approval step's dispatch label is the coder's choice, so its replies are routed by the COMMAND
      the prompt carries, not by label: `route_approval_step` patches the harness agent mock in memory
      (monkeypatch; the harness file is not edited) so a prompt that runs approve_acs.py is answered with
      `DRY_KEY`'s reply when it carries --dry-run and with `APPLY_KEY`'s reply otherwise.
    - Those replies are the REAL approve_acs.py stdout/exit code on a tmp store
      (unit_tests/ac_store/_acd_300c_4_fixtures.py), never typed. While the id-list mode does not exist
      the real reply is a usage error (exit 2), which a correct workflow must never treat as an approval.
    - `approval-holds` (approval_hold_report.py) is answered with a report that DISAGREES with the step
      (it holds nothing), so a workflow that takes its hold list from it approves the held id.
    - Every label the run dispatches is supplied (incl. `rule-check-itpo-handback`), so no run depends on
      a harness default that does not exist.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
for _extra in ("unit_tests", "unit_tests/ac_store", "scripts/ac_store", "unit_tests/ac_driven_dev/test_design_stage"):
    sys.path.insert(0, str(REPO_ROOT / _extra))

import _workflow_engine_harness as harness  # noqa: E402
from _acd_2500d_5_i_fixtures import run_prepass  # noqa: E402
from _acd_300c_4_fixtures import BATCH, HELD, RELEASED, UNDECIDED, batch_store, l1_store, run_ids  # noqa: E402
from _approval_holds import build_report  # noqa: E402
from _design_stage_support import GATE, RUN_ID, calls, check_reply, gate_record, names, position, run  # noqa: E402
from _rule_check_fixtures import make_store, valid_record  # noqa: E402

DRY_KEY = "__approve_acs_dry_run__"
APPLY_KEY = "__approve_acs_apply__"
L1_BATCH = ["ACD-9990a", "ACD-9990a-1", "ACD-9990a-2"]
STEP_SCRIPT = "approve_acs.py"

__all__ = [
    "APPLY_KEY", "BATCH", "DRY_KEY", "GATE", "HELD", "L1_BATCH", "RELEASED", "UNDECIDED", "apply_calls",
    "approve_calls", "calls", "dry_calls", "gate_record", "ids_of", "names", "pause", "position",
    "prepass_for", "priority_of", "readiness_editing_prompts", "resume", "route_approval_step", "run",
    "step_replies", "table",
]


def route_approval_step(monkeypatch) -> None:
    """Answer approve_acs.py dispatches by command (dry run / apply), whatever their label."""
    needle = "__capturedCalls__.push({\n"
    assert needle in harness._BOOTSTRAP_SOURCE_JS, "harness agent mock changed shape"
    routed = (
        "if (typeof promptOrOpts === 'string' && promptOrOpts.indexOf('" + STEP_SCRIPT + "') >= 0) {"
        " var _key = promptOrOpts.indexOf('--dry-run') >= 0 ? '" + DRY_KEY + "' : '" + APPLY_KEY + "';"
        " if (Object.prototype.hasOwnProperty.call(__labelResponses__, _key)) { response = __labelResponses__[_key]; _unscripted = false; } }\n  "
    )
    monkeypatch.setattr(harness, "_BOOTSTRAP_SOURCE_JS", harness._BOOTSTRAP_SOURCE_JS.replace(needle, routed + needle))


def _reply(done) -> dict:
    return {"output": done.stdout, "exit_code": done.exit_code, "stderr": done.stderr}


def step_replies(tmp_path: Path, *, batch=None, released=None, l1: bool = False, already_applied: bool = False):
    """The REAL approve_acs.py replies on a tmp store: (dry-run on the batch, apply on the released ids).

    `already_applied` runs the apply once before (the second application of ACD-300c-4-i).
    """
    store = (l1_store if l1 else batch_store)(tmp_path / "approval-store")
    batch = list(batch or (L1_BATCH if l1 else BATCH))
    released = list(released or (L1_BATCH if l1 else RELEASED))
    if already_applied:
        run_ids(store, released, priority="high")
    dry = run_ids(store, batch, "--dry-run", priority="high")
    applied = run_ids(store, released, priority="high")
    return _reply(dry), _reply(applied)


def prepass_for(tmp_path: Path, ids: list[str]) -> dict:
    """The REAL design_prepass.py stdout for `ids`, as the agent relay returns it."""
    store = make_store(tmp_path / "prepass-store", [valid_record(rid) for rid in ids])
    done = run_prepass(store, ids)
    assert done.exit_code == 0, done.stderr
    return {"output": done.stdout.decode("utf-8"), "exit_code": 0, "stderr": ""}


def pause(ids: list[str]) -> dict:
    """The durable final-gate pause record of a run whose batch is `ids`."""
    return {"exists": True, "stale": False, "record": {"gate_id": GATE, "context": {"stage": "final", "acs": ids, "all_acs": ids}}}


def table(prepass: dict, ids: list[str], dry: dict | None = None, apply: dict | None = None, **overrides) -> dict:
    """Every label the technical route dispatches for batch `ids`, plus the routed approval-step replies."""
    designer = {"status": "ok", "anomalies": [],
                "records": [{"id": rid, "test_design": "written", "file_findings": "none", "reason": None} for rid in ids]}
    labels: dict[str, dict] = {
        "stage-0-triage": {"route": "technical", "existing_acs": [], "parent_l1_id": None, "rationale": "forced"},
        "stage-itpo-author": {"status": "ok", "acs_written": list(ids), "message": "done"},
        "branch-check": {"output": "ac-authoring/final-gate-approval", "exit_code": 0},
        "commit-stage-output": {"status": "committed", "commit_answer": {"status": "committed", "reason_code": None, "reason": None, "sha": "abc1234"}},
        "peek-pause-record": pause(ids), "read-pause-record": pause(ids), "pause-persist-verify": pause(ids),
        "clear-pause-record": {"ok": True}, "clear-pause-record-verify": {"exists": False},
        "design-prepass": prepass,
        "stage-test-design-author": designer,
        "rule-check-test-design": check_reply(),
        "rule-check-itpo-handback": check_reply(),
        # The old hold report DISAGREES with the step: it holds nothing.
        "approval-holds": {"output": json.dumps(build_report(list(ids), [])), "exit_code": 0, "stderr": ""},
        "deliver-authoring-branch": {"status": "ok", "message": "PR opened", "pr_url": "https://example.invalid/pr/1"},
    }
    if dry is not None:
        labels[DRY_KEY] = dry
    if apply is not None:
        labels[APPLY_KEY] = apply
    labels.update(overrides)
    return labels


def resume(action: str = "approve", priority: str = "high", feedback: str | None = None) -> dict:
    """A person's answer to the final gate: approve carries a priority; the others are single choices."""
    if action == "approve":
        answer = {"gate_id": GATE, "type": "priority_choice", "action": "approve", "priority": priority, "channel": "person"}
    else:
        answer = {"gate_id": GATE, "type": "single_choice", "action": action, "channel": "person"}
        if feedback is not None:
            answer["feedback"] = feedback
    return {"run_id": RUN_ID, "resume_answer": answer}


def approve_calls(result) -> list:
    return [c for c in result.agent_calls if isinstance(c.prompt, str) and STEP_SCRIPT in c.prompt]


def dry_calls(result) -> list:
    return [c for c in approve_calls(result) if "--dry-run" in c.prompt]


def apply_calls(result) -> list:
    return [c for c in approve_calls(result) if "--dry-run" not in c.prompt]


def ids_of(call) -> list[str]:
    """The --ids value of an approval-step command, as a list (order kept)."""
    match = re.search(r"--ids[ =]['\"]?([A-Za-z0-9._,-]+)", call.prompt)
    assert match, f"the approval-step command carries no --ids: {call.prompt[:600]}"
    return match.group(1).split(",")


def priority_of(call) -> str | None:
    match = re.search(r"--priority[ =]['\"]?([a-z]+)", call.prompt)
    return match.group(1) if match else None


_EDIT_FIELD = re.compile(r"\b(set|sets|setting|update|updates|write|writes|edit|edits)\b[^\n]{0,80}\b(readiness|priority)\b", re.IGNORECASE)


def readiness_editing_prompts(result) -> list[str]:
    """Labels of agent prompts (other than the approval-step command) that ask to set readiness/priority."""
    return [
        str(c.label) for c in result.agent_calls
        if isinstance(c.prompt, str) and STEP_SCRIPT not in c.prompt and _EDIT_FIELD.search(c.prompt)
    ]
