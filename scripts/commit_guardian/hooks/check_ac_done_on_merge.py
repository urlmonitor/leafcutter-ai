"""
MODULE: scripts/commit_guardian/hooks/check_ac_done_on_merge.py
GOAL: Post-merge hook that marks ACs done for all source_ac tickets in the merge.
BUSINESS CONTEXT: Ticket 03 — AC done-linker. Fires after a ticket branch is
    merged into main. Reads the changed files from the merge diff, filters to
    ticket files with status: done and source_ac set, and invokes mark_ac_done.py
    for each such ticket. Non-fatal: any per-ticket failure is logged and skipped
    so the hook never blocks the merge.
ARCHITECTURE: Post-merge hook script. Uses subprocess.run(['git', 'diff', ...])
    to discover changed files (diff approach — approved by architect-review).
    Supports LEAFCUTTER_FAKE_GIT_DIFF env var for test injection.
    Supports LEAFCUTTER_AC_ROOT env var to override the AC store root.
    Exit code: always 0.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import yaml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SCRIPT_DIR = Path(__file__).resolve().parent
# _WORKTREE_ROOT resolution path:
#   This hook lives at .leafcutter/scripts/commit_guardian/hooks/check_ac_done_on_merge.py
#   on a consumer install (deployed by build.py into <project>/.leafcutter/).
#   Three .parent steps: hooks/ → commit_guardian/ → scripts/ → .leafcutter/
#   So _WORKTREE_ROOT resolves to the .leafcutter/ directory itself, and
#   _MARK_AC_DONE resolves to .leafcutter/scripts/ac_store/mark_ac_done.py —
#   which is exactly where build_ac_store() deploys the script (AC-5 clarity note).
_WORKTREE_ROOT = _SCRIPT_DIR.parent.parent.parent
_MARK_AC_DONE = _WORKTREE_ROOT / "scripts" / "ac_store" / "mark_ac_done.py"


def _get_changed_files() -> list[str]:
    """Return a list of file paths changed in the most recent merge commit.

    In test mode (when LEAFCUTTER_FAKE_GIT_DIFF is set in the environment),
    returns lines from that environment variable instead of invoking git.

    Returns:
        List of file path strings (one per changed file in the diff).
    """
    fake_diff = os.environ.get("LEAFCUTTER_FAKE_GIT_DIFF")
    if fake_diff is not None:
        return [line.strip() for line in fake_diff.splitlines() if line.strip()]

    try:
        result = subprocess.run(
            ["git", "diff", "HEAD~1", "HEAD", "--name-only"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            print(
                f"[check_ac_done_on_merge] WARNING: git diff failed: {result.stderr.strip()}",
                file=sys.stderr,
            )
            return []
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except (OSError, subprocess.SubprocessError) as exc:
        print(
            f"[check_ac_done_on_merge] WARNING: cannot run git diff: {exc}",
            file=sys.stderr,
        )
        return []


def _read_ticket_frontmatter(ticket_path: Path) -> Optional[dict]:
    """Parse YAML frontmatter from a ticket markdown file.

    Args:
        ticket_path: Absolute or relative path to the ticket markdown file.

    Returns:
        Parsed frontmatter dict, or None if absent or unreadable.
    """
    try:
        content = ticket_path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not content.startswith("---"):
        return None
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        data = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def _invoke_mark_ac_done(ticket_path: Path, ac_root: Path) -> bool:
    """Invoke mark_ac_done.py for a given ticket, capturing the result.

    Args:
        ticket_path: Path to the ticket file with source_ac set.
        ac_root: Root directory of the AC YAML store.

    Returns:
        True if mark_ac_done exited 0, False otherwise.
    """
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(_MARK_AC_DONE),
                "--ticket", str(ticket_path),
                "--ac-root", str(ac_root),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(
            f"[check_ac_done_on_merge] WARNING: cannot invoke mark_ac_done for "
            f"{ticket_path.name}: {exc}",
            file=sys.stderr,
        )
        return False
    else:
        if result.stdout.strip():
            print(f"[check_ac_done_on_merge] {result.stdout.strip()}")
        if result.returncode != 0 and result.stderr.strip():
            print(
                f"[check_ac_done_on_merge] WARNING: mark_ac_done failed for "
                f"{ticket_path.name}: {result.stderr.strip()}",
                file=sys.stderr,
            )
        return result.returncode == 0


# ---------------------------------------------------------------------------
# Main hook logic
# ---------------------------------------------------------------------------


def run() -> int:
    """Post-merge hook entry point.

    Returns:
        Always 0 — hook failure must not block the merge.
    """
    ac_root_override = os.environ.get("LEAFCUTTER_AC_ROOT")
    ac_root = Path(ac_root_override) if ac_root_override else Path("docs/acceptance-criteria/")

    changed_files = _get_changed_files()

    ticket_files = [
        f for f in changed_files
        if "tickets/" in f.replace("\\", "/") and f.endswith(".md")
    ]

    if not ticket_files:
        # Also handle absolute paths passed via LEAFCUTTER_FAKE_GIT_DIFF
        ticket_files = [f for f in changed_files if f.endswith(".md")]

    marked = 0
    skipped = 0
    failed = 0

    for file_str in ticket_files:
        ticket_path = Path(file_str)
        if not ticket_path.is_absolute():
            ticket_path = Path.cwd() / ticket_path

        if not ticket_path.exists():
            print(
                f"[check_ac_done_on_merge] WARNING: ticket file not found: {ticket_path}",
                file=sys.stderr,
            )
            skipped += 1
            continue

        frontmatter = _read_ticket_frontmatter(ticket_path)
        if frontmatter is None:
            skipped += 1
            continue

        ticket_status = frontmatter.get("status", "")
        source_ac = frontmatter.get("source_ac")

        if ticket_status != "done":
            print(
                f"[check_ac_done_on_merge] skipped {ticket_path.name} "
                f"(status={ticket_status!r}, not done)"
            )
            skipped += 1
            continue

        if not source_ac:
            print(
                f"[check_ac_done_on_merge] skipped {ticket_path.name} (no source_ac field)"
            )
            skipped += 1
            continue

        success = _invoke_mark_ac_done(ticket_path, ac_root)
        if success:
            marked += 1
        else:
            failed += 1

    print(
        f"[check_ac_done_on_merge] done: {marked} marked, {skipped} skipped, {failed} failed"
    )
    # Always exit 0 — hook failure must not block the merge
    return 0


if __name__ == "__main__":
    sys.exit(run())
