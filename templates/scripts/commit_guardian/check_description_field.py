"""
MODULE: check_description_field
GOAL: Pre-commit hook that enforces the presence of a non-empty `description:`
    frontmatter field on all staged Markdown files under the target directories
    (docs/**/*.md, docs/architecture/adrs/*.md, docs/architecture/components/*.md).
BUSINESS CONTEXT: Prevents future commits from introducing doc files that are
    missing a description: field, preserving the coverage enforced by the
    02a backfill migration. A missing description: field breaks knowledge-graph
    queries that rely on structured doc metadata.
ARCHITECTURE: Accepts file paths as positional CLI arguments (same interface as
    other commit-guardian hooks). Silently skips files outside the target scope
    (ticket files, skill SKILL.md files, agent template files). Parses YAML
    frontmatter with stdlib re; no external dependencies. Exit 0 = pass,
    exit 1 = one or more violations found.

Exit Codes:
    0 - All target files have a non-empty description: field (or no target files staged)
    1 - One or more target files are missing the description: field

Usage:
    python scripts/commit_guardian/check_description_field.py docs/some_doc.md
    python scripts/commit_guardian/check_description_field.py  # reads staged files from git
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Scope rules
# ---------------------------------------------------------------------------

_TARGET_PREFIXES = (
    "docs/",
)

_EXCLUDED_PREFIXES = (
    "tickets/",
    "templates/skills/",
    "templates/agents/",
)

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_DESCRIPTION_RE = re.compile(r"^\s*description\s*:\s*(.+)$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Scope filtering
# ---------------------------------------------------------------------------


def _is_in_scope(filepath: str) -> bool:
    """Return True when a file path is in scope for the description check.

    A file is in scope when one of the target prefixes appears in its path
    (as a path component sequence) and none of the excluded prefixes appear.
    This supports both relative paths (from git) and absolute paths (from CLI
    in test scenarios where temp dirs are used).

    Args:
        filepath: Relative or absolute file path string.

    Returns:
        bool: True if the file should be checked, False if it should be skipped.
    """
    path = Path(filepath)
    # Build both relative and posix representations for matching.
    rel = path.as_posix()
    parts_str = "/".join(path.parts) + "/"

    # Check excluded prefixes first (relative prefix or suffix component).
    for excluded in _EXCLUDED_PREFIXES:
        if rel.startswith(excluded) or f"/{excluded}" in parts_str:
            return False

    # Check target prefixes — accept relative OR embedded path components.
    for target in _TARGET_PREFIXES:
        if rel.startswith(target) or f"/{target}" in parts_str:
            return True

    return False


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------


def _has_description(content: str) -> bool:
    """Return True when the file has a non-empty `description:` frontmatter field.

    Parses the YAML frontmatter block (between the first two `---` delimiters)
    and checks for a `description:` key with a non-empty, non-whitespace value.

    Args:
        content: Full text content of the Markdown file.

    Returns:
        bool: True if `description:` is present with a non-empty value, else False.
    """
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return False

    frontmatter_text = match.group(1)
    desc_match = _DESCRIPTION_RE.search(frontmatter_text)
    if not desc_match:
        return False

    value = desc_match.group(1).strip()
    return bool(value)


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------


def _read_file(filepath: str) -> str | None:
    """Read a file's text content, returning None on I/O failure.

    Args:
        filepath: Path to the file to read.

    Returns:
        str: File content, or None if the file cannot be read.
    """
    try:
        return Path(filepath).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(
            f"Warning: cannot read {filepath}: {exc}",
            file=sys.stderr,
        )
        return None


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _get_staged_md_files() -> list[str]:
    """Return a list of staged .md file paths (relative to repo root).

    Returns:
        list[str]: Staged Markdown file paths. Empty list on git errors.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(
            f"Warning: git diff failed: {exc}",
            file=sys.stderr,
        )
        return []

    return [
        f
        for f in result.stdout.strip().splitlines()
        if f.lower().endswith(".md")
    ]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Entry point for the description-field pre-commit hook.

    Returns:
        int: Exit code (0 = pass, 1 = violations found).
    """
    if len(sys.argv) > 1:
        candidates = sys.argv[1:]
    else:
        candidates = _get_staged_md_files()

    violations: list[str] = []

    for filepath in candidates:
        if not _is_in_scope(filepath):
            continue

        content = _read_file(filepath)
        if content is None:
            # I/O error already reported; skip without flagging
            continue

        if not _has_description(content):
            violations.append(filepath)

    for path in violations:
        print(f"FAIL: {path} — missing description field")

    if violations:
        print(
            f"\ncheck_description_field: {len(violations)} file(s) missing "
            "description: frontmatter field.",
            file=sys.stderr,
        )
        print(
            "  FIX: Add a non-empty `description:` field to the YAML frontmatter "
            "of each flagged file.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-05 14:00 [python-coder]: Initial implementation.
  Enforces presence of non-empty description: frontmatter field on staged
  docs/**/*.md files. Silently skips tickets/, templates/skills/, and
  templates/agents/ trees. Follows check_ac_schema.py and
  check_paths_integrity.py patterns: positional CLI args, exit 1 with
  FAIL: <path> — missing description field per-line output.
  Registered in commit_guardian.json hooks_manifest.
  (EPIC-KnowledgeGraphQueryLayer/02b_description_field_enforcement_hook)
====================================================================
"""
