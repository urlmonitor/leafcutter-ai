"""
MODULE: worktree_canaries
GOAL: Prove, by a real operation each declared git stage rejects, that the
    protections a workspace DECLARES actually fire there (BO-4300c-1, c-1-i,
    c-1-ii, c-1-iii).
BUSINESS CONTEXT: Split out of worktree_readiness.py (file-size limit). A
    stage that is declared but cannot be shown to reject its known-bad input
    is reported as not firing, which readiness turns into a HOOKS_INACTIVE
    refusal. Canaries leave the branch tip, index and tree exactly as before.
ARCHITECTURE: Stdlib-only; deployed beside worktree_readiness.py (NAMED entry
    in the build deploy manifest). Every git call goes through
    ``worktree_git.run_git`` (working directory = the workspace, never
    ``git -C``). The stage set comes from the workspace's own generated
    ``.pre-commit-config.yaml``; the known-bad input for each stage comes
    from the install's own ``commit_guardian.json`` (``stage_canaries``).
    Shims are installed by the install's own ``install_pre_commit_shims.py``
    run as a separate process.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import worktree_answer as wa
import worktree_git as wg

_log = logging.getLogger(__name__)

_NON_GIT_STAGES = frozenset({"manual"})  # only ever run explicitly, never by a git operation
_ID = ["-c", "user.name=leafcutter-canary", "-c", "user.email=canary@leafcutter.invalid",
       "-c", "commit.gpgsign=false"]
_CANARY_REF = "refs/leafcutter/canary-post-merge"
_STAGES_KEY = re.compile(r"^(\s*)(?:-\s+)?stages:\s*(.*)$")
_LIST_ITEM = re.compile(r"^(\s*)-\s+([\w.-]+)\s*$")


def install_dir(workspace: Path) -> Path | None:
    """Return the workspace's own install root (holds ``scripts/commit_guardian``), or ``None``."""
    for candidate in (workspace / ".leafcutter", workspace):
        if (candidate / "scripts" / "commit_guardian").is_dir():
            return candidate
    return None


def declared_stages(workspace: Path) -> list[str]:
    """Return the git stages the workspace's own ``.pre-commit-config.yaml`` names (sorted).

    Reads every ``stages:`` key -- inline ``[a, b]`` or block list, including
    PyYAML's column-0 block lists (items at the key's own indent) -- which is
    the same source ``install_pre_commit_shims.collect_stages`` reads; the
    maker stays stdlib-only so it does not import that module. ``manual`` is
    never a git stage and is left out.
    """
    try:
        lines = (workspace / ".pre-commit-config.yaml").read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        _log.warning("declared_stages: cannot read the hook declaration: %s", exc)
        return []
    found: set[str] = set()
    for index, raw in enumerate(lines):
        match = _STAGES_KEY.match(raw.split("#", 1)[0].rstrip())
        if not match:
            continue
        inline = match.group(2).strip()
        if inline.startswith("["):
            found.update(s.strip().strip("'\"") for s in inline.strip("[]").split(",") if s.strip())
            continue
        for follow in lines[index + 1:]:
            item = _LIST_ITEM.match(follow.split("#", 1)[0].rstrip())
            if not item or len(item.group(1)) < len(match.group(1)):
                if follow.strip() and not follow.strip().startswith("#"):
                    break
                continue
            found.add(item.group(2))
    return sorted(found - _NON_GIT_STAGES)


def install_shims(workspace: Path) -> None:
    """Run the install's own shim installer (separate process, cwd = workspace); log, never raise."""
    root = install_dir(workspace)
    script = root / "scripts" / "commit_guardian" / "install_pre_commit_shims.py" if root else None
    if script is None or not script.is_file():
        _log.warning("install_shims: the install ships no shim installer under %s", root)
        return
    try:
        proc = subprocess.run([sys.executable, str(script)], cwd=str(workspace), capture_output=True,
                              text=True, timeout=120, check=False,
                              stdin=subprocess.DEVNULL, env=wg.git_env())
    except (OSError, subprocess.SubprocessError) as exc:
        _log.warning("install_shims: could not run %s: %s", script, exc)
        return
    wa.forward_child_output(proc)
    if proc.returncode != 0:
        _log.warning("install_shims: %s exited %s", script, proc.returncode)


def stage_canaries(workspace: Path) -> dict[str, Any]:
    """Return the install's own declaration of each stage's known-bad input (``{}`` when absent)."""
    root = install_dir(workspace)
    path = root / "scripts" / "commit_guardian" / "commit_guardian.json" if root else None
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path and path.is_file() else {}
    except (OSError, json.JSONDecodeError) as exc:
        _log.warning("stage_canaries: cannot read the canary declaration: %s", exc)
        return {}
    declared = data.get("stage_canaries") if isinstance(data, dict) else None
    return declared if isinstance(declared, dict) else {}


def hooks_dir(workspace: Path) -> Path | None:
    """Resolve the workspace's effective hooks directory (``core.hooksPath`` if set, else the common git dir)."""
    configured = wg.git_config_get(workspace, "core.hooksPath")
    if configured:
        path = Path(configured).expanduser()
        return path if path.is_absolute() else (workspace / path).resolve()
    proc = wg.run_git(["rev-parse", "--git-common-dir"], workspace)
    common = proc.stdout.strip()
    if proc.returncode != 0 or not common:
        return None
    path = Path(common)
    return (path if path.is_absolute() else (workspace / path).resolve()) / "hooks"


def _write_bad_file(workspace: Path, spec: dict[str, Any]) -> Path | None:
    """Write a stage canary's known-bad file (LF endings); ``None`` when the declaration is unusable."""
    rel = spec.get("path")
    content = spec.get("content", "leafcutter stage canary\n")  # keyed on the path, not the content
    if not isinstance(rel, str) or not isinstance(content, str):
        return None
    target = workspace / rel
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
    except OSError as exc:
        _log.warning("canary: cannot write %s: %s", target, exc)
        return None
    return target


_REJECT_MARKER = "PRECOMMIT_CANARY_REJECTED"


def _hook_rejected(result: subprocess.CompletedProcess) -> bool:
    """True when *result* failed AND its output carries the canary hook's own rejection marker."""
    return result.returncode != 0 and _REJECT_MARKER in f"{result.stdout}{result.stderr}"


def _hook_shim_exists(workspace: Path, stage: str) -> bool:
    """True when the workspace's own hooks directory holds a shim for *stage*."""
    hooks = hooks_dir(workspace)
    return bool(hooks and (hooks / stage).is_file())


def _pre_commit_fires(workspace: Path, spec: dict[str, Any], head: str) -> bool:
    """Commit the known-bad file; the canary fired when the commit is rejected."""
    target = _write_bad_file(workspace, spec)
    if target is None or not _hook_shim_exists(workspace, "pre-commit"):
        return False
    try:
        _git(workspace, "add", "--", str(spec["path"]))
        rejected = _hook_rejected(_git(workspace, *_ID, "commit", "-q", "-m", "leafcutter workspace canary"))
        if not rejected:
            return False
        # Control: the same commit must pass with hooks bypassed, so the rejection is the hook's.
        return _git(workspace, *_ID, "commit", "-q", "--no-verify", "-m", "leafcutter workspace canary"
                    ).returncode == 0
    finally:
        _git(workspace, "reset", "-q", "--hard", head)
        target.unlink(missing_ok=True)


def _commit_msg_fires(workspace: Path, spec: dict[str, Any], head: str) -> bool:
    """Run the commit-msg hook on the known-bad message; the canary fired when it is rejected.

    The hook is run directly (``git hook run commit-msg``) rather than through a
    real commit: ``git commit`` runs the pre-commit stage first, and with
    ``fail_fast`` a real pre-commit hook failing there would stop the commit
    before commit-msg ever ran, so the stage would be reported as not firing.
    """
    message = spec.get("message")
    if not isinstance(message, str) or not _hook_shim_exists(workspace, "commit-msg"):
        return False
    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", prefix="leafcutter-canary-msg-",
                                         delete=False)
    msg_file = Path(handle.name)
    try:
        with handle:
            handle.write(message + "\n")
    except OSError as exc:
        _log.warning("canary: cannot write %s: %s", msg_file, exc)
        msg_file.unlink(missing_ok=True)
        return False
    try:
        if not _hook_rejected(_git(workspace, "hook", "run", "commit-msg", "--", str(msg_file))):
            return False
        # Control: the same message must pass with hooks bypassed, so the rejection is the hook's.
        return _git(workspace, *_ID, "commit", "-q", "--allow-empty", "--no-verify", "-m", message).returncode == 0
    finally:
        _git(workspace, "reset", "-q", "--hard", head)
        msg_file.unlink(missing_ok=True)


def _post_merge_fires(workspace: Path, spec: dict[str, Any], head: str, branch: str) -> bool:
    """Merge a known-bad change in from a disposable ref; the canary fired when the hook reports failure.

    ``git merge`` ignores a post-merge hook's exit, so the hook is run again
    (``git hook run``) after the merge, with ORIG_HEAD/HEAD as the merge left
    them, and ITS exit is the answer. The branch itself is never moved: the
    work happens on a detached HEAD and the tip/index/tree are put back.
    """
    if not _hook_shim_exists(workspace, "post-merge"):
        return False
    target = None
    try:
        _git(workspace, "checkout", "-q", "--detach")
        target = _write_bad_file(workspace, spec)
        if target is None:
            return False
        _git(workspace, "add", "--", str(spec["path"]))
        if _git(workspace, *_ID, "commit", "-q", "--no-verify", "-m", "canary change").returncode != 0:
            return False
        _git(workspace, "update-ref", _CANARY_REF, "HEAD")
        _git(workspace, "reset", "-q", "--hard", head)
        merged = _git(workspace, *_ID, "merge", "-q", "--no-ff", "--no-verify", "-m", "canary merge", _CANARY_REF)
        if merged.returncode != 0:
            return False
        ran = _git(workspace, "hook", "run", "post-merge", "--", "0")
        return _hook_rejected(ran)
    finally:
        _git(workspace, "checkout", "-q", "-f", branch)
        _git(workspace, "reset", "-q", "--hard", head)
        _git(workspace, "update-ref", "-d", _CANARY_REF)
        if target is not None:
            target.unlink(missing_ok=True)


def run_canaries(workspace: Path, stages: list[str], branch: str) -> dict[str, bool]:
    """Show, per declared stage, whether a real operation it should reject is rejected.

    Precondition: the tracked tree is clean (the caller refuses otherwise).
    A declared stage with no declared canary input, or no canary kind this
    maker can drive, cannot be shown to fire and is ``False``.
    """
    head = _git(workspace, "rev-parse", "HEAD").stdout.strip()
    declared = stage_canaries(workspace)
    fired: dict[str, bool] = {}
    for stage in stages:
        spec = declared.get(stage)
        if not isinstance(spec, dict) or not head:
            fired[stage] = False
        elif stage == "pre-commit":
            fired[stage] = _pre_commit_fires(workspace, spec, head)
        elif stage == "commit-msg":
            fired[stage] = _commit_msg_fires(workspace, spec, head)
        elif stage == "post-merge":
            fired[stage] = _post_merge_fires(workspace, spec, head, branch)
        else:
            fired[stage] = False
    return fired


def _git(workspace: Path, *args: str) -> subprocess.CompletedProcess:
    """``git <args>`` with cwd = workspace (never ``-C``)."""
    return wg.run_git(list(args), workspace)


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-10-09 12:00 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05]: (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05)
#   Created: the canary-proving group (declared_stages, stage_canaries,
#   hooks_dir, install_shims, run_canaries and the per-stage canaries) moved
#   out of worktree_readiness.py, which was over the file-size limit. Pure
#   move, no behaviour change; worktree_readiness re-imports the public
#   names. (ADR-018)
# ===========================================================================
