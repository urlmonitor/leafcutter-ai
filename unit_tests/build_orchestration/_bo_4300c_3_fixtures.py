"""
MODULE: unit_tests/build_orchestration/_bo_4300c_3_fixtures.py
AC: BO-4300c-3 / BO-4300c-3-i / BO-4300c-3-ii / BO-4300a-1-ia (ticket 10,
    "Workflow runtime: one WORKSPACE-ANSWER block, one shell-runner agent,
    refusals end the run").
GOAL: Shared, test-only helpers for the harness-driven tests of the six
    workspace-consuming workflows. NOT a test file (leading underscore).

CONTRACT THE TESTS PIN (coder: these are the spec, not guesses)
- The WORKSPACE-ANSWER dispatch helper issues the workspace step as ONE
  agent() dispatch labelled WORKSPACE_LABEL ("workspace-ensure") to
  agentType "shell-runner" (permits_shell: true), whose prompt carries the
  exact absolute maker command (it names "worktree.py" and "ensure") plus an
  instruction to run it unchanged / relay stdout verbatim.
- shell-runner's reply (ADR-070 1.4/1.5) is `{command, exit_status, stdout,
  stderr}` (stdout holds the maker's single JSON answer as a STRING) or a
  decline `{declined: true, agent, reason}` with no `exit_status`.
- Acceptance predicate: the maker answer parses as ONE JSON object AND
  status == "ok" AND workspace_path is a non-empty string; anything else ends
  the run with terminal `status: "error"` quoting (<= 2 KB) what was received.
- A workflow that is handed `args.workspace` (the maker's answer object)
  dispatches NO workspace step.
- The consuming set is DERIVED (reads args.workspace, or records a
  WORKSPACE_LABEL dispatch in its harness run), never listed; REQUIRED_CONSUMERS
  is only the floor the AC itself names (long-running build, single-ticket
  build, quick fix, requirements authoring, fast lane, finalize), so an empty
  derived set can never pass vacuously.

Deployed copies are produced by the real build phase (build_workflow_scripts)
into a temporary target, never read from the source tree or the gitignored
.claude/workflows.
"""
from __future__ import annotations

import atexit
import json
import os
import re
import shutil
import sys
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
TEMPLATES_DIR = REPO_ROOT / "templates"
SHARED_SOURCE = TEMPLATES_DIR / "workflows-js" / "_shared" / "workspace-answer.js"
for _p in (str(REPO_ROOT / "unit_tests"), str(REPO_ROOT), str(SCRIPTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _workflow_engine_harness import (  # noqa: E402
    HarnessResult,
    _default_args_for_script,
    _default_label_responses_for_script,
    run_workflow_under_e2,
)

WORKSPACE_LABEL = "workspace-ensure"
START_MARKER = "// WORKSPACE-ANSWER-START"
END_MARKER = "// WORKSPACE-ANSWER-END"
REQUIRED_CONSUMERS = (
    "build-feature.js", "build-ticket.js", "quick-fix.js",
    "plan-feature.js", "fast-lane-ship.js", "finalize-feature.js",
)
SENTINEL_MAIN_COPY = "/sentinel/main-copy-must-never-be-used"
GIVEN_WORKSPACE = "/tmp/bo4300c3-given-workspace"
# The pre-change harness default, now only ever returned because a test says so.
LEGACY_OK_STUB = {"status": "ok", "message": "stub", "passed": True, "git_type": "file",
                  "branch": "feature-stub", "exit_code": 0, "output": ""}
# Labels each workflow dispatches BEFORE its workspace step; scripted because
# the harness no longer answers unscripted dispatches with success. A superset
# is harmless: an unused scripted label is never dispatched.
PRE_WORKSPACE_LABELS = {
    "plan-feature.js": ("detect-current-branch",),
    "quick-fix.js": ("isolation-check", "guard-checks"),
    "finalize-feature.js": ("pre-flight", "gh-config", "step-0-baseline"),
}
_DEPLOYED: Path | None = None


def deployed_workflows_dir() -> Path:
    """Build the workflow scripts with the REAL build phase into a temp
    target (once per process) and return its workflows/ directory."""
    global _DEPLOYED
    if _DEPLOYED is None:
        root = Path(tempfile.mkdtemp(prefix="bo4300c3-deployed-"))
        atexit.register(shutil.rmtree, str(root), True)
        import build_phases
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_VERSION": "2.1.154"}):
            build_phases.build_workflow_scripts(
                root / ".claude", {"workflows": {"enabled": True}, "output_root": ".leafcutter"},
                dry_run=False, force=True)
        _DEPLOYED = root / ".claude" / "workflows"
    return _DEPLOYED


def deployed_workflow_names() -> list[str]:
    return sorted(p.name for p in deployed_workflows_dir().glob("*.js"))


def extract_between_markers(source: str) -> str | None:
    """Text strictly between the START/END marker lines, outer newlines trimmed."""
    s, e = source.find(START_MARKER), source.find(END_MARKER)
    if s == -1 or e == -1 or e < s:
        return None
    return source[s + len(START_MARKER):e].strip("\r\n")


def shared_source_block() -> str:
    """The single tracked source block (between its own markers if it has them)."""
    text = SHARED_SOURCE.read_text(encoding="utf-8")
    inner = extract_between_markers(text)
    return (inner if inner is not None else text).strip("\r\n")


# ---------------------------------------------------------------- replies

def shell_result(stdout: str, exit_status: int = 0, stderr: str = "") -> dict[str, Any]:
    return {"command": "python3 /abs/scripts/worktree.py ensure", "exit_status": exit_status,
            "stdout": stdout, "stderr": stderr}


def ok_maker_answer(path: str = GIVEN_WORKSPACE) -> dict[str, Any]:
    return {"schema_version": 1, "status": "ok", "code": "OK", "verb": "ensure",
            "workspace_path": path, "worktree_path": path, "branch": "fast-lane/fixture",
            "created": True, "message": "workspace ready"}


def hostile_reply(kind: str, token: str | None = None) -> Any:
    """The scripted reply of the workspace step, exactly as the engine would
    deliver it (strings stay strings; nothing is pre-parsed into an ok object)."""
    t = token or f"TOKEN-{kind}"
    return {
        "ok": shell_result(json.dumps(ok_maker_answer())),
        "refusal": shell_result(json.dumps({"status": "refused", "code": "OCCUPIED", "message": t}), 2),
        "error": shell_result(json.dumps({"status": "error", "code": "GIT_FAILED", "message": t}), 1),
        "prose": f"I looked at the repository and set things up as best I could. {t}. Nothing more to add.",
        "neither": shell_result(json.dumps({"status": "pending", "note": t})),
        "none": None,
        "script_path": shell_result(f"/abs/leafcutter/scripts/worktree.py {t}\n"),
        "no_status": shell_result(json.dumps({"message": t})),
        "decline_object": {"declined": True, "agent": "shell-runner",
                           "reason": f"outside my role: {t}"},
        "decline_prose": f"I can't help with that; running this command is outside my role. {t}",
    }[kind]


FIVE_HOSTILE = ("refusal", "error", "prose", "neither", "none")


# ---------------------------------------------------------------- scenarios

def scenario_inputs(name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """(label_responses, args) that reach the workspace step of workflow `name`,
    every pre-workspace dispatch scripted explicitly."""
    # Built-in harness defaults (plan-feature's registry-backed permission and
    # worktree-setup replies, fast-lane gates) are located from the SOURCE
    # script's repo, because the temp deployed copy has no repo above it.
    src_script = TEMPLATES_DIR / "workflows-js" / name
    labels: dict[str, Any] = dict(_default_label_responses_for_script(src_script))
    labels.update({lab: dict(LEGACY_OK_STUB) for lab in PRE_WORKSPACE_LABELS.get(name, ())})
    args: dict[str, Any] = dict(_default_args_for_script(src_script))
    if name == "build-feature.js":
        from unit_tests.workflows import _bo4000_fixtures as bfx
        labels.update(bfx.success_label_responses(ticket_paths=["tickets/00_inbox/epics/EPIC-X/01_TICKET-x.md"]))
        args["target"] = bfx.EPIC_NAME
    elif name == "fast-lane-ship.js":
        args["ac"] = "BO-4300C3-FIXTURE-1"
    return labels, args


def run_scenario(name: str, workspace_reply: Any = "__ABSENT__", args_extra: dict[str, Any] | None = None,
                 extra_labels: dict[str, Any] | None = None) -> HarnessResult:
    """Run the DEPLOYED workflow `name` under the harness. `workspace_reply` is
    scripted for WORKSPACE_LABEL unless the sentinel "__ABSENT__"."""
    key = (name, json.dumps(workspace_reply, sort_keys=True, default=str),
           json.dumps(args_extra, sort_keys=True, default=str), json.dumps(extra_labels, sort_keys=True, default=str))
    return _run_cached(key, name, workspace_reply, args_extra, extra_labels)


_CACHE: dict[Any, HarnessResult] = {}


def _run_cached(key, name, workspace_reply, args_extra, extra_labels) -> HarnessResult:
    if key not in _CACHE:
        labels, args = scenario_inputs(name)
        if workspace_reply != "__ABSENT__":
            labels[WORKSPACE_LABEL] = workspace_reply
        labels.update(extra_labels or {})
        args.update(args_extra or {})
        _CACHE[key] = run_workflow_under_e2(deployed_workflows_dir() / name, timeout=90,
                                            label_responses=labels, args=args)
    return _CACHE[key]


def workspace_calls(result: HarnessResult) -> list:
    return [c for c in result.agent_calls if c.label == WORKSPACE_LABEL]


def reads_args_workspace(source: str) -> bool:
    return bool(re.search(r"\bargs\.workspace\b|args\[\s*['\"]workspace['\"]\s*\]", source))


@lru_cache(maxsize=None)
def consuming_workflows() -> tuple[str, ...]:
    """Workflows that read args.workspace OR record a workspace dispatch when
    run without it -- derived from the deployed set, never listed."""
    out = []
    for name in deployed_workflow_names():
        src = (deployed_workflows_dir() / name).read_text(encoding="utf-8")
        if reads_args_workspace(src) or workspace_calls(run_scenario(name, hostile_reply("ok"))):
            out.append(name)
    return tuple(out)


def terminal(result: HarnessResult) -> dict[str, Any]:
    return result.result if isinstance(result.result, dict) else {}


def terminal_text(result: HarnessResult) -> str:
    return json.dumps(result.result, default=str)
