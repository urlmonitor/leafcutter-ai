"""
MODULE: test_build_ac_store_scaffold
GOAL: Unit tests for the build_ac_store_scaffold() phase function.
TICKET: EPIC-ACTraceabilityStore/02_ac_store_directory_scaffold.md
"""

from __future__ import annotations

import sys
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

sys.path.insert(0, str(_SCRIPTS_DIR))

from build_ac_store_scaffold import build_ac_store_scaffold  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _config() -> dict:
    """Minimal config dict — build_ac_store_scaffold does not consume config."""
    return {}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestScaffoldCreatesDirectory:
    """test_scaffold_creates_directory — scaffold creates the directory when absent."""

    def test_scaffold_creates_directory(self, tmp_path: Path) -> None:
        """Directory docs/acceptance-criteria/ is created when it does not exist."""
        target_root = tmp_path / "project"
        target_root.mkdir()

        build_ac_store_scaffold(target_root, _config(), dry_run=False, force=False)

        assert (target_root / "docs" / "acceptance-criteria").is_dir()


class TestScaffoldCreatesIndexYaml:
    """test_scaffold_creates_index_yaml — index.yaml exists after scaffold."""

    def test_scaffold_creates_index_yaml(self, tmp_path: Path) -> None:
        """index.yaml is installed when the directory is absent."""
        target_root = tmp_path / "project"
        target_root.mkdir()

        build_ac_store_scaffold(target_root, _config(), dry_run=False, force=False)

        index_yaml = target_root / "docs" / "acceptance-criteria" / "index.yaml"
        assert index_yaml.exists(), "index.yaml should be created by the scaffold phase"
        content = index_yaml.read_text(encoding="utf-8")
        # Must contain at least one example component entry
        assert "components:" in content
        assert "id:" in content


class TestScaffoldCreatesReadme:
    """test_scaffold_creates_readme — README.md exists after scaffold."""

    def test_scaffold_creates_readme(self, tmp_path: Path) -> None:
        """README.md is installed when the directory is absent."""
        target_root = tmp_path / "project"
        target_root.mkdir()

        build_ac_store_scaffold(target_root, _config(), dry_run=False, force=False)

        readme = target_root / "docs" / "acceptance-criteria" / "README.md"
        assert readme.exists(), "README.md should be created by the scaffold phase"


class TestScaffoldIdempotent:
    """test_scaffold_idempotent — second build run does not overwrite modified index.yaml."""

    def test_scaffold_idempotent(self, tmp_path: Path) -> None:
        """Second invocation preserves user-edited index.yaml."""
        target_root = tmp_path / "project"
        target_root.mkdir()

        # First run — installs scaffold
        build_ac_store_scaffold(target_root, _config(), dry_run=False, force=False)

        # User modifies index.yaml
        index_yaml = target_root / "docs" / "acceptance-criteria" / "index.yaml"
        user_content = "# User edited this file\ncomponents:\n  - id: myapp\n    prefix: APP\n"
        index_yaml.write_text(user_content, encoding="utf-8")

        # Second run — must NOT overwrite the user-edited file
        build_ac_store_scaffold(target_root, _config(), dry_run=False, force=False)

        assert index_yaml.read_text(encoding="utf-8") == user_content, (
            "build_ac_store_scaffold must not overwrite user-edited index.yaml"
        )

    def test_scaffold_idempotent_returns_zero_on_second_run(self, tmp_path: Path) -> None:
        """Second invocation returns 0 (nothing written)."""
        target_root = tmp_path / "project"
        target_root.mkdir()

        # First run
        first_count = build_ac_store_scaffold(target_root, _config(), dry_run=False, force=False)
        assert first_count > 0

        # Second run — nothing to write
        second_count = build_ac_store_scaffold(target_root, _config(), dry_run=False, force=False)
        assert second_count == 0


class TestValidateOnlyPasses:
    """test_validate_only_passes — dry_run mode reports intent but writes nothing."""

    def test_dry_run_writes_nothing(self, tmp_path: Path) -> None:
        """dry_run=True reports intent but does not create any files."""
        target_root = tmp_path / "project"
        target_root.mkdir()

        count = build_ac_store_scaffold(target_root, _config(), dry_run=True, force=False)

        # Count > 0 means it would write, but nothing is actually on disk
        assert count > 0
        assert not (target_root / "docs" / "acceptance-criteria").exists()

    def test_dry_run_on_existing_scaffold_returns_zero(self, tmp_path: Path) -> None:
        """dry_run=True returns 0 when all scaffold files already exist."""
        target_root = tmp_path / "project"
        target_root.mkdir()

        # Install scaffold first
        build_ac_store_scaffold(target_root, _config(), dry_run=False, force=False)

        # dry_run on already-present scaffold
        count = build_ac_store_scaffold(target_root, _config(), dry_run=True, force=False)
        assert count == 0
