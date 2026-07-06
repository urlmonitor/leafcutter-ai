"""
MODULE: check_files_touched_reconciliation
GOAL: Pre-commit hook that flags source files changed by a ticket's work but
    absent from the ticket's declared files_touched UNION out_of_scope,
    immediately before the ticket is allowed to reach status: done.
BUSINESS CONTEXT: BP-1100e-1 — A ticket can pass every gate (tests green,
    sign-offs complete) and still deliver nothing, because the files it
    actually changed do not match the files it declared. This hook fires
    at the pre-done commit gate and blocks the commit when an undeclared
    source file (.py, .sql, .ts, .tsx, .js) is found in the branch diff.
    Complements BP-1100a (pre-dispatch scope declaration) without duplicating
    it: BP-1100a fires before work starts; this hook fires after work is done.
ARCHITECTURE: Standalone hook in templates/scripts/commit_guardian/hooks/
    (portable — no leafcutter-internal imports). Fires when a ticket .md file
    is staged. Computes changed source files from git diff origin/main...HEAD
    plus the current staged set, then compares against files_touched UNION
    out_of_scope in the ticket frontmatter. Exits 1 (blocking) when undeclared
    source files are found; exits 0 on any reconciliation error (fail-open per
    BP-1100e-2). Registered in hooks_manifest.hooks[] of
    templates/scripts/commit_guardian/commit_guardian.json, mirroring the
    check-agent-spawn-consistency entry.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SOURCE_EXTENSIONS: frozenset[str] = frozenset({".py", ".sql", ".ts", ".tsx", ".js"})
_BRANCH_BASE_CANDIDATES: list[str] = ["origin/main", "main"]
_HOOK_TAG = "[check-predone-scope]"


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _get_staged_files() -> list[str]:
    """Return staged file paths from the git index.

    Returns:
        List of repo-relative staged path strings, or empty list on error.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            check=False,
        )
    except subprocess.SubprocessError as exc:
        print(f"{_HOOK_TAG} WARNING: git diff --cached failed: {exc}", file=sys.stderr)
        return []
    return [ln for ln in result.stdout.strip().splitlines() if ln.strip()]


def _get_repo_root() -> str:
    """Return the absolute path to the git repository root.

    Returns:
        Repo root as a string, or empty string on error.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
    except subprocess.SubprocessError:
        return ""
    return result.stdout.strip()


def _get_branch_diff_files() -> frozenset[str]:
    """Return source files changed in this branch relative to origin/main.

    Tries origin/main first, then main. Uses the three-dot merge-base diff
    syntax so only commits on this branch (not on main) are included.
    Fails open — returns empty frozenset when git is unavailable or both
    base candidates fail.

    Returns:
        frozenset of repo-relative path strings changed since the branch point.
    """
    for base in _BRANCH_BASE_CANDIDATES:
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", f"{base}...HEAD"],
                capture_output=True,
                text=True,
                check=False,
            )
        except subprocess.SubprocessError:
            continue
        if result.returncode == 0:
            return frozenset(
                ln.strip()
                for ln in result.stdout.strip().splitlines()
                if ln.strip()
            )
    return frozenset()


# ---------------------------------------------------------------------------
# Frontmatter parsing (pure — no I/O, no try/except)
# ---------------------------------------------------------------------------


def _extract_frontmatter(content: str) -> str | None:
    """Extract the YAML frontmatter block from ticket content.

    Args:
        content: Full file content.

    Returns:
        YAML block text between the leading and closing --- delimiters, or
        None when the frontmatter block is absent or malformed.
    """
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    return match.group(1) if match else None


def _get_status(frontmatter: str) -> str:
    """Extract the status value from frontmatter text.

    Args:
        frontmatter: Raw YAML text between the --- delimiters.

    Returns:
        Status string (e.g. 'done', 'in_progress'), or empty string if absent.
    """
    match = re.search(r"^status:\s*(\S+)", frontmatter, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _parse_yaml_list_field(frontmatter: str, field_name: str) -> list[str]:
    """Parse a block-sequence YAML list field from frontmatter text.

    Handles the standard ticket format:
        field_name:
          - item1
          - item2

    Args:
        frontmatter: Raw YAML text between the --- delimiters.
        field_name: The field to extract (e.g. 'files_touched', 'out_of_scope').

    Returns:
        List of stripped string values, or empty list if the field is absent.
    """
    pattern = rf"^{re.escape(field_name)}:\s*\n((?:[ \t]+-[ \t]+\S[^\n]*\n?)+)"
    match = re.search(pattern, frontmatter, re.MULTILINE)
    if not match:
        return []
    items = re.findall(r"^[ \t]+-[ \t]+(\S[^\n]*)", match.group(1), re.MULTILINE)
    return [item.strip() for item in items if item.strip()]


# ---------------------------------------------------------------------------
# Core reconciliation logic (pure — no I/O)
# ---------------------------------------------------------------------------


def _normalise_path(path: str) -> str:
    """Strip leading ./ and normalise path separators.

    Args:
        path: Raw file path from frontmatter or git output.

    Returns:
        Normalised repo-relative path string.
    """
    return path.strip().lstrip("./").replace("\\", "/")


def _is_source_file(path: str) -> bool:
    """Return True if the file has a source/executable extension.

    Source extensions (from BP-1100e-1): .py, .sql, .ts, .tsx, .js

    Args:
        path: File path to test.

    Returns:
        bool: True when the file extension is in SOURCE_EXTENSIONS.
    """
    return Path(path).suffix in SOURCE_EXTENSIONS


def _compute_undeclared(
    declared_scope: set[str],
    branch_diff_files: frozenset[str],
    staged_files: list[str],
) -> list[str]:
    """Compute source files changed but not in the declared scope.

    Args:
        declared_scope: Normalised set of paths from files_touched UNION out_of_scope.
        branch_diff_files: Files changed in commits on this branch (from git diff).
        staged_files: Files staged for the current commit.

    Returns:
        Sorted list of undeclared source file paths.
    """
    all_changed = branch_diff_files | frozenset(staged_files)
    changed_sources = {
        _normalise_path(p)
        for p in all_changed
        if _is_source_file(p)
    }
    return sorted(changed_sources - declared_scope)


# ---------------------------------------------------------------------------
# Main entry point helpers
# ---------------------------------------------------------------------------


def _check_ticket(
    rel_path: str,
    repo_root: str,
    staged_files: list[str],
) -> list[str]:
    """Check one staged ticket file for undeclared source changes.

    Reads the ticket from disk, parses its frontmatter, and returns undeclared
    source files when the ticket status is 'done' and its declared scope misses
    at least one changed source file.

    Args:
        rel_path: Repo-relative path to the staged ticket .md file.
        repo_root: Absolute path to the git repo root (may be empty string).
        staged_files: All staged file paths for the current commit.

    Returns:
        Sorted list of undeclared source file paths.
        Empty list means the ticket is clean, status is not done, or a
        read/parse error occurred (fail-open).
    """
    abs_path = Path(repo_root, rel_path) if repo_root else Path(rel_path)

    try:
        content = abs_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(
            f"{_HOOK_TAG} WARNING: cannot read {rel_path}: {exc} — skipping",
            file=sys.stderr,
        )
        return []

    frontmatter = _extract_frontmatter(content)
    if frontmatter is None or _get_status(frontmatter) != "done":
        return []

    files_touched = _parse_yaml_list_field(frontmatter, "files_touched")
    out_of_scope = _parse_yaml_list_field(frontmatter, "out_of_scope")

    if not files_touched and not out_of_scope:
        return []  # no declared scope → nothing to reconcile against

    declared: set[str] = {_normalise_path(p) for p in files_touched + out_of_scope}
    branch_diff = _get_branch_diff_files()
    undeclared = _compute_undeclared(declared, branch_diff, staged_files)
    ticket_norm = _normalise_path(rel_path)
    return [p for p in undeclared if p != ticket_norm]


def _print_errors(all_errors: list[tuple[str, list[str]]]) -> None:
    """Print structured error output for undeclared source file violations.

    Args:
        all_errors: List of (ticket_path, undeclared_files) tuples.
    """
    print(
        f"\n{_HOOK_TAG} ERROR: source files changed but not declared in "
        "files_touched or out_of_scope",
        flush=True,
    )
    for ticket_path, undeclared_files in all_errors:
        print(f"\n  Ticket : {ticket_path}", flush=True)
        print("  Undeclared source files:", flush=True)
        for path in undeclared_files:
            print(f"    - {path}", flush=True)
    print(
        "\n  Fix: add the above files to files_touched (or out_of_scope if",
        flush=True,
    )
    print(
        "  intentionally excluded) in the ticket frontmatter before marking done.",
        flush=True,
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Run the pre-done scope reconciliation pre-commit hook.

    Reads staged ticket files, identifies those transitioning to status: done,
    computes the branch's actual changed source files, and blocks the commit
    when any source file was changed but not declared in the ticket's
    files_touched or out_of_scope frontmatter.

    Returns:
        0 when no done ticket is staged, all sources are declared, or a
        reconciliation error occurs (fail-open per BP-1100e-2).
        1 when undeclared source files are found in a ticket being set to done.
    """
    staged_files = _get_staged_files()
    if not staged_files:
        return 0

    repo_root = _get_repo_root()
    all_errors: list[tuple[str, list[str]]] = []

    for rel_path in staged_files:
        if not rel_path.startswith("tickets/") or not rel_path.endswith(".md"):
            continue
        undeclared = _check_ticket(rel_path, repo_root, staged_files)
        if undeclared:
            all_errors.append((rel_path, undeclared))

    if not all_errors:
        return 0

    _print_errors(all_errors)
    return 1


if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-07-06 [python-coder/BP-1100e-1]: Initial implementation.
#   AC BP-1100e-1: fires at the pre-done commit gate when a staged ticket
#   has status: done. Computes branch diff (origin/main...HEAD) plus staged
#   files, filters to source extensions (.py/.sql/.ts/.tsx/.js), and flags
#   paths absent from files_touched UNION out_of_scope. Fail-open on all
#   git/IO errors per BP-1100e-2. Standalone — no leafcutter-internal
#   imports for portability (ADR-001). Mirrors check-agent-spawn-consistency
#   entry in commit_guardian.json hooks_manifest.hooks[].
# ====================================================================
