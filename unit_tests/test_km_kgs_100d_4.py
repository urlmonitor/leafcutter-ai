"""
MODULE: test_km_kgs_100d_4
GOAL: TDD stubs for KM-KGS-100d-4 -- every relationship that names the same
      file lands on one node keyed by that file's path, instead of surviving
      only as a raw-string leaf exempt from the phantom-edge filter.
BUSINESS CONTEXT: see docs/acceptance-criteria/knowledge-management/
    KM-KGS-100-knowledge-graph-surfaces/KM-KGS-100d-4.yaml. Fixture tests
    live here; the whole-repository arm lives in the sibling module
    test_km_kgs_100d_4_real.py (about 5s to build). Both reuse
    km_kgs_100d_4_shared for the temp-project builder and CLI runner so a
    hand-built surface map can never substitute for the real
    config/paths.json declarations.

ASSUMED API NAMES (not yet implemented; named here per the "unknown API"
    rule so the coder implements exactly these):
  - EdgeRecord.anchor: str | None -- the text after a stripped '#symbol' or
    '::test' suffix, carried as an edge attribute.
  - NodeRecord.surface == "files" for the new path-keyed synthetic node
    kind; NodeRecord.id is the canonical repo-relative POSIX path.
  - JSON export: each edge object gains an "anchor" key (string or null);
    node objects on the files surface behave like any other node object
    (id/surface/title/description/path).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from km_kgs_100d_4_shared import (
    REAL_PATHS_JSON,
    build_criteria_fixture,
    run_cli_json,
    write_ac_yaml,
)

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from knowledge_query import build_knowledge_map  # noqa: E402
from knowledge_file_nodes import _split_absolute  # noqa: E402


def _edges(km, *, source=None, edge_type=None, target=None):
    edges = list(km.edges)
    if source is not None:
        edges = [e for e in edges if e.source_id == source]
    if edge_type is not None:
        edges = [e for e in edges if e.edge_type == edge_type]
    if target is not None:
        edges = [e for e in edges if e.target_id == target]
    return edges


def _node(km, node_id):
    matches = [n for n in km.nodes if n.id == node_id]
    return matches


def test_one_files_node_per_distinct_canonical_path(tmp_path):
    # covers: KM-KGS-100d-4
    # angle: criterion
    """Exactly one files-surface node per distinct canonical path; only
    referenced files become nodes, and every three convergent spellings
    (./ + #anchor, ::test, backslash) canonicalise cleanly."""
    project_root = build_criteria_fixture(tmp_path)
    km = build_knowledge_map(project_root, project_root / "config" / "paths.json")

    foo_nodes = [n for n in km.nodes if n.id == "scripts/foo.py"]
    test_foo_nodes = [n for n in km.nodes if n.id == "unit_tests/test_foo.py"]
    assert len(foo_nodes) == 1, (
        f"expected exactly one node id 'scripts/foo.py'; got {foo_nodes}"
    )
    assert foo_nodes[0].surface == "files"
    assert len(test_foo_nodes) == 1, (
        f"expected exactly one node id 'unit_tests/test_foo.py'; got {test_foo_nodes}"
    )
    assert test_foo_nodes[0].surface == "files"

    for node in km.nodes:
        assert "\\" not in node.id, f"node id must never carry a backslash: {node.id!r}"
        assert not node.id.startswith("./"), f"node id must never carry a leading './': {node.id!r}"
        assert "#" not in node.id, f"node id must never carry a stripped anchor: {node.id!r}"
        assert "::" not in node.id, f"node id must never carry a stripped test suffix: {node.id!r}"

    assert not _node(km, "scripts/unreferenced.py"), (
        "an unreferenced file must never become a node -- only referenced "
        "files become nodes"
    )


def test_implemented_by_and_files_touched_end_on_same_file_node_with_anchor(tmp_path):
    # covers: KM-KGS-100d-4
    # angle: criterion
    """implemented_by (with anchor) and files_touched converge on one node."""
    project_root = build_criteria_fixture(tmp_path)
    km = build_knowledge_map(project_root, project_root / "config" / "paths.json")

    impl_edges = _edges(km, source="KM-EX-010", edge_type="implemented_by")
    assert len(impl_edges) == 1, impl_edges
    assert impl_edges[0].target_id == "scripts/foo.py"
    assert impl_edges[0].anchor == "_check_limits", (
        "the KM-EX-010 implemented_by edge must carry anchor '_check_limits'"
    )

    ft_edges = _edges(km, source="T-1", edge_type="files_touched", target="scripts/foo.py")
    assert len(ft_edges) == 1, ft_edges
    assert ft_edges[0].anchor is None, "T-1's files_touched edge carries no anchor"


def test_covered_by_and_backslash_files_touched_end_on_same_test_file_node(tmp_path):
    # covers: KM-KGS-100d-4
    # angle: criterion
    """covered_by (with anchor) and the backslash-spelled files_touched converge."""
    project_root = build_criteria_fixture(tmp_path)
    km = build_knowledge_map(project_root, project_root / "config" / "paths.json")

    cov_edges = _edges(km, source="KM-EX-011", edge_type="covered_by", target="unit_tests/test_foo.py")
    assert len(cov_edges) == 1, cov_edges
    assert cov_edges[0].anchor == "test_limits"

    ft_edges = _edges(km, source="T-1", edge_type="files_touched", target="unit_tests/test_foo.py")
    assert len(ft_edges) == 1, (
        "the backslash-separated files_touched value 'unit_tests\\test_foo.py' "
        f"must canonicalise onto the same node as the covered_by edge; edges={ft_edges}"
    )


def test_implemented_by_naming_a_ticket_file_ends_on_the_ticket_node(tmp_path):
    # covers: KM-KGS-100d-4
    # angle: criterion
    """A value naming a ticket's own path resolves to the ticket node, not a
    files node -- index-first resolution beats synthetic-node creation."""
    project_root = build_criteria_fixture(tmp_path)
    km = build_knowledge_map(project_root, project_root / "config" / "paths.json")

    edges = _edges(km, source="KM-EX-012", edge_type="implemented_by")
    assert len(edges) == 1, edges
    assert edges[0].target_id == "T-1", (
        f"expected KM-EX-012's implemented_by edge to end on ticket id 'T-1', got {edges[0].target_id!r}"
    )
    target_nodes = _node(km, "T-1")
    assert target_nodes and target_nodes[0].surface == "tickets"
    assert not _node(km, "tickets/T-1.md"), (
        "no files-surface node may be created for a ticket's own referenced path"
    )


def test_covered_by_child_ac_id_still_ends_on_criterion_node(tmp_path):
    # covers: KM-KGS-100d-4
    # angle: boundary
    """A non-path-shaped covered_by value (a child AC id) keeps id resolution."""
    project_root = build_criteria_fixture(tmp_path)
    km = build_knowledge_map(project_root, project_root / "config" / "paths.json")

    edges = _edges(km, source="KM-EX-011", edge_type="covered_by", target="KM-EX-011-i")
    assert len(edges) == 1, edges
    target_nodes = [n for n in km.nodes if n.id == "KM-EX-011-i" and n.surface == "acs"]
    assert target_nodes, "KM-EX-011-i must exist as a node on the acs surface"
    assert not [n for n in km.nodes if n.id == "KM-EX-011-i" and n.surface == "files"], (
        "a non-path-shaped covered_by value must never create a files-surface node"
    )


def test_json_export_answers_which_criteria_and_tickets_touched_a_file(tmp_path):
    # covers: KM-KGS-100d-4
    # angle: reachability
    """The shipped CLI's JSON export answers 'which criteria/tickets touched
    this file' by following edges alone, with no disk read in the assertion."""
    project_root = build_criteria_fixture(tmp_path)
    payload = run_cli_json(project_root)

    node_by_id = {n["id"]: n for n in payload["nodes"]}
    assert node_by_id.get("scripts/foo.py", {}).get("surface") == "files"

    edges_to_foo = [e for e in payload["edges"] if e["target"] == "scripts/foo.py"]
    sources = {e["source"] for e in edges_to_foo}
    assert sources == {"KM-EX-010", "T-1"}, (
        f"expected exactly {{'KM-EX-010', 'T-1'}} as sources of edges into "
        f"scripts/foo.py; got {sources}"
    )
    km_ex_010_edge = next(e for e in edges_to_foo if e["source"] == "KM-EX-010")
    assert km_ex_010_edge.get("anchor") == "_check_limits"


def test_absolute_path_inside_project_root_resolves_to_repo_relative_node(tmp_path):
    # covers: KM-KGS-100d-4
    # angle: boundary
    """An absolute path inside the project root canonicalises to repo-relative."""
    project_root = build_criteria_fixture(tmp_path)
    absolute_value = str(project_root / "scripts" / "foo.py")
    acs_dir = project_root / "docs" / "acceptance-criteria" / "example-component"
    write_ac_yaml(acs_dir, "KM-EX-013", implemented_by=[absolute_value])

    km = build_knowledge_map(project_root, project_root / "config" / "paths.json")
    edges = _edges(km, source="KM-EX-013", edge_type="implemented_by")
    assert len(edges) == 1, edges
    assert edges[0].target_id == "scripts/foo.py", (
        f"absolute path {absolute_value!r} must canonicalise to 'scripts/foo.py'; "
        f"got {edges[0].target_id!r}"
    )
    assert not any(n.id == absolute_value for n in km.nodes), (
        "no node id may be an absolute path"
    )


def test_paths_differing_only_in_case_stay_distinct_nodes(tmp_path):
    # covers: KM-KGS-100d-4
    # angle: boundary
    """No case-folding: 'scripts/foo.py' and 'Scripts/Foo.py' stay distinct."""
    project_root = build_criteria_fixture(tmp_path)
    acs_dir = project_root / "docs" / "acceptance-criteria" / "example-component"
    write_ac_yaml(acs_dir, "KM-EX-014", implemented_by=["scripts/foo.py"])
    write_ac_yaml(acs_dir, "KM-EX-015", implemented_by=["Scripts/Foo.py"])

    km = build_knowledge_map(project_root, project_root / "config" / "paths.json")
    files_ids = {n.id for n in km.nodes if n.surface == "files"}
    assert "scripts/foo.py" in files_ids
    assert "Scripts/Foo.py" in files_ids, (
        "a differently-cased path must create its OWN distinct files node, "
        f"not fold onto 'scripts/foo.py'; files node ids={files_ids}"
    )


def test_file_path_resolution_follows_each_surfaces_own_declaration(tmp_path):
    # covers: KM-KGS-100d-4
    # angle: boundary
    """Resolution is per-surface and declaration-driven -- proven with two
    surfaces no production code can know by name: 'widgets' declares
    'touches' as a file_path_field and gets resolution; 'gadgets' declares
    'covered_by' as a plain edge field (not a file_path_field) and gets
    none, even though 'covered_by' is globally exempt via the acs surface
    today. This is exactly the global-vs-per-surface distinction
    KM-KGS-100d-4 changes."""
    project_root = build_criteria_fixture(tmp_path)
    paths_json = project_root / "config" / "paths.json"
    data = json.loads(paths_json.read_text(encoding="utf-8"))
    data["surfaces"]["widgets"] = {
        "path": "widgets/",
        "edge_fields": ["touches"],
        "file_path_fields": ["touches"],
        "_optional": True,
    }
    data["surfaces"]["gadgets"] = {
        "path": "gadgets/",
        "edge_fields": ["covered_by"],
        "_optional": True,
    }
    paths_json.write_text(json.dumps(data), encoding="utf-8")

    widgets_dir = project_root / "widgets"
    widgets_dir.mkdir(parents=True, exist_ok=True)
    (widgets_dir / "W-1.yaml").write_text(
        "id: W-1\ntitle: Widget one\ntouches:\n  - scripts/foo.py\n",
        encoding="utf-8",
    )
    gadgets_dir = project_root / "gadgets"
    gadgets_dir.mkdir(parents=True, exist_ok=True)
    (gadgets_dir / "G-1.yaml").write_text(
        "id: G-1\ntitle: Gadget one\ncovered_by:\n  - unit_tests/only_here.py\n",
        encoding="utf-8",
    )

    km = build_knowledge_map(project_root, paths_json)

    widget_edges = _edges(km, source="W-1", edge_type="touches")
    assert len(widget_edges) == 1, widget_edges
    assert widget_edges[0].target_id == "scripts/foo.py"
    foo_node = _node(km, "scripts/foo.py")
    assert foo_node and foo_node[0].surface == "files"

    gadget_edges = _edges(km, source="G-1", edge_type="covered_by")
    assert not gadget_edges, (
        "gadgets does not declare 'covered_by' in its OWN file_path_fields, "
        f"so no edge from G-1 may survive; got {gadget_edges}"
    )
    assert not _node(km, "unit_tests/only_here.py"), (
        "no files node may be created for a field a surface did not declare "
        "as a file_path_field"
    )


def test_real_config_declares_every_file_path_field():
    # covers: KM-KGS-100d-4
    # angle: criterion
    """The real config/paths.json declares implemented_by/covered_by (acs)
    and files_touched (tickets) as file_path_fields; this record depends on
    the tickets declaration and must not re-author it (KM-KGS-100c-4)."""
    data = json.loads(REAL_PATHS_JSON.read_text(encoding="utf-8"))
    acs_fpf = data["surfaces"]["acs"].get("file_path_fields", [])
    assert "implemented_by" in acs_fpf and "covered_by" in acs_fpf, (
        f"acs surface must declare implemented_by and covered_by in "
        f"file_path_fields; got {acs_fpf!r}"
    )
    tickets_fpf = data["surfaces"]["tickets"].get("file_path_fields", [])
    assert "files_touched" in tickets_fpf, (
        "KM-KGS-100c-4 -- tickets surface must declare files_touched in "
        f"file_path_fields; got {tickets_fpf!r}"
    )


def test_drive_letter_case_mismatch_resolves_to_repo_relative_node():
    # covers: KM-KGS-100d-4
    # angle: boundary
    """pr-reviewer regression: _split_absolute's in-project check
    (`value.startswith(prefix)`, knowledge_file_nodes.py:168) is
    case-sensitive, but Windows drive letters are not -- project_root
    resolves to an uppercase drive while a value may spell it lowercase.
    Deterministic on any OS: a synthetic project_root_posix is constructed
    directly (no dependency on the host's own drive-letter case), so this
    is red on Windows AND Linux/macOS test hosts alike. The repo-relative
    TAIL must stay case-sensitive (no case-folding elsewhere)."""
    project_root_posix = "C:/Users/hendrik/project"

    flipped_drive = "c:/Users/hendrik/project/scripts/foo.py"
    canon, is_foreign = _split_absolute(flipped_drive, project_root_posix)
    assert not is_foreign, (
        f"a drive-letter case mismatch must not be treated as foreign; "
        f"got is_foreign=True for {flipped_drive!r} against root {project_root_posix!r}"
    )
    assert canon == "scripts/foo.py", (
        f"expected the in-project tail 'scripts/foo.py'; got {canon!r}"
    )

    tail_case_value = "C:/Users/hendrik/project/Scripts/Foo.py"
    tail_canon, tail_is_foreign = _split_absolute(tail_case_value, project_root_posix)
    assert not tail_is_foreign
    assert tail_canon == "Scripts/Foo.py", (
        f"the repo-relative tail must never be case-folded; got {tail_canon!r}"
    )
    assert tail_canon != canon, (
        "a differently-cased tail must stay a DIFFERENT canonical value "
        "(no case-folding), even though the drive letter itself is not case-sensitive"
    )


def test_drive_letter_case_mismatch_resolves_via_real_builder(tmp_path):
    # covers: KM-KGS-100d-4
    # angle: boundary
    """Integration-level confirmation through the real project root, a byte
    copy of the real config/paths.json, and the public build_knowledge_map.
    Genuinely exercises the reported defect when the host OS provides a real
    drive letter (Windows); the deterministic, host-independent proof of the
    SAME defect is test_drive_letter_case_mismatch_resolves_to_repo_relative_node
    above, which never depends on what this host happens to be."""
    project_root = build_criteria_fixture(tmp_path)
    absolute_value = str(project_root / "scripts" / "foo.py")
    if os.name == "nt" and len(absolute_value) > 1 and absolute_value[1] == ":":
        absolute_value = absolute_value[0].swapcase() + absolute_value[1:]
    acs_dir = project_root / "docs" / "acceptance-criteria" / "example-component"
    write_ac_yaml(acs_dir, "KM-EX-018", implemented_by=[absolute_value])

    km = build_knowledge_map(project_root, project_root / "config" / "paths.json")
    edges = _edges(km, source="KM-EX-018", edge_type="implemented_by")
    assert len(edges) == 1, edges
    assert edges[0].target_id == "scripts/foo.py", (
        f"an absolute in-project value must resolve to 'scripts/foo.py' "
        f"regardless of drive-letter case; got {edges[0].target_id!r} "
        f"(os.name={os.name!r}, value used={absolute_value!r})"
    )
