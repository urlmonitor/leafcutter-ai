"""
MODULE: _workspace_harness_defaults
GOAL: Give every test that runs a workspace-consuming workflow a ready workspace
    answer by default, and carry a pre-BO-4300c-3 fixture across to the one-way
    workspace step.
BUSINESS CONTEXT: BO-4300c-3 made each workflow that needs a workspace take it
    only from the workspace maker's answer: ``args.workspace`` (the maker's JSON
    object handed in verbatim) or one maker dispatch. It accepts the answer only
    when ``status == "ok"`` and ``workspace_path`` is a non-empty string, and ends
    the run with an error otherwise. Hundreds of older tests were written when
    the workflows found, probed or created their own worktree, so a run that
    names no workspace now stops at the workspace step before the step the test
    is about. This module supplies, in one place and never pasted per caller:
    the ready answer a run gets when its caller says nothing about the workspace,
    and the restatement of an old-shaped scripted reply in the maker's shape. A
    test about the workspace step itself (a refusal, an error, prose, no answer)
    scripts that step's reply or passes ``args.workspace``, and always wins.
ARCHITECTURE: Pure-Python helpers, no test classes. Lives directly under
    unit_tests/, a sibling of _workflow_engine_harness.py (which calls
    ``default_workspace_args``, ``legacy_workspace_fixtures`` and
    ``inline_workspace_block``) and of the hand-rolled Node shims some tests
    keep (which call ``inline_workspace_block`` and ``ready_workspace_args``).
    Split out of the harness because that file sits at the check-file-size
    ratchet.

DECISION HISTORY
================================================================================
- 2026-10-15 [test-writer]: Created for BO-4300c-3 test-drift repair. The ready
  answer is handed in as ``args.workspace`` rather than scripted as a label
  reply, because a legacy run names no project root and the workflow asks the
  maker only when it can name one. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/23)
- 2026-10-16 12:00 [python-coder]: Restored from the set-aside copy and wired into
  the engine harness. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/23)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

#: The label of each workspace-consuming workflow's one workspace step (the
#: maker dispatch made by the WORKSPACE-ANSWER block's ``obtainWorkspace``).
WORKSPACE_STEP_LABELS: dict[str, str] = {
    "build-epic.js": "workspace-ensure",
    "build-feature.js": "workspace-ensure",
    "build-ticket.js": "workspace-ensure",
    "quick-fix.js": "workspace-ensure",
    "plan-feature.js": "workspace-ensure",
    "fast-lane-ship.js": "fastlane-worktree",
    "finalize-feature.js": "pre-flight",
}
DEFAULT_WORKSPACE_PATH = "/tmp/harness-default-workspace"
DEFAULT_PROJECT_ROOT = "/tmp/harness-default-project"
DEFAULT_FINALIZE_TARGET = "EPIC-HarnessDefault"

_START = "// WORKSPACE-ANSWER-START"
_END = "// WORKSPACE-ANSWER-END"
_REPO_ROOT = Path(__file__).resolve().parents[1]
_STEP_LABEL_RE = re.compile(r"obtainWorkspace\(.*?label:\s*[\"']([^\"']+)[\"']", re.DOTALL)


def workspace_step_label(script_path: Path) -> str | None:
    """The label of ``script_path``'s workspace step, or None when it has none.

    Matched by file name first (the common case), then by reading the script, so
    a source-patched TEMP COPY under an unrelated file name (several tests make
    one to inject a single line) still gets the workspace defaults.
    """
    label = WORKSPACE_STEP_LABELS.get(script_path.name)
    if label is not None:
        return label
    try:
        text = script_path.read_text(encoding="utf-8")
    except OSError:
        return None
    if _START not in text:
        return None
    found = _STEP_LABEL_RE.search(text)
    return found.group(1) if found else None


def inline_workspace_block(source: str, script_path: Path) -> str:
    """Fill an EMPTY WORKSPACE-ANSWER marker pair the way the build phase does.

    A raw ``templates/workflows-js/<name>.js`` carries only the empty pair (the
    build fills it, BO-4300c-3), so a test that runs the template itself would
    otherwise meet an undefined ``obtainWorkspace``. A deployed copy already
    holds the block and is returned untouched, so the deployed text is what runs.
    """
    if _START not in source or _END not in source:
        return source
    if source.split(_START, 1)[1].split(_END, 1)[0].strip():
        return source
    scripts_dir = str(_REPO_ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from build_workflow_inline import inline_workspace_block as build_inline

    return build_inline(source, script_path.name, _REPO_ROOT / "templates" / "workflows-js")


def ready_workspace_args(path: str = DEFAULT_WORKSPACE_PATH) -> dict[str, Any]:
    """The maker's ready answer for ``path``, as an ``args`` fragment."""
    return {
        "workspace": {
            "status": "ok",
            "workspace_path": path,
            "worktree_path": path,
            "branch": "feature/harness-default",
        }
    }


def _scripted_location(label_responses: dict[str, Any]) -> str | None:
    """The location a legacy fixture scripted for the old worktree step, if any.

    Old tests said where the work happens through the target resolver's
    ``worktree_path`` (build-feature / build-epic / build-ticket) or through the
    ``worktree-setup`` reply's JSON (plan-feature); both are kept as the
    location of the ready answer so an assertion about where a later dispatch
    runs keeps its meaning.
    """
    resolved = label_responses.get("resolve-target")
    if isinstance(resolved, dict) and isinstance(resolved.get("worktree_path"), str):
        if resolved["worktree_path"].strip():
            return resolved["worktree_path"]
    check = label_responses.get("isolation-check")
    if isinstance(check, dict) and isinstance(check.get("session_cwd"), str):
        # quick-fix used to work in place, in the session's own folder
        if check["session_cwd"].strip():
            return check["session_cwd"]
    setup = label_responses.get("worktree-setup")
    if isinstance(setup, dict):
        text = setup.get("output")
        try:
            parsed = json.loads(text) if isinstance(text, str) else setup
        except ValueError:
            parsed = None
        if isinstance(parsed, dict) and isinstance(parsed.get("worktree_path"), str):
            return parsed["worktree_path"] or None
    return None


def _scripted_branch(label_responses: dict[str, Any]) -> str | None:
    """The branch a legacy quick-fix fixture scripted for its isolation check, if any.

    The old quick-fix workflow read the branch it was on from the isolation check
    (``initial_branch``) and reported it; the ready answer now carries the branch,
    so a fixture's scripted branch is kept as the ready answer's branch.
    """
    check = label_responses.get("isolation-check")
    if isinstance(check, dict):
        branch = check.get("initial_branch")
        if isinstance(branch, str) and branch.strip():
            return branch
    return None


def default_workspace_args(
    script_path: Path, args: dict[str, Any], label_responses: dict[str, Any]
) -> dict[str, Any]:
    """Ready workspace answer, handed in as ``args.workspace`` (BO-4300c-3).

    The location is the run's own ``worktree_path`` / ``caller_worktree_path``
    arg, else the location a legacy fixture scripted, else a fixed harness
    location. Empty for a script without a workspace step, for a run that
    already hands the maker's answer in as ``args.workspace``, and for a run
    whose caller scripts the workspace step's own reply (that test is about the
    workspace step).
    """
    label = workspace_step_label(script_path)
    if label is None or "workspace" in args or label in label_responses:
        return {}
    path = (
        args.get("worktree_path")
        or args.get("caller_worktree_path")
        or _scripted_location(label_responses)
        or DEFAULT_WORKSPACE_PATH
    )
    answer = ready_workspace_args(path)
    branch = _scripted_branch(label_responses)
    if branch is not None:
        answer["workspace"]["branch"] = branch
    return answer


def default_workspace_label_responses(
    script_path: Path, args: dict[str, Any], label_responses: dict[str, Any]
) -> dict[str, Any]:
    """Ready workspace answer scripted for the workspace step's own label.

    The ``workspace_default="label"`` form of ``default_workspace_args``: the run
    still makes the ONE maker dispatch, and that dispatch is answered ready. For
    a test whose subject is that dispatch (which workflows make one, what it
    carries) and so must observe it, which the ``args.workspace`` form hides.
    Empty for a script without a workspace step, a run that hands in
    ``args.workspace``, and a run whose caller scripts the label itself.
    """
    label = workspace_step_label(script_path)
    if label is None or "workspace" in args or label in label_responses:
        return {}
    path = args.get("worktree_path") or args.get("caller_worktree_path") or DEFAULT_WORKSPACE_PATH
    return {label: ready_workspace_args(path)["workspace"]}


def apply_workspace_defaults(
    script_path: Path,
    args: dict[str, Any],
    label_responses: dict[str, Any],
    mode: str = "args",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return ``(args, label_responses)`` with the workspace defaults applied.

    ``mode`` is the harness's ``workspace_default``: ``"args"`` hands a ready
    answer in as ``args.workspace`` and carries a legacy fixture across;
    ``"label"`` scripts the ready answer as the maker dispatch's reply (the run
    still makes that dispatch); ``"none"`` returns both unchanged. A caller's own
    value always wins.
    """
    if mode == "none":
        return args, label_responses
    if mode == "label":
        extra = default_workspace_label_responses(script_path, args, label_responses)
        return args, {**extra, **label_responses}
    if mode != "args":
        raise ValueError(f"workspace_default must be 'args', 'label' or 'none', got {mode!r}")  # noqa: TRY003
    merged_args = {**default_workspace_args(script_path, args, label_responses), **args}
    legacy_args, legacy_labels = legacy_workspace_fixtures(script_path, merged_args, label_responses)
    return {**legacy_args, **merged_args}, {**label_responses, **legacy_labels}


def has_derivable_project_root(args: dict[str, Any]) -> bool:
    """True when the WORKSPACE-ANSWER block can read a project root off ``args``.

    Mirrors ``workspaceProjectRoot`` in templates/workflows-js/_shared/workspace-answer.js:
    an explicit ``project_root`` / ``repo_root``, or an absolute work-store path
    under ``<root>/tickets/``.
    """
    for key in ("project_root", "repo_root"):
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            return True
    for key in ("ticket_path", "epic_path", "target"):
        value = args.get(key)
        if not isinstance(value, str):
            continue
        norm = value.replace("\\", "/")
        at = norm.find("/tickets/")
        if at > 0 and (norm.startswith("/") or re.match(r"^[A-Za-z]:/", norm)):
            return True
    return False


def _legacy_location(reply: Any) -> str | None:
    """The location an OLD-shaped workspace reply names, else None.

    Old shape: no ``status``, no ``workspace_path``, a location under
    ``worktree_path`` (the setup agents) or ``worktree_root`` (finalize's
    pre-flight, ``found`` not false).
    """
    if not isinstance(reply, dict) or "status" in reply or "workspace_path" in reply:
        return None
    if reply.get("found") is False:
        return None
    for key in ("worktree_path", "worktree_root"):
        value = reply.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def legacy_workspace_fixtures(
    script_path: Path, args: dict[str, Any], label_responses: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Carry a pre-BO-4300c-3 fixture across to the one-way workspace step.

    Before BO-4300c-3 a test scripted the workspace step's label with the OLD
    reply shape (a ``worktree_path`` or ``worktree_root``, no ``status``) and
    passed no project root. The workflow now asks the maker only when it can
    name a project root, and accepts only ``status == "ok"`` with a
    ``workspace_path`` (BO-4300c-2). For a run in exactly that legacy position
    this returns (extra args, replacement label_responses): a default project
    root, and the scripted reply restated in the maker's ready shape. A run that
    gives a project root, hands in ``args.workspace``, scripts no workspace
    reply, or scripts a reply that already carries ``workspace_path`` or a
    ``status`` is left exactly as the caller wrote it, so a test about a
    hostile or refused answer still sends that answer verbatim.
    """
    label = workspace_step_label(script_path)
    if label is None or "workspace" in args or label not in label_responses:
        return {}, {}
    reply = label_responses[label]
    extra_args: dict[str, Any] = {}
    if not has_derivable_project_root(args):
        extra_args["project_root"] = DEFAULT_PROJECT_ROOT
    if label == "pre-flight" and not (args.get("target") or args.get("target_branch")):
        # finalize names its workspace by the target it was asked to finalize; a
        # run that names none cannot ask the maker (it used to read the cwd).
        extra_args["target"] = DEFAULT_FINALIZE_TARGET
    location = _legacy_location(reply)
    if location is None:
        return extra_args, {}
    return extra_args, {label: {**reply, "status": "ok", "workspace_path": location}}
