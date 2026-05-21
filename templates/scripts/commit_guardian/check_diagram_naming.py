"""
MODULE: check_diagram_naming.py
GOAL: Pre-commit hook that enforces the c{level}-{seq:03d}-{slug}.md filename
      convention for architecture diagram files under docs/architecture/.
BUSINESS CONTEXT: Architecture diagrams must follow a deterministic naming
                  scheme so that the C4 level is visible in the filename,
                  files sort correctly in directory listings, and agents
                  can allocate conflict-free names on the first attempt.
ARCHITECTURE: Validates staged docs/architecture/*.md files: checks filename
              matches the c[1-4]-NNN-slug.md pattern, and verifies the level
              digit matches the flight_level frontmatter.
              Respects [NO-ARCH-UPDATE] bypass.

====
DECISION HISTORY
- 2026-05-14 20:00 [EPIC-ArchitectureDocsEnforcement/ticket 09 — Hendrik/Claude]:
  Created as a standalone hook (separate from check_doc_frontmatter.py) to
  keep each hook single-concern. Validates both the pattern AND the
  level/flight_level consistency in a single pass.
====
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml

_BYPASS_TOKEN = "[NO-ARCH-UPDATE]"
_FILENAME_RE = re.compile(r"^c([1-4])-(\d{3})-([a-z0-9-]+)\.md$")
_FLIGHT_LEVEL_MAP = {
    "L1-Context": "1",
    "L2-Container": "2",
    "L3-Component": "3",
    "L4-Code": "4",
}


def _get_staged_files() -> list[Path]:
    """Return list of staged file paths from git diff --cached.

    Returns:
        List of Path objects for each file currently staged.
    """
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [Path(p) for p in result.stdout.splitlines() if p.strip()]


def _get_commit_message() -> str:
    """Read the pending commit message from COMMIT_EDITMSG if available.

    Returns:
        The commit message string, or empty string when unavailable.
    """
    try:
        msg_file = Path(
            subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        ) / "COMMIT_EDITMSG"
        if msg_file.exists():
            return msg_file.read_text(encoding="utf-8")
    except (subprocess.CalledProcessError, OSError):
        pass
    return ""


def _parse_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter from a markdown file.

    Args:
        content: Full text content of a markdown file.

    Returns:
        Parsed frontmatter dict, or empty dict when absent or malformed.
    """
    if not content.startswith("---"):
        return {}
    end = content.find("\n---", 3)
    if end == -1:
        return {}
    try:
        return yaml.safe_load(content[3:end]) or {}
    except yaml.YAMLError:
        return {}


def _check_diagram_naming(path: Path, repo_root: Path) -> list[str]:
    """Validate filename convention for a single architecture diagram.

    Checks that the filename matches the c[1-4]-NNN-slug.md pattern and that
    the level digit in the filename matches the flight_level frontmatter.

    Args:
        path: Relative path to the file (relative to repo root).
        repo_root: Absolute path to the repository root.

    Returns:
        List of error message strings. Empty list means no violations.
    """
    abs_path = repo_root / path
    if not abs_path.exists():
        return []

    try:
        content = abs_path.read_text(encoding="utf-8")
    except OSError:
        return []

    fm = _parse_frontmatter(content)
    file_type = fm.get("type", "")
    if file_type != "architecture":
        return []

    filename = path.name
    match = _FILENAME_RE.match(filename)
    if not match:
        return [
            f"diagram naming: '{path}' has type 'architecture' but filename "
            f"'{filename}' does not match c{{level}}-{{seq:03d}}-{{slug}}.md pattern. "
            f"Rename to e.g. 'c2-001-{filename}' or add [NO-ARCH-UPDATE] to bypass."
        ]

    level_from_name = match.group(1)
    flight_level = fm.get("flight_level", "")
    expected_level = _FLIGHT_LEVEL_MAP.get(flight_level, "")

    if expected_level and level_from_name != expected_level:
        return [
            f"diagram naming: level mismatch for '{path}' — filename prefix 'c{level_from_name}-' "
            f"but frontmatter flight_level is '{flight_level}' (expected 'c{expected_level}-'). "
            f"Fix the filename prefix or the flight_level frontmatter field."
        ]

    return []


def main() -> int:
    """Run the diagram naming check on all staged architecture diagram files.

    Returns:
        Exit code: 0 when all checks pass or bypass is active, 1 on any violation.
    """
    commit_msg = _get_commit_message()
    if _BYPASS_TOKEN in commit_msg:
        return 0

    try:
        repo_root = Path(
            subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        )
    except subprocess.CalledProcessError:
        print("check-diagram-naming: could not determine repo root — skipping.", file=sys.stderr)
        return 0

    staged = _get_staged_files()
    arch_docs = [
        p for p in staged
        if str(p).startswith("docs/architecture/") and p.suffix == ".md"
    ]

    if not arch_docs:
        return 0

    all_errors: list[str] = []
    for doc_path in arch_docs:
        all_errors.extend(_check_diagram_naming(doc_path, repo_root))

    if all_errors:
        for err in all_errors:
            print(f"[check-diagram-naming] {err}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
