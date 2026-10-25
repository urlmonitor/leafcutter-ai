"""
MODULE: unit_tests/workflows/_tq500g1v_fixtures.py
GOAL: Shared stubs and readers for the TQ-500g-1-v workflow tests: driving
    templates/workflows-js/fast-lane-ship.js (the TEMPLATE, never a deployed copy) through the
    wrong-version steps that sit between the Review phase and the commit dispatch.
BUSINESS CONTEXT: The route is: [recover on a resumed drive], the writer's list step, test-breaker
    (only when something is owed), then ONE finish call. Each command step is dispatched to
    command-step-runner; its reply is {command, workspace, exit_status, stdout, stderr}, the
    command's own JSON as text in stdout (the shape the claim step already uses). The verdict
    stubs are built with the runner's own ``assemble`` / ``row``, never typed by hand.
PINNED DISPATCH LABELS (the contract these tests constrain the coder to; the AC names none):
    recover  -> label ``fastlane-wv-recover``      agentType ``command-step-runner``
    list     -> label ``fastlane-wv-list``         agentType ``command-step-runner``
    breaker  -> label ``fastlane-wv-test-breaker`` agentType ``test-breaker``
    finish   -> label ``fastlane-wv-finish``       agentType ``command-step-runner``
    A drive is RESUMED when the worktree phase reports ``created: false`` (it reconnected).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from _workflow_engine_harness import HarnessResult, resolve_connected_reply, run_workflow_under_e2, workspace_ensure_from_opened

import workflows._fast_lane_claim_fixtures as claim_fx

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WORKFLOW = REPO_ROOT / "templates" / "workflows-js" / "fast-lane-ship.js"
sys.path.insert(0, str(REPO_ROOT / "scripts" / "build_orchestration"))
from _wvr_verdict import assemble, row  # noqa: E402
from wrong_version_runner import NO_TESTS_OUTCOME  # noqa: E402

RECOVER, LIST, BREAKER, FINISH = (f"fastlane-wv-{s}" for s in ("recover", "list", "test-breaker", "finish"))
EXECUTOR = "command-step-runner"
COMMIT, PR, REVIEW, CODER = "fastlane-commit", "fastlane-pr", "fastlane-review", "coder-connected"
WORKTREE = "/tmp/fastlane-wt-tq500g1v"
AC = "BO-STUB-1"
TEST, WRONG = "test_gate_blocks_refresh_without_retry", "drop the retry_due condition"
ROOT_RE = re.compile(r"^(/|[A-Za-z]:[\\/])")


def ran(payload: Any, exit_status: int = 0) -> dict:
    """A command-step-runner reply: the command ran; its stdout is *payload* (str, or JSON-encoded)."""
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return {"exit_status": exit_status, "stdout": text, "stderr": ""}


def declined() -> dict:
    """A reply from an executor that refused to run the command."""
    return claim_fx.claim_declined("would not run the command", step="fastlane-wv")


def recover_reply(ok: Any = True) -> dict:
    return ran({"restored": [], "ok": ok, "copy_dir": None, "detail": ""})


def list_reply(owed: list[dict], error: str | None = None, to_prepare: list[dict] | None = None) -> dict:
    """The list step's reply; ``to_prepare`` defaults to *owed* ("prepare everything", TQ-500g-1-xi); both [] on error."""
    prepare = [] if error is not None else (list(owed) if to_prepare is None else to_prepare)
    return ran({"owed": owed, "to_prepare": prepare, "decisions": [], "error": error}, 0 if error is None else 1)


def owed_item(name: str, files: list[str], scope: str = "declared") -> dict:
    return {"name": name, "files": files, "scope": scope}


def writer_json(written: bool = True, error: str | None = None) -> dict:
    return {"written": written, "manifest_path": "/m/alterations.json" if written else None, "error": error,
            "entries": [], "ignored_reply_names": [], "preparer_anomalies": []}


def verdict_f1() -> dict:
    return assemble([row(TEST, WRONG, "caught", "failed under it by an assertion")])


def verdict_f2() -> dict:
    return assemble([row(TEST, WRONG, "survived", "still passed under it")])


def verdict_f3() -> dict:
    return assemble([], applicable=False, outcome=NO_TESTS_OUTCOME)


def finish_reply(verdict: dict | None, *, stopped_at: str | None = None, writer: dict | None = None) -> dict:
    """The reply to the finish step; exit status 1 whenever the wrapper's gate_passed is false."""
    passed = bool(verdict and verdict["gate_passed"])
    out = {"gate_passed": passed, "stopped_at": stopped_at, "writer": writer or writer_json(), "verdict": verdict,
           "pins": None}
    return ran(out, 0 if passed else 1)


def writer_stop_reply(error: str = "the preparer's reply could not be read: the reply is empty") -> dict:
    return finish_reply(None, stopped_at="write", writer=writer_json(False, error))


def green_labels(worktree: str = WORKTREE, ac_ids: tuple[str, ...] = (AC,), created: bool = True) -> dict:
    """Responses that drive the lane to the commit and PR phases, with the wrong-version steps passing."""
    slug = ac_ids[-1].lower()
    return {
        "workspace-ensure": workspace_ensure_from_opened({"worktree_path": worktree, "branch": f"fast-lane/{slug}", "created": created,
                                                         "ac_store_path": f"{worktree}/docs/acceptance-criteria"}),
        "resolve-connected": resolve_connected_reply({"ac_ids": list(ac_ids), "message": f"{len(ac_ids)} to build"}),
        "claim-connected": claim_fx.claim_ran(list(ac_ids)),
        "test-writer-connected": {"status": "ok", "tests_written": ["unit_tests/test_stub.py"], "gate_passed": True,
                                  "reason": None, "green_at_baseline": [], "message": "red baseline ok"},
        CODER: {"status": "ok", "files_modified": ["scripts/stub_impl.py"], "green": True, "coverage_ok": True,
                "uncovered_ac_ids": [], "message": "implementation green"},
        "fastlane-context-bundle": {"obtained": True, "message": "bundle assembled", "bundle": (
            "ARCHITECTURE (stub)\n\n<!-- CACHE_BREAKPOINT -->\n\nBATCH ACS (stub)\n\nPRIOR TESTS (stub)")},
        REVIEW: {"verdict_obtained": True, "high_findings": [], "medium_findings": [], "low_suppressed_count": 0,
                 "message": "clean"},
        "fastlane-changelog": {"status": "ok", "entry_added": True, "entry_path": "changelogs/x.md", "message": "ok"},
        COMMIT: {"status": "ok", "branch": f"fast-lane/{slug}", "message": "committed"},
        PR: {"status": "ok", "pr_url": "https://github.com/example/repo/pull/1", "message": "PR opened"},
        RECOVER: recover_reply(),
        LIST: list_reply([]),
        BREAKER: {"work_key": ac_ids[-1], "entries": [], "anomalies": []},
        FINISH: finish_reply(verdict_f1()),
    }


def wrong_version_passing() -> dict:
    """Replies for just the wrong-version steps, all answering "nothing owed / gate passed"."""
    keep = (RECOVER, LIST, BREAKER, FINISH)
    return {k: v for k, v in green_labels().items() if k in keep}


def run_lane(overrides: dict | None = None, *, worktree: str = WORKTREE, ac_ids: tuple[str, ...] = (AC,),
             created: bool = True) -> HarnessResult:
    """Run the template under the E2 harness with the green baseline plus *overrides* (label -> reply)."""
    labels = green_labels(worktree, ac_ids, created)
    labels.update(overrides or {})
    return run_workflow_under_e2(WORKFLOW, timeout=60, label_responses=labels, args={"ac": ac_ids[-1]})


def labels_of(result: HarnessResult) -> list[str | None]:
    return [c.label for c in result.agent_calls]


def calls(result: HarnessResult, label: str) -> list:
    return [c for c in result.agent_calls if c.label == label]


def released(result: HarnessResult) -> bool:
    """True when a release-on-* dispatch was made (the claimed ACs were given back)."""
    return any((c.label or "").startswith("release-on-") for c in result.agent_calls)


def command_of(call) -> str:
    """The shell command a command-step dispatch carries (its JSON ``command``, else the prompt text)."""
    try:
        return str(json.loads(call.prompt)["command"])
    except (ValueError, KeyError, TypeError):
        return str(call.prompt)


def flag(command: str, name: str) -> str | None:
    """The value after ``--name`` in *command* (quotes stripped), or None when the flag is absent."""
    match = re.search(rf"--{name}[ =]+[\"']?([^\s\"']+)", command)
    return match.group(1) if match else None


def breaker_input(call) -> dict | None:
    """The input object of a test-breaker dispatch: the first JSON object in its prompt with wrong_versions."""
    text, decoder = str(call.prompt), json.JSONDecoder()
    for m in re.finditer(r"\{", text):
        try:
            obj, _ = decoder.raw_decode(text, m.start())
        except ValueError:
            continue
        if isinstance(obj, dict) and "wrong_versions" in obj:
            return obj
    return None


def _bash() -> str:
    """A POSIX shell: Git's bash on Windows (``bash`` there can be the WSL launcher), else ``bash``."""
    if os.name == "nt" and (git := shutil.which("git")):
        for parent in Path(git).resolve().parents[:3]:
            for rel in ("bin/bash.exe", "usr/bin/bash.exe"):
                if (parent / rel).is_file():
                    return str(parent / rel)
    return "bash"


def run_recorded(call, gate_script: Path, cwd: Path) -> subprocess.CompletedProcess:
    """Execute the recorded finish command in a REAL shell, with the wrapper's path swapped for *gate_script*."""
    command = command_of(call)
    python = f'"{Path(sys.executable).as_posix()}" "{gate_script.as_posix()}"'
    swapped, count = re.subn(r"\bpython3?\s+\S*wrong_version_gate\.py", lambda _m: python, command, count=1)
    assert count == 1, f"the finish command does not invoke wrong_version_gate.py: {command!r}"
    # A script file, not `bash -c`: the Windows argument round-trip would rewrite quotes and backslashes in the reply.
    with tempfile.TemporaryDirectory() as scratch:
        script = Path(scratch) / "finish.sh"
        script.write_bytes((swapped + "\n").encode("utf-8"))
        return subprocess.run([_bash(), script.as_posix()], cwd=cwd, capture_output=True, timeout=900)


def stdin_capture_gate(directory: Path) -> tuple[Path, Path]:
    """A stand-in wrapper that saves the bytes it reads on stdin; return ``(script, saved file)``."""
    saved = directory / "stdin.bin"
    script = directory / "capture_gate.py"
    script.write_text(
        "import json, sys\nfrom pathlib import Path\n"
        f"Path({saved.as_posix()!r}).write_bytes(sys.stdin.buffer.read())\n"
        "print(json.dumps({'gate_passed': True, 'stopped_at': None, 'writer': None, 'verdict': None}))\n",
        encoding="utf-8")
    return script, saved
