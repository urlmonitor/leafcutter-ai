"""
MODULE: test_context_accumulation
GOAL: Unit tests for scripts/knowledge/context_file_maintenance.py.
BUSINESS CONTEXT: Verifies that component AC directories accumulate README.md
    files with domain conventions, and skill-scoped PROJECT_CONTEXT.md files
    grow with each run while preserving existing entries (reverse-chronological,
    append-only, agent-attributed). These tests define the acceptance gate for
    AC-1 (INF-400d-1), AC-2 (INF-400d-2), and AC-3 (INF-400d-3).
ARCHITECTURE: Pure unit tests using unittest.TestCase with tempfile.TemporaryDirectory
    for filesystem isolation. No database connections required.
    All tests must complete in < 5 seconds.
"""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: resolve context_file_maintenance module without installed package
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent.parent
_MODULE_PATH = _REPO_ROOT / "scripts" / "knowledge" / "context_file_maintenance.py"


def _load_module():
    """Load context_file_maintenance from source path."""
    spec = importlib.util.spec_from_file_location(
        "context_file_maintenance", _MODULE_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


try:
    cfm = _load_module()
except (FileNotFoundError, ModuleNotFoundError, AttributeError) as exc:
    # Production code does not yet exist — tests must be RED at this stage.
    cfm = None
    _LOAD_ERROR = str(exc)
else:
    _LOAD_ERROR = None


# ---------------------------------------------------------------------------
# Helper: require the module (fails fast if import failed)
# ---------------------------------------------------------------------------


class _ModuleNotImplementedError(ImportError):
    """Raised when context_file_maintenance has not yet been implemented."""


def _require_module():
    """Return cfm or raise _ModuleNotImplementedError — causes a red test when code is absent."""
    if cfm is None:
        msg = f"context_file_maintenance not yet implemented: {_LOAD_ERROR}"
        raise _ModuleNotImplementedError(msg)
    return cfm


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestReadmeCreatedWhenAbsent(unittest.TestCase):
    """AC-1 (INF-400d-1): component README.md is created if it does not exist."""

    def test_readme_created_when_absent(self):
        # covers: INF-400d-1
        """
        Route a learning with entry_kind 'per-folder-readme' to a destination
        that does not yet exist. Assert the file is created with the standard
        header and a dated, agent-attributed entry.
        """
        mod = _require_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "docs" / "acceptance-criteria" / "infrastructure" / "README.md"
            # File must not exist before the call
            self.assertFalse(dest.exists(), "Destination should not exist before call")

            mod.create_readme(
                path=dest,
                component="infrastructure",
            )

            self.assertTrue(dest.exists(), "README.md was not created")
            content = dest.read_text(encoding="utf-8")
            self.assertIn(
                "# infrastructure — domain conventions",
                content,
                "Standard header missing from created README.md",
            )

    def test_readme_appends_not_overwrites(self):
        # covers: INF-400d-1
        """
        Route two learnings to the same README.md. Assert both entries are
        present (not overwritten).
        """
        mod = _require_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "README.md"
            mod.create_readme(path=dest, component="infrastructure")

            mod.append_entry(
                path=dest,
                date="2026-06-04",
                agent="python-coder",
                text="First learning entry.",
            )
            mod.append_entry(
                path=dest,
                date="2026-06-05",
                agent="test-writer",
                text="Second learning entry.",
            )

            content = dest.read_text(encoding="utf-8")
            self.assertIn("First learning entry.", content, "First entry was overwritten")
            self.assertIn("Second learning entry.", content, "Second entry missing")


class TestProjectContextPreservesExisting(unittest.TestCase):
    """AC-2 (INF-400d-2): PROJECT_CONTEXT.md preserves prior entries on append."""

    def test_project_context_preserves_existing(self):
        # covers: INF-400d-2
        """
        Fixture: PROJECT_CONTEXT.md with 3 accumulated entries.
        Route a 4th learning. Assert all 4 entries are present.
        """
        mod = _require_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "PROJECT_CONTEXT.md"
            # Pre-populate with 3 entries
            initial_content = (
                "# Project Context\n\n"
                "## 2026-06-01 — agent-a\nEntry one.\n\n"
                "## 2026-06-02 — agent-b\nEntry two.\n\n"
                "## 2026-06-03 — agent-c\nEntry three.\n\n"
            )
            dest.write_text(initial_content, encoding="utf-8")

            mod.append_entry(
                path=dest,
                date="2026-06-05",
                agent="business-analyst-v3",
                text="Entry four — new learning.",
            )

            content = dest.read_text(encoding="utf-8")
            self.assertIn("Entry one.", content, "Prior entry 1 was lost")
            self.assertIn("Entry two.", content, "Prior entry 2 was lost")
            self.assertIn("Entry three.", content, "Prior entry 3 was lost")
            self.assertIn("Entry four — new learning.", content, "New entry missing")

    def test_project_context_filename_convention(self):
        # covers: INF-400d-2
        """
        The file naming convention must be PROJECT_CONTEXT.md (all uppercase,
        underscore separator), not project_context.md or ProjectContext.md.
        """
        mod = _require_module()
        # The module must expose a constant or function indicating the correct filename.
        # Acceptable: a CONTEXT_FILENAME constant, or a get_context_filename() function.
        filename = getattr(mod, "CONTEXT_FILENAME", None) or getattr(
            mod, "get_context_filename", lambda: None
        )()
        self.assertIsNotNone(
            filename,
            "Module must expose CONTEXT_FILENAME constant or get_context_filename() function",
        )
        self.assertEqual(
            filename,
            "PROJECT_CONTEXT.md",
            "Context filename must be 'PROJECT_CONTEXT.md' (all uppercase, underscore)",
        )


class TestReverseChronologicalOrder(unittest.TestCase):
    """AC-3 (INF-400d-3): entries appear newest-first after appending."""

    def test_reverse_chronological_order(self):
        # covers: INF-400d-3
        """
        Route 3 entries with different dates. Assert newest entry appears
        before older entries in the file.
        """
        mod = _require_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "README.md"
            mod.create_readme(path=dest, component="test-component")

            mod.append_entry(
                path=dest,
                date="2026-06-01",
                agent="agent-a",
                text="Oldest entry.",
            )
            mod.append_entry(
                path=dest,
                date="2026-06-03",
                agent="agent-b",
                text="Middle entry.",
            )
            mod.append_entry(
                path=dest,
                date="2026-06-05",
                agent="agent-c",
                text="Newest entry.",
            )

            content = dest.read_text(encoding="utf-8")
            pos_newest = content.find("Newest entry.")
            pos_middle = content.find("Middle entry.")
            pos_oldest = content.find("Oldest entry.")

            self.assertLess(
                pos_newest,
                pos_middle,
                "Newest entry should appear before middle entry (reverse chronological)",
            )
            self.assertLess(
                pos_middle,
                pos_oldest,
                "Middle entry should appear before oldest entry (reverse chronological)",
            )


class TestEntryAttribution(unittest.TestCase):
    """AC-1 + AC-2: entries include date and agent name."""

    def test_entry_attribution(self):
        # covers: INF-400d-1
        # covers: INF-400d-2
        """
        Route a learning from 'business-analyst-v3'. Assert the agent name
        appears in the entry written to the context file.
        """
        mod = _require_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "README.md"
            mod.create_readme(path=dest, component="infrastructure")

            mod.append_entry(
                path=dest,
                date="2026-06-05",
                agent="business-analyst-v3",
                text="Agent attribution test learning.",
            )

            content = dest.read_text(encoding="utf-8")
            self.assertIn(
                "business-analyst-v3",
                content,
                "Agent name 'business-analyst-v3' must appear in the entry",
            )
            self.assertIn(
                "2026-06-05",
                content,
                "Date must appear in the entry",
            )


class TestSummaryGeneration(unittest.TestCase):
    """AC-3 (INF-400d-3): summary section is updated when entry count exceeds 15."""

    def test_summary_generated_after_threshold(self):
        # covers: INF-400d-3
        """
        Accumulate 16 entries. Assert the file includes a summary section
        near the top.
        """
        mod = _require_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "README.md"
            mod.create_readme(path=dest, component="infrastructure")

            for i in range(16):
                mod.append_entry(
                    path=dest,
                    date=f"2026-06-{i + 1:02d}",
                    agent=f"agent-{i}",
                    text=f"Learning number {i + 1}.",
                )

            content = dest.read_text(encoding="utf-8")
            # The summary section should exist and appear near the top of the file
            summary_pos = content.lower().find("summary")
            self.assertGreaterEqual(
                summary_pos,
                0,
                "A summary section must be present when entry count exceeds 15",
            )
            # Summary should be in the first 30% of the file (near the top)
            first_third = len(content) // 3
            self.assertLessEqual(
                summary_pos,
                first_third,
                "Summary section must appear near the top of the file (first 30%)",
            )


if __name__ == "__main__":
    unittest.main()
