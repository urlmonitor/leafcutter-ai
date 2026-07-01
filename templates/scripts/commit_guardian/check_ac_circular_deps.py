"""
MODULE: check_ac_circular_deps
GOAL: Pre-commit hook that detects circular depends_on chains in staged AC YAML
    files and blocks the commit with an error message naming the full cycle path.
BUSINESS CONTEXT: The depends_on field forms a directed graph of composition
    dependencies between AC patterns. If a circular dependency is introduced
    (e.g. PTN-010 -> PTN-020 -> PTN-010), pattern resolution would loop
    infinitely, breaking any tool that recursively resolves depends_on references.
    This hook enforces a directed-acyclic-graph (DAG) invariant on the
    depends_on graph at commit time, before circular additions enter the
    shared history.
ARCHITECTURE: Reads staged .yaml files from docs/acceptance-criteria/ (via
    git diff --cached, or HOOK_TEST_FILES env var for testing). Builds a
    combined depends_on graph by merging:
      - All on-disk AC YAML files via _ac_store_index.get_ac_index (shared
        mtime-cached index, parsed exactly once per commit across all hooks)
      - The staged versions of any changed files (to capture the proposed change)
    Then runs a depth-first search (DFS) to detect cycles in the merged graph.
    CRITICAL: the FULL graph scope is preserved — cycles can route through
    unstaged nodes, so all AC nodes from the index are included in the graph.
    If a cycle is detected that involves any staged AC ID, the commit is blocked
    with an error message listing the full cycle path
    (e.g. "Circular dependency detected: PTN-010 -> PTN-020 -> PTN-010").
    Fail-open: any unexpected exception exits 0 with [check-ac-circular-deps]
    prefix on stderr.

Exit codes:
    0 - No circular depends_on chains detected (or no AC files staged)
    1 - One or more circular depends_on chains detected involving staged files

Usage:
    python scripts/commit_guardian/run_hook.py \\
        scripts/commit_guardian/check_ac_circular_deps.py

DOC_LINKS:
  - docs/reference/ac-schema.md
  - docs/architecture/adrs/ADR-007-ac-store-schema-id-format-enforcement.md
  - config/ac_store_schema.json

DECISION HISTORY:
  - 2026-06-17 [python-coder/ACS-500e-1-i]: Created check_ac_circular_deps.py.
    Implements DAG invariant enforcement for depends_on graph at commit time.
    Loads the full AC store from disk and overlays staged changes to detect
    cycles introduced by the proposed commit. DFS-based cycle detection with
    cycle path reporting. Fail-open on unexpected exceptions.
  - 2026-06-30 [python-coder/TICKET-20260629-AC_Hook_Store_Index]: Replaced the
    per-invocation _build_depends_graph store walk with a call to
    _ac_store_index.get_ac_index(). The shared mtime-keyed cached index is
    parsed exactly once per commit across all four AC guardrail hooks. Full
    graph scope preserved: all AC nodes from the index are merged into the
    graph so cycles through unstaged nodes are still detected.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

try:
    from _ac_store_index import get_ac_index  # type: ignore[import]
    _AC_STORE_INDEX_AVAILABLE = True
except ImportError:
    _AC_STORE_INDEX_AVAILABLE = False


_HOOK_PREFIX = "[check-ac-circular-deps]"
_AC_STORE_DIR = "docs/acceptance-criteria"


# ---------------------------------------------------------------------------
# Project root detection
# ---------------------------------------------------------------------------


def _find_project_root() -> Path | None:
    """Find the project root by walking up from cwd.

    Uses HOOK_ROOT env var when set (testing / CI override).

    Returns:
        Absolute Path of the project root, or None if not found.
    """
    env_root = os.environ.get("HOOK_ROOT")
    if env_root:
        return Path(env_root)

    for ancestor in [Path.cwd(), *Path.cwd().parents]:
        if (ancestor / ".git").exists() or (ancestor / "CLAUDE.md").exists():
            return ancestor

    return None


# ---------------------------------------------------------------------------
# Staged file detection
# ---------------------------------------------------------------------------


def _get_staged_ac_paths() -> list[str]:
    """Return staged .yaml file paths under docs/acceptance-criteria/.

    Uses HOOK_TEST_FILES env var when set (OS pathsep- or newline-separated).
    In HOOK_NO_GIT mode, returns an empty list (no git interaction).

    Returns:
        List of path strings (absolute when from HOOK_TEST_FILES,
        relative to repo root when from git diff --cached).
    """
    test_files = os.environ.get("HOOK_TEST_FILES")
    if test_files:
        raw_paths = test_files.replace(os.pathsep, "\n").splitlines()
        return [
            p.strip()
            for p in raw_paths
            if p.strip() and p.strip().endswith(".yaml")
        ]

    if os.environ.get("HOOK_NO_GIT"):
        return []

    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: could not run git diff: {exc}",
            file=sys.stderr,
        )
        return []

    if result.returncode != 0:
        return []

    return [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
        and _AC_STORE_DIR in line
        and line.strip().endswith(".yaml")
    ]


# ---------------------------------------------------------------------------
# YAML loading (soft dependency on PyYAML; minimal fallback)
# ---------------------------------------------------------------------------


def _load_yaml_safe(content: str, source_label: str) -> dict | None:
    """Parse a YAML string, returning a dict or None on failure.

    Tries PyYAML first; falls back to a minimal line-oriented parser for
    simple top-level scalar/list fields when PyYAML is unavailable.

    Args:
        content: Raw YAML string.
        source_label: Human-readable label used in error messages.

    Returns:
        Parsed dict on success, None on parse failure (fail-open).
    """
    try:
        import yaml  # type: ignore[import]

        try:
            data = yaml.safe_load(content)
            return data if isinstance(data, dict) else None
        except yaml.YAMLError as exc:
            print(
                f"{_HOOK_PREFIX} WARNING: YAML parse error in {source_label}: {exc}",
                file=sys.stderr,
            )
            return None
    except ImportError:
        pass  # PyYAML absent — use minimal fallback

    # Minimal line-based fallback: handles top-level scalars only.
    # Lists (e.g. depends_on: [PTN-010, PTN-020]) are parsed as raw strings.
    result: dict = {}
    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        if not line or line.startswith("#") or line[0:1] in (" ", "\t"):
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip()
    return result or None


def _load_file_yaml(file_path: str) -> dict | None:
    """Read and parse a YAML file from disk.

    Args:
        file_path: Absolute or repo-relative path to the YAML file.

    Returns:
        Parsed dict on success, None on I/O or parse failure.
    """
    path = Path(file_path)
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: cannot read file {file_path}: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return None
    return _load_yaml_safe(content, source_label=str(file_path))


# ---------------------------------------------------------------------------
# depends_on extraction
# ---------------------------------------------------------------------------


def _extract_depends_on(data: dict) -> list[str]:
    """Extract the depends_on list from a parsed AC YAML dict.

    Handles three YAML representations produced by safe_load or the minimal
    fallback:
    - PyYAML list: ``depends_on: [PTN-010, PTN-020]``  → ``["PTN-010", "PTN-020"]``
    - PyYAML empty list: ``depends_on: []``              → ``[]``
    - Minimal fallback string: ``"[PTN-010, PTN-020]"`` → parsed via split
    - PyYAML null / missing / None                       → ``[]``

    Args:
        data: Parsed YAML dict from an AC file.

    Returns:
        List of dependency ID strings. Empty list when depends_on is absent or empty.
    """
    raw = data.get("depends_on")
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if item is not None and str(item).strip()]
    if isinstance(raw, str):
        stripped = raw.strip()
        if stripped in ("[]", ""):
            return []
        stripped = stripped.strip("[]")
        return [item.strip() for item in stripped.split(",") if item.strip()]
    return []


# ---------------------------------------------------------------------------
# Graph building
# ---------------------------------------------------------------------------


def _build_depends_graph(
    ac_store_root: Path,
    staged_overrides: dict[str, dict],
) -> dict[str, list[str]]:
    """Build a full depends_on adjacency list from the AC store.

    Uses _ac_store_index.get_ac_index when available for a shared mtime-cached
    index (parsed once per commit across all hooks). Falls back to a direct
    per-invocation rglob walk when the index module is unavailable.

    Staged files are substituted with their in-memory parsed content from
    staged_overrides (keyed by AC id) so the graph reflects the proposed
    commit state rather than the current HEAD state.

    FULL GRAPH SCOPE: all AC nodes from the index are included in the graph
    (not just staged files) because cycles can route through unstaged nodes.

    Args:
        ac_store_root: Path to the docs/acceptance-criteria/ directory.
        staged_overrides: Mapping from AC id string → parsed YAML dict for
            each file that is staged. These override the on-disk content for
            the same AC id, allowing cycle detection to use the proposed state.

    Returns:
        Adjacency list mapping each AC id to its list of depends_on ids.
        Keys are AC ids; values are lists of dependency ids.
    """
    graph: dict[str, list[str]] = {}

    if not ac_store_root.is_dir():
        return graph

    # Collect all AC ids from staged overrides first (they may be new files
    # not yet on disk, or modified versions of existing files).
    for ac_id, data in staged_overrides.items():
        deps = _extract_depends_on(data)
        graph[ac_id] = deps

    if _AC_STORE_INDEX_AVAILABLE:
        # Fast path: use the shared mtime-cached index.
        store_index = get_ac_index(str(ac_store_root))
        for ac_id, data in store_index.items():
            if ac_id in staged_overrides:
                # Staged version already recorded; skip on-disk version.
                continue
            deps = _extract_depends_on(data)
            graph[ac_id] = deps
        return graph

    # Slow path (fallback): per-invocation rglob walk when index module absent.
    for yaml_file in ac_store_root.rglob("*.yaml"):
        try:
            content = yaml_file.read_text(encoding="utf-8")
        except (OSError, ValueError):
            continue
        data = _load_yaml_safe(content, source_label=str(yaml_file))
        if data is None:
            continue
        ac_id = str(data.get("id", "")).strip()
        if not ac_id:
            continue
        if ac_id in staged_overrides:
            # Staged version already recorded; skip on-disk version
            continue
        deps = _extract_depends_on(data)
        graph[ac_id] = deps

    return graph


# ---------------------------------------------------------------------------
# Cycle detection (DFS)
# ---------------------------------------------------------------------------


def _find_cycle(
    graph: dict[str, list[str]],
    start_node: str,
) -> list[str] | None:
    """Detect a cycle reachable from start_node using iterative DFS.

    Args:
        graph: Adjacency list mapping each AC id to its depends_on ids.
        start_node: The AC id to begin the traversal from.

    Returns:
        A list of AC ids forming the cycle path (including the repeated start
        node at the end) if a cycle is found, or None if no cycle exists.
        Example return for a cycle PTN-010 -> PTN-020 -> PTN-010:
          ["PTN-010", "PTN-020", "PTN-010"]
    """
    # Iterative DFS: each stack entry is (current_node, path_so_far)
    stack: list[tuple[str, list[str]]] = [(start_node, [start_node])]

    while stack:
        current, path = stack.pop()
        neighbors = graph.get(current, [])
        for neighbor in neighbors:
            if neighbor == start_node:
                # Cycle detected: return the full path including the cycle close
                return [*path, neighbor]
            if neighbor not in path:
                stack.append((neighbor, [*path, neighbor]))

    return None


def _detect_all_cycles_for_staged(
    graph: dict[str, list[str]],
    staged_ids: set[str],
) -> list[str]:
    """Find all cycles in the graph that involve at least one staged AC id.

    Runs cycle detection only for nodes that are either staged or are
    dependencies of staged nodes, to keep the check focused on what the
    commit is changing. Returns only cycles that include a staged id on
    the path.

    Args:
        graph: Full adjacency list of the AC store (including staged changes).
        staged_ids: Set of AC ids that appear in staged files.

    Returns:
        List of human-readable error strings for each detected cycle.
        Each string takes the form:
          "Circular dependency detected: ID-A -> ID-B -> ID-A"
    """
    errors: list[str] = []
    # Track which start nodes we have already found cycles for, to avoid
    # reporting the same cycle multiple times from different entry points.
    reported_cycle_keys: set[frozenset] = set()

    for staged_id in staged_ids:
        # Only check nodes that appear in the graph (have depends_on or are
        # depended upon). Skip staged ids with no outgoing edges.
        if staged_id not in graph and not any(
            staged_id in deps for deps in graph.values()
        ):
            continue

        cycle = _find_cycle(graph, staged_id)
        if cycle is None:
            continue

        # Deduplicate: normalise the cycle as a frozenset of edges to
        # avoid reporting the same cycle from multiple starting points.
        cycle_edges = frozenset(zip(cycle[:-1], cycle[1:]))
        if cycle_edges in reported_cycle_keys:
            continue
        reported_cycle_keys.add(cycle_edges)

        path_str = " -> ".join(cycle)
        errors.append(f"Circular dependency detected: {path_str}")

    return errors


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _emit_violations(violations: list[str]) -> None:
    """Print violation messages to stderr for human-readable CI output.

    Args:
        violations: List of violation description strings.
    """
    print(
        f"\n{_HOOK_PREFIX} BLOCKED — circular depends_on chain(s) detected:",
        file=sys.stderr,
    )
    for i, v in enumerate(violations, start=1):
        print(f"  [{i}] {v}", file=sys.stderr)
    print(
        "\nTo fix: remove the depends_on reference that closes the cycle.",
        file=sys.stderr,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Run the circular depends_on chain detection check.

    Returns:
        0 when no cycles are detected (or no AC files staged).
        1 when one or more circular depends_on chains are detected.
    """
    # Discover project root and AC store
    project_root = _find_project_root()
    if project_root is not None:
        ac_store = project_root / _AC_STORE_DIR
    else:
        ac_store = Path.cwd() / _AC_STORE_DIR

    if not ac_store.is_dir():
        # No AC store — nothing to check
        return 0

    # Get staged AC YAML files
    staged_paths = _get_staged_ac_paths()
    if not staged_paths:
        return 0

    # Load staged files and build staged_overrides map: AC id → parsed dict
    staged_overrides: dict[str, dict] = {}
    for staged_path in staged_paths:
        abs_path = staged_path
        if not Path(staged_path).is_absolute():
            if project_root:
                abs_path = str(project_root / staged_path)
        data = _load_file_yaml(abs_path)
        if data is None:
            continue
        ac_id = str(data.get("id", "")).strip()
        if not ac_id:
            continue
        staged_overrides[ac_id] = data

    if not staged_overrides:
        # No recognisable AC files among staged paths — nothing to check
        return 0

    # Build the full depends_on graph, applying staged overrides
    graph = _build_depends_graph(ac_store, staged_overrides)

    # Detect cycles involving staged ids
    staged_ids = set(staged_overrides.keys())
    violations = _detect_all_cycles_for_staged(graph, staged_ids)

    if not violations:
        return 0

    _emit_violations(violations)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(
            f"{_HOOK_PREFIX} unexpected error (fail-open): {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        sys.exit(0)
