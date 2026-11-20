"""
MODULE: unit_tests/ac_driven_dev/test_design_stage/_design_stage_support.py
GOAL: Shared label replies, run helpers and gate-record readers for the ACD-2500c-2 workflow
    tests (test_acd_2500c_2.py and test_acd_2500c_2_failures.py). Not collected: no tests here.
BUSINESS CONTEXT: ACD-2500c-2 (G4 architect note, section 2): /plan-feature gains a
    `test-design` pipeline entry after an auto-approved `itpo` stage; the workflow runs the
    pre-pass script, the test-designer agent, the rule check and the approval-hold report, and
    the final gate offers only the records with no hold.
ARCHITECTURE: Drives the REAL templates/workflows-js/plan-feature.js through
    run_workflow_under_e2 on the "technical" route (pipeline: itpo, then test-design). The
    harness file is not edited and the existing default replies are not extended (that is the
    coder's work): every label the new stage dispatches is supplied here, so a run never depends
    on a default that does not exist yet.
    - The pre-pass reply is the REAL design_prepass.py stdout on a tmp store (never typed).
    - The approval-hold reply is built with the real `_approval_holds.build_report`.
    - The gate payload is the pause record the workflow persists (`pause-persist` prompt), because
      the headless gate never invokes its live-gate closure.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
for _extra in ("unit_tests", "unit_tests/ac_store", "scripts/ac_store"):
    sys.path.insert(0, str(REPO_ROOT / _extra))

import _workflow_engine_harness as harness  # noqa: E402
from _acd_2500d_5_i_fixtures import run_prepass  # noqa: E402
from _approval_holds import build_report  # noqa: E402
from _plan_feature_harness_defaults import approval_apply_reply  # noqa: E402
from _rule_check_fixtures import make_store, valid_record  # noqa: E402
from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402

PLAN_FEATURE_JS = REPO_ROOT / "templates" / "workflows-js" / "plan-feature.js"
IDS = ["TDG-1", "TDG-2", "TDG-3", "TDG-4"]
PENDING = "test design pending"
GATE = "final-gate"
RUN_ID = "test-design-run"
PAUSE = {
    "exists": True, "stale": False,
    "record": {"gate_id": GATE, "context": {"stage": "final", "acs": IDS, "all_acs": IDS}},
}
NO_RECORD = {"exists": False, "stale": False, "record": None}


def prepass_reply(tmp_path: Path) -> dict:
    """The REAL pre-pass stdout for the 4 leaf requirements, as the agent relay would return it."""
    store = make_store(tmp_path, [valid_record(rid) for rid in IDS])
    done = run_prepass(store, IDS)
    assert done.exit_code == 0, done.stderr
    return {"output": done.stdout.decode("utf-8"), "exit_code": 0, "stderr": ""}


def prepass_paths(reply: dict) -> list[str]:
    """Every declared file path in the (real) pre-pass report: distinct per record."""
    report = json.loads(reply["output"])
    return [f["path"] for record in report["records"] for f in record["declared_files"]]


def empty_prepass_reply() -> dict:
    """A pre-pass that ran and found no record in scope."""
    return {"output": json.dumps({"batch": [], "records": []}), "exit_code": 0, "stderr": ""}


def holds_reply(held: dict[str, str] | None = None, exit_code: int = 0) -> dict:
    """The approval-hold report (real shape): `held` is {id: reason}; the rest are approvable."""
    held = held or {}
    approved = [rid for rid in IDS if rid not in held]
    entries = [{"id": rid, "file": f"docs/acceptance-criteria/x/{rid}.yaml", "reason": why} for rid, why in held.items()]
    return {"output": json.dumps(build_report(approved, entries)), "exit_code": exit_code, "stderr": ""}


def designer_reply(pending: tuple[str, ...] = ()) -> dict:
    """The designer's machine-parsed JSON: written for every id except `pending` ones."""
    records = [
        {"id": rid, "test_design": "pending" if rid in pending else "written", "file_findings": "none",
         "reason": "declared file could not be opened" if rid in pending else None}
        for rid in IDS
    ]
    return {"status": "ok", "records": records, "anomalies": []}


def check_reply(passed: bool = True) -> dict:
    """A rule-check reply shaped like requirement_rule_check.py stdout, plus its exit code."""
    verdict = "passed" if passed else "failed"
    findings = [] if passed else [{
        "file": "docs/acceptance-criteria/x/TDG-1.yaml", "record_id": "TDG-1",
        "rule_family": "test design grounding", "disposition": "needs a decision",
        "message": "TDG-1 names a code file that does not exist", "line": None, "detail": None,
    }]
    report = {"verdict": verdict, "location": "docs/acceptance-criteria", "records_checked": 4,
              "findings": findings, "records_to_commit": []}
    return {"output": json.dumps(report), "exit_code": 0 if passed else 1, "stderr": ""}


def labels(prepass: dict, holds: dict, designer=None, check=None, **overrides) -> dict:
    """Every label the technical route dispatches, with the new stage's replies supplied."""
    table: dict[str, dict] = {
        "stage-0-triage": {"route": "technical", "existing_acs": [], "parent_l1_id": None, "rationale": "forced"},
        "stage-itpo-author": {"status": "ok", "acs_written": IDS, "message": "done"},
        "branch-check": {"output": "ac-authoring/test-design", "exit_code": 0},
        "commit-stage-output": {"status": "committed", "commit_answer": {"status": "committed", "reason_code": None, "reason": None, "sha": "abc1234"}},
        "peek-pause-record": PAUSE, "read-pause-record": PAUSE, "pause-persist-verify": PAUSE,
        "clear-pause-record": {"ok": True}, "clear-pause-record-verify": {"exists": False},
        "design-prepass": prepass,
        "stage-test-design-author": designer if designer is not None else designer_reply(),
        "rule-check-test-design": check if check is not None else check_reply(),
        "approval-holds": holds,  # the pre-gate report AND the approval step's dry run (ACD-300c-4)
        "approval-apply": approval_apply_reply(holds),  # applies what the dry run released
    }
    table.update(overrides)
    return table


def resume_args(action: str = "approve") -> dict:
    """A person's answer to the final gate."""
    answer = {"gate_id": GATE, "type": "priority_choice", "action": action, "priority": "high", "channel": "person"}
    return {"run_id": RUN_ID, "resume_answer": answer}


def run(label_table: dict, args: dict | None = None):
    """Run plan-feature.js under the harness; a harness failure fails the test loudly."""
    result = run_workflow_under_e2(PLAN_FEATURE_JS, label_responses=label_table, args=args or {"run_id": RUN_ID}, timeout=90)
    assert not result.error, result.error
    return result


def sequenced(monkeypatch) -> None:
    """Make the harness agent mock serve `{"__sequence__": [...]}` replies in order (last repeats)."""
    needle = "response = __labelResponses__[label];"
    assert needle in harness._BOOTSTRAP_SOURCE_JS, "harness agent mock changed shape"
    patched = harness._BOOTSTRAP_SOURCE_JS.replace(
        needle,
        needle + " if (response && typeof response === 'object' && Array.isArray(response.__sequence__))"
        " { var _q = response.__sequence__; response = _q.length > 1 ? _q.shift() : _q[0]; }",
    )
    monkeypatch.setattr(harness, "_BOOTSTRAP_SOURCE_JS", patched)


def names(result) -> list[str]:
    return [c.label for c in result.agent_calls]


def calls(result, label: str) -> list:
    return [c for c in result.agent_calls if c.label == label]


def position(result, label: str, nth: int = 0) -> int:
    """Index of the nth dispatch of `label`; a missing dispatch fails with the real sequence."""
    seen = [i for i, c in enumerate(result.agent_calls) if c.label == label]
    assert len(seen) > nth, f"no dispatch #{nth} of {label!r}; dispatched: {names(result)}"
    return seen[nth]


def gate_record(result) -> dict | None:
    """The pause record persisted for the final gate (the gate payload), or None when none was."""
    for call in calls(result, "pause-persist"):
        if GATE not in call.prompt:
            continue
        match = re.search(r"--record '(\{.*\})'", call.prompt, re.DOTALL)
        assert match, f"pause-persist prompt carries no record: {call.prompt[:400]}"
        return json.loads(match.group(1))
    return None


def gate_context(result) -> dict:
    """The final gate's persisted context; fails when the run never reached the final gate."""
    record = gate_record(result)
    assert record is not None, f"the run never paused at {GATE}; dispatched: {names(result)}"
    return record.get("context") or {}
