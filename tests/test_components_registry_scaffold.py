"""
MODULE: test_components_registry_scaffold
GOAL: Verify that build_components_registry() materialises docs/components.json
    from the template with strict write-if-absent semantics.
BUSINESS CONTEXT: docs/components.json is treated as mandatory by several
    parts of the installed system (rules, agents, pre-commit hooks). This test
    suite guards the four contracts in the ticket acceptance criteria:
    (1) creates file when absent, (2) skips when already present,
    (3) honours dry-run mode, (4) returns 0 gracefully when template is absent,
    (5) ignores force=True (write-if-absent takes priority).
ARCHITECTURE: Uses unittest.TestCase with tmp_path-style TemporaryDirectory
    fixtures so all writes are isolated from the real project tree. TEMPLATES_DIR
    in build_phases is patched via monkeypatching the module attribute directly.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

sys.path.insert(0, str(_SCRIPTS_DIR))

import build_phases  # noqa: E402 — sys.path must be configured first
from build_phases import build_components_registry  # noqa: E402


# Minimal template content used across test cases.
_MINIMAL_TEMPLATE = '{\n  "_comment": "test",\n  "components": {}\n}\n'


def _make_templates_dir(base: Path) -> Path:
    """Create a minimal templates/docs/ layout under *base* and return the
    templates root so it can be patched into build_phases.TEMPLATES_DIR."""
    docs_dir = base / "templates" / "docs"
    docs_dir.mkdir(parents=True)
    template_file = docs_dir / "components.json.template"
    template_file.write_text(_MINIMAL_TEMPLATE, encoding="utf-8")
    return base / "templates"


class TestCreatesComponentsJsonWhenAbsent(unittest.TestCase):
    """AC-1: file is created when docs/components.json does not exist."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.base = Path(self._tmpdir.name)
        self.target_root = self.base / "project"
        self.target_root.mkdir()
        self.templates_root = _make_templates_dir(self.base)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_creates_components_json_when_absent(self):
        with mock.patch.object(build_phases, "TEMPLATES_DIR", self.templates_root):
            result = build_components_registry(
                self.target_root, config={}, dry_run=False, force=False
            )

        self.assertEqual(result, 1, "Expected return value 1 (file written)")
        target = self.target_root / "docs" / "components.json"
        self.assertTrue(target.exists(), "docs/components.json was not created")

        parsed = json.loads(target.read_text(encoding="utf-8"))
        self.assertIn("components", parsed, "Written JSON missing 'components' key")


class TestSkipsWhenComponentsJsonExists(unittest.TestCase):
    """AC-2: existing file is never overwritten (write-if-absent contract)."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.base = Path(self._tmpdir.name)
        self.target_root = self.base / "project"
        (self.target_root / "docs").mkdir(parents=True)
        self.existing_content = '{"existing": true}\n'
        (self.target_root / "docs" / "components.json").write_text(
            self.existing_content, encoding="utf-8"
        )
        self.templates_root = _make_templates_dir(self.base)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_skips_when_components_json_exists(self):
        with mock.patch.object(build_phases, "TEMPLATES_DIR", self.templates_root):
            result = build_components_registry(
                self.target_root, config={}, dry_run=False, force=False
            )

        self.assertEqual(result, 0, "Expected return value 0 (file skipped)")
        actual = (self.target_root / "docs" / "components.json").read_text(
            encoding="utf-8"
        )
        self.assertEqual(actual, self.existing_content, "Existing file content was modified")


class TestDryRunDoesNotWrite(unittest.TestCase):
    """AC-3: dry_run=True reports intent (return 1) but writes no file."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.base = Path(self._tmpdir.name)
        self.target_root = self.base / "project"
        self.target_root.mkdir()
        self.templates_root = _make_templates_dir(self.base)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_dry_run_does_not_write(self):
        with mock.patch.object(build_phases, "TEMPLATES_DIR", self.templates_root):
            result = build_components_registry(
                self.target_root, config={}, dry_run=True, force=False
            )

        self.assertEqual(result, 1, "Expected return value 1 (would write in dry-run)")
        target = self.target_root / "docs" / "components.json"
        self.assertFalse(
            target.exists(), "dry-run must not create files on disk"
        )


class TestMissingTemplateReturnsZero(unittest.TestCase):
    """AC-4: when the template file is absent, phase returns 0 gracefully."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.base = Path(self._tmpdir.name)
        self.target_root = self.base / "project"
        self.target_root.mkdir()
        # Provide a templates dir that has no components.json.template inside it.
        empty_templates = self.base / "empty_templates"
        (empty_templates / "docs").mkdir(parents=True)
        self.empty_templates = empty_templates

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_missing_template_returns_zero(self):
        with mock.patch.object(build_phases, "TEMPLATES_DIR", self.empty_templates):
            result = build_components_registry(
                self.target_root, config={}, dry_run=False, force=False
            )

        self.assertEqual(result, 0, "Expected return value 0 when template is absent")
        target = self.target_root / "docs" / "components.json"
        self.assertFalse(target.exists(), "No file should be created when template is missing")


class TestForceFlagIsIgnored(unittest.TestCase):
    """AC-5: force=True must not overwrite an existing components.json."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.base = Path(self._tmpdir.name)
        self.target_root = self.base / "project"
        (self.target_root / "docs").mkdir(parents=True)
        self.existing_content = '{"user_data": "should survive"}\n'
        (self.target_root / "docs" / "components.json").write_text(
            self.existing_content, encoding="utf-8"
        )
        self.templates_root = _make_templates_dir(self.base)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_force_flag_is_ignored(self):
        with mock.patch.object(build_phases, "TEMPLATES_DIR", self.templates_root):
            result = build_components_registry(
                self.target_root, config={}, dry_run=False, force=True
            )

        self.assertEqual(result, 0, "Expected return value 0 (force ignored, file skipped)")
        actual = (self.target_root / "docs" / "components.json").read_text(
            encoding="utf-8"
        )
        self.assertEqual(
            actual, self.existing_content, "force=True must not overwrite components.json"
        )


if __name__ == "__main__":
    unittest.main()
