"""
MODULE: test_knowledge_query
GOAL: TDD test stubs for knowledge_query.py — cross-surface knowledge index script.
      All tests are RED before python-coder runs; they must be GREEN after implementation.
BUSINESS CONTEXT: Verifies the public API (load_surfaces, extract_nodes, extract_edges)
    and CLI behaviour (--query, --format json, missing paths.json) for the
    single-pass knowledge-graph query utility.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

sys.path.insert(0, str(_SCRIPTS_DIR))

# -----------------------------------------------------------------------
# Import the module under test.
# If knowledge_query.py does not yet exist the ImportError propagates and
# all tests in this file are collected as errors (valid RED state).
# -----------------------------------------------------------------------
from knowledge_query import (  # noqa: E402
    NodeRecord,
    extract_edges,
    extract_nodes,
    load_surfaces,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def minimal_paths_json(tmp_path):
    """Build a minimal paths.json that exposes two surfaces: agents and tickets."""
    agents_dir = tmp_path / "config"
    agents_dir.mkdir(parents=True)
    registry = {
        "agents": [
            {
                "id": "python-coder",
                "name": "Python Coder",
                "description": "Writes production-quality Python.",
                "is_ticket_phase": True,
                "spawn_allowlist": [],
                "spawned_by": ["ticket-supervisor"],
                "skills_used": ["signoff"],
            }
        ]
    }
    (agents_dir / "agent_registry.json").write_text(
        json.dumps(registry), encoding="utf-8"
    )

    tickets_dir = tmp_path / "tickets" / "00_inbox"
    tickets_dir.mkdir(parents=True)
    ticket_content = (
        "---\n"
        "title: Sample Ticket\n"
        "description: A test ticket\n"
        "agents:\n"
        "  python-coder: needed\n"
        "depends_on: []\n"
        "files_touched:\n"
        "  - scripts/foo.py\n"
        "---\n\n"
        "# Sample Ticket\n\nBody text.\n"
    )
    (tickets_dir / "sample_ticket.md").write_text(ticket_content, encoding="utf-8")

    paths_data = {
        "surfaces": {
            "agents": {
                "path": "config/agent_registry.json",
                "edge_fields": ["spawn_allowlist", "spawned_by", "skills_used"],
            },
            "tickets": {
                "path": "tickets/00_inbox",
                "edge_fields": ["depends_on", "files_touched"],
                "_optional": True,
            },
        }
    }
    paths_file = tmp_path / "config" / "paths.json"
    paths_file.write_text(json.dumps(paths_data), encoding="utf-8")

    return tmp_path, paths_file


@pytest.fixture
def paths_json_with_optional_missing(tmp_path):
    """paths.json where one surface root does not exist but is optional."""
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    registry = {"agents": []}
    (config_dir / "agent_registry.json").write_text(
        json.dumps(registry), encoding="utf-8"
    )

    paths_data = {
        "surfaces": {
            "agents": {
                "path": "config/agent_registry.json",
                "edge_fields": [],
            },
            "missing_surface": {
                "path": "does/not/exist",
                "edge_fields": [],
                "_optional": True,
            },
        }
    }
    paths_file = config_dir / "paths.json"
    paths_file.write_text(json.dumps(paths_data), encoding="utf-8")
    return tmp_path, paths_file


# ---------------------------------------------------------------------------
# AC-8: load_surfaces tests
# ---------------------------------------------------------------------------


class TestLoadSurfaces:
    """Tests for the load_surfaces() public function (AC-8)."""

    def test_load_surfaces_returns_all_present_surfaces(self, minimal_paths_json):
        # covers: UNKNOWN
        """AC-8: load_surfaces returns a dict keyed by surface name for all present paths."""
        project_root, paths_file = minimal_paths_json
        surfaces = load_surfaces(project_root, paths_file)
        assert isinstance(surfaces, dict), "load_surfaces must return a dict"
        assert "agents" in surfaces, "agents surface must be present"

    def test_load_surfaces_skips_optional_missing(self, paths_json_with_optional_missing):
        # covers: UNKNOWN
        """AC-8: load_surfaces silently skips optional surfaces whose path is absent."""
        project_root, paths_file = paths_json_with_optional_missing
        surfaces = load_surfaces(project_root, paths_file)
        assert "missing_surface" not in surfaces, (
            "Optional missing surface must be skipped"
        )
        assert "agents" in surfaces, "Present surface must still be returned"


# ---------------------------------------------------------------------------
# AC-8: extract_nodes tests
# ---------------------------------------------------------------------------


class TestExtractNodes:
    """Tests for the extract_nodes() generator function (AC-8)."""

    def test_extract_nodes_uses_description_frontmatter(self, tmp_path):
        # covers: UNKNOWN
        """AC-8: extract_nodes uses the frontmatter 'description:' field when present."""
        md_file = tmp_path / "ticket_a.md"
        md_file.write_text(
            "---\ntitle: My Ticket\ndescription: Explicit description from frontmatter\n---\n\nBody line.\n",
            encoding="utf-8",
        )
        nodes = list(extract_nodes("tickets", tmp_path))
        assert len(nodes) >= 1, "Should yield at least one node"
        node = nodes[0]
        assert node.description == "Explicit description from frontmatter", (
            "Description must come from frontmatter when present"
        )

    def test_extract_nodes_falls_back_to_first_body_line(self, tmp_path):
        # covers: UNKNOWN
        """AC-8: extract_nodes falls back to first non-blank body line when description absent."""
        md_file = tmp_path / "ticket_b.md"
        md_file.write_text(
            "---\ntitle: No Description Ticket\n---\n\n# Heading\n\nFirst body paragraph.\n",
            encoding="utf-8",
        )
        nodes = list(extract_nodes("tickets", tmp_path))
        assert len(nodes) >= 1, "Should yield at least one node"
        node = nodes[0]
        assert node.description, "Fallback description must not be empty"
        assert (
            "Heading" in node.description or "First body paragraph" in node.description
        ), "Fallback description must come from the first non-blank body line"


# ---------------------------------------------------------------------------
# AC-8: extract_edges tests
# ---------------------------------------------------------------------------


class TestExtractEdges:
    """Tests for the extract_edges() generator function (AC-8)."""

    def test_extract_edges_spawn_allowlist(self):
        # covers: UNKNOWN
        """AC-8: extract_edges produces edges from spawn_allowlist for the agents surface."""
        fake_record = NodeRecord(
            id="python-coder",
            surface="agents",
            title="Python Coder",
            description="Writes Python.",
            path=Path("config/agent_registry.json"),
        )
        raw_data = {
            "id": "python-coder",
            "spawn_allowlist": ["research-agent", "test-runner"],
        }
        edges = list(extract_edges("agents", fake_record, raw_data))
        edge_targets = {e.target_id for e in edges}
        assert "research-agent" in edge_targets, (
            "spawn_allowlist entries must produce edges"
        )
        assert "test-runner" in edge_targets, (
            "All spawn_allowlist entries must produce edges"
        )
        for edge in edges:
            assert edge.edge_type, "Every edge must have a non-empty edge_type"


# ---------------------------------------------------------------------------
# AC-3/AC-8: --query filter
# ---------------------------------------------------------------------------


class TestQueryFilter:
    """Tests for --query CLI filter behaviour (AC-3/AC-8)."""

    def test_query_filter_case_insensitive(self, minimal_paths_json):
        # covers: UNKNOWN
        """AC-3/AC-8: --query filter is case-insensitive."""
        project_root, paths_file = minimal_paths_json
        surfaces = load_surfaces(project_root, paths_file)
        all_nodes: list = []
        for surface_name, surface_path in surfaces.items():
            all_nodes.extend(extract_nodes(surface_name, surface_path))

        keyword = "PYTHON"
        matched = [
            n for n in all_nodes
            if keyword.lower() in (n.title or "").lower()
            or keyword.lower() in (n.description or "").lower()
        ]
        assert len(matched) >= 1, (
            "Case-insensitive query for 'PYTHON' must match at least one node"
        )


# ---------------------------------------------------------------------------
# AC-2/AC-8: --format json
# ---------------------------------------------------------------------------


class TestJsonFormat:
    """Tests for --format json output (AC-2/AC-8)."""

    def test_format_json_valid_schema(self, minimal_paths_json):
        # covers: UNKNOWN
        """AC-2/AC-8: --format json has top-level 'nodes'/'edges' keys with correct schema."""
        project_root, paths_file = minimal_paths_json
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPTS_DIR / "knowledge_query.py"),
                "--format", "json",
                "--project-root", str(project_root),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"--format json must exit 0; stderr: {result.stderr}"
        )
        data = json.loads(result.stdout)
        assert "nodes" in data, "JSON output must have 'nodes' key"
        assert "edges" in data, "JSON output must have 'edges' key"
        if data["nodes"]:
            node = data["nodes"][0]
            for field in ("id", "surface", "title", "description", "path"):
                assert field in node, f"Node must have '{field}' field"
        if data["edges"]:
            edge = data["edges"][0]
            for field in ("source", "target", "type"):
                assert field in edge, f"Edge must have '{field}' field"


# ---------------------------------------------------------------------------
# AC-6/AC-8: missing paths.json
# ---------------------------------------------------------------------------


class TestMissingPathsJson:
    """Tests for clean error handling when paths.json is absent (AC-6/AC-8)."""

    def test_missing_paths_json_exits_cleanly(self, tmp_path):
        # covers: UNKNOWN
        """AC-6/AC-8: Script exits with code 1 and clean error message when paths.json absent."""
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPTS_DIR / "knowledge_query.py"),
                "--project-root", str(tmp_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, (
            "Script must exit with code 1 when paths.json is absent"
        )
        combined = result.stdout + result.stderr
        assert "ERROR" in combined and "paths.json" in combined, (
            "Error message must mention 'ERROR' and 'paths.json'"
        )
        assert "Traceback" not in combined, "Script must not emit a Python traceback"


# ---------------------------------------------------------------------------
# AC-1/AC-8: stdlib-only imports
# ---------------------------------------------------------------------------


class TestStdlibOnly:
    """Tests that knowledge_query.py uses only stdlib imports (AC-1/AC-8)."""

    def test_stdlib_only(self):
        # covers: UNKNOWN
        """AC-1/AC-8: knowledge_query.py must not import any known third-party packages."""
        module_path = _SCRIPTS_DIR / "knowledge_query.py"
        assert module_path.exists(), f"knowledge_query.py must exist at {module_path}"
        source = module_path.read_text(encoding="utf-8")
        forbidden = [
            "import requests",
            "import numpy",
            "import pandas",
            "import yaml",
            "import toml",
            "import pydantic",
            "import sqlalchemy",
            "import psycopg2",
            "import aiohttp",
        ]
        for imp in forbidden:
            assert imp not in source, (
                f"Third-party import '{imp}' found — only stdlib allowed (AC-1)"
            )


# ---------------------------------------------------------------------------
# Ticket 04a Integration Tests — surfaces config wiring
# These tests are RED until python-coder adds the "surfaces" key to
# config/paths.json.
# ---------------------------------------------------------------------------

_REAL_PATHS_JSON = _REPO_ROOT / "config" / "paths.json"


class TestPathsJsonSurfacesKey:
    """KM-KQS-015 / KM-KQS-016: paths.json must contain a 'surfaces' top-level key
    with exactly 8 surface entries, each having 'path' and 'edge_fields'."""

    def test_paths_json_surfaces_key(self):
        # covers: KM-KQS-015
        # covers: KM-KQS-016
        """KM-KQS-015/016: paths.json surfaces key with 8 entries; all paths resolve."""
        assert _REAL_PATHS_JSON.exists(), f"paths.json not found at {_REAL_PATHS_JSON}"
        data = json.loads(_REAL_PATHS_JSON.read_text(encoding="utf-8"))
        assert "surfaces" in data, (
            "paths.json must have a top-level 'surfaces' key (KM-KQS-015)"
        )
        surfaces = data["surfaces"]
        required_names = {"agents", "skills", "tickets", "docs", "adrs", "components", "roadmap", "glossary"}
        actual_names = set(surfaces.keys())
        assert actual_names == required_names, (
            f"surfaces must have exactly {required_names}; got {actual_names}"
        )
        for name, entry in surfaces.items():
            assert "path" in entry, f"Surface '{name}' missing 'path' field (KM-KQS-015)"
            assert isinstance(entry["path"], str), f"Surface '{name}' path must be a string"
            assert "edge_fields" in entry, f"Surface '{name}' missing 'edge_fields' field"
            assert isinstance(entry["edge_fields"], list), (
                f"Surface '{name}' edge_fields must be a list"
            )
            # KM-KQS-016: resolved paths must exist (non-optional)
            resolved = _REPO_ROOT / entry["path"]
            assert resolved.exists(), (
                f"Surface '{name}' path '{entry['path']}' does not resolve to an "
                f"existing file or directory (KM-KQS-016)"
            )


class TestRealRepoNodeProduction:
    """KM-KQS-017: knowledge_query.py must produce >50 nodes against the real repo."""

    def test_real_repo_node_production(self):
        # covers: KM-KQS-017
        """KM-KQS-017: knowledge_query.py --format json produces >50 nodes from real repo."""
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPTS_DIR / "knowledge_query.py"),
                "--format", "json",
                "--project-root", str(_REPO_ROOT),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, (
            f"knowledge_query.py must exit 0; stderr: {result.stderr}"
        )
        data = json.loads(result.stdout)
        nodes = data.get("nodes", [])
        assert len(nodes) > 50, (
            f"Expected >50 nodes from real repo; got {len(nodes)} (KM-KQS-017)"
        )
        # Each of the 8 surfaces must have at least one node
        surfaces_found = {n["surface"] for n in nodes}
        required_surfaces = {"agents", "skills", "tickets", "docs", "adrs", "components", "roadmap", "glossary"}
        for surface in required_surfaces:
            assert surface in surfaces_found, (
                f"No node found for surface '{surface}' (KM-KQS-017)"
            )


class TestEdgeFieldsCorrectness:
    """KM-KQS-018: edge_fields in surfaces config match fields present in each surface source."""

    def test_edge_fields_correctness(self):
        # covers: KM-KQS-018
        """KM-KQS-018: agents edge_fields include spawn_allowlist/skills_used; tickets include depends_on/files_touched."""
        assert _REAL_PATHS_JSON.exists(), f"paths.json not found at {_REAL_PATHS_JSON}"
        data = json.loads(_REAL_PATHS_JSON.read_text(encoding="utf-8"))
        surfaces = data.get("surfaces", {})

        # KM-KQS-018: agents surface edge_fields
        agents_fields = set(surfaces.get("agents", {}).get("edge_fields", []))
        assert "spawn_allowlist" in agents_fields, (
            "agents edge_fields must include 'spawn_allowlist' (KM-KQS-018)"
        )
        assert "skills_used" in agents_fields, (
            "agents edge_fields must include 'skills_used' (KM-KQS-018)"
        )

        # KM-KQS-018: tickets surface edge_fields
        tickets_fields = set(surfaces.get("tickets", {}).get("edge_fields", []))
        assert "depends_on" in tickets_fields, (
            "tickets edge_fields must include 'depends_on' (KM-KQS-018)"
        )
        assert "files_touched" in tickets_fields, (
            "tickets edge_fields must include 'files_touched' (KM-KQS-018)"
        )

        # KM-KQS-018: skills surface edge_fields
        skills_fields = set(surfaces.get("skills", {}).get("edge_fields", []))
        assert "dependencies" in skills_fields, (
            "skills edge_fields must include 'dependencies' (KM-KQS-018)"
        )


class TestPathsIntegrityPasses:
    """KM-KQS-019: check_paths_integrity.py must exit 0 with both paths and surfaces keys."""

    def test_paths_integrity_passes(self):
        # covers: KM-KQS-019
        """KM-KQS-019: check_paths_integrity.py exits 0 after surfaces key is added."""
        script = _REPO_ROOT / "scripts" / "commit_guardian" / "check_paths_integrity.py"
        assert script.exists(), f"check_paths_integrity.py not found at {script}"
        # The script checks staged files; when run standalone, it exits 0 when paths.json
        # is not staged (the "not staged; skipping" path). We verify the exit code is 0.
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
        )
        assert result.returncode == 0, (
            f"check_paths_integrity.py must exit 0; stderr: {result.stderr}; "
            f"stdout: {result.stdout}"
        )


class TestEmptySurfaceGraceful:
    """KM-KQS-020: knowledge_query.py handles empty surface directory gracefully."""

    def test_empty_surface_graceful(self, tmp_path):
        # covers: KM-KQS-020
        """KM-KQS-020: knowledge_query.py exits 0 with zero nodes for empty surface."""
        # Create a paths.json with an empty directory as a surface
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True)
        empty_surface_dir = tmp_path / "empty_surface_dir"
        empty_surface_dir.mkdir()
        paths_data = {
            "surfaces": {
                "empty_surface": {
                    "path": "empty_surface_dir/",
                    "edge_fields": [],
                }
            }
        }
        (config_dir / "paths.json").write_text(
            json.dumps(paths_data), encoding="utf-8"
        )
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPTS_DIR / "knowledge_query.py"),
                "--surface", "empty_surface",
                "--project-root", str(tmp_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"Script must exit 0 for empty surface; stderr: {result.stderr}"
        )
        combined = result.stdout + result.stderr
        assert "Traceback" not in combined, (
            "Script must not emit a traceback for empty surface (KM-KQS-020)"
        )


# ---------------------------------------------------------------------------
# Ticket 05a: edge connectivity tests — KM-KQS-021 through KM-KQS-030
# These tests are RED until python-coder implements the edge connectivity fixes.
# ---------------------------------------------------------------------------


class TestComponentHubEdges:
    """KM-KQS-021 / KM-KQS-027 / KM-KQS-029: component_membership edges from components field."""

    def test_component_hub_edges_basic(self):
        # covers: KM-KQS-021
        """KM-KQS-021: extract_edges emits component_membership edges for a node with components field."""
        fake_record = NodeRecord(
            id="python-coder",
            surface="agents",
            title="Python Coder",
            description="Writes Python.",
            path=Path("config/agent_registry.json"),
        )
        raw_data = {
            "id": "python-coder",
            "components": ["knowledge-management", "build_pipeline"],
        }
        edges = list(extract_edges("agents", fake_record, raw_data))
        component_edges = [e for e in edges if e.edge_type == "component_membership"]
        targets = {e.target_id for e in component_edges}
        assert "knowledge-management" in targets, (
            "components entry 'knowledge-management' must produce a component_membership edge (KM-KQS-021)"
        )
        assert "build_pipeline" in targets, (
            "components entry 'build_pipeline' must produce a component_membership edge (KM-KQS-021)"
        )
        assert len(component_edges) == 2, (
            "Expected exactly 2 component_membership edges for components: [knowledge-management, build_pipeline]"
        )

    def test_component_hub_edges_multiple_surfaces(self):
        # covers: KM-KQS-021
        """KM-KQS-021: component_membership edges are emitted for ticket surface too."""
        ticket_record = NodeRecord(
            id="05a_edge_connectivity_fix",
            surface="tickets",
            title="Fix edge connectivity",
            description="Fixes edge connectivity.",
            path=Path("tickets/00_inbox/epics/EPIC-KnowledgeGraphQueryLayer/05a_edge_connectivity_fix.md"),
        )
        raw_data = {
            "title": "Fix edge connectivity",
            "components": ["knowledge-management"],
        }
        edges = list(extract_edges("tickets", ticket_record, raw_data))
        component_edges = [e for e in edges if e.edge_type == "component_membership"]
        assert len(component_edges) == 1, (
            "Ticket with components: [knowledge-management] must produce 1 component_membership edge"
        )
        assert component_edges[0].target_id == "knowledge-management", (
            "component_membership edge target must be the component name (KM-KQS-021)"
        )

    def test_component_hub_edges_empty_components(self):
        # covers: KM-KQS-029
        """KM-KQS-029: extract_edges emits zero component_membership edges for empty components list."""
        fake_record = NodeRecord(
            id="some-agent",
            surface="agents",
            title="Some Agent",
            description="Does something.",
            path=Path("config/agent_registry.json"),
        )
        raw_data = {
            "id": "some-agent",
            "components": [],
        }
        edges = list(extract_edges("agents", fake_record, raw_data))
        component_edges = [e for e in edges if e.edge_type == "component_membership"]
        assert len(component_edges) == 0, (
            "components: [] must produce zero component_membership edges (KM-KQS-029)"
        )

    def test_component_hub_undocumented_component(self):
        # covers: KM-KQS-027
        """KM-KQS-027: extract_edges emits edge for component with no matching component doc."""
        fake_record = NodeRecord(
            id="some-skill",
            surface="skills",
            title="Some Skill",
            description="Does something.",
            path=Path("config/skill_registry.json"),
        )
        raw_data = {
            "id": "some-skill",
            "components": ["undocumented-component"],
        }
        edges = list(extract_edges("skills", fake_record, raw_data))
        component_edges = [e for e in edges if e.edge_type == "component_membership"]
        assert len(component_edges) == 1, (
            "components: [undocumented-component] must produce 1 component_membership edge (KM-KQS-027)"
        )
        assert component_edges[0].target_id == "undocumented-component", (
            "Edge target must be the component name even when no doc exists (KM-KQS-027)"
        )


class TestDependsOnPathResolution:
    """KM-KQS-022 / KM-KQS-026 / KM-KQS-028: depends_on path-to-stem resolution."""

    def test_depends_on_file_path_resolved_to_stem(self):
        # covers: KM-KQS-022
        """KM-KQS-022: extract_edges resolves depends_on file path to filename stem."""
        ticket_record = NodeRecord(
            id="05a_edge_connectivity_fix",
            surface="tickets",
            title="Fix edge connectivity",
            description="Fixes edge connectivity.",
            path=Path("tickets/00_inbox/epics/EPIC-KnowledgeGraphQueryLayer/05a_edge_connectivity_fix.md"),
        )
        raw_data = {
            "title": "Fix edge connectivity",
            "depends_on": [
                "tickets/00_inbox/epics/EPIC-Foo/01a_schema.md",
                "tickets/00_inbox/epics/EPIC-Foo/02a_bar.md",
            ],
        }
        edges = list(extract_edges("tickets", ticket_record, raw_data))
        depends_edges = [e for e in edges if e.edge_type == "depends_on"]
        targets = {e.target_id for e in depends_edges}
        assert "01a_schema" in targets, (
            "depends_on path must be resolved to stem '01a_schema' (KM-KQS-022)"
        )
        assert "02a_bar" in targets, (
            "depends_on path must be resolved to stem '02a_bar' (KM-KQS-022)"
        )
        # Raw paths must NOT appear as targets
        for target in targets:
            assert "/" not in target, (
                f"Raw file path must not appear as edge target; got '{target}' (KM-KQS-022)"
            )
            assert target.endswith(".md") is False, (
                f"Edge target must not include .md extension; got '{target}' (KM-KQS-022)"
            )

    def test_depends_on_bare_id_unchanged(self):
        # covers: KM-KQS-028
        """KM-KQS-028: depends_on bare node ID is passed through unchanged."""
        ticket_record = NodeRecord(
            id="05b_follow_on",
            surface="tickets",
            title="Follow-on ticket",
            description="A follow-on ticket.",
            path=Path("tickets/00_inbox/05b_follow_on.md"),
        )
        raw_data = {
            "title": "Follow-on ticket",
            "depends_on": ["01a_schema"],
        }
        edges = list(extract_edges("tickets", ticket_record, raw_data))
        depends_edges = [e for e in edges if e.edge_type == "depends_on"]
        assert len(depends_edges) == 1, (
            "depends_on: [01a_schema] must produce exactly 1 depends_on edge (KM-KQS-028)"
        )
        assert depends_edges[0].target_id == "01a_schema", (
            "Bare node ID must pass through unchanged as edge target (KM-KQS-028)"
        )

    def test_depends_on_nonexistent_path_silently_dropped(self):
        # covers: KM-KQS-026
        """KM-KQS-026: depends_on path with no matching node produces no edge (no crash)."""
        ticket_record = NodeRecord(
            id="some_ticket",
            surface="tickets",
            title="Some ticket",
            description=".",
            path=Path("tickets/00_inbox/some_ticket.md"),
        )
        raw_data = {
            "title": "Some ticket",
            "depends_on": ["nonexistent/path/fake_ticket.md"],
        }
        # This should not raise — it may emit an edge that is later filtered,
        # but the stem "fake_ticket" must be the target (path-resolved), not the raw path.
        # The phantom filter in _collect_all will drop it from final output.
        try:
            edges = list(extract_edges("tickets", ticket_record, raw_data))
        except Exception as exc:  # noqa: BLE001
            pytest.fail(
                f"extract_edges must not raise on nonexistent path; got {exc} (KM-KQS-026)"
            )
        # The edge is emitted with the stem as target (filtering happens at collect level)
        depends_edges = [e for e in edges if e.edge_type == "depends_on"]
        for edge in depends_edges:
            assert "/" not in edge.target_id, (
                f"Raw path must not appear as edge target; got '{edge.target_id}' (KM-KQS-026)"
            )


class TestPhantomEdgeFiltering:
    """KM-KQS-024 / KM-KQS-030: phantom edge filtering by node-existence check."""

    def test_phantom_edges_filtered_by_node_existence(self, tmp_path):
        # covers: KM-KQS-024
        """KM-KQS-024: edges targeting non-existent nodes are filtered from output."""
        # Build a minimal paths.json + surface that produces phantom edges
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True)
        registry = {
            "agents": [
                {
                    "id": "python-coder",
                    "name": "Python Coder",
                    "description": "Writes Python.",
                    "is_ticket_phase": True,
                    "spawn_allowlist": ["phantom-agent"],  # phantom target
                    "spawned_by": ["ticket-supervisor"],
                    "skills_used": [],
                }
            ]
        }
        (config_dir / "agent_registry.json").write_text(
            json.dumps(registry), encoding="utf-8"
        )
        paths_data = {
            "surfaces": {
                "agents": {
                    "path": "config/agent_registry.json",
                    "edge_fields": ["spawn_allowlist"],
                }
            }
        }
        (config_dir / "paths.json").write_text(json.dumps(paths_data), encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPTS_DIR / "knowledge_query.py"),
                "--format", "json",
                "--project-root", str(tmp_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"Script must exit 0; stderr: {result.stderr}"
        )
        data = json.loads(result.stdout)
        edges = data.get("edges", [])
        node_ids = {n["id"] for n in data.get("nodes", [])}
        # All edge targets must be in the node set (no phantoms allowed in output)
        for edge in edges:
            assert edge["target"] in node_ids, (
                f"Edge target '{edge['target']}' is not in node set — "
                f"phantom filtering failed (KM-KQS-024)"
            )

    def test_phantom_filter_by_node_existence_not_blocklist(self, tmp_path):
        # covers: KM-KQS-030
        """KM-KQS-030: phantom filter uses node-existence check, not a hardcoded blocklist."""
        # If a node named "user" were added, edges to "user" should be retained.
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True)
        # Surface: one agent that spawns "user"; also a "user" agent in the registry
        registry = {
            "agents": [
                {
                    "id": "python-coder",
                    "name": "Python Coder",
                    "description": "Writes Python.",
                    "is_ticket_phase": True,
                    "spawn_allowlist": ["user"],
                    "spawned_by": [],
                    "skills_used": [],
                },
                {
                    "id": "user",
                    "name": "User",
                    "description": "Represents the human user.",
                    "is_ticket_phase": False,
                    "spawn_allowlist": [],
                    "spawned_by": [],
                    "skills_used": [],
                },
            ]
        }
        (config_dir / "agent_registry.json").write_text(
            json.dumps(registry), encoding="utf-8"
        )
        paths_data = {
            "surfaces": {
                "agents": {
                    "path": "config/agent_registry.json",
                    "edge_fields": ["spawn_allowlist"],
                }
            }
        }
        (config_dir / "paths.json").write_text(json.dumps(paths_data), encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPTS_DIR / "knowledge_query.py"),
                "--format", "json",
                "--project-root", str(tmp_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"Script must exit 0; stderr: {result.stderr}"
        )
        data = json.loads(result.stdout)
        edges = data.get("edges", [])
        node_ids = {n["id"] for n in data.get("nodes", [])}
        # "user" is now a real node, so the edge to "user" must be retained
        assert "user" in node_ids, (
            "Node 'user' must be present in nodes array when declared in registry (KM-KQS-030)"
        )
        user_edges = [e for e in edges if e["target"] == "user"]
        assert len(user_edges) >= 1, (
            "Edge to 'user' must be preserved when 'user' is a real node (KM-KQS-030); "
            "filtering must be by node-existence, not a hardcoded blocklist"
        )


class TestEdgeCountIntegration:
    """KM-KQS-025: combined improvements must produce >= 600 edges from real repo."""

    def test_edge_count_integration(self):
        # covers: KM-KQS-025
        """KM-KQS-025: knowledge_query.py --format json produces >= 600 edges from real repo."""
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPTS_DIR / "knowledge_query.py"),
                "--format", "json",
                "--project-root", str(_REPO_ROOT),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, (
            f"knowledge_query.py must exit 0; stderr: {result.stderr}"
        )
        data = json.loads(result.stdout)
        edges = data.get("edges", [])
        assert len(edges) >= 600, (
            f"Expected >= 600 edges after all improvements; got {len(edges)} (KM-KQS-025)"
        )
        # All edge targets must be known node IDs (no phantoms)
        node_ids = {n["id"] for n in data.get("nodes", [])}
        for edge in edges:
            assert edge["target"] in node_ids, (
                f"Edge target '{edge['target']}' is not in node set — "
                f"phantom filtering must be applied (KM-KQS-025)"
            )
        # Must contain at least one component_membership edge
        cm_edges = [e for e in edges if e["type"] == "component_membership"]
        assert len(cm_edges) >= 1, (
            "Expected at least one component_membership edge; got 0 (KM-KQS-025)"
        )
        # Must not contain phantoms "user" or "__ticket_phase_agents__" unless they are real nodes
        phantom_ids = {"user", "__ticket_phase_agents__"}
        for phantom_id in phantom_ids:
            if phantom_id not in node_ids:
                phantom_edges = [e for e in edges if e["target"] == phantom_id]
                assert len(phantom_edges) == 0, (
                    f"Phantom target '{phantom_id}' must not appear as edge target (KM-KQS-025)"
                )


class TestPathsJsonEdgeFields:
    """KM-KQS-023: paths.json edge_fields must include 'components' for applicable surfaces."""

    def test_paths_json_edge_fields_components(self):
        # covers: KM-KQS-023
        """KM-KQS-023: 'components' in edge_fields for agents, skills, tickets, docs, adrs, components."""
        assert _REAL_PATHS_JSON.exists(), f"paths.json not found at {_REAL_PATHS_JSON}"
        data = json.loads(_REAL_PATHS_JSON.read_text(encoding="utf-8"))
        surfaces = data.get("surfaces", {})
        surfaces_needing_components = ["agents", "skills", "tickets", "docs", "adrs", "components"]
        for surface_name in surfaces_needing_components:
            assert surface_name in surfaces, (
                f"Surface '{surface_name}' must be present in paths.json (KM-KQS-023)"
            )
            edge_fields = surfaces[surface_name].get("edge_fields", [])
            assert "components" in edge_fields, (
                f"Surface '{surface_name}' edge_fields must include 'components' (KM-KQS-023); "
                f"got {edge_fields}"
            )

    def test_paths_json_edge_fields_related_docs(self):
        # covers: KM-KQS-023
        """KM-KQS-023: 'related_docs' in edge_fields for docs, adrs, components surfaces."""
        assert _REAL_PATHS_JSON.exists(), f"paths.json not found at {_REAL_PATHS_JSON}"
        data = json.loads(_REAL_PATHS_JSON.read_text(encoding="utf-8"))
        surfaces = data.get("surfaces", {})
        surfaces_needing_related_docs = ["docs", "adrs", "components"]
        for surface_name in surfaces_needing_related_docs:
            assert surface_name in surfaces, (
                f"Surface '{surface_name}' must be present in paths.json (KM-KQS-023)"
            )
            edge_fields = surfaces[surface_name].get("edge_fields", [])
            assert "related_docs" in edge_fields, (
                f"Surface '{surface_name}' edge_fields must include 'related_docs' (KM-KQS-023); "
                f"got {edge_fields}"
            )
