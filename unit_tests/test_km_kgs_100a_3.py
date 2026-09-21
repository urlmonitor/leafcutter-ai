"""
MODULE: test_km_kgs_100a_3
GOAL: TDD stubs for KM-KGS-100a-3 — an acceptance criterion's four
      relationship fields each become a distinct edge.
BUSINESS CONTEXT: This is the L2 composite over KM-KGS-100a-3-i..-viii, so
    its tests stay at edge-production level: real file -> real reader
    (_parse_yaml_file) -> real edge extractor (extract_edges), asserting
    candidate-edge type/source/count-and-quote-freedom per field (before
    target-existence validation), plus a reachability test that runs the
    real knowledge_query CLI end-to-end and proves the produced edge types
    are exactly those declared in paths.json's edge_fields for the acs
    surface, with no acs-specific code branch.
"""

import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_KNOWLEDGE_QUERY_SCRIPT = _SCRIPTS_DIR / "knowledge_query.py"
sys.path.insert(0, str(_SCRIPTS_DIR))

from knowledge_query import _parse_yaml_file, extract_edges  # noqa: E402

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


def test_acs_file_implemented_by_yields_implemented_by_edges(tmp_path):
    # covers: KM-KGS-100a-3
    # angle: seam
    """Real read -> real extract_edges yields one implemented_by edge, quote-free."""
    node, fields = _read_km_ex_010(tmp_path)
    edges = list(extract_edges("acs", node, fields, _ACS_EDGE_FIELDS))
    implemented_by_edges = [e for e in edges if e.edge_type == "implemented_by"]
    assert len(implemented_by_edges) == 1
    edge = implemented_by_edges[0]
    assert edge.source_id == "KM-EX-010"
    assert edge.target_id
    assert '"' not in edge.target_id and "'" not in edge.target_id


def test_acs_file_covered_by_yields_covered_by_edges(tmp_path):
    # covers: KM-KGS-100a-3
    # angle: seam
    """Real read -> real extract_edges yields one covered_by edge, quote-free."""
    node, fields = _read_km_ex_010(tmp_path)
    edges = list(extract_edges("acs", node, fields, _ACS_EDGE_FIELDS))
    covered_by_edges = [e for e in edges if e.edge_type == "covered_by"]
    assert len(covered_by_edges) == 1
    edge = covered_by_edges[0]
    assert edge.source_id == "KM-EX-010"
    assert edge.target_id
    assert '"' not in edge.target_id and "'" not in edge.target_id


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
