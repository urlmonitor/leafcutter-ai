"""
MODULE: test_package_audit
GOAL: Unit tests for leafcutter/scripts/package_audit.py —
    classification logic, section reporting, Markdown/JSON output, and
    CLI behaviour.
BUSINESS CONTEXT: package_audit.py formalises the gap analysis between
    the leafcutter package templates and the live project's
    files. Tests verify that classification buckets (portable vs
    project-specific vs unknown), action derivation (move / mark-boundary
    / none), and output formatters behave correctly without touching the
    real filesystem.
ARCHITECTURE: Standard unittest. No database, no network. Uses
    tempfile.TemporaryDirectory for all synthetic directory layouts so no
    real project files are touched. The module is loaded via importlib to
    avoid sys.path contamination.

DOC_LINKS: None
DECISION HISTORY:
  - 2026-05-13 12:00 [epic-supervisor]: Created for T01 acceptance criteria.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Module loading
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_MODULE_PATH = _SCRIPTS_DIR / "package_audit.py"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


def _load_module():
    """Load package_audit.py dynamically.

    Registers the module in sys.modules so that Python 3.13 dataclass
    processing can resolve the module dict correctly via sys.modules.

    Returns:
        The loaded module object.
    """
    spec = importlib.util.spec_from_file_location("package_audit", _MODULE_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load package_audit.py from {_MODULE_PATH}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["package_audit"] = mod
    spec.loader.exec_module(mod)
    return mod


_mod = _load_module()

run_audit = _mod.run_audit
format_markdown = _mod.format_markdown
format_json = _mod.format_json
AuditReport = _mod.AuditReport
SectionReport = _mod.SectionReport
AuditItem = _mod.AuditItem
_classify_item = _mod._classify_item
_suggest_action = _mod._suggest_action


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_boundary_config(sections: dict) -> dict:
    """Build a minimal package_boundary.json payload.

    Args:
        sections: Dict of {section_name: section_cfg} to embed.

    Returns:
        Dict ready to be serialised and written to a temp file.
    """
    return {"sections": sections}


def _write_config(tmp_path: Path, data: dict) -> Path:
    """Write a dict to a JSON file inside tmp_path.

    Args:
        tmp_path: Directory to write into.
        data: Python dict to serialise.

    Returns:
        Path to the written JSON file.
    """
    cfg_path = tmp_path / "package_boundary.json"
    cfg_path.write_text(json.dumps(data), encoding="utf-8")
    return cfg_path


# ---------------------------------------------------------------------------
# _classify_item tests
# ---------------------------------------------------------------------------

class TestClassifyItem(unittest.TestCase):
    """Tests for _classify_item()."""

    def test_portable_classification(self):
        """Files in items_map with 'portable' return 'portable'."""
        items_map = {"check_secrets.py": "portable"}
        result = _classify_item("check_secrets.py", items_map)
        self.assertEqual(result, "portable")

    def test_project_specific_classification(self):
        """Files in items_map with 'project-specific' return 'project-specific'."""
        items_map = {"apply_sql_changes.py": "project-specific"}
        result = _classify_item("apply_sql_changes.py", items_map)
        self.assertEqual(result, "project-specific")

    def test_unknown_classification(self):
        """Files not in items_map return 'unknown'."""
        result = _classify_item("some_new_hook.py", {})
        self.assertEqual(result, "unknown")


# ---------------------------------------------------------------------------
# _suggest_action tests
# ---------------------------------------------------------------------------

class TestSuggestAction(unittest.TestCase):
    """Tests for _suggest_action()."""

    def test_portable_not_in_template_returns_move(self):
        """Portable file absent from template → action 'move'."""
        self.assertEqual(_suggest_action("portable", False), "move")

    def test_project_specific_not_in_template_returns_mark_boundary(self):
        """Project-specific file absent from template → action 'mark-boundary'."""
        self.assertEqual(_suggest_action("project-specific", False), "mark-boundary")

    def test_in_template_returns_none_regardless(self):
        """Any file already in template → action 'none'."""
        self.assertEqual(_suggest_action("portable", True), "none")
        self.assertEqual(_suggest_action("project-specific", True), "none")
        self.assertEqual(_suggest_action("unknown", True), "none")

    def test_unknown_not_in_template_returns_none(self):
        """Unknown file absent from template → action 'none' (conservative)."""
        self.assertEqual(_suggest_action("unknown", False), "none")


# ---------------------------------------------------------------------------
# run_audit tests
# ---------------------------------------------------------------------------

class TestRunAudit(unittest.TestCase):
    """Integration tests for run_audit() using synthetic temp directories."""

    def setUp(self):
        """Set up shared temp directory and default test data."""
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        """Clean up temp directory."""
        self._tmp.cleanup()

    def _make_layout(self, live_files: list[str], template_files: list[str]) -> tuple[Path, Path]:
        """Create live and template subdirectories with the given files.

        Args:
            live_files: Filenames to create in live dir.
            template_files: Filenames to create in template dir.

        Returns:
            (live_dir, template_dir) Path tuple.
        """
        live_dir = self.tmp / "live"
        template_dir = self.tmp / "template"
        live_dir.mkdir()
        template_dir.mkdir()
        for f in live_files:
            (live_dir / f).write_text("# stub", encoding="utf-8")
        for f in template_files:
            (template_dir / f).write_text("# stub", encoding="utf-8")
        return live_dir, template_dir

    def test_portable_file_missing_from_template_is_flagged(self):
        """A portable file absent from template appears with action 'move'."""
        live_dir, template_dir = self._make_layout(
            live_files=["check_secrets.py"],
            template_files=[],
        )
        cfg = _make_boundary_config({
            "commit-guardian": {
                "live_dir": str(live_dir.relative_to(self.tmp)),
                "template_dir": str(template_dir.relative_to(self.tmp)),
                "items": {"check_secrets.py": "portable"},
            }
        })
        cfg_path = _write_config(self.tmp, cfg)
        audit = run_audit(
            project_root=self.tmp,
            package_root=self.tmp / "pkg",
            boundary_config_path=cfg_path,
        )
        self.assertEqual(len(audit.sections), 1)
        section = audit.sections[0]
        self.assertEqual(section.missing_count, 1)
        self.assertEqual(audit.total_missing, 1)
        item = section.items[0]
        self.assertEqual(item.filename, "check_secrets.py")
        self.assertEqual(item.classification, "portable")
        self.assertFalse(item.in_template)
        self.assertEqual(item.action, "move")

    def test_portable_file_in_template_shows_no_gap(self):
        """A portable file already in template shows action 'none' and zero missing."""
        live_dir, template_dir = self._make_layout(
            live_files=["check_secrets.py"],
            template_files=["check_secrets.py"],
        )
        cfg = _make_boundary_config({
            "commit-guardian": {
                "live_dir": str(live_dir.relative_to(self.tmp)),
                "template_dir": str(template_dir.relative_to(self.tmp)),
                "items": {"check_secrets.py": "portable"},
            }
        })
        cfg_path = _write_config(self.tmp, cfg)
        audit = run_audit(
            project_root=self.tmp,
            package_root=self.tmp / "pkg",
            boundary_config_path=cfg_path,
        )
        section = audit.sections[0]
        self.assertEqual(section.missing_count, 0)
        self.assertEqual(audit.total_missing, 0)
        self.assertEqual(section.items[0].action, "none")

    def test_project_specific_file_gets_mark_boundary_action(self):
        """A project-specific file absent from template shows 'mark-boundary', not 'move'."""
        live_dir, template_dir = self._make_layout(
            live_files=["apply_sql_changes.py"],
            template_files=[],
        )
        cfg = _make_boundary_config({
            "commit-guardian": {
                "live_dir": str(live_dir.relative_to(self.tmp)),
                "template_dir": str(template_dir.relative_to(self.tmp)),
                "items": {"apply_sql_changes.py": "project-specific"},
            }
        })
        cfg_path = _write_config(self.tmp, cfg)
        audit = run_audit(
            project_root=self.tmp,
            package_root=self.tmp / "pkg",
            boundary_config_path=cfg_path,
        )
        item = audit.sections[0].items[0]
        self.assertEqual(item.action, "mark-boundary")
        # project-specific files do not count toward "missing from package"
        self.assertEqual(audit.total_missing, 0)

    def test_missing_live_dir_returns_empty_section(self):
        """When live_dir does not exist, the section reports zero items."""
        cfg = _make_boundary_config({
            "commit-guardian": {
                "live_dir": "nonexistent/live",
                "template_dir": "nonexistent/template",
                "items": {},
            }
        })
        cfg_path = _write_config(self.tmp, cfg)
        audit = run_audit(
            project_root=self.tmp,
            package_root=self.tmp / "pkg",
            boundary_config_path=cfg_path,
        )
        self.assertEqual(audit.sections[0].items, [])
        self.assertEqual(audit.total_missing, 0)

    def test_skip_names_are_excluded(self):
        """__init__.py and __pycache__ are skipped from audit items."""
        live_dir, template_dir = self._make_layout(
            live_files=["__init__.py", "check_secrets.py"],
            template_files=[],
        )
        cfg = _make_boundary_config({
            "commit-guardian": {
                "live_dir": str(live_dir.relative_to(self.tmp)),
                "template_dir": str(template_dir.relative_to(self.tmp)),
                "items": {"check_secrets.py": "portable"},
            }
        })
        cfg_path = _write_config(self.tmp, cfg)
        audit = run_audit(
            project_root=self.tmp,
            package_root=self.tmp / "pkg",
            boundary_config_path=cfg_path,
        )
        names = [i.filename for i in audit.sections[0].items]
        self.assertNotIn("__init__.py", names)
        self.assertIn("check_secrets.py", names)

    def test_zero_gap_after_all_portable_files_moved(self):
        """When all portable files are in the template, total_missing is zero."""
        live_dir, template_dir = self._make_layout(
            live_files=["check_secrets.py", "check_build_drift.py"],
            template_files=["check_secrets.py", "check_build_drift.py"],
        )
        cfg = _make_boundary_config({
            "commit-guardian": {
                "live_dir": str(live_dir.relative_to(self.tmp)),
                "template_dir": str(template_dir.relative_to(self.tmp)),
                "items": {
                    "check_secrets.py": "portable",
                    "check_build_drift.py": "portable",
                },
            }
        })
        cfg_path = _write_config(self.tmp, cfg)
        audit = run_audit(
            project_root=self.tmp,
            package_root=self.tmp / "pkg",
            boundary_config_path=cfg_path,
        )
        self.assertEqual(audit.total_missing, 0)


# ---------------------------------------------------------------------------
# Output formatter tests
# ---------------------------------------------------------------------------

class TestFormatMarkdown(unittest.TestCase):
    """Tests for format_markdown()."""

    def _make_audit(self, missing_count: int = 0) -> AuditReport:
        """Build a synthetic AuditReport for testing.

        Args:
            missing_count: Number of missing files to simulate in the section.

        Returns:
            AuditReport with one section.
        """
        item_action = "move" if missing_count > 0 else "none"
        item = AuditItem(
            filename="check_secrets.py",
            classification="portable",
            in_template=(missing_count == 0),
            action=item_action,
        )
        section = SectionReport(
            name="commit-guardian",
            live_dir="/live",
            template_dir="/template",
            items=[item],
            missing_count=missing_count,
        )
        return AuditReport(
            project_root="/proj",
            package_root="/pkg",
            sections=[section],
            total_missing=missing_count,
        )

    def test_markdown_contains_section_name(self):
        """The Markdown output includes the section name as a heading."""
        md = format_markdown(self._make_audit())
        self.assertIn("## commit-guardian", md)

    def test_zero_gap_emits_no_gap_message(self):
        """When total_missing is 0, the report includes the 'No package gap' message."""
        md = format_markdown(self._make_audit(missing_count=0))
        self.assertIn("No package gap detected", md)

    def test_nonzero_gap_shows_total(self):
        """When files are missing, the total count appears in the report."""
        md = format_markdown(self._make_audit(missing_count=1))
        self.assertIn("Total portable files missing from package**: 1", md)

    def test_markdown_table_includes_file_row(self):
        """Each AuditItem appears as a table row in the Markdown."""
        md = format_markdown(self._make_audit(missing_count=1))
        self.assertIn("`check_secrets.py`", md)
        self.assertIn("move", md)


class TestFormatJson(unittest.TestCase):
    """Tests for format_json()."""

    def test_json_is_parseable(self):
        """format_json returns valid JSON that can be parsed."""
        item = AuditItem(
            filename="check_secrets.py",
            classification="portable",
            in_template=False,
            action="move",
        )
        section = SectionReport(
            name="commit-guardian",
            live_dir="/live",
            template_dir="/template",
            items=[item],
            missing_count=1,
        )
        audit = AuditReport(
            project_root="/proj",
            package_root="/pkg",
            sections=[section],
            total_missing=1,
        )
        data = json.loads(format_json(audit))
        self.assertEqual(data["total_missing"], 1)
        self.assertEqual(data["sections"][0]["name"], "commit-guardian")
        self.assertEqual(data["sections"][0]["items"][0]["filename"], "check_secrets.py")


if __name__ == "__main__":
    unittest.main()
