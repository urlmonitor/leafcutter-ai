"""
MODULE: check_mermaid_parent_link
GOAL: Pre-commit hook that enforces bidirectional parent-child linking for
      architecture diagrams and ADR-diagram cross-references.
BUSINESS CONTEXT: Architecture docs drift apart silently when a child diagram
      is added without updating the parent's children: list. This hook makes
      the bidirectional link a commit-time requirement, preventing orphan diagrams
      and broken cross-reference trees.
ARCHITECTURE: Not needed.

Checks performed:
    1. docs/architecture/**/*.md — must declare parent: (or root: true).
       parent file must exist; parent flight_level must be strictly higher;
       parent's children: list must contain this file.
    2. *.py files — mermaid block in module docstring requires PARENT_DIAGRAM:
       in the module header comment block.
    3. *.sql files — mermaid block in the SQL comment header requires
       PARENT_DIAGRAM: in that header.
    4. ADR bidirectional rule — every ADR that declares affects_diagrams: [path]
       must have each listed diagram declare related_adrs: [ADR-NNN].

Bypass: include [NO-ARCH-UPDATE] in the commit message to skip all checks.

Exit codes:
    0 — all checks pass (or bypass active)
    1 — one or more violations found

Usage:
    python scripts/commit_guardian/check_mermaid_parent_link.py

DECISION HISTORY:
  - 2026-05-14 20:00 [EPIC-ArchitectureDocsEnforcement/ticket 04 — Hendrik/Claude]:
    Created hook. Implements bidirectional parent-link enforcement for architecture
    docs, Python/SQL mermaid blocks, and ADR-diagram cross-references.
    Starts in strict mode (exit 1 on violation); use [NO-ARCH-UPDATE] to bypass.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Regexes
# ---------------------------------------------------------------------------

MERMAID_FENCE_RE = re.compile(r"```mermaid", re.IGNORECASE)
PARENT_DIAGRAM_RE = re.compile(r"PARENT_DIAGRAM\s*:", re.IGNORECASE)
ADR_NUM_RE = re.compile(r"ADR-(\d+)", re.IGNORECASE)
FLIGHT_LEVEL_RE = re.compile(r"L(\d+)", re.IGNORECASE)

ARCH_DOC_PATTERN = re.compile(r"^docs/architecture/.*\.md$")
ADR_PATTERN = re.compile(r"^docs/architecture/adrs/ADR-.*\.md$", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _bypass_active() -> bool:
    """Return True when [NO-ARCH-UPDATE] is present in the commit message."""
    msg = os.environ.get("GIT_COMMIT_MSG", "")
    if "[NO-ARCH-UPDATE]" in msg:
        return True
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            capture_output=True, text=True, check=False,
        )
        return "[NO-ARCH-UPDATE]" in result.stdout
    except Exception:
        return False


def _get_staged_files() -> list[str]:
    """Return relative paths of all staged non-deleted files."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-status"],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError:
        return []
    paths = []
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2 and not parts[0].startswith("D"):
            paths.append(parts[-1])
    return paths


# ---------------------------------------------------------------------------
# Frontmatter helpers
# ---------------------------------------------------------------------------


def _parse_frontmatter(content: str) -> Optional[dict]:
    """Parse YAML frontmatter from a markdown file.

    Args:
        content: Full file content as a string.

    Returns:
        Optional[dict]: Parsed frontmatter dict, or None if absent/malformed.
    """
    if not content.startswith("---"):
        return None
    end = content.find("\n---", 3)
    if end == -1:
        return None
    try:
        return yaml.safe_load(content[3:end]) or {}
    except yaml.YAMLError:
        return None


def _flight_level_int(fm: dict) -> Optional[int]:
    """Extract the numeric flight level from frontmatter (L1 → 1, L2 → 2, etc.).

    Args:
        fm: Parsed frontmatter dictionary.

    Returns:
        Optional[int]: The numeric flight level, or None if not present or unreadable.
    """
    fl = fm.get("flight_level", "")
    m = FLIGHT_LEVEL_RE.search(str(fl))
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Check 1 — Architecture docs parent-child bidirectional link
# ---------------------------------------------------------------------------


def _validate_level_order(rel_path: str, fm: dict, parent_fm: dict, parent_rel: str) -> list[str]:
    """Validate that the parent document has a higher flight level than the child.

    Args:
        rel_path: Repo-relative path to the architecture markdown file.
        fm: Parsed frontmatter dictionary of the current file.
        parent_fm: Parsed frontmatter dictionary of the parent file.
        parent_rel: Repo-relative path to the parent markdown file.

    Returns:
        list[str]: Violation messages, empty when level order is correct.
    """
    child_level = _flight_level_int(fm)
    parent_level = _flight_level_int(parent_fm)
    if child_level is not None and parent_level is not None:
        if parent_level >= child_level:
            return [
                f"ARCH-LEVEL-ORDER: '{rel_path}' (L{child_level}) declares parent "
                f"'{parent_rel}' (L{parent_level}). Parent flight_level must be "
                "strictly higher (lower number) than child."
            ]
    return []

def _validate_markdown_link(rel_path: str, content: str, parent_rel: str) -> list[str]:
    """Validate that there is a markdown link to the parent below the first mermaid fence.

    Args:
        rel_path: Repo-relative path to the architecture markdown file.
        content: The full content of the markdown file.
        parent_rel: Repo-relative path to the parent markdown file.

    Returns:
        list[str]: Violation messages, empty when the markdown link exists.
    """
    mermaid_match = MERMAID_FENCE_RE.search(content)
    if mermaid_match:
        end_fence_idx = content.find("```", mermaid_match.end())
        if end_fence_idx != -1:
            after_fence = content[end_fence_idx + 3:]
            parent_basename = Path(parent_rel).name
            if parent_basename not in after_fence:
                return [
                    f"ARCH-MARKDOWN-LINK: '{rel_path}' declares parent '{parent_rel}' "
                    "but has no markdown link to it below the first mermaid block. "
                    "Add a markdown link to the parent below the diagram."
                ]
    return []

def _validate_bidirectional(rel_path: str, parent_fm: dict, parent_rel: str) -> list[str]:
    """Validate that the parent lists the current file in its children frontmatter.

    Args:
        rel_path: Repo-relative path to the architecture markdown file.
        parent_fm: Parsed frontmatter dictionary of the parent file.
        parent_rel: Repo-relative path to the parent markdown file.

    Returns:
        list[str]: Violation messages, empty when bidirectional link exists.
    """
    parent_children = parent_fm.get("children") or []
    basename = Path(rel_path).name
    child_listed = any(
        basename in str(c) or rel_path in str(c) for c in parent_children
    )
    if not child_listed:
        return [
            f"ARCH-BIDIRECTIONAL: '{rel_path}' declares parent '{parent_rel}' "
            f"but '{parent_rel}' does not list this file in its 'children:' frontmatter. "
            "Add the child path to the parent's children: list."
        ]
    return []

def _check_arch_doc(rel_path: str) -> list[str]:
    """Validate parent-child bidirectional links for an architecture doc.

    Args:
        rel_path: Repo-relative path to the architecture markdown file.

    Returns:
        list[str]: Violation messages, empty when all checks pass.
    """
    errors: list[str] = []
    abs_path = REPO_ROOT / rel_path
    if not abs_path.exists():
        return []

    content = abs_path.read_text(encoding="utf-8")
    fm = _parse_frontmatter(content)
    if fm is None:
        return []

    # Skip if no mermaid block at all (not a diagram doc)
    if not MERMAID_FENCE_RE.search(content):
        return []

    # L1 exception: root: true skips parent check
    if fm.get("root"):
        return []

    parent_rel = fm.get("parent")
    if not parent_rel:
        return [
            f"ARCH-PARENT-MISSING: '{rel_path}' has a mermaid block but no 'parent:' "
            "frontmatter field. Add parent: <relative-path> or set root: true for L1 docs."
        ]

    parent_abs = REPO_ROOT / parent_rel
    if not parent_abs.exists():
        return [
            f"ARCH-PARENT-NOTFOUND: '{rel_path}' declares parent: {parent_rel!r} "
            "but that file does not exist."
        ]

    parent_content = parent_abs.read_text(encoding="utf-8")
    parent_fm = _parse_frontmatter(parent_content) or {}

    errors.extend(_validate_level_order(rel_path, fm, parent_fm, parent_rel))
    errors.extend(_validate_markdown_link(rel_path, content, parent_rel))
    errors.extend(_validate_bidirectional(rel_path, parent_fm, parent_rel))

    return errors


# ---------------------------------------------------------------------------
# Check 2 — Python mermaid blocks require PARENT_DIAGRAM: in module header
# ---------------------------------------------------------------------------


def _check_py_mermaid(rel_path: str) -> list[str]:
    """Block Python files that have a mermaid block without PARENT_DIAGRAM:.

    Args:
        rel_path: Repo-relative path to the Python file.

    Returns:
        list[str]: Violation messages, empty when the check passes.
    """
    abs_path = REPO_ROOT / rel_path
    if not abs_path.exists():
        return []
    content = abs_path.read_text(encoding="utf-8")
    if not MERMAID_FENCE_RE.search(content):
        return []
    if PARENT_DIAGRAM_RE.search(content):
        return []
    return [
        f"PY-PARENT-DIAGRAM: '{rel_path}' contains a mermaid block but no "
        "'PARENT_DIAGRAM:' declaration in the module header. Add "
        "'PARENT_DIAGRAM: docs/architecture/<parent>.md' to the module docstring."
    ]


# ---------------------------------------------------------------------------
# Check 3 — SQL mermaid blocks require PARENT_DIAGRAM: in SQL header
# ---------------------------------------------------------------------------


def _check_sql_mermaid(rel_path: str) -> list[str]:
    """Block SQL files that have a mermaid block without PARENT_DIAGRAM:.

    Args:
        rel_path: Repo-relative path to the SQL file.

    Returns:
        list[str]: Violation messages, empty when the check passes.
    """
    abs_path = REPO_ROOT / rel_path
    if not abs_path.exists():
        return []
    content = abs_path.read_text(encoding="utf-8")
    if not MERMAID_FENCE_RE.search(content):
        return []
    if PARENT_DIAGRAM_RE.search(content):
        return []
    return [
        f"SQL-PARENT-DIAGRAM: '{rel_path}' contains a mermaid block but no "
        "'PARENT_DIAGRAM:' declaration in the SQL comment header. Add "
        "'PARENT_DIAGRAM: docs/architecture/<parent>.md' to the file header."
    ]


# ---------------------------------------------------------------------------
# Check 4 — ADR bidirectional: affects_diagrams ↔ diagram related_adrs
# ---------------------------------------------------------------------------


def _check_adr_diagram_link(rel_path: str) -> list[str]:
    """Validate that each diagram in affects_diagrams back-links to this ADR.

    Args:
        rel_path: Repo-relative path to the ADR markdown file.

    Returns:
        list[str]: Violation messages, empty when all bidirectional links are present.
    """
    errors: list[str] = []
    abs_path = REPO_ROOT / rel_path
    if not abs_path.exists():
        return []
    content = abs_path.read_text(encoding="utf-8")
    fm = _parse_frontmatter(content) or {}
    affects = fm.get("affects_diagrams") or []
    if not affects:
        return []

    adr_num_m = ADR_NUM_RE.search(Path(rel_path).name)
    adr_label = adr_num_m.group(0) if adr_num_m else Path(rel_path).stem

    for diagram_rel in affects:
        diagram_abs = REPO_ROOT / diagram_rel
        if not diagram_abs.exists():
            errors.append(
                f"ADR-DIAGRAM-NOTFOUND: '{rel_path}' lists affects_diagrams: "
                f"{diagram_rel!r} but that file does not exist."
            )
            continue
        diag_content = diagram_abs.read_text(encoding="utf-8")
        diag_fm = _parse_frontmatter(diag_content) or {}
        related = diag_fm.get("related_adrs") or []
        back_linked = any(adr_label in str(r) for r in related)
        if not back_linked:
            errors.append(
                f"ADR-BIDIRECTIONAL: '{rel_path}' lists affects_diagrams: "
                f"'{diagram_rel}' but that diagram does not list '{adr_label}' "
                "in its related_adrs: frontmatter. Add the ADR to related_adrs."
            )
    return errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    """Run all parent-link checks on staged files."""
    if _bypass_active():
        return 0

    staged = _get_staged_files()
    if not staged:
        return 0

    violations: list[str] = []

    for rel_path in staged:
        if ARCH_DOC_PATTERN.match(rel_path) and not ADR_PATTERN.match(rel_path):
            violations.extend(_check_arch_doc(rel_path))

        if ADR_PATTERN.match(rel_path):
            violations.extend(_check_adr_diagram_link(rel_path))

        if rel_path.endswith(".py") and "unit_tests" not in rel_path:
            violations.extend(_check_py_mermaid(rel_path))

        if rel_path.endswith(".sql"):
            violations.extend(_check_sql_mermaid(rel_path))

    if violations:
        print("\nMermaid Parent-Link Check Failed\n")
        for v in violations:
            print(f"  {v}\n")
        print(
            "  Fix: add the required parent: / children: / PARENT_DIAGRAM: / "
            "related_adrs: fields, or use [NO-ARCH-UPDATE] to bypass."
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
