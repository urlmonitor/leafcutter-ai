"""
MODULE: test_build_package_version
GOAL: Verify that build.py reads config/version.json and surfaces the package
    version in build output and as a deployed LEAFCUTTER_VERSION file.
BUSINESS CONTEXT: AC ACD-1100e-2 requires that a user examining the deployed
    output can determine they are running leafcutter v2.0.0 without reading the
    source package directly. These tests confirm that both the build log message
    ("Package version: 2.0.0") and the LEAFCUTTER_VERSION file satisfy the AC.
ARCHITECTURE: Tests import build.py directly and monkeypatch expensive phases.
    The _read_package_version helper is tested in isolation against a temp
    config/version.json; the main() integration tests verify end-to-end wiring.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import build as _build  # noqa: E402 — after sys.path setup


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def target_root(tmp_path: Path) -> Path:
    """Minimal target directory with a valid skills_config.json."""
    target = tmp_path / "target"
    target.mkdir()
    config_dir = target / ".claude"
    config_dir.mkdir()
    config_file = config_dir / "skills_config.json"
    config_file.write_text(
        json.dumps(
            {
                "project_name": "test-project",
                "docs_root": "docs/",
                "output_root": ".leafcutter",
            }
        ),
        encoding="utf-8",
    )
    return target


@pytest.fixture()
def package_root_with_version(tmp_path: Path) -> Path:
    """Package root with config/version.json containing 2.0.0."""
    pkg = tmp_path / "pkg"
    cfg = pkg / "config"
    cfg.mkdir(parents=True)
    (cfg / "version.json").write_text(
        json.dumps({"version": "2.0.0"}), encoding="utf-8"
    )
    return pkg


@pytest.fixture()
def package_root_no_version(tmp_path: Path) -> Path:
    """Package root with no config/version.json."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    return pkg


def _make_argv(target_root: Path, extra: list[str] | None = None) -> list[str]:
    """Build a minimal argv for build.main()."""
    base = ["--target-dir", str(target_root), "--no-shims"]
    return base + (extra or [])


# ---------------------------------------------------------------------------
# Helpers: stub out expensive build phases
# ---------------------------------------------------------------------------


def _noop_run_phases(*args, **kwargs) -> int:  # noqa: ANN002
    return 0


def _noop_write_manifest(*args, **kwargs) -> None:  # noqa: ANN002
    pass


def _noop_check_halt(*args, **kwargs):  # noqa: ANN002
    result = MagicMock()
    result.should_halt = False
    return result


def _noop_cleanup(*args, **kwargs) -> int:  # noqa: ANN002
    return 0


def _noop_validate_registry(*args, **kwargs) -> list:  # noqa: ANN002
    """Stub that replaces validate_agent_registry — skips pre-existing registry errors."""
    return []


def _build_patches(target_root: Path):
    """Return a context manager that stubs all expensive build phases."""
    return (
        patch.object(_build, "_run_phases", _noop_run_phases),
        patch.object(_build, "write_build_manifest", _noop_write_manifest),
        patch.object(_build, "check_halt_guard", _noop_check_halt),
        patch.object(_build, "_cleanup_stale_paths", _noop_cleanup),
        patch.object(_build, "write_lock_file", lambda *a, **k: None),
        patch.object(_build, "_resolve_package_sha", lambda *a: "abc123"),
        patch.object(_build, "scan_for_placeholders", lambda *a: []),
        patch.object(_build, "check_referential_integrity", lambda *a, **k: []),
        patch.object(_build, "validate_agent_registry", _noop_validate_registry),
    )


# ---------------------------------------------------------------------------
# Unit tests: _read_package_version helper
# ---------------------------------------------------------------------------


class TestReadPackageVersion:
    """Unit tests for the _read_package_version() helper function."""

    def test_reads_version_from_valid_file(
        self, package_root_with_version: Path
    ) -> None:
        """Returns the version string from a valid config/version.json."""
        result = _build._read_package_version(package_root_with_version)
        assert result == "2.0.0"

    def test_returns_unknown_when_file_absent(
        self, package_root_no_version: Path
    ) -> None:
        """Returns 'unknown' when config/version.json does not exist."""
        result = _build._read_package_version(package_root_no_version)
        assert result == "unknown"

    def test_returns_unknown_for_malformed_json(self, tmp_path: Path) -> None:
        """Returns 'unknown' when config/version.json contains invalid JSON."""
        cfg = tmp_path / "config"
        cfg.mkdir()
        (cfg / "version.json").write_text("not valid json!!!", encoding="utf-8")
        result = _build._read_package_version(tmp_path)
        assert result == "unknown"

    def test_returns_unknown_when_version_key_missing(self, tmp_path: Path) -> None:
        """Returns 'unknown' when version.json has no 'version' key."""
        cfg = tmp_path / "config"
        cfg.mkdir()
        (cfg / "version.json").write_text(
            json.dumps({"other_key": "1.0.0"}), encoding="utf-8"
        )
        result = _build._read_package_version(tmp_path)
        assert result == "unknown"

    def test_reads_non_standard_version(self, tmp_path: Path) -> None:
        """Returns the exact string value of the 'version' key."""
        cfg = tmp_path / "config"
        cfg.mkdir()
        (cfg / "version.json").write_text(
            json.dumps({"version": "3.1.4-rc1"}), encoding="utf-8"
        )
        result = _build._read_package_version(tmp_path)
        assert result == "3.1.4-rc1"


# ---------------------------------------------------------------------------
# Integration tests: package_version in build.main() output
# ---------------------------------------------------------------------------


class TestPackageVersionInBuildOutput:
    """Integration tests confirming package version appears in build output."""

    def test_package_version_printed_in_stdout(
        self, target_root: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """A normal build run must print 'Package version: X.Y.Z' in stdout.

        Satisfies AC ACD-1100e-2: build log message includes the package version.
        """
        with (
            patch.object(_build, "_run_phases", _noop_run_phases),
            patch.object(_build, "write_build_manifest", _noop_write_manifest),
            patch.object(_build, "check_halt_guard", _noop_check_halt),
            patch.object(_build, "_cleanup_stale_paths", _noop_cleanup),
            patch.object(_build, "write_lock_file", lambda *a, **k: None),
            patch.object(_build, "_resolve_package_sha", lambda *a: "abc123"),
            patch.object(_build, "scan_for_placeholders", lambda *a: []),
            patch.object(_build, "check_referential_integrity", lambda *a, **k: []),
            patch.object(_build, "validate_agent_registry", _noop_validate_registry),
        ):
            rc = _build.main(_make_argv(target_root))

        assert rc == 0, f"build.main returned {rc}"
        captured = capsys.readouterr()
        assert "Package version:" in captured.out, (
            f"'Package version:' not found in stdout.\nstdout: {captured.out}"
        )

    def test_leafcutter_version_file_written(self, target_root: Path) -> None:
        """A normal build must write LEAFCUTTER_VERSION to target_root.

        Satisfies AC ACD-1100e-2: deployed file lets user determine package version
        without reading the source package directly.
        """
        with (
            patch.object(_build, "_run_phases", _noop_run_phases),
            patch.object(_build, "write_build_manifest", _noop_write_manifest),
            patch.object(_build, "check_halt_guard", _noop_check_halt),
            patch.object(_build, "_cleanup_stale_paths", _noop_cleanup),
            patch.object(_build, "write_lock_file", lambda *a, **k: None),
            patch.object(_build, "_resolve_package_sha", lambda *a: "abc123"),
            patch.object(_build, "scan_for_placeholders", lambda *a: []),
            patch.object(_build, "check_referential_integrity", lambda *a, **k: []),
            patch.object(_build, "validate_agent_registry", _noop_validate_registry),
        ):
            rc = _build.main(_make_argv(target_root))

        assert rc == 0, f"build.main returned {rc}"
        lv_file = target_root / "LEAFCUTTER_VERSION"
        assert lv_file.exists(), (
            f"LEAFCUTTER_VERSION file was not written to {target_root}"
        )
        content = lv_file.read_text(encoding="utf-8").strip()
        assert content, "LEAFCUTTER_VERSION file must not be empty"

    def test_leafcutter_version_matches_config_version_json(
        self, target_root: Path
    ) -> None:
        """LEAFCUTTER_VERSION content must match config/version.json version field.

        Core AC check: the deployed file reflects the version from config/version.json.
        """
        # Read the expected version from the real config/version.json in this repo
        real_version_path = _REPO_ROOT / "config" / "version.json"
        if real_version_path.exists():
            expected = json.loads(
                real_version_path.read_text(encoding="utf-8")
            )["version"]
        else:
            pytest.skip("config/version.json not present — skipping version-match test")

        with (
            patch.object(_build, "_run_phases", _noop_run_phases),
            patch.object(_build, "write_build_manifest", _noop_write_manifest),
            patch.object(_build, "check_halt_guard", _noop_check_halt),
            patch.object(_build, "_cleanup_stale_paths", _noop_cleanup),
            patch.object(_build, "write_lock_file", lambda *a, **k: None),
            patch.object(_build, "_resolve_package_sha", lambda *a: "abc123"),
            patch.object(_build, "scan_for_placeholders", lambda *a: []),
            patch.object(_build, "check_referential_integrity", lambda *a, **k: []),
            patch.object(_build, "validate_agent_registry", _noop_validate_registry),
        ):
            rc = _build.main(_make_argv(target_root))

        assert rc == 0, f"build.main returned {rc}"
        lv_file = target_root / "LEAFCUTTER_VERSION"
        actual = lv_file.read_text(encoding="utf-8").strip()
        assert actual == expected, (
            f"LEAFCUTTER_VERSION file contains '{actual}' but "
            f"config/version.json has version '{expected}'"
        )

    def test_dry_run_no_leafcutter_version_file(
        self, target_root: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """A --dry-run build must NOT write the LEAFCUTTER_VERSION file."""
        with (
            patch.object(_build, "_run_phases", _noop_run_phases),
            patch.object(_build, "write_build_manifest", _noop_write_manifest),
            patch.object(_build, "check_halt_guard", _noop_check_halt),
            patch.object(_build, "_cleanup_stale_paths", _noop_cleanup),
            patch.object(_build, "write_lock_file", lambda *a, **k: None),
            patch.object(_build, "_resolve_package_sha", lambda *a: "abc123"),
            patch.object(_build, "scan_for_placeholders", lambda *a: []),
            patch.object(_build, "check_referential_integrity", lambda *a, **k: []),
            patch.object(_build, "validate_agent_registry", _noop_validate_registry),
        ):
            rc = _build.main(_make_argv(target_root, extra=["--dry-run"]))

        assert rc == 0, f"build.main --dry-run returned {rc}"

        lv_file = target_root / "LEAFCUTTER_VERSION"
        assert not lv_file.exists(), (
            "LEAFCUTTER_VERSION file was written during --dry-run (should not be)"
        )

        captured = capsys.readouterr()
        # Dry-run intent must be printed
        assert "LEAFCUTTER_VERSION" in captured.out, (
            f"Expected 'LEAFCUTTER_VERSION' in dry-run stdout.\nstdout: {captured.out}"
        )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-06-10 [test-writer/EPIC-AcPipelineConsolidation/12]: (#EPIC-AcPipelineConsolidation/12)
#   Created module. Tests cover: _read_package_version unit tests (valid file,
#   absent file, malformed JSON, missing key, non-standard version); integration
#   tests for "Package version:" log line in stdout; LEAFCUTTER_VERSION file
#   written with correct content; dry-run suppresses file write but prints intent.
#   AC ACD-1100e-2 satisfied by the combination of log message and deployed file.
# ====================================================================
