"""
MODULE: test_km_kgs_100a_3
GOAL: TDD stubs for KM-KGS-100a-3 — an acceptance criterion's four
      relationship fields each become a distinct edge.
BUSINESS CONTEXT: This is the L2 composite over KM-KGS-100a-3-i..-viii.
    Tests 3-5 stay at edge-production level: real file -> real reader
    (_parse_yaml_file) -> real edge extractor (extract_edges), asserting
    candidate-edge type/source/count-and-quote-freedom per field (before
    target-existence validation), plus a reachability test that runs the
    real knowledge_query CLI end-to-end and proves the produced edge types
    are exactly those declared in paths.json's edge_fields for the acs
    surface, with no acs-specific code branch.

    Tests 1-2 (implemented_by, covered_by) were tightened 2026-09-25
    (user-approved decision, KM-KGS-100d-4): the target-form question is
    now decided — "the node for scripts/foo.py" is the files-surface node
    whose id is the canonical repo-relative path, resolved through a real
    config/paths.json and the public build_knowledge_map(), never a
    hand-built edges dict. They assert four things: the target equals the
    canonical path, that id is a files node in the node set, the edge
    survives validate_edges_integrity() with no exempt edge type, and an
    #symbol/::test anchor is kept on the edge (built map and JSON export).
    A sibling AC, KM-EX-013, carries the anchored spellings so KM-EX-010
    stays exactly as the Gherkin criteria write it. Both tests are RED
    until the KM-KGS-100d-4 epic is built (no 'files' surface, no
    'missing'/'anchor' fields, and exempt_edge_types is not yet empty).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_REAL_PATHS_JSON = _REPO_ROOT / "config" / "paths.json"
_KNOWLEDGE_QUERY_SCRIPT = _SCRIPTS_DIR / "knowledge_query.py"
sys.path.insert(0, str(_SCRIPTS_DIR))

from knowledge_query import (  # noqa: E402
    _parse_yaml_file,
    build_knowledge_map,
    extract_edges,
    validate_edges_integrity,
)

# The AC file is written in the column-zero / quoted forms the store actually
# uses (see KM-KGS-100a-3-i and -iii), so this seam test's failures are the
# same underlying reader defects those L3 criteria pin, observed here through
# the composed read -> extract_edges seam rather than the reader alone.
_KM_EX_010_YAML = (
    "id: KM-EX-010\n"
    "title: Example AC for edge relationship test\n"
    "implemented_by:\n"
    "- scripts/foo.py\n"
    "covered_by:\n"
    '  - "unit_tests/test_foo.py"\n'
    "depends_on:\n"
    "  - KM-EX-009\n"
    "components:\n"
    "  - build-pipeline\n"
)

_KM_EX_009_YAML = (
    "id: KM-EX-009\n"
    "title: Prerequisite AC\n"
    "implemented_by: []\n"
    "covered_by: []\n"
    "depends_on: []\n"
    "components:\n"
    "  - build-pipeline\n"
)

_ACS_EDGE_FIELDS = ["implemented_by", "covered_by", "depends_on", "components"]


def _read_km_ex_010(tmp_path):
    p = tmp_path / "KM-EX-010.yaml"
    p.write_text(_KM_EX_010_YAML, encoding="utf-8")
    fields = _parse_yaml_file(p.read_text(encoding="utf-8"))
    from knowledge_query import NodeRecord

    node = NodeRecord(
        id="KM-EX-010",
        surface="acs",
        title="Example AC for edge relationship test",
        description="",
        path=p,
    )
    return node, fields


# KM-EX-013: the sibling AC carrying the anchored spellings (IT-PO-specified),
# so KM-EX-010 above stays exactly as the Gherkin criteria write it.
_KM_EX_013_YAML = (
    "id: KM-EX-013\n"
    "title: Sibling AC carrying anchored spellings\n"
    "implemented_by:\n"
    "- ./scripts/foo.py#_check_limits\n"
    "covered_by:\n"
    "- unit_tests/test_foo.py::test_limits\n"
    "depends_on: []\n"
    "components:\n"
    "  - build-pipeline\n"
)


def _build_ac_relationships_project(tmp_path):
    """Real config/paths.json + KM-EX-009/010/013 + the real files they name."""
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "paths.json").write_bytes(_REAL_PATHS_JSON.read_bytes())

    acs_dir = tmp_path / "docs" / "acceptance-criteria" / "example-component"
    acs_dir.mkdir(parents=True)
    (acs_dir / "KM-EX-009.yaml").write_text(_KM_EX_009_YAML, encoding="utf-8")
    (acs_dir / "KM-EX-010.yaml").write_text(_KM_EX_010_YAML, encoding="utf-8")
    (acs_dir / "KM-EX-013.yaml").write_text(_KM_EX_013_YAML, encoding="utf-8")

    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "foo.py").write_text("# real file\n", encoding="utf-8")

    unit_tests_dir = tmp_path / "unit_tests"
    unit_tests_dir.mkdir(parents=True)
    (unit_tests_dir / "test_foo.py").write_text("# real test file\n", encoding="utf-8")

    return tmp_path, config_dir / "paths.json"


def _run_cli_json(project_root):
    result = subprocess.run(
        [
            sys.executable,
            str(_KNOWLEDGE_QUERY_SCRIPT),
            "--format",
            "json",
            "--project-root",
            str(project_root),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert result.returncode == 0, f"CLI must exit 0; stderr: {result.stderr}"
    return json.loads(result.stdout)


def test_acs_file_implemented_by_yields_implemented_by_edges(tmp_path):
    # covers: KM-KGS-100a-3
    # angle: seam
    """implemented_by resolves to the canonical-path files node, survives validation, keeps anchor."""
    project_root, paths_json = _build_ac_relationships_project(tmp_path)
    km = build_knowledge_map(project_root, paths_json)

    implemented_by_edges = [
        e for e in km.edges if e.source_id == "KM-EX-010" and e.edge_type == "implemented_by"
    ]
    assert len(implemented_by_edges) == 1
    edge = implemented_by_edges[0]
    assert edge.target_id == "scripts/foo.py", (
        "the target must equal the canonical repo-relative path, not a raw-string leaf"
    )

    node_ids = {n.id: n for n in km.nodes}
    assert edge.target_id in node_ids, "the target must be a node in the built node set"
    assert node_ids[edge.target_id].surface == "files"

    integrity = validate_edges_integrity(km, project_root, paths_json)
    assert edge in integrity.validated_edges, "the edge must survive validation"
    assert edge not in integrity.dropped_edges
    assert integrity.exempt_edge_types == frozenset(), (
        "the edge must survive because its target is a node, not via an exemption"
    )

    km_ex_013_edges = [
        e for e in km.edges if e.source_id == "KM-EX-013" and e.edge_type == "implemented_by"
    ]
    assert len(km_ex_013_edges) == 1
    assert km_ex_013_edges[0].target_id == "scripts/foo.py"
    assert getattr(km_ex_013_edges[0], "anchor", None) == "_check_limits", (
        "the #_check_limits anchor must be kept as the edge attribute 'anchor'"
    )
    assert getattr(edge, "anchor", None) is None, "KM-EX-010's edge carries no anchor"

    payload = _run_cli_json(project_root)
    exported = [
        e for e in payload["edges"]
        if e["source"] == "KM-EX-013" and e["type"] == "implemented_by"
    ]
    assert exported and exported[0].get("anchor") == "_check_limits", (
        "the anchor must also be present on the edge object in the CLI's JSON export"
    )


def test_acs_file_covered_by_yields_covered_by_edges(tmp_path):
    # covers: KM-KGS-100a-3
    # angle: seam
    """covered_by resolves to the canonical-path files node, survives validation, keeps anchor."""
    project_root, paths_json = _build_ac_relationships_project(tmp_path)
    km = build_knowledge_map(project_root, paths_json)

    covered_by_edges = [
        e for e in km.edges if e.source_id == "KM-EX-010" and e.edge_type == "covered_by"
    ]
    assert len(covered_by_edges) == 1
    edge = covered_by_edges[0]
    assert edge.target_id == "unit_tests/test_foo.py", (
        "the target must be quote-free and equal the canonical repo-relative path"
    )

    node_ids = {n.id: n for n in km.nodes}
    assert edge.target_id in node_ids, "the target must be a files-surface node in the node set"
    assert node_ids[edge.target_id].surface == "files"

    integrity = validate_edges_integrity(km, project_root, paths_json)
    assert edge in integrity.validated_edges
    assert edge not in integrity.dropped_edges
    assert integrity.exempt_edge_types == frozenset()

    km_ex_013_edges = [
        e for e in km.edges if e.source_id == "KM-EX-013" and e.edge_type == "covered_by"
    ]
    assert len(km_ex_013_edges) == 1
    assert km_ex_013_edges[0].target_id == "unit_tests/test_foo.py"
    assert getattr(km_ex_013_edges[0], "anchor", None) == "test_limits", (
        "the ::test_limits anchor must be kept as the edge attribute 'anchor'"
    )

    payload = _run_cli_json(project_root)
    exported = [
        e for e in payload["edges"]
        if e["source"] == "KM-EX-013" and e["type"] == "covered_by"
    ]
    assert exported and exported[0].get("anchor") == "test_limits", (
        "the anchor must also be present in the built map and the JSON export"
    )


def test_acs_file_depends_on_yields_depends_on_edge_to_criterion(tmp_path):
    # covers: KM-KGS-100a-3
    # angle: seam
    """Real read -> real extract_edges yields a depends_on edge to KM-EX-009."""
    node, fields = _read_km_ex_010(tmp_path)
    edges = list(extract_edges("acs", node, fields, _ACS_EDGE_FIELDS))
    depends_on_edges = [e for e in edges if e.edge_type == "depends_on"]
    assert len(depends_on_edges) == 1
    assert depends_on_edges[0].source_id == "KM-EX-010"
    assert depends_on_edges[0].target_id == "KM-EX-009"


def test_acs_file_components_yields_component_membership_edge_to_hub(tmp_path):
    # covers: KM-KGS-100a-3
    # angle: seam
    """The components value produces a component_membership edge, not a 'components' edge."""
    node, fields = _read_km_ex_010(tmp_path)
    edges = list(extract_edges("acs", node, fields, _ACS_EDGE_FIELDS))
    assert not [e for e in edges if e.edge_type == "components"]
    hub_edges = [e for e in edges if e.edge_type == "component_membership"]
    assert len(hub_edges) == 1
    assert hub_edges[0].source_id == "KM-EX-010"
    assert hub_edges[0].target_id == "build-pipeline"


def test_acs_edge_types_follow_declared_edge_fields(tmp_path):
    # covers: KM-KGS-100a-3
    # angle: reachability
    """The real CLI's acs edge types are exactly those declared in paths.json.

    Runs the shipped knowledge_query.py CLI as a subprocess (the real
    production entry point) against a temporary project root, then mutates
    the declared edge_fields and reruns, proving the produced edge types
    track the declaration with no acs-specific code branch.
    """
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    acs_dir = tmp_path / "docs" / "acceptance-criteria" / "example-component"
    acs_dir.mkdir(parents=True)
    (acs_dir / "KM-EX-010.yaml").write_text(_KM_EX_010_YAML, encoding="utf-8")
    (acs_dir / "KM-EX-009.yaml").write_text(_KM_EX_009_YAML, encoding="utf-8")

    def _write_paths_json(edge_fields):
        paths_json = {
            "surfaces": {
                "acs": {
                    "path": "docs/acceptance-criteria/",
                    "edge_fields": edge_fields,
                    "file_path_fields": ["implemented_by", "covered_by"],
                }
            }
        }
        (config_dir / "paths.json").write_text(
            json.dumps(paths_json), encoding="utf-8"
        )

    def _run_cli():
        result = subprocess.run(
            [
                sys.executable,
                str(_KNOWLEDGE_QUERY_SCRIPT),
                "--project-root",
                str(tmp_path),
                "--surface",
                "acs",
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)

    _write_paths_json(_ACS_EDGE_FIELDS)
    payload = _run_cli()
    produced_types = {
        e["type"] for e in payload["edges"] if e["source"] == "KM-EX-010"
    }
    expected_types = {
        "component_membership" if f == "components" else f
        for f in _ACS_EDGE_FIELDS
    }
    assert produced_types == expected_types

    # Changing the declaration must change the produced types with no code edit.
    _write_paths_json(["implemented_by", "components"])
    payload2 = _run_cli()
    produced_types2 = {
        e["type"] for e in payload2["edges"] if e["source"] == "KM-EX-010"
    }
    assert "depends_on" not in produced_types2
    assert "covered_by" not in produced_types2
    assert produced_types2 == {"implemented_by", "component_membership"}


def test_covered_by_full_pytest_node_id_keeps_class_and_method_in_anchor_only(tmp_path):
    # covers: KM-KGS-100a-3
    # angle: boundary
    """Regression: a covered_by value with a second '::' must not leak into the node id.

    _strip_anchor originally split at the LAST '#'/'::'. For a covered_by
    value that is a full pytest node id, 'unit_tests/x/test_a.py::TestClass::
    test_method', that left '::TestClass' inside the canonical path. It must
    split at the FIRST '::' instead, so the path portion is exactly the file
    and everything after (including the second '::') is kept as the anchor.
    """
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "paths.json").write_bytes(_REAL_PATHS_JSON.read_bytes())

    acs_dir = tmp_path / "docs" / "acceptance-criteria" / "example-component"
    acs_dir.mkdir(parents=True)
    (acs_dir / "KM-EX-014.yaml").write_text(
        "id: KM-EX-014\n"
        "title: Covered by a full pytest node id\n"
        "covered_by:\n"
        "- unit_tests/test_foo.py::TestFoo::test_bar\n",
        encoding="utf-8",
    )

    unit_tests_dir = tmp_path / "unit_tests"
    unit_tests_dir.mkdir(parents=True)
    (unit_tests_dir / "test_foo.py").write_text("# real test file\n", encoding="utf-8")

    km = build_knowledge_map(tmp_path, config_dir / "paths.json")
    covered_by_edges = [
        e for e in km.edges if e.source_id == "KM-EX-014" and e.edge_type == "covered_by"
    ]
    assert len(covered_by_edges) == 1
    edge = covered_by_edges[0]
    assert edge.target_id == "unit_tests/test_foo.py", (
        f"the node id must be exactly the file path with no '::' left in it; "
        f"got {edge.target_id!r}"
    )
    assert "::" not in edge.target_id
    assert edge.anchor == "TestFoo::test_bar", (
        f"the anchor must keep the class and method, including the second "
        f"'::'; got {edge.anchor!r}"
    )
