"""
MODULE: knowledge_surface_check
GOAL: The public surface-set completeness check for a built KnowledgeMap --
      every declared surface whose path exists must have contributed at
      least one primary (provenance-based) node, and every node's surface
      label must be either a declared surface or one of the map's named
      synthetic surface labels.
BUSINESS CONTEXT: KM-KGS-100c-1's promise -- "every declared surface whose
    path exists contributes its nodes to the map ... and no surface is
    read that was not declared" -- was previously "proven" by an assertion
    that could never fail: contributing_surfaces was computed from node
    labels filtered to the declared set, so an undeclared label never
    entered it (KM-KGS-100c-1-ii), and a synthetic component-hub node
    sharing the "components" label could stand in for a real read from
    that surface's own path (KM-KGS-100c-1-i). check_surface_set() makes
    both clauses checkable: it reports a declared surface whose path
    exists but produced no primary node, and it reports any node carrying
    a surface label that is neither declared nor synthetic, naming both
    the offending label and node so the fault is traceable without a
    debugger.
ARCHITECTURE: Sibling module to knowledge_query.py, loaded the same way as
    knowledge_frontmatter_reader.py and knowledge_file_nodes.py via
    knowledge_query._load_sibling_module(), resolved relative to that
    file's own __file__ so the load works both from source (scripts/) and
    from a deployed consumer's .leafcutter/scripts/ with no scripts/
    directory on sys.path at all. Kept in its own file, rather than added
    to knowledge_query.py directly, so that file's own already-oversized
    content-line count (the GE-127b-1 check-file-size ratchet) never grows
    for this check. This module never imports knowledge_query (that would
    be circular, and knowledge_query.py can load this module with no
    scripts/ directory on sys.path at all) -- load_surfaces_with_meta is
    passed in by the caller instead, the same dependency-injection shape
    knowledge_file_nodes.resolve_file_path_edges() already uses for
    NodeRecord/EdgeRecord. SYNTHETIC_SURFACE_LABELS is the ONE named
    collection of surface labels the map creates that are never
    themselves declared, traversed surfaces: component hub nodes (label
    "components") and path-keyed file nodes (label "files",
    KM-KGS-100d-4). A new kind of synthetic node joins the set here, not
    via a conditional elsewhere (KM-KGS-100c-2's no-special-casing
    invariant). No surface name is hard-coded anywhere in this module.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

#: The map's one named collection of synthetic surface labels: surface
#: names a node may legitimately carry without being a declared, traversed
#: surface. See this module's ARCHITECTURE docstring.
SYNTHETIC_SURFACE_LABELS: frozenset[str] = frozenset({"components", "files"})

#: The shape of ``knowledge_query.load_surfaces_with_meta``, injected by the
#: caller rather than imported back (see ARCHITECTURE docstring above).
LoadSurfacesWithMeta = Callable[[Path, Path], dict[str, dict[str, Any]]]


def _not_contributing_failures(
    km: Any, surfaces_meta: dict[str, dict[str, Any]]
) -> list[str]:
    """Return one failure per declared surface with an existing, empty path.

    Args:
        km: A ``KnowledgeMap`` produced by ``build_knowledge_map()``.
        surfaces_meta: The ``load_surfaces_with_meta`` result for the same
            project/config the map was built from.

    Returns:
        One failure string per offending surface (KM-KGS-100c-1-i); empty
        when every declared surface with an existing path contributed at
        least one primary node.
    """
    failures: list[str] = []
    for surface in sorted(km.declared_surfaces):
        info = surfaces_meta.get(surface)
        if info is None:
            continue
        if info["path"].exists() and surface not in km.contributing_surfaces:
            failures.append(
                f"declared surface '{surface}' has an existing path but "
                "contributed no items"
            )
    return failures


def _stray_label_failures(km: Any) -> list[str]:
    """Return one failure per node whose surface is neither declared nor synthetic.

    Args:
        km: A ``KnowledgeMap`` produced by ``build_knowledge_map()``.

    Returns:
        One failure string per offending node (KM-KGS-100c-1-ii); empty
        when every node's surface is in ``km.declared_surfaces`` or
        ``SYNTHETIC_SURFACE_LABELS``.
    """
    allowed = km.declared_surfaces | SYNTHETIC_SURFACE_LABELS
    return [
        f"node '{node.id}' has surface label '{node.surface}', which is "
        "neither a declared surface nor a synthetic surface label"
        for node in km.nodes
        if node.surface not in allowed
    ]


def check_surface_set(
    km: Any,
    project_root: Path,
    paths_json: Path,
    load_surfaces_meta: LoadSurfacesWithMeta,
) -> list[str]:
    """Return every surface-set failure for a built KnowledgeMap.

    Both checks read only ``km.declared_surfaces`` -- never a fresh,
    widened read of *paths_json* -- so a restricted (``surface_filter``)
    map is judged against its own narrowed declared set (KM-KGS-100c-1-ii):

    1. A declared surface whose resolved path exists on disk but is absent
       from ``km.contributing_surfaces``. A non-optional surface whose path
       does not exist is never flagged this way -- existence gates the
       failure, not the surface's optional flag.
    2. Any node whose surface is neither a declared surface nor a member of
       ``SYNTHETIC_SURFACE_LABELS``.

    Args:
        km: A ``KnowledgeMap`` produced by ``build_knowledge_map()``.
        project_root: Absolute path to the project root directory.
        paths_json: Absolute path to the paths.json configuration file.
        load_surfaces_meta: ``knowledge_query.load_surfaces_with_meta``,
            injected by the caller so this module never imports back from
            knowledge_query (see ARCHITECTURE docstring).

    Returns:
        Human-readable failure strings; empty when *km* is fully accounted
        for.
    """
    surfaces_meta = load_surfaces_meta(project_root, paths_json)
    return _not_contributing_failures(km, surfaces_meta) + _stray_label_failures(km)


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-25 15:16 [python-coder]: Initial authoring. (#TICKETLESS reason=km-kgs-100c-1-surface-check)
  New sibling module implementing check_surface_set() and
  SYNTHETIC_SURFACE_LABELS for KM-KGS-100c-1/-i/-ii. Split out of
  knowledge_query.py (rather than added there) so that file's own
  content-line count never grows past its HEAD baseline under the
  check-file-size ratchet (GE-127b-1). Loaded via knowledge_query's
  existing _load_sibling_module() pattern; load_surfaces_with_meta is
  passed in explicitly (dependency injection) to avoid a circular import
  back into knowledge_query, mirroring knowledge_file_nodes.py's own
  NodeRecord/EdgeRecord injection.
====================================================================
"""
