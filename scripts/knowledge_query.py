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
ARCHITECTURE: Four public functions (load_surfaces, load_surfaces_with_meta,
    extract_nodes, extract_edges) and a CLI entry point. Surface discovery
    driven by paths.json; no surface path or edge_fields list is hardcoded —
    adding a new surface only requires a new entry in paths.json. All file I/O
    wrapped in try/except with specific exception types (repo error-handling
    policy). Stdlib-only: no third-party dependencies.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Generator
from pathlib import Path
from typing import Any, NamedTuple


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class NodeRecord(NamedTuple):
    """A single node in the knowledge graph.

    Attributes:
        id: Unique identifier for the node (slug or filename stem).
        surface: The surface this node belongs to (e.g. 'agents', 'tickets').
        title: Human-readable display name.
        description: One-line summary extracted from frontmatter or body.
        path: Absolute or relative Path to the source file or registry.
    """

    id: str
    surface: str
    title: str
    description: str
    path: Path


class EdgeRecord(NamedTuple):
    """A directed edge between two nodes in the knowledge graph.

    Attributes:
        source_id: Node id of the source.
        target_id: Node id of the target.
        edge_type: Semantic label for the edge (e.g. 'spawn_allowlist',
            'depends_on', 'files_touched').
    """

    source_id: str
    target_id: str
    edge_type: str


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

# ---------------------------------------------------------------------------
# Frontmatter parser (stdlib only, mirrors roadmap_query.py pattern)
# ---------------------------------------------------------------------------


def _find_frontmatter_end(lines: list[str]) -> int:
    """Return the index of the closing ``---`` delimiter, or -1 if absent.

    Args:
        lines: All lines of the file. Assumes ``lines[0]`` is ``---``.

    Returns:
        Line index of the closing delimiter, or -1 if not found.
    """
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            return i
    return -1


def _parse_scalar_value(raw: str) -> Any:
    """Parse an inline scalar YAML value string.

    Args:
        raw: Trimmed right-hand side of a ``key: value`` YAML line.

    Returns:
        True, False, None, or a string.
    """
    lower = raw.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    if lower in ("null", "~"):
        return None
    if len(raw) >= 2 and raw[0] in ('"', "'") and raw[-1] == raw[0]:
        return raw[1:-1]
    return raw


def _parse_block_children(lines: list[str], start: int, end: int) -> tuple[list[str], int]:
    """Collect YAML list items from indented lines following a bare ``key:`` line.

    Args:
        lines: All lines of the file.
        start: Index of the first line after the bare ``key:`` line.
        end: Index of the closing ``---`` delimiter.

    Returns:
        A tuple of (list_of_items, next_line_index).
    """
    children: list[str] = []
    j = start
    while j < end and (lines[j].startswith("  ") or lines[j].strip() == ""):
        stripped = lines[j].strip()
        if stripped.startswith("- "):
            children.append(stripped[2:].strip())
        j += 1
    return children, j


def _parse_frontmatter(text: str) -> dict[str, Any]:
    """Extract YAML frontmatter fields from a markdown file's text.

    Args:
        text: Full text content of a file.

    Returns:
        Dict of frontmatter field names to values. Empty dict when absent.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end = _find_frontmatter_end(lines)
    if end == -1:
        return {}
    fm: dict[str, Any] = {}
    i = 1
    while i < end:
        line = lines[i]
        if not line.strip() or line.startswith("  "):
            i += 1
            continue
        m = re.match(r"^(\w[\w_-]*):\s*(.*)", line)
        if not m:
            i += 1
            continue
        key = m.group(1)
        raw = m.group(2).strip()
        if raw == "":
            children, i = _parse_block_children(lines, i + 1, end)
            if children:
                fm[key] = children
            continue
        fm[key] = _parse_scalar_value(raw)
        i += 1
    return fm


def _parse_yaml_file(text: str) -> dict[str, Any]:
    """Parse a plain YAML file (no ``---`` delimiters) and return a flat field dict.

    Handles only the scalar and block-list syntax used by AC YAML files:
    - ``key: value`` scalar lines at column 0
    - ``key: |`` multiline block scalars (value collected as-is)
    - ``key:`` bare lines followed by indented ``- item`` list lines

    This is intentionally minimal — it covers the AC YAML schema and nothing
    more. It does not support nested mappings, anchors, or flow scalars.
    Stdlib-only: no third-party imports (PyYAML is explicitly excluded by the
    project's stdlib-only policy and by the AC test suite's forbidden-imports
    check).

    Args:
        text: Full text content of a YAML file (no frontmatter delimiters).

    Returns:
        Dict of field names to parsed values.  Empty dict on empty input.
    """
    lines = text.splitlines()
    total = len(lines)
    result: dict[str, Any] = {}
    i = 0
    while i < total:
        line = lines[i]
        # Skip blank lines and comment lines
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue
        # Skip indented lines at the top level (they belong to a prior block)
        if line.startswith("  ") or line.startswith("\t"):
            i += 1
            continue
        m = re.match(r"^(\w[\w_-]*):\s*(.*)", line)
        if not m:
            i += 1
            continue
        key = m.group(1)
        raw = m.group(2).strip()
        # Block scalar indicator ``|`` or ``>``
        if raw in ("|", ">"):
            # Collect all indented lines following as a single string
            block_lines: list[str] = []
            i += 1
            while i < total and (lines[i].startswith("  ") or lines[i].startswith("\t") or lines[i].strip() == ""):
                block_lines.append(lines[i])
                i += 1
            # Dedent by 2 spaces if applicable, then join
            dedented = []
            for bl in block_lines:
                if bl.startswith("  "):
                    dedented.append(bl[2:])
                elif bl.startswith("\t"):
                    dedented.append(bl[1:])
                else:
                    dedented.append(bl)
            result[key] = "\n".join(dedented).rstrip()
            continue
        # Bare key — may be followed by block list items
        if raw == "":
            children, i = _parse_block_children(lines, i + 1, total)
            if children:
                result[key] = children
            continue
        # Inline scalar value
        result[key] = _parse_scalar_value(raw)
        i += 1
    return result


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
        list[str]}``.

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
        result[name] = {"path": resolved, "edge_fields": edge_fields}

    return result


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
        except OSError:
            continue
        fields = _parse_yaml_file(text)
        node_id = str(fields.get("id") or yaml_file.stem)
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


def _collect_all(
    project_root: Path,
    paths_json: Path,
    surface_filter: str | None = None,
) -> tuple[list[NodeRecord], list[EdgeRecord]]:
    """Traverse all surfaces and collect nodes and edges.

    After collecting all primary nodes and edges, this function:
    1. Creates synthetic hub NodeRecords for each unique component value seen in
       component_membership edges that doesn't already exist as a node. These
       hubs have surface="components".
    2. Filters edges to keep only those where both source_id and target_id exist
       in the full node set (including synthetic hubs). This removes phantom
       edge targets without using a hardcoded blocklist.

    Args:
        project_root: Absolute path to the project root.
        paths_json: Path to paths.json.
        surface_filter: When non-None, restrict traversal to this surface only.

    Returns:
        Tuple of (nodes_list, edges_list).
    """
    surfaces_meta = load_surfaces_with_meta(project_root, paths_json)
    all_nodes: list[NodeRecord] = []
    all_edges: list[EdgeRecord] = []

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
                try:
                    data = json.loads(surface_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
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
                    if isinstance(entry, dict):
                        entry_id = str(entry.get("id") or entry.get("name") or "")
                        if entry_id == node.id:
                            for edge in extract_edges(
                                surface_name, node, entry, surface_edge_fields
                            ):
                                all_edges.append(edge)
            elif surface_path.is_dir() or (surface_path.is_file() and surface_path.suffix == ".md"):
                # For markdown nodes, try to extract edges from frontmatter
                if node.path.is_file() and node.path.suffix == ".md":
                    try:
                        text = node.path.read_text(encoding="utf-8")
                    except OSError:
                        continue
                    fm = _parse_frontmatter(text)
                    for edge in extract_edges(
                        surface_name, node, fm, surface_edge_fields
                    ):
                        all_edges.append(edge)
                # For YAML nodes (e.g. acs surface), extract edges from parsed fields
                elif node.path.is_file() and node.path.suffix == ".yaml":
                    try:
                        text = node.path.read_text(encoding="utf-8")
                    except OSError:
                        continue
                    fields = _parse_yaml_file(text)
                    for edge in extract_edges(
                        surface_name, node, fields, surface_edge_fields
                    ):
                        all_edges.append(edge)

    # Post-processing step 1: create synthetic hub nodes for component values
    # that appear as targets in component_membership edges but don't exist yet.
    existing_ids = {n.id for n in all_nodes}
    seen_component_targets: set[str] = set()
    for edge in all_edges:
        if edge.edge_type == "component_membership":
            seen_component_targets.add(edge.target_id)

    for component_name in sorted(seen_component_targets):
        if component_name not in existing_ids:
            # Title: replace hyphens and underscores with spaces, title-case each word
            hub_title = component_name.replace("-", " ").replace("_", " ").title()
            hub_node = NodeRecord(
                id=component_name,
                surface="components",
                title=hub_title,
                description=f"Component hub: {component_name}",
                path=Path("docs/architecture/components/"),
            )
            all_nodes.append(hub_node)
            existing_ids.add(component_name)

    # Post-processing step 2: filter phantom edges — keep only edges where both
    # source and target exist in the node set (no hardcoded blocklist).
    node_ids = existing_ids
    filtered_edges = [
        e for e in all_edges
        if e.source_id in node_ids and e.target_id in node_ids
    ]

    return all_nodes, filtered_edges


# ---------------------------------------------------------------------------
# Output rendering
# ---------------------------------------------------------------------------


def render_text(
    nodes: list[NodeRecord],
    edges: list[EdgeRecord],
    query: str | None,
    show_edges: bool,
) -> str:
    """Render the knowledge index as human-readable text.

    Args:
        nodes: List of NodeRecords to include.
        edges: List of EdgeRecords to include.
        query: Optional keyword filter (case-insensitive).
        show_edges: When True, append the full edge list section.

    Returns:
        Multi-line formatted string.
    """
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
    lines.append(f"Surfaces: {len(by_surface)}   Nodes: {len(nodes)}   Edges: {len(filtered_edges)}")
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
) -> str:
    """Render the knowledge index as JSON.

    Args:
        nodes: List of NodeRecords.
        edges: List of EdgeRecords.

    Returns:
        JSON string with top-level 'nodes' and 'edges' keys.
    """
    return json.dumps(
        {
            "nodes": [
                {
                    "id": n.id,
                    "surface": n.surface,
                    "title": n.title,
                    "description": n.description,
                    "path": str(n.path),
                }
                for n in nodes
            ],
            "edges": [
                {
                    "source": e.source_id,
                    "target": e.target_id,
                    "type": e.edge_type,
                }
                for e in edges
            ],
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
    args = parser.parse_args(argv)

    project_root = (
        Path(args.project_root).resolve() if args.project_root else Path.cwd()
    )
    paths_json = project_root / "config" / "paths.json"

    nodes, edges = _collect_all(project_root, paths_json, surface_filter=args.surface)

    if args.format == "json":
        print(render_json(nodes, edges))
        return 0

    print(render_text(nodes, edges, query=args.query, show_edges=args.edges))
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
====================================================================
"""
