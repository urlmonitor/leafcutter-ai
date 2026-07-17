"""
MODULE: check_ac_done_on_merge
GOAL: Post-merge hook that marks source ACs as work_status: done when ticket
      files are updated to status: done in a merge commit.
BUSINESS CONTEXT: After a ticket-linked merge lands, the source AC in the AC
    YAML store must be automatically closed (work_status: done) so the AC
    coverage dashboard stays accurate without manual intervention. This hook
    reads the merge diff, finds changed ticket markdown files, and invokes
    mark_ac_done.py for each ticket that has status: done and a source_ac
    field in its YAML frontmatter.
    Non-fatal: any per-ticket failure is logged and skipped so the hook never
    blocks a merge (exit code is always 0).
ARCHITECTURE: Standalone post-merge hook script with no leafcutter-internal
    imports. Supports LEAFCUTTER_FAKE_GIT_DIFF env var for test injection of
    diff output, and LEAFCUTTER_AC_ROOT env var for AC root directory override.
    Changed ticket paths are read from the diff; each is parsed for status and
    source_ac frontmatter fields. Qualifying tickets are processed by invoking
    mark_ac_done.py as a subprocess. The hook always exits 0.

Exit Codes:
    0 - Always (non-fatal post-merge hook).

Usage:
    python scripts/commit_guardian/hooks/check_ac_done_on_merge.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import yaml

_HOOK_NAME = "check-ac-done-on-merge"


def _get_diff_paths() -> list[str]:
    """Return changed file paths from the merge diff or an injected env var.

    When ``LEAFCUTTER_FAKE_GIT_DIFF`` is set in the environment, its value is
    returned as a newline-split list of paths (used by tests). Otherwise, the
    real diff is obtained via ``git diff --name-only HEAD~1 HEAD``.

    Returns:
        List of file path strings listed in the diff output.
    """
    fake = os.environ.get("LEAFCUTTER_FAKE_GIT_DIFF")
    if fake is not None:
        return [line for line in fake.splitlines() if line.strip()]

    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except subprocess.SubprocessError as exc:
        print(
            f"[{_HOOK_NAME}] WARNING: git diff failed: {exc}",
            file=sys.stderr,
        )
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def _read_ticket_frontmatter(ticket_path: Path) -> dict:
    """Parse YAML frontmatter from a ticket markdown file.

    Reads the file, splits on the ``---`` delimiter, and parses the first
    YAML block. Returns an empty dict when the file is unreadable, not
    frontmatter-prefixed, or the frontmatter is not valid YAML.

    Args:
        ticket_path: Path to the ticket ``.md`` file.

    Returns:
        Parsed frontmatter dict, or empty dict on any parse failure.
    """
    try:
        content = ticket_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(
            f"[{_HOOK_NAME}] WARNING: Cannot read ticket {ticket_path}: {exc}",
            file=sys.stderr,
        )
        return {}

    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}

    try:
        data = yaml.safe_load(parts[1])
    except yaml.YAMLError as exc:
        print(
            f"[{_HOOK_NAME}] WARNING: Cannot parse frontmatter in {ticket_path}: {exc}",
            file=sys.stderr,
        )
        return {}

    return data if isinstance(data, dict) else {}


def _get_ac_root() -> Path:
    """Return the AC root directory from the environment or the project default.

    Reads ``LEAFCUTTER_AC_ROOT`` when set; falls back to
    ``docs/acceptance-criteria`` relative to the current working directory.

    Returns:
        Path to the AC root directory.
    """
    ac_root_env = os.environ.get("LEAFCUTTER_AC_ROOT")
    if ac_root_env:
        return Path(ac_root_env)
    return Path("docs/acceptance-criteria")


def _get_mark_script_path() -> Path:
    """Return the absolute path to mark_ac_done.py.

    Resolves ``scripts/ac_store/mark_ac_done.py`` relative to this hook's
    own location by walking three parent directories up from the hook script
    (``hooks/`` → ``commit_guardian/`` → ``scripts/``) then descending into
    ``ac_store/``.

    Returns:
        Absolute path to mark_ac_done.py.
    """
    return Path(__file__).resolve().parent.parent.parent / "ac_store" / "mark_ac_done.py"


def _mark_ac_done_for_ticket(ticket_path: Path, ac_root: Path) -> None:
    """Invoke mark_ac_done.py for one ticket. Logs on failure; never raises.

    Calls ``mark_ac_done.py --ticket <path> --ac-root <root>`` as a subprocess.
    Failures (subprocess error or non-zero exit) are logged to stderr and the
    function returns normally so the hook can continue with the next ticket.

    Args:
        ticket_path: Absolute path to the ticket markdown file.
        ac_root: Root directory for AC YAML file lookup.
    """
    mark_script = _get_mark_script_path()
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(mark_script),
                "--ticket",
                str(ticket_path),
                "--ac-root",
                str(ac_root),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except subprocess.SubprocessError as exc:
        print(
            f"[{_HOOK_NAME}] WARNING: Failed to invoke mark_ac_done "
            f"for {ticket_path.name}: {exc}",
            file=sys.stderr,
        )
        return

    if result.returncode != 0:
        print(
            f"[{_HOOK_NAME}] WARNING: mark_ac_done for {ticket_path.name} "
            f"exited {result.returncode}: {result.stderr.strip()}",
            file=sys.stderr,
        )
    else:
        output = result.stdout.strip()
        if output:
            print(f"[{_HOOK_NAME}] {output}")


def main() -> int:
    """Run the post-merge hook to mark source ACs done for merged tickets.

    Reads changed files from the merge diff, filters to ``.md`` ticket files
    that exist on disk, parses their YAML frontmatter, and invokes
    mark_ac_done.py for each ticket with ``status: done`` and a ``source_ac``
    field. Per-ticket failures are logged but do not affect the exit code.

    Returns:
        Always 0 (non-fatal post-merge hook).
    """
    diff_paths = _get_diff_paths()
    ac_root = _get_ac_root()

    for path_str in diff_paths:
        ticket_path = Path(path_str)
        if ticket_path.suffix != ".md":
            continue
        if not ticket_path.exists():
            continue

        frontmatter = _read_ticket_frontmatter(ticket_path)
        status = frontmatter.get("status", "")
        source_ac = frontmatter.get("source_ac")

        if status != "done" or not source_ac:
            continue

        _mark_ac_done_for_ticket(ticket_path, ac_root)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(
            f"[{_HOOK_NAME}] unexpected error, skipping: {exc}",
            file=sys.stderr,
        )
        sys.exit(0)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-07-15 [python-coder/EPIC-RedTestClusterRepair/02]: Initial
#   implementation. AC ACD-600b: post-merge hook marks source ACs as
#   work_status: done when ticket files have status: done and source_ac
#   set. Supports LEAFCUTTER_FAKE_GIT_DIFF and LEAFCUTTER_AC_ROOT env
#   vars for test injection. Delegates to mark_ac_done.py as subprocess;
#   per-ticket failures are logged and skipped (exit always 0).
#   (#EPIC-RedTestClusterRepair/02)
# ====================================================================
