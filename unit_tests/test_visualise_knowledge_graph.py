"""
Tests for visualise_knowledge_graph.py — core HTML generation and D3.js data embedding.

These tests are written BEFORE the implementation (TDD / test-first).
All tests are expected to be RED until python-coder delivers the implementation.
"""
from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Module loader helper — mirrors the pattern the script itself will use.
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
_MODULE_PATH = _SCRIPTS_DIR / "visualise_knowledge_graph.py"


class _ModuleNotBuiltError(ImportError):
    """Raised when visualise_knowledge_graph.py has not been created yet."""


def _load_module():
    """Dynamically load visualise_knowledge_graph.py from scripts/."""
    if not _MODULE_PATH.exists():
        raise _ModuleNotBuiltError(str(_MODULE_PATH))
    spec = importlib.util.spec_from_file_location("visualise_knowledge_graph", _MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Shared mock factory for knowledge_query module
# ---------------------------------------------------------------------------

def _make_mock_kq(nodes=None, edges=None):
    """Return a mock knowledge_query module with controllable outputs."""
    if nodes is None:
        nodes = []
    if edges is None:
        edges = []

    mock_kq = MagicMock()
    mock_kq.load_surfaces.return_value = {"agents": Path("/fake/agents")}
    mock_kq.extract_nodes.return_value = iter(nodes)
    mock_kq.extract_edges.return_value = iter(edges)

    # NodeRecord and EdgeRecord as simple namedtuple-like objects
    mock_kq.NodeRecord = MagicMock
    mock_kq.EdgeRecord = MagicMock

    return mock_kq


# ---------------------------------------------------------------------------
# Helper: build a fake NodeRecord
# ---------------------------------------------------------------------------

def _node(id_, surface, title):
    """Return a simple namespace object that looks like a NodeRecord."""
    n = MagicMock()
    n.id = id_
    n.surface = surface
    n.title = title
    n.description = f"Description of {id_}"
    n.path = Path(f"/fake/{surface}/{id_}.md")
    return n


def _edge(source_id, target_id, edge_type):
    """Return a simple namespace object that looks like an EdgeRecord."""
    e = MagicMock()
    e.source_id = source_id
    e.target_id = target_id
    e.edge_type = edge_type
    return e


# ---------------------------------------------------------------------------
# AC-7 Tests (test-writer ACs)
# ---------------------------------------------------------------------------


class TestWritesHtmlFile(unittest.TestCase):
    """AC-7: test_writes_html_file — output file exists and is valid HTML."""

    def test_writes_html_file(self):
        # covers: UNKNOWN
        """AC-1: Running with --no-open writes a file containing <!DOCTYPE html>."""
        mod = _load_module()

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
            output_path = tmp.name

        mock_kq = _make_mock_kq(nodes=[_node("agent-1", "agents", "Agent One")])

        with patch.object(mod, "_load_kq_module", return_value=mock_kq):
            try:
                mod.main(["--output", output_path, "--no-open"])
            except SystemExit as exc:
                self.assertEqual(exc.code, 0, f"Script exited with code {exc.code}")

        content = Path(output_path).read_text(encoding="utf-8")
        self.assertIn("<!DOCTYPE html>", content)
        Path(output_path).unlink(missing_ok=True)


class TestEmbeddedJsonValid(unittest.TestCase):
    """AC-7: test_embedded_json_valid — embedded DATA block is valid JSON."""

    def test_embedded_json_valid(self):
        # covers: UNKNOWN
        """AC-2: Embedded JSON contains nodes and edges keys."""
        mod = _load_module()

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
            output_path = tmp.name

        mock_kq = _make_mock_kq(
            nodes=[_node("agent-1", "agents", "Agent One")],
            edges=[_edge("agent-1", "skill-1", "skills_used")],
        )

        with patch.object(mod, "_load_kq_module", return_value=mock_kq):
            try:
                mod.main(["--output", output_path, "--no-open"])
            except SystemExit as exc:
                self.assertEqual(exc.code, 0, f"Script exited with code {exc.code}")

        content = Path(output_path).read_text(encoding="utf-8")

        # Find the const DATA = ... line in the HTML
        match = re.search(r"const DATA\s*=\s*(\{.*?\});", content, re.DOTALL)
        self.assertIsNotNone(match, "Could not find 'const DATA = ...' block in HTML")

        data = json.loads(match.group(1))
        self.assertIn("nodes", data)
        self.assertIn("edges", data)
        self.assertIsInstance(data["nodes"], list)
        self.assertIsInstance(data["edges"], list)

        Path(output_path).unlink(missing_ok=True)


class TestNodesHaveColorField(unittest.TestCase):
    """AC-7: test_nodes_have_color_field — agent nodes have correct teal color."""

    def test_nodes_have_color_field(self):
        # covers: UNKNOWN
        """AC-2: Every node has a color field derived from SURFACE_COLORS."""
        mod = _load_module()

        # Verify SURFACE_COLORS is a public constant
        self.assertTrue(
            hasattr(mod, "SURFACE_COLORS"),
            "visualise_knowledge_graph must export SURFACE_COLORS dict",
        )

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
            output_path = tmp.name

        mock_kq = _make_mock_kq(nodes=[_node("agent-1", "agent", "Agent One")])

        with patch.object(mod, "_load_kq_module", return_value=mock_kq):
            try:
                mod.main(["--output", output_path, "--no-open"])
            except SystemExit as exc:
                self.assertEqual(exc.code, 0, f"Script exited with code {exc.code}")

        content = Path(output_path).read_text(encoding="utf-8")
        match = re.search(r"const DATA\s*=\s*(\{.*?\});", content, re.DOTALL)
        self.assertIsNotNone(match)

        data = json.loads(match.group(1))
        self.assertTrue(len(data["nodes"]) > 0, "Expected at least one node")
        node = data["nodes"][0]
        self.assertIn("color", node, "Node must have 'color' field")
        self.assertEqual(
            node["color"],
            mod.SURFACE_COLORS["agent"],
            f"Agent node color should be {mod.SURFACE_COLORS['agent']}",
        )

        Path(output_path).unlink(missing_ok=True)


class TestNoD3DownloadInScript(unittest.TestCase):
    """AC-7: test_no_d3_download_in_script — script does not download D3 at runtime."""

    def test_no_d3_download_in_script(self):
        # covers: UNKNOWN
        """AC-3: The script does not import urllib, requests, or http.client."""
        source = _MODULE_PATH.read_text(encoding="utf-8")

        forbidden_patterns = [
            r"\bimport urllib\b",
            r"\bfrom urllib\b",
            r"\bimport requests\b",
            r"\bfrom requests\b",
            r"\bimport http\.client\b",
            r"\bfrom http\.client\b",
        ]
        for pattern in forbidden_patterns:
            self.assertIsNone(
                re.search(pattern, source),
                f"visualise_knowledge_graph.py must not import '{pattern}' "
                "(D3 is referenced from CDN in HTML template, not downloaded by Python).",
            )


class TestMissingKqModuleExitsCleanly(unittest.TestCase):
    """AC-7: test_missing_kq_module_exits_cleanly — clean error when knowledge_query.py absent."""

    def test_missing_kq_module_exits_cleanly(self):
        # covers: UNKNOWN
        """AC-5: When knowledge_query.py is missing, exits with clean error message."""
        mod = _load_module()

        # Patch the module loader to simulate FileNotFoundError
        with patch.object(mod, "_load_kq_module", side_effect=FileNotFoundError("no such file")):
            import io
            from contextlib import redirect_stderr, redirect_stdout
            captured_stdout = io.StringIO()
            captured_stderr = io.StringIO()

            with self.assertRaises(SystemExit) as ctx:
                with redirect_stdout(captured_stdout):
                    with redirect_stderr(captured_stderr):
                        mod.main(["--no-open"])

            self.assertEqual(ctx.exception.code, 1, "Script should exit with code 1 when kq module missing")

            output = captured_stdout.getvalue() + captured_stderr.getvalue()
            self.assertIn(
                "knowledge_query.py not found",
                output,
                f"Expected 'knowledge_query.py not found' in output. Got: {output!r}",
            )
            # No Python traceback should appear
            self.assertNotIn(
                "Traceback",
                output,
                "Script must not show a Python traceback when knowledge_query.py is missing.",
            )


# ---------------------------------------------------------------------------
# Additional structural tests (AC-1 through AC-6)
# ---------------------------------------------------------------------------


class TestNodeStructure(unittest.TestCase):
    """Verify node records have id, surface, title, and color fields (AC-2)."""

    def test_embedded_nodes_have_required_fields(self):
        # covers: UNKNOWN
        """AC-2: Every embedded node has id, surface, title, and color."""
        mod = _load_module()

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
            output_path = tmp.name

        mock_kq = _make_mock_kq(
            nodes=[
                _node("ticket-1", "ticket", "My Ticket"),
                _node("doc-1", "doc", "My Doc"),
            ]
        )

        with patch.object(mod, "_load_kq_module", return_value=mock_kq):
            try:
                mod.main(["--output", output_path, "--no-open"])
            except SystemExit as exc:
                self.assertEqual(exc.code, 0)

        content = Path(output_path).read_text(encoding="utf-8")
        match = re.search(r"const DATA\s*=\s*(\{.*?\});", content, re.DOTALL)
        self.assertIsNotNone(match)

        data = json.loads(match.group(1))
        for node in data["nodes"]:
            for field in ("id", "surface", "title", "color"):
                self.assertIn(field, node, f"Node missing required field: {field}")

        Path(output_path).unlink(missing_ok=True)


class TestEdgeStructure(unittest.TestCase):
    """Verify edge records have source, target, and type fields (AC-2)."""

    def test_embedded_edges_have_required_fields(self):
        # covers: UNKNOWN
        """AC-2: Every embedded edge has source, target, and type."""
        mod = _load_module()

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
            output_path = tmp.name

        mock_kq = _make_mock_kq(
            nodes=[_node("agent-1", "agent", "A1"), _node("skill-1", "skill", "S1")],
            edges=[_edge("agent-1", "skill-1", "skills_used")],
        )

        with patch.object(mod, "_load_kq_module", return_value=mock_kq):
            try:
                mod.main(["--output", output_path, "--no-open"])
            except SystemExit as exc:
                self.assertEqual(exc.code, 0)

        content = Path(output_path).read_text(encoding="utf-8")
        match = re.search(r"const DATA\s*=\s*(\{.*?\});", content, re.DOTALL)
        self.assertIsNotNone(match)

        data = json.loads(match.group(1))
        for edge in data["edges"]:
            for field in ("source", "target", "type"):
                self.assertIn(field, edge, f"Edge missing required field: {field}")

        Path(output_path).unlink(missing_ok=True)


class TestD3CdnReference(unittest.TestCase):
    """Verify D3 is referenced from CDN (AC-3)."""

    def test_html_references_d3_cdn(self):
        # covers: UNKNOWN
        """AC-3: Generated HTML references D3 from d3js.org CDN."""
        mod = _load_module()

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
            output_path = tmp.name

        mock_kq = _make_mock_kq()

        with patch.object(mod, "_load_kq_module", return_value=mock_kq):
            try:
                mod.main(["--output", output_path, "--no-open"])
            except SystemExit as exc:
                self.assertEqual(exc.code, 0)

        content = Path(output_path).read_text(encoding="utf-8")
        self.assertIn(
            "d3js.org/d3.v7.min.js",
            content,
            "HTML must reference D3.js from https://d3js.org/d3.v7.min.js",
        )
        Path(output_path).unlink(missing_ok=True)


class TestImportlibUsePattern(unittest.TestCase):
    """Verify the module uses importlib.util pattern (AC-6)."""

    def test_uses_importlib_pattern(self):
        # covers: UNKNOWN
        """AC-6: Script uses importlib.util.spec_from_file_location, not sys.path manipulation."""
        source = _MODULE_PATH.read_text(encoding="utf-8")

        self.assertIn(
            "spec_from_file_location",
            source,
            "Must use importlib.util.spec_from_file_location to load knowledge_query.py",
        )
        self.assertIn(
            "module_from_spec",
            source,
            "Must use importlib.util.module_from_spec to load knowledge_query.py",
        )

        # Should NOT use sys.path manipulation
        self.assertNotIn(
            "sys.path.insert",
            source,
            "Must not use sys.path.insert — use importlib.util pattern instead.",
        )
        self.assertNotIn(
            "sys.path.append",
            source,
            "Must not use sys.path.append — use importlib.util pattern instead.",
        )


class TestSurfaceColorsConstant(unittest.TestCase):
    """Verify SURFACE_COLORS constant maps surface names to hex colors (AC-2)."""

    def test_surface_colors_has_required_entries(self):
        # covers: UNKNOWN
        """AC-2: SURFACE_COLORS includes all required surface types."""
        mod = _load_module()

        self.assertTrue(hasattr(mod, "SURFACE_COLORS"), "Missing SURFACE_COLORS constant")
        colors = mod.SURFACE_COLORS

        required_surfaces = {"agent", "skill", "ticket", "doc", "adr", "component", "roadmap", "glossary"}
        for surface in required_surfaces:
            self.assertIn(surface, colors, f"SURFACE_COLORS missing entry for surface: {surface}")

        # Verify all values are hex color strings
        hex_pattern = re.compile(r"^#[0-9a-fA-F]{6}$")
        for surface, color in colors.items():
            self.assertTrue(
                hex_pattern.match(color),
                f"SURFACE_COLORS['{surface}'] = {color!r} is not a valid hex color",
            )

    def test_agent_color_is_teal(self):
        # covers: UNKNOWN
        """AC-2: Agent surface color is teal (#2dd4bf)."""
        mod = _load_module()
        self.assertEqual(mod.SURFACE_COLORS.get("agent"), "#2dd4bf")

    def test_skill_color_is_red(self):
        # covers: UNKNOWN
        """AC-2: Skill surface color is red (#f87171)."""
        mod = _load_module()
        self.assertEqual(mod.SURFACE_COLORS.get("skill"), "#f87171")

    def test_ticket_color_is_yellow(self):
        # covers: UNKNOWN
        """AC-2: Ticket surface color is yellow (#fbbf24)."""
        mod = _load_module()
        self.assertEqual(mod.SURFACE_COLORS.get("ticket"), "#fbbf24")


# ---------------------------------------------------------------------------
# Ticket 03b Tests — --surface and --project-root CLI flags
# ---------------------------------------------------------------------------


class TestSurfaceFilterExcludesOthers(unittest.TestCase):
    """AC-1: --surface flag filters graph to only named surfaces.

    test_surface_filter_excludes_others: call with --surface agents, mock
    data with agent and ticket nodes, assert only agent nodes in embedded JSON.
    """

    def test_surface_filter_excludes_others(self):
        # covers: UNKNOWN
        """AC-1: Running with --surface agents produces a graph with only agent nodes."""
        import tempfile
        mod = _load_module()

        # Mock data: one agent node and one ticket node
        agent_node = _node("agent-1", "agents", "Agent One")
        ticket_node = _node("ticket-1", "tickets", "Ticket One")

        mock_kq = _make_mock_kq(nodes=[agent_node, ticket_node])

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
            output_path = tmp.name

        with patch.object(mod, "_load_kq_module", return_value=mock_kq):
            try:
                mod.main(["--output", output_path, "--no-open", "--surface", "agents"])
            except SystemExit as exc:
                self.assertEqual(exc.code, 0, f"Script exited with code {exc.code}")

        content = Path(output_path).read_text(encoding="utf-8")
        match = re.search(r"const DATA\s*=\s*(\{.*?\});", content, re.DOTALL)
        self.assertIsNotNone(match, "Could not find 'const DATA = ...' block in HTML")

        data = json.loads(match.group(1))
        node_ids = [n["id"] for n in data["nodes"]]

        # agent-1 should be present; ticket-1 should be absent
        self.assertIn("agent-1", node_ids, "Agent node must be present when --surface agents given")
        self.assertNotIn(
            "ticket-1",
            node_ids,
            "Ticket node must be excluded when --surface agents specified",
        )

        Path(output_path).unlink(missing_ok=True)


class TestProjectRootFlagPassedToKq(unittest.TestCase):
    """AC-2: --project-root flag passes the path to load_surfaces().

    test_project_root_flag_passed_to_kq: mock load_surfaces, assert it is
    called with the value passed to --project-root.
    """

    def test_project_root_flag_passed_to_kq(self):
        # covers: UNKNOWN
        """AC-2: --project-root value is passed to kq.load_surfaces() as project_root."""
        import tempfile
        mod = _load_module()

        mock_kq = _make_mock_kq()
        # Patch load_surfaces so we can inspect the call args
        mock_kq.load_surfaces.return_value = {}

        custom_root = "/custom/project/root"

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
            output_path = tmp.name

        with patch.object(mod, "_load_kq_module", return_value=mock_kq):
            try:
                mod.main([
                    "--output", output_path,
                    "--no-open",
                    "--project-root", custom_root,
                ])
            except SystemExit as exc:
                self.assertEqual(exc.code, 0, f"Script exited with code {exc.code}")

        # Verify load_surfaces was called with the custom project_root
        self.assertTrue(
            mock_kq.load_surfaces.called,
            "load_surfaces() must be called when --project-root is passed",
        )

        call_kwargs = mock_kq.load_surfaces.call_args

        # Accept both positional and keyword argument forms
        call_args_list = call_kwargs[0] if call_kwargs[0] else []
        call_kwargs_dict = call_kwargs[1] if call_kwargs[1] else {}

        custom_path = Path(custom_root)
        found_root = False
        if call_args_list and Path(str(call_args_list[0])) == custom_path:
            found_root = True
        if "project_root" in call_kwargs_dict and Path(str(call_kwargs_dict["project_root"])) == custom_path:
            found_root = True

        self.assertTrue(
            found_root,
            f"load_surfaces() must be called with project_root={custom_root!r}. "
            f"Actual call args: {call_kwargs}",
        )

        Path(output_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
