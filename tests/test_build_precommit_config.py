"""
MODULE: test_build_precommit_config
GOAL: Unit tests for _render_hook_yaml() and _strip_package_managed_blocks()
    in build_precommit.py (re-exported via build_phases.py).
BUSINESS CONTEXT: The pre-commit-config generation phase is a load-bearing
    build step. These unit tests verify the YAML rendering and sentinel-block
    stripping logic in isolation, without touching the filesystem.
ARCHITECTURE: Standard unittest. No database, no network. build_phases is
    imported via importlib to avoid sys.path contamination.

DOC_LINKS: None
DECISION HISTORY:
  - 2026-05-14 00:55 [epic-supervisor/T04]: Split into two files: unit tests
    here, integration + regression tests in test_build_precommit_integration.py.
    Required to keep each file under the 400-line limit.
  - 2026-05-14 00:45 [epic-supervisor/T04]: Added tests for
    _find_decision_history_index and package-managed-before-decision-history
    placement (regression guard for T04 bug fix).
  - 2026-05-13 15:30 [epic-supervisor/T03]: Created for T03 acceptance criteria.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Dynamic import of build_phases (avoids polluting sys.path permanently)
# ---------------------------------------------------------------------------
_SCRIPTS_DIR = (
    Path(__file__).resolve().parent.parent
    / "scripts"
)


def _load_build_phases():
    """Load build_phases module via importlib."""
    scripts_str = str(_SCRIPTS_DIR)
    if scripts_str not in sys.path:
        sys.path.insert(0, scripts_str)

    spec = importlib.util.spec_from_file_location(
        "build_phases", _SCRIPTS_DIR / "build_phases.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["build_phases"] = mod
    spec.loader.exec_module(mod)
    return mod


_bp = _load_build_phases()


class TestRenderHookYaml(unittest.TestCase):
    """Tests for _render_hook_yaml()."""

    def test_basic_hook_renders_id_and_name(self):
        """A minimal hook dict produces id, name, entry, language, stages, pass_filenames."""
        hook = {
            "id": "my-hook",
            "name": "My Hook",
            "entry": "python scripts/run.py",
            "language": "system",
            "stages": ["pre-commit"],
            "pass_filenames": False,
        }
        yaml = _bp._render_hook_yaml(hook)
        self.assertIn("- id: my-hook", yaml)
        self.assertIn("name: My Hook  # @package-managed", yaml)
        self.assertIn("entry: python scripts/run.py", yaml)
        self.assertIn("language: system", yaml)
        self.assertIn("stages: [pre-commit]", yaml)
        self.assertIn("pass_filenames: false", yaml)

    def test_optional_files_field(self):
        hook = {
            "id": "x",
            "name": "X",
            "entry": "e",
            "language": "system",
            "files": "^foo/",
            "stages": ["pre-commit"],
            "pass_filenames": True,
        }
        yaml = _bp._render_hook_yaml(hook)
        self.assertIn("files: ^foo/", yaml)
        self.assertIn("pass_filenames: true", yaml)

    def test_types_field(self):
        hook = {
            "id": "x",
            "name": "X",
            "entry": "e",
            "language": "system",
            "types": ["python"],
            "stages": ["pre-commit"],
            "pass_filenames": False,
        }
        yaml = _bp._render_hook_yaml(hook)
        self.assertIn("types: [python]", yaml)
        self.assertNotIn("types_or", yaml)

    def test_types_or_field(self):
        hook = {
            "id": "x",
            "name": "X",
            "entry": "e",
            "language": "system",
            "types_or": ["python", "sql"],
            "stages": ["pre-commit"],
            "pass_filenames": False,
        }
        yaml = _bp._render_hook_yaml(hook)
        self.assertIn("types_or: [python, sql]", yaml)
        self.assertNotIn("types:", yaml)

    def test_always_run(self):
        hook = {
            "id": "x",
            "name": "X",
            "entry": "e",
            "language": "system",
            "stages": ["pre-commit"],
            "pass_filenames": False,
            "always_run": True,
        }
        yaml = _bp._render_hook_yaml(hook)
        self.assertIn("always_run: true", yaml)

    def test_sentinel_marker_present(self):
        hook = {
            "id": "x",
            "name": "X",
            "entry": "e",
            "language": "system",
            "stages": ["pre-commit"],
            "pass_filenames": False,
        }
        yaml = _bp._render_hook_yaml(hook)
        self.assertIn("@package-managed", yaml)


class TestStripPackageManagedBlocks(unittest.TestCase):
    """Tests for _strip_package_managed_blocks()."""

    def _lines(self, text: str) -> list[str]:
        return text.splitlines()

    def test_removes_single_package_managed_block(self):
        yaml_text = """\
fail_fast: true
repos:
  - repo: local
    hooks:

      # --- package-managed hooks (do not edit below) ---

      - id: check-build-drift
        name: Check Build Drift  # @package-managed
        entry: python scripts/run.py
        language: system
        stages: [pre-commit]
        pass_filenames: false
"""
        result = _bp._strip_package_managed_blocks(self._lines(yaml_text))
        joined = "\n".join(result)
        self.assertNotIn("@package-managed", joined)
        self.assertNotIn("check-build-drift", joined)
        self.assertIn("fail_fast: true", joined)

    def test_preserves_project_specific_hook(self):
        yaml_text = """\
fail_fast: true
repos:
  - repo: local
    hooks:

      - id: check-alembic-chain
        name: Check Alembic Migration Chain Integrity
        entry: python scripts/run.py
        language: system
        stages: [pre-commit]
        pass_filenames: false

      # --- package-managed hooks (do not edit below) ---

      - id: check-build-drift
        name: Check Build Drift  # @package-managed
        entry: python scripts/run.py
        language: system
        stages: [pre-commit]
        pass_filenames: false
"""
        result = _bp._strip_package_managed_blocks(self._lines(yaml_text))
        joined = "\n".join(result)
        self.assertIn("check-alembic-chain", joined)
        self.assertNotIn("check-build-drift", joined)
        self.assertNotIn("@package-managed", joined)

    def test_idempotent_on_clean_file(self):
        """Stripping a file with no package-managed blocks returns it unchanged."""
        yaml_text = """\
fail_fast: true
repos:
  - repo: local
    hooks:
      - id: my-hook
        name: My Hook
        entry: e
        language: system
        stages: [pre-commit]
        pass_filenames: false
"""
        lines = self._lines(yaml_text)
        result = _bp._strip_package_managed_blocks(lines)
        self.assertEqual(lines, result)

    def test_preserves_decision_history_after_sentinel(self):
        """DECISION HISTORY block after # --- sentinel is preserved, not stripped."""
        yaml_text = """\
fail_fast: true
repos:
  - repo: local
    hooks:

      # --- package-managed hooks (do not edit below) ---

      - id: check-build-drift
        name: Check Build Drift  # @package-managed
        entry: python scripts/run.py
        language: system
        stages: [pre-commit]
        pass_filenames: false
# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-01 00:00 [Author]: Initial.
# ====================================================================
"""
        result = _bp._strip_package_managed_blocks(self._lines(yaml_text))
        joined = "\n".join(result)
        self.assertIn("DECISION HISTORY", joined)
        self.assertNotIn("check-build-drift", joined)


if __name__ == "__main__":
    unittest.main()
