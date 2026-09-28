"""
MODULE: test_km_kgs_100d_4_i
GOAL: TDD stubs for KM-KGS-100d-4-i -- a file path never lands on a node
      because a name matches, or because several items share it. The
      ambiguity rule: an index hit is unambiguous only if exactly one node
      was read from that canonical path AND no other node on the map, on
      any surface, carries that node's id.
BUSINESS CONTEXT: see docs/acceptance-criteria/knowledge-management/
    KM-KGS-100-knowledge-graph-surfaces/KM-KGS-100d-4-i.yaml. Reuses the
    shared temp-project builder in km_kgs_100d_4_shared, which reproduces
    the real surface traversal order (tickets before docs) so a
    surface-priority pick would fail this fixture, exactly as the
    coordinator's verified example states.

ASSUMED API NAMES: EdgeRecord.anchor (see test_km_kgs_100d_4.py); no new
    names introduced here beyond what KM-KGS-100d-4 already assumes.
"""
from __future__ import annotations

import sys
from pathlib import Path

from km_kgs_100d_4_shared import (
    build_ambiguity_fixture,
    run_cli_json,
    write_ac_yaml,
)

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from knowledge_query import build_knowledge_map, validate_edges_integrity  # noqa: E402


def _edges(km, *, source=None, edge_type=None):
    edges = list(km.edges)
    if source is not None:
        edges = [e for e in edges if e.source_id == source]
    if edge_type is not None:
        edges = [e for e in edges if e.edge_type == edge_type]
    return edges


def test_file_named_like_a_skill_does_not_land_on_the_skill(tmp_path):
    # covers: KM-KGS-100d-4-i
    # angle: criterion
    """A file no node was read from, whose stem equals a skill's id, must
    land on a files node -- never on that skill by name-based fallback."""
    project_root = build_ambiguity_fixture(tmp_path)
    km = build_knowledge_map(project_root, project_root / "config" / "paths.json")

    edges = _edges(km, source="KM-EX-030", edge_type="implemented_by")
    assert len(edges) == 1, edges
    assert edges[0].target_id == ".claude/commands/it-po.md"
    target_nodes = [n for n in km.nodes if n.id == ".claude/commands/it-po.md"]
    assert target_nodes and target_nodes[0].surface == "files"
    assert not any(e.target_id == "it-po" for e in edges), (
        "the edge must never land on skill node 'it-po' by stem match"
    )


def test_file_shared_by_many_registry_nodes_lands_on_files_node(tmp_path):
    # covers: KM-KGS-100d-4-i
    # angle: criterion
    """A registry file read by many nodes is ambiguous by source-path
    multiplicity; the edge lands on a files node, not on any agent node."""
    project_root = build_ambiguity_fixture(tmp_path)
    km = build_knowledge_map(project_root, project_root / "config" / "paths.json")

    edges = _edges(km, source="KM-EX-031", edge_type="implemented_by")
    assert len(edges) == 1, edges
    assert edges[0].target_id == "config/agent_registry.json"
    agent_ids = {n.id for n in km.nodes if n.surface == "agents"}
    assert edges[0].target_id not in agent_ids, (
        "the edge must not resolve to any agents-surface node id"
    )
    target_nodes = [n for n in km.nodes if n.id == "config/agent_registry.json"]
    assert target_nodes and target_nodes[0].surface == "files"


def test_file_of_a_ticket_whose_id_collides_lands_on_files_node(tmp_path):
    # covers: KM-KGS-100d-4-i
    # angle: criterion
    """A ticket's own path is ambiguous when its id is shared by a docs
    node; the edge lands on a files node, never on the shared id 'T-3'."""
    project_root = build_ambiguity_fixture(tmp_path)
    km = build_knowledge_map(project_root, project_root / "config" / "paths.json")

    # Both a ticket and a doc carry id "T-3" -- confirm the fixture actually
    # reproduces the collision before trusting the assertion below.
    t3_nodes = [n for n in km.nodes if n.id == "T-3"]
    assert len(t3_nodes) >= 2, (
        f"fixture must reproduce the T-3 id collision (ticket + doc); got {t3_nodes}"
    )

    edges = _edges(km, source="KM-EX-032", edge_type="implemented_by")
    assert len(edges) == 1, edges
    assert edges[0].target_id == "tickets/T-3.md", (
        f"expected target_id 'tickets/T-3.md' (files surface), not the "
        f"colliding id 'T-3'; got {edges[0].target_id!r}"
    )
    target_nodes = [n for n in km.nodes if n.id == "tickets/T-3.md"]
    assert target_nodes and target_nodes[0].surface == "files"


def test_none_of_the_three_ambiguous_edges_is_dropped(tmp_path):
    # covers: KM-KGS-100d-4-i
    # angle: failure
    """Ambiguity resolves to a files node -- it must never drop the edge,
    in the built map, the JSON export, or the integrity validation report."""
    project_root = build_ambiguity_fixture(tmp_path)
    paths_json = project_root / "config" / "paths.json"
    km = build_knowledge_map(project_root, paths_json)

    for source in ("KM-EX-030", "KM-EX-031", "KM-EX-032"):
        edges = _edges(km, source=source, edge_type="implemented_by")
        assert len(edges) == 1, f"{source} must have exactly one implemented_by edge; got {edges}"

    payload = run_cli_json(project_root)
    sources_in_payload = {
        e["source"] for e in payload["edges"] if e["type"] == "implemented_by"
    }
    for source in ("KM-EX-030", "KM-EX-031", "KM-EX-032"):
        assert source in sources_in_payload, f"{source}'s edge missing from JSON export"

    integrity = validate_edges_integrity(km, project_root, paths_json)
    dropped_sources = {e.source_id for e in integrity.dropped_edges}
    for source in ("KM-EX-030", "KM-EX-031", "KM-EX-032"):
        assert source not in dropped_sources, (
            f"{source}'s edge must not appear in validate_edges_integrity dropped_edges"
        )


def test_unambiguous_ticket_file_still_lands_on_ticket_node(tmp_path):
    # covers: KM-KGS-100d-4-i
    # angle: boundary
    """CONTROL: an unambiguous ticket path (one node read from it, id
    carried by no other node) must still land on the ticket node -- the
    ambiguity rule cannot be satisfied by always creating a files node."""
    project_root = build_ambiguity_fixture(tmp_path)
    acs_dir = project_root / "docs" / "acceptance-criteria" / "example-component"
    write_ac_yaml(acs_dir, "KM-EX-033", implemented_by=["tickets/T-4.md"])

    km = build_knowledge_map(project_root, project_root / "config" / "paths.json")
    edges = _edges(km, source="KM-EX-033", edge_type="implemented_by")
    assert len(edges) == 1, edges
    assert edges[0].target_id == "T-4", (
        f"an unambiguous ticket path must resolve to the ticket id 'T-4'; got {edges[0].target_id!r}"
    )
    assert not [n for n in km.nodes if n.id == "tickets/T-4.md"], (
        "no files-surface node 'tickets/T-4.md' may exist for an unambiguous ticket path"
    )


def test_case_and_suffix_variants_never_land_on_indexed_node(tmp_path):
    # covers: KM-KGS-100d-4-i
    # angle: boundary
    """No name-based fallback of any kind: case, suffix and basename
    variants of an indexed path never land on that indexed node."""
    project_root = build_ambiguity_fixture(tmp_path)
    acs_dir = project_root / "docs" / "acceptance-criteria" / "example-component"
    write_ac_yaml(acs_dir, "KM-EX-034", implemented_by=["Tickets/T-4.md"])
    write_ac_yaml(acs_dir, "KM-EX-035", implemented_by=["archive/tickets/T-4.md"])
    write_ac_yaml(acs_dir, "KM-EX-036", implemented_by=["T-4.md"])

    km = build_knowledge_map(project_root, project_root / "config" / "paths.json")
    for source, expected_target in (
        ("KM-EX-034", "Tickets/T-4.md"),
        ("KM-EX-035", "archive/tickets/T-4.md"),
        ("KM-EX-036", "T-4.md"),
    ):
        edges = _edges(km, source=source, edge_type="implemented_by")
        assert len(edges) == 1, f"{source}: {edges}"
        assert edges[0].target_id == expected_target, (
            f"{source}: expected target_id {expected_target!r}, got {edges[0].target_id!r}"
        )
        assert edges[0].target_id != "T-4", (
            f"{source} must never resolve to indexed node 'T-4' by case, "
            f"suffix or basename fallback"
        )


def test_real_repository_path_resolved_edges_avoid_shared_ids_and_shared_sources():
    # covers: KM-KGS-100d-4-i
    # angle: real_artifact
    """Real repository: every path-resolved edge (reached through the path
    index, not landing on the source node's own surface) avoids a shared id
    and a shared source path -- data-driven, not a list of known offenders."""
    repo_root = Path(__file__).resolve().parent.parent
    paths_json = repo_root / "config" / "paths.json"
    assert paths_json.is_file(), f"real config/paths.json not found at {paths_json}"

    from knowledge_query import load_surfaces_with_meta  # noqa: E402

    surfaces_meta = load_surfaces_with_meta(repo_root, paths_json)
    file_path_edge_types: set[str] = set()
    for info in surfaces_meta.values():
        file_path_edge_types.update(info.get("file_path_fields", []))
    assert file_path_edge_types, (
        "no surface declares any file_path_fields in the real config -- "
        "cannot evaluate the path-resolved arm"
    )

    km = build_knowledge_map(repo_root, paths_json)

    id_counts: dict[str, int] = {}
    source_path_counts: dict[str, int] = {}
    for node in km.nodes:
        id_counts[node.id] = id_counts.get(node.id, 0) + 1
        canonical_source = Path(node.path).as_posix()
        source_path_counts[canonical_source] = source_path_counts.get(canonical_source, 0) + 1

    node_by_id: dict[str, list] = {}
    for node in km.nodes:
        node_by_id.setdefault(node.id, []).append(node)

    path_resolved_edges = []
    for edge in km.edges:
        if edge.edge_type not in file_path_edge_types:
            continue
        targets = node_by_id.get(edge.target_id, [])
        if not targets:
            continue
        target_node = targets[0]
        source_nodes = [n for n in km.nodes if n.id == edge.source_id]
        source_surface = source_nodes[0].surface if source_nodes else None
        if target_node.surface == "files" or target_node.surface == source_surface:
            continue
        path_resolved_edges.append((edge, target_node))

    assert path_resolved_edges, (
        "expected at least one edge reached through the path index in the "
        "real repository"
    )
    for edge, target_node in path_resolved_edges:
        assert id_counts[target_node.id] == 1, (
            f"path-resolved edge {edge} landed on id {target_node.id!r}, "
            f"which is carried by {id_counts[target_node.id]} nodes map-wide"
        )
        canonical_source = Path(target_node.path).as_posix()
        assert source_path_counts[canonical_source] == 1, (
            f"path-resolved edge {edge} landed on a node whose source path "
            f"{canonical_source!r} is shared by {source_path_counts[canonical_source]} nodes"
        )
