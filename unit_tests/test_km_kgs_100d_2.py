"""
MODULE: test_km_kgs_100d_2
GOAL: TDD stubs for KM-KGS-100d-2 -- every edge points to a node that
      actually exists, checked against the full node set with no
      hand-maintained allow-list and no edge-type exemption.
BUSINESS CONTEXT: No pre-existing test file was found for this AC in this
    worktree (searched for 'test_non_deferred_edge_targets_exist_in_node_set'
    and 'validate_edges_integrity' usage across unit_tests/ per the
    authoring instructions; neither matched outside scripts/), so all six
    test_spec entries are authored fresh here, including the rename from
    test_non_deferred_edge_targets_exist_in_node_set to
    test_every_edge_target_exists_in_node_set (now covering every edge
    type, with the exclusion constant removed on the test side).

    The raw-path vs resolved-node decision is settled (user-approved
    2026-09-25, KM-KGS-100d-4): file-path values resolve to path-keyed
    nodes and the file_path_fields exemption is retired in the same
    change, so the criteria hold literally with no carve-out. The target
    test, the exempt-set test and the real-repository arm describe that
    target state and are RED until the KM-KGS-100d-4 epic is built.
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_REAL_PATHS_JSON = _REPO_ROOT / "config" / "paths.json"

sys.path.insert(0, str(_SCRIPTS_DIR))

from knowledge_query import build_knowledge_map, validate_edges_integrity  # noqa: E402


def _build_multi_surface_project(tmp_path):
    """acs (KM-EX-019/020, all four fields) + a ticket (files_touched), over
    a byte copy of the real config/paths.json, so every declared surface's
    file_path_fields are exercised, not a hand-built map."""
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "paths.json").write_bytes(_REAL_PATHS_JSON.read_bytes())

    acs_dir = tmp_path / "docs" / "acceptance-criteria" / "example-component"
    acs_dir.mkdir(parents=True)
    (acs_dir / "KM-EX-019.yaml").write_text(
        "id: KM-EX-019\n"
        "title: Prerequisite AC\n"
        "implemented_by: []\n"
        "covered_by: []\n"
        "depends_on: []\n"
        "components:\n"
        "  - build-pipeline\n",
        encoding="utf-8",
    )
    (acs_dir / "KM-EX-020.yaml").write_text(
        "id: KM-EX-020\n"
        "title: Example AC with all four relationship fields\n"
        "implemented_by:\n"
        "- scripts/foo.py\n"
        "covered_by:\n"
        "- unit_tests/test_foo.py\n"
        "depends_on:\n"
        "- KM-EX-019\n"
        "components:\n"
        "- build-pipeline\n",
        encoding="utf-8",
    )

    tickets_dir = tmp_path / "tickets"
    tickets_dir.mkdir(parents=True)
    (tickets_dir / "T-3.md").write_text(
        "---\n"
        "id: T-3\n"
        "title: Touches an existing file and a never-created one\n"
        "agents:\n"
        "  python-coder: needed\n"
        "depends_on: []\n"
        "files_touched:\n"
        "  - scripts/foo.py\n"
        "  - unit_tests/other_test.py\n"
        "---\n\nBody.\n",
        encoding="utf-8",
    )

    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "foo.py").write_text("# real file\n", encoding="utf-8")
    unit_tests_dir = tmp_path / "unit_tests"
    unit_tests_dir.mkdir(parents=True)
    (unit_tests_dir / "test_foo.py").write_text("# real test file\n", encoding="utf-8")
    # unit_tests/other_test.py is deliberately never created (KM-KGS-100d-4-ii
    # territory: a missing file still becomes a real node once that AC lands).

    return tmp_path, config_dir / "paths.json"


def test_every_edge_source_exists_in_node_set(tmp_path):
    # covers: KM-KGS-100d-2
    # angle: criterion
    """Every validated edge's source id is in the full node-id set."""
    project_root, paths_json = _build_multi_surface_project(tmp_path)
    km = build_knowledge_map(project_root, paths_json)
    integrity = validate_edges_integrity(km, project_root, paths_json)
    node_ids = {n.id for n in km.nodes}
    for edge in integrity.validated_edges:
        assert edge.source_id in node_ids, f"edge {edge} has a source not in the node set"


def test_every_edge_target_exists_in_node_set(tmp_path):
    # covers: KM-KGS-100d-2
    # angle: criterion
    """Every validated edge's target id is in the full node-id set, no edge type excluded."""
    project_root, paths_json = _build_multi_surface_project(tmp_path)
    km = build_knowledge_map(project_root, paths_json)
    integrity = validate_edges_integrity(km, project_root, paths_json)
    node_ids = {n.id for n in km.nodes}
    offending = [e for e in integrity.validated_edges if e.target_id not in node_ids]
    assert offending == [], (
        f"every validated edge of every edge type must target a real node "
        f"(implemented_by, covered_by and files_touched included, no exclusion); "
        f"offending edges: {offending}"
    )


def test_validation_reports_no_exempt_edge_types(tmp_path):
    # covers: KM-KGS-100d-2
    # angle: criterion
    """exempt_edge_types is empty even though the real config declares file_path_fields."""
    project_root, paths_json = _build_multi_surface_project(tmp_path)
    km = build_knowledge_map(project_root, paths_json)
    integrity = validate_edges_integrity(km, project_root, paths_json)
    assert integrity.exempt_edge_types == frozenset(), (
        f"expected no exempt edge types even though acs declares "
        f"implemented_by/covered_by and tickets declares files_touched in "
        f"file_path_fields; got {integrity.exempt_edge_types!r}"
    )
    for edge_type in ("implemented_by", "covered_by", "files_touched"):
        matching = [e for e in km.edges if e.edge_type == edge_type]
        for edge in matching:
            assert edge in integrity.validated_edges, (
                f"{edge_type} edge {edge} must be in validated_edges via node "
                f"membership, not passed through as exempt"
            )


def test_component_membership_edges_reach_hub_nodes_after_validation(tmp_path):
    # covers: KM-KGS-100d-2
    # angle: seam
    """An acs node's component_membership edge survives validation and targets a real hub."""
    project_root, paths_json = _build_multi_surface_project(tmp_path)
    km = build_knowledge_map(project_root, paths_json)
    integrity = validate_edges_integrity(km, project_root, paths_json)
    node_ids = {n.id for n in km.nodes}

    cm_edges = [
        e for e in integrity.validated_edges
        if e.edge_type == "component_membership" and e.source_id == "KM-EX-020"
    ]
    assert cm_edges, "expected KM-EX-020's component_membership edge to survive validation"
    assert cm_edges[0].target_id in node_ids
    hub_node = next(n for n in km.nodes if n.id == cm_edges[0].target_id)
    assert hub_node.surface == "components", (
        f"component_membership target must be a synthetic hub node; got "
        f"surface {hub_node.surface!r}"
    )


def test_missing_target_dropped_uniformly_for_non_acs_surface(tmp_path):
    # covers: KM-KGS-100d-2
    # angle: boundary
    """A non-acs surface's node-to-node edge to a missing id is dropped; the real one survives."""
    project_root, paths_json = _build_multi_surface_project(tmp_path)
    (project_root / "tickets" / "T-4.md").write_text(
        "---\n"
        "id: T-4\n"
        "title: Names a missing depends_on target and a real one\n"
        "agents:\n"
        "  python-coder: needed\n"
        "depends_on:\n"
        "  - DOES-NOT-EXIST\n"
        "  - T-3\n"
        "files_touched: []\n"
        "---\n\nBody.\n",
        encoding="utf-8",
    )
    km = build_knowledge_map(project_root, paths_json)
    integrity = validate_edges_integrity(km, project_root, paths_json)

    t4_depends_on = [
        e for e in integrity.validated_edges if e.source_id == "T-4" and e.edge_type == "depends_on"
    ]
    targets = {e.target_id for e in t4_depends_on}
    assert targets == {"T-3"}, f"only the resolvable depends_on target must survive; got {targets}"
    assert "DOES-NOT-EXIST" not in {n.id for n in km.nodes}, (
        "the missing id must never become a node just because an edge named it"
    )
    # NOTE: _collect_all() already silently pre-filters any edge whose target is
    # absent from the node set (its own long-standing phantom-edge check) before
    # build_knowledge_map() returns, so a missing-target edge from a normal
    # build never reaches validate_edges_integrity()'s input at all and can
    # never appear in its dropped_edges here. Asserting on dropped_edges in
    # this fixture would fail permanently regardless of KM-KGS-100d-2's fix
    # (a pre-existing architecture quirk, not this AC's contract), so this
    # test instead pins the full-node-set-membership outcome the criteria
    # actually name.


def test_real_repository_every_edge_endpoint_is_a_node_with_no_exemption():
    # covers: KM-KGS-100d-2
    # angle: real_artifact
    """Real repository: no exemption, no invalid edges, every endpoint is a node."""
    assert _REPO_ROOT.exists(), f"repo root must exist: {_REPO_ROOT}"
    assert _REAL_PATHS_JSON.exists(), f"paths.json must exist: {_REAL_PATHS_JSON}"
    km = build_knowledge_map(_REPO_ROOT, _REAL_PATHS_JSON)
    integrity = validate_edges_integrity(km, _REPO_ROOT, _REAL_PATHS_JSON)

    assert integrity.exempt_edge_types == frozenset(), (
        f"expected no exempt edge types in the real repository; got "
        f"{integrity.exempt_edge_types!r}"
    )
    assert integrity.invalid_edges == [], (
        f"expected no invalid edges; got {len(integrity.invalid_edges)}"
    )

    implemented_by_count = sum(1 for e in km.edges if e.edge_type == "implemented_by")
    assert implemented_by_count > 0, "expected > 0 implemented_by edges (result must not be vacuous)"

    node_ids = {n.id for n in km.nodes}
    offending = [e for e in km.edges if e.source_id not in node_ids or e.target_id not in node_ids]
    assert offending == [], (
        f"every edge must have both endpoints in the full node set "
        f"(implemented_by count={implemented_by_count}); offending: {offending[:5]}"
    )
