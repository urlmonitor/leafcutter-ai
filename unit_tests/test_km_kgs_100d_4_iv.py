"""
MODULE: test_km_kgs_100d_4_iv
GOAL: TDD stubs for KM-KGS-100d-4-iv -- a map restricted to one surface
      still shows the files that surface's relationships name. The
      path-keyed index is scoped to the traversed surface(s) only, so a
      value naming another surface's file (e.g. a ticket path from an
      acs-restricted build) falls back to a files node instead of dangling.
BUSINESS CONTEXT: see docs/acceptance-criteria/knowledge-management/
    KM-KGS-100-knowledge-graph-surfaces/KM-KGS-100d-4-iv.yaml. The two
    test_spec entries that restate unit_tests/test_ac_edge_relationships.py
    (test_implemented_by_edge_ends_on_files_node_under_acs_restriction and
    test_covered_by_edge_ends_on_files_node_under_acs_restriction) live in
    THAT file, not here, per the AC's explicit file placement -- this
    module holds the other 7.

ASSUMED API NAMES (see test_km_kgs_100d_4.py for EdgeRecord.anchor and the
    files-surface node kind; additionally, this module assumes, per
    KM-KGS-100d-4-ii / -iii which this AC's boundary test cross-checks
    against a restricted build):
  - NodeRecord.missing: bool -- True when a files-surface node's canonical
    path does not exist on disk (KM-KGS-100d-4-ii).
  - KnowledgeMap.declined_count: int -- the number of relationship values
    declined as not-a-repo-path (KM-KGS-100d-4-iii), carried on the
    KnowledgeMap return value.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from km_kgs_100d_4_shared import (
    build_criteria_fixture,
    run_cli_json,
    write_ac_yaml,
)

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from knowledge_query import build_knowledge_map  # noqa: E402

_IMPLEMENTED_BY_FLOOR = 1500
_COVERED_BY_FLOOR = 4500


def _edges(km, *, source=None, edge_type=None):
    edges = list(km.edges)
    if source is not None:
        edges = [e for e in edges if e.source_id == source]
    if edge_type is not None:
        edges = [e for e in edges if e.edge_type == edge_type]
    return edges


def test_acs_restricted_map_holds_criteria_and_their_file_nodes_with_anchors(tmp_path):
    # covers: KM-KGS-100d-4-iv
    # angle: criterion
    """An acs-restricted build still resolves implemented_by/covered_by file
    targets to files nodes with their anchors, and keeps the child-AC id edge."""
    project_root = build_criteria_fixture(tmp_path)
    km = build_knowledge_map(project_root, project_root / "config" / "paths.json", surface_filter="acs")

    acs_ids = {n.id for n in km.nodes if n.surface == "acs"}
    assert {"KM-EX-010", "KM-EX-011", "KM-EX-011-i", "KM-EX-012"} <= acs_ids

    files_ids = {n.id for n in km.nodes if n.surface == "files"}
    assert {"scripts/foo.py", "unit_tests/test_foo.py"} <= files_ids

    impl_edges = _edges(km, source="KM-EX-010", edge_type="implemented_by")
    assert len(impl_edges) == 1 and impl_edges[0].target_id == "scripts/foo.py"
    assert impl_edges[0].anchor == "_check_limits"

    cov_edges = _edges(km, source="KM-EX-011", edge_type="covered_by")
    to_test_foo = [e for e in cov_edges if e.target_id == "unit_tests/test_foo.py"]
    assert len(to_test_foo) == 1 and to_test_foo[0].anchor == "test_limits"

    to_child = [e for e in cov_edges if e.target_id == "KM-EX-011-i"]
    assert len(to_child) == 1
    child_node = [n for n in km.nodes if n.id == "KM-EX-011-i"]
    assert child_node and child_node[0].surface == "acs"
    assert not [n for n in km.nodes if n.id == "KM-EX-011-i" and n.surface == "files"]


def test_ticket_path_is_a_files_node_when_restricted_and_the_ticket_node_when_not(tmp_path):
    # covers: KM-KGS-100d-4-iv
    # angle: boundary
    """Both sides pinned in one test: restricted index scope is a function
    of the included surface's own nodes alone."""
    project_root = build_criteria_fixture(tmp_path)
    paths_json = project_root / "config" / "paths.json"

    restricted = build_knowledge_map(project_root, paths_json, surface_filter="acs")
    restricted_edges = _edges(restricted, source="KM-EX-012", edge_type="implemented_by")
    assert len(restricted_edges) == 1
    assert restricted_edges[0].target_id == "tickets/T-1.md"
    restricted_target = [n for n in restricted.nodes if n.id == "tickets/T-1.md"]
    assert restricted_target and restricted_target[0].surface == "files"

    unrestricted = build_knowledge_map(project_root, paths_json)
    unrestricted_edges = _edges(unrestricted, source="KM-EX-012", edge_type="implemented_by")
    assert len(unrestricted_edges) == 1
    assert unrestricted_edges[0].target_id == "T-1"
    unrestricted_target = [n for n in unrestricted.nodes if n.id == "T-1"]
    assert unrestricted_target and unrestricted_target[0].surface == "tickets"
    assert not [n for n in unrestricted.nodes if n.id == "tickets/T-1.md"]


def test_acs_restricted_map_has_no_ticket_node_no_files_touched_edge_and_no_dangling_edge(tmp_path):
    # covers: KM-KGS-100d-4-iv
    # angle: criterion
    """Restricted to acs: no tickets node, no files_touched edge, and every
    edge endpoint is a node on the restricted map -- with more than 0
    implemented_by/covered_by edges, so zero-dangling isn't reached by
    dropping them."""
    project_root = build_criteria_fixture(tmp_path)
    km = build_knowledge_map(project_root, project_root / "config" / "paths.json", surface_filter="acs")

    assert not any(n.surface == "tickets" for n in km.nodes)
    assert not any(e.edge_type == "files_touched" for e in km.edges)

    node_ids = {n.id for n in km.nodes}
    dangling = [e for e in km.edges if e.source_id not in node_ids or e.target_id not in node_ids]
    assert not dangling, f"restricted map must have zero dangling edges; got {dangling}"

    assert len([e for e in km.edges if e.edge_type == "implemented_by"]) > 0
    assert len([e for e in km.edges if e.edge_type == "covered_by"]) > 0


def test_acs_restricted_json_export_lists_file_nodes_and_their_edges(tmp_path):
    # covers: KM-KGS-100d-4-iv
    # angle: reachability
    """The shipped CLI's --surface acs JSON export lists the files nodes
    and their edges; every edge endpoint in the payload is a payload node."""
    project_root = build_criteria_fixture(tmp_path)
    payload = run_cli_json(project_root, extra_args=["--surface", "acs"])

    node_ids = {n["id"] for n in payload["nodes"]}
    for expected in ("scripts/foo.py", "unit_tests/test_foo.py", "tickets/T-1.md"):
        assert expected in node_ids, f"expected {expected!r} in restricted export nodes"
        node = next(n for n in payload["nodes"] if n["id"] == expected)
        assert node["surface"] == "files"

    def _find_edge(source, target, edge_type):
        return [
            e for e in payload["edges"]
            if e["source"] == source and e["target"] == target and e["type"] == edge_type
        ]

    impl = _find_edge("KM-EX-010", "scripts/foo.py", "implemented_by")
    assert len(impl) == 1 and impl[0].get("anchor") == "_check_limits"
    cov = _find_edge("KM-EX-011", "unit_tests/test_foo.py", "covered_by")
    assert len(cov) == 1 and cov[0].get("anchor") == "test_limits"
    assert _find_edge("KM-EX-012", "tickets/T-1.md", "implemented_by")

    for edge in payload["edges"]:
        assert edge["source"] in node_ids, f"dangling source in restricted export: {edge}"
        assert edge["target"] in node_ids, f"dangling target in restricted export: {edge}"


def test_restriction_applies_the_same_resolution_rules_to_the_included_surface(tmp_path):
    # covers: KM-KGS-100d-4-iv
    # angle: boundary
    """Canonicalisation, the missing mark and the decline figure are equal
    across a restricted and an unrestricted build of the same fixture."""
    project_root = build_criteria_fixture(tmp_path)
    acs_dir = project_root / "docs" / "acceptance-criteria" / "example-component"
    write_ac_yaml(acs_dir, "KM-EX-016", implemented_by=["scripts/removed_tool.py"])
    outside_path = "D:\\OutsideProject\\scripts\\foo.py" if os.name == "nt" else "/opt/outside-project/scripts/foo.py"
    write_ac_yaml(acs_dir, "KM-EX-017", implemented_by=[outside_path])

    paths_json = project_root / "config" / "paths.json"
    restricted = build_knowledge_map(project_root, paths_json, surface_filter="acs")
    unrestricted = build_knowledge_map(project_root, paths_json)

    for km in (restricted, unrestricted):
        removed = [n for n in km.nodes if n.id == "scripts/removed_tool.py"]
        assert removed, f"'scripts/removed_tool.py' must be a node in both builds; nodes={[n.id for n in km.nodes]}"
        assert getattr(removed[0], "missing", None) is True, (
            "'scripts/removed_tool.py' must be marked missing (KM-KGS-100d-4-ii) in both builds"
        )
        assert not any(n.id == outside_path for n in km.nodes), (
            f"no node id may be the outside-project absolute path {outside_path!r}"
        )

    declined_restricted = getattr(restricted, "declined_count", None)
    declined_unrestricted = getattr(unrestricted, "declined_count", None)
    assert declined_restricted is not None and declined_unrestricted is not None, (
        "KnowledgeMap must carry a declined_count (KM-KGS-100d-4-iii) in both builds"
    )
    assert declined_restricted == declined_unrestricted, (
        f"declined_count must be equal across restricted ({declined_restricted}) and "
        f"unrestricted ({declined_unrestricted}) builds of the same fixture"
    )

    restricted_files_ids = {n.id for n in restricted.nodes if n.surface == "files"}
    unrestricted_files_ids = {n.id for n in unrestricted.nodes if n.surface == "files"}
    assert (restricted_files_ids - {"tickets/T-1.md"}) == unrestricted_files_ids, (
        f"restricted files ids minus the ticket fallback must equal the unrestricted "
        f"files ids; restricted={restricted_files_ids} unrestricted={unrestricted_files_ids}"
    )


def test_restriction_to_another_surface_resolves_its_own_file_path_fields_by_declaration(tmp_path):
    # covers: KM-KGS-100d-4-iv
    # angle: boundary
    """No surface-specific code path: a tickets restriction and a fictional
    'widgets' restriction both resolve their own declared file_path_fields."""
    project_root = build_criteria_fixture(tmp_path)
    paths_json = project_root / "config" / "paths.json"

    tickets_km = build_knowledge_map(project_root, paths_json, surface_filter="tickets")
    ft_edges = _edges(tickets_km, source="T-1", edge_type="files_touched")
    targets = {e.target_id for e in ft_edges}
    assert targets == {"scripts/foo.py", "unit_tests/test_foo.py"}, (
        f"T-1's files_touched edges (restricted to tickets) must end on the two "
        f"canonicalised files nodes; got {targets}"
    )
    assert not any(n.surface == "acs" for n in tickets_km.nodes)
    assert not any(e.edge_type in ("implemented_by", "covered_by") for e in tickets_km.edges)

    data = json.loads(paths_json.read_text(encoding="utf-8"))
    data["surfaces"]["widgets"] = {
        "path": "widgets/",
        "edge_fields": ["touches"],
        "file_path_fields": ["touches"],
        "_optional": True,
    }
    paths_json.write_text(json.dumps(data), encoding="utf-8")
    widgets_dir = project_root / "widgets"
    widgets_dir.mkdir(parents=True, exist_ok=True)
    (widgets_dir / "W-1.yaml").write_text(
        "id: W-1\ntitle: Widget one\ntouches:\n  - scripts/foo.py\n",
        encoding="utf-8",
    )

    widgets_km = build_knowledge_map(project_root, paths_json, surface_filter="widgets")
    widget_edges = _edges(widgets_km, source="W-1", edge_type="touches")
    assert len(widget_edges) == 1 and widget_edges[0].target_id == "scripts/foo.py"
    foo_node = [n for n in widgets_km.nodes if n.id == "scripts/foo.py"]
    assert foo_node and foo_node[0].surface == "files"


def test_real_repository_acs_restricted_map_has_file_nodes_and_no_dangling_edge():
    # covers: KM-KGS-100d-4-iv
    # angle: real_artifact
    """Real repository, acs-restricted: files nodes exist, no tickets node,
    zero dangling edges, and pinned implemented_by/covered_by floors hold."""
    repo_root = Path(__file__).resolve().parent.parent
    paths_json = repo_root / "config" / "paths.json"
    assert paths_json.is_file(), f"real config/paths.json not found at {paths_json}"

    km = build_knowledge_map(repo_root, paths_json, surface_filter="acs")
    assert km.declared_surfaces == frozenset({"acs"})

    files_nodes = [n for n in km.nodes if n.surface == "files"]
    assert len(files_nodes) > 0, f"expected > 0 files nodes; got {len(files_nodes)}"
    assert not any(n.surface == "tickets" for n in km.nodes)

    node_ids = {n.id for n in km.nodes}
    dangling = [e for e in km.edges if e.source_id not in node_ids or e.target_id not in node_ids]
    assert not dangling, f"{len(dangling)} dangling edge(s) in acs-restricted real map"

    implemented_by = [e for e in km.edges if e.edge_type == "implemented_by"]
    covered_by = [e for e in km.edges if e.edge_type == "covered_by"]
    assert len(implemented_by) >= _IMPLEMENTED_BY_FLOOR
    assert len(covered_by) >= _COVERED_BY_FLOOR

    ticket_prefixed = [n for n in files_nodes if n.id.startswith("tickets/")]
    assert ticket_prefixed, (
        f"expected at least one files-node id starting with 'tickets/' "
        f"(files-node count: {len(files_nodes)})"
    )
