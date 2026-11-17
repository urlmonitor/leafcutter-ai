"""
MODULE: unit_tests/workflows/_acd_300a_support.py
GOAL: Shared label tables, run helpers and template readers for the ACD-300a-1, -2 and -3 tests (the
    Haiku triage routes of /plan-feature). Not collected: no tests here.
ARCHITECTURE: Drives the REAL templates/workflows-js/plan-feature.js through run_workflow_under_e2.
    - Fresh runs script the triage reply, `pt-classify` (outcome none) and the first author stage only.
    - Crash-resume runs reuse the label table of
      unit_tests/ac_driven_dev/file_findings/_handback_support.py (design-prepass is the REAL
      design_prepass.py stdout; the hold report is the real `_approval_holds.build_report`), plus the
      commit scan and the resume log that make the product-owner / business-analyst stages "committed".
    - The gate payload is read from the pause record persisted by the `pause-persist` dispatch, because the
      headless gate never calls its live closure.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
for _extra in ("unit_tests", "unit_tests/ac_driven_dev/file_findings"):
    sys.path.insert(0, str(REPO_ROOT / _extra))

import _handback_support as hs  # noqa: E402
from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402

PLAN_FEATURE_JS = REPO_ROOT / "templates" / "workflows-js" / "plan-feature.js"
TRIAGE_TEMPLATE = REPO_ROOT / "templates" / "agents" / "ac-triage.md"
RUN_ID = "acd-300a-run"
COVERED_GATE = "covered-route-gate"
PARENT_L1 = "ACD-9100"
COVERING = ["ACD-9101", "ACD-9102"]
TITLES = {"ACD-9101": "Alpha widget export is validated", "ACD-9102": "Bravo report archive is purged"}
_BATCH_IDS = ["ACD-9301", "ACD-9302"]
_CLEAN_TREE = {"output": "", "exit_code": 0}


def triage(route: str, existing: list[str] | None = None, parent: str | None = None) -> dict:
    return {"route": route, "existing_acs": list(existing or []), "parent_l1_id": parent, "rationale": "scripted"}


def _written(ids: list[str] | None = None) -> dict:
    return {"status": "ok", "acs_written": list(ids or _BATCH_IDS), "message": "done"}


def fresh_table(route_reply: dict, **overrides) -> dict:
    """Labels a fresh run needs to reach its first author stage and pause at that stage's gate."""
    table = {
        "stage-0-triage": route_reply,
        "pt-classify": {"outcome": "none"},
        "scan-orphans-git-status": dict(_CLEAN_TREE),
        "stage-po-author": _written(), "stage-ba-author": _written(), "stage-itpo-author": _written(),
        "pause-persist-verify": {"exists": True, "stale": False, "record": {"run_id": RUN_ID}},
        "peek-pause-record": {"exists": False, "stale": False, "record": None},
        "read-pause-record": {"exists": False, "stale": False, "record": None},
        "clear-pause-record": {"ok": True}, "clear-pause-record-verify": {"exists": False, "stale": False, "record": None},
    }
    table.update(overrides)
    return table


def full_table(tmp_path: Path, route_reply: dict, **overrides) -> dict:
    """The _handback_support.py table (technical route to the final gate) with `route_reply` as the triage."""
    table = hs.labels(hs.prepass_reply(tmp_path), hs.holds_reply({}))
    table.update({"stage-0-triage": route_reply, "pt-classify": {"outcome": "none"},
                  "scan-orphans-git-status": dict(_CLEAN_TREE)})
    table.update(overrides)
    return table


def committed_stages(*stage_labels: str) -> dict:
    """`scan-committed-stages` and `resume-log` replies for the given commit labels (e.g. "PO", "BA")."""
    subjects = [f"a{i}b{i}c{i} plan-feature({label}): component" for i, label in enumerate(stage_labels)]
    bodies = [f"plan-feature({label}): component\n\nAC IDs: ACD-93{i:02d}\n" for i, label in enumerate(stage_labels, 1)]
    return {
        "scan-committed-stages": {"output": "\n".join(subjects) + "\n", "exit_code": 0},
        "resume-log": {"output": "\n".join(bodies), "exit_code": 0},
    }


def run(label_table: dict, args: dict | None = None, user_input: str = "build the widget export"):
    merged = {"run_id": RUN_ID, "userInput": user_input, **(args or {})}
    result = run_workflow_under_e2(PLAN_FEATURE_JS, label_responses=label_table, args=merged, timeout=90)
    assert not result.error, result.error
    return result


def names(result) -> list[str]:
    return [str(c.label) for c in result.agent_calls]


def calls(result, label: str) -> list:
    return [c for c in result.agent_calls if c.label == label]


def author_calls(result) -> list:
    return [c for c in result.agent_calls if re.fullmatch(r"stage-.+-author", str(c.label))]


def authoring_labels(result) -> list[str]:
    """Every dispatch that belongs to the authoring pipeline or the product-truth phase, in order."""
    pattern = re.compile(r"stage-.+-author|pt-classify|pt-.+-author|design-prepass")
    return [str(c.label) for c in result.agent_calls if pattern.fullmatch(str(c.label))]


def terminal(result) -> dict:
    assert isinstance(result.result, dict), f"no terminal payload: {result.result!r} stderr={result.stderr!r}"
    return result.result


def pause_records(result) -> list[dict]:
    """Every pause record persisted by a `pause-persist` dispatch, in order."""
    records = []
    for call in calls(result, "pause-persist"):
        match = re.search(r"--record '(\{.*\})'", call.prompt, re.DOTALL)
        assert match, f"pause-persist prompt carries no record: {call.prompt[:400]}"
        records.append(json.loads(match.group(1)))
    return records


def covered_pause_record(result) -> dict:
    for record in pause_records(result):
        if record.get("gate_id") == COVERED_GATE:
            return record
    raise AssertionError(f"no pause record names {COVERED_GATE}; dispatched: {names(result)}")


def covered_resume(action: str, existing: list[str] | None = None) -> tuple[dict, dict]:
    """(pause-record reply, args) for a person's answer to covered-route-gate (shape of test_acd_2100c_3_iv)."""
    record = {"exists": True, "stale": False, "record": {
        "run_id": RUN_ID, "gate_id": COVERED_GATE, "status": "paused_awaiting_input",
        "question": {"type": "single_choice", "gate_id": COVERED_GATE, "options": ["cancel", "amend", "force"]},
        "context": {"route": "covered", "existing_acs": list(existing or COVERING)},
    }}
    answer = {"gate_id": COVERED_GATE, "type": "single_choice", "action": action, "channel": "person"}
    return record, {"resume_answer": answer}


def template_parts() -> tuple[dict, str]:
    """(frontmatter, body) of the real templates/agents/ac-triage.md."""
    text = TRIAGE_TEMPLATE.read_text(encoding="utf-8")
    _, front, body = text.split("---", 2)
    return yaml.safe_load(front), body


def section(body: str, start: str, end: str | None = None) -> str:
    """The text from the first line containing `start` up to the line containing `end` (or the next heading)."""
    begin = body.index(start)
    stop_marks = [body.find(end, begin + len(start))] if end else []
    stop_marks.append(body.find("\n## ", begin + len(start)))
    stops = [m for m in stop_marks if m != -1]
    return body[begin:min(stops)] if stops else body[begin:]


def position_of(result, label: str) -> int:
    """Index of the first dispatch of `label`; a missing dispatch fails with the real sequence."""
    seen = [i for i, c in enumerate(result.agent_calls) if c.label == label]
    assert seen, f"no dispatch of {label!r}; dispatched: {names(result)}"
    return seen[0]
