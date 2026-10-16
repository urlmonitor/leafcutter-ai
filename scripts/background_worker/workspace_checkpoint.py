"""Detect edits to preserved work before reusing its checked prerequisite evidence."""
import hashlib
import json
import logging
import os
from pathlib import Path
import stat

from .execution_boundary import ExecutorError
from .git_ops import GitOps

LOGGER = logging.getLogger(__name__)


def fingerprint(git, run):
    root = git.assert_workspace(run)
    names = git.git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard").split("\0")
    entries = []
    try:
        for name in sorted(set(names) - {""}):
            path = root / name
            if Path(name).is_absolute() or ".." in Path(name).parts:
                raise ExecutorError("Invalid worktree path during evidence verification")
            for parent in path.parents:
                if parent == root:
                    break
                if parent.is_symlink():
                    raise ExecutorError("Worktree path traverses a symlink during evidence verification")
            if path.is_symlink():
                value = ["symlink", os.readlink(path)]
            elif not path.exists():
                value = ["missing"]
            elif path.is_file():
                value = ["file", stat.S_IMODE(path.stat().st_mode), hashlib.sha256(path.read_bytes()).hexdigest()]
            else:
                raise ExecutorError("Unsupported directory/submodule in worktree evidence: " + name)
            entries.append([name, value])
        head = git.head(root)
        index = git.git(root, "ls-files", "--stage", "-z")
        digest = hashlib.sha256(json.dumps([head, index, entries], ensure_ascii=True).encode()).hexdigest()
        return {"head_sha": head, "digest": digest}
    except OSError as exc:
        LOGGER.warning("Cannot inspect preserved worktree: %s", type(exc).__name__)
        raise ExecutorError("Cannot verify preserved worktree evidence") from exc


def execute_phase(engine, phase, run):
    real_git = isinstance(engine.git, GitOps)
    if real_git and run.get("workspace") and phase != "prepare":
        saved = run["payload"].get("workspace_checkpoint")
        if saved is None or fingerprint(engine.git, run) != saved:
            raise ExecutorError("Preserved worktree changed or lacks checkpoint evidence; human reconciliation required")
    try:
        return getattr(engine, "_" + phase)(run)
    finally:
        # Preserve changes made by a finished attempt/check, including needs-input
        # and draining. Unknown still-in-flight effects retain their old proof.
        current = engine.store.get_run(run["id"])
        if real_git and current.get("workspace") and not current["payload"].get("in_flight"):
            engine.store.checkpoint(run["id"], current["state"],
                                    {"workspace_checkpoint": fingerprint(engine.git, current)})
