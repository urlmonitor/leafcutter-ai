"""
MODULE: unit_tests/workflows/_bo400e3_finalize_harness.py
GOAL: Drive the REAL finalize-feature.js through the E2 workflow-engine harness for the Step 3.5
      (pre-merge closure) tests of BO-400e-3-ii .. -viii and BO-4500a-5-iv.

NOT a test file. Nothing is collected.

DISPATCH CONTRACT PINNED FOR THE CODER (finalize-feature.js Step 3.5 does not do this yet):

  step-3.5-derive-set     agent permitted to run shell; prompt runs
                          `finalize_closable_set.py derive ...`; the reply is the command-step-runner
                          result {command, workspace, exit_status, stdout, stderr} whose stdout is the
                          CLI's JSON object (run_finalize wraps a bare object that way; a reply with a
                          non-zero exit_status or a non-string stdout is a failed step).
  step-3.5-close-set      prompt runs `finalize_closable_set.py close ...` against the persisted set
                          file ONLY (no record list in the prompt); the reply is the CLI's JSON object.
  step-3.5-closure-commit the `commit` agent running the shared step in supervised mode, naming the
                          run (args.run_id) and exactly the close reply's commit_paths; the reply is
                          {status, commit_answer:{status, reason_code, reason, ...}}.
  The person-only gate before any write uses the pause/resume machinery (ADR-024): the first headless
  invocation pauses (pause-persist), and a resume_answer {gate_id, type, action: 'confirm'|'decline',
  channel: 'person'} validated against the durable record (read-pause-record) is the only 'yes'.

Every reply handed to the workflow is the REAL module's output for a real scratch repository (see
unit_tests/build_orchestration/_bo400e3_support.py), never a hand-typed literal of the shape.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_UNIT_TESTS = Path(__file__).resolve().parent.parent
for _p in (_UNIT_TESTS, _UNIT_TESTS / "build_orchestration"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from _workflow_engine_harness import HarnessResult, finalize_baseline_responses, run_workflow_under_e2, workspace_ensure_reply  # noqa: E402

REPO_ROOT = _UNIT_TESTS.parent
FINALIZE_JS = REPO_ROOT / "templates" / "workflows-js" / "finalize-feature.js"

DERIVE = "step-3.5-derive-set"
CLOSE = "step-3.5-close-set"
COMMIT = "step-3.5-closure-commit"
RESET_MERGE = "step-3.5-reset-merge"
MERGE = "step-4-merge-pr"
MERGE_GATE = "step-4-merge-gate"
TIMEOUT = 60


def base_responses(branch: str, worktree_root: str) -> dict:
    """Steer finalize through pre-flight and steps 1-3 to Step 3.5 (same shape the BO-2300 tests use)."""
    return {
        "workspace-ensure": workspace_ensure_reply(worktree_root, branch=branch),
        **finalize_baseline_responses(),
        "step-1-pr-probe": {"found": True, "number": 99, "url": "https://github.com/test/test/pull/99"},
        "step-2-merge-main": {"status": "already_up_to_date", "merge_strategy": "already_up_to_date"},
        "pre-step-4-sync-check": {"status": "up_to_date", "local_sha": "abc1234", "origin_sha": "abc1234",
                                  "ahead_count": 0, "behind_count": 0},
        # Sub-step A fails closed: only aborted | no_merge continue. A clean tree answers no_merge;
        # a test modelling an in-progress Step 2 merge overrides with {"status": "aborted"}.
        RESET_MERGE: {"status": "no_merge"},
        # BO-4300c-3-ii: an unscripted dispatch is an error reply, no longer a generic "ok" stub, so the
        # merge-confirmation gate the closure tests run on to is scripted as the person saying yes.
        MERGE_GATE: {"status": "ok"},
    }


def committed_answer(sha: str = "abc1234") -> dict:
    answer = {"status": "committed", "reason_code": None, "reason": None, "sha": sha}
    return {"status": "committed", "commit_answer": answer}


def refused_answer(status: str, reason_code: str, reason: str) -> dict:
    answer = {"status": status, "reason_code": reason_code, "reason": reason, "sha": None}
    return {"status": status, "commit_answer": answer}


def runner_reply(value, command: str = "finalize_closable_set.py") -> dict:
    """Wrap a closer's printed output the way command-step-runner relays it: {command, workspace,
    exit_status, stdout, stderr}, stdout being the module's printed text verbatim.

    A dict that already carries an `exit_status` key is a hand-built runner reply (a test of the
    runner-reply checks) and is passed through unchanged.
    """
    if isinstance(value, dict) and "exit_status" in value:
        return value
    text = value if isinstance(value, str) else json.dumps(value)
    return {"command": command, "workspace": "", "exit_status": 0, "stdout": text, "stderr": ""}


def run_finalize(
    branch: str, worktree_root: str, *, derive=None, close=None, commit=None, extra=None, args=None,
) -> HarnessResult:
    responses = base_responses(branch, worktree_root)
    for label, value in ((DERIVE, derive), (CLOSE, close), (COMMIT, commit)):
        if value is not None:
            responses[label] = runner_reply(value) if label in (DERIVE, CLOSE) else value
    responses.update(extra or {})
    result = run_workflow_under_e2(FINALIZE_JS, timeout=TIMEOUT, label_responses=responses, args=args or {})
    assert result.error == "", f"harness error: {result.error}"
    return result


def labels(result: HarnessResult) -> list:
    return [c.label for c in result.agent_calls]


def calls(result: HarnessResult, label: str) -> list:
    return [c for c in result.agent_calls if c.label == label]


def prompt_of(call) -> str:
    return call.prompt if isinstance(call.prompt, str) else json.dumps(call.prompt)


def step35_prompts(result: HarnessResult) -> list[str]:
    return [prompt_of(c) for c in result.agent_calls
            if str(c.label or "").startswith("step-3.5") or c.phase_name == "Step 3.5"]


def report_text(result: HarnessResult) -> str:
    """The whole terminal payload as lower-case text, underscores read as spaces."""
    return json.dumps(result.result, sort_keys=True).lower().replace("_", " ")


def near(text: str, needle: str, *words: str, span: int = 300) -> bool:
    """True when `needle` occurs within `span` characters of any of `words` (all lower-case)."""
    needle = needle.lower()
    for match in re.finditer(re.escape(needle), text):
        window = text[max(0, match.start() - span): match.end() + span]
        if any(w in window for w in words):
            return True
    return False


def completed_steps(result: HarnessResult) -> list[str]:
    payload = result.result if isinstance(result.result, dict) else {}
    return [str(s) for s in (payload.get("completed_steps") or [])]


def _walk_record(text: str) -> dict:
    marker = "--record '"
    start = text.index("{", text.index(marker) + len(marker))
    depth, in_string, i = 0, False, start
    while i < len(text):
        ch = text[i]
        if in_string:
            if ch == "\\":
                i += 2
                continue
            in_string = ch != '"'
        elif ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start: i + 1])
        i += 1
    raise ValueError("unbalanced --record payload")  # noqa: TRY003


def closure_pause(result: HarnessResult) -> tuple[dict, str]:
    """(record, prompt) of the pause-persist dispatch for the closure gate (not the Step 4 gate)."""
    for call in calls(result, "pause-persist"):
        prompt = prompt_of(call)
        record = _walk_record(prompt)
        if record.get("gate_id") != MERGE_GATE:
            return record, prompt
    raise AssertionError(f"no closure-gate pause was persisted; labels: {labels(result)}")  # noqa: TRY003


def first_run(branch, worktree_root, *, derive, close=None, commit=None, extra=None, args=None):
    """The headless invocation: lists the records and pauses at the person-only closure gate."""
    return run_finalize(branch, worktree_root, derive=derive, close=close, commit=commit, extra=extra,
                        args={"run_id": "finalize-epic-x-20261012", **(args or {})})


def resume_run(
    branch, worktree_root, record: dict, action: str, *, derive, close=None, commit=None, channel="person",
    stale: bool = False, extra=None,
):
    """The second invocation: a resume answer for the closure gate, validated against the pause record."""
    answer = {"gate_id": record["gate_id"], "type": record["question"]["type"], "action": action}
    if channel is not None:
        answer["channel"] = channel
    responses = {"read-pause-record": {"exists": True, "stale": stale, "record": record}, **(extra or {})}
    return run_finalize(branch, worktree_root, derive=derive, close=close, commit=commit, extra=responses,
                        args={"run_id": "finalize-epic-x-20261012", "resume_answer": answer})


def confirmed_run(branch, worktree_root, *, derive, close, commit=None, extra=None):
    """Both invocations with a person's confirmation; returns (paused_first_run, resumed_run)."""
    first = first_run(branch, worktree_root, derive=derive, close=close, commit=commit, extra=extra)
    record, _prompt = closure_pause(first)
    second = resume_run(branch, worktree_root, record, "confirm", derive=derive, close=close,
                        commit=commit or committed_answer(), extra=extra)
    return first, second
