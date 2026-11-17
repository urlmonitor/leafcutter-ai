"""
MODULE: unit_tests/workflows/_acd_300g_support.py
GOAL: Shared gate-resume runs and isolated-function drivers for the ACD-300g-1-i and ACD-300g-4 tests (the
    commit-failure message and the cancel message of /plan-feature). Not collected: no tests here.
ARCHITECTURE: Built on _acd_300a_support.py. A gate run resumes the REAL plan-feature.js (run_workflow_under_e2)
    at one gate with a person's answer; the durable pause record names that gate and carries the stage's ids as
    its context (the shape of test_acd_300c_5.py::_mid_gate_cancel). formatCommitError and buildCancelMessage
    are run in isolation through run_isolated_e2 (unit_tests/_plan_feature_e2_runner.py), the helper the
    existing cancel-message tests use.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _acd_300a_support import RUN_ID, calls, committed_stages, fresh_table, names, run, terminal, triage  # noqa: E402
from _plan_feature_e2_runner import run_isolated_e2  # noqa: E402

__all__ = [
    "BA_IDS", "PO_IDS", "UNDO", "after_gate", "build_cancel_message", "calls", "commit_failure", "committed_stages",
    "format_commit_error", "gate_run", "names", "terminal",
]

PO_IDS = ["ACD-9301", "ACD-9302"]
BA_IDS = ["ACD-9401", "ACD-9402"]
_STAGE_OF_GATE = {"gate-po": "po", "gate-ba": "ba"}
# A dispatch that would discard or rewrite the drafts or the committed history.
UNDO = re.compile(r"git(?: -C \"[^\"]*\")? (?:restore|checkout|reset|revert)\b|(?:^|[\s;&|])rm\s", re.MULTILINE)


def commit_failure(hook_name: str | None = "check-ac-schema", conflict: bool = False) -> dict:
    """A commit-stage-output reply for a failed commit (the shapes the commit instructions return)."""
    if conflict:
        return {"status": "error", "message": "index conflict detected", "hook_name": None,
                "failing_files": ["docs/acceptance-criteria/x/ACD-9301.yaml"], "is_conflict": True}
    return {"status": "error", "message": "pre-commit hook rejected staged files", "hook_name": hook_name,
            "failing_files": ["docs/acceptance-criteria/x/ACD-9301.yaml"], "is_conflict": False}


def gate_run(route: str, gate: str, action: str, ids: list[str], **labels):
    """Resume `gate` with a person's `action`; the pause record's context carries the stage's `ids`."""
    record = {"exists": True, "stale": False, "record": {
        "run_id": RUN_ID, "gate_id": gate, "status": "paused_awaiting_input",
        "question": {"type": "single_choice", "gate_id": gate, "options": ["approve", "edit", "cancel"]},
        "context": {"stage": _STAGE_OF_GATE[gate], "acs": list(ids)},
    }}
    table = fresh_table(triage(route), **{
        "peek-pause-record": record, "read-pause-record": record, "pause-persist-verify": record,
        "branch-check": {"output": "ac-authoring/acd-300g", "exit_code": 0}, **labels,
    })
    answer = {"gate_id": gate, "type": "single_choice", "action": action, "channel": "person"}
    return run(table, {"resume_answer": answer})


def after_gate(result) -> list:
    """The dispatches made after the gate's answer was read."""
    answered = max(i for i, c in enumerate(result.agent_calls) if c.label in ("peek-pause-record", "read-pause-record"))
    return result.agent_calls[answered + 1:]


def _isolated(function: str, driver_call: str) -> str:
    return run_isolated_e2([function], "process.stdout.write(" + driver_call + ");", timeout=15)


def format_commit_error(outcome: dict, label: str = "it-po", stage: str = "itpo") -> str:
    """formatCommitError's text for a commit outcome (the real function, run in isolation)."""
    return _isolated("formatCommitError", f"formatCommitError({json.dumps(label)}, {json.dumps(stage)}, {json.dumps(outcome)}, [])")


def build_cancel_message(committed: list[str], drafts: list[str], where: str = "gate after product-owner",
                         store: str = "docs/acceptance-criteria", worktree: str | None = None,
                         paths: list[str] | None = None) -> str:
    """buildCancelMessage's text (the real function, run in isolation).

    `paths` is the rule check's records_to_commit list (repo-relative record paths). It is passed as a TRAILING
    POSITIONAL argument (the sixth); this is the one place that call shape lives.
    """
    args = ", ".join(json.dumps(a) for a in (committed, drafts, where, store, worktree, list(paths or [])))
    return _isolated("buildCancelMessage", f"buildCancelMessage({args})")
