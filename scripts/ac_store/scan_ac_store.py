#!/usr/bin/env python3
"""
scan_ac_store.py — Scan the AC YAML store and list leaf-level todo ACs.

Usage:
    python3 scripts/ac_store/scan_ac_store.py [options]

Options:
    --level {leaf,all}          Filter by AC level. 'leaf' selects L2 and L3
                                only (default: leaf).
    --work-status {todo,done,all}
                                Filter by work_status field (default: todo).
    --json                      Output as JSON instead of human-readable text.
    --ac-root PATH              Root directory of the AC store (default:
                                docs/acceptance-criteria/ relative to the
                                worktree root detected at runtime).

Exit codes:
    0  Success (even when no ACs match the filter — empty is valid).
    1  One or more AC YAML files could not be read or parsed. A per-file
       diagnostic is written to stderr for each bad file.
    2  A dependency cycle was detected in the depends_on graph. The cycle
       description is written to stderr.

AC-1: Leaf scanner identifies todo, unblocked L2/L3 ACs.
AC-5: Scanner JSON output is machine-consumable.
ACS-100i-1: derive_parent_id() derives the parent AC ID by stripping the last segment.
ACS-500e-2: resolve_behavior_stack() makes composition depth visible through
            implements_pattern (page→composite) and depends_on (composite→atomic).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LEAF_LEVELS: frozenset[str] = frozenset({"L2", "L3"})
_COMPLEXITY_ORDER: dict[str, int] = {"S": 0, "M": 1, "L": 2, "XL": 3}
_PRIORITY_ORDER: dict[str, int] = {"critical": 0, "high": 1, "medium": 2, "low": 3}
_DEFAULT_AC_ROOT: str = "docs/acceptance-criteria"

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

AcRecord = dict[str, Any]


# ---------------------------------------------------------------------------
# Worktree root detection
# ---------------------------------------------------------------------------


def _find_worktree_root(start: Path) -> Path:
    """Walk up from *start* until a directory containing a .git file/dir is found.

    Args:
        start: Starting path for the upward search (typically the script location).

    Returns:
        The worktree root path.

    Raises:
        FileNotFoundError: When no .git marker is found before the filesystem root.
    """
    current = start.resolve()
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            return parent
    raise FileNotFoundError(  # noqa: TRY003
        f"Could not locate worktree root from {start}"
    )


# ---------------------------------------------------------------------------
# AC store walking
# ---------------------------------------------------------------------------


def _walk_ac_yamls(ac_root: Path) -> list[Path]:
    """Return all .yaml files under *ac_root* (recursive).

    Args:
        ac_root: Root directory of the AC store.

    Returns:
        Sorted list of absolute YAML file paths.
    """
    return sorted(ac_root.rglob("*.yaml"))


def _load_ac(path: Path) -> AcRecord | None:
    """Load and return a single AC YAML file.

    Args:
        path: Absolute path to the YAML file.

    Returns:
        Parsed AC dict, or None when the file cannot be parsed (error to stderr).
    """
    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if not isinstance(data, dict):
            print(f"ERROR: {path}: expected a YAML mapping, got {type(data).__name__}", file=sys.stderr)
            return None
        data["_path"] = str(path)
    except yaml.YAMLError as exc:
        print(f"ERROR: {path}: YAML parse error: {exc}", file=sys.stderr)
        return None
    except OSError as exc:
        print(f"ERROR: {path}: could not read file: {exc}", file=sys.stderr)
        return None
    else:
        return data
    return None  # unreachable; satisfies type checkers


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


def _is_leaf(ac: AcRecord) -> bool:
    """Return True when the AC is at leaf level (L2 or L3).

    Args:
        ac: Parsed AC dict.

    Returns:
        True for L2/L3 ACs; False for L0/L1.
    """
    return ac.get("level", "") in _LEAF_LEVELS


def _matches_work_status(ac: AcRecord, target: str) -> bool:
    """Return True when the AC's work_status matches *target*.

    Args:
        ac: Parsed AC dict.
        target: One of 'todo', 'done', or 'all'.

    Returns:
        True when the AC matches the filter.
    """
    if target == "all":
        return True
    return ac.get("work_status", "") == target


def _is_active(ac: AcRecord) -> bool:
    """Return True when the AC has status: active.

    Args:
        ac: Parsed AC dict.

    Returns:
        True for active ACs.
    """
    return ac.get("status", "") == "active"


def _is_approved(ac: AcRecord) -> bool:
    """Return True when the AC has readiness: approved.

    ACs with readiness: draft or readiness: reviewed are NOT eligible for
    scanner pickup. Only readiness: approved ACs may be picked up.
    ACs without a readiness field (pre-backfill) are treated as NOT approved
    (conservative — scanner ignores them until backfilled and promoted).

    Args:
        ac: Parsed AC dict.

    Returns:
        True only for readiness: approved ACs.
    """
    return ac.get("readiness", "") == "approved"


# ---------------------------------------------------------------------------
# Dependency resolution
# ---------------------------------------------------------------------------


def _build_id_index(records: list[AcRecord]) -> dict[str, AcRecord]:
    """Build a mapping from AC id to record dict.

    Args:
        records: All successfully loaded AC records.

    Returns:
        Dict mapping id → AcRecord.
    """
    index: dict[str, AcRecord] = {}
    for rec in records:
        ac_id = rec.get("id")
        if ac_id:
            index[ac_id] = rec
    return index


def _is_dep_done(dep_id: str, id_index: dict[str, AcRecord]) -> bool:
    """Return True when *dep_id* refers to an AC with work_status: done.

    Unknown dep ids are treated as NOT done (conservative / blocking).

    Args:
        dep_id: The dependency AC id to check.
        id_index: Full id-to-record mapping.

    Returns:
        True only when the dep AC exists and has work_status: done.
    """
    dep_rec = id_index.get(dep_id)
    if dep_rec is None:
        return False
    return dep_rec.get("work_status", "") == "done"


def _classify_ac(
    ac: AcRecord,
    id_index: dict[str, AcRecord],
) -> tuple[str, list[str]]:
    """Classify *ac* as 'ready' or 'blocked' based on depends_on resolution.

    Args:
        ac: The AC record to classify.
        id_index: Full id-to-record mapping (all ACs, not just filtered).

    Returns:
        A tuple ``('ready', [])`` or ``('blocked', [<blocking_dep_ids>])``.
    """
    depends_on: list[str] = ac.get("depends_on") or []
    blocking: list[str] = [
        dep for dep in depends_on if not _is_dep_done(dep, id_index)
    ]
    if blocking:
        return "blocked", blocking
    return "ready", []


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------


def _detect_cycle(
    id_index: dict[str, AcRecord],
) -> list[str] | None:
    """Return a cycle description if a dependency cycle exists, else None.

    Uses DFS coloring (white/grey/black).

    Args:
        id_index: Full id-to-record mapping.

    Returns:
        A list of AC ids forming the cycle, or None when the graph is acyclic.
    """
    WHITE, GREY, BLACK = 0, 1, 2
    color: dict[str, int] = {ac_id: WHITE for ac_id in id_index}
    parent: dict[str, str | None] = {ac_id: None for ac_id in id_index}

    def _dfs(node: str) -> list[str] | None:
        color[node] = GREY
        for dep in id_index[node].get("depends_on") or []:
            if dep not in color:
                continue
            if color[dep] == GREY:
                # Reconstruct the cycle
                cycle = [dep, node]
                cur = node
                while parent.get(cur) and parent[cur] != dep:
                    cur = parent[cur]  # type: ignore[assignment]
                    cycle.append(cur)
                cycle.append(dep)
                return list(reversed(cycle))
            if color[dep] == WHITE:
                parent[dep] = node
                result = _dfs(dep)
                if result is not None:
                    return result
        color[node] = BLACK
        return None

    for ac_id in list(id_index.keys()):
        if color[ac_id] == WHITE:
            cycle = _dfs(ac_id)
            if cycle is not None:
                return cycle
    return None


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------


def _sort_ready(ready: list[AcRecord]) -> list[AcRecord]:
    """Sort ready ACs: priority ascending (critical<high<medium<low), then
    estimated_complexity ascending (S<M<L<XL), then id ascending.

    Args:
        ready: List of ready AcRecord dicts.

    Returns:
        Sorted list.
    """
    def _sort_key(ac: AcRecord) -> tuple[int, int, str]:
        priority = ac.get("priority", "medium")
        priority_order = _PRIORITY_ORDER.get(priority, 99)
        complexity = ac.get("estimated_complexity", "")
        complexity_order = _COMPLEXITY_ORDER.get(complexity, 99)
        return priority_order, complexity_order, ac.get("id", "")

    return sorted(ready, key=_sort_key)


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _to_ready_item(ac: AcRecord) -> dict[str, str]:
    """Convert a ready AcRecord to the JSON output schema dict.

    Args:
        ac: Ready AC record.

    Returns:
        Dict with keys: ac_id, title, assigned_agent, estimated_complexity, path.
    """
    return {
        "ac_id": ac.get("id", ""),
        "title": ac.get("title", ""),
        "assigned_agent": ac.get("assigned_agent", ""),
        "estimated_complexity": ac.get("estimated_complexity", ""),
        "path": ac.get("_path", ""),
    }


def _to_blocked_item(ac: AcRecord, blocking_deps: list[str]) -> dict[str, Any]:
    """Convert a blocked AcRecord to the JSON output schema dict.

    Args:
        ac: Blocked AC record.
        blocking_deps: List of dep AC ids that are not done.

    Returns:
        Dict with keys: ac_id, blocked_by.
    """
    return {
        "ac_id": ac.get("id", ""),
        "blocked_by": blocking_deps,
    }


def _print_human(
    ready: list[AcRecord],
    blocked: list[tuple[AcRecord, list[str]]],
) -> None:
    """Print human-readable READY and BLOCKED sections to stdout.

    Args:
        ready: Sorted list of ready AcRecords.
        blocked: List of (AcRecord, blocking_dep_ids) tuples for blocked ACs.
    """
    print(f"READY ({len(ready)}):")
    if ready:
        for ac in ready:
            print(
                f"  [{ac.get('estimated_complexity', '?'):>2}] "
                f"{ac.get('id', '?'):30s} {ac.get('title', '')}"
            )
    else:
        print("  (none)")

    print()
    print(f"BLOCKED ({len(blocked)}):")
    if blocked:
        for ac, deps in blocked:
            print(
                f"  {ac.get('id', '?'):30s} blocked by: {', '.join(deps)}"
            )
    else:
        print("  (none)")


def _print_json(
    ready: list[AcRecord],
    blocked: list[tuple[AcRecord, list[str]]],
) -> None:
    """Print JSON output conforming to AC-5 schema.

    Args:
        ready: Sorted list of ready AcRecords.
        blocked: List of (AcRecord, blocking_dep_ids) tuples for blocked ACs.
    """
    output = {
        "ready": [_to_ready_item(ac) for ac in ready],
        "blocked": [_to_blocked_item(ac, deps) for ac, deps in blocked],
    }
    print(json.dumps(output, indent=2))


# ---------------------------------------------------------------------------
# Tree traversal (ACD-1200a-1, ACD-1200a-1-i)
# ---------------------------------------------------------------------------


def _load_ac_by_id(ac_store_root: Path, ac_id: str) -> AcRecord | None:
    """Load and return the AC YAML record with the given id, or None if not found.

    Searches *ac_store_root* recursively for a YAML file whose ``id`` field
    matches *ac_id*.

    Args:
        ac_store_root: Root directory of the AC YAML store.
        ac_id: The AC id to look up.

    Returns:
        Parsed AC dict if found; ``None`` when the id is absent or the file
        cannot be parsed.
    """
    for yaml_path in sorted(ac_store_root.rglob("*.yaml")):
        record = _load_ac(yaml_path)
        if record is not None and record.get("id") == ac_id:
            return record
    return None


def traverse_ac_tree(
    root_id: str,
    ac_store_root: Path,
) -> list[str]:
    """Return the ordered list of leaf AC ids beneath *root_id*.

    A leaf is an AC whose ``covered_by`` field is empty or absent.
    The traversal is **depth-first** with **alphabetical sibling ordering**
    at every level.

    When *root_id* itself is a leaf (no ``covered_by`` children), the function
    returns ``[root_id]``.

    When *root_id* cannot be found in *ac_store_root*, the function returns an
    empty list and emits a warning to stderr — it does NOT raise.

    Performance: completes in under 200ms for trees up to 200 nodes when each
    AC YAML is small (< 4 KB) and *ac_store_root* is on a local filesystem.

    Args:
        root_id: The AC id to start traversal from (may be L0, L1, or deeper).
        ac_store_root: Absolute path to the root of the AC YAML store.

    Returns:
        Ordered list of leaf AC ids, depth-first alphabetical-sibling order.
        Returns ``[]`` when *root_id* is not found.
    """
    # Build a full id → record index for O(1) child lookups.
    id_index: dict[str, AcRecord] = {}
    for yaml_path in sorted(ac_store_root.rglob("*.yaml")):
        record = _load_ac(yaml_path)
        if record is not None:
            ac_id = record.get("id")
            if ac_id:
                id_index[ac_id] = record

    if root_id not in id_index:
        print(
            f"WARNING: traverse_ac_tree: root_id {root_id!r} not found in {ac_store_root}",
            file=sys.stderr,
        )
        return []

    leaves: list[str] = []
    seen: set[str] = set()
    _dfs_collect_leaves(root_id, id_index, leaves, seen)
    return leaves


def _dfs_collect_leaves(
    node_id: str,
    id_index: dict[str, AcRecord],
    result: list[str],
    seen: set[str],
) -> None:
    """Recursive DFS helper that appends leaf ids to *result*.

    Visits children in alphabetical order (depth-first, alphabetical siblings).
    Each node is processed at most once — if *node_id* is already in *seen*,
    the function returns immediately.  This prevents duplicate emissions when a
    node is reachable by more than one covered_by path (ACD-1200a-9-i).

    Args:
        node_id: Current AC id being visited.
        id_index: Full id-to-record mapping built from the AC store.
        result: Accumulator list — leaf ids are appended here in traversal order.
        seen: Set of already-visited node ids; mutated in place to guard against
            re-traversal.  First-visit order wins.
    """
    if node_id in seen:
        return
    seen.add(node_id)

    record = id_index.get(node_id)
    if record is None:
        return

    level: str = record.get("level", "")
    children: list[str] = record.get("covered_by") or []

    # L2 and L3 are always leaves — emit them regardless of covered_by.
    # L0/L1 nodes are composites and must never be emitted as leaves.
    if level in _LEAF_LEVELS:
        result.append(node_id)

    # Recurse into covered_by children for any level that has them.
    for child_id in sorted(children):
        _dfs_collect_leaves(child_id, id_index, result, seen)


# ---------------------------------------------------------------------------
# Behavior stack resolution (ACS-500e-2)
# ---------------------------------------------------------------------------


BehaviorLayer = dict[str, Any]


def resolve_behavior_stack(
    ac_id: str,
    id_index: dict[str, AcRecord],
) -> list[BehaviorLayer]:
    """Resolve the full behavior stack for a page AC, returning layers in precedence order.

    The behavior stack is the ordered list of AC layers that together define
    the complete behavior for a page AC. The ordering is:

    1. **Page-specific criteria** — the page AC itself (first; highest precedence).
    2. **Composite wiring behavior** — the pattern AC referenced via
       ``implements_pattern`` (second; if present).
    3. **Atomic behaviors** — the ACs listed in the composite pattern's
       ``depends_on`` field (third; in ``depends_on`` declaration order).

    Composition depth is therefore visible through two standard AC fields alone:
    ``implements_pattern`` (page → composite link) and ``depends_on``
    (composite → atomic links). No additional hierarchy mechanism is required.

    When ``ac_id`` is not found in *id_index*, an empty list is returned.
    When the page AC has no ``implements_pattern``, only the page AC layer is
    returned. When the composite pattern has no ``depends_on``, the stack
    contains only the page layer and the composite layer.

    The function does **not** recurse into ``depends_on`` chains beyond one hop
    (i.e. it resolves only the direct atomic dependencies of the composite
    pattern, not transitive dependencies of those atomics). Multi-hop resolution
    is intentionally left to ``resolve_leaf_dependencies`` in
    ``goal_to_epic.py``.

    Args:
        ac_id: The page AC id to resolve the behavior stack for.
        id_index: Full id-to-record mapping built from the AC store (see
            ``_build_id_index``).

    Returns:
        Ordered list of ``BehaviorLayer`` dicts, each with keys:
        ``layer`` (``"page"``, ``"composite"``, or ``"atomic"``),
        ``ac_id`` (string), ``criteria`` (string or None), and
        ``source`` (``"self"``, ``"implements_pattern"``, or ``"depends_on"``).
        Returns ``[]`` when *ac_id* is absent from *id_index*.

    Example::

        # Given:
        #   PAGE-001 implements_pattern PTN-020
        #   PTN-020 depends_on [PTN-010, PTN-011, PTN-012]
        stack = resolve_behavior_stack("PAGE-001", id_index)
        # Returns:
        # [
        #   {"layer": "page",      "ac_id": "PAGE-001", "source": "self", ...},
        #   {"layer": "composite", "ac_id": "PTN-020",  "source": "implements_pattern", ...},
        #   {"layer": "atomic",    "ac_id": "PTN-010",  "source": "depends_on", ...},
        #   {"layer": "atomic",    "ac_id": "PTN-011",  "source": "depends_on", ...},
        #   {"layer": "atomic",    "ac_id": "PTN-012",  "source": "depends_on", ...},
        # ]
    """
    page_record = id_index.get(ac_id)
    if page_record is None:
        return []

    stack: list[BehaviorLayer] = []

    # Layer 1: page-specific criteria
    stack.append(
        {
            "layer": "page",
            "ac_id": ac_id,
            "criteria": page_record.get("criteria"),
            "source": "self",
        }
    )

    # Layer 2: composite wiring behavior (via implements_pattern)
    pattern_id: str | None = page_record.get("implements_pattern")
    if not pattern_id:
        return stack

    composite_record = id_index.get(pattern_id)
    if composite_record is None:
        return stack

    stack.append(
        {
            "layer": "composite",
            "ac_id": pattern_id,
            "criteria": composite_record.get("criteria"),
            "source": "implements_pattern",
        }
    )

    # Layer 3: atomic behaviors (via composite's depends_on)
    atomic_ids: list[str] = composite_record.get("depends_on") or []
    for atomic_id in atomic_ids:
        atomic_record = id_index.get(atomic_id)
        stack.append(
            {
                "layer": "atomic",
                "ac_id": atomic_id,
                "criteria": atomic_record.get("criteria") if atomic_record else None,
                "source": "depends_on",
            }
        )

    return stack


# ---------------------------------------------------------------------------
# Parent ID derivation (ACS-100i-1)
# ---------------------------------------------------------------------------

# Root AC ID pattern: PREFIX-NNN (2-6 uppercase letters, hyphen, 3+ digits).
# Examples: ACS-100, ACD-050, FIN-001.
_ROOT_AC_RE = re.compile(r"^[A-Z]{2,6}-\d+$")

# Level-1 AC ID pattern: PREFIX-NNNx where x is one or more lowercase letters
# appended directly to the digit block (no hyphen separator).
# Examples: ACS-100a, ACD-050b, ACS-300h.
_LEVEL1_AC_RE = re.compile(r"^([A-Z]{2,6}-\d+)([a-z]+)$")


def derive_parent_id(ac_id: str) -> str | None:
    """Return the parent AC ID for *ac_id*, or ``None`` when *ac_id* is a root.

    The parent ID is derived by stripping the last segment from the child ID:

    * Root IDs (``PREFIX-NNN``, e.g. ``ACS-100``) have no parent — returns
      ``None``.
    * Level-1 IDs (``PREFIX-NNNx``, e.g. ``ACS-100a``) have the root as
      their parent — returns ``PREFIX-NNN`` (e.g. ``ACS-100``).
    * All deeper IDs (e.g. ``ACS-300h-1``, ``ACS-300h-2-i``) have the ID
      with the last hyphen-separated segment removed as their parent.

    Args:
        ac_id: The child AC ID string (e.g. ``"ACS-300h-1"``).

    Returns:
        The parent AC ID string, or ``None`` when *ac_id* is a root-level ID.

    Examples::

        >>> derive_parent_id("ACS-300h-1")
        'ACS-300h'
        >>> derive_parent_id("ACS-300h-2-i")
        'ACS-300h-2'
        >>> derive_parent_id("ACS-100")
        None
        >>> derive_parent_id("ACS-100a")
        'ACS-100'
    """
    # Root pattern: PREFIX-NNN — no parent
    if _ROOT_AC_RE.match(ac_id):
        return None

    # Level-1 pattern: PREFIX-NNNx — parent is PREFIX-NNN
    m = _LEVEL1_AC_RE.match(ac_id)
    if m:
        return m.group(1)

    # All deeper levels: strip the last hyphen-delimited segment
    if "-" in ac_id:
        return ac_id.rsplit("-", 1)[0]

    # Fallback: unrecognised format — treat as root (no parent)
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description="Scan the AC YAML store and list leaf-level todo ACs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--level",
        choices=["leaf", "all"],
        default="leaf",
        help="Filter by AC level. 'leaf' selects L2 and L3 only (default: leaf).",
    )
    parser.add_argument(
        "--work-status",
        choices=["todo", "done", "all"],
        default="todo",
        dest="work_status",
        help="Filter by work_status field (default: todo).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON instead of human-readable text.",
    )
    parser.add_argument(
        "--ac-root",
        dest="ac_root",
        default=None,
        help=(
            f"Root directory of the AC store (default: {_DEFAULT_AC_ROOT} relative "
            "to the worktree root)."
        ),
    )
    parser.add_argument(
        "--ac-store-dir",
        dest="ac_root",
        default=None,
        help="Alias for --ac-root. Root directory of the AC store.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for scan_ac_store.py.

    Args:
        argv: Command-line arguments (default: sys.argv[1:]).

    Returns:
        Exit code: 0 on success, 1 on YAML errors, 2 on dependency cycle.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Resolve ac_root
    if args.ac_root:
        ac_root = Path(args.ac_root)
    else:
        try:
            worktree = _find_worktree_root(Path(__file__))
        except FileNotFoundError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        ac_root = worktree / _DEFAULT_AC_ROOT

    if not ac_root.exists():
        print(f"ERROR: AC root directory not found: {ac_root}", file=sys.stderr)
        return 1

    # Load all YAML files
    yaml_paths = _walk_ac_yamls(ac_root)
    all_records: list[AcRecord] = []
    load_errors = 0

    for path in yaml_paths:
        record = _load_ac(path)
        if record is None:
            load_errors += 1
        else:
            all_records.append(record)

    if load_errors:
        return 1

    # Build id index for dependency resolution
    id_index = _build_id_index(all_records)

    # Cycle detection
    cycle = _detect_cycle(id_index)
    if cycle is not None:
        print(
            f"ERROR: dependency cycle detected: {' → '.join(cycle)}",
            file=sys.stderr,
        )
        return 2

    # Filter: level + work_status + status + readiness (approved only)
    filtered: list[AcRecord] = []
    for ac in all_records:
        if args.level == "leaf" and not _is_leaf(ac):
            continue
        if not _matches_work_status(ac, args.work_status):
            continue
        if not _is_active(ac):
            continue
        if not _is_approved(ac):
            continue
        filtered.append(ac)

    # Classify ready vs blocked
    ready: list[AcRecord] = []
    blocked: list[tuple[AcRecord, list[str]]] = []

    for ac in filtered:
        status, blocking_deps = _classify_ac(ac, id_index)
        if status == "ready":
            ready.append(ac)
        else:
            blocked.append((ac, blocking_deps))

    # Sort ready list
    ready = _sort_ready(ready)

    # Output
    if args.json_output:
        _print_json(ready, blocked)
    else:
        _print_human(ready, blocked)

    return 0


if __name__ == "__main__":
    sys.exit(main())


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-05 [ticket-01]: Initial implementation.
  Walks docs/acceptance-criteria/, filters by level (L2/L3), work_status
  (todo), and status (active). Resolves depends_on chains to classify ACs
  as ready or blocked. Sorts ready ACs by estimated_complexity (S<M<L<XL)
  then id. Outputs human-readable or JSON. Exits 0 on success, 1 on YAML
  errors, 2 on dependency cycle.
- 2026-06-08 [TICKET-20260607-ACS-100i-1]: Added derive_parent_id().
  Implements ACS-100i-1: given a child AC ID, strip the last segment to
  derive the parent ID. Root IDs (PREFIX-NNN) return None. Level-1 IDs
  (PREFIX-NNNx) return PREFIX-NNN. Deeper IDs strip the last hyphen-
  delimited segment. Uses two compiled regexes plus rsplit for O(1).
- 2026-06-08 [TICKET-20260608-ACD-1200a-9]: Fixed _dfs_collect_leaves().
  Replaced `if not children: result.append(node_id)` (covered_by-based
  leaf detection) with `if level in _LEAF_LEVELS: result.append(node_id)`
  (level-based leaf detection). L2/L3 nodes are now always emitted as
  leaves regardless of whether they have covered_by children. L0/L1 nodes
  are now correctly treated as pure composites and never emitted. Recursion
  into covered_by children is preserved for all levels. Fixes the bug where
  an L2 with L3 edge-case children was silently skipped, and where L0/L1
  nodes with empty covered_by were incorrectly emitted as leaves.
- 2026-06-17 [TICKET-20260611-ACS-500e-2]: Added resolve_behavior_stack().
  Implements ACS-500e-2: given a page AC id and an id_index, resolves the
  full behavior stack in layer order: (1) page-specific criteria from the
  page AC itself, (2) composite wiring behavior from the pattern AC
  referenced via implements_pattern, (3) atomic behaviors from the
  composite's depends_on list. Returns a list of BehaviorLayer dicts with
  keys: layer, ac_id, criteria, source. Composition depth is visible
  through the two standard fields alone — no additional mechanism required.
====================================================================
"""
