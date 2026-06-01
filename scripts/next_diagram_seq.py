"""
MODULE: next_diagram_seq.py
GOAL: Print the next available sequence number for a given C4 level in
      docs/architecture/, so agents and developers never guess or collide
      on sequence numbers when naming a new diagram file.
BUSINESS CONTEXT: Architecture diagrams follow the c{level}-{seq:03d}-{slug}.md
                  naming convention. This script is the canonical source of
                  truth for sequence allocation — always run it before creating
                  a new diagram instead of guessing.
ARCHITECTURE: Scans docs/architecture/c{level}-*.md via glob, extracts the 3-digit
              sequence number from each filename, and prints max(used) + 1.
              Returns 1 when no files exist at that level. Read-only; does not
              modify any files.

====
DECISION HISTORY
- 2026-05-14 20:00 [EPIC-ArchitectureDocsEnforcement/ticket 09 — Hendrik/Claude]: (#EPIC-LeafcutterMVP/01)
  Created as the single authoritative tool for sequence allocation. Using
  max(existing) + 1 (rather than first-gap) intentionally avoids reuse of
  numbers from deleted diagrams, which would cause confusion in git history.
====
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_SEQ_RE = re.compile(r"^c([1-4])-(\d{3})-")


def _find_repo_root(start: Path) -> Path:
    """Walk up from start until a .git directory is found.

    Args:
        start: Directory path to begin the search.

    Returns:
        Path to the repository root directory.

    Raises:
        SystemExit: When no .git directory is found within 20 parent hops.
    """
    current = start.resolve()
    for _ in range(20):
        if (current / ".git").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    print("Error: could not determine repository root.", file=sys.stderr)
    sys.exit(1)


def next_seq(level: int, arch_dir: Path) -> int:
    """Return the next available sequence number for the given C4 level.

    Scans arch_dir for files matching c{level}-NNN-*.md, finds the highest
    existing sequence number, and returns that value plus one. Returns 1
    when no files exist at that level.

    Args:
        level: C4 level digit, must be 1, 2, 3, or 4.
        arch_dir: Path to the docs/architecture/ directory to scan.

    Returns:
        Integer sequence number to use for the next diagram at this level.
    """
    used: list[int] = []
    pattern = f"c{level}-*.md"
    for path in arch_dir.glob(pattern):
        match = _SEQ_RE.match(path.name)
        if match and int(match.group(1)) == level:
            used.append(int(match.group(2)))
    if not used:
        return 1
    return max(used) + 1


def main() -> None:
    """Entry point: print the next free sequence number for a C4 level.

    Expects one positional argument: the level integer (1–4).
    Prints a single integer to stdout.
    """
    if len(sys.argv) < 2:
        print("Usage: python next_diagram_seq.py <level>  (level is 1, 2, 3, or 4)", file=sys.stderr)
        sys.exit(1)

    try:
        level = int(sys.argv[1])
    except ValueError:
        print(f"Error: level must be an integer, got '{sys.argv[1]}'", file=sys.stderr)
        sys.exit(1)

    if level not in (1, 2, 3, 4):
        print(f"Error: level must be 1, 2, 3, or 4 — got {level}", file=sys.stderr)
        sys.exit(1)

    script_path = Path(__file__).resolve()
    repo_root = _find_repo_root(script_path.parent)
    arch_dir = repo_root / "docs" / "architecture"

    if not arch_dir.exists():
        print("1")
        return

    print(next_seq(level, arch_dir))


if __name__ == "__main__":
    main()
