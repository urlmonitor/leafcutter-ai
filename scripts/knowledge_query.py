"""
MODULE: knowledge_query
GOAL: Single-pass traversal of all knowledge surfaces defined in paths.json.
      Produces a flat node+edge index for cross-surface search and graph export.
BUSINESS CONTEXT: Gives agents and humans a one-command answer to
    "show me everything related to X" across all leafcutter knowledge surfaces.
    Reads paths.json for surface discovery, traverses tickets, ADRs, docs,
    agents, skills, components, roadmap, glossary, acs, and feedback in a
    single pass, extracts a one-line description for every node, follows
    cross-surface edges, and dumps a flat index in both human-readable text
    and JSON format.
ARCHITECTURE: Seven public functions (load_surfaces, load_surfaces_with_meta,
    build_knowledge_map, validate_knowledge_map, validate_edges_integrity,
    extract_nodes, extract_edges) and a CLI entry point.
    build_knowledge_map() is the primary API for callers that need both the
    graph data and surface-completeness audit metadata (declared_surfaces,
    contributing_surfaces). validate_knowledge_map() verifies each declared
    surface produces only the edge relationship kinds it declares in paths.json
    — the check is fully data-driven, so adding or removing a surface in
    paths.json changes the validated set without any code edit.
    validate_edges_integrity() validates edges in a KnowledgeMap using a
    two-tier policy (AC KM-KGS-100d-2-i): edges whose target node is absent
    are silently **dropped** (logged at DEBUG; recorded in
    ``EdgeIntegrityResult.dropped_edges``) rather than flagged as integrity
    violations — the build must not fail solely because a relationship named
    a missing target.  Only edges whose source node is absent are treated as
    true integrity failures.  There is no edge-type exemption (KM-KGS-100d-2,
    amended): a field a surface declares in its own ``file_path_fields`` now
    means "resolve this field's values to path-keyed nodes" rather than
    "exempt this field's edges from the membership check" — see
    knowledge_file_nodes.py below. ``exempt_edge_types`` is always empty.
    Surface discovery driven by paths.json; no surface path, edge_fields
    list, or file-path field name is hardcoded anywhere in this module
    (KM-KGS-100c-2) — adding a new surface only requires a new entry in
    paths.json. All file I/O wrapped in try/except with specific exception
    types (repo error-handling policy). Stdlib-only: no third-party
    dependencies.
    The ten frontmatter/YAML reader functions (_find_frontmatter_end,
    _strip_matched_quotes, _split_flow_sequence_items, _parse_scalar_value,
    _line_indent, _strip_inline_comment, _is_mapping_item_text,
    _parse_block_children, _parse_frontmatter, _parse_yaml_file) live in the
    sibling module knowledge_frontmatter_reader.py (KM-KGS-100a-3-xi) and are
    re-exported here as the SAME function objects via _load_reader_module(),
    which resolves the sibling module relative to this file's own __file__
    so the re-export holds both from source scripts/ and a deployed
    consumer's .leafcutter/scripts/. A second sibling module,
    knowledge_file_nodes.py (KM-KGS-100d-4), is loaded the same way
    (_load_file_nodes_module()) and owns canonicalisation, the path-keyed
    index, present/missing marking, and decline reporting for every field a
    surface declares in file_path_fields; ``_collect_all_ex()`` (the
    3-tuple-returning core _collect_all() now delegates to) routes each such
    field's candidate values to it in the same post-processing step that
    creates synthetic component-hub nodes, before the membership filter runs.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import sys
from collections.abc import Generator
from pathlib import Path
from typing import Any, NamedTuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class NodeRecord(NamedTuple):
    """A single node in the knowledge graph.

    Attributes:
        id: Unique identifier for the node (slug or filename stem; a
            repo-relative POSIX path for a 'files'-surface node).
        surface: The surface this node belongs to (e.g. 'agents', 'tickets',
            'files' for a path-keyed synthetic node, KM-KGS-100d-4).
        title: Human-readable display name.
        description: One-line summary extracted from frontmatter or body.
        path: Absolute or relative Path to the source file or registry.
        missing: True when a 'files'-surface node's canonical path does not
            exist under the project root (KM-KGS-100d-4-ii). Defaults to
            False and is only meaningful on the 'files' surface; a consumer
            reading map data produced before this field existed must treat
            an unmarked node as present.
    """

    id: str
    surface: str
    title: str
    description: str
    path: Path
    missing: bool = False


class EdgeRecord(NamedTuple):
    """A directed edge between two nodes in the knowledge graph.

    Attributes:
        source_id: Node id of the source.
        target_id: Node id of the target.
        edge_type: Semantic label for the edge (e.g. 'spawn_allowlist',
            'depends_on', 'files_touched').
        anchor: The '#symbol' or '::test' suffix stripped from a file-path
            value during canonicalisation (KM-KGS-100d-4), or None when the
            value carried none or the edge is not a file-path edge.
    """

    source_id: str
    target_id: str
    edge_type: str
    anchor: str | None = None


# ---------------------------------------------------------------------------
# Surface-specific edge fields
# ---------------------------------------------------------------------------

# NOTE: _SURFACE_EDGE_FIELDS is kept only as a legacy fallback for callers
# that invoke extract_edges() without passing edge_fields explicitly.
# The authoritative source of edge_fields is the ``edge_fields`` array in each
# surface entry of paths.json (loaded by load_surfaces_with_meta).
# Do NOT add new surfaces here — declare them in paths.json instead.
_SURFACE_EDGE_FIELDS: dict[str, list[str]] = {
    "agents": ["spawn_allowlist", "spawned_by", "skills_used", "components"],
    "skills": ["dependencies", "components"],
    "tickets": ["depends_on", "files_touched", "components"],
    "docs": ["related_docs", "components"],
    "adrs": ["related_docs", "components"],
    "components": ["related_docs", "components"],
    "roadmap": ["components"],
    "glossary": [],
}

# Fields that use "component_membership" edge type (targeting component hub nodes)
_COMPONENT_FIELDS: frozenset[str] = frozenset({"components"})

# Fields whose values may be file paths that need stem resolution
_PATH_FIELDS: frozenset[str] = frozenset({"depends_on"})

# Canonical outbound edge types produced by the ``acs`` surface.
#
# When a reader collects the outbound edges of an AC node (e.g. KM-EX-010),
# ONLY these four edge-type labels may appear — no other relationship kind is
# produced.  This is enforced by the ``edge_fields`` list in the ``acs``
# surface entry of paths.json, which is the single configuration point that
# controls which YAML fields are traversed.  The mapping from raw field name
# to edge-type label is:
#
#   implemented_by  → "implemented_by"   (source files that deliver the AC)
#   covered_by      → "covered_by"       (test files that prove the AC)
#   depends_on      → "depends_on"       (other criteria this AC depends on)
#   components      → "component_membership"  (component hub the AC belongs to)
#
# If future AC YAML schemas add new relationship fields, they MUST also be
# added to this constant so that callers (including downstream tools such as
# the graph visualiser and how-to queries) have a single, authoritative
# definition to validate against.
_AC_EDGE_TYPES: frozenset[str] = frozenset(
    {"implemented_by", "covered_by", "depends_on", "component_membership"}
)

# NOTE (KM-KGS-100d-2, amended 2026-09-25): there is no longer a phantom
# -filter exemption set here. A field a surface declares in its own
# file_path_fields (e.g. acs' implemented_by/covered_by, tickets'
# files_touched) now resolves through knowledge_file_nodes.py to a real,
# path-keyed node instead of being exempted from the membership check --
# see KM-KGS-100d-4 and this module's ARCHITECTURE docstring.

# ---------------------------------------------------------------------------
# Frontmatter parser — re-exported from the sibling knowledge_frontmatter_reader
# module (KM-KGS-100a-3-xi). Loaded via spec_from_file_location, resolved
# relative to THIS file's own __file__ (never sys.path, never a hard-coded
# absolute path), so the re-export holds both when knowledge_query is
# imported normally with scripts/ on sys.path AND when it is loaded via
# importlib.util.spec_from_file_location with no scripts/ directory on
# sys.path at all — the way scripts/visualise_knowledge_graph.py loads
# knowledge_query itself. The loaded module is registered in sys.modules
# under its own name so the ten functions' __module__ resolves to a real,
# reachable module object rather than an orphan. The names below are the
# SAME function objects as the reader module's own attributes (identity,
# not a copy) — every existing caller in this file keeps using the bare
# names unchanged.
# ---------------------------------------------------------------------------

def _load_sibling_module(module_name: str):
    """Load a "<module_name>.py" sibling module by file path.

    Resolved relative to THIS file's own __file__ (never sys.path, never a
    hard-coded absolute path), so the load works both when knowledge_query
    is imported normally with scripts/ on sys.path AND when it is loaded via
    importlib.util.spec_from_file_location with no scripts/ directory on
    sys.path at all (the way scripts/visualise_knowledge_graph.py loads
    knowledge_query itself). Shared by the frontmatter/YAML reader module
    (KM-KGS-100a-3-xi) and the file-path resolution module (KM-KGS-100d-4).

    Args:
        module_name: Bare module name; the file is "<module_name>.py" next
            to this file.

    Returns:
        The loaded module, cached in ``sys.modules`` so repeated calls (and
        any other importer) share the same module object.

    Raises:
        FileNotFoundError: When "<module_name>.py" is not found next to
            this file.
    """
    cached = sys.modules.get(module_name)
    if cached is not None:
        return cached
    module_path = Path(__file__).resolve().parent / f"{module_name}.py"
    if not module_path.exists():
        raise FileNotFoundError(str(module_path))
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_reader = _load_sibling_module("knowledge_frontmatter_reader")
_find_frontmatter_end = _reader._find_frontmatter_end
_strip_matched_quotes = _reader._strip_matched_quotes
_split_flow_sequence_items = _reader._split_flow_sequence_items
_parse_scalar_value = _reader._parse_scalar_value
_line_indent = _reader._line_indent
_strip_inline_comment = _reader._strip_inline_comment
_is_mapping_item_text = _reader._is_mapping_item_text
_parse_block_children = _reader._parse_block_children
_parse_frontmatter = _reader._parse_frontmatter
_parse_yaml_file = _reader._parse_yaml_file

# KM-KGS-100d-4: canonicalisation, the path-keyed index, present/missing
# marking, and decline reporting for every file_path_fields-declared field.
_file_nodes = _load_sibling_module("knowledge_file_nodes")


def _extract_frontmatter_end_line(text: str) -> int:
    """Return line index (0-based) of the closing ``---`` delimiter, or 0.

    Args:
        text: Full text content of a file.

    Returns:
        Line index of the closing ``---`` or 0 when no frontmatter.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return 0
    idx = _find_frontmatter_end(lines)
    return idx if idx != -1 else 0


def _first_body_line(text: str) -> str:
    """Return the first non-blank, non-heading body line after the frontmatter.

    Args:
        text: Full text content of a file.

    Returns:
        First meaningful body line, or empty string when none found.
    """
    fm_end = _extract_frontmatter_end_line(text)
    lines = text.splitlines()
    for line in lines[fm_end + 1 :]:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    # Fallback: first heading if no non-heading body lines
    for line in lines[fm_end + 1 :]:
        stripped = line.strip()
        if stripped:
            return stripped.lstrip("#").strip()
    return ""


# ---------------------------------------------------------------------------
# Public API: load_surfaces
# ---------------------------------------------------------------------------


def load_surfaces(project_root: Path, paths_json: Path) -> dict[str, Path]:
    """Load surface paths from paths.json.

    Reads paths.json and resolves each surface's root path relative to
    project_root. Silently skips surfaces marked ``_optional: true`` when
    the path does not exist.

    Args:
        project_root: Absolute path to the project root directory.
        paths_json: Absolute path to the paths.json configuration file.

    Returns:
        Dict mapping surface name (str) to its resolved Path.

    Raises:
        SystemExit: With exit code 1 when paths.json is absent or invalid JSON.
    """
    meta = load_surfaces_with_meta(project_root, paths_json)
    return {name: info["path"] for name, info in meta.items()}


def load_surfaces_with_meta(
    project_root: Path, paths_json: Path
) -> dict[str, dict[str, Any]]:
    """Load surface paths and edge_fields from paths.json.

    Reads paths.json, resolves each surface's root path relative to
    project_root, and captures the ``edge_fields`` list from each surface
    entry. Silently skips surfaces marked ``_optional: true`` when the path
    does not exist.

    This is the preferred loader for code that needs both paths and edge
    metadata. ``load_surfaces`` delegates to this function and strips the
    extra metadata for backward compatibility.

    Args:
        project_root: Absolute path to the project root directory.
        paths_json: Absolute path to the paths.json configuration file.

    Returns:
        Dict mapping surface name (str) to ``{"path": Path, "edge_fields":
        list[str], "file_path_fields": list[str]}``.  The ``file_path_fields``
        entry lists edge fields whose values are file-path strings rather than
        node IDs; these are exempt from phantom-edge filtering in
        ``_collect_all``.

    Raises:
        SystemExit: With exit code 1 when paths.json is absent or invalid JSON.
    """
    if not paths_json.exists():
        print(
            f"ERROR: {paths_json.name} not found at {paths_json}.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        raw = paths_json.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: Cannot read {paths_json}: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"ERROR: {paths_json.name} is not valid JSON: {exc}", file=sys.stderr)
        sys.exit(1)

    surfaces_cfg = data.get("surfaces", {})
    result: dict[str, dict[str, Any]] = {}

    for name, cfg in surfaces_cfg.items():
        if not isinstance(cfg, dict):
            continue
        path_str = cfg.get("path", "")
        if not path_str:
            continue
        resolved = project_root / path_str
        optional = cfg.get("_optional", False)
        if not resolved.exists():
            if optional:
                continue
            # Non-optional but missing: include anyway; extract_nodes will handle
        edge_fields: list[str] = cfg.get("edge_fields", [])
        if not isinstance(edge_fields, list):
            edge_fields = []
        file_path_fields: list[str] = cfg.get("file_path_fields", [])
        if not isinstance(file_path_fields, list):
            file_path_fields = []
        result[name] = {
            "path": resolved,
            "edge_fields": edge_fields,
            "file_path_fields": file_path_fields,
        }

    return result


# ---------------------------------------------------------------------------
# Public API: build_knowledge_map
# ---------------------------------------------------------------------------


class KnowledgeMap(NamedTuple):
    """Result of a full-graph traversal against all declared surfaces.

    This is the primary return type for ``build_knowledge_map()``.  It carries
    both the graph data and audit metadata so callers can assert completeness
    without re-reading paths.json.

    Attributes:
        nodes: All NodeRecords collected across every contributing surface.
        edges: All filtered EdgeRecords (phantom edges removed).
        declared_surfaces: The set of surface names that were declared in
            paths.json **and** whose path exists on disk (optional absent
            surfaces are excluded from this set, matching the behaviour of
            ``load_surfaces_with_meta``).
        contributing_surfaces: The subset of ``declared_surfaces`` that
            produced at least one NodeRecord.  For a well-formed project
            every element of ``declared_surfaces`` should appear here.
        declined_count: Number of relationship values declined as not a
            repo path (KM-KGS-100d-4-iii) -- neither an on-map id nor a
            resolvable file path. Zero included, never omitted.
    """

    nodes: list[NodeRecord]
    edges: list[EdgeRecord]
    declared_surfaces: frozenset[str]
    contributing_surfaces: frozenset[str]
    declined_count: int = 0


def build_knowledge_map(
    project_root: Path,
    paths_json: Path,
    surface_filter: str | None = None,
) -> KnowledgeMap:
    """Build the full knowledge map and return graph data plus surface audit metadata.

    Traverses every surface declared in paths.json (skipping optional absent
    surfaces), collects all NodeRecords and EdgeRecords, applies phantom-edge
    filtering, and returns a :class:`KnowledgeMap` that includes both the graph
    data and the ``declared_surfaces`` / ``contributing_surfaces`` audit sets.

    The caller can assert completeness without knowing which surfaces are
    declared by testing::

        assert km.contributing_surfaces == km.declared_surfaces

    This assertion is expressed against the *declared set itself*, not against
    any hardcoded surface name list.  If a surface is declared but its path
    produces zero nodes (e.g. the directory is empty), it will appear in
    ``declared_surfaces`` but not in ``contributing_surfaces``.

    Args:
        project_root: Absolute path to the project root directory.
        paths_json: Absolute path to the paths.json configuration file.
        surface_filter: When non-None, restrict traversal to this surface only.

    Returns:
        A :class:`KnowledgeMap` with nodes, edges, declared_surfaces, and
        contributing_surfaces.

    Raises:
        SystemExit: With exit code 1 when paths.json is absent or invalid JSON.
    """
    surfaces_meta = load_surfaces_with_meta(project_root, paths_json)
    declared = {
        name for name in surfaces_meta if not surface_filter or name == surface_filter
    }

    all_nodes, all_edges, declines = _collect_all_ex(project_root, paths_json, surface_filter)

    # A surface contributed a primary node only if it appears in the
    # declared set (excludes synthetic hub/files nodes, whose surface names
    # -- "components"/"files" -- are never themselves declared surfaces).
    contributing = {node.surface for node in all_nodes if node.surface in declared}

    return KnowledgeMap(
        nodes=all_nodes,
        edges=all_edges,
        declared_surfaces=frozenset(declared),
        contributing_surfaces=frozenset(contributing),
        declined_count=len(declines),
    )


# ---------------------------------------------------------------------------
# Public API: validate_knowledge_map
# ---------------------------------------------------------------------------


class SurfaceValidationResult(NamedTuple):
    """Validation result for a single declared surface.

    Attributes:
        surface: The name of the surface (e.g. 'agents', 'tickets').
        declared_edge_fields: The relationship kinds declared in paths.json for
            this surface.  An empty list means the surface claims to contribute
            no edges.
        unexpected_edge_types: Edge types found in the graph for nodes from
            this surface that are NOT in ``declared_edge_fields``.  An empty
            set means the surface is valid.
        valid: ``True`` when ``unexpected_edge_types`` is empty (the surface
            produced only the relationship kinds it declared, or declared none
            and produced none).
    """

    surface: str
    declared_edge_fields: list[str]
    unexpected_edge_types: frozenset[str]
    valid: bool


def validate_knowledge_map(
    knowledge_map: KnowledgeMap,
    project_root: Path,
    paths_json: Path,
) -> list[SurfaceValidationResult]:
    """Validate each declared surface against the edge_fields it promises.

    For every surface declared in paths.json (and present in
    ``knowledge_map.declared_surfaces``), this function:

    1. Reads the ``edge_fields`` the surface declared in paths.json.
    2. Collects all edge types emitted by nodes belonging to that surface in
       the knowledge map.
    3. Computes the unexpected edge types (emitted but not declared).
    4. Returns a :class:`SurfaceValidationResult` per surface.

    A surface that declares an empty ``edge_fields`` list is treated as
    promising no edges.  If such a surface produces zero edges (or only
    phantom-filter-exempt edges) it is valid.

    The iteration is fully data-driven: the function reads the declared
    surfaces from paths.json at call time, so adding or removing a surface
    in paths.json automatically changes the set of surfaces validated without
    any edit to this function.

    Args:
        knowledge_map: A :class:`KnowledgeMap` produced by
            ``build_knowledge_map()``.
        project_root: Absolute path to the project root directory (used to
            locate paths.json).
        paths_json: Absolute path to the paths.json configuration file.

    Returns:
        A list of :class:`SurfaceValidationResult`, one per surface in
        ``knowledge_map.declared_surfaces``.  The list is sorted by surface
        name for stable ordering.
    """
    surfaces_meta = load_surfaces_with_meta(project_root, paths_json)

    # Index edges by source-node surface for efficient lookup.
    # Build a mapping: surface_name -> set of edge_types produced by that surface.
    node_surface: dict[str, str] = {n.id: n.surface for n in knowledge_map.nodes}
    edges_by_surface: dict[str, set[str]] = {}
    for edge in knowledge_map.edges:
        surface_name = node_surface.get(edge.source_id)
        if surface_name is None:
            continue
        edges_by_surface.setdefault(surface_name, set()).add(edge.edge_type)

    results: list[SurfaceValidationResult] = []

    for surface_name in sorted(knowledge_map.declared_surfaces):
        surface_info = surfaces_meta.get(surface_name, {})
        declared_edge_fields: list[str] = surface_info.get("edge_fields", [])

        # Allowed edge types: the declared edge_fields plus any remapped names.
        # The 'components' field is remapped to 'component_membership' in extract_edges,
        # so 'components' in declared_edge_fields implicitly allows 'component_membership'.
        allowed_types: set[str] = set(declared_edge_fields)
        if "components" in allowed_types:
            allowed_types.add("component_membership")

        actual_types: set[str] = edges_by_surface.get(surface_name, set())
        unexpected: frozenset[str] = frozenset(actual_types - allowed_types)

        results.append(
            SurfaceValidationResult(
                surface=surface_name,
                declared_edge_fields=declared_edge_fields,
                unexpected_edge_types=unexpected,
                valid=len(unexpected) == 0,
            )
        )

    return results


# ---------------------------------------------------------------------------
# Public API: validate_edges_integrity
# ---------------------------------------------------------------------------


class EdgeIntegrityResult(NamedTuple):
    """Result of edge integrity validation for a knowledge map.

    Edges whose target_id is absent from the node set are **silently dropped**
    (see ``dropped_edges``) rather than flagged as integrity failures.  Only
    edges whose source_id is absent are treated as true integrity violations and
    appear in ``invalid_edges``.  This satisfies AC KM-KGS-100d-2-i: a
    relationship naming a missing target is dropped, not rendered as a dead end,
    and does not cause the build to fail.

    Attributes:
        valid: ``True`` when every non-exempt, non-dropped edge has its
            source_id present in the full node set.  A missing target alone
            does not set this to ``False`` — those edges are dropped instead.
        invalid_edges: List of ``(EdgeRecord, reason)`` tuples for every edge
            whose *source* node is absent from the node set.  Empty when
            ``valid`` is ``True``.
        dropped_edges: List of ``EdgeRecord`` instances that were silently
            dropped because their target_id was absent from the node set.
            Callers may inspect this field for diagnostic purposes.  The build
            must not fail solely because this list is non-empty.
        validated_edges: The subset of the input edges that survived validation
            — i.e. edges in the original map minus those in ``dropped_edges``
            and minus those in ``invalid_edges``.
        node_ids: The full node-ID set derived from
            ``knowledge_map.nodes`` and used for the validation.
        exempt_edge_types: Always empty (KM-KGS-100d-2, amended 2026-09-25).
            A field a surface declares in file_path_fields now resolves to a
            real, path-keyed node (KM-KGS-100d-4) instead of being exempted
            from this check, so no edge type is ever exempt.
    """

    valid: bool
    invalid_edges: list
    dropped_edges: list
    validated_edges: list
    node_ids: frozenset
    exempt_edge_types: frozenset


def validate_edges_integrity(
    knowledge_map: KnowledgeMap,
    project_root: Path,
    paths_json: Path,
) -> "EdgeIntegrityResult":
    """Validate edges, dropping those whose target node is absent from the map.

    For every edge in ``knowledge_map.edges`` this function checks that both
    ``source_id`` and ``target_id`` are present in the set of node IDs derived
    from ``knowledge_map.nodes``, with the following two-tier policy:

    * **Missing target** (AC KM-KGS-100d-2-i): an edge whose ``target_id``
      is not in the node set is **dropped silently** — logged at DEBUG level
      and recorded in ``result.dropped_edges``, but NOT added to
      ``invalid_edges`` and does NOT cause ``valid`` to be ``False``.  The
      build must not fail solely because a relationship named a missing target.
    * **Missing source**: an edge whose ``source_id`` is not in the node set
      is treated as a true integrity violation — it IS added to
      ``invalid_edges`` and causes ``valid`` to be ``False``.

    There is no edge-type exemption (KM-KGS-100d-2, amended 2026-09-25): a
    field declared in a surface's file_path_fields now resolves its values
    to real, path-keyed nodes (KM-KGS-100d-4) instead of being exempted from
    this membership check, so ``exempt_edge_types`` is always empty and every
    edge of every type is checked against the SAME full node-ID set — no
    hand-maintained allow-list of target ids.

    This function works for edges contributed by any declared surface,
    including the ``acs`` surface, because it operates on the assembled
    ``KnowledgeMap`` alone.

    Args:
        knowledge_map: A :class:`KnowledgeMap` produced by
            ``build_knowledge_map()``.
        project_root: Absolute path to the project root directory. Accepted
            for interface parity with existing callers; not consulted (no
            exempt set is computed).
        paths_json: Absolute path to the paths.json configuration file.
            Accepted for interface parity; not consulted.

    Returns:
        An :class:`EdgeIntegrityResult` whose ``valid`` field is ``True`` when
        no edge has a missing source node.  Edges with missing target nodes
        are dropped (see ``dropped_edges``) rather than causing ``valid`` to
        be ``False``.  ``validated_edges`` contains the surviving edge set
        after drops are applied.
    """
    node_ids: frozenset[str] = frozenset(n.id for n in knowledge_map.nodes)

    # Classify each edge using the two-tier policy, uniformly for every edge
    # type (no exemption):
    #   - missing source: true integrity violation → invalid_edges.
    #   - missing target: silently drop → dropped_edges (AC KM-KGS-100d-2-i).
    #   - both present: survives → validated_edges.
    invalid_edges: list[tuple[EdgeRecord, str]] = []
    dropped_edges: list[EdgeRecord] = []
    validated_edges: list[EdgeRecord] = []

    for edge in knowledge_map.edges:
        if edge.source_id not in node_ids:
            invalid_edges.append(
                (edge, f"source_id '{edge.source_id}' not in node set")
            )
        elif edge.target_id not in node_ids:
            # AC KM-KGS-100d-2-i: drop the edge; do NOT set valid=False.
            # Log at DEBUG so the information is observable without being
            # noisy in normal operation.  The build must not fail solely
            # because a relationship named a missing target.
            logger.debug(
                "Edge dropped: %s -[%s]-> %s — target node '%s' not in map",
                edge.source_id,
                edge.edge_type,
                edge.target_id,
                edge.target_id,
            )
            dropped_edges.append(edge)
        else:
            validated_edges.append(edge)

    return EdgeIntegrityResult(
        valid=len(invalid_edges) == 0,
        invalid_edges=invalid_edges,
        dropped_edges=dropped_edges,
        validated_edges=validated_edges,
        node_ids=node_ids,
        exempt_edge_types=frozenset(),
    )


# ---------------------------------------------------------------------------
# Public API: extract_nodes
# ---------------------------------------------------------------------------


def extract_nodes(surface: str, path: Path) -> Generator[NodeRecord, None, None]:
    """Yield NodeRecords from a surface path.

    Behaviour depends on the surface type:
    - JSON registry files (agents, skills): read ``agents`` or ``skills`` array.
    - Markdown directories (tickets, docs, adrs, components): glob ``**/*.md``.
    - JSON files (roadmap): yield one node per phase.
    - Single markdown files (glossary): yield one node for the file.

    For markdown files, description is taken from frontmatter ``description:``
    field; falls back to the first non-blank, non-heading body line.

    Args:
        surface: Surface name (e.g. 'agents', 'tickets', 'docs').
        path: Resolved Path to the surface root (file or directory).

    Yields:
        NodeRecord for each discovered knowledge node.
    """
    if not path.exists():
        return

    if path.is_file() and path.suffix == ".json":
        yield from _extract_nodes_from_json(surface, path)
    elif path.is_file() and path.suffix == ".md":
        yield from _extract_nodes_from_md_file(surface, path)
    elif path.is_dir():
        yield from _extract_nodes_from_dir(surface, path)


def _extract_nodes_from_json(surface: str, path: Path) -> Generator[NodeRecord, None, None]:
    """Yield nodes from a JSON registry file.

    Args:
        surface: Surface name.
        path: Path to the JSON file.

    Yields:
        NodeRecord for each entry in the registry.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return

    # Support: {"agents": [...]} or {"skills": [...]} or {"phases": [...]}
    # Prefer matching the surface name as the array key
    entries: list[Any] = []
    if isinstance(data, list):
        entries = data
    elif isinstance(data, dict):
        # Try surface name first, then common keys
        for key in (surface, "agents", "skills", "phases", "items"):
            if key in data and isinstance(data[key], list):
                entries = data[key]
                break
        if not entries:
            # Fall back to the first list value found
            for v in data.values():
                if isinstance(v, list):
                    entries = v
                    break

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        node_id = str(entry.get("id") or entry.get("name") or "")
        if not node_id:
            continue
        title = str(entry.get("name") or entry.get("title") or node_id)
        description = str(entry.get("description") or "")
        yield NodeRecord(
            id=node_id,
            surface=surface,
            title=title,
            description=description,
            path=path,
        )


def _extract_nodes_from_md_file(surface: str, path: Path) -> Generator[NodeRecord, None, None]:
    """Yield a single node from a standalone markdown file.

    Args:
        surface: Surface name.
        path: Path to the markdown file.

    Yields:
        NodeRecord for the file.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return

    fm = _parse_frontmatter(text)
    node_id = fm.get("id") or path.stem
    title = str(fm.get("title") or path.stem)
    description = str(
        fm.get("description") or _first_body_line(text) or ""
    )
    yield NodeRecord(
        id=str(node_id),
        surface=surface,
        title=title,
        description=description,
        path=path,
    )


def _extract_nodes_from_dir(surface: str, path: Path) -> Generator[NodeRecord, None, None]:
    """Yield nodes from all markdown and YAML files in a directory tree.

    Skips ``Master_Plan.md``, ``README.md``, and ``index.yaml``.
    For ``.md`` files, description falls back to the first non-blank body line.
    For ``.yaml`` files, description falls back to empty string (no body text).

    Args:
        surface: Surface name.
        path: Path to the directory.

    Yields:
        NodeRecord for each markdown or YAML file found.
    """
    _SKIP_MD = {"Master_Plan.md", "README.md"}
    _SKIP_YAML = {"index.yaml"}

    try:
        md_files = sorted(path.glob("**/*.md"))
    except OSError:
        return

    for md_file in md_files:
        if md_file.name in _SKIP_MD:
            continue
        try:
            text = md_file.read_text(encoding="utf-8")
        except OSError:
            continue
        fm = _parse_frontmatter(text)
        node_id = str(fm.get("id") or md_file.stem)
        title = str(fm.get("title") or md_file.stem)
        description = str(
            fm.get("description") or _first_body_line(text) or ""
        )
        yield NodeRecord(
            id=node_id,
            surface=surface,
            title=title,
            description=description,
            path=md_file,
        )

    try:
        yaml_files = sorted(path.glob("**/*.yaml"))
    except OSError:
        return

    for yaml_file in yaml_files:
        if yaml_file.name in _SKIP_YAML:
            continue
        try:
            text = yaml_file.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("Skipping unreadable YAML file %s: %s", yaml_file, exc)
            continue
        fields = _parse_yaml_file(text)
        raw_id = fields.get("id")
        if not raw_id:
            logger.warning(
                "Skipping YAML file %s: no 'id' field found (file may be non-criterion or unparseable)",
                yaml_file,
            )
            continue
        node_id = str(raw_id)
        title = str(fields.get("title") or yaml_file.stem)
        description = str(fields.get("description") or "")
        yield NodeRecord(
            id=node_id,
            surface=surface,
            title=title,
            description=description,
            path=yaml_file,
        )


# ---------------------------------------------------------------------------
# Public API: extract_edges
# ---------------------------------------------------------------------------


def _resolve_depends_on_target(value: str) -> str:
    """Resolve a depends_on value to a node ID (filename stem).

    If the value contains '/' or ends with '.md', it is treated as a file path
    and reduced to its filename stem. Otherwise it is returned unchanged.

    Args:
        value: Raw depends_on value from frontmatter.

    Returns:
        Node ID string (filename stem or unchanged bare ID).
    """
    if "/" in value or value.endswith(".md"):
        return Path(value).stem
    return value


def extract_edges(
    surface: str,
    record: NodeRecord,
    raw_data: dict[str, Any],
    edge_fields: list[str] | None = None,
) -> Generator[EdgeRecord, None, None]:
    """Yield EdgeRecords from a node's raw data.

    Reads the edge fields configured for the surface and produces one edge per
    value in each field. String values become single edges; list values produce
    one edge per element.

    For fields in ``_COMPONENT_FIELDS`` (i.e. ``components``), the edge type is
    set to ``component_membership`` instead of the field name.

    For fields in ``_PATH_FIELDS`` (i.e. ``depends_on``), path values are
    resolved to filename stems before being used as target IDs.

    Args:
        surface: Surface name (e.g. 'agents', 'tickets').
        record: The source NodeRecord.
        raw_data: Dict of raw data for the node (e.g. a registry entry or
            frontmatter dict). May contain edge fields as strings or lists.
        edge_fields: Explicit list of field names to treat as edges. When
            ``None``, falls back to the legacy ``_SURFACE_EDGE_FIELDS`` lookup
            keyed by ``surface``. Callers that load surface metadata from
            paths.json (via ``load_surfaces_with_meta``) should pass the
            ``edge_fields`` value from that metadata so that no new surface
            requires a corresponding change in this module.

    Yields:
        EdgeRecord for each outbound edge.
    """
    if edge_fields is None:
        edge_fields = _SURFACE_EDGE_FIELDS.get(surface, [])
    for field in edge_fields:
        value = raw_data.get(field)
        if value is None:
            continue
        # Determine edge type: components field uses "component_membership"
        edge_type = "component_membership" if field in _COMPONENT_FIELDS else field
        if isinstance(value, str):
            if value:
                target = _resolve_depends_on_target(value) if field in _PATH_FIELDS else value
                yield EdgeRecord(
                    source_id=record.id,
                    target_id=target,
                    edge_type=edge_type,
                )
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item:
                    target = _resolve_depends_on_target(item) if field in _PATH_FIELDS else item
                    yield EdgeRecord(
                        source_id=record.id,
                        target_id=target,
                        edge_type=edge_type,
                    )


# ---------------------------------------------------------------------------
# Internal helpers for full-graph traversal
# ---------------------------------------------------------------------------


def _route_edges(edges, surface_name, node, surface_info, all_edges, pending) -> None:
    """Route each candidate edge to ``all_edges`` or to ``pending``.

    A candidate whose ``edge_type`` is one the SOURCE surface declared in
    its own ``file_path_fields`` is a file-path candidate (KM-KGS-100d-4):
    it is deferred to ``pending`` for canonicalisation and path-index
    resolution once every surface's primary nodes are known, rather than
    kept as a raw-string leaf. Every other candidate is an ordinary
    node-to-node edge and is appended unchanged, exactly as before.

    Args:
        edges: Candidate EdgeRecords from one node's raw data.
        surface_name: The surface these candidates were produced from.
        node: The source NodeRecord.
        surface_info: This surface's ``load_surfaces_with_meta`` entry.
        all_edges: Mutable list of ordinary edges (appended to in place).
        pending: Mutable list of ``(surface, node, field, raw_value)``
            file-path candidates (appended to in place).
    """
    file_fields = surface_info.get("file_path_fields", [])
    for edge in edges:
        if edge.edge_type in file_fields:
            pending.append((surface_name, node, edge.edge_type, edge.target_id))
        else:
            all_edges.append(edge)


def _extract_json_registry_edges(surface_name, node, surface_path, surface_edge_fields, surface_info, all_edges, pending) -> None:
    """Extract and route candidate edges for one node of a JSON-registry surface.

    Split out of ``_collect_all_ex`` purely to keep that function's own
    cyclomatic complexity down; behaviour is unchanged.

    Args:
        surface_name: The surface this node belongs to.
        node: The NodeRecord to extract edges for.
        surface_path: The surface's resolved JSON registry path.
        surface_edge_fields: This surface's declared edge_fields.
        surface_info: This surface's ``load_surfaces_with_meta`` entry.
        all_edges: Mutable list of ordinary edges (appended to in place).
        pending: Mutable list of file-path candidates (appended to in place).
    """
    try:
        data = json.loads(surface_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    entries: list[Any] = []
    if isinstance(data, list):
        entries = data
    elif isinstance(data, dict):
        for key in (surface_name, "agents", "skills", "phases", "items"):
            if key in data and isinstance(data[key], list):
                entries = data[key]
                break
        if not entries:
            for v in data.values():
                if isinstance(v, list):
                    entries = v
                    break
    for entry in entries:
        if isinstance(entry, dict) and str(entry.get("id") or entry.get("name") or "") == node.id:
            _route_edges(extract_edges(surface_name, node, entry, surface_edge_fields), surface_name, node, surface_info, all_edges, pending)


def _extract_dir_edges(surface_name, node, surface_edge_fields, surface_info, all_edges, pending) -> None:
    """Extract and route candidate edges for one node of a directory surface.

    Split out of ``_collect_all_ex`` purely to keep that function's own
    cyclomatic complexity down; behaviour is unchanged. Handles both a
    markdown node (frontmatter) and a YAML node (e.g. the acs surface).

    Args:
        surface_name: The surface this node belongs to.
        node: The NodeRecord to extract edges for.
        surface_edge_fields: This surface's declared edge_fields.
        surface_info: This surface's ``load_surfaces_with_meta`` entry.
        all_edges: Mutable list of ordinary edges (appended to in place).
        pending: Mutable list of file-path candidates (appended to in place).
    """
    if node.path.is_file() and node.path.suffix == ".md":
        try:
            text = node.path.read_text(encoding="utf-8")
        except OSError:
            return
        fm = _parse_frontmatter(text)
        _route_edges(extract_edges(surface_name, node, fm, surface_edge_fields), surface_name, node, surface_info, all_edges, pending)
    elif node.path.is_file() and node.path.suffix == ".yaml":
        try:
            text = node.path.read_text(encoding="utf-8")
        except OSError:
            return
        fields = _parse_yaml_file(text)
        _route_edges(extract_edges(surface_name, node, fields, surface_edge_fields), surface_name, node, surface_info, all_edges, pending)


def _create_component_hub_nodes(all_edges, existing_ids: set[str]) -> list[NodeRecord]:
    """Create one synthetic ``components``-surface hub node per new target.

    Args:
        all_edges: Every candidate edge collected so far.
        existing_ids: Mutable set of node ids seen so far; a newly created
            hub's id is added to it in place.

    Returns:
        The newly created hub NodeRecords (empty when every
        component_membership target already exists as a node).
    """
    seen_component_targets = {e.target_id for e in all_edges if e.edge_type == "component_membership"}
    hub_nodes: list[NodeRecord] = []
    for component_name in sorted(seen_component_targets):
        if component_name not in existing_ids:
            hub_title = component_name.replace("-", " ").replace("_", " ").title()
            hub_nodes.append(NodeRecord(
                id=component_name, surface="components", title=hub_title,
                description=f"Component hub: {component_name}", path=Path("docs/architecture/components/"),
            ))
            existing_ids.add(component_name)
    return hub_nodes


def _filter_dangling_edges(all_edges, node_ids: set[str]) -> list[EdgeRecord]:
    """Keep only edges whose source and target both exist in ``node_ids``.

    No edge-type exemption (KM-KGS-100d-2, amended): every file-path edge
    was already resolved to a real node (or declined and never added)
    before this runs. Per AC KM-KGS-100d-2-i, a relationship whose target
    is absent is dropped (not rendered as a dead end) and logged at DEBUG
    level so the drop is observable without causing a build failure.

    Args:
        all_edges: Every edge collected so far (ordinary plus resolved).
        node_ids: The full node-id set (primary, hub, and files nodes).

    Returns:
        The surviving edges.
    """
    filtered_edges: list[EdgeRecord] = []
    for e in all_edges:
        if e.source_id not in node_ids:
            logger.debug("Edge dropped (missing source): %s -[%s]-> %s", e.source_id, e.edge_type, e.target_id)
            continue
        if e.target_id not in node_ids:
            logger.debug("Edge dropped (missing target): %s -[%s]-> %s", e.source_id, e.edge_type, e.target_id)
            continue
        filtered_edges.append(e)
    return filtered_edges


def _collect_all_ex(project_root: Path, paths_json: Path, surface_filter: str | None = None) -> tuple[list[NodeRecord], list[EdgeRecord], list]:
    """Traverse all surfaces and collect nodes, edges, and declines.

    After collecting all primary nodes and candidate edges, this function:
    1. Creates synthetic hub NodeRecords for each unique component value seen in
       component_membership edges that doesn't already exist as a node. These
       hubs have surface="components".
    2. Resolves every file-path candidate (deferred by ``_route_edges`` from a
       field the source surface declared in its own ``file_path_fields``)
       via ``knowledge_file_nodes.resolve_file_path_edges`` — canonicalised,
       looked up in the path-keyed index, and landed on an existing node, a
       new/reused ``files``-surface node, or declined (KM-KGS-100d-4 and
       its -i/-ii/-iii/-iv children). This is the SAME post-processing step
       that creates the component hubs, before the membership filter runs.
    3. Filters edges to keep only those where both source_id and target_id
       exist in the full node set (including synthetic hubs and files
       nodes). There is no edge-type exemption (KM-KGS-100d-2, amended).

    Args:
        project_root: Absolute path to the project root.
        paths_json: Path to paths.json.
        surface_filter: When non-None, restrict traversal to this surface only.

    Returns:
        Tuple of (nodes_list, edges_list, declines_list).
    """
    surfaces_meta = load_surfaces_with_meta(project_root, paths_json)
    all_nodes: list[NodeRecord] = []
    all_edges: list[EdgeRecord] = []
    pending: list = []

    for surface_name, surface_info in surfaces_meta.items():
        surface_path: Path = surface_info["path"]
        surface_edge_fields: list[str] = surface_info["edge_fields"]
        if surface_filter and surface_name != surface_filter:
            continue
        # Collect nodes
        for node in extract_nodes(surface_name, surface_path):
            all_nodes.append(node)
            # Best-effort: extract edges from JSON-registry surfaces
            if surface_path.is_file() and surface_path.suffix == ".json":
                _extract_json_registry_edges(surface_name, node, surface_path, surface_edge_fields, surface_info, all_edges, pending)
            elif surface_path.is_dir() or (surface_path.is_file() and surface_path.suffix == ".md"):
                _extract_dir_edges(surface_name, node, surface_edge_fields, surface_info, all_edges, pending)

    # Post-processing step 1: create synthetic hub nodes for component values
    # that appear as targets in component_membership edges but don't exist yet.
    primary_nodes = list(all_nodes)
    existing_ids = {n.id for n in all_nodes}
    hub_nodes = _create_component_hub_nodes(all_edges, existing_ids)
    all_nodes.extend(hub_nodes)

    # Post-processing step 2 (KM-KGS-100d-4): resolve every deferred
    # file-path candidate to a real node -- an existing node found
    # unambiguously via the path-keyed index, a new/reused files-surface
    # node, or a decline. Runs in the SAME post-processing step as hub
    # creation, before the membership filter, so a resolved edge survives
    # because its target is a node, never via an exemption.
    new_files_nodes, resolved_edges, declines = _file_nodes.resolve_file_path_edges(
        project_root=project_root, pending=pending, primary_nodes=primary_nodes,
        hub_nodes=hub_nodes, node_record_cls=NodeRecord, edge_record_cls=EdgeRecord,
    )
    all_nodes.extend(new_files_nodes)
    all_edges.extend(resolved_edges)
    existing_ids.update(n.id for n in new_files_nodes)

    # Post-processing step 3: filter phantom edges -- see _filter_dangling_edges.
    filtered_edges = _filter_dangling_edges(all_edges, existing_ids)

    return all_nodes, filtered_edges, declines


def _collect_all(project_root: Path, paths_json: Path, surface_filter: str | None = None) -> tuple[list[NodeRecord], list[EdgeRecord]]:
    """Backward-compatible 2-tuple wrapper around ``_collect_all_ex``.

    Existing callers (the visualiser, direct test calls) that only need
    nodes and edges keep working unchanged; ``build_knowledge_map()`` and
    the CLI call ``_collect_all_ex`` directly for the declines list too.

    Args:
        project_root: Absolute path to the project root.
        paths_json: Path to paths.json.
        surface_filter: When non-None, restrict traversal to this surface only.

    Returns:
        Tuple of (nodes_list, edges_list).
    """
    nodes, edges, _declines = _collect_all_ex(project_root, paths_json, surface_filter)
    return nodes, edges


# ---------------------------------------------------------------------------
# Output rendering
# ---------------------------------------------------------------------------


def _files_and_missing_counts(nodes: list[NodeRecord]) -> tuple[int, int]:
    """Return (files-surface node count, of-those marked missing) (KM-KGS-100d-4-ii).

    Shared by ``render_text`` and ``render_json`` so both renderers report
    the identical pair from one place.

    Args:
        nodes: The full (unfiltered) node set for the build.

    Returns:
        ``(files_nodes, missing_files)``, zero included.
    """
    files_nodes = [n for n in nodes if n.surface == "files"]
    return len(files_nodes), sum(1 for n in files_nodes if n.missing)


def render_text(
    nodes: list[NodeRecord],
    edges: list[EdgeRecord],
    query: str | None,
    show_edges: bool,
    declined: int = 0,
) -> str:
    """Render the knowledge index as human-readable text.

    Args:
        nodes: List of NodeRecords to include.
        edges: List of EdgeRecords to include.
        query: Optional keyword filter (case-insensitive).
        show_edges: When True, append the full edge list section.
        declined: Number of relationship values declined as not a repo path
            (KM-KGS-100d-4-iii). Zero included, never omitted.

    Returns:
        Multi-line formatted string.
    """
    # Files/Missing are whole-build figures (KM-KGS-100d-4-ii), computed
    # from the unfiltered node set so a --query keyword never changes them.
    files_count, missing_count = _files_and_missing_counts(nodes)

    if query:
        q_lower = query.lower()
        nodes = [
            n
            for n in nodes
            if q_lower in (n.title or "").lower()
            or q_lower in (n.description or "").lower()
        ]

    # Build edge lookup for nodes that passed the filter
    node_ids = {n.id for n in nodes}
    filtered_edges = [e for e in edges if e.source_id in node_ids]

    # Group by surface
    by_surface: dict[str, list[NodeRecord]] = {}
    for node in nodes:
        by_surface.setdefault(node.surface, []).append(node)

    lines: list[str] = []
    lines.append("# Knowledge Index")
    lines.append(
        f"Surfaces: {len(by_surface)}   Nodes: {len(nodes)}   Edges: {len(filtered_edges)}   "
        f"Files: {files_count}   Missing: {missing_count}   Declined: {declined}"
    )
    lines.append("")

    for surface_name, snodes in sorted(by_surface.items()):
        lines.append(f"## {surface_name} ({len(snodes)})")
        for node in snodes:
            desc = node.description or "(no description)"
            lines.append(f"  [{node.surface}] {node.id} — {desc}")
            # Inline edges for this node
            node_edges = [e for e in filtered_edges if e.source_id == node.id]
            for edge in node_edges:
                lines.append(f"    -> {edge.edge_type}: {edge.target_id}")
        lines.append("")

    if show_edges and edges:
        lines.append("## edges")
        for edge in edges:
            lines.append(f"  {edge.source_id} --[{edge.edge_type}]--> {edge.target_id}")
        lines.append("")

    return "\n".join(lines)


def render_json(
    nodes: list[NodeRecord],
    edges: list[EdgeRecord],
    declined: int = 0,
) -> str:
    """Render the knowledge index as JSON.

    Args:
        nodes: List of NodeRecords.
        edges: List of EdgeRecords.
        declined: Number of relationship values declined as not a repo path
            (KM-KGS-100d-4-iii). Zero included, never omitted.

    Returns:
        JSON string with top-level 'nodes' and 'edges' keys, plus the
        always-emitted integer keys 'files_nodes', 'missing_files' and
        'declined' (KM-KGS-100d-4-ii/-iii), zero included.
    """
    files_nodes, missing_files = _files_and_missing_counts(nodes)
    return json.dumps(
        {
            "nodes": [
                {
                    "id": n.id,
                    "surface": n.surface,
                    "title": n.title,
                    "description": n.description,
                    "path": str(n.path),
                    "missing": n.missing,
                }
                for n in nodes
            ],
            "edges": [
                {
                    "source": e.source_id,
                    "target": e.target_id,
                    "type": e.edge_type,
                    "anchor": e.anchor,
                }
                for e in edges
            ],
            "files_nodes": files_nodes,
            "missing_files": missing_files,
            "declined": declined,
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Entry point for knowledge_query CLI.

    Args:
        argv: Argument list. Defaults to ``sys.argv[1:]`` when None.

    Returns:
        Exit code: 0 on success, 1 on fatal error.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Single-pass traversal of all knowledge surfaces defined in paths.json. "
            "Produces a flat node+edge index for cross-surface search and graph export."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  knowledge_query.py\n"
            "  knowledge_query.py --query roadmap\n"
            "  knowledge_query.py --surface agents\n"
            "  knowledge_query.py --format json\n"
            "  knowledge_query.py --edges\n"
            "  knowledge_query.py --project-root /path/to/project\n"
            "  knowledge_query.py --list-surfaces\n"
        ),
    )
    parser.add_argument(
        "--query",
        metavar="KEYWORD",
        default=None,
        help=(
            "Filter nodes by keyword (case-insensitive). "
            "Matches against title and description fields."
        ),
    )
    parser.add_argument(
        "--surface",
        metavar="NAME",
        default=None,
        help="Restrict output to one named surface (e.g. agents, tickets, docs).",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format: 'text' (default) or 'json'.",
    )
    parser.add_argument(
        "--edges",
        action="store_true",
        help="Include the full edge list section in text output.",
    )
    parser.add_argument(
        "--project-root",
        metavar="DIR",
        help="Root of the project to scan. Defaults to the current working directory.",
    )
    parser.add_argument(
        "--list-surfaces",
        action="store_true",
        help="List the knowledge surfaces declared in config/paths.json and exit.",
    )
    args = parser.parse_args(argv)

    project_root = (
        Path(args.project_root).resolve() if args.project_root else Path.cwd()
    )
    paths_json = project_root / "config" / "paths.json"

    if args.list_surfaces:
        if not paths_json.exists():
            print(
                f"ERROR: {paths_json.name} not found at {paths_json}.",
                file=sys.stderr,
            )
            return 1
        try:
            raw = paths_json.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"ERROR: Cannot read {paths_json}: {exc}", file=sys.stderr)
            return 1
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            print(f"ERROR: {paths_json.name} is not valid JSON: {exc}", file=sys.stderr)
            return 1
        surfaces_cfg = data.get("surfaces", {})
        for name in surfaces_cfg:
            print(name)
        return 0

    nodes, edges, declines = _collect_all_ex(project_root, paths_json, surface_filter=args.surface)
    for decline in declines:
        print(_file_nodes.format_decline_line(decline), file=sys.stderr)

    if args.format == "json":
        print(render_json(nodes, edges, declined=len(declines)))
        return 0

    print(render_text(nodes, edges, query=args.query, show_edges=args.edges, declined=len(declines)))
    return 0


if __name__ == "__main__":
    sys.exit(main())


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-05 14:00 [EPIC-KnowledgeGraphQueryLayer/01a]: Initial implementation. (#EPIC-KnowledgeGraphQueryLayer/01a)
  Single-pass traversal of all knowledge surfaces (agents, skills, tickets,
  docs, adrs, components, roadmap, glossary). Surface discovery via paths.json
  (AC-5). Three public functions: load_surfaces, extract_nodes, extract_edges
  (AC-7). NodeRecord/EdgeRecord NamedTuples. CLI flags: --query, --surface,
  --format, --edges, --project-root. Stdlib-only (AC-1). Clean error when
  paths.json absent (AC-6). render_text and render_json as separate functions.
- 2026-06-22 [03_TICKET-20260622-KM-KGS-100a-2-i]: Skip YAML files with no id field in _extract_nodes_from_dir. (#03_TICKET-20260622-KM-KGS-100a-2-i)
  Added import logging and a module-level logger. Updated _extract_nodes_from_dir to skip
  YAML files where _parse_yaml_file returns no 'id' field — covers both "file with no id
  field" and "unparseable file" cases (both yield an empty or id-less dict). Emits a
  logger.warning per skipped file. Valid criterion files with an id field are unaffected.
  Also tightened the OSError except block in the YAML read path to log the exception
  instead of silently continuing (error handling policy compliance).
- 2026-06-22 [02_TICKET-20260622-KM-KGS-100a-2]: AC YAML node extraction in _extract_nodes_from_dir. (#02_TICKET-20260622-KM-KGS-100a-2)
  Added _parse_yaml_file() — a stdlib-only plain-YAML parser (no --- delimiters) that
  handles scalar values, block-scalar (|/>), and block-list items. Updated
  _extract_nodes_from_dir() to glob **/*.yaml after **/*.md, skipping index.yaml, and
  yield NodeRecords with id/title/description taken from parsed YAML fields (fallback to
  stem). Updated _collect_all() to also extract edges from .yaml nodes via _parse_yaml_file
  + extract_edges, mirroring the existing .md frontmatter path. PyYAML is intentionally
  excluded (forbidden by AC test suite stdlib-only check).
- 2026-06-22 [01_TICKET-20260622-KM-KGS-100a-1]: Added acs surface + dynamic edge_fields loading. (#01_TICKET-20260622-KM-KGS-100a-1)
  Added "acs" surface entry to config/paths.json (path: docs/acceptance-criteria/,
  edge_fields: implemented_by, covered_by, depends_on, components). Introduced
  load_surfaces_with_meta() to return both path and edge_fields per surface.
  Updated _collect_all() to use load_surfaces_with_meta and pass surface_edge_fields
  to extract_edges, removing the need to update _SURFACE_EDGE_FIELDS for new
  surfaces. extract_edges() gains an optional edge_fields parameter; falls back
  to legacy _SURFACE_EDGE_FIELDS when None for backward compatibility.
- 2026-06-22 [06_TICKET-20260622-KM-KGS-100b-1]: Named constant _AC_EDGE_TYPES for the four AC outbound edge types; fixed inline flow-sequence parsing. (#06_TICKET-20260622-KM-KGS-100b-1)
  Added _AC_EDGE_TYPES frozenset documenting the canonical four edge types produced
  by the acs surface: implemented_by, covered_by, depends_on, component_membership.
  Satisfies AC KM-KGS-100b-1: "no extra outbound relationship kind is returned beyond
  these four". The constraint is enforced by edge_fields in paths.json acs entry;
  _AC_EDGE_TYPES is the single authoritative constant for downstream tools to
  validate against. Updated templates/skills/knowledge-query/SKILL.md acs row to
  state "exactly four outbound edge types and no others" with per-type descriptions.
  Also fixed _parse_scalar_value to handle inline YAML flow sequences ([] and
  [item1, item2]) — previously [] was returned as the string "[]", causing phantom
  edges with target_id="[]" to slip through phantom filtering. The fix returns an
  empty list for [] and a list of stripped items for non-empty inline sequences.
  Fixed unit_tests/test_knowledge_query.py TestEdgeCountIntegration to exempt
  implemented_by and covered_by from the "no phantom targets" assertion — these
  edge types intentionally point to file paths not in the node set.
- 2026-06-22 [10_TICKET-20260622-KM-KGS-100c-1]: Added build_knowledge_map() public API for surface-completeness assertions. (#10_TICKET-20260622-KM-KGS-100c-1)
  Introduced KnowledgeMap NamedTuple (nodes, edges, declared_surfaces,
  contributing_surfaces) and build_knowledge_map() public function. Satisfies
  AC KM-KGS-100c-1: "the build asserts against the declared set itself, not a
  fixed expected number of surfaces." The KnowledgeMap carries both the graph
  data and audit metadata so callers can write:
      assert km.contributing_surfaces == km.declared_surfaces
  without enumerating any specific surface name. declared_surfaces is derived
  dynamically from paths.json via load_surfaces_with_meta(); contributing_surfaces
  is the subset that actually produced at least one primary NodeRecord. Tests in
  unit_tests/test_knowledge_query.py (TestSurfaceContributionCompleteness) validate
  the AC behavior using parametric assertions against the declared set.
- 2026-06-22 [11_TICKET-20260622-KM-KGS-100c-2]: Data-driven phantom-filter-exempt via file_path_fields in paths.json. (#11_TICKET-20260622-KM-KGS-100c-2)
  Added optional ``file_path_fields`` attribute to paths.json surface entries. When
  present, these field names are automatically added to the phantom-edge-filter-exempt
  set in _collect_all(), removing the code-level special-case of hardcoding
  ``implemented_by`` and ``covered_by`` in ``_PHANTOM_FILTER_EXEMPT_EDGE_TYPES``.
  Updated ``load_surfaces_with_meta()`` to capture ``file_path_fields`` from each
  surface entry. Updated ``_collect_all()`` to build ``effective_exempt`` dynamically
  by unioning the legacy constant with all ``file_path_fields`` values from
  paths.json. Added ``file_path_fields: [implemented_by, covered_by]`` to the ``acs``
  surface entry in config/paths.json. Any new surface that declares file-path edge
  fields now only needs a paths.json entry — no code change is required. Satisfies
  AC KM-KGS-100c-2: "no special-casing for acs that other surfaces do not also receive."
- 2026-06-22 [13_TICKET-20260622-KM-KGS-100d-1]: Data-driven surface edge_fields validation via validate_knowledge_map(). (#13_TICKET-20260622-KM-KGS-100d-1)
  Added SurfaceValidationResult NamedTuple (surface, declared_edge_fields,
  unexpected_edge_types, valid) and validate_knowledge_map() public function.
  Satisfies AC KM-KGS-100d-1: "for every declared surface, the validation checks
  that surface against the exact edge_fields it declares — not against a fixed
  expected list of relationship kinds." The validation iterates over
  knowledge_map.declared_surfaces (derived from paths.json) so adding or removing
  a surface changes the validated set without any code edit. Surfaces that declare
  an empty edge_fields list are accepted as valid when they produce no edges.
  The 'components' field is transparently remapped to 'component_membership' in
  allowed_types so the validation accounts for the canonical edge-type rename
  applied by extract_edges(). Updated module docstring ARCHITECTURE field to list
  six public functions (validate_knowledge_map added).
- 2026-06-24 [15_TICKET-20260622-KM-KGS-100d-2-i]: Drop missing-target edges in validate_edges_integrity; log dropped edges in _collect_all. (#15_TICKET-20260622-KM-KGS-100d-2-i)
  Satisfies AC KM-KGS-100d-2-i: "a relationship pointing at a missing target is
  dropped, not rendered as a dead end." Updated EdgeIntegrityResult NamedTuple to
  add two new fields: dropped_edges (list of EdgeRecords silently dropped because
  their target node was absent) and validated_edges (the surviving edge set after
  drops). Changed validate_edges_integrity() to use a two-tier policy: missing-
  target edges are dropped (logged at DEBUG) rather than flagged as valid=False;
  only missing-source edges trigger valid=False. Updated _collect_all() phantom-
  edge filter from a list comprehension to an explicit loop that emits a
  logger.debug() for each dropped edge (missing source or missing target), so
  drops are observable without being noisy. Updated module docstring ARCHITECTURE
  to describe the two-tier policy. The build does not fail solely because a
  relationship named a missing target (Gherkin clause 3 of the AC).
- 2026-09-16 09:00 [python-coder]: Quote-aware block-list item parsing plus
  indentation-tolerant list scanning. (#TICKETLESS reason=km-kgs-100a-3-i-vii-fastlane)
  Introduced _strip_matched_quotes() (strips a matched surrounding quote pair
  without touching an interior or single-sided quote) and made
  _split_flow_sequence_items() quote-aware so a comma inside a quoted flow-
  sequence item is not treated as an item separator. Generalized
  _parse_block_children() to accept "- item" lines at any indentation, not
  just a fixed two-space depth, since YAML block-list indentation is not
  itself significant to list membership. Applied uniformly to both
  _parse_frontmatter() (.md) and _parse_yaml_file() (.yaml) since both call
  _parse_block_children().
- 2026-09-16 10:30 [python-coder]: Comment and blank lines inside a block list no
  longer end the list or become items. (#TICKETLESS reason=km-kgs-100a-3-ix-fastlane)
  A whole-store differential against PyYAML (KM-KGS-100a-3-viii) found one
  remaining disagreement: docs/acceptance-criteria/build-orchestration/BO-201.yaml
  declares covered_by as a block list whose first item is followed by seven
  indented comment lines and then a second, unquoted item; _parse_block_children
  treated the first comment line as the end of the list and silently dropped
  every item after it. Fixed by skipping any line whose stripped text starts
  with "#" (blank lines were already skipped) inside _parse_block_children,
  before the "- " item check and before the not-a-list-item break that ends
  the scan. This holds at any indentation, including column zero, and even
  when the comment's text looks like a "key: value" line (e.g.
  "# covers: KM-EX-010") — it is still just skipped, never mistaken for the
  next top-level key. The list still ends at the first non-blank,
  non-comment line that isn't a "- " item (the real next top-level key), and
  a "#" inside an item value (a path#symbol anchor, KM-KGS-100a-3-v) is
  unaffected because only the stripped line's leading character is checked,
  never a substring scan of item text. Since both _parse_frontmatter() (.md)
  and _parse_yaml_file() (.yaml) delegate to _parse_block_children(), the fix
  applies uniformly to both readers with a single change.
- 2026-09-16 12:00 [python-coder]: Continuation lines inside a block list no
  longer end the list; trailing inline comments on unquoted items are
  stripped. (#TICKETLESS reason=km-kgs-100a-3-x-fastlane)
  Fixed a regression introduced by the -i..-ix fastlane work: a line indented
  deeper than the list's item column that was not itself a "- " item ended
  the scan outright, dropping every later item — on the real store this
  truncated docs/acceptance-criteria/index.yaml's `components` list from 16
  PyYAML-equivalent entries to 1. Reworked _parse_block_children() so the
  indentation of the list's *first* item fixes the item column for the rest
  of the list (a deeper "- " line, e.g. a nested `directory_patterns` list
  inside a mapping item, is never mistaken for a sibling item); a
  non-blank, non-comment line indented deeper than that column now
  continues the current item instead of ending the list. For a plain
  scalar item the continuation folds in with a single space, matching
  PyYAML; for a mapping item (item text matching `key: value`) the
  continuation is discarded rather than folded, since the mapping item's
  own produced value is an explicit non-goal — discarding still guarantees
  the list is never truncated and the next top-level key's items are never
  absorbed. Added _line_indent() to measure a raw line's leading-space
  count, and _is_mapping_item_text() to classify an item's text. Also fixed
  the pre-existing gap where a trailing "# comment" on a plain (unquoted)
  list item stayed in the value: added _strip_inline_comment(), a
  quote-aware scanner that treats a "#" preceded by whitespace as a comment
  start, leaves a "#" glued to a token (`path#symbol`) or inside a matched
  quoted span untouched, and — for a quoted item followed by trailing text
  (`"a b"  # note`) — strips the comment after the closing quote before
  _strip_matched_quotes() removes the quotes. Applied to both the initial
  item text and to continuation lines. Since both _parse_frontmatter()
  (.md) and _parse_yaml_file() (.yaml) delegate to _parse_block_children(),
  the fix applies uniformly to both readers with a single change.
- 2026-09-17 12:00 [python-coder]: Extracted the ten frontmatter-reader
  functions into scripts/knowledge_frontmatter_reader.py. (#TICKETLESS
  reason=km-kgs-100a-3-xi-fastlane)
  Moved _find_frontmatter_end, _strip_matched_quotes,
  _split_flow_sequence_items, _parse_scalar_value, _line_indent,
  _strip_inline_comment, _is_mapping_item_text, _parse_block_children,
  _parse_frontmatter and _parse_yaml_file (plus the _MAPPING_ITEM_PATTERN
  constant they share) verbatim into a new sibling module — no reader rule
  from KM-KGS-100a-3-i..-x changed. This file's own code length (1104
  content lines) had grown past its origin/main baseline (1013), which the
  check-file-size ratchet (GE-127a-1/GE-127b-1) refuses for an
  already-oversized file. Added _load_reader_module(), which resolves
  knowledge_frontmatter_reader.py relative to THIS file's own __file__
  (never sys.path, never a hard-coded absolute path) via
  importlib.util.spec_from_file_location, registers it in sys.modules, and
  re-exports all ten names as the reader module's own function objects
  (identity, not a copy) — so every existing caller in this file, plus
  scripts/visualise_knowledge_graph.py's spec_from_file_location load with
  no scripts/ directory on sys.path, keeps working unchanged. Also dropped
  the now-unused top-level `import re` (all re.* usage moved with the
  functions) and added `import importlib.util`. Deploy wiring
  (scripts/build_phases_knowledge.py, scripts/build.py,
  scripts/build_phases_workflows.py) updated in the same change so the new
  module ships alongside knowledge_query.py in every consumer install.
- 2026-09-25 [python-coder/KM-KGS-100d-4 epic]: File-path relationship
  values (implemented_by, covered_by, files_touched, and any field a
  surface declares in its own file_path_fields) now resolve to real,
  path-keyed 'files'-surface nodes instead of surviving only via the
  retired _PHANTOM_FILTER_EXEMPT_EDGE_TYPES exemption (deleted, together
  with _collect_all's dynamic_exempt/effective_exempt union logic and
  validate_edges_integrity's file_path_fields-derived exempt-set
  computation — exempt_edge_types is now always frozenset()). Added
  NodeRecord.missing (default False; True only for a 'files' node whose
  canonical path does not exist under the project root, tested once per
  distinct path) and EdgeRecord.anchor (the stripped '#symbol'/'::test'
  suffix, or None). KnowledgeMap gained declined_count. The new logic
  (canonicalisation, the ambiguity rule, present/missing marking, decline
  reporting) lives in a NEW sibling module, scripts/knowledge_file_nodes.py,
  loaded the same way knowledge_frontmatter_reader.py already is — via the
  now-generalised _load_sibling_module(name) (renamed from
  _load_reader_module, which took no argument; every existing caller of
  the ten re-exported reader names is unaffected, since only the loader's
  own name changed, not what it returns). _collect_all's body moved,
  unchanged in its traversal logic, into a new _collect_all_ex() that
  additionally routes each file_path_fields-declared candidate edge (via
  the new _route_edges() helper, replacing three duplicated
  extract-then-append blocks) into a pending list, resolves it through
  knowledge_file_nodes.resolve_file_path_edges() in the SAME
  post-processing step that creates component hubs (before the membership
  filter), and returns the resulting declines as a third tuple element;
  _collect_all() itself is now a 2-tuple-returning wrapper so every
  existing direct caller (the visualiser, unit_tests/test_ac_edge_
  relationships.py) is unchanged. build_knowledge_map() and the CLI's
  main() now call _collect_all_ex() directly. render_json() gained
  'files_nodes', 'missing_files' and 'declined' top-level integer keys
  (zero included) and a per-node 'missing' boolean and per-edge 'anchor'
  key; render_text() gained 'Files:'/'Missing:'/'Declined:' labels beside
  the existing Edges figure, computed from the unfiltered node set so a
  --query keyword never changes them. main() prints one
  'DECLINED | surface=... | doc=... | field=... | value=... | reason=...'
  stderr line per decline (KM-KGS-100d-4-iii), carried out of
  _collect_all_ex as data and only printed here, never from inside a
  generator. Deploy wiring for knowledge_file_nodes.py added to
  scripts/build_phases_knowledge.py's _manifest_workflow_tool_scripts and
  scripts/build_phases_workflows.py's build_workflow_tools, alongside
  knowledge_frontmatter_reader.py. (#TICKETLESS reason=km-fast-lane-file-nodes)
====================================================================
"""
