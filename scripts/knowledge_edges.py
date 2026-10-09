"""
MODULE: knowledge_edges
GOAL: Turn one node's raw frontmatter / registry / YAML data into candidate
      EdgeRecords, count what each declared field produced or had refused,
      and route each candidate either onto the ordinary edge list or onto the
      deferred file-path list.
BUSINESS CONTEXT: The edge-extraction path of the knowledge graph builder.
    GE-127 puts a ratchet on file size (check-file-size): knowledge_query.py
    was over its limit and a change that grew it was refused, so this
    cohesive block moved out verbatim rather than being compressed. The
    behaviour is KM-KGS-100d-3-i's: every list entry the shared resolver
    refuses is announced and counted per field instead of dropped silently,
    and ``edges`` is counted at yield time, before the dangling-edge filter.
ARCHITECTURE: Sibling module to knowledge_query.py, loaded the same way as
    knowledge_file_nodes.py (``_load_sibling_module("knowledge_edges")``,
    resolved relative to knowledge_query.py's own ``__file__``), so it works
    both from source and from a deployed ``.leafcutter/scripts/``. This module
    never imports knowledge_query (that would be circular): it owns
    ``EdgeRecord`` and the edge-field constants, which knowledge_query
    re-exports as the SAME objects, and it reads a node only through the
    structural ``_NodeLike`` protocol (``id`` and ``path``). It loads the two
    sibling modules it needs (frontmatter reader, path resolver) itself by
    the same file-path rule, sharing their ``sys.modules`` entries.
    Stdlib-only (KM-KQS-007).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from collections.abc import Generator, Iterable
from pathlib import Path
from types import ModuleType
from typing import Any, NamedTuple, Protocol


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


class _NodeLike(Protocol):
    """The two attributes of knowledge_query.NodeRecord this module reads."""

    @property
    def id(self) -> str: ...

    @property
    def path(self) -> Path: ...


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

# (surface, node, field, raw_value); node is Any so the caller's own
# list[tuple[str, NodeRecord, str, str]] is accepted despite list invariance.
_PendingList = list[tuple[str, Any, str, str]]


def _sibling(module_name: str) -> ModuleType:
    """Load (or reuse from ``sys.modules``) the "<module_name>.py" next to this file.

    Same rule as knowledge_query._load_sibling_module: resolved from THIS
    file's ``__file__``, never ``sys.path``, cached under its own name so the
    entry knowledge_query already created is reused rather than duplicated.

    Args:
        module_name: Bare module name of a sibling in the same directory.

    Returns:
        The loaded sibling module.

    Raises:
        ImportError: When importlib cannot build a loadable spec.
    """
    if (cached := sys.modules.get(module_name)) is not None:
        return cached
    module_path = Path(__file__).resolve().parent / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {module_path}")  # noqa: TRY003
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_reader = _sibling("knowledge_frontmatter_reader")
_resolver = _sibling("frontmatter_path_resolver")
resolve_frontmatter_path_entry = _resolver.resolve_frontmatter_path_entry
PathEntryRefusal = _resolver.PathEntryRefusal


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
    record: _NodeLike,
    raw_data: dict[str, Any],
    edge_fields: list[str] | None = None,
    declines: list | None = None,
    field_counts: dict[str, dict[str, int]] | None = None,
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
        declines: Optional out-list. Each list element the shared resolver
            refuses is appended as ``(surface, record, field, entry,
            reason)`` instead of being dropped silently (KM-KGS-100d-3-i).
        field_counts: Optional accumulator ``{field: {"edges": n, "declined":
            m}}``. Every examined field gets an entry (zero included); counts
            are taken as edges are yielded / entries refused, so they are
            correct however much of the generator the caller consumes.

    Yields:
        EdgeRecord for each outbound edge.
    """
    if edge_fields is None:
        edge_fields = _SURFACE_EDGE_FIELDS.get(surface, [])
    for field in edge_fields:
        # Register the field BEFORE reading its value so a field the document
        # does not declare is still stated as edges=0 declined=0.
        figures = field_counts.setdefault(field, {"edges": 0, "declined": 0}) if field_counts is not None else None
        value = raw_data.get(field)
        if value is None:
            continue
        # Determine edge type: components field uses "component_membership"
        edge_type = "component_membership" if field in _COMPONENT_FIELDS else field
        if isinstance(value, str):
            if value:
                target = _resolve_depends_on_target(value) if field in _PATH_FIELDS else value
                _bump(figures, "edges")
                yield EdgeRecord(source_id=record.id, target_id=target, edge_type=edge_type)
        elif isinstance(value, list):
            for item in value:
                # No early skip of "": the shared resolver refuses it, so an
                # empty entry is announced and counted like any other refusal.
                resolved = resolve_frontmatter_path_entry(_reader.entry_for_resolver(item), field)
                if isinstance(resolved, PathEntryRefusal):
                    if declines is not None:
                        declines.append((surface, record, field, item, resolved.reason))
                    _bump(figures, "declined")
                    continue
                target = _resolve_depends_on_target(resolved) if field in _PATH_FIELDS else resolved
                # DENOMINATOR: "edges" is counted HERE, at yield, i.e. BEFORE
                # _filter_dangling_edges. It measures what the field's entries
                # produced, so edges=0 declined=0 means "nothing declared"
                # and edges=0 declined=3 means "declared but refused". Counting
                # after the dangling filter would conflate a target that is
                # not a node with a field that contributed nothing.
                # Bumped before the yield: code after a yield runs only if the
                # caller resumes, so a bump after it could be lost.
                _bump(figures, "edges")
                yield EdgeRecord(source_id=record.id, target_id=target, edge_type=edge_type)


def _bump(figures: dict[str, int] | None, key: str) -> None:
    """Increment *key* in a per-field figures dict, if one is being kept."""
    if figures is not None:
        figures[key] += 1


def _route_edges(edges: Iterable[EdgeRecord], surface_name: str, node: _NodeLike, surface_info: dict, all_edges: list[EdgeRecord], pending: _PendingList) -> None:
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


def _extract_json_registry_edges(surface_name: str, node: _NodeLike, surface_path: Path, surface_edge_fields: list[str], surface_info: dict, all_edges: list[EdgeRecord], pending: _PendingList, entry_declines: list | None = None, field_counts: dict | None = None) -> None:
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
        entry_declines: Optional out-list of refused entries.
        field_counts: Optional per-field edges/declined accumulator.
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
            _route_edges(extract_edges(surface_name, node, entry, surface_edge_fields, entry_declines, field_counts), surface_name, node, surface_info, all_edges, pending)


def _extract_dir_edges(surface_name: str, node: _NodeLike, surface_edge_fields: list[str], surface_info: dict, all_edges: list[EdgeRecord], pending: _PendingList, entry_declines: list | None = None, field_counts: dict | None = None) -> None:
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
        entry_declines: Optional out-list of refused entries.
        field_counts: Optional per-field edges/declined accumulator.
    """
    if node.path.is_file() and node.path.suffix == ".md":
        try:
            text = node.path.read_text(encoding="utf-8")
        except OSError:
            return
        fm = _reader._parse_frontmatter(text)
        _route_edges(extract_edges(surface_name, node, fm, surface_edge_fields, entry_declines, field_counts), surface_name, node, surface_info, all_edges, pending)
    elif node.path.is_file() and node.path.suffix == ".yaml":
        try:
            text = node.path.read_text(encoding="utf-8")
        except OSError:
            return
        fields = _reader._parse_yaml_file(text)
        _route_edges(extract_edges(surface_name, node, fields, surface_edge_fields, entry_declines, field_counts), surface_name, node, surface_info, all_edges, pending)
