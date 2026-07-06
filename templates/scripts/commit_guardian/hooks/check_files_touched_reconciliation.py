"""
MODULE: check_files_touched_reconciliation
GOAL: Pre-commit hook that flags source files changed by a ticket's work but
    absent from the ticket's declared files_touched UNION out_of_scope,
    immediately before the ticket is allowed to reach status: done.
BUSINESS CONTEXT: BP-1100e-1 — blocks commits when a ticket moves to done
    but changed source files (.py, .sql, .ts, .tsx, .js) are absent from
    files_touched or out_of_scope. Complements BP-1100a (fires before work
    starts; this hook fires after work is done).
ARCHITECTURE: Standalone hook in templates/scripts/commit_guardian/hooks/
    (portable — no leafcutter-internal imports). Computes branch diff plus
    staged source files, compares against files_touched UNION out_of_scope.
    Exits 1 on undeclared sources; 0 on errors (fail-open, BP-1100e-2).
    Registered in hooks_manifest.hooks[] of commit_guardian.json.
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

# Path segment and filename markers that identify code-generated files.
# Slashed markers match full path segments; dot/underscore markers match
# generated filename stems (e.g. ".generated.", "_generated.").
GENERATED_PATH_PATTERNS: frozenset[str] = frozenset({
    "/generated/",
    "/.generated/",
    "/__generated__/",
    "/dist/",
    ".generated.",
    "_generated.",
})

# Well-known lock-file base-names (always exempt; no declarable behavior).
LOCKFILE_NAMES: frozenset[str] = frozenset({
    "poetry.lock",
    "Pipfile.lock",
    "package-lock.json",
    "yarn.lock",
    "composer.lock",
    "Gemfile.lock",
    "go.sum",
    "Cargo.lock",
    "pnpm-lock.yaml",
    "uv.lock",
})

_BRANCH_BASE_CANDIDATES: list[str] = ["origin/main", "main"]
_HOOK_TAG = "[check-predone-scope]"

# Module-level cache for the case-insensitivity probe result.  None means
# the probe has not yet run; True/False are cached outcomes.
_FS_CASE_INSENSITIVE: bool | None = None


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _get_staged_files() -> list[str]:
    """Return staged file paths from the git index, or empty list on error."""
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
    """Return the absolute git repo root path, or empty string on error."""
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
    """Return files changed in this branch relative to origin/main.

    Tries origin/main, then main; uses three-dot merge-base syntax.
    Fails open — returns empty frozenset when git is unavailable.

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


def _is_case_insensitive_fs() -> bool:
    """Return True if the git working tree is on a case-insensitive filesystem.

    Detects case-insensitivity by querying ``git config --get core.ignoreCase``.
    Result is cached at module level so the subprocess call runs at most once
    per process invocation.  Fails open — returns False on any subprocess error,
    consistent with the hook's BP-1100e-2 fail-open policy.

    Returns:
        bool: True when ``core.ignoreCase`` is ``true`` (NTFS / APFS),
        False otherwise.
    """
    global _FS_CASE_INSENSITIVE
    if _FS_CASE_INSENSITIVE is not None:
        return _FS_CASE_INSENSITIVE
    try:
        result = subprocess.run(
            ["git", "config", "--get", "core.ignoreCase"],
            capture_output=True,
            text=True,
            check=False,
        )
    except subprocess.SubprocessError as exc:
        print(
            f"{_HOOK_TAG} WARNING: git config core.ignoreCase failed: {exc}",
            file=sys.stderr,
        )
        _FS_CASE_INSENSITIVE = False
        return False
    _FS_CASE_INSENSITIVE = result.stdout.strip().lower() == "true"
    return _FS_CASE_INSENSITIVE


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
    """Parse a block-sequence YAML list field from raw frontmatter text.

    Handles the ``field_name:\\n  - item`` block-sequence format.

    Args:
        frontmatter: Raw YAML text between the --- delimiters.
        field_name: Field to extract (e.g. 'files_touched', 'out_of_scope').

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
    """Strip leading ./ and normalise path separators; apply case-folding on
    case-insensitive filesystems.

    Applies case-folding (lowercase) when the underlying filesystem is
    case-insensitive, as detected by :func:`_is_case_insensitive_fs`.  This
    ensures paths that differ only by case (e.g. ``Scripts/Build.py`` vs
    ``scripts/build.py`` on NTFS or APFS) compare as equal after normalisation.
    Both separator normalisation and case-folding are applied in sequence so
    the two transformations compose correctly on Windows NTFS and macOS APFS.

    Args:
        path: Raw file path from frontmatter or git output.

    Returns:
        Normalised repo-relative path string, lowercased on case-insensitive
        filesystems.
    """
    normalised = path.strip().lstrip("./").replace("\\", "/")
    if _is_case_insensitive_fs():
        return normalised.lower()
    return normalised


def _is_source_file(path: str) -> bool:
    """Return True if the file has a source/executable extension.

    Source extensions (from BP-1100e-1): .py, .sql, .ts, .tsx, .js

    Args:
        path: File path to test.

    Returns:
        bool: True when the file extension is in SOURCE_EXTENSIONS.
    """
    return Path(path).suffix in SOURCE_EXTENSIONS


def _is_generated_file(path: str) -> bool:
    """Return True if the path belongs to a code-generated artifact.

    Prepends a leading slash before checking GENERATED_PATH_PATTERNS so
    segment markers (e.g. ``/generated/``) match full segments only, not
    substrings of unrelated names like ``not_generated/``.

    Args:
        path: File path to test (repo-relative or absolute).

    Returns:
        bool: True when a GENERATED_PATH_PATTERNS marker is found.
    """
    norm = "/" + path.replace("\\", "/").lstrip("/")
    return any(marker in norm for marker in GENERATED_PATH_PATTERNS)


def _is_lockfile(path: str) -> bool:
    """Return True if the file is a well-known dependency lock-file.

    Provides an explicit, readable guard even though most lock-files are
    already implicitly exempt because their extensions are not in
    SOURCE_EXTENSIONS.

    Args:
        path: File path to test.

    Returns:
        bool: True when the filename matches a known lock-file name.
    """
    return Path(path).name in LOCKFILE_NAMES


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
        if _is_source_file(p) and not _is_generated_file(p) and not _is_lockfile(p)
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

    Reads the ticket, parses its frontmatter, and returns undeclared source
    files when status is 'done' and the declared scope misses a changed file.

    Args:
        rel_path: Repo-relative path to the staged ticket .md file.
        repo_root: Absolute git repo root path (may be empty string).
        staged_files: All staged file paths for the current commit.

    Returns:
        Sorted list of undeclared source file paths, or empty list when the
        ticket is clean, not-done, or a read/parse error occurred.
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

    Identifies done-staged tickets, computes changed source files, and blocks
    the commit when any source file is absent from files_touched / out_of_scope.

    Returns:
        0 when clean or on any reconciliation error (fail-open per BP-1100e-2).
        1 when undeclared source files are found.
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
# - 2026-07-06 [python-coder/BP-1100e-1-i]: Add generated-file and
#   lockfile exemptions (AC BP-1100e-1-i). GENERATED_PATH_PATTERNS covers
#   path segments (/generated/, /__generated__/, /dist/, /.generated/) and
#   stem markers (.generated., _generated.). LOCKFILE_NAMES covers common
#   lock-files by basename. Both _is_generated_file() and _is_lockfile()
#   are pure (no I/O). _compute_undeclared() filters both categories.
# - 2026-07-06 [python-coder/BP-1100e-1-ii]: Add case-folding to
#   _normalise_path() for case-insensitive filesystems (NTFS/APFS).
#   AC BP-1100e-1-ii: paths that differ only by case (e.g.
#   "Scripts/Build_Phases.py" vs "scripts/build_phases.py") are treated
#   as matching on case-insensitive filesystems.
#   _is_case_insensitive_fs() queries git config --get core.ignoreCase,
#   caches the boolean result at module level (_FS_CASE_INSENSITIVE), and
#   fails open (returns False on SubprocessError) per BP-1100e-2 policy.
#   Separator normalisation (backslash → forward slash) and case-folding
#   compose correctly in _normalise_path() — both applied in sequence.
# ====================================================================
