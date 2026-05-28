"""
Pre-commit hook to warn or block when mermaid diagrams exceed complexity thresholds.

Parses every mermaid code block in staged .md files, counts structural elements
(nodes, edges, participants, subgraphs) by diagram type, and reports when
configurable thresholds are exceeded.

Usage:
    python scripts/commit_guardian/run_hook.py scripts/commit_guardian/check_mermaid_complexity.py

MODULE: check_mermaid_complexity.py
GOAL: Enforce complexity limits on mermaid diagrams at commit time.
BUSINESS CONTEXT: Prevents architecture diagrams from becoming unreadable walls of boxes.
ARCHITECTURE: Part of the commit_guardian hook suite; regex-based element counting.
"""

import re
import subprocess
import sys
from pathlib import Path

current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent

from config import (
    MERMAID_COMPLEXITY_MAX_BOUNDARIES,
    MERMAID_COMPLEXITY_MAX_CLASSES,
    MERMAID_COMPLEXITY_MAX_EDGES,
    MERMAID_COMPLEXITY_MAX_INTERACTIONS,
    MERMAID_COMPLEXITY_MAX_NODES,
    MERMAID_COMPLEXITY_MAX_PARTICIPANTS,
    MERMAID_COMPLEXITY_MAX_STATES,
    MERMAID_COMPLEXITY_MAX_TABLES,
    MERMAID_COMPLEXITY_STRICT,
)

BYPASS_TOKEN = "[NO-COMPLEXITY-CHECK]"

DIAGRAM_TYPE_PATTERNS = [
    (re.compile(r"^\s*(C4Context|C4Container|C4Component)"), "c4"),
    (re.compile(r"^\s*(flowchart|graph)\b"), "flowchart"),
    (re.compile(r"^\s*sequenceDiagram"), "sequence"),
    (re.compile(r"^\s*erDiagram"), "erd"),
    (re.compile(r"^\s*(stateDiagram-v2|stateDiagram)"), "state"),
    (re.compile(r"^\s*classDiagram"), "class"),
]

# Counting patterns per diagram type
C4_NODE_PATTERN = re.compile(
    r"^\s*(Component|Container|ContainerDb|System|System_Ext|Person|Person_Ext)\("
)
FLOWCHART_NODE_PATTERN = re.compile(r"^\s*\w+[\[\(\{>]")
FLOWCHART_EDGE_PATTERN = re.compile(r"(-->|---|-\.->|==>)")
C4_EDGE_PATTERN = re.compile(r"^\s*(Rel|BiRel|Rel_D|Rel_U|Rel_L|Rel_R)\(")
SEQUENCE_PARTICIPANT_PATTERN = re.compile(r"^\s*participant\s")
SEQUENCE_INTERACTION_PATTERN = re.compile(r"(->>|-->>|-\)|--\))")
ERD_TABLE_PATTERN = re.compile(r"^\s*\w+\s*\{")
STATE_PATTERN = re.compile(r"(^\s*\w+\s*:|^\s*state\s|\[\*\])")
CLASS_PATTERN = re.compile(r"^\s*class\s+\w+")
BOUNDARY_PATTERN = re.compile(
    r"(^\s*subgraph\b|System_Boundary\(|Container_Boundary\(|Boundary\()"
)


def detect_diagram_type(lines: list[str]) -> str | None:
    """Detect the mermaid diagram type from the first non-empty line."""
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        for pattern, dtype in DIAGRAM_TYPE_PATTERNS:
            if pattern.match(stripped):
                return dtype
        break
    return None


def count_elements(lines: list[str], diagram_type: str) -> dict[str, int]:
    """Count structural elements in a mermaid block by diagram type."""
    counts: dict[str, int] = {"boundaries": 0}

    for line in lines:
        if BOUNDARY_PATTERN.search(line):
            counts["boundaries"] += 1

    if diagram_type in ("flowchart", "c4"):
        counts["nodes"] = 0
        counts["edges"] = 0
        for line in lines:
            if diagram_type == "c4":
                if C4_NODE_PATTERN.match(line):
                    counts["nodes"] += 1
                if C4_EDGE_PATTERN.match(line):
                    counts["edges"] += 1
            else:
                if FLOWCHART_NODE_PATTERN.match(line):
                    counts["nodes"] += 1
                if FLOWCHART_EDGE_PATTERN.search(line):
                    counts["edges"] += 1

    elif diagram_type == "sequence":
        counts["participants"] = 0
        counts["interactions"] = 0
        for line in lines:
            if SEQUENCE_PARTICIPANT_PATTERN.match(line):
                counts["participants"] += 1
            if SEQUENCE_INTERACTION_PATTERN.search(line):
                counts["interactions"] += 1

    elif diagram_type == "erd":
        counts["tables"] = 0
        for line in lines:
            if ERD_TABLE_PATTERN.match(line):
                counts["tables"] += 1

    elif diagram_type == "state":
        counts["states"] = 0
        for line in lines:
            if STATE_PATTERN.search(line):
                counts["states"] += 1

    elif diagram_type == "class":
        counts["classes"] = 0
        for line in lines:
            if CLASS_PATTERN.match(line):
                counts["classes"] += 1

    return counts


def get_thresholds(diagram_type: str) -> dict[str, int]:
    """Return the threshold map for the given diagram type."""
    thresholds: dict[str, int] = {"boundaries": MERMAID_COMPLEXITY_MAX_BOUNDARIES}

    if diagram_type in ("flowchart", "c4"):
        thresholds["nodes"] = MERMAID_COMPLEXITY_MAX_NODES
        thresholds["edges"] = MERMAID_COMPLEXITY_MAX_EDGES
    elif diagram_type == "sequence":
        thresholds["participants"] = MERMAID_COMPLEXITY_MAX_PARTICIPANTS
        thresholds["interactions"] = MERMAID_COMPLEXITY_MAX_INTERACTIONS
    elif diagram_type == "erd":
        thresholds["tables"] = MERMAID_COMPLEXITY_MAX_TABLES
    elif diagram_type == "state":
        thresholds["states"] = MERMAID_COMPLEXITY_MAX_STATES
    elif diagram_type == "class":
        thresholds["classes"] = MERMAID_COMPLEXITY_MAX_CLASSES

    return thresholds


def extract_mermaid_blocks(content: str) -> list[tuple[int, list[str]]]:
    """Extract mermaid code blocks from markdown content.

    Returns:
        list of (block_number, lines) tuples.
    """
    blocks: list[tuple[int, list[str]]] = []
    in_block = False
    current_lines: list[str] = []
    block_num = 0

    for line in content.splitlines():
        if re.match(r"^\s*```mermaid", line):
            in_block = True
            current_lines = []
            block_num += 1
        elif in_block and re.match(r"^\s*```\s*$", line):
            in_block = False
            blocks.append((block_num, current_lines))
        elif in_block:
            current_lines.append(line)

    return blocks


def check_file(filepath: str) -> list[str]:
    """Check a single file for mermaid complexity violations.

    Returns:
        List of warning/error strings for this file.
    """
    try:
        content = Path(filepath).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    blocks = extract_mermaid_blocks(content)
    if not blocks:
        return []

    warnings: list[str] = []

    for block_num, lines in blocks:
        diagram_type = detect_diagram_type(lines)
        if diagram_type is None:
            continue

        counts = count_elements(lines, diagram_type)
        thresholds = get_thresholds(diagram_type)

        for metric, count in counts.items():
            threshold = thresholds.get(metric, 0)
            if threshold and count > threshold:
                warnings.append(
                    f"  mermaid block {block_num} ({diagram_type}): "
                    f"{count} {metric} (threshold: {threshold})"
                )

    return warnings


def get_commit_message() -> str:
    """Get the current commit message (if available)."""
    try:
        msg_file = Path(".git/COMMIT_EDITMSG")
        if msg_file.exists():
            return msg_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        pass
    return ""


def get_staged_md_files() -> list[str]:
    """Get staged .md files from git."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return []

    return [f for f in result.stdout.strip().split("\n") if f.endswith(".md") and f]


def main() -> int:
    """Run mermaid complexity checks on staged markdown files."""
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            pass

    commit_msg = get_commit_message()
    if BYPASS_TOKEN in commit_msg:
        return 0

    staged_files = get_staged_md_files()
    if not staged_files:
        return 0

    all_warnings: list[tuple[str, list[str]]] = []

    for filepath in staged_files:
        file_warnings = check_file(filepath)
        if file_warnings:
            all_warnings.append((filepath, file_warnings))

    if not all_warnings:
        return 0

    mode = "ERROR" if MERMAID_COMPLEXITY_STRICT else "WARNING"
    print(f"\n{'🚫' if MERMAID_COMPLEXITY_STRICT else '⚠️'}  Mermaid Complexity Check — {mode}\n")

    for filepath, warnings in all_warnings:
        print(f"{mode}: {filepath}")
        for w in warnings:
            print(w)
        print("  Consider splitting this diagram into separate concerns.\n")

    if MERMAID_COMPLEXITY_STRICT:
        print("Commit blocked. Fix the above or add [NO-COMPLEXITY-CHECK] to bypass.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
