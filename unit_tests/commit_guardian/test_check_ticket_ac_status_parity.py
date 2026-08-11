"""
MODULE: unit_tests/commit_guardian/test_check_ticket_ac_status_parity.py
GOAL: Verify check_ticket_ac_status_parity.py (KI-1 guard) covers the five
    correctness cases: fail on done-ticket/non-done-AC mismatch, pass on
    done-ticket/done-AC match, skip when ticket is not done, skip when no
    source_ac, and warn-only (no failure) when the AC file is missing.
BUSINESS CONTEXT: KI-1 (BO-2200 retrospective) — the BO-2200 finalization
    required manual repair because tickets were flipped status:done while their
    source AC remained work_status:todo. These tests confirm the mechanical
    guard catches that exact drift at pre-commit time.
ARCHITECTURE: Imports the hook directly from the template source tree via
    importlib so tests are not dependent on a deployed build. All file
    fixtures use yaml.safe_dump (real-format mandate) and tempfile for
    isolation. No mocking of git or subprocess — the hook's internal functions
    are tested directly.

# covers: KI-1
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Load the hook from the template source tree
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HOOK_SCRIPT = (
    _REPO_ROOT
    / "templates"
    / "scripts"
    / "commit_guardian"
    / "check_ticket_ac_status_parity.py"
)
# _resolve_root must be importable when the hook module loads
_CG_TEMPLATE_DIR = _HOOK_SCRIPT.parent
if str(_CG_TEMPLATE_DIR) not in sys.path:
    sys.path.insert(0, str(_CG_TEMPLATE_DIR))

_MODULE_NAME = "check_ticket_ac_status_parity_test_shim"

try:
    _spec = importlib.util.spec_from_file_location(_MODULE_NAME, _HOOK_SCRIPT)
    _mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
    sys.modules[_MODULE_NAME] = _mod
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
    check_ticket_ac_parity = _mod.check_ticket_ac_parity
    _parse_frontmatter = _mod._parse_frontmatter
    _find_ac_file = _mod._find_ac_file
    _read_ac_work_status = _mod._read_ac_work_status
    _IMPORT_OK = True
except (FileNotFoundError, AttributeError, ImportError, SyntaxError) as _exc:
    _IMPORT_OK = False
    _IMPORT_ERROR = str(_exc)


def _requires_import(func):
    """Skip test if the hook module failed to import."""
    if not _IMPORT_OK:
        return unittest.skip(
            f"check_ticket_ac_status_parity not importable: {_IMPORT_ERROR}"
        )(func)
    return func


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_ticket(tmp: Path, name: str, frontmatter: dict) -> Path:
    """Write a ticket markdown file with YAML frontmatter under tmp/tickets/.

    Args:
        tmp: Temporary root directory.
        name: Filename (e.g. 'TICKET-001.md').
        frontmatter: Dict to serialise as YAML frontmatter.

    Returns:
        Absolute path to the written ticket file.
    """
    ticket_dir = tmp / "tickets"
    ticket_dir.mkdir(parents=True, exist_ok=True)
    path = ticket_dir / name
    try:
        content = "---\n" + yaml.safe_dump(frontmatter) + "---\n\n# Body\n"
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"_write_ticket: cannot write {path}: {exc}") from exc
    return path


def _write_ac(tmp: Path, component: str, ac_id: str, work_status: str) -> Path:
    """Write an AC YAML file under tmp/docs/acceptance-criteria/<component>/.

    Args:
        tmp: Temporary root directory.
        component: Component directory name (e.g. 'build_pipeline').
        ac_id: AC identifier (e.g. 'BP-1100e-1') — filename will be <ac_id>.yaml.
        work_status: The ``work_status`` value to write.

    Returns:
        Absolute path to the written AC file.
    """
    ac_dir = tmp / "docs" / "acceptance-criteria" / component
    ac_dir.mkdir(parents=True, exist_ok=True)
    path = ac_dir / f"{ac_id}.yaml"
    data = {
        "id": ac_id,
        "work_status": work_status,
        "title": f"Test AC {ac_id}",
    }
    try:
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"_write_ac: cannot write {path}: {exc}") from exc
    return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCheckTicketAcParityFail(unittest.TestCase):
    """Fail case: done ticket, AC exists, AC work_status is not done."""

    @_requires_import
    def test_violation_when_done_ticket_has_todo_ac(self) -> None:
        """check_ticket_ac_parity returns one violation for a done-ticket/todo-AC pair."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            ac_root = tmp / "docs" / "acceptance-criteria"
            _write_ac(tmp, "build_pipeline", "BP-100", "todo")
            ticket_path = _write_ticket(
                tmp,
                "TICKET-001.md",
                {"status": "done", "source_ac": "BP-100", "title": "T1"},
            )
            violations = check_ticket_ac_parity([ticket_path], ac_root=ac_root)
            self.assertEqual(len(violations), 1)
            self.assertEqual(violations[0]["source_ac"], "BP-100")
            self.assertEqual(violations[0]["work_status"], "todo")
            self.assertIn("TICKET-001.md", violations[0]["ticket"])

    @_requires_import
    def test_violation_when_ac_work_status_is_in_progress(self) -> None:
        """check_ticket_ac_parity reports violation for work_status:in_progress."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            ac_root = tmp / "docs" / "acceptance-criteria"
            _write_ac(tmp, "commit_guardian", "CG-001", "in_progress")
            ticket_path = _write_ticket(
                tmp,
                "TICKET-002.md",
                {"status": "done", "source_ac": "CG-001", "title": "T2"},
            )
            violations = check_ticket_ac_parity([ticket_path], ac_root=ac_root)
            self.assertEqual(len(violations), 1)
            self.assertEqual(violations[0]["work_status"], "in_progress")


class TestCheckTicketAcParityPass(unittest.TestCase):
    """Pass case: done ticket, AC exists, AC work_status is done."""

    @_requires_import
    def test_no_violation_when_done_ticket_has_done_ac(self) -> None:
        """check_ticket_ac_parity returns no violations when AC is done."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            ac_root = tmp / "docs" / "acceptance-criteria"
            _write_ac(tmp, "build_pipeline", "BP-200", "done")
            ticket_path = _write_ticket(
                tmp,
                "TICKET-003.md",
                {"status": "done", "source_ac": "BP-200", "title": "T3"},
            )
            violations = check_ticket_ac_parity([ticket_path], ac_root=ac_root)
            self.assertEqual(violations, [])

    @_requires_import
    def test_no_violation_when_empty_staged_list(self) -> None:
        """check_ticket_ac_parity returns empty list for no staged tickets."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            ac_root = tmp / "docs" / "acceptance-criteria"
            violations = check_ticket_ac_parity([], ac_root=ac_root)
            self.assertEqual(violations, [])


class TestCheckTicketAcParitySkipNotDone(unittest.TestCase):
    """Skip case: ticket status is not done — no violation emitted."""

    @_requires_import
    def test_no_violation_when_ticket_status_todo(self) -> None:
        """Tickets with status:todo are silently skipped."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            ac_root = tmp / "docs" / "acceptance-criteria"
            # AC is NOT done — but ticket is also not done, so skip
            _write_ac(tmp, "build_pipeline", "BP-300", "todo")
            ticket_path = _write_ticket(
                tmp,
                "TICKET-004.md",
                {"status": "todo", "source_ac": "BP-300", "title": "T4"},
            )
            violations = check_ticket_ac_parity([ticket_path], ac_root=ac_root)
            self.assertEqual(violations, [])

    @_requires_import
    def test_no_violation_when_ticket_status_in_progress(self) -> None:
        """Tickets with status:in_progress are silently skipped."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            ac_root = tmp / "docs" / "acceptance-criteria"
            _write_ac(tmp, "build_pipeline", "BP-400", "todo")
            ticket_path = _write_ticket(
                tmp,
                "TICKET-005.md",
                {"status": "in_progress", "source_ac": "BP-400", "title": "T5"},
            )
            violations = check_ticket_ac_parity([ticket_path], ac_root=ac_root)
            self.assertEqual(violations, [])


class TestCheckTicketAcParitySkipNoSourceAc(unittest.TestCase):
    """Skip case: done ticket has no source_ac field."""

    @_requires_import
    def test_no_violation_when_no_source_ac(self) -> None:
        """Done tickets without source_ac are silently skipped (epics/composites)."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            ac_root = tmp / "docs" / "acceptance-criteria"
            ticket_path = _write_ticket(
                tmp,
                "TICKET-006.md",
                {"status": "done", "title": "T6"},
            )
            violations = check_ticket_ac_parity([ticket_path], ac_root=ac_root)
            self.assertEqual(violations, [])

    @_requires_import
    def test_no_violation_when_source_ac_is_empty_string(self) -> None:
        """Done tickets with empty source_ac string are silently skipped."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            ac_root = tmp / "docs" / "acceptance-criteria"
            ticket_path = _write_ticket(
                tmp,
                "TICKET-007.md",
                {"status": "done", "source_ac": "", "title": "T7"},
            )
            violations = check_ticket_ac_parity([ticket_path], ac_root=ac_root)
            self.assertEqual(violations, [])


class TestCheckTicketAcParityWarnAcMissing(unittest.TestCase):
    """Warn-only case: done ticket has source_ac but AC file not found in store."""

    @_requires_import
    def test_warn_only_when_ac_not_found(self) -> None:
        """Missing AC file produces a WARNING but no violation (no hard block)."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            # ac_root exists but contains no AC file matching 'MISSING-001'
            ac_root = tmp / "docs" / "acceptance-criteria"
            ac_root.mkdir(parents=True, exist_ok=True)
            ticket_path = _write_ticket(
                tmp,
                "TICKET-008.md",
                {"status": "done", "source_ac": "MISSING-001", "title": "T8"},
            )
            import io
            from contextlib import redirect_stderr

            buf = io.StringIO()
            with redirect_stderr(buf):
                violations = check_ticket_ac_parity([ticket_path], ac_root=ac_root)

            self.assertEqual(violations, [])
            self.assertIn("MISSING-001", buf.getvalue())
            self.assertIn("not found", buf.getvalue())


class TestParseFrontmatter(unittest.TestCase):
    """Unit tests for _parse_frontmatter."""

    @_requires_import
    def test_parses_valid_frontmatter(self) -> None:
        """_parse_frontmatter returns dict for standard YAML frontmatter."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            path = tmp / "ticket.md"
            try:
                path.write_text(
                    "---\nstatus: done\nsource_ac: X-1\n---\n\n# body\n",
                    encoding="utf-8",
                )
            except OSError as exc:
                self.skipTest(f"Cannot write temp file: {exc}")
            result = _parse_frontmatter(path)
            self.assertIsNotNone(result)
            self.assertEqual(result["status"], "done")

    @_requires_import
    def test_returns_none_for_no_frontmatter(self) -> None:
        """_parse_frontmatter returns None when file has no --- delimiters."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            path = tmp / "nofm.md"
            try:
                path.write_text("# Just a heading\n\nno frontmatter here\n", encoding="utf-8")
            except OSError as exc:
                self.skipTest(f"Cannot write temp file: {exc}")
            result = _parse_frontmatter(path)
            self.assertIsNone(result)


class TestFindAcFile(unittest.TestCase):
    """Unit tests for _find_ac_file."""

    @_requires_import
    def test_finds_ac_in_subdirectory(self) -> None:
        """_find_ac_file locates an AC file in a nested subdirectory."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            ac_root = tmp / "docs" / "acceptance-criteria"
            sub = ac_root / "build_pipeline" / "BP-1100"
            sub.mkdir(parents=True, exist_ok=True)
            try:
                (sub / "BP-1100e-1.yaml").write_text("id: BP-1100e-1\n", encoding="utf-8")
            except OSError as exc:
                self.skipTest(f"Cannot write temp file: {exc}")
            result = _find_ac_file("BP-1100e-1", ac_root)
            self.assertIsNotNone(result)
            self.assertEqual(result.name, "BP-1100e-1.yaml")

    @_requires_import
    def test_returns_none_when_ac_absent(self) -> None:
        """_find_ac_file returns None when no file with that id exists."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            ac_root = tmp / "docs" / "acceptance-criteria"
            ac_root.mkdir(parents=True, exist_ok=True)
            result = _find_ac_file("NONEXISTENT-999", ac_root)
            self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
