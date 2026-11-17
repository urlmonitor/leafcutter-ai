"""
MODULE: _lint_git
GOAL: Give check_lint_gate.py and its helpers ONE way to ask git about the
    commit being made: the staged set, an index blob, a HEAD blob. Every
    answer is read through git commands against the INDEX the hook was handed,
    never from the working tree and never from `.git/index` directly.
BUSINESS CONTEXT: BP-1300e-1-ii requires each staged file to be judged as it
    will be committed. `git commit -- <paths>`, `git commit -a` and `--only`
    run hooks against a TEMPORARY index named by GIT_INDEX_FILE; a helper that
    strips GIT_* variables, or reads `.git/index`, would judge content that is
    not the content being committed. Every call here inherits the hook's
    environment unchanged (it only ADDS GIT_LITERAL_PATHSPECS so a file name
    containing a glob character is a name, not a pattern).
ARCHITECTURE: Stdlib only, no {{config.*}} tokens (build.py's inject_config
    rewrites contiguous config literals in deployed .py), no leafcutter imports.
    Any git failure is raised as GitError carrying git's own stderr; the caller
    (check_lint_gate.py) converts it to a could_not_check outcome -- an empty
    answer is never fabricated from a failed call.

DECISION HISTORY
- 2026-10-12 [python-coder/BP-1300e-1-ii]: Created. The staged set is read with
    `git diff --cached --raw -z --no-renames --diff-filter=ACMR` (not
    `--name-only`) so gitlink entries (mode 160000) can be recognised and
    skipped; `--no-renames` reports a rename as a delete plus an add, which
    yields the same inspected set as judging a rename at its new path.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

GITLINK_MODE = "160000"


class GitError(Exception):
    """git could not answer a question the gate needs answered."""


def run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run ``git <args>`` in *cwd*, inheriting the hook's environment.

    Args:
        args: git arguments (without the leading ``git``).
        cwd: The subject root.

    Returns:
        The completed process (bytes output); the caller inspects the code.

    Raises:
        GitError: If git cannot be launched at all.
    """
    env = {**os.environ, "GIT_LITERAL_PATHSPECS": "1"}
    try:
        return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, check=False, env=env)
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("cannot run git %s: %s", args[:1], exc)
        msg = f"cannot run git {' '.join(args[:2])}: {exc}"
        raise GitError(msg) from exc


def _checked(args: list[str], cwd: Path) -> bytes:
    """Run git and return stdout, raising GitError on a non-zero exit."""
    proc = run_git(args, cwd)
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip() or "no message"
        msg = f"git {' '.join(args[:2])} exited {proc.returncode}: {detail}"
        raise GitError(msg)
    return proc.stdout


def parse_raw_z(data: bytes) -> list[str]:
    """Parse ``git diff --raw -z`` output (no renames) into repo-relative paths.

    Gitlink entries (new mode 160000) are skipped: they are not files.

    Args:
        data: Raw NUL-separated output: ``:<omode> <nmode> <osha> <nsha> <st>``
            then the path, repeated.

    Returns:
        Paths in git's order.
    """
    fields = data.split(b"\0")
    paths: list[str] = []
    for meta, path in zip(fields[0::2], fields[1::2], strict=False):
        parts = meta.decode("utf-8", "replace").lstrip(":").split()
        if len(parts) >= 2 and parts[1] == GITLINK_MODE:
            continue
        paths.append(path.decode("utf-8", "surrogateescape"))
    return paths


def staged_paths(root: Path) -> list[str]:
    """Return the staged paths added/copied/modified, as the commit will have them."""
    args = ["diff", "--cached", "--raw", "-z", "--no-renames", "--diff-filter=ACMR"]
    return parse_raw_z(_checked(args, root))


def in_index(root: Path, rel: str) -> bool:
    """True when *rel* is a tracked path of the (possibly temporary) index."""
    return bool(_checked(["ls-files", "--stage", "-z", "--", rel], root))


def index_blob(root: Path, rel: str) -> bytes | None:
    """Return the staged bytes of *rel*, or None when it is not in the index."""
    if not in_index(root, rel):
        return None
    return _checked(["show", f":{rel}"], root)


def has_head(root: Path) -> bool:
    """True when the repository has a HEAD commit to compare against."""
    proc = run_git(["rev-parse", "--verify", "--quiet", "HEAD"], root)
    if proc.returncode == 0:
        return True
    if proc.returncode == 1:
        return False
    detail = proc.stderr.decode("utf-8", "replace").strip() or "no message"
    msg = f"git rev-parse exited {proc.returncode}: {detail}"
    raise GitError(msg)


def head_blob(root: Path, rel: str) -> bytes | None:
    """Return *rel* as committed at HEAD, or None (new file, or no HEAD yet)."""
    if not has_head(root):
        return None
    if not _checked(["ls-tree", "-z", "--name-only", "HEAD", "--", rel], root):
        return None
    return _checked(["show", f"HEAD:{rel}"], root)
