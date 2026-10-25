"""
MODULE: _workflow_engine_workspace
GOAL: Test-side helpers for the workspace step every workspace-consuming
      workflow carries (WORKSPACE-ANSWER block, BO-4300c-3) and for the
      shell-runner reply shape (BO-4300a-1-ia, ADR-070).
BUSINESS CONTEXT: The workflow engine harness scripts agent replies by label.
    Workflows now obtain their workspace and run shell steps through one
    verbatim dispatch each; tests need ready/refused replies in the exact
    shape the real engine delivers, and an empty marker pair filled from the
    single tracked source.
ARCHITECTURE: Pure functions and constants with no dependency on the harness
    itself; _workflow_engine_harness star-imports this module so existing
    ``from _workflow_engine_harness import workspace_ensure_reply`` callers
    keep working. Split out of the harness to honour the file-size ratchet.

DECISION HISTORY:
    - 2026-10-12 (BO-4300 ticket 10): moved verbatim out of
      _workflow_engine_harness.py; behaviour unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

__all__ = [
    "_WORKSPACE_ANSWER_START",
    "_fill_workspace_answer",
    "_handed_in_verify_default",
    "_workspace_step_default_responses",
    "finalize_baseline_responses",
    "finalize_deploy_parity_responses",
    "finalize_targeted_rerun_responses",
    "fill_workspace_answer",
    "pytest_run_reply",
    "resolve_connected_reply",
    "scratch_workspace_reply",
    "shell_step_reply",
    "workspace_answer_of",
    "workspace_ensure_from_opened",
    "workspace_ensure_reply",
    "workspace_refusal_reply",
]


def _workspace_step_default_responses(script_path: Path) -> dict[str, Any]:
    """Script-specific default for the ONE workspace step (BO-4300c-3), same class as the gates above.

    A workflow that carries the WORKSPACE-ANSWER block dispatches a single
    ``workspace-ensure`` step when it is not handed ``args.workspace``. Callers
    that are not about that step (most of the suite) would otherwise stop at it,
    so a ready shell-runner reply -- ``{command, exit_status, stdout, stderr}``
    with the maker's ok answer as the stdout STRING, exactly as the real engine
    delivers it -- is scripted for that label only. Any test that exercises the
    step (hostile or not) scripts the label itself and wins (merge order), and
    an unscripted label other than this one is still an error-shaped reply.
    """
    try:
        text = script_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    if _WORKSPACE_ANSWER_START not in text:
        return {}
    answer = {
        "schema_version": 1, "status": "ok", "code": "OK", "verb": "ensure",
        "workspace_path": "/tmp/harness-default-workspace",
        "worktree_path": "/tmp/harness-default-workspace",
        "branch": "feature/harness-default", "created": False,
        "message": "workspace ready (harness default)",
    }
    return {
        "workspace-ensure": {
            "command": "python3 worktree.py ensure (harness default)",
            "exit_status": 0,
            "stdout": json.dumps(answer),
            "stderr": "",
        }
    }


def workspace_ensure_reply(workspace_path: Any, branch: str = "feature/test-workspace", **extra: Any) -> dict[str, Any]:
    """A ready ``workspace-ensure`` reply for a test to script (BO-4300c-3): the shell-runner shape
    ``{command, exit_status, stdout, stderr}`` carrying the maker's ok answer as the stdout STRING,
    exactly as the real engine delivers it. ``extra`` keys (``ac_store_path``, ``created``,
    ``base_commit`` ...) are added to the maker's answer."""
    answer: dict[str, Any] = {
        "schema_version": 1, "status": "ok", "code": "OK", "verb": "ensure",
        "workspace_path": str(workspace_path), "worktree_path": str(workspace_path),
        "branch": branch, "created": False, "message": "workspace ready (test)",
    }
    answer.update(extra)
    return {
        "command": "python3 worktree.py ensure (test)",
        "exit_status": 0,
        "stdout": json.dumps(answer),
        "stderr": "",
    }


def workspace_ensure_from_opened(payload: dict[str, Any]) -> dict[str, Any]:
    """The ready ``workspace-ensure`` reply for a test that used to script an opened-worktree payload.

    ``payload`` carries ``worktree_path`` and optionally ``branch`` plus the other facts the lane reads
    (``ac_store_path``, ``created`` ...); they ride the maker's ok answer unchanged.
    """
    extra = {k: v for k, v in payload.items() if k not in ("worktree_path", "branch", "status")}
    return workspace_ensure_reply(
        payload["worktree_path"], branch=payload.get("branch") or "feature/test-workspace", **extra
    )


def workspace_refusal_reply(code: str = "WORKSPACE_OCCUPIED", message: str = "workspace refused (test)", **extra: Any) -> dict[str, Any]:
    """A ``workspace-ensure`` reply in which the maker REFUSED (``status: refused``, exit status 2)."""
    answer: dict[str, Any] = {
        "schema_version": 1, "status": "refused", "code": code, "verb": "ensure", "message": message,
    }
    answer.update(extra)
    return {
        "command": "python3 worktree.py ensure (test)",
        "exit_status": 2,
        "stdout": json.dumps(answer),
        "stderr": "",
    }


def shell_step_reply(stdout: Any = "", exit_status: int = 0, stderr: str = "", command: str = "(test)") -> dict[str, Any]:
    """A shell executor's reply ``{command, exit_status, stdout, stderr}`` (BO-4300a-1-ia, ADR-070).

    ``stdout`` that is not already a string is serialised as JSON, as the real executor relays the
    command's printed text verbatim (so a list of AC ids is delivered as the string ``'["A", "B"]'``).
    """
    return {
        "command": command,
        "exit_status": exit_status,
        "stdout": stdout if isinstance(stdout, str) else json.dumps(stdout),
        "stderr": stderr,
    }


def resolve_connected_reply(payload: Any) -> dict[str, Any]:
    """The ``resolve-connected`` command step's reply: the resolver prints a JSON list of AC ids.

    ``payload`` is the list itself or a mapping carrying it under ``ac_ids``.
    """
    ids = payload.get("ac_ids", []) if isinstance(payload, dict) else payload
    return shell_step_reply(list(ids), command="fast_lane.py select_connected (test)")


def workspace_answer_of(reply: dict[str, Any]) -> dict[str, Any]:
    """The maker's answer (parsed) carried in a scripted ``workspace-ensure`` reply's stdout."""
    return json.loads(reply["stdout"])


def pytest_run_reply(failing_ids: Any = (), exit_status: int | None = None) -> dict[str, Any]:
    """A shell executor's reply to one ``python3 -m pytest --tb=no -q`` run: the ids it reports failing are
    printed as ``FAILED <id> - ...`` lines; exit status 1 when any fail, else 0 (unless ``exit_status``)."""
    ids = list(failing_ids)
    lines = [f"FAILED {test_id} - AssertionError" for test_id in ids]
    lines.append(f"{len(ids)} failed" if ids else "all passed")
    status = (1 if ids else 0) if exit_status is None else exit_status
    return shell_step_reply(chr(10).join(lines), exit_status=status)


def scratch_workspace_reply(label: str, base_commit: str = "abc1234") -> dict[str, Any]:
    """The maker's ready answer for the scratch workspace (a clone at origin/main) a baseline run uses."""
    return workspace_ensure_reply(f"/tmp/scratch-{label}", branch="scratch/main", base_commit=base_commit)


def finalize_baseline_responses(
    failing_ids: Any = (), base_commit: str = "abc1234", label: str = "step-0-baseline"
) -> dict[str, Any]:
    """The scripted replies of a SUCCESSFUL finalize baseline run (BO-4300a-1-ia): a scratch workspace from
    the maker, one pytest run reporting ``failing_ids`` failing, and the maker's removal of the scratch."""
    return {
        f"{label}-workspace": scratch_workspace_reply("baseline", base_commit),
        label: pytest_run_reply(failing_ids),
        "cleanup-baseline-worktree": shell_step_reply({"status": "ok"}),
    }


_SHARED_DIR = Path(__file__).resolve().parents[1] / "templates" / "workflows-js" / "_shared"
_WORKSPACE_ANSWER_START = "// WORKSPACE-ANSWER-START"


# Marker name -> the single tracked source the build fills that pair from.
_SHARED_BLOCKS = (
    ("WORKSPACE-ANSWER", "workspace-answer.js"),  # BO-4300c-3
    ("WRONG-VERSION-RUNS", "wrong-version-runs.js"),  # TQ-500g-1-xi (build-feature.js, build-ticket.js)
)


def _fill_pair(source: str, name: str, filename: str) -> str:
    """Fill one EMPTY ``// <name>-START`` / ``// <name>-END`` pair from ``_shared/<filename>``."""
    start_marker, end_marker = f"// {name}-START", f"// {name}-END"
    start = source.find(start_marker)
    if start == -1:
        return source
    end = source.find(end_marker, start)
    if end == -1 or source[start + len(start_marker):end].strip():
        return source
    block = (_SHARED_DIR / filename).read_text(encoding="utf-8").strip()
    return source[:start + len(start_marker)] + "\n" + block + "\n" + source[end:]


def _fill_workspace_answer(source: str) -> str:
    """Fill every EMPTY shared-block marker pair from its single tracked source, as the build does.

    Despite the name (kept for its callers) this fills each pair in ``_SHARED_BLOCKS``. The build
    phase does this when it deploys a workflow; a test that runs a template straight from
    ``templates/workflows-js/`` (or a source-patched copy of one) would otherwise execute a body
    whose block is empty. A pair that already holds text (a deployed copy) or a source with no
    pair (fast-lane-ship.js keeps its own wrong-version block) is returned unchanged -- the
    harness never overwrites a block.
    """
    for name, filename in _SHARED_BLOCKS:
        source = _fill_pair(source, name, filename)
    return source


fill_workspace_answer = _fill_workspace_answer


"""Public alias: a test that reads a workflow TEMPLATE and runs it itself fills the empty marker pair first."""


def finalize_targeted_rerun_responses(spec: dict) -> dict:
    """Translate the recovery outcome a test wants into the scripted replies of the dispatches that now
    produce it (BO-4300a-1-ia: a scratch workspace from the maker, [build], one pytest run, its removal).

    ``spec`` keeps the old vocabulary: ``ok`` + ``recovered_failures`` -> the run reports exactly those ids
    failing; ``checkout_failed`` -> the maker refuses the scratch workspace; ``build_failed`` -> the deploy
    step (build.py) in the scratch workspace exits non-zero.
    """
    status = spec["status"]
    out: dict = {}
    if status == "ok":
        out["step-3-targeted-rerun-workspace"] = scratch_workspace_reply("rerun")
        out["step-3-targeted-rerun-deploy"] = shell_step_reply("", exit_status=0)
        out["step-3-targeted-rerun"] = pytest_run_reply(list(spec["recovered_failures"]))
    elif status == "checkout_failed":
        out["step-3-targeted-rerun-workspace"] = workspace_refusal_reply("FETCH_FAILED", "could not clone origin/main")
    elif status == "build_failed":
        out["step-3-targeted-rerun-workspace"] = scratch_workspace_reply("rerun")
        out["step-3-targeted-rerun-deploy"] = shell_step_reply("", exit_status=1, stderr="build.py failed")
    else:  # pragma: no cover - a test asked for an outcome this helper does not know
        raise AssertionError(f"unknown targeted rerun outcome {status!r}")
    return out


def finalize_deploy_parity_responses(still_failing, deploy_exit_status=0):
    """The scripted replies of the deploy-parity self-check: build.py (one shell step), then ONE pytest
    re-run of the failing ids that reports ``still_failing`` as still failing. Everything the re-run does
    not report failing is build-state skew, computed by the workflow -- never taken from prose."""
    return {
        "step-3-deploy-parity": shell_step_reply("", exit_status=deploy_exit_status),
        "step-3-deploy-parity-rerun": pytest_run_reply(list(still_failing)),
    }


def _handed_in_verify_default(script_path: Path, args: dict[str, Any]) -> dict[str, Any]:
    """Default ``workspace-verify`` reply for a run handed a location (BO-4300c-4-i).

    A workflow carrying the WORKSPACE-ANSWER block confirms a handed-in ``worktree_path`` /
    ``workspace_path`` with ONE verify request. Callers that are not about that step get the
    maker's ok verify answer naming the SAME location; a test that exercises the step scripts
    the ``workspace-verify`` label itself and wins (merge order).
    """
    given = next((args[k] for k in ("worktree_path", "workspace_path") if isinstance(args.get(k), str) and args[k].strip()), None)
    if given is None or args.get("workspace") is not None or not _workspace_step_default_responses(script_path):
        return {}
    answer = workspace_ensure_reply(given.strip(), branch="feature/harness-default")
    answer["stdout"] = json.dumps({**json.loads(answer["stdout"]), "verb": "verify"})
    return {"workspace-verify": answer}
