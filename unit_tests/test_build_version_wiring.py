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

    PATCH TARGETS (BP-100n-4): a stub only intercepts if it replaces the name
    at the module whose globals the CALL SITE reads. ``main()`` still lives in
    build.py, but BP-100n-4 moved most of its inline steps into
    ``build_main_helpers``; the steps that call ``write_build_manifest``,
    ``check_halt_guard``, ``write_lock_file``, ``_resolve_package_sha``,
    ``scan_for_placeholders`` and ``check_referential_integrity`` now resolve
    those names through ``build_main_helpers``' globals, so those six are
    patched on ``_bmh``. The remaining stubs stay on ``_build`` because
    ``main()`` still reads them from build.py's own globals (``_run_phases``
    directly; ``_cleanup_stale_paths`` / ``_check_script_reference_guard`` are
    read there and passed into the helpers as parameters). Patching the wrong
    module is silent: the attribute is rebound, nobody reads it, and the test
    goes green while asserting nothing — see
    ``test_write_build_manifest_stub_actually_intercepts``.
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
import build_main_helpers as _bmh  # noqa: E402 — after sys.path setup


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
        patch.object(_bmh, "write_build_manifest", _noop_write_manifest),
        patch.object(_bmh, "check_halt_guard", _noop_check_halt),
        patch.object(_build, "_cleanup_stale_paths", _noop_cleanup),
        patch.object(_bmh, "write_lock_file", lambda *a, **k: None),
        patch.object(_bmh, "_resolve_package_sha", lambda *a: "abc123"),
        patch.object(_bmh, "scan_for_placeholders", lambda *a: []),
        patch.object(_bmh, "check_referential_integrity", lambda *a, **k: []),
        patch.object(_build, "_check_script_reference_guard", lambda *a, **k: 0),
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
        patch.object(_bmh, "write_build_manifest", _noop_write_manifest),
        patch.object(_bmh, "check_halt_guard", _noop_check_halt),
        patch.object(_build, "_cleanup_stale_paths", _noop_cleanup),
        patch.object(_bmh, "write_lock_file", lambda *a, **k: None),
        patch.object(_bmh, "_resolve_package_sha", lambda *a: "abc123"),
        patch.object(_bmh, "scan_for_placeholders", lambda *a: []),
        patch.object(_bmh, "check_referential_integrity", lambda *a, **k: []),
        patch.object(_build, "_check_script_reference_guard", lambda *a, **k: 0),
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
        patch.object(_bmh, "write_build_manifest", _noop_write_manifest),
        patch.object(_bmh, "check_halt_guard", _noop_check_halt),
        patch.object(_build, "_cleanup_stale_paths", _noop_cleanup),
        patch.object(_bmh, "write_lock_file", lambda *a, **k: None),
        patch.object(_bmh, "_resolve_package_sha", lambda *a: "abc123"),
        patch.object(_bmh, "scan_for_placeholders", lambda *a: []),
        patch.object(_bmh, "check_referential_integrity", lambda *a, **k: []),
        patch.object(_build, "_check_script_reference_guard", lambda *a, **k: 0),
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
        patch.object(_bmh, "write_build_manifest", _noop_write_manifest),
        patch.object(_bmh, "check_halt_guard", _noop_check_halt),
        patch.object(_build, "_cleanup_stale_paths", _noop_cleanup),
        patch.object(_bmh, "write_lock_file", lambda *a, **k: None),
        patch.object(_bmh, "_resolve_package_sha", lambda *a: "abc123"),
        patch.object(_build, "_check_script_reference_guard", lambda *a, **k: 0),
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


def test_write_build_manifest_stub_actually_intercepts(target_root: Path) -> None:
    """The manifest stub must be installed where main() RESOLVES the name.

    Regression guard for the BP-100n-4 refactor. Every test above stubs
    ``write_build_manifest`` so ``main()`` stays fast and writes no real
    manifest. A stub installed on the WRONG module is silent: it rebinds a
    name nobody reads, no AttributeError is raised, the suite goes green — and
    the real manifest step runs anyway, unasserted. ``patch.object`` only
    protects against the name being ABSENT; it cannot tell you the name is the
    one the call site reads.

    Asserting the spy was actually called is what distinguishes "stubbed" from
    "merely rebound", so it also pins the correct patch module for the sibling
    stubs in this file and in test_build_package_version.py.
    """
    spy = MagicMock(return_value=None)
    with (
        patch.object(_build, "_run_phases", _noop_run_phases),
        patch.object(_bmh, "write_build_manifest", spy),
        patch.object(_bmh, "check_halt_guard", _noop_check_halt),
        patch.object(_build, "_cleanup_stale_paths", _noop_cleanup),
        patch.object(_bmh, "write_lock_file", lambda *a, **k: None),
        patch.object(_bmh, "_resolve_package_sha", lambda *a: "abc123"),
        patch.object(_bmh, "scan_for_placeholders", lambda *a: []),
        patch.object(_bmh, "check_referential_integrity", lambda *a, **k: []),
        patch.object(_build, "_check_script_reference_guard", lambda *a, **k: 0),
    ):
        rc = _build.main(_make_argv(target_root))

    assert rc == 0, f"build.main returned {rc}"
    assert spy.call_count == 1, (
        "write_build_manifest stub was never called, so every stub in this "
        "module is patching a name main() does not resolve — the tests are "
        "vacuous and the real manifest step ran unasserted. Patch the module "
        "whose globals hold the call site (build_main_helpers), not build."
    )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-14 [python-coder/BP-100n-4]: Retargeted six stubs from `_build` to (#BP-100n-4)
#   `_bmh` (build_main_helpers) and added
#   test_write_build_manifest_stub_actually_intercepts.
#   BP-100n-4 moved main()'s inline steps into build_main_helpers, taking the
#   calls to write_build_manifest, check_halt_guard, write_lock_file,
#   _resolve_package_sha, scan_for_placeholders and check_referential_integrity
#   with them; those names are no longer bound in build.py's globals, so
#   patch.object(_build, ...) raised AttributeError (8 CI failures across this
#   file and test_build_package_version.py).
#   Rejected the cheaper fix — re-adding `from build_helpers import
#   write_build_manifest` to build.py so the attribute exists again. It clears
#   the AttributeError WITHOUT fixing anything: build_main_helpers resolves the
#   name through its OWN globals, so the patch rebinds a name nobody reads and
#   the real manifest step runs unasserted. Measured, not assumed: running
#   main() with a MagicMock installed on build_main_helpers gives call_count=1;
#   the same spy installed on build (create=True) gives call_count=0.
#   Rejected passing the six in as parameters from main() (the pattern used for
#   build.py's own locals) — that adds real branching to main() purely to
#   preserve a patch target, fighting the complexity paydown this ticket exists
#   for. These names were never build.py's contract; they were imports that
#   happened to sit in the module main()'s body lived in. The contract is
#   main()'s behaviour, and that is unchanged.
# - 2026-05-27 12:30 [test-writer/TICKET-20260527-WireVersionIntoBuild]: (#TICKETLESS reason=standalone-ticket-closeout)
#   Created module. Four tests cover the four acceptance criteria: version
#   printed, VERSION file written, dry-run skips write, validate-only skips
#   computation. Tests import build.py directly (monkeypatching expensive
#   phases) to avoid subprocess overhead and WSL filesystem slowness.
# ====================================================================
