"""
MODULE: check_ac_limits
GOAL: Pre-commit hook that enforces AC tree depth limits on staged YAML files
    under docs/acceptance-criteria/ — hard cap: >7 L1s per L0 (ACS-100c-1),
    >5 L2s per L1 (ACS-100c-1); advisory: <3 children per parent (ACS-100c-2).
BUSINESS CONTEXT: Overcrowded AC trees are hard to navigate, review, and
    implement. This hook blocks commits that add a child AC that would push
    a parent over its limit, so the PO v3 or BA v3 agent can invoke the
    ac-tree-split skill before the file enters the repository. The sparse
    advisory warns when a parent has fewer than 3 children (a sign the
    AC may be misclassified) without blocking the commit.
ARCHITECTURE: Discovers all .yaml files staged in docs/acceptance-criteria/,
    loads them with PyYAML (stdlib fallback when absent), builds a parent->children
    map using the 'level' and 'depends_on' fields, then checks:
      - L0 nodes: count of L1 children > 7 → hard block (ACS-100c-1).
      - L1 nodes: count of L2 children > 5 → hard block (ACS-100c-1).
      - Any parent with 1 or 2 children → advisory warning (ACS-100c-2).
    Reads staged file list from git diff --cached (or HOOK_TEST_FILES env var
    for unit testing). Reads file content from disk (not from the diff) since
    the full tree context is needed, not just the diff hunk.
    Exits 0 on pass (including advisory-only); exits 1 on hard violations.

Exit codes:
    0 - All staged AC YAML files pass hard limits (advisories printed only)
    1 - One or more parents exceed their child limit (ACS-100c-1)

Usage:
    python scripts/commit_guardian/run_hook.py \\
        scripts/commit_guardian/check_ac_limits.py

DOC_LINKS:
  - templates/skills/ac-tree-split/SKILL.md

DECISION HISTORY:
  - 2026-06-05 [python-coder/EPIC-ACTreeSplit]: Created check_ac_limits.py.
    Enforces ACS-100c-1 (hard cap: >7 L1s/L0, >5 L2s/L1) and ACS-100c-2
    (advisory: <3 children). Reads full AC store from disk so the tree
    context is complete even when only one file is staged. Fail-open on
    subprocess / YAML errors to avoid blocking commits for unrelated reasons.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants — limits enforced by ACS-100c-1 and ACS-100c-2
# ---------------------------------------------------------------------------

_MAX_L1_PER_L0: int = 7   # ACS-100c-1 hard cap
_MAX_L2_PER_L1: int = 5   # ACS-100c-1 hard cap
_MIN_CHILDREN_ADVISORY: int = 3   # ACS-100c-2 sparse advisory (warn, don't block)

_AC_STORE_DIR = "docs/acceptance-criteria"

_VALID_LEVELS = {"L0", "L1", "L2", "L3"}
_PARENT_CHILD = {
    "L0": "L1",
    "L1": "L2",
    "L2": "L3",
}
_MAX_CHILDREN = {
    "L0": _MAX_L1_PER_L0,
    "L1": _MAX_L2_PER_L1,
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class AcNode:
    """A single acceptance-criterion record loaded from a YAML file."""

    ac_id: str
    level: str
    depends_on: list[str] = field(default_factory=list)
    source_path: Path | None = None


@dataclass
class TreeViolation:
    """A hard-cap violation on a parent AC."""

    parent_id: str
    parent_level: str
    child_level: str
    child_count: int
    limit: int


@dataclass
class TreeAdvisory:
    """A sparse-tree advisory on a parent AC."""

    parent_id: str
    child_count: int


# ---------------------------------------------------------------------------
# YAML loading (soft dependency on PyYAML)
# ---------------------------------------------------------------------------


def _load_yaml_data(path: Path) -> dict | None:
    """Load a YAML file; return a dict or None on parse/import failure.

    Tries PyYAML first; falls back to a minimal key: value parser when PyYAML
    is unavailable. Returns None on any error (fail-open).

    Args:
        path: Absolute path to a .yaml file.

    Returns:
        Parsed dict, or None when the file cannot be read or parsed.
    """
    try:
        import yaml  # type: ignore[import]

        try:
            with path.open(encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except (OSError, yaml.YAMLError) as exc:
            print(f"[check-ac-limits] WARNING: cannot parse {path}: {exc}", file=sys.stderr)
            return None
        return data if isinstance(data, dict) else None

    except ImportError:
        pass  # PyYAML absent — fall through to manual parser

    # Minimal fallback parser: handles simple top-level scalar fields only.
    result: dict = {}
    try:
        with path.open(encoding="utf-8") as fh:
            for raw_line in fh:
                line = raw_line.rstrip()
                if not line or line.startswith("#") or line[0].isspace():
                    continue
                if ":" in line:
                    key, _, value = line.partition(":")
                    result[key.strip()] = value.strip()
    except OSError as exc:
        print(f"[check-ac-limits] WARNING: cannot read {path}: {exc}", file=sys.stderr)
        return None
    return result or None


def _parse_depends_on(raw: object) -> list[str]:
    """Normalise the depends_on field to a list of strings.

    The field can be a YAML list, a scalar string, or absent/null.

    Args:
        raw: The value of the 'depends_on' key from a parsed YAML dict.

    Returns:
        List of dependency ID strings (may be empty).
    """
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(item) for item in raw if item is not None]
    if isinstance(raw, str):
        # Handle comma- or space-separated inline lists from the fallback parser
        stripped = raw.strip("[]")
        return [p.strip() for p in stripped.split(",") if p.strip()]
    return []


# ---------------------------------------------------------------------------
# AC store discovery and loading
# ---------------------------------------------------------------------------


def _find_ac_store_root() -> Path | None:
    """Locate the docs/acceptance-criteria/ directory from cwd or git root.

    Returns:
        Absolute path to the AC store directory, or None if not found.
    """
    env_root = os.environ.get("HOOK_ROOT")
    if env_root:
        candidate = Path(env_root) / _AC_STORE_DIR
        return candidate if candidate.is_dir() else None

    # Try cwd first, then walk upward to find a git root
    for ancestor in [Path.cwd(), *Path.cwd().parents]:
        candidate = ancestor / _AC_STORE_DIR
        if candidate.is_dir():
            return candidate
        if (ancestor / ".git").exists() or (ancestor / "CLAUDE.md").exists():
            break  # Reached project root — stop looking

    return None


def _load_ac_store(ac_store_dir: Path) -> list[AcNode]:
    """Load all .yaml files from the AC store directory into AcNode objects.

    Skips files whose 'level' field is absent or not in _VALID_LEVELS. Also
    skips files whose 'id' field is absent (cannot be a tree participant).

    Args:
        ac_store_dir: Absolute path to docs/acceptance-criteria/.

    Returns:
        List of AcNode objects representing the full AC tree.
    """
    nodes: list[AcNode] = []
    for yaml_file in sorted(ac_store_dir.rglob("*.yaml")):
        data = _load_yaml_data(yaml_file)
        if data is None:
            continue
        ac_id = data.get("id")
        level = data.get("level")
        if not ac_id or level not in _VALID_LEVELS:
            continue
        depends_on = _parse_depends_on(data.get("depends_on"))
        nodes.append(
            AcNode(
                ac_id=str(ac_id),
                level=str(level),
                depends_on=depends_on,
                source_path=yaml_file,
            )
        )
    return nodes


# ---------------------------------------------------------------------------
# Staged file detection
# ---------------------------------------------------------------------------


def _get_staged_ac_paths() -> list[str]:
    """Return staged .yaml file paths that live under docs/acceptance-criteria/.

    Uses HOOK_TEST_FILES env var (newline-separated path list) when set, so
    unit tests can inject a staged file list without running git.

    Returns:
        List of relative path strings (relative to repo root).
    """
    test_files = os.environ.get("HOOK_TEST_FILES")
    if test_files:
        return [
            p.strip()
            for p in test_files.splitlines()
            if p.strip() and _AC_STORE_DIR in p and p.strip().endswith(".yaml")
        ]

    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        print(
            f"[check-ac-limits] WARNING: could not run git diff: {exc}",
            file=sys.stderr,
        )
        return []

    if result.returncode != 0:
        return []

    return [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip() and _AC_STORE_DIR in line and line.strip().endswith(".yaml")
    ]


# ---------------------------------------------------------------------------
# Tree analysis
# ---------------------------------------------------------------------------


def _build_children_map(nodes: list[AcNode]) -> dict[str, list[AcNode]]:
    """Build a mapping from each AC id to its direct children.

    A child is identified by having its parent's ID in its 'depends_on' list
    and having the child level expected for that parent (L0->L1, L1->L2).

    Args:
        nodes: Full list of AcNode objects from the AC store.

    Returns:
        Dict mapping parent_id -> list of child AcNode objects.
    """
    id_to_node: dict[str, AcNode] = {n.ac_id: n for n in nodes}
    children_map: dict[str, list[AcNode]] = {n.ac_id: [] for n in nodes}

    for node in nodes:
        expected_child_level = None
        for parent_level, child_level in _PARENT_CHILD.items():
            if node.level == child_level:
                # Find which depends_on entries are parents at parent_level
                for dep_id in node.depends_on:
                    parent_node = id_to_node.get(dep_id)
                    if parent_node and parent_node.level == parent_level:
                        children_map[dep_id].append(node)
                break

    return children_map


def _check_limits(
    nodes: list[AcNode],
    children_map: dict[str, list[AcNode]],
    staged_ids: set[str],
) -> tuple[list[TreeViolation], list[TreeAdvisory]]:
    """Check hard limits and sparse advisory for all parents in the tree.

    Only parents whose children include at least one staged AC are checked for
    hard violations (to avoid flagging pre-existing oversized parents on every
    commit). Sparse advisories are emitted for all parents regardless.

    Args:
        nodes: Full list of AC nodes.
        children_map: Parent ID -> child AcNode list mapping.
        staged_ids: Set of AC IDs whose source files are staged.

    Returns:
        Tuple of (violations, advisories).
    """
    violations: list[TreeViolation] = []
    advisories: list[TreeAdvisory] = []

    for node in nodes:
        if node.level not in _MAX_CHILDREN:
            continue  # Only L0 and L1 can be parents with hard caps

        children = children_map.get(node.ac_id, [])
        child_count = len(children)
        limit = _MAX_CHILDREN[node.level]
        child_level = _PARENT_CHILD[node.level]

        # Hard limit: only report when at least one staged AC is involved
        # (either the parent itself is staged, or one of its children is staged).
        child_ids = {c.ac_id for c in children}
        involves_staged = (
            node.ac_id in staged_ids
            or bool(child_ids & staged_ids)
        )

        if involves_staged and child_count > limit:
            violations.append(
                TreeViolation(
                    parent_id=node.ac_id,
                    parent_level=node.level,
                    child_level=child_level,
                    child_count=child_count,
                    limit=limit,
                )
            )

        # Sparse advisory: warn for parents with 1 or 2 children that are staged
        if involves_staged and 0 < child_count < _MIN_CHILDREN_ADVISORY:
            advisories.append(
                TreeAdvisory(parent_id=node.ac_id, child_count=child_count)
            )

    return violations, advisories


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _print_advisories(advisories: list[TreeAdvisory]) -> None:
    """Print sparse-tree advisory messages to stderr (non-blocking).

    Args:
        advisories: List of TreeAdvisory objects to report.
    """
    for adv in advisories:
        print(
            f"[check-ac-limits] ADVISORY (ACS-100c-2): parent '{adv.parent_id}' "
            f"has only {adv.child_count} child(ren) — fewer than {_MIN_CHILDREN_ADVISORY} "
            f"suggests it may be too narrow. Consider merging into an existing parent "
            f"or planning additional children.",
            file=sys.stderr,
        )


def _print_violations(violations: list[TreeViolation]) -> None:
    """Print hard-limit violation messages to stderr.

    Args:
        violations: List of TreeViolation objects to report.
    """
    print("\n[check-ac-limits] BLOCKED — AC tree depth limits exceeded (ACS-100c-1)\n",
          file=sys.stderr)
    for v in violations:
        print(
            f"  Parent '{v.parent_id}' ({v.parent_level}): "
            f"{v.child_count} {v.child_level} children exceeds max {v.limit}.",
            file=sys.stderr,
        )
    print(
        "\nFix: load the ac-tree-split skill and run the appropriate split pattern "
        "before committing the new child AC.",
        file=sys.stderr,
    )
    print(
        "  Pattern A (horizontal): overcrowded L0 — create a sibling L0.\n"
        "  Pattern C (intermediate): overcrowded L1 — split into sibling L1s.\n",
        file=sys.stderr,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Run the AC tree depth limit check.

    Returns:
        0 when all staged AC files pass hard limits, 1 when any parent exceeds
        its child cap and the staged set involves that parent.
    """
    staged_paths = _get_staged_ac_paths()
    if not staged_paths:
        return 0  # No AC YAML files staged — nothing to check

    ac_store_dir = _find_ac_store_root()
    if ac_store_dir is None:
        # No AC store present — fail open (project may not use ACs yet)
        return 0

    nodes = _load_ac_store(ac_store_dir)
    if not nodes:
        return 0  # Empty store — nothing to check

    # Resolve staged AC IDs from staged paths
    staged_ids: set[str] = set()
    for staged_path in staged_paths:
        # Match staged relative path to loaded nodes
        for node in nodes:
            if node.source_path is not None:
                # Compare by path suffix (staged path is relative to repo root)
                try:
                    if str(node.source_path).endswith(staged_path.lstrip("/")):
                        staged_ids.add(node.ac_id)
                except (AttributeError, TypeError):
                    pass

    if not staged_ids:
        # Staged files did not match any known AC nodes — fail open
        return 0

    children_map = _build_children_map(nodes)
    violations, advisories = _check_limits(nodes, children_map, staged_ids)

    _print_advisories(advisories)

    if not violations:
        return 0

    _print_violations(violations)
    return 1


if __name__ == "__main__":
    sys.exit(main())
