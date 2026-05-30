"""
MODULE: auto_commit_inbox_ticket.py
GOAL: PostToolUse hook that automatically stages, commits, and pushes any
    standalone ``.md`` file written directly to ``tickets/00_inbox/`` so that
    newly created tickets appear on ``origin/main`` immediately after
    ``create-ticket`` writes them — no manual commit step required.
BUSINESS CONTEXT: When ``create-ticket`` finishes it writes a ticket file to
    ``tickets/00_inbox/`` with a date-stamped filename.  In practice, users have had
    to manually ask Claude to commit and push these files.  Inbox tickets are
    just work-item definitions — they contain no implementation code, no
    secrets, and no partial state — so committing them immediately is always
    safe.  The only constraints are:
      1. Do not commit if the file is already in a clean committed state
         (idempotency).
      2. Do not push if the current branch is not ``main`` (avoids polluting a
         feature branch with ticket commits).
      3. Do not push if we are inside a git worktree whose branch is not
         ``main`` (worktrees are always feature branches; their ticket work is
         bundled by ``create-epic`` in its Phase 5 commit).
      4. Do not trigger for paths inside ``tickets/00_inbox/epics/`` or any
         deeper subdirectory — those are managed by the epic workflow which
         does its own bundled commit.
    Known limitation: ``git push origin main`` pushes the entire ``main``
    branch, not just the new file.  This is safe for inbox tickets (they are
    always additive) but means any other uncommitted local changes on ``main``
    would also be pushed if present.  The ``_is_already_committed`` guard and
    the branch guard together ensure we only push when on a clean ``main``
    with a single new file staged.  The hook does not verify that ``main`` has
    no other staged changes.
ARCHITECTURE: PostToolUse hook on ``Edit|Write`` tool calls.  Receives the
    tool payload as JSON on stdin.  Exits 0 unconditionally (PostToolUse hooks
    cannot block tool execution).  Follows the same structural pattern as
    ``check_ticket_rename_tracking.py`` and ``ticket_frontmatter_guard.py``:
    a Python script registered in ``templates/settings.json`` under the
    ``PostToolUse / Edit|Write`` matcher, receiving the tool payload as JSON
    on stdin.

PostToolUse hook contract (Edit|Write tool):
- stdout is shown to the agent as informational feedback
- exit code is ignored (PostToolUse hooks cannot block)
- the hook should be idempotent and safe to run multiple times

DECISION HISTORY
- 2026-05-30 [TICKET-20260530-AutoCommitInboxTicket]: Initial implementation.
  Adds automatic commit-and-push for standalone inbox tickets written to
  ``tickets/00_inbox/`` on the ``main`` branch.  Guards: idempotency check,
  branch guard, worktree guard, epic-subfolder exclusion.  Fail-open on all
  errors.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _is_target_path(file_path: str) -> bool:
    """Return True only when *file_path* is a direct child of ``tickets/00_inbox/``.

    Specifically, the path must have exactly 3 parts
    (``tickets``, ``00_inbox``, ``<name>.md``), the name must end with
    ``.md``, and the parent must be exactly ``tickets/00_inbox``.  Paths
    inside any subdirectory (e.g. ``tickets/00_inbox/epics/…``) return False.

    Args:
        file_path: Repo-relative path string to evaluate.

    Returns:
        True when the path is a direct ``.md`` child of ``tickets/00_inbox/``.
    """
    try:
        p = Path(file_path)
        parts = p.parts
        if len(parts) != 3:
            return False
        if parts[0] != "tickets" or parts[1] != "00_inbox":
            return False
        if not parts[2].endswith(".md"):
            return False
        return True
    except Exception:
        return False


def _find_repo_root(start: Path) -> Path | None:
    """Walk up from *start* to find the directory containing ``.git``.

    Args:
        start: Starting path (typically the directory containing the file
            being written).

    Returns:
        The directory that contains a ``.git`` entry (file or directory), or
        None if no such directory is found before the filesystem root.
    """
    current = start.resolve()
    while True:
        if (current / ".git").exists():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def _current_branch(repo_root: Path) -> str:
    """Return the current git branch name for the repo at *repo_root*.

    Args:
        repo_root: Absolute path to the repository root (the directory that
            contains ``.git``).

    Returns:
        The branch name string, or ``""`` on any error.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode != 0:
            return ""
        return result.stdout.strip()
    except OSError:
        return ""


def _is_worktree(repo_root: Path) -> bool:
    """Return True when *repo_root* is a linked git worktree (not the main worktree).

    A main worktree has its ``.git`` as a directory ending in ``/.git``.
    A linked worktree has a ``.git`` *file* whose content points to
    ``.git/worktrees/<name>`` inside the main repo.

    We detect this by running ``git rev-parse --git-dir`` and checking whether
    the output path contains ``.git/worktrees/``.

    Args:
        repo_root: Absolute path to the repository root.

    Returns:
        True when inside a linked worktree; False when in the main worktree or
        on any error (fail-open).
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode != 0:
            return False  # fail-open
        git_dir = result.stdout.strip()
        # A linked worktree's --git-dir output contains '.git/worktrees/'
        return ".git/worktrees/" in git_dir
    except OSError:
        return False  # fail-open


def _is_already_committed(file_path: str, repo_root: Path) -> bool:
    """Return True when *file_path* is tracked and has no pending changes.

    Runs ``git status --porcelain -- <file_path>``.  An empty stdout means
    the file is tracked and clean (already committed).

    Args:
        file_path: Repo-relative path to the file.
        repo_root: Absolute path to the repository root.

    Returns:
        True when the file is already committed and clean; False otherwise or
        on any error (fail-open — prefer committing over silently skipping).
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "status", "--porcelain", "--", file_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode != 0:
            return False  # fail-open
        return result.stdout.strip() == ""
    except OSError:
        return False  # fail-open


def _run_commit_and_push(file_path: str, repo_root: Path) -> str:
    """Stage, commit, and push *file_path* to ``origin main``.

    Runs the three-step sequence:
      1. ``git -C <repo_root> add <file_path>``
      2. ``git -C <repo_root> commit -m "chore(tickets): add <basename>"``
      3. ``git -C <repo_root> push origin main``

    Args:
        file_path: Repo-relative path to the file to commit.
        repo_root: Absolute path to the repository root.

    Returns:
        ``"ok"`` on full success, ``"commit_failed: <stderr>"`` if the commit
        step fails, or ``"push_failed: <stderr>"`` if the push step fails.
    """
    basename = Path(file_path).stem  # filename without extension

    # Step 1: stage
    try:
        add_result = subprocess.run(
            ["git", "-C", str(repo_root), "add", file_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if add_result.returncode != 0:
            return f"commit_failed: git add failed: {add_result.stderr.strip()}"
    except OSError as exc:
        return f"commit_failed: git add raised {exc}"

    # Step 2: commit
    try:
        commit_result = subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                "commit",
                "-m",
                f"chore(tickets): add {basename}",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if commit_result.returncode != 0:
            return f"commit_failed: {commit_result.stderr.strip()}"
    except OSError as exc:
        return f"commit_failed: git commit raised {exc}"

    # Step 3: push
    try:
        push_result = subprocess.run(
            ["git", "-C", str(repo_root), "push", "origin", "main"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if push_result.returncode != 0:
            return f"push_failed: {push_result.stderr.strip()}"
    except OSError as exc:
        return f"push_failed: git push raised {exc}"

    return "ok"


def main() -> None:
    """Entry point.  Reads PostToolUse payload from stdin and acts on it."""
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        # Fail-open: malformed stdin should never block
        sys.exit(0)

    try:
        tool_input = payload.get("tool_input") or {}
        file_path_raw: str = str(tool_input.get("file_path") or "")
    except Exception:
        sys.exit(0)

    if not file_path_raw:
        sys.exit(0)

    # Attempt to find repo root from the file's location
    try:
        # file_path_raw may be absolute or relative; find the repo root
        abs_candidate = Path(file_path_raw)
        if abs_candidate.is_absolute():
            start = abs_candidate.parent
        else:
            start = Path.cwd()

        repo_root = _find_repo_root(start)
        if repo_root is None:
            # Not in a git repo at all — no-op
            sys.exit(0)

        # Normalise to repo-relative path
        try:
            if abs_candidate.is_absolute():
                file_path = str(abs_candidate.relative_to(repo_root))
            else:
                file_path = file_path_raw
        except ValueError:
            # file_path_raw is absolute but not under repo_root
            file_path = file_path_raw

        # Guard 1: is this a direct inbox ticket?
        if not _is_target_path(file_path):
            sys.exit(0)

        # Guard 2: not inside a linked worktree
        if _is_worktree(repo_root):
            print(
                f"[auto-commit-inbox] skipped: running inside a git worktree — "
                f"not pushing to main from a feature context ({file_path})"
            )
            sys.exit(0)

        # Guard 3: must be on main branch
        branch = _current_branch(repo_root)
        if branch != "main":
            print(
                f"[auto-commit-inbox] skipped: current branch is '{branch}', "
                f"not 'main' — push skipped for {file_path}"
            )
            sys.exit(0)

        # Guard 4: idempotency — already committed?
        if _is_already_committed(file_path, repo_root):
            # Silently no-op
            sys.exit(0)

        # All guards passed — commit and push
        result = _run_commit_and_push(file_path, repo_root)
        basename = Path(file_path).name

        if result == "ok":
            print(
                f"[auto-commit-inbox] committed and pushed: {basename} → origin/main"
            )
        elif result.startswith("commit_failed"):
            print(
                f"[auto-commit-inbox] WARNING: commit failed for {basename}: "
                f"{result}"
            )
        elif result.startswith("push_failed"):
            print(
                f"[auto-commit-inbox] WARNING: push failed for {basename}: "
                f"{result}"
            )
        else:
            print(f"[auto-commit-inbox] WARNING: unexpected result: {result}")

    except Exception as exc:
        # Fail-open: no error in this hook should ever block tool execution
        print(f"[auto-commit-inbox] WARNING: unexpected exception: {exc}")

    sys.exit(0)


if __name__ == "__main__":
    main()
