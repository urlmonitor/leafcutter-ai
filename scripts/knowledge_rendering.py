"""MODULE: knowledge_rendering
GOAL: Render canonical graph records without changing their identities.
BUSINESS CONTEXT: Keep CLI text and JSON output stable as the graph producer evolves.
ARCHITECTURE: Pure rendering sibling re-exported by knowledge_query; no graph traversal.

DECISION HISTORY
========================================
- 2026-10-01 [python-coder]: Extract existing rendering functions for the file-size ratchet.
- 2026-10-09 [python-coder]: KM-KGS-100d-3-i -- render per-field edges/declined figures
  (JSON ``field_counts``, text ``Field <name>: edges=<n> declined=<m>`` lines).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scripts.knowledge_query import NodeRecord, EdgeRecord


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


def _filter_text_nodes(nodes: list[NodeRecord], query: str | None) -> list[NodeRecord]:
    """Filter display nodes while leaving whole-build figures to the caller.

    Args:
        nodes: Unfiltered nodes in producer order.
        query: Optional case-insensitive title or description substring.

    Returns:
        Matching nodes in original order, or the original list without a query.
    """
    if not query:
        return nodes
    q_lower = query.lower()
    return [
        node
        for node in nodes
        if q_lower in (node.title or "").lower() or q_lower in (node.description or "").lower()
    ]


def render_text(
    nodes: list[NodeRecord],
    edges: list[EdgeRecord],
    query: str | None,
    show_edges: bool,
    declined: int = 0,
    entries_declined: int = 0,
    field_counts: dict[str, dict[str, int]] | None = None,
) -> str:
    """Render the knowledge index as human-readable text.

    Args:
        nodes: List of NodeRecords to include.
        edges: List of EdgeRecords to include.
        query: Optional keyword filter (case-insensitive).
        show_edges: When True, append the full edge list section.
        declined: Number of relationship values declined as not a repo path
            (KM-KGS-100d-4-iii). Zero included, never omitted.
        entries_declined: Number of list entries the shared resolver refused
            (KM-KGS-100d-3-i). Zero included, never omitted.
        field_counts: Per-field ``{"edges": n, "declined": m}`` figures, one
            entry per examined edge field, rendered as ``Field`` lines.

    Returns:
        Multi-line formatted string.
    """
    # Files/Missing are whole-build figures (KM-KGS-100d-4-ii), computed
    # from the unfiltered node set so a --query keyword never changes them.
    files_count, missing_count = _files_and_missing_counts(nodes)

    nodes = _filter_text_nodes(nodes, query)

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
        f"Files: {files_count}   Missing: {missing_count}   Declined: {declined}   "
        f"Entries declined: {entries_declined}"
    )
    # One line per examined edge field, zero included (KM-KGS-100d-3-i).
    for field_name, figures in sorted((field_counts or {}).items()):
        lines.append(f"Field {field_name}: edges={figures['edges']} declined={figures['declined']}")
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
    entries_declined: int = 0,
    field_counts: dict[str, dict[str, int]] | None = None,
) -> str:
    """Render the knowledge index as JSON.

    Args:
        field_counts: Per-field ``{"edges": n, "declined": m}`` figures, one
            entry per examined edge field, zero included (KM-KGS-100d-3-i).
        nodes: List of NodeRecords.
        edges: List of EdgeRecords.
        declined: Number of relationship values declined as not a repo path
            (KM-KGS-100d-4-iii). Zero included, never omitted.
        entries_declined: Number of list entries the shared resolver refused
            (KM-KGS-100d-3-i). Zero included, never omitted.

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
            "entries_declined": entries_declined,
            "field_counts": dict(sorted((field_counts or {}).items())),
        },
        indent=2,
    )
