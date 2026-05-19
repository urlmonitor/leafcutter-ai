"""
MODULE: test_build_precommit_integration
GOAL: Integration and regression tests for build_precommit_config(),
    _find_decision_history_index(), and _build_output_lines() in
    build_precommit.py (re-exported via build_phases.py).
BUSINESS CONTEXT: build_precommit_config() must preserve project-specific
    hooks on re-run, place package-managed hooks before the DECISION HISTORY
    section, and produce idempotent output. These filesystem-level tests
    complement the pure-unit tests in test_build_precommit_config.py.
ARCHITECTURE: Standard unittest. Uses tempfile.TemporaryDirectory for all
    synthetic project layouts. build_phases is imported via importlib to avoid
    sys.path contamination.

DOC_LINKS: None
DECISION HISTORY:
  - 2026-05-14 00:55 [epic-supervisor/T04]: Created by splitting from
    test_build_precommit_config.py to stay under 400-line limit. Contains
    integration tests for build_precommit_config() and regression guard for
    the package-managed-before-DECISION-HISTORY placement fix.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
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

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

_MANIFEST_HOOKS = [
    {
        "id": "check-build-drift",
        "name": "Check Build Drift",
        "entry": "python scripts/commit_guardian/run_hook.py scripts/commit_guardian/check_build_drift.py",
        "language": "system",
        "files": "^leafcutter/templates/",
        "stages": ["pre-commit"],
        "pass_filenames": False,
    },
    {
        "id": "check-secrets",
        "name": "Check Secrets",
        "entry": "python scripts/commit_guardian/run_hook.py scripts/commit_guardian/check_secrets.py",
        "language": "system",
        "stages": ["pre-commit"],
        "pass_filenames": False,
    },
]

_COMMIT_GUARDIAN_JSON = {
    "hooks_manifest": {
        "hooks": _MANIFEST_HOOKS,
    }
}


class TestFindDecisionHistoryIndex(unittest.TestCase):
    """Tests for _find_decision_history_index()."""

    def _lines(self, text: str) -> list[str]:
        return text.splitlines()

    def test_finds_decision_history_block(self):
        """Returns the index of the # === block that precedes DECISION HISTORY."""
        text = """\
fail_fast: true
# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-13 14:00 [Author]: Did something.
"""
        lines = self._lines(text)
        idx = _bp._find_decision_history_index(lines)
        self.assertEqual(idx, 1)  # line index 1 = # ===...

    def test_returns_minus_one_when_absent(self):
        """Returns -1 when no DECISION HISTORY block exists."""
        text = "fail_fast: true\nrepos:\n  - repo: local\n"
        lines = self._lines(text)
        idx = _bp._find_decision_history_index(lines)
        self.assertEqual(idx, -1)


class TestBuildOutputLinesDecisionHistoryPlacement(unittest.TestCase):
    """Regression guard: package-managed hooks must appear before DECISION HISTORY."""

    def _lines(self, text: str) -> list[str]:
        return text.splitlines()

    def test_hooks_before_decision_history(self):
        """Package-managed hooks are inserted before the DECISION HISTORY block."""
        existing = """\
fail_fast: true
repos:
  - repo: local
    hooks:

      - id: project-hook
        name: Project Hook
        entry: python run.py
        language: system
        stages: [pre-commit]
        pass_filenames: false
# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-01 00:00 [Author]: Initial.
"""
        clean_lines = _bp._strip_package_managed_blocks(self._lines(existing))
        hook_block = _bp._render_hook_yaml({
            "id": "pkg-hook",
            "name": "Pkg Hook",
            "entry": "python pkg.py",
            "language": "system",
            "stages": ["pre-commit"],
            "pass_filenames": False,
        })
        output = _bp._build_output_lines(clean_lines, [hook_block])

        pkg_idx = output.index("pkg-hook")
        dh_idx = output.index("DECISION HISTORY")
        self.assertLess(pkg_idx, dh_idx,
                        "package-managed hooks must appear before DECISION HISTORY")


class TestBuildPrecommitConfig(unittest.TestCase):
    """Tests for build_precommit_config() — integration-level."""

    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp_dir.name)

    def tearDown(self):
        self._tmp_dir.cleanup()

    def test_fresh_project_creates_config(self):
        """A fresh project with no .pre-commit-config.yaml gets one created."""
        cg_parent = self.tmp / "templates"
        cg_dir = cg_parent / "commit-guardian"
        cg_dir.mkdir(parents=True)
        (cg_dir / "commit_guardian.json").write_text(
            json.dumps(_COMMIT_GUARDIAN_JSON, indent=2), encoding="utf-8"
        )

        target = self.tmp / "project"
        target.mkdir()

        orig = _bp.TEMPLATES_DIR
        try:
            _bp.TEMPLATES_DIR = cg_parent
            count = _bp.build_precommit_config(target, {}, dry_run=False, force=True)
        finally:
            _bp.TEMPLATES_DIR = orig

        self.assertEqual(count, 1)
        config_path = target / ".pre-commit-config.yaml"
        self.assertTrue(config_path.exists())
        content = config_path.read_text(encoding="utf-8")
        self.assertIn("check-build-drift", content)
        self.assertIn("check-secrets", content)
        self.assertIn("@package-managed", content)

    def test_existing_project_specific_hooks_preserved(self):
        """Re-running build preserves project-specific hooks in the YAML."""
        cg_parent = self.tmp / "templates"
        cg_dir = cg_parent / "commit-guardian"
        cg_dir.mkdir(parents=True)
        (cg_dir / "commit_guardian.json").write_text(
            json.dumps(_COMMIT_GUARDIAN_JSON, indent=2), encoding="utf-8"
        )

        target = self.tmp / "project"
        target.mkdir()
        initial_config = """\
fail_fast: true
repos:
  - repo: local
    hooks:

      - id: check-alembic-chain
        name: Check Alembic Migration Chain Integrity
        entry: python scripts/check_alembic.py
        language: system
        stages: [pre-commit]
        pass_filenames: false
"""
        (target / ".pre-commit-config.yaml").write_text(initial_config, encoding="utf-8")

        orig = _bp.TEMPLATES_DIR
        try:
            _bp.TEMPLATES_DIR = cg_parent
            _bp.build_precommit_config(target, {}, dry_run=False, force=True)
        finally:
            _bp.TEMPLATES_DIR = orig

        content = (target / ".pre-commit-config.yaml").read_text(encoding="utf-8")
        self.assertIn("check-alembic-chain", content)
        self.assertIn("check-build-drift", content)
        self.assertIn("check-secrets", content)

    def test_idempotent_reruns(self):
        """Running build twice produces the same output (no duplicate hooks)."""
        cg_parent = self.tmp / "templates"
        cg_dir = cg_parent / "commit-guardian"
        cg_dir.mkdir(parents=True)
        (cg_dir / "commit_guardian.json").write_text(
            json.dumps(_COMMIT_GUARDIAN_JSON, indent=2), encoding="utf-8"
        )

        target = self.tmp / "project"
        target.mkdir()

        orig = _bp.TEMPLATES_DIR
        try:
            _bp.TEMPLATES_DIR = cg_parent
            _bp.build_precommit_config(target, {}, dry_run=False, force=True)
            first = (target / ".pre-commit-config.yaml").read_text(encoding="utf-8")
            _bp.build_precommit_config(target, {}, dry_run=False, force=True)
            second = (target / ".pre-commit-config.yaml").read_text(encoding="utf-8")
        finally:
            _bp.TEMPLATES_DIR = orig

        self.assertEqual(
            first.count("id: check-build-drift"),
            second.count("id: check-build-drift"),
        )
        self.assertEqual(first.count("@package-managed"), second.count("@package-managed"))

    def test_removed_hook_disappears_on_rerun(self):
        """If a hook is removed from the manifest, re-running build removes it."""
        hook_a = {
            "id": "hook-a",
            "name": "Hook A",
            "entry": "python scripts/hook_a.py",
            "language": "system",
            "stages": ["pre-commit"],
            "pass_filenames": False,
        }
        hook_b = {
            "id": "hook-b",
            "name": "Hook B",
            "entry": "python scripts/hook_b.py",
            "language": "system",
            "stages": ["pre-commit"],
            "pass_filenames": False,
        }

        cg_parent = self.tmp / "templates"
        cg_dir = cg_parent / "commit-guardian"
        cg_dir.mkdir(parents=True)
        cg_json = cg_dir / "commit_guardian.json"

        target = self.tmp / "project"
        target.mkdir()

        orig = _bp.TEMPLATES_DIR
        try:
            _bp.TEMPLATES_DIR = cg_parent
            cg_json.write_text(
                json.dumps({"hooks_manifest": {"hooks": [hook_a, hook_b]}}, indent=2),
                encoding="utf-8",
            )
            _bp.build_precommit_config(target, {}, dry_run=False, force=True)
            first = (target / ".pre-commit-config.yaml").read_text(encoding="utf-8")
            self.assertIn("hook-a", first)
            self.assertIn("hook-b", first)

            cg_json.write_text(
                json.dumps({"hooks_manifest": {"hooks": [hook_a]}}, indent=2),
                encoding="utf-8",
            )
            _bp.build_precommit_config(target, {}, dry_run=False, force=True)
            second = (target / ".pre-commit-config.yaml").read_text(encoding="utf-8")
            self.assertIn("hook-a", second)
            self.assertNotIn("hook-b", second)
        finally:
            _bp.TEMPLATES_DIR = orig

    def test_dry_run_does_not_write(self):
        """Dry-run returns 1 (would write) but does not create the file."""
        cg_parent = self.tmp / "templates"
        cg_dir = cg_parent / "commit-guardian"
        cg_dir.mkdir(parents=True)
        (cg_dir / "commit_guardian.json").write_text(
            json.dumps(_COMMIT_GUARDIAN_JSON, indent=2), encoding="utf-8"
        )
        target = self.tmp / "project"
        target.mkdir()

        orig = _bp.TEMPLATES_DIR
        try:
            _bp.TEMPLATES_DIR = cg_parent
            count = _bp.build_precommit_config(target, {}, dry_run=True, force=True)
        finally:
            _bp.TEMPLATES_DIR = orig

        self.assertEqual(count, 1)
        self.assertFalse((target / ".pre-commit-config.yaml").exists())

    def test_empty_manifest_returns_zero(self):
        """An empty hooks list returns 0 (nothing to write)."""
        cg_parent = self.tmp / "templates"
        cg_dir = cg_parent / "commit-guardian"
        cg_dir.mkdir(parents=True)
        (cg_dir / "commit_guardian.json").write_text(
            json.dumps({"hooks_manifest": {"hooks": []}}), encoding="utf-8"
        )
        target = self.tmp / "project"
        target.mkdir()

        orig = _bp.TEMPLATES_DIR
        try:
            _bp.TEMPLATES_DIR = cg_parent
            count = _bp.build_precommit_config(target, {}, dry_run=False, force=True)
        finally:
            _bp.TEMPLATES_DIR = orig

        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
