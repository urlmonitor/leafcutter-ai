"""
Advisory pre-commit hook that warns when major code changes land without
corresponding documentation updates.

MODULE: check_doc_coverage
GOAL: Detect three coverage-gap signals in staged changes — new Python
    modules without a doc, new SQL procedures without a doc, and large
    diffs (>50 lines) without any staged markdown — and emit AGENT_HINT
    advisory messages. Never blocks a commit (exit code always 0).
BUSINESS CONTEXT: Surfaces documentation gaps at commit time so AI agents
    and developers can decide whether to update docs before landing the
    change. Reduces silent drift between code and documentation.
ARCHITECTURE: Not needed.

Signals detected:
    1. Staged .py file containing MODULE: in its header + no .md staged
    2. Staged .sql file under sql_functions/ matching CREATE PROCEDURE/FUNCTION
       + no .md staged
    3. Staged .py or .sql file whose added-line count > threshold + no .md staged

    In all three cases: if a knowledge_graph.json exists and the file
    already has DOC_LINKS coverage, the warning is suppressed.

Exit Codes:
    0 - Always (advisory-only hook)

Usage:
    poetry run python scripts/commit_guardian/check_doc_coverage.py
    poetry run python scripts/commit_guardian/check_doc_coverage.py --staged

DOC_LINKS:
    - docs/knowledge_graph_schema.md
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from _resolve_root import find_project_root

project_root = find_project_root()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.commit_guardian.config import DOC_COVERAGE_LARGE_DIFF_THRESHOLD  # noqa: E402

# ---------------------------------------------------------------------------
# ANSI colours (matching existing hook style)
# ---------------------------------------------------------------------------
_YELLOW = "\033[93m"
_CYAN = "\033[96m"
_RESET = "\033[0m"


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def get_staged_files() -> list[str]:
    """Return all staged (non-deleted) file paths.

    Returns:
        list[str]: Relative file paths staged for commit.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-status"],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError:
        return []

    paths = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2 and not parts[0].startswith("D"):
            paths.append(parts[-1])
    return paths


def count_added_lines(filepath: str) -> int:
    """Return the number of lines added in the staged diff for *filepath*.

    Args:
        filepath: Relative file path (as returned by git).

    Returns:
        int: Number of ``+`` lines in the cached diff for this file.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--numstat", filepath],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError:
        return 0

    line = result.stdout.strip()
    if not line:
        return 0
    parts = line.split("\t")
    try:
        return int(parts[0])
    except (ValueError, IndexError):
        return 0


def read_file_header(filepath: str, lines: int = 20) -> str:
    """Read the first *lines* lines of a staged file.

    Falls back to an empty string if the file cannot be read.

    Args:
        filepath: Relative file path.
        lines: Number of header lines to read (default 20).

    Returns:
        str: Joined header content.
    """
    try:
        p = _project_root / filepath
        raw = p.read_text(encoding="utf-8", errors="replace")
        return "\n".join(raw.split("\n")[:lines])
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# Knowledge graph helpers
# ---------------------------------------------------------------------------


def load_documented_paths(knowledge_graph_path: Path) -> set[str]:
    """Load the set of code-file paths that have DOC_LINKS coverage.

    Reads the knowledge graph JSON produced by build_knowledge_graph.py and
    returns the set of CodeFile paths that have at least one DOCUMENTED_BY
    edge.

    Args:
        knowledge_graph_path: Path to knowledge_graph.json.

    Returns:
        set[str]: Relative paths of code files with at least one doc link.
    """
    if not knowledge_graph_path.exists():
        return set()
    try:
        data = json.loads(knowledge_graph_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()

    documented: set[str] = set()
    for edge in data.get("edges", []):
        if edge.get("@type") == "DOCUMENTED_BY":
            documented.add(edge["from"])
    return documented


# ---------------------------------------------------------------------------
# Signal detectors
# ---------------------------------------------------------------------------


def is_new_python_module(filepath: str) -> bool:
    """Return True if the file is a .py with a MODULE: header field.

    Args:
        filepath: Relative file path.

    Returns:
        bool: True if MODULE: appears in the first 20 lines.
    """
    if not filepath.lower().endswith(".py"):
        return False
    return "MODULE:" in read_file_header(filepath)


def is_new_sql_procedure(filepath: str) -> bool:
    """Return True if the file is a .sql under sql_functions/ with a CREATE statement.

    Args:
        filepath: Relative file path.

    Returns:
        bool: True if the file lives under sql_functions/ and contains a
        CREATE OR REPLACE (FUNCTION|PROCEDURE) statement.
    """
    if not filepath.lower().endswith(".sql"):
        return False
    if "sql_functions/" not in filepath.replace("\\", "/"):
        return False
    header = read_file_header(filepath, lines=30)
    return bool(re.search(r"CREATE\s+OR\s+REPLACE\s+(FUNCTION|PROCEDURE)", header, re.IGNORECASE))


def has_doc_staged(staged_files: list[str]) -> bool:
    """Return True if at least one markdown or README file is staged.

    Args:
        staged_files: All staged file paths.

    Returns:
        bool: True if any .md or README* file is in the staged set.
    """
    for f in staged_files:
        name = Path(f).name.lower()
        if name.endswith(".md") or name.startswith("readme"):
            return True
    return False


# ---------------------------------------------------------------------------
# Warning emitter
# ---------------------------------------------------------------------------


def _warn(filepath: str, message: str, hint: str) -> None:
    """Print an advisory warning in the project's AGENT_HINT format.

    Args:
        filepath: The file that triggered the warning.
        message: Short one-line description of the gap.
        hint: Actionable suggestion for the developer/agent.
    """
    print(f"{_YELLOW}WARNING [check_doc_coverage] {filepath}{_RESET}")
    print(f"{_YELLOW}  → {message}{_RESET}")
    print(f"{_CYAN}  AGENT_HINT: {hint}{_RESET}")
    print()


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------


def check_coverage(
    staged_files: list[str],
    documented_paths: set[str],
    large_diff_threshold: int,
) -> int:
    """Evaluate all staged files for documentation coverage gaps.

    Args:
        staged_files: All staged file paths from git.
        documented_paths: Code paths with existing DOC_LINKS coverage
            (from knowledge graph; may be empty if graph not built yet).
        large_diff_threshold: Minimum added-line count to trigger the
            large-diff signal.

    Returns:
        int: Number of warnings emitted (informational; exit code stays 0).
    """
    doc_present = has_doc_staged(staged_files)
    warnings = 0

    for filepath in staged_files:
        normed = filepath.replace("\\", "/")

        # Skip if knowledge graph already confirms coverage
        if normed in documented_paths:
            continue

        if is_new_python_module(filepath):
            if not doc_present:
                _warn(
                    filepath,
                    "New module staged without a doc update.",
                    "Add or update a doc that describes this module, then restage it. "
                    "Skip with # noqa-doc if the module is internal/test-only.",
                )
                warnings += 1
            continue  # Don't also check large-diff for new modules

        if is_new_sql_procedure(filepath):
            if not doc_present:
                ns = normed.split("sql_functions/")[-1].split("/")[0]
                hint_path = f"docs/logic/{ns}.md" if ns else "docs/logic/<namespace>.md"
                _warn(
                    filepath,
                    "New SQL procedure staged without a doc update.",
                    f"Consider adding or updating {hint_path} to document this procedure.",
                )
                warnings += 1
            continue

        # Large-diff signal for any .py or .sql file
        if filepath.lower().endswith((".py", ".sql")):
            added = count_added_lines(filepath)
            if added > large_diff_threshold and not doc_present:
                _warn(
                    filepath,
                    f"Large change ({added} lines) staged without a doc update.",
                    "If this change affects documented behaviour, update the relevant "
                    "doc before committing.",
                )
                warnings += 1

    return warnings


def main() -> int:
    """Entry point for the doc coverage advisory pre-commit hook.

    Returns:
        int: Always 0 — this hook is advisory only.
    """
    parser = argparse.ArgumentParser(
        description="Advisory hook: warn when staged code has no doc coverage."
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Explicitly read staged files (default behaviour; flag is a no-op).",
    )
    parser.add_argument(
        "--knowledge-graph",
        default=str(_project_root / "knowledge_graph.json"),
        help="Path to knowledge_graph.json for DOC_LINKS coverage lookup.",
    )
    args = parser.parse_args()

    staged_files = get_staged_files()
    if not staged_files:
        return 0

    documented_paths = load_documented_paths(Path(args.knowledge_graph))
    threshold = DOC_COVERAGE_LARGE_DIFF_THRESHOLD

    warnings = check_coverage(staged_files, documented_paths, threshold)

    if warnings:
        print(
            f"{_YELLOW}[check_doc_coverage] {warnings} advisory warning(s) — "
            f"commit proceeds normally.{_RESET}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-12 11:30 [Agent]: Initial implementation. Advisory hook with
  three signals: new Python module (MODULE: header), new SQL procedure
  (CREATE OR REPLACE in sql_functions/), large diff (>50 lines). All
  suppressed when a .md is staged or when the knowledge graph confirms
  coverage. Exit code always 0. (EPIC-DocTraceability ticket 12)
====================================================================
"""
