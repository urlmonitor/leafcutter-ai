"""
MODULE: test_build_version_wiring
GOAL: Verify that build.py correctly wires compute_next_version.py to
    auto-apply SemVer during builds, respecting dry-run and validate-only flags.
BUSINESS CONTEXT: These tests guard the version-wiring integration added by
    TICKET-20260527-WireVersionIntoBuild. They confirm that every build run
    surfaces the computed version and writes a VERSION file, and that the
    dry-run and validate-only paths honour their contracts.
ARCHITECTURE: Tests import build.py helpers directly (avoiding subprocess
    overhead) and mock filesystem writes using tmp_path. The main() function is
    tested with monkeypatching to stub out expensive build phases while leaving
    the version-wiring logic under test.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

# Ensure scripts/ is importable
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
        json.dumps({"project_name": "test-project", "docs_root": "docs/", "output_root": ".leafcutter"}),
        encoding="utf-8",
    )
    return target


def _make_argv(target_root: Path, extra: list[str] | None = None) -> list[str]:
    """Build a minimal argv for build.main()."""
    base = ["--target-dir", str(target_root), "--no-shims"]
    return base + (extra or [])


# ---------------------------------------------------------------------------
# Helpers: stub out all expensive build phases so tests complete quickly
# ---------------------------------------------------------------------------


def _noop_run_phases(*args, **kwargs) -> int:  # noqa: ANN002
    """Stub that replaces _run_phases — does nothing and returns 0."""
    return 0


def _noop_write_manifest(*args, **kwargs) -> None:  # noqa: ANN002
    """Stub that replaces write_build_manifest — does nothing."""


def _noop_check_halt(*args, **kwargs):  # noqa: ANN002
    """Stub that replaces check_halt_guard — returns no-halt result."""
    result = MagicMock()
    result.should_halt = False
    return result


def _noop_cleanup(*args, **kwargs) -> int:  # noqa: ANN002
    """Stub that replaces _cleanup_stale_paths — does nothing and returns 0."""
    return 0


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_version_printed_in_build_output(target_root: Path, capsys: pytest.CaptureFixture) -> None:
    """A normal build run must print 'Build version: vX.Y.Z' in stdout.

    Verifies Acceptance Criterion 1: the computed version is printed in the
    build output.
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
    ):
        rc = _build.main(_make_argv(target_root))

    assert rc == 0, f"build.main returned {rc}"

    captured = capsys.readouterr()
    import re
    version_pattern = re.compile(r"Build version:\s+v\d+\.\d+\.\d+")
    assert version_pattern.search(captured.out), (
        f"'Build version: vX.Y.Z' not found in stdout.\nstdout: {captured.out}"
    )


def test_version_file_written(target_root: Path) -> None:
    """A normal (non-dry-run) build must write a VERSION file to target_root.

    Verifies Acceptance Criterion 1: VERSION file exists and contains a bare
    SemVer string matching v\\d+\\.\\d+\\.\\d+.
    """
    import re

    with (
        patch.object(_build, "_run_phases", _noop_run_phases),
        patch.object(_build, "write_build_manifest", _noop_write_manifest),
        patch.object(_build, "check_halt_guard", _noop_check_halt),
        patch.object(_build, "_cleanup_stale_paths", _noop_cleanup),
        patch.object(_build, "write_lock_file", lambda *a, **k: None),
        patch.object(_build, "_resolve_package_sha", lambda *a: "abc123"),
        patch.object(_build, "scan_for_placeholders", lambda *a: []),
        patch.object(_build, "check_referential_integrity", lambda *a, **k: []),
    ):
        rc = _build.main(_make_argv(target_root))

    assert rc == 0, f"build.main returned {rc}"

    version_file = target_root / "VERSION"
    assert version_file.exists(), f"VERSION file was not written to {target_root}"

    version_content = version_file.read_text(encoding="utf-8").strip()
    assert re.fullmatch(r"v\d+\.\d+\.\d+", version_content), (
        f"VERSION file content '{version_content}' does not match vX.Y.Z pattern."
    )


def test_dry_run_no_version_file(target_root: Path, capsys: pytest.CaptureFixture) -> None:
    """A --dry-run build must print the version but NOT write the VERSION file.

    Verifies Acceptance Criterion 2: dry-run prints version, skips all writes.
    """
    import re

    with (
        patch.object(_build, "_run_phases", _noop_run_phases),
        patch.object(_build, "write_build_manifest", _noop_write_manifest),
        patch.object(_build, "check_halt_guard", _noop_check_halt),
        patch.object(_build, "_cleanup_stale_paths", _noop_cleanup),
        patch.object(_build, "write_lock_file", lambda *a, **k: None),
        patch.object(_build, "_resolve_package_sha", lambda *a: "abc123"),
        patch.object(_build, "scan_for_placeholders", lambda *a: []),
        patch.object(_build, "check_referential_integrity", lambda *a, **k: []),
    ):
        rc = _build.main(_make_argv(target_root, extra=["--dry-run"]))

    assert rc == 0, f"build.main --dry-run returned {rc}"

    captured = capsys.readouterr()

    # Version must still be printed in dry-run mode
    version_pattern = re.compile(r"Build version:\s+v\d+\.\d+\.\d+")
    assert version_pattern.search(captured.out), (
        f"'Build version: vX.Y.Z' not found in dry-run stdout.\nstdout: {captured.out}"
    )

    # VERSION file must NOT exist in dry-run mode
    version_file = target_root / "VERSION"
    assert not version_file.exists(), (
        f"VERSION file was written during --dry-run (should not be).\nstdout: {captured.out}"
    )

    # The DRY-RUN intent message must appear
    assert "[DRY-RUN] would write" in captured.out, (
        f"Expected '[DRY-RUN] would write' in stdout.\nstdout: {captured.out}"
    )


def test_validate_only_skips_version(target_root: Path, capsys: pytest.CaptureFixture) -> None:
    """A --validate-only build must skip version computation entirely.

    Verifies Acceptance Criterion 3: validate-only exits after config check,
    prints no version line, and writes no VERSION file.
    """
    import re

    # validate-only exits before any stubbed code is reached, so stubs are
    # present as a safety net but may not be called.
    with (
        patch.object(_build, "_run_phases", _noop_run_phases),
        patch.object(_build, "write_build_manifest", _noop_write_manifest),
        patch.object(_build, "check_halt_guard", _noop_check_halt),
        patch.object(_build, "_cleanup_stale_paths", _noop_cleanup),
        patch.object(_build, "write_lock_file", lambda *a, **k: None),
        patch.object(_build, "_resolve_package_sha", lambda *a: "abc123"),
    ):
        rc = _build.main(_make_argv(target_root, extra=["--validate-only"]))

    assert rc == 0, f"build.main --validate-only returned {rc}"

    captured = capsys.readouterr()

    # No 'Build version:' line in validate-only output
    version_pattern = re.compile(r"Build version:")
    assert not version_pattern.search(captured.out), (
        f"'Build version:' should NOT appear in --validate-only stdout.\nstdout: {captured.out}"
    )

    # No VERSION file
    version_file = target_root / "VERSION"
    assert not version_file.exists(), (
        f"VERSION file was written during --validate-only (should not be).\nstdout: {captured.out}"
    )

    # Should print the config-validation success message
    assert "Config validation complete" in captured.out, (
        f"Expected 'Config validation complete' in validate-only stdout.\nstdout: {captured.out}"
    )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-27 12:30 [test-writer/TICKET-20260527-WireVersionIntoBuild]: (#TICKETLESS reason=standalone-ticket-closeout)
#   Created module. Four tests cover the four acceptance criteria: version
#   printed, VERSION file written, dry-run skips write, validate-only skips
#   computation. Tests import build.py directly (monkeypatching expensive
#   phases) to avoid subprocess overhead and WSL filesystem slowness.
# ====================================================================
