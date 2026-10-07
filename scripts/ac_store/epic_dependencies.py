"""
epic_dependencies.py — Leaf-to-leaf dependency resolution and build ordering.

MODULE: epic_dependencies
GOAL: Turn the AC store's ``depends_on`` graph into a leaf-to-leaf dependency
      map restricted to one generated set, then order that map topologically so
      dependees are built first — raising on a cycle before anything is written.
BUSINESS CONTEXT: Implements ACD-1200c (dependency wiring + topological sort).
      Extracted from goal_to_epic.py so that file can meet the 400-line
      check_file_size limit.
ARCHITECTURE: One O(n) store scan builds an in-memory index; all leaf lookups
      resolve from that index. Ordering is Kahn's BFS with alphabetical
      tie-breaking for determinism; cycle reporting is a coloured DFS. Imports
      epic_errors (CyclicDependencyError) and _gtfa_store (the shared
      prerequisite rule, deployed flat beside it). Deployed flat beside
      goal_to_epic.py in <output_root>/scripts/ac_store/ (see
      AC_STORE_DEPLOY_MAP in scripts/build_phases.py).

AC coverage owned by this module:
    ACD-1200c-1:   resolve_leaf_dependencies() resolves transitive depends_on
                   chains through composite ACs and emits only edges whose
                   endpoints are both in the generated leaf set.
    ACD-1200c-1-i: topological_sort() raises CyclicDependencyError with the
                   full cycle path BEFORE any file writes.
    ACD-1200c-2:   deterministic ordering via alphabetical tie-breaking;
                   diamond dependencies produce no duplicates.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from _gtfa_store import (
    _expects_from_ac_ids,
    _load_derive_parent_id_fn,
    _prerequisite_ac_ids,
)
from epic_errors import CyclicDependencyError

# ---------------------------------------------------------------------------
# Dependency resolution (ACD-1200c-1)
# ---------------------------------------------------------------------------


class DepGraph(dict):
    """Leaf dependency map that also carries the raw edge kinds for reporting.

    Behaves exactly like ``dict[str, list[str]]``; ``edges`` maps each owner
    AC id to ``{prerequisite: field}`` (``depends_on`` or ``expects_from``) so
    :func:`topological_sort` can name every edge of a cycle (BO-2600a-5 AC-8).
    """

    edges: dict[str, dict[str, str]]


def _load_records(ac_store_root: Path) -> dict[str, dict]:
    """Read every AC record in *ac_store_root* once, skipping unreadable files.

    Args:
        ac_store_root: Root directory of the AC YAML store.

    Returns:
        Mapping from AC id to its parsed record dict.
    """
    records: dict[str, dict] = {}
    for yaml_path in sorted(ac_store_root.rglob("*.yaml")):
        try:
            with open(yaml_path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except (yaml.YAMLError, OSError):
            continue
        if isinstance(data, dict) and data.get("id"):
            records[data["id"]] = data
    return records


def _scan_edges(ac_store_root: Path) -> dict[str, dict[str, str]]:
    """Build ``owner -> {prerequisite: field}`` for the whole store.

    Prerequisites are ``depends_on`` plus ``expects_from[].ac_id`` through the
    rule the ticket generator shares (:func:`_gtfa_store._prerequisite_ac_ids`).
    BO-2600a-5 AC-7: a child's ``depends_on`` on its own structural parent
    (``derive_parent_id``, as the generator uses) yields, and is not an ordering
    edge, when the parent's ``expects_from`` names that child. Every
    ``expects_from`` edge and every other parent link is kept.

    Args:
        ac_store_root: Root directory of the AC YAML store.

    Returns:
        Mapping from AC id to its ordered ``{prerequisite: field}`` edges.
    """
    records = _load_records(ac_store_root)
    derive = _load_derive_parent_id_fn(warn_context="epic ordering parent yield")
    edges: dict[str, dict[str, str]] = {}
    for ac_id, rec in records.items():
        parent = derive(ac_id) if derive is not None else None
        parent_rec = (records.get(parent) or {}) if parent is not None else {}  # root AC: no parent, no yield
        yields_parent = ac_id in _expects_from_ac_ids(parent_rec.get("expects_from"))
        expects = _expects_from_ac_ids(rec.get("expects_from"))
        owned: dict[str, str] = {}
        for dep in _prerequisite_ac_ids(rec):
            if dep == parent and yields_parent and dep not in expects:
                continue  # parent link yields to the parent's expects_from
            owned[dep] = "expects_from" if dep in expects and dep not in (rec.get("depends_on") or []) else "depends_on"
        edges[ac_id] = owned
    return edges


def _build_depends_on_index(ac_store_root: Path) -> dict[str, list[str]]:
    """Build a mapping from AC id to its ordering prerequisite ids.

    Scans *ac_store_root* once. Missing or malformed files are skipped.

    Args:
        ac_store_root: Root directory of the AC YAML store.

    Returns:
        Dict mapping AC id to the list of AC ids it must wait for (see
        :func:`_scan_edges`). ACs with none appear with an empty list.
    """
    return {ac_id: list(owned) for ac_id, owned in _scan_edges(ac_store_root).items()}


def _resolve_to_leaf_deps_from_index(
    ac_id: str,
    dep_index: dict[str, list[str]],
    leaf_id_set: frozenset[str],
    _visited: set[str] | None = None,
) -> list[str]:
    """Recursively resolve *ac_id*'s ``depends_on`` to leaf ACs in *leaf_id_set*.

    Follows composite AC references transitively until leaf ACs (those present
    in *leaf_id_set*) are reached. Cycles are broken by the *_visited* set so
    the recursion always terminates.

    Args:
        ac_id: The AC id whose dependencies are being resolved.
        dep_index: Pre-built mapping from AC id to its depends_on list
                   (built once by :func:`_build_depends_on_index`).
        leaf_id_set: Set of all leaf AC IDs in the generated set. Only
                     endpoints present here are emitted.
        _visited: Internal set used to prevent infinite loops in recursive
                  calls. Callers should not pass this argument.

    Returns:
        Deduplicated list of leaf AC IDs (from *leaf_id_set*) that *ac_id*
        transitively depends on.
    """
    if _visited is None:
        _visited = set()

    if ac_id in _visited:
        return []
    _visited.add(ac_id)

    raw_deps = dep_index.get(ac_id, [])
    leaf_deps: list[str] = []

    for dep_id in raw_deps:
        if dep_id in leaf_id_set:
            # Direct leaf-to-leaf edge
            leaf_deps.append(dep_id)
        else:
            # Composite AC — resolve transitively
            transitive = _resolve_to_leaf_deps_from_index(
                dep_id, dep_index, leaf_id_set, _visited
            )
            leaf_deps.extend(transitive)

    # Deduplicate while preserving insertion order
    seen: dict[str, None] = {}
    for item in leaf_deps:
        seen[item] = None
    return list(seen.keys())


def resolve_leaf_dependencies(
    leaf_ids: list[str],
    ac_store_root: Path,
) -> dict[str, list[str]]:
    """Build a leaf-to-leaf dependency map for the given leaf AC set.

    For each leaf AC in *leaf_ids*, resolves its ``depends_on`` chain
    transitively through any composite (non-leaf) ACs to find only the
    leaf-to-leaf edges. Dependency edges where the target is NOT in
    *leaf_ids* are silently dropped (the target may be outside the
    generated set).

    Missing AC references in ``depends_on`` fields are skipped without
    aborting — the AC store may reference ACs outside the generated set.

    Performance: scans *ac_store_root* once to build an in-memory index,
    then resolves all leaf dependencies from that index. Designed to complete
    in under 500ms for up to 100 leaf ACs with up to 500 dependency edges
    on a local filesystem.

    Args:
        leaf_ids: Ordered list of leaf AC ids in the generated set.
        ac_store_root: Root directory of the AC YAML store.

    Returns:
        A ``dict[str, list[str]]`` mapping each leaf AC id to the
        (possibly empty) list of leaf AC ids it depends on that are also
        in the generated set. Each leaf in *leaf_ids* is guaranteed to
        have a key in the returned dict.

    Example::

        resolve_leaf_dependencies(
            ["ACD-050a-2-i", "ACD-050a-1", "ACD-050b-1"],
            Path("docs/acceptance-criteria"),
        )
        # Returns:
        # {
        #   "ACD-050a-2-i": ["ACD-050a-1"],
        #   "ACD-050a-1":   [],
        #   "ACD-050b-1":   [],
        # }
    """
    # Build index once — O(n) store scan amortised across all leaf lookups
    edges = _scan_edges(ac_store_root)
    dep_index = {ac_id: list(owned) for ac_id, owned in edges.items()}
    leaf_id_set = frozenset(leaf_ids)
    result = DepGraph()
    result.edges = edges

    for leaf_id in leaf_ids:
        deps = _resolve_to_leaf_deps_from_index(leaf_id, dep_index, leaf_id_set)
        # Final guard: remove self-loops and any deps not in the set
        result[leaf_id] = [d for d in deps if d in leaf_id_set and d != leaf_id]

    return result


# ---------------------------------------------------------------------------
# Topological sort (ACD-1200c-2)
# ---------------------------------------------------------------------------


def _extract_cycle(
    dep_graph: dict[str, list[str]],
    cycle_nodes: set[str],
) -> list[str]:
    """Extract a human-readable cycle path from the remaining cyclic nodes.

    Uses DFS with path tracking to find one complete cycle among *cycle_nodes*.

    Args:
        dep_graph: Full dependency graph (node to list of dependencies).
        cycle_nodes: Set of node ids known to be in a cycle (those with
                     non-zero in-degree after Kahn's algorithm terminates).

    Returns:
        A list of AC ids forming one cycle, with the starting id repeated at
        the end: ``[id1, id2, ..., idN, id1]``. Returns ``["<unknown>"]``
        when no cycle can be found (should never happen if called correctly).
    """
    # Restrict graph to only the nodes in cycle_nodes
    sub_graph = {n: [d for d in dep_graph[n] if d in cycle_nodes] for n in cycle_nodes}

    WHITE, GREY, BLACK = 0, 1, 2
    color: dict[str, int] = {n: WHITE for n in sub_graph}

    def _dfs(node: str, path: list[str]) -> list[str] | None:
        """Depth-first search from *node*, returning the first cycle found.

        Args:
            node: The node to start (or continue) the search from.
            path: The GREY path accumulated so far; mutated in place.

        Returns:
            The cycle as a list of ids with the start repeated at the end, or
            None when no cycle is reachable from *node*.
        """
        color[node] = GREY
        path.append(node)
        for dep in sorted(sub_graph.get(node, [])):
            if dep not in color:
                continue
            if color[dep] == GREY:
                cycle_start = dep
                cycle_idx = path.index(cycle_start)
                return path[cycle_idx:] + [cycle_start]
            if color[dep] == WHITE:
                result = _dfs(dep, path)
                if result is not None:
                    return result
        path.pop()
        color[node] = BLACK
        return None

    for start_node in sorted(sub_graph.keys()):
        if color[start_node] == WHITE:
            found = _dfs(start_node, [])
            if found is not None:
                return found

    return ["<unknown>"]


def _build_in_degrees(
    dep_graph: dict[str, list[str]],
) -> tuple[dict[str, int], dict[str, list[str]]]:
    """Compute in-degree counts and the reverse adjacency map for Kahn's algorithm.

    Edges whose target is referenced but absent from *dep_graph* are skipped
    (treated as already satisfied), matching the out-of-set edge filter that
    :func:`resolve_leaf_dependencies` applies upstream.

    Args:
        dep_graph: Mapping from AC id to the list of AC ids it depends on.

    Returns:
        tuple[dict[str, int], dict[str, list[str]]]: The in-degree count per
        node, and ``reverse_edges[dep] -> [nodes that depend on dep]``.
    """
    in_degree: dict[str, int] = {node: 0 for node in dep_graph}
    # reverse_edges[dep] = list of nodes that depend on dep
    reverse_edges: dict[str, list[str]] = {node: [] for node in dep_graph}

    for node, deps in dep_graph.items():
        for dep in deps:
            if dep not in in_degree:
                # dep referenced but not in graph — skip (treated as satisfied)
                continue
            in_degree[node] += 1
            reverse_edges[dep].append(node)

    return in_degree, reverse_edges


def _real_path(
    start: str, goal: str, edges: dict[str, dict[str, str]], in_set: set[str]
) -> list[str] | None:
    """Shortest raw-edge path ``start -> ... -> goal`` through out-of-set ACs only.

    Args:
        start: Owner AC id.
        goal: Prerequisite AC id reached by the collapsed edge.
        edges: Raw ``owner -> {prerequisite: field}`` map.
        in_set: AC ids of the generated set (never used as intermediates).

    Returns:
        The id path including both ends, or None when no such path exists.
    """
    queue: list[list[str]] = [[start]]
    seen = {start}
    while queue:
        path = queue.pop(0)
        for nxt in sorted(edges.get(path[-1], {})):
            if nxt == goal:
                return [*path, nxt]
            if nxt not in seen and nxt not in in_set:
                seen.add(nxt)
                queue.append([*path, nxt])
    return None


def _cycle_message(cycle_path: list[str], dep_graph: dict[str, list[str]]) -> str:
    """Render the cycle error naming every AC and every edge (BO-2600a-5 AC-8).

    Each collapsed edge is expanded to the real store edges it stands for, so
    ACs outside the requested set are named. Edge format:
    ``<owner> -> <prerequisite> (<depends_on|expects_from>, parent-link: <true|false>)``.
    Without raw edge data (a plain dict) only the collapsed path is reported.

    Args:
        cycle_path: Collapsed cycle ``[a, b, ..., a]`` from :func:`_extract_cycle`.
        dep_graph: The graph that was being sorted; a :class:`DepGraph` carries
            the raw edges.

    Returns:
        The multi-line error message.
    """
    edges = getattr(dep_graph, "edges", None)
    if not edges:
        return f"Circular dependency detected: {' -> '.join(cycle_path)}"
    in_set = set(dep_graph)
    full = [cycle_path[0]]
    for owner, prereq in zip(cycle_path, cycle_path[1:]):
        full.extend((_real_path(owner, prereq, edges, in_set) or [owner, prereq])[1:])
    derive = _load_derive_parent_id_fn(warn_context="cycle report parent-link flag")
    lines = [f"Circular dependency detected: {' -> '.join(full)}"]
    for owner, prereq in zip(full, full[1:]):
        field = edges.get(owner, {}).get(prereq, "depends_on")
        is_parent = str(derive is not None and derive(owner) == prereq).lower()
        lines.append(f"  {owner} -> {prereq} ({field}, parent-link: {is_parent})")
    return "\n".join(lines)


def topological_sort(dep_graph: dict[str, list[str]]) -> list[str]:
    """Return the leaf AC ids in topological build order (Kahn's BFS algorithm).

    Dependees (ACs with no unresolved dependencies) appear first in the
    returned list. ACs that depend on others appear after their dependencies.

    The result is **deterministic**: when multiple nodes have zero in-degree
    simultaneously, they are ordered alphabetically to guarantee a stable
    ordering regardless of insertion order in *dep_graph*.

    Raises :class:`CyclicDependencyError` when a cycle is detected in
    *dep_graph*. The error message includes the full cycle path in the form:
    ``"Circular dependency detected: <id1> -> <id2> -> ... -> <id1>"``.

    Note: cycle detection fires before any ticket files are written or any
    AC YAML files are modified (ACD-1200c-1-i contract).

    Args:
        dep_graph: Mapping from AC id to list of AC ids it depends on
                   (output of :func:`resolve_leaf_dependencies`). All
                   ids referenced as values must also appear as keys.

    Returns:
        Ordered list of AC ids in build order (dependees first).

    Raises:
        CyclicDependencyError: When the dependency graph contains a cycle.

    Example::

        topological_sort({
            "ACD-050a-1": [],
            "ACD-050a-2": ["ACD-050a-1"],
            "ACD-050b-1": [],
        })
        # Returns: ["ACD-050a-1", "ACD-050b-1", "ACD-050a-2"]
        # (alphabetical tie-breaking among zero-in-degree nodes)
    """
    in_degree, reverse_edges = _build_in_degrees(dep_graph)

    # Initialize queue with all zero-in-degree nodes, sorted alphabetically
    queue: list[str] = sorted(node for node, deg in in_degree.items() if deg == 0)
    order: list[str] = []

    while queue:
        # Pop the alphabetically smallest zero-in-degree node for determinism
        node = queue.pop(0)
        order.append(node)

        for dependent in sorted(reverse_edges[node]):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)
                queue.sort()

    if len(order) != len(dep_graph):
        # Not all nodes were processed — there is a cycle
        remaining = {node for node, deg in in_degree.items() if deg > 0}
        cycle_path = _extract_cycle(dep_graph, remaining)
        raise CyclicDependencyError(_cycle_message(cycle_path, dep_graph))  # noqa: TRY003

    return order


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-10-07 [python-coder]: CI mypy follow-up, EPIC-BuildToolingRunsThrough.
  _scan_edges looks up the parent record only when derive_parent_id returned a
  parent; a root AC has no structural parent, so there is no yield. Same result
  as before for every non-None parent (arg-type fix).
- 2026-06-05 [EPIC-GoalToEpic/03]: Dependency wiring and topological sort.
  Implements ACD-1200c-1: resolve_leaf_dependencies() builds leaf-to-leaf
  dependency map by resolving transitive depends_on chains through composite
  ACs; only emits edges where both endpoints are in the generated leaf set;
  handles missing AC references gracefully; uses single-pass store index for
  O(n) performance. Implements ACD-1200c-1-i: topological_sort() via Kahn's
  BFS algorithm; raises CyclicDependencyError with full cycle path message
  before any file writes. Implements ACD-1200c-2: deterministic output via
  alphabetical tie-breaking; diamond dependencies produce no duplicates.
  run() wired to call resolve_leaf_dependencies + topological_sort before
  generate_tickets_for_leaves — cycle detection fires pre-write (ACD-1200c-1-i).
- 2026-09-14 12:00 [goal-to-epic-decompose]: Moved here from
  scripts/goal_to_epic.py, which exceeded the 400-line check_file_size limit.
  _build_depends_on_index, _resolve_to_leaf_deps_from_index,
  resolve_leaf_dependencies and _extract_cycle moved verbatim. Two edits, both
  behaviour-preserving: (1) the nested _dfs() helper inside _extract_cycle
  gained a docstring, which check_docstrings requires of an added definition
  and the original lacked; (2) topological_sort's in-degree/reverse-edge setup
  was extracted into _build_in_degrees(), lowering topological_sort from
  cyclomatic 12 to 7 with no change to the traversal, the alphabetical
  tie-breaking, or the CyclicDependencyError message.
  (#TICKETLESS reason=file-size-decomposition-refactor)
- 2026-10-06 [BO-2600a-5, EPIC-BuildToolingRunsThrough/08]: _build_depends_on_index
  now reads expects_from[].ac_id as well as depends_on, through
  _gtfa_store._prerequisite_ac_ids (the rule _build_ticket_depends_on uses), so
  an expects_from-only edge orders the epic and joins cycle detection.
- 2026-10-07 [BO-2600a-5, EPIC-BuildToolingRunsThrough/08, dec-46476988badbd5e6]:
  AC-7: a child's depends_on on its own structural parent yields (is not an
  ordering edge) when the parent's expects_from names that child; all other
  edges kept. AC-8: resolve_leaf_dependencies returns a DepGraph carrying the
  raw edge kinds, and topological_sort's CyclicDependencyError names every AC
  on the cycle (out-of-set ones too) and each edge as
  "<owner> -> <prereq> (<field>, parent-link: <true|false>)".
====================================================================
"""
