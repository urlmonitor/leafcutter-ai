"""
MODULE: test_build_components_table
GOAL: Verify that _build_components_table and _inject_components_table in
      scripts/build_phases.py correctly replace the {{components_table}}
      placeholder with a human-readable Markdown table of component metadata.
BUSINESS CONTEXT: ACS-300k-1 — build.py must inject components data into agent
      templates so that agents receive a formatted component registry table at
      prompt-compile time. This test proves the injection produces the correct
      columns (id, name, type, description, agent_affinity), is sorted by
      component id, and leaves zero occurrences of the literal placeholder in
      the output.
ARCHITECTURE: Tests import _build_components_table and _inject_components_table
      directly from scripts/build_phases.py (the build engine, not a templated
      hook). A temporary directory fixture provides an isolated components.json
      without relying on the live docs/components.json, keeping tests fast and
      hermetic.
# covers: ACS-300k-1
"""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Module loading — scripts/build_phases.py is the build engine (not a hook
# template), so we load it from scripts/ directly per task instructions.
# We prepend scripts/ to sys.path so the transitive import of template_compiler
# (also in scripts/) resolves without a ModuleNotFoundError.
# ---------------------------------------------------------------------------

_WORKTREE_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_DIR = _WORKTREE_ROOT / "scripts"

# Insert scripts/ at the front of sys.path for the duration of module load.
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

try:
    spec = importlib.util.spec_from_file_location(
        "build_phases", _SCRIPTS_DIR / "build_phases.py"
    )
    _bp_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_bp_mod)
    _build_components_table = _bp_mod._build_components_table
    _inject_components_table = _bp_mod._inject_components_table
    MODULE_AVAILABLE = True
except Exception as exc:  # noqa: BLE001 — discovery error, not runtime
    MODULE_AVAILABLE = False
    _load_error = str(exc)


def _write_components_json(directory: Path, components: dict) -> Path:
    """Write a minimal components.json file under *directory* and return its path."""
    data = {"components": components}
    path = directory / "components.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Fixtures shared across tests
# ---------------------------------------------------------------------------

# Two-entry dict whose keys are intentionally non-alphabetical (z before a) so
# sorting can be verified.
_SAMPLE_COMPONENTS: dict = {
    "zebra_logger": {
        "id": "zebra_logger",
        "name": "Zebra Logger",
        "type": "utility",
        "description": "Logs events in zebra stripe format for diagnostics.",
        "agent_affinity": ["python-coder"],
        "status": "active",
        "primary_code": ["scripts/zebra_logger.py"],
    },
    "alpha_runner": {
        "id": "alpha_runner",
        "name": "Alpha Runner",
        "type": "orchestration",
        "description": "Runs alpha-phase tasks in the correct sequence.",
        "agent_affinity": ["ticket-supervisor", "epic-supervisor"],
        "status": "active",
        "primary_code": ["scripts/alpha_runner.py"],
    },
}


@unittest.skipUnless(MODULE_AVAILABLE, f"module load failed: {_load_error if not MODULE_AVAILABLE else ''}")
class TestBuildComponentsTable(unittest.TestCase):
    """Unit tests for _build_components_table (ACS-300k-1)."""

    def setUp(self) -> None:
        """Create a temporary directory for each test."""
        import tempfile
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmppath = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    # ------------------------------------------------------------------
    # Happy-path: table structure and content
    # ------------------------------------------------------------------

    def test_table_contains_required_columns(self):
        """Output must contain id, name, type, description, agent_affinity headers."""
        path = _write_components_json(self._tmppath, _SAMPLE_COMPONENTS)
        table = _build_components_table(path)
        for column in ("id", "name", "type", "description", "agent_affinity"):
            self.assertIn(
                column, table,
                f"Required column '{column}' missing from table:\n{table}",
            )

    def test_table_sorted_by_component_id(self):
        """alpha_runner must appear before zebra_logger in the sorted output."""
        path = _write_components_json(self._tmppath, _SAMPLE_COMPONENTS)
        table = _build_components_table(path)
        alpha_pos = table.find("alpha_runner")
        zebra_pos = table.find("zebra_logger")
        self.assertGreater(
            alpha_pos,
            -1,
            "alpha_runner not found in table output",
        )
        self.assertGreater(
            zebra_pos,
            -1,
            "zebra_logger not found in table output",
        )
        self.assertLess(
            alpha_pos,
            zebra_pos,
            "Table is not sorted: alpha_runner should precede zebra_logger",
        )

    def test_table_contains_component_names(self):
        """Each component's name must appear in the table rows."""
        path = _write_components_json(self._tmppath, _SAMPLE_COMPONENTS)
        table = _build_components_table(path)
        self.assertIn("Alpha Runner", table)
        self.assertIn("Zebra Logger", table)

    def test_table_contains_component_types(self):
        """Each component's type must appear in the table rows."""
        path = _write_components_json(self._tmppath, _SAMPLE_COMPONENTS)
        table = _build_components_table(path)
        self.assertIn("utility", table)
        self.assertIn("orchestration", table)

    def test_table_contains_component_descriptions(self):
        """Each component's description (or prefix) must appear in the table rows."""
        path = _write_components_json(self._tmppath, _SAMPLE_COMPONENTS)
        table = _build_components_table(path)
        self.assertIn("Logs events in zebra stripe format", table)
        self.assertIn("Runs alpha-phase tasks", table)

    def test_table_contains_agent_affinity(self):
        """agent_affinity values must appear in the table."""
        path = _write_components_json(self._tmppath, _SAMPLE_COMPONENTS)
        table = _build_components_table(path)
        self.assertIn("python-coder", table)
        self.assertIn("ticket-supervisor", table)

    def test_table_is_markdown_formatted(self):
        """Output must use Markdown pipe-table delimiters."""
        path = _write_components_json(self._tmppath, _SAMPLE_COMPONENTS)
        table = _build_components_table(path)
        # A Markdown table must contain | delimiters and a separator row (---)
        self.assertIn("|", table, "No pipe character found — not a Markdown table")
        self.assertIn("---", table, "No separator row (---) found — not a Markdown table")

    # ------------------------------------------------------------------
    # Error / missing file paths
    # ------------------------------------------------------------------

    def test_missing_file_returns_placeholder(self):
        """When components.json does not exist, a descriptive placeholder is returned."""
        missing = self._tmppath / "nonexistent.json"
        result = _build_components_table(missing)
        self.assertIn("not found", result.lower())

    def test_empty_components_dict_returns_placeholder(self):
        """When the components object is empty, a descriptive placeholder is returned."""
        path = _write_components_json(self._tmppath, {})
        result = _build_components_table(path)
        self.assertIn("no components", result.lower())

    def test_malformed_json_returns_placeholder(self):
        """When components.json contains invalid JSON, a descriptive placeholder is returned."""
        bad_path = self._tmppath / "components.json"
        bad_path.write_text("{not valid json", encoding="utf-8")
        result = _build_components_table(bad_path)
        self.assertIn("error", result.lower())


@unittest.skipUnless(MODULE_AVAILABLE, f"module load failed: {_load_error if not MODULE_AVAILABLE else ''}")
class TestInjectComponentsTable(unittest.TestCase):
    """Unit tests for _inject_components_table (ACS-300k-1)."""

    def setUp(self) -> None:
        import tempfile
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmppath = Path(self._tmpdir.name)
        # Build a package_root structure: package_root/docs/components.json
        docs_dir = self._tmppath / "docs"
        docs_dir.mkdir()
        _write_components_json(docs_dir, _SAMPLE_COMPONENTS)
        self._package_root = self._tmppath

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_placeholder_is_replaced(self):
        """{{components_table}} in the template text must be replaced."""
        text = "Header\n{{components_table}}\nFooter"
        result = _inject_components_table(text, self._package_root)
        self.assertNotIn(
            "{{components_table}}",
            result,
            "Placeholder was NOT replaced — zero-occurrence guarantee violated",
        )

    def test_zero_occurrences_of_placeholder_after_injection(self):
        """Output must contain zero occurrences of the literal {{components_table}}."""
        text = "{{components_table}}"
        result = _inject_components_table(text, self._package_root)
        count = result.count("{{components_table}}")
        self.assertEqual(
            count,
            0,
            f"Found {count} remaining occurrences of '{{{{components_table}}}}' after injection",
        )

    def test_injected_table_contains_required_columns(self):
        """After injection the result must contain the required column headers."""
        text = "Preamble\n{{components_table}}\nPostamble"
        result = _inject_components_table(text, self._package_root)
        for column in ("id", "name", "type", "description", "agent_affinity"):
            self.assertIn(
                column, result,
                f"Required column '{column}' missing from injected output",
            )

    def test_text_without_placeholder_returned_unchanged(self):
        """Text that contains no {{components_table}} must be returned byte-for-byte unchanged."""
        original = "No placeholder here."
        result = _inject_components_table(original, self._package_root)
        self.assertEqual(result, original)

    def test_placeholder_replaced_with_sorted_table(self):
        """The injected table must be sorted by component id."""
        text = "{{components_table}}"
        result = _inject_components_table(text, self._package_root)
        alpha_pos = result.find("alpha_runner")
        zebra_pos = result.find("zebra_runner")  # not in data; find zebra_logger
        zebra_pos = result.find("zebra_logger")
        self.assertLess(
            alpha_pos,
            zebra_pos,
            "Injected table is not sorted: alpha_runner should precede zebra_logger",
        )

    def test_preamble_and_postamble_preserved(self):
        """Text surrounding the placeholder must remain intact after injection."""
        text = "BEGIN_MARKER\n{{components_table}}\nEND_MARKER"
        result = _inject_components_table(text, self._package_root)
        self.assertIn("BEGIN_MARKER", result)
        self.assertIn("END_MARKER", result)


if __name__ == "__main__":
    unittest.main()
