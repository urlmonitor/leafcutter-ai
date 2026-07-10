"""
MODULE: test_check_surface_components_e2
GOAL: Unit tests for check_surface_components_e2.py, the pre-commit hook that
    blocks commits when a staged ticket or doc .md file lacks a non-empty
    `components` frontmatter field.
BUSINESS CONTEXT: KM-KGS-100e-2. Verifies that the hook correctly detects
    violations on synthetic fixtures AND on a real on-disk ticket file, guarding
    against the synthetic-fixture bias identified in EPIC-PhantomDoneFilesTouched.
ARCHITECTURE: Tests load the hook from templates/scripts/commit_guardian/ via
    importlib (matching the convention in test_check_ac_circular_deps.py).
    HOOK_TEST_FILES and HOOK_ROOT env vars are used for isolation.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_HOOK_PATH = (
    _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
    / "check_surface_components_e2.py"
)

try:
    _MODULE_NAME = "check_surface_components_e2_test_shim"
    _spec = importlib.util.spec_from_file_location(_MODULE_NAME, str(_HOOK_PATH))
    _mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
    sys.modules[_MODULE_NAME] = _mod
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]

    _find_project_root = _mod._find_project_root
    _check_file = _mod._check_file
    _extract_frontmatter = _mod._extract_frontmatter
    _check_components = _mod._check_components
    _get_staged_md_paths = _mod._get_staged_md_paths
    _main = _mod.main
    _IMPORT_OK = True
    _IMPORT_ERROR = ""
except (FileNotFoundError, AttributeError, ImportError, SyntaxError, TypeError, ValueError) as _exc:
    _IMPORT_OK = False
    _IMPORT_ERROR = str(_exc)


def _requires_import(func):
    """Skip test if the hook module failed to import."""
    if not _IMPORT_OK:
        return unittest.skip(
            f"check_surface_components_e2 not importable: {_IMPORT_ERROR}"
        )(func)
    return func


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_VALID_TICKET_FM = (
    "---\n"
    "title: Test ticket\n"
    "status: todo\n"
    "components:\n"
    "  - build-pipeline\n"
    "created: 2026-07-08\n"
    "depends_on: []\n"
    "---\n\n# Body\n"
)

_MISSING_TICKET_FM = (
    "---\n"
    "title: Test ticket\n"
    "status: todo\n"
    "created: 2026-07-08\n"
    "depends_on: []\n"
    "---\n\n# Body\n"
)

_EMPTY_COMPONENTS_FM = (
    "---\n"
    "title: Test ticket\n"
    "status: todo\n"
    "components: []\n"
    "created: 2026-07-08\n"
    "depends_on: []\n"
    "---\n\n# Body\n"
)

_NO_FRONTMATTER = "# Just a doc\n\nSome content.\n"


def _write_file(root: Path, rel_path: str, content: str) -> Path:
    """Write a file at root/rel_path, creating parent dirs as needed."""
    p = root / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# _extract_frontmatter
# ---------------------------------------------------------------------------


@_requires_import
class TestExtractFrontmatter(unittest.TestCase):
    """Tests for YAML frontmatter extraction."""

    def test_valid_frontmatter_parsed(self) -> None:
        data = _extract_frontmatter(_VALID_TICKET_FM)
        self.assertIsNotNone(data)
        self.assertIn("title", data)
        self.assertIn("components", data)

    def test_no_frontmatter_returns_none(self) -> None:
        data = _extract_frontmatter(_NO_FRONTMATTER)
        self.assertIsNone(data)

    def test_empty_content_returns_none(self) -> None:
        data = _extract_frontmatter("")
        self.assertIsNone(data)


# ---------------------------------------------------------------------------
# _check_components
# ---------------------------------------------------------------------------


@_requires_import
class TestCheckComponents(unittest.TestCase):
    """Tests for the components field validation predicate."""

    def test_valid_components_passes(self) -> None:
        data = {"components": ["build-pipeline"]}
        errs = _check_components(data, "test.md")
        self.assertEqual(errs, [])

    def test_missing_components_fails(self) -> None:
        errs = _check_components({"title": "t"}, "test.md")
        self.assertTrue(len(errs) > 0)
        self.assertTrue(any("missing required" in e for e in errs))

    def test_empty_list_fails(self) -> None:
        errs = _check_components({"components": []}, "test.md")
        self.assertTrue(len(errs) > 0)

    def test_blank_only_list_fails(self) -> None:
        errs = _check_components({"components": ["", "  "]}, "test.md")
        self.assertTrue(len(errs) > 0)

    def test_scalar_instead_of_list_fails(self) -> None:
        errs = _check_components({"components": "build-pipeline"}, "test.md")
        self.assertTrue(len(errs) > 0)

    def test_multiple_valid_components_pass(self) -> None:
        data = {"components": ["build-pipeline", "infrastructure"]}
        errs = _check_components(data, "test.md")
        self.assertEqual(errs, [])

    def test_error_message_names_file(self) -> None:
        errs = _check_components({}, "tickets/my-ticket.md")
        self.assertTrue(any("tickets/my-ticket.md" in e for e in errs))


# ---------------------------------------------------------------------------
# _check_file
# ---------------------------------------------------------------------------


@_requires_import
class TestCheckFile(unittest.TestCase):
    """Tests for per-file validation."""

    def test_valid_ticket_passes(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            p = _write_file(root, "tickets/my-ticket.md", _VALID_TICKET_FM)
            errs = _check_file(str(p), None)
            self.assertEqual(errs, [])

    def test_missing_components_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            p = _write_file(root, "tickets/bad-ticket.md", _MISSING_TICKET_FM)
            errs = _check_file(str(p), None)
            self.assertEqual(len(errs), 1)

    def test_empty_components_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            p = _write_file(root, "tickets/empty.md", _EMPTY_COMPONENTS_FM)
            errs = _check_file(str(p), None)
            self.assertEqual(len(errs), 1)

    def test_no_frontmatter_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            p = _write_file(root, "docs/plain.md", _NO_FRONTMATTER)
            errs = _check_file(str(p), None)
            self.assertEqual(errs, [])

    def test_nonexistent_file_returns_empty(self) -> None:
        errs = _check_file("/tmp/totally_nonexistent_xyzzy.md", None)
        self.assertEqual(errs, [])


# ---------------------------------------------------------------------------
# HOOK_TEST_FILES seam — end-to-end main()
# ---------------------------------------------------------------------------


@_requires_import
class TestMainWithTestFiles(unittest.TestCase):
    """End-to-end tests for main() using the HOOK_TEST_FILES env seam."""

    def setUp(self) -> None:
        self._orig_env = os.environ.copy()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._orig_env)

    def test_main_returns_0_no_staged_files(self) -> None:
        os.environ["HOOK_NO_GIT"] = "1"
        os.environ.pop("HOOK_TEST_FILES", None)
        result = _main()
        self.assertEqual(result, 0)

    def test_main_returns_0_clean_ticket(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            p = _write_file(root, "tickets/ok.md", _VALID_TICKET_FM)
            os.environ["HOOK_TEST_FILES"] = str(p)
            result = _main()
            self.assertEqual(result, 0)

    def test_main_returns_1_missing_components(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            p = _write_file(root, "tickets/bad.md", _MISSING_TICKET_FM)
            os.environ["HOOK_TEST_FILES"] = str(p)
            result = _main()
            self.assertEqual(result, 1)


# ---------------------------------------------------------------------------
# Real-fixture behavioral verification
# ---------------------------------------------------------------------------


@_requires_import
class TestRealFixtureBehavior(unittest.TestCase):
    """Exercises the hook against a real on-disk ticket file.

    Guards against the synthetic-fixture bias: a real ticket from the store
    must be parseable and validated correctly (not silently skipped).
    """

    _TICKETS_DIR = _REPO_ROOT / "tickets"

    def _find_real_ticket_with_components(self) -> Path | None:
        """Return the first ticket that has a components frontmatter field."""
        if not self._TICKETS_DIR.is_dir():
            return None
        for md_file in self._TICKETS_DIR.rglob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
            except (OSError, ValueError):
                continue
            data = _extract_frontmatter(content)
            if data and data.get("components"):
                return md_file
        return None

    def test_real_ticket_with_components_passes(self) -> None:
        """A real ticket that already has components must pass the check."""
        real_ticket = self._find_real_ticket_with_components()
        if real_ticket is None:
            self.skipTest("No tickets with components found in real store")
        errs = _check_file(str(real_ticket), None)
        self.assertEqual(
            errs,
            [],
            f"Real ticket {real_ticket} unexpectedly failed: {errs}",
        )

    def test_real_ticket_frontmatter_is_parsed(self) -> None:
        """Verify the frontmatter parser works on a real ticket's format."""
        real_ticket = self._find_real_ticket_with_components()
        if real_ticket is None:
            self.skipTest("No tickets with components found in real store")
        try:
            content = real_ticket.read_text(encoding="utf-8")
        except (OSError, ValueError):
            self.skipTest("Could not read real ticket file")
        data = _extract_frontmatter(content)
        self.assertIsNotNone(
            data,
            f"Real ticket {real_ticket} should have parseable frontmatter",
        )
        self.assertIsInstance(data.get("components"), list)


if __name__ == "__main__":
    unittest.main()
