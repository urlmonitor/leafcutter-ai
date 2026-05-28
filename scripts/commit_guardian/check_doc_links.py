"""
Pre-commit hook to validate DOC_LINKS in Python and SQL files.

MODULE: check_doc_links
GOAL: Enforce bidirectional traceability between code files and documentation
    by validating DOC_LINKS references and cross-checking doc frontmatter.
BUSINESS CONTEXT: Ensures code-to-doc and doc-to-code links stay in sync,
    reducing documentation drift and enabling automated traceability audits.
ARCHITECTURE: Not needed.
PARENT_DIAGRAM: docs/architecture/L2_data_pipeline_macro.md

Checks:
    1. Referenced doc paths actually exist on disk.
    2. (Optional) Referenced doc's frontmatter ``related_code`` links back.
    3. Files with ARCHITECTURE mermaid diagrams consider linking to a parent
       architecture diagram via DOC_LINKS.

All failures are **advisory warnings** with AGENT_HINT — they never block commits.

Exit Codes:
    0 — Always (advisory-only hook)

Usage:
    poetry run python scripts/commit_guardian/check_doc_links.py
    poetry run python scripts/commit_guardian/check_doc_links.py --file src/worker.py
    poetry run python scripts/commit_guardian/check_doc_links.py --all
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from _resolve_root import find_project_root

project_root = find_project_root()

from config import (
    DOC_LINKS_CHECK_BIDIRECTIONAL,
    DOC_LINKS_CHECK_MERMAID,
    EXCLUDED_DIRS,
)

# ---------------------------------------------------------------------------
# ANSI colours
# ---------------------------------------------------------------------------
_YELLOW = "\033[93m"
_CYAN = "\033[96m"
_RESET = "\033[0m"


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def extract_python_doc_links(content: str) -> list[str]:
    """Extract DOC_LINKS paths from a Python module docstring.

    Parses lines after ``DOC_LINKS:`` that start with ``- `` until the next
    recognised header field (another ``ALL_CAPS:`` key) or the closing ``\"\"\"``.

    Args:
        content: Full file content as a string.

    Returns:
        list[str]: List of relative doc paths found in the DOC_LINKS block.
    """
    links: list[str] = []
    marker = "DOC_LINKS:"
    idx = content.find(marker)
    if idx == -1:
        return links

    lines = content[idx + len(marker):].split("\n")
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Stop conditions
        if re.match(r"^[A-Z_]+:", stripped):
            break
        if stripped in ('"""', "'''"):
            break
        if stripped.startswith("- "):
            link = stripped[2:].strip()
            if link:
                links.append(link)
    return links


def extract_sql_doc_links(content: str) -> list[str]:
    """Extract Doc Links paths from an SQL header comment block.

    Parses lines after ``Doc Links:`` that start with ``- `` until the next
    header field or the closing ``*/``.

    Args:
        content: Full file content as a string.

    Returns:
        list[str]: List of relative doc paths found in the Doc Links block.
    """
    links: list[str] = []
    marker = "Doc Links:"
    idx = content.find(marker)
    if idx == -1:
        return links

    lines = content[idx + len(marker):].split("\n")
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped == "*/":
            break
        # Next header field (e.g. "Goal:", "Business Context:")
        if re.match(r"^[A-Za-z][A-Za-z _]+:", stripped) and not stripped.startswith("- "):
            break
        if stripped.startswith("- "):
            link = stripped[2:].strip()
            if link:
                links.append(link)
    return links


def has_mermaid_diagram(content: str) -> bool:
    """Check whether the file contains a mermaid code block.

    Args:
        content: Full file content as a string.

    Returns:
        bool: True if a ```mermaid block is found.
    """
    return "```mermaid" in content


def has_architecture_doc_link(links: list[str]) -> bool:
    """Check whether any link points to an architecture doc.

    Args:
        links: List of DOC_LINKS paths.

    Returns:
        bool: True if at least one link contains 'architecture' in the path.
    """
    return any("architecture" in link.lower() for link in links)


def parse_frontmatter_related_code(md_content: str) -> list[str]:
    """Extract ``related_code`` entries from markdown YAML frontmatter.

    Args:
        md_content: Full markdown file content.

    Returns:
        list[str]: List of related code paths from the frontmatter.
    """
    if not md_content.startswith("---"):
        return []

    end_idx = md_content.find("---", 3)
    if end_idx == -1:
        return []

    raw_yaml = md_content[3:end_idx].strip()
    try:
        parsed = yaml.safe_load(raw_yaml)
    except yaml.YAMLError:
        return []

    if not isinstance(parsed, dict):
        return []

    related = parsed.get("related_code", [])
    if not isinstance(related, list):
        return []
    return [str(p).strip().strip("'\"") for p in related]


# ---------------------------------------------------------------------------
# Warning printer
# ---------------------------------------------------------------------------


def print_warning(filepath: str, message: str, hint: str) -> None:
    """Print a coloured warning with AGENT_HINT.

    Args:
        filepath: Relative path of the file being checked.
        message: Human-readable warning message.
        hint: Actionable hint for AI agents or developers.
    """
    print(f"{_YELLOW}WARNING [check_doc_links] {filepath}{_RESET}")
    print(f"{_YELLOW}  → {message}{_RESET}")
    print(f"{_CYAN}  AGENT_HINT: {hint}{_RESET}")
    print()


# ---------------------------------------------------------------------------
# Core validation
# ---------------------------------------------------------------------------


def check_file(file_path: Path, root_dir: Path) -> int:
    """Validate DOC_LINKS for a single file.

    Args:
        file_path: Absolute path to the file to check.
        root_dir: Absolute path to the project root.

    Returns:
        int: Number of warnings emitted.
    """
    warnings_found = 0
    rel_path = file_path.relative_to(root_dir).as_posix()

    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0

    is_python = file_path.suffix == ".py"
    links = (
        extract_python_doc_links(content)
        if is_python
        else extract_sql_doc_links(content)
    )

    # --- Check 3: Mermaid diagram without architecture link ---
    if DOC_LINKS_CHECK_MERMAID and has_mermaid_diagram(content):
        if not has_architecture_doc_link(links):
            print_warning(
                rel_path,
                "File has ARCHITECTURE mermaid diagram but no architecture_diagrams "
                "reference in DOC_LINKS.",
                "This file has an embedded Mermaid diagram. If it is a detail view "
                "of a higher-level architecture diagram (e.g., "
                "docs/architecture/L3_database_phase_flows.md), add it to DOC_LINKS. Skip if the "
                "diagram is purely internal (state machine, loop).",
            )
            warnings_found += 1

    for link in links:
        doc_path = root_dir / link

        # --- Check 1: Path existence ---
        if not doc_path.exists():
            print_warning(
                rel_path,
                f"DOC_LINKS path '{link}' does not exist.",
                "Check if the doc was renamed or moved. Update the path or "
                "remove the link.",
            )
            warnings_found += 1
            continue

        # --- Check 2: Bidirectional linking ---
        if DOC_LINKS_CHECK_BIDIRECTIONAL and doc_path.suffix == ".md":
            try:
                md_content = doc_path.read_text(encoding="utf-8")
                related_code = parse_frontmatter_related_code(md_content)
                if related_code and rel_path not in related_code:
                    print_warning(
                        rel_path,
                        f"Missing bidirectional link in '{link}'.",
                        f"Add '{rel_path}' to {link} frontmatter related_code list.",
                    )
                    warnings_found += 1
            except (OSError, UnicodeDecodeError):
                pass

    return warnings_found


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def get_staged_files() -> list[str]:
    """Get staged Python and SQL files from git.

    Returns:
        list[str]: List of relative file paths.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-status"],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError:
        return []

    files = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            status = parts[0]
            filepath = parts[-1]
            if not status.startswith("D") and (
                filepath.endswith(".py") or filepath.endswith(".sql")
            ):
                files.append(filepath)
    return files


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def configure_stdout() -> None:
    """Ensure output works on Windows with UTF-8."""
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Entry point for the doc links pre-commit hook.

    Returns:
        int: Always 0 (advisory-only).
    """
    parser = argparse.ArgumentParser(description="Validate DOC_LINKS in Python/SQL files.")
    parser.add_argument("--file", help="Specific file to check (bypasses git staged files).")
    parser.add_argument("--all", action="store_true", help="Scan all Python/SQL files.")
    parser.add_argument("filenames", nargs="*", help="Files to check (passed by pre-commit)")
    args = parser.parse_args()

    configure_stdout()

    # Determine files to check
    if args.file:
        file_path = Path(args.file)
        if not file_path.is_absolute():
            file_path = project_root / file_path
        files_to_check = [file_path]
    elif args.all:
        files_to_check = list(project_root.rglob("*.py")) + list(
            project_root.rglob("*.sql")
        )
    elif args.filenames:
        files_to_check = []
        for f in args.filenames:
            file_path = Path(f)
            if not file_path.is_absolute():
                file_path = project_root / file_path
            files_to_check.append(file_path)
    else:
        staged = get_staged_files()
        files_to_check = [project_root / f for f in staged]

    total_warnings = 0
    checked = 0

    for f in files_to_check:
        if not f.is_file():
            continue
        # Exclude standard dirs
        rel_parts = set(f.relative_to(project_root).parts)
        if rel_parts & EXCLUDED_DIRS:
            continue
        if any(part.startswith(".") for part in f.relative_to(project_root).parts):
            continue

        warnings = check_file(f, project_root)
        total_warnings += warnings
        checked += 1

    if total_warnings > 0:
        print(
            f"{_YELLOW}⚠️  DOC_LINKS: {total_warnings} warning(s) in "
            f"{checked} file(s) checked.{_RESET}"
        )
    elif checked > 0:
        print(f"✅ DOC_LINKS: {checked} file(s) checked — all links valid.")

    # Advisory only — always return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-18 00:00 [epic-supervisor/merge]: Added PARENT_DIAGRAM declaration to module docstring to satisfy check-mermaid-parent-link hook. (#EPIC-UserSurfaceVerification/merge)
- 2026-05-12 00:00 [Agent]: Updated example path in mermaid hint from data_flow.md
  to L3_database_phase_flows.md (EPIC-ArchitectureDocs ticket 07 rename).
- 2026-05-04 19:00 [Antigravity]: Added file arguments to check_doc_links hook.
- 2026-05-03 12:00 [AI/Antigravity]: Initial implementation. Advisory-only hook
  that validates DOC_LINKS in Python module docstrings and SQL header comments.
  Checks path existence, bidirectional frontmatter links, and mermaid diagram
  architecture references. All warnings include AGENT_HINT for AI triage.
====================================================================
"""
