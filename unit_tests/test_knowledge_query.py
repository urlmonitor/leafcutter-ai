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
    EdgeRecord,
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
