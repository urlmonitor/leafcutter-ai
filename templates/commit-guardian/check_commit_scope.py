"""
MODULE: check_commit_scope.py
GOAL: Warn-only pre-commit guard that diffs staged files against the active
    ticket's ``files_touched`` frontmatter list and prints a non-blocking
    warning when unexpected files are staged.
BUSINESS CONTEXT: Agent-driven commits occasionally absorb unrelated in-flight
    files from parallel worktrees or from pre-commit hooks that auto-modify
    files not declared in the ticket scope.  Catching this at commit time —
    before the commit object is written — gives the agent or developer an
    immediate signal to review the staged set without blocking legitimate work.
    This is option (c) of the EPIC-AgentSystemFrictionReduction T01 design
    trade-off matrix: SOP updates + warn-only guard with a clear upgrade path
    to blocking mode (option b) once false-positive patterns are understood.
ARCHITECTURE: Thin git-subprocess wrapper.  Reads staged file paths from
    ``git diff --cached --name-only``, then scans staged ticket ``.md`` files
    for a ``files_touched:`` YAML frontmatter block to determine the expected
    scope.  Computes the diff between staged and expected, prints a structured
    warning to stdout, and always exits 0 (never blocks).  Config surface in
    ``commit_guardian.json`` → ``commit_scope`` section (optional — the hook
    works with sensible defaults when the section is absent).

# DECISION HISTORY
# - 2026-05-18 11:00 [epic-supervisor]: Initial implementation — option (c) hybrid warn-only guard. (#EPIC-AgentSystemFrictionReduction/01)
#   Exit 0 always. Upgrade path to blocking (b): replace sys.exit(0) with sys.exit(1) + escape token.
#   Architect design payload: T01 ## Comments, 2026-05-18 10:30.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Config (soft-import — works even if the section is absent from the JSON)
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent

# Inject project root into sys.path so ``config.py`` can be imported.

try:
    from config import load_config as _load_config

    _cfg = _load_config().get("commit_scope", {})
except Exception:  # pragma: no cover — config import failure is non-fatal
    _cfg = {}

# ---------------------------------------------------------------------------
# Constants (all overridable via commit_guardian.json → "commit_scope")
# ---------------------------------------------------------------------------

# Patterns for files that pre-commit hooks auto-modify and that should NOT be
# flagged as unexpected even when not in files_touched (hook artefacts).
_DEFAULT_HOOK_ARTEFACT_PATTERNS: list[str] = [
    r"^changelogs/",
    r"\.md$",          # doc-frontmatter hook rewrites last_updated
    r"^tickets/",      # ticket sign-off files — always expected
    r"^\.pre-commit-config\.yaml$",  # build-drift hook may rewrite this
]

HOOK_ARTEFACT_PATTERNS: list[str] = _cfg.get(
    "hook_artefact_patterns", _DEFAULT_HOOK_ARTEFACT_PATTERNS
)

# Files matching any of these patterns are never flagged, regardless of scope.
_COMPILED_ARTEFACT: list[re.Pattern[str]] = [
    re.compile(p) for p in HOOK_ARTEFACT_PATTERNS
]

# Maximum number of unexpected-file paths to print (avoid log flood).
MAX_WARN_LINES: int = _cfg.get("max_warn_lines", 20)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(cmd: list[str]) -> str:
    """Run a subprocess and return stripped stdout.

    Args:
        cmd: Command and arguments list.

    Returns:
        str: stdout, stripped, or empty string on error.
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip()
    except Exception:  # pragma: no cover
        return ""


def _get_staged_files() -> list[str]:
    """Return the list of staged file paths (relative to repo root).

    Returns:
        list[str]: Staged paths, or empty list when none are staged.
    """
    output = _run(["git", "diff", "--cached", "--name-only"])
    return [line for line in output.splitlines() if line.strip()]


def _parse_files_touched(ticket_path: Path) -> Optional[list[str]]:
    """Parse the ``files_touched`` YAML frontmatter list from a ticket file.

    Only the YAML front-matter block (between the first ``---`` pair) is
    parsed — a full YAML library is not required because the field is always
    a simple list of strings in the ticket schema.

    Args:
        ticket_path: Absolute or relative path to the ticket Markdown file.

    Returns:
        list[str] if ``files_touched`` is present and non-empty;
        None if the field is absent, empty, or the file cannot be read.
    """
    try:
        text = ticket_path.read_text(encoding="utf-8")
    except OSError:
        return None

    # Extract YAML frontmatter (first --- ... --- block)
    fm_match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not fm_match:
        return None

    fm_text = fm_match.group(1)

    # Find ``files_touched:`` list — handles both block-sequence and
    # comma-less multiline formats produced by the ticket-authoring skill.
    ft_match = re.search(r"^files_touched:\s*\n((?:[ \t]+-[ \t]+\S[^\n]*\n?)+)", fm_text, re.MULTILINE)
    if not ft_match:
        return None

    items = re.findall(r"^[ \t]+-[ \t]+(\S[^\n]*)", ft_match.group(1), re.MULTILINE)
    return [item.strip() for item in items if item.strip()] or None


def _find_active_ticket(staged: list[str]) -> Optional[Path]:
    """Identify the active ticket from staged files.

    Heuristic: look for a staged Markdown file under ``tickets/`` whose
    frontmatter contains an ``agents:`` map — that is the ticket being
    committed.  Returns the first match (there should be at most one ticket
    in flight per commit in the epic worktree model).

    Args:
        staged: List of staged file paths relative to repo root.

    Returns:
        Path to the ticket file, or None when no ticket is found.
    """
    for rel_path in staged:
        if not rel_path.startswith("tickets/"):
            continue
        if not rel_path.endswith(".md"):
            continue

        abs_path = _REPO_ROOT / rel_path
        try:
            text = abs_path.read_text(encoding="utf-8")
        except OSError:
            continue

        if re.search(r"^agents:", text, re.MULTILINE):
            return abs_path

    return None


def _is_hook_artefact(path: str) -> bool:
    """Return True when *path* matches a known hook-artefact pattern.

    Args:
        path: Repo-relative file path to test.

    Returns:
        bool: True if the path should be exempt from scope checking.
    """
    return any(p.search(path) for p in _COMPILED_ARTEFACT)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    """Warn-only commit-scope guard entry point.

    Returns:
        int: Always 0 — this guard is advisory only and must never block.
    """
    staged = _get_staged_files()
    if not staged:
        return 0

    ticket_path = _find_active_ticket(staged)
    if ticket_path is None:
        # No ticket in scope — nothing to check.
        return 0

    files_touched = _parse_files_touched(ticket_path)
    if not files_touched:
        # Ticket has no files_touched list — cannot check scope, skip silently.
        return 0

    # Normalise declared paths (strip leading "./" etc.)
    expected: set[str] = {p.lstrip("./") for p in files_touched}

    # Filter staged files: skip hook artefacts and the ticket file itself
    # (the ticket sign-off is always expected regardless of files_touched).
    ticket_rel = str(ticket_path.relative_to(_REPO_ROOT)).replace("\\", "/")
    unexpected: list[str] = []
    for path in staged:
        norm = path.lstrip("./")
        if norm == ticket_rel.lstrip("./"):
            continue
        if _is_hook_artefact(path):
            continue
        if norm not in expected:
            unexpected.append(path)

    if not unexpected:
        return 0

    # -------------------------------------------------------------------------
    # Print structured warning — always exit 0 (non-blocking, option c).
    # To upgrade to blocking mode (option b): replace the ``return 0`` below
    # with ``return 1`` and add an escape-token check on the commit message.
    # -------------------------------------------------------------------------
    print(
        "\n[check-commit-scope] WARNING: staged files outside declared scope",
        flush=True,
    )
    print(
        f"  Active ticket : {ticket_path.relative_to(_REPO_ROOT)}",
        flush=True,
    )
    print(
        "  Unexpected staged files (not in files_touched):",
        flush=True,
    )
    shown = unexpected[:MAX_WARN_LINES]
    for path in shown:
        print(f"    - {path}", flush=True)
    if len(unexpected) > MAX_WARN_LINES:
        print(
            f"    ... and {len(unexpected) - MAX_WARN_LINES} more (truncated)",
            flush=True,
        )
    print(
        "  This is a warning only — the commit will proceed.  Review staged",
        flush=True,
    )
    print(
        "  files and consider using `git add <explicit paths>` next time.",
        flush=True,
    )
    print(
        "  To upgrade to blocking mode see: docs/how-to/agent-commit-discipline.md",
        flush=True,
    )

    # Option (c): always exit 0.
    return 0


if __name__ == "__main__":
    sys.exit(main())
