"""
MODULE: test_ac_edge_relationships
GOAL: TDD test stubs for KM-KGS-100a-3 — AC four-relationship-field edge generation.
      All tests are RED before python-coder implements the feature; must be GREEN after.
BUSINESS CONTEXT: Verifies that each of the four AC relationship fields
    (implemented_by, covered_by, depends_on, components) produces the correct
    edge type when the knowledge map is built from the "acs" surface.
    Covers the Gherkin AC for ticket 04_TICKET-20260622-KM-KGS-100a-3.
"""

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

sys.path.insert(0, str(_SCRIPTS_DIR))

from knowledge_query import (  # noqa: E402
    NodeRecord,
    _collect_all,
    extract_edges,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ac_surface_tmp(tmp_path):
    """Build a minimal project tree with an 'acs' surface containing one AC YAML.

    The AC YAML has all four relationship fields populated:
      - implemented_by: ["scripts/foo.py"]
      - covered_by:     ["unit_tests/test_foo.py"]
      - depends_on:     ["KM-EX-009"]
      - components:     ["build-pipeline"]
    """
    # Create config dir + paths.json
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)

    # Create the acs surface directory with one AC YAML
    acs_dir = tmp_path / "docs" / "acceptance-criteria" / "example-component"
    acs_dir.mkdir(parents=True)

    ac_yaml_content = (
        "id: KM-EX-010\n"
        "title: Example AC for edge relationship test\n"
        "description: Tests all four relationship edges\n"
        "status: active\n"
        "component: example-component\n"
        "implemented_by:\n"
        "  - scripts/foo.py\n"
        "covered_by:\n"
        "  - unit_tests/test_foo.py\n"
        "depends_on:\n"
        "  - KM-EX-009\n"
        "components:\n"
        "  - build-pipeline\n"
    )
    (acs_dir / "KM-EX-010.yaml").write_text(ac_yaml_content, encoding="utf-8")

    # Create a KM-EX-009 AC YAML so the depends_on edge isn't phantom-filtered
    ac_009_content = (
        "id: KM-EX-009\n"
        "title: Prerequisite AC\n"
        "description: The AC that KM-EX-010 depends on\n"
        "status: active\n"
        "component: example-component\n"
        "implemented_by: []\n"
        "covered_by: []\n"
        "depends_on: []\n"
        "components:\n"
        "  - build-pipeline\n"
    )
    (acs_dir / "KM-EX-009.yaml").write_text(ac_009_content, encoding="utf-8")

    # KM-KGS-100d-4-iv: copy the real acs entry so this fixture can never
    # drift from production's own file_path_fields declaration.
    real_data = json.loads((_REPO_ROOT / "config" / "paths.json").read_text(encoding="utf-8"))
    paths_data = {"surfaces": {"acs": real_data["surfaces"]["acs"]}}
    (config_dir / "paths.json").write_text(json.dumps(paths_data), encoding="utf-8")

    return tmp_path


# ---------------------------------------------------------------------------
# Unit-level tests: extract_edges() for AC relationship fields
# ---------------------------------------------------------------------------


class TestExtractEdgesAcRelationshipFields:
    """Unit tests for extract_edges() with AC YAML relationship fields."""

    def _make_ac_node(self) -> NodeRecord:
        return NodeRecord(
            id="KM-EX-010",
            surface="acs",
            title="Example AC for edge relationship test",
            description="Tests all four relationship edges",
            path=Path("docs/acceptance-criteria/example-component/KM-EX-010.yaml"),
        )

    def test_ac1_implemented_by_edge(self):
        # covers: UNKNOWN
        """AC-1 (KM-KGS-100a-3): implemented_by field produces an implemented_by edge to the script file node."""
        record = self._make_ac_node()
        raw_data = {
            "id": "KM-EX-010",
            "implemented_by": ["scripts/foo.py"],
            "covered_by": [],
            "depends_on": [],
            "components": [],
        }
        edges = list(extract_edges("acs", record, raw_data,
                                   edge_fields=["implemented_by", "covered_by", "depends_on", "components"]))
        impl_edges = [e for e in edges if e.edge_type == "implemented_by"]
        assert len(impl_edges) >= 1, (
            "implemented_by field must produce at least one 'implemented_by' edge"
        )
        targets = {e.target_id for e in impl_edges}
        assert "scripts/foo.py" in targets, (
            "implemented_by edge target must be 'scripts/foo.py' "
            "(raw path value, not stem-resolved for implemented_by)"
        )
        for edge in impl_edges:
            assert edge.source_id == "KM-EX-010", (
                "implemented_by edge source must be the AC node id 'KM-EX-010'"
            )

    def test_ac2_covered_by_edge(self):
        # covers: UNKNOWN
        """AC-2 (KM-KGS-100a-3): covered_by field produces a covered_by edge to the test file node."""
        record = self._make_ac_node()
        raw_data = {
            "id": "KM-EX-010",
            "implemented_by": [],
            "covered_by": ["unit_tests/test_foo.py"],
            "depends_on": [],
            "components": [],
        }
        edges = list(extract_edges("acs", record, raw_data,
                                   edge_fields=["implemented_by", "covered_by", "depends_on", "components"]))
        cov_edges = [e for e in edges if e.edge_type == "covered_by"]
        assert len(cov_edges) >= 1, (
            "covered_by field must produce at least one 'covered_by' edge"
        )
        targets = {e.target_id for e in cov_edges}
        assert "unit_tests/test_foo.py" in targets, (
            "covered_by edge target must be 'unit_tests/test_foo.py'"
        )
        for edge in cov_edges:
            assert edge.source_id == "KM-EX-010", (
                "covered_by edge source must be the AC node id 'KM-EX-010'"
            )

    def test_ac3_depends_on_edge(self):
        # covers: UNKNOWN
        """AC-3 (KM-KGS-100a-3): depends_on field produces a depends_on edge to sibling AC node KM-EX-009."""
        record = self._make_ac_node()
        raw_data = {
            "id": "KM-EX-010",
            "implemented_by": [],
            "covered_by": [],
            "depends_on": ["KM-EX-009"],
            "components": [],
        }
        edges = list(extract_edges("acs", record, raw_data,
                                   edge_fields=["implemented_by", "covered_by", "depends_on", "components"]))
        dep_edges = [e for e in edges if e.edge_type == "depends_on"]
        assert len(dep_edges) >= 1, (
            "depends_on field must produce at least one 'depends_on' edge"
        )
        targets = {e.target_id for e in dep_edges}
        assert "KM-EX-009" in targets, (
            "depends_on edge target must be 'KM-EX-009' (bare AC id, no path resolution)"
        )
        for edge in dep_edges:
            assert edge.source_id == "KM-EX-010", (
                "depends_on edge source must be the AC node id 'KM-EX-010'"
            )

    def test_ac4_component_membership_edge(self):
        # covers: UNKNOWN
        """AC-4 (KM-KGS-100a-3): components field produces a component_membership edge to the build-pipeline hub."""
        record = self._make_ac_node()
        raw_data = {
            "id": "KM-EX-010",
            "implemented_by": [],
            "covered_by": [],
            "depends_on": [],
            "components": ["build-pipeline"],
        }
        edges = list(extract_edges("acs", record, raw_data,
                                   edge_fields=["implemented_by", "covered_by", "depends_on", "components"]))
        comp_edges = [e for e in edges if e.edge_type == "component_membership"]
        assert len(comp_edges) >= 1, (
            "components field must produce at least one 'component_membership' edge"
        )
        targets = {e.target_id for e in comp_edges}
        assert "build-pipeline" in targets, (
            "component_membership edge target must be 'build-pipeline'"
        )
        for edge in comp_edges:
            assert edge.source_id == "KM-EX-010", (
                "component_membership edge source must be the AC node id 'KM-EX-010'"
            )

    def test_ac_all_four_edge_types_simultaneously(self):
        # covers: UNKNOWN
        """AC (KM-KGS-100a-3): all four edges are emitted simultaneously from one AC raw_data dict."""
        record = self._make_ac_node()
        raw_data = {
            "id": "KM-EX-010",
            "implemented_by": ["scripts/foo.py"],
            "covered_by": ["unit_tests/test_foo.py"],
            "depends_on": ["KM-EX-009"],
            "components": ["build-pipeline"],
        }
        edges = list(extract_edges("acs", record, raw_data,
                                   edge_fields=["implemented_by", "covered_by", "depends_on", "components"]))
        edge_types = {e.edge_type for e in edges}
        assert "implemented_by" in edge_types, (
            "All four: implemented_by edge must be present"
        )
        assert "covered_by" in edge_types, (
            "All four: covered_by edge must be present"
        )
        assert "depends_on" in edge_types, (
            "All four: depends_on edge must be present"
        )
        assert "component_membership" in edge_types, (
            "All four: component_membership edge must be present (components field)"
        )


# ---------------------------------------------------------------------------
# Integration tests: _collect_all() with acs surface
# ---------------------------------------------------------------------------


class TestCollectAllAcsSurface:
    """Integration tests for _collect_all() on an acs surface fixture."""

    def test_ac1_implemented_by_edge_in_collect_all(self, ac_surface_tmp):
        # covers: UNKNOWN
        # angle: criterion
        """AC-1 (KM-KGS-100a-3): _collect_all produces implemented_by edge from KM-EX-010 to scripts/foo.py."""
        project_root = ac_surface_tmp
        paths_json = project_root / "config" / "paths.json"
        nodes, edges = _collect_all(project_root, paths_json, surface_filter="acs")

        impl_edges = [
            e for e in edges
            if e.edge_type == "implemented_by" and e.source_id == "KM-EX-010"
        ]
        assert len(impl_edges) >= 1, (
            "_collect_all must produce at least one 'implemented_by' edge from KM-EX-010 "
            "when the AC YAML has implemented_by: ['scripts/foo.py']"
        )
        targets = {e.target_id for e in impl_edges}
        assert "scripts/foo.py" in targets, (
            "implemented_by edge target must be 'scripts/foo.py' in _collect_all output"
        )
        assert [n for n in nodes if n.id == "scripts/foo.py" and n.surface == "files"], nodes  # KM-KGS-100d-4-iv

    def test_ac2_covered_by_edge_in_collect_all(self, ac_surface_tmp):
        # covers: UNKNOWN
        # angle: criterion
        """AC-2 (KM-KGS-100a-3): _collect_all produces covered_by edge from KM-EX-010 to unit_tests/test_foo.py."""
        project_root = ac_surface_tmp
        paths_json = project_root / "config" / "paths.json"
        nodes, edges = _collect_all(project_root, paths_json, surface_filter="acs")

        cov_edges = [
            e for e in edges
            if e.edge_type == "covered_by" and e.source_id == "KM-EX-010"
        ]
        assert len(cov_edges) >= 1, (
            "_collect_all must produce at least one 'covered_by' edge from KM-EX-010 "
            "when the AC YAML has covered_by: ['unit_tests/test_foo.py']"
        )
        targets = {e.target_id for e in cov_edges}
        assert "unit_tests/test_foo.py" in targets, (
            "covered_by edge target must be 'unit_tests/test_foo.py' in _collect_all output"
        )
        assert [n for n in nodes if n.id == "unit_tests/test_foo.py" and n.surface == "files"], nodes  # KM-KGS-100d-4-iv

    def test_ac3_depends_on_edge_in_collect_all(self, ac_surface_tmp):
        # covers: UNKNOWN
        """AC-3 (KM-KGS-100a-3): _collect_all produces depends_on edge from KM-EX-010 to KM-EX-009."""
        project_root = ac_surface_tmp
        paths_json = project_root / "config" / "paths.json"
        nodes, edges = _collect_all(project_root, paths_json, surface_filter="acs")

        dep_edges = [
            e for e in edges
            if e.edge_type == "depends_on" and e.source_id == "KM-EX-010"
        ]
        assert len(dep_edges) >= 1, (
            "_collect_all must produce at least one 'depends_on' edge from KM-EX-010 "
            "when the AC YAML has depends_on: ['KM-EX-009']"
        )
        targets = {e.target_id for e in dep_edges}
        assert "KM-EX-009" in targets, (
            "depends_on edge target must be 'KM-EX-009' in _collect_all output"
        )

    def test_ac4_component_membership_edge_in_collect_all(self, ac_surface_tmp):
        # covers: UNKNOWN
        """AC-4 (KM-KGS-100a-3): _collect_all produces component_membership edge from KM-EX-010 to build-pipeline."""
        project_root = ac_surface_tmp
        paths_json = project_root / "config" / "paths.json"
        nodes, edges = _collect_all(project_root, paths_json, surface_filter="acs")

        comp_edges = [
            e for e in edges
            if e.edge_type == "component_membership" and e.source_id == "KM-EX-010"
        ]
        assert len(comp_edges) >= 1, (
            "_collect_all must produce at least one 'component_membership' edge from KM-EX-010 "
            "when the AC YAML has components: ['build-pipeline']"
        )
        targets = {e.target_id for e in comp_edges}
        assert "build-pipeline" in targets, (
            "component_membership edge target must be 'build-pipeline' (component hub node)"
        )

    def test_component_hub_node_created_for_build_pipeline(self, ac_surface_tmp):
        # covers: UNKNOWN
        """AC-4 (KM-KGS-100a-3): _collect_all creates a synthetic hub node for 'build-pipeline'."""
        project_root = ac_surface_tmp
        paths_json = project_root / "config" / "paths.json"
        nodes, edges = _collect_all(project_root, paths_json, surface_filter="acs")

        node_ids = {n.id for n in nodes}
        assert "build-pipeline" in node_ids, (
            "A synthetic hub NodeRecord for 'build-pipeline' must be created by _collect_all "
            "when the AC YAML references it in components"
        )

    def test_ac_node_km_ex_010_present(self, ac_surface_tmp):
        # covers: UNKNOWN
        """AC (KM-KGS-100a-3): _collect_all must produce a node for KM-EX-010 from the acs surface."""
        project_root = ac_surface_tmp
        paths_json = project_root / "config" / "paths.json"
        nodes, edges = _collect_all(project_root, paths_json, surface_filter="acs")

        node_ids = {n.id for n in nodes}
        assert "KM-EX-010" in node_ids, (
            "AC node 'KM-EX-010' must be present in nodes after _collect_all on acs surface"
        )

    def test_all_four_edges_present_in_collect_all(self, ac_surface_tmp):
        # covers: UNKNOWN
        # angle: criterion
        """AC (KM-KGS-100a-3): all four edge types are produced together by _collect_all."""
        project_root = ac_surface_tmp
        paths_json = project_root / "config" / "paths.json"
        nodes, edges = _collect_all(project_root, paths_json, surface_filter="acs")

        km_ex_010_edges = [e for e in edges if e.source_id == "KM-EX-010"]
        edge_types = {e.edge_type for e in km_ex_010_edges}

        assert "implemented_by" in edge_types, (
            "implemented_by edge type must be present in _collect_all output for KM-EX-010"
        )
        assert "covered_by" in edge_types, (
            "covered_by edge type must be present in _collect_all output for KM-EX-010"
        )
        assert "depends_on" in edge_types, (
            "depends_on edge type must be present in _collect_all output for KM-EX-010"
        )
        assert "component_membership" in edge_types, (
            "component_membership edge type must be present in _collect_all output for KM-EX-010"
        )
        files_ids = {n.id for n in nodes if n.surface == "files"}  # KM-KGS-100d-4-iv
        assert {"scripts/foo.py", "unit_tests/test_foo.py"} <= files_ids, files_ids


# ---------------------------------------------------------------------------
# KM-KGS-100d-4-iv restatement: AC file edges end on files-surface nodes
# ---------------------------------------------------------------------------


class TestAcFileEdgesEndOnFileNodes:
    """implemented_by / covered_by file targets end on real files-surface
    nodes. RENAMED from TestPhantomFilterDoesNotDropAcEdges (KM-KGS-100d-4-iv):
    once the file_path_fields exemption retires (KM-KGS-100d-2), these edges
    survive only by resolving to a files-surface node, not as a raw-string
    leaf that merely "will NOT have corresponding nodes"."""

    def test_implemented_by_edge_ends_on_files_node_under_acs_restriction(self, ac_surface_tmp):
        # covers: KM-KGS-100d-4-iv
        # angle: criterion
        """implemented_by's file target must be a files-surface node."""
        project_root = ac_surface_tmp
        paths_json = project_root / "config" / "paths.json"
        nodes, edges = _collect_all(project_root, paths_json, surface_filter="acs")

        impl_edges = [e for e in edges if e.edge_type == "implemented_by" and e.source_id == "KM-EX-010"]
        assert len(impl_edges) >= 1 and impl_edges[0].target_id == "scripts/foo.py", impl_edges
        target_nodes = [n for n in nodes if n.id == "scripts/foo.py"]
        assert target_nodes and target_nodes[0].surface == "files", target_nodes

    def test_covered_by_edge_ends_on_files_node_under_acs_restriction(self, ac_surface_tmp):
        # covers: KM-KGS-100d-4-iv
        # angle: criterion
        """covered_by's file target must be a files-surface node."""
        project_root = ac_surface_tmp
        paths_json = project_root / "config" / "paths.json"
        nodes, edges = _collect_all(project_root, paths_json, surface_filter="acs")

        cov_edges = [e for e in edges if e.edge_type == "covered_by" and e.source_id == "KM-EX-010"]
        assert len(cov_edges) >= 1 and cov_edges[0].target_id == "unit_tests/test_foo.py", cov_edges
        target_nodes = [n for n in nodes if n.id == "unit_tests/test_foo.py"]
        assert target_nodes and target_nodes[0].surface == "files", target_nodes
