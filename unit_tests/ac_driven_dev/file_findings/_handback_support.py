"""
MODULE: unit_tests/ac_driven_dev/file_findings/_handback_support.py
GOAL: Label replies and run helpers for the ticket 39 workflow tests (the it-po hand-back of undecided
    file findings in plan-feature.js). Not collected: no tests here.
BUSINESS CONTEXT: ACD-2500d-3-i (G4 architect note, section 2.5): after a passing `rule-check-test-design`,
    on the live path, the workflow reads the hold report; for the requirements held with "file finding
    undecided" it dispatches `it-po` (label `it-po-findings-round-N`, at most 2 rounds), adds the ids
    the planner returns to the run, re-runs the check and the holds, and shows what is still undecided
    at the final gate as held.
ARCHITECTURE: The REAL plan-feature.js under run_workflow_under_e2 on the "technical" route (pipeline:
    itpo, then the test-design stage of ticket 31). Every label that stage dispatches is supplied here
    (ticket 31 owns the harness defaults, so no run depends on a default that may not exist yet):
    - the pre-pass reply is the REAL design_prepass.py stdout on a tmp store;
    - the hold report is built with the real `_approval_holds.build_report`;
    - the hold report must change once the planner has run, so `by_round` patches the harness agent mock
      (in memory, via monkeypatch) to serve `{"__by_round__": [r0, r1, ...]}`: reply i is served after i
      `it-po-findings-round-*` dispatches (the last repeats). The harness file itself is not edited.
    - the gate payload is the pause record persisted at final-gate (`pause-persist` prompt).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
for _extra in ("unit_tests", "unit_tests/ac_store", "scripts/ac_store"):
    sys.path.insert(0, str(REPO_ROOT / _extra))

import _workflow_engine_harness as harness  # noqa: E402
from _acd_2500d_5_i_fixtures import run_prepass  # noqa: E402
from _approval_holds import build_report  # noqa: E402
from _rule_check_fixtures import make_store, valid_record  # noqa: E402
from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402

PLAN_FEATURE_JS = REPO_ROOT / "templates" / "workflows-js" / "plan-feature.js"
R, S, T = "FFH-1", "FFH-2", "FFH-3"  # R: undecided finding, S: decided, T: test design pending
IDS = [R, S, T]
UNDECIDED = "file finding undecided"
PENDING = "test design pending"
GATE = "final-gate"
RUN_ID = "file-findings-handback-run"
PAUSE = {
    "exists": True, "stale": False,
    "record": {"gate_id": GATE, "context": {"stage": "final", "acs": IDS, "all_acs": IDS}},
}
NO_RECORD = {"exists": False, "stale": False, "record": None}


def prepass_reply(tmp_path: Path) -> dict:
    """The REAL pre-pass stdout for the three requirements, as the agent relay would return it."""
    store = make_store(tmp_path, [valid_record(rid) for rid in IDS])
    done = run_prepass(store, IDS)
    assert done.exit_code == 0, done.stderr
    return {"output": done.stdout.decode("utf-8"), "exit_code": 0, "stderr": ""}


def holds_reply(held: dict[str, str], ids: list[str] | None = None) -> dict:
    """The approval-hold report (real shape): `held` is {id: reason}; the rest are approvable."""
    every = ids or IDS
    entries = [{"id": rid, "file": f"docs/acceptance-criteria/x/{rid}.yaml", "reason": why} for rid, why in held.items()]
    report = build_report([rid for rid in every if rid not in held], entries)
    return {"output": json.dumps(report), "exit_code": 0, "stderr": ""}


def check_reply() -> dict:
    """A passed rule-check reply shaped like requirement_rule_check.py stdout."""
    report = {"verdict": "passed", "location": "docs/acceptance-criteria", "records_checked": 3,
              "findings": [], "records_to_commit": []}
    return {"output": json.dumps(report), "exit_code": 0, "stderr": ""}


def designer_reply() -> dict:
    """The designer's machine-parsed JSON: every record written, findings written."""
    records = [{"id": rid, "test_design": "written", "file_findings": "written", "reason": None} for rid in IDS]
    return {"status": "ok", "records": records, "anomalies": []}


def planner_reply(*ids: str) -> dict:
    """The it-po reply to a hand-back round."""
    return {"status": "ok", "acs_written": list(ids or (R,)), "message": "decisions recorded"}


def labels(prepass: dict, holds: dict, **overrides) -> dict:
    """Every label the technical route dispatches, with the test-design stage's replies supplied."""
    table = {
        "stage-0-triage": {"route": "technical", "existing_acs": [], "parent_l1_id": None, "rationale": "forced"},
        "stage-itpo-author": {"status": "ok", "acs_written": IDS, "message": "done"},
        "branch-check": {"output": "ac-authoring/file-findings", "exit_code": 0},
        "commit-stage-output": {"status": "ok", "message": "committed successfully"},
        "peek-pause-record": NO_RECORD, "read-pause-record": NO_RECORD, "pause-persist-verify": PAUSE,
        "clear-pause-record": {"ok": True}, "clear-pause-record-verify": {"exists": False},
        "design-prepass": prepass,
        "stage-test-design-author": designer_reply(),
        "rule-check-test-design": check_reply(),
        "approval-holds": holds,
        "rule-check-itpo-handback": check_reply(),  # each hand-back round is checked as itpo-handback (ACD-2500a-2-ix)
        "it-po-findings-round-1": planner_reply(),
        "it-po-findings-round-2": planner_reply(),
        "it-po-findings-round-3": planner_reply(),
    }
    table.update(overrides)
    return table


def by_round(monkeypatch) -> None:
    """Serve `{"__by_round__": [...]}` replies: reply i after i it-po hand-back dispatches (last repeats)."""
    needle = "response = __labelResponses__[label];"
    assert needle in harness._BOOTSTRAP_SOURCE_JS, "harness agent mock changed shape"
    served = (
        " if (response && typeof response === 'object' && Array.isArray(response.__by_round__)) {"
        " var _n = __capturedCalls__.filter(function (c) { return c.opts && typeof c.opts.label === 'string'"
        " && c.opts.label.indexOf('it-po-findings-round-') === 0; }).length;"
        " response = response.__by_round__[Math.min(_n, response.__by_round__.length - 1)]; }"
    )
    monkeypatch.setattr(harness, "_BOOTSTRAP_SOURCE_JS", harness._BOOTSTRAP_SOURCE_JS.replace(needle, needle + served))


def run(label_table: dict):
    """Run plan-feature.js under the harness; a harness failure fails the test loudly."""
    result = run_workflow_under_e2(PLAN_FEATURE_JS, label_responses=label_table, args={"run_id": RUN_ID}, timeout=90)
    assert not result.error, result.error
    return result


def names(result) -> list[str]:
    return [c.label for c in result.agent_calls]


def calls(result, label: str) -> list:
    return [c for c in result.agent_calls if c.label == label]


def position(result, label: str, nth: int = 0) -> int:
    """Index of the nth dispatch of `label`; a missing dispatch fails with the real sequence."""
    seen = [i for i, c in enumerate(result.agent_calls) if c.label == label]
    assert len(seen) > nth, f"no dispatch #{nth} of {label!r}; dispatched: {names(result)}"
    return seen[nth]


def gate_context(result) -> dict:
    """The final gate's persisted context; fails when the run never paused at the final gate."""
    for call in calls(result, "pause-persist"):
        if GATE not in call.prompt:
            continue
        match = re.search(r"--record '(\{.*\})'", call.prompt, re.DOTALL)
        assert match, f"pause-persist prompt carries no record: {call.prompt[:400]}"
        return json.loads(match.group(1)).get("context") or {}
    pytest.fail(f"the run never paused at {GATE}; dispatched: {names(result)}")
