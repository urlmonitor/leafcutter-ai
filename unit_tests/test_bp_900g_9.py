"""
MODULE: test_bp_900g_9
GOAL: Behavioural tests for BP-900g-9 — a declared deploy entry whose source is
    missing must FAIL the build, not warn and continue.

BUSINESS CONTEXT: The branch this AC replaces already does almost everything
    right. It finds the missing source, identifies it correctly, and logs it
    accurately. The only thing it gets wrong is the exit code. That makes it the
    purest grep-shaped false-green trap in this subtree: a test asserting the
    failure text appears is green against BOTH the broken and the fixed
    implementation, because the broken one emits exactly the same text.

    Reproduced before writing these tests, on the unfixed tree: deleting
    scripts/ac_store/_component_migration_map.py — a file the deploy map
    declares — produced `build_ac_store: source script not found, skipping`
    AND exit code 0. A consumer install missing a declared file, reported as a
    successful build.

ARCHITECTURE: Every assertion here is on the exit code, the accumulated
    records, or the SET of names in a single failure. None is on log output.

    Choice of fixture, and why it is not the obvious one. The AC's test_spec
    says to delete the source behind a declared entry. Doing that with the
    first file to hand is a vacuous must_block: deleting
    scripts/knowledge/harvest_learnings.py makes the SCRIPT-REFERENCE guard
    exit 1 before any phase runs (it is named by agents/knowledge-harvester.md),
    so the test would pass without the deploy loop ever executing. Verified by
    running it. `_component_migration_map.py` is referenced by no template and,
    once deleted, drops out of every closure so the closure guard stays silent
    too — it is the one deletion that actually reaches the loop under test.

    The many-findings case appends synthetic absent entries to the declaration
    rather than deleting three more real files, for the same reason: three real
    deletions that each avoid every earlier guard do not exist, and a synthetic
    entry is what "the declaration names a path with no source" means anyway.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import build_phases as _bp  # noqa: E402 -- after sys.path setup

_BUILD_PY = _SCRIPTS_DIR / "build.py"
_DECLARED_SOURCE = _SCRIPTS_DIR / "ac_store" / "_component_migration_map.py"
_BUILD_PHASES_PY = _SCRIPTS_DIR / "build_phases.py"


def _run_build(target: Path) -> subprocess.CompletedProcess[str]:
    """Run the REAL build entry point as a subprocess against *target*.

    The fail-open branch is reached through the build's own iteration, so the
    criterion is only satisfied by going through this process — a test calling
    the phase helper directly is green while the loop still swallows the result.
    """
    return subprocess.run(
        [sys.executable, str(_BUILD_PY), "--target-dir", str(target)],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=str(_REPO_ROOT),
    )


# ---------------------------------------------------------------------------
# Test 1 — angle: criterion. The record, and the verdict. Never the log.
# ---------------------------------------------------------------------------


def test_bp_900g_9_missing_declared_source_produces_a_failure_record_not_a_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # covers: BP-900g-9
    """A declared entry with no source accumulates a record and makes the run fail.

    Drives the real deploy iteration with PACKAGE_ROOT pointed at an empty tree,
    so every declared entry is unresolvable. Asserts the record carries phase,
    entry and source_path — the three fields the author needs to locate and fix
    the declaration — and that the run's verdict is failure.

    Deliberately does NOT assert that a warning was logged. The unfixed code
    logs the same thing.
    """
    empty_pkg = tmp_path / "empty_pkg"
    empty_pkg.mkdir()
    monkeypatch.setattr(_bp, "PACKAGE_ROOT", empty_pkg)

    _bp.reset_deploy_failures()
    _bp.build_ac_store(tmp_path / "target", {}, dry_run=True, force=False)

    failures = _bp.get_deploy_failures()
    assert failures, (
        "The deploy iteration met declared entries whose sources do not exist "
        "and accumulated no failure records — it warned and continued, which is "
        "the defect."
    )

    record = failures[0]
    assert record.phase == "build_ac_store", (
        f"The record must name the phase that declared the entry so the author "
        f"knows which declaration to edit. Got: {record.phase!r}"
    )
    assert record.entry, "The record must name the declaration entry as written."
    assert record.source_path, (
        "The record must carry the source path that was not found — the one fact "
        "the current warning already emits correctly and the build then discards."
    )

    with pytest.raises(_bp.DeployDeclarationError):
        _bp.raise_if_deploy_failures()


# ---------------------------------------------------------------------------
# Test 2 — angle: reachability (must_block). The production entry point.
# ---------------------------------------------------------------------------


def test_bp_900g_9_build_subprocess_exits_non_zero_on_a_declared_but_absent_source(
    tmp_path: Path,
) -> None:
    # covers: BP-900g-9
    """Deleting a declared source must make `build.py` exit non-zero and say why.

    On the unfixed tree this exits 0 while logging the miss — verified before
    this test was written. The exit code is the whole assertion; the naming
    assertions below are the criterion's "names the phase, the entry, and the
    source path", not a substitute for it.
    """
    original = _DECLARED_SOURCE.read_bytes()
    try:
        _DECLARED_SOURCE.unlink()

        result = _run_build(tmp_path / "withheld_target")
        combined = result.stdout + result.stderr

        assert result.returncode != 0, (
            "build.py exited 0 while the deploy declaration named "
            "'scripts/ac_store/_component_migration_map.py', whose source was "
            "deleted. The build reported a consumer install it did not produce. "
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        assert "build_ac_store" in combined, (
            f"The failure must name the declaring phase. Output:\n{combined}"
        )
        assert "_component_migration_map.py" in combined, (
            f"The failure must name the entry and its source path. "
            f"Output:\n{combined}"
        )
    finally:
        _DECLARED_SOURCE.write_bytes(original)


# ---------------------------------------------------------------------------
# Test 3 — angle: boundary. Zero entries and all-resolving are both success.
# ---------------------------------------------------------------------------


def test_bp_900g_9_empty_and_fully_resolving_declarations_both_build_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # covers: BP-900g-9
    """"Nothing to ship" and "everything shipped" are both success.

    The false-positive control for the fail-closed flip. Without it, making the
    loop fail-closed can turn an empty declaration into a build failure and
    nobody finds out until an unrelated phase legitimately ships nothing — the
    EPIC-BOPhantomDoneRemediation T03 shape, where an empty-list guard was
    present in one check and absent from its structurally identical twin while
    all 22 tests passed.

    The empty case runs at the loop level rather than through a subprocess: the
    only way to give the real build a zero-entry declaration is to empty
    AC_STORE_DEPLOY_MAP on disk, which also empties Set B and trips the closure
    and tracked-source guards, so the subprocess would exit non-zero for
    reasons that have nothing to do with this AC. The all-resolving half runs
    through the real subprocess, where it is meaningful.
    """
    monkeypatch.setattr(_bp, "AC_STORE_DEPLOY_MAP", ())
    _bp.reset_deploy_failures()
    _bp.build_ac_store(tmp_path / "empty_decl_target", {}, dry_run=True, force=False)

    assert _bp.get_deploy_failures() == [], (
        "A declaration with zero entries produced failure records. Nothing was "
        "promised, so nothing can have been dropped."
    )
    _bp.raise_if_deploy_failures()  # must not raise

    result = _run_build(tmp_path / "clean_target")
    assert result.returncode == 0, (
        "build.py exited non-zero against the UNMODIFIED tree, where every "
        "declared entry resolves. A guard that always fails proves nothing.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# Test 4 — angle: boundary. Every finding in one run, not one per run.
# ---------------------------------------------------------------------------


def test_bp_900g_9_three_unresolvable_entries_are_all_named_in_one_run(
    tmp_path: Path,
) -> None:
    # covers: BP-900g-9
    """Three unresolvable entries must all be named by a single build.

    This is the only test that distinguishes a guard which halts at the first
    finding from one that reports the set, and the difference is worth a test:
    halting turns N stale entries into N build-fix-build cycles with a GREEN
    build between each one, so an author who stops at the first green ships the
    remaining N-1.

    Appends three synthetic absent entries to the declaration rather than
    deleting three more real files — three real deletions that each dodge every
    earlier guard do not exist, and "the declaration names a path with no
    source" is exactly what a synthetic entry is.
    """
    probe_names = (
        "__bp900g9_absent_one.py",
        "__bp900g9_absent_two.py",
        "__bp900g9_absent_three.py",
    )
    injected = "".join(
        f'    ("scripts/ac_store/{name}", "{name}"),\n' for name in probe_names
    )
    original_text = _BUILD_PHASES_PY.read_text(encoding="utf-8")
    anchor = "AC_STORE_DEPLOY_MAP: tuple[tuple[str, str], ...] = (\n"
    assert anchor in original_text, (
        "Fixture anchor not found — the declaration's literal form changed and "
        "this test can no longer inject entries into it."
    )

    try:
        _BUILD_PHASES_PY.write_text(
            original_text.replace(anchor, anchor + injected, 1), encoding="utf-8"
        )

        result = _run_build(tmp_path / "three_target")
        combined = result.stdout + result.stderr

        assert result.returncode != 0, (
            "build.py exited 0 with three declared entries whose sources do not "
            f"exist.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        missing_from_report = [n for n in probe_names if n not in combined]
        assert not missing_from_report, (
            "A single build run must name EVERY unresolvable entry, so one build "
            "tells the author the whole remediation set. These were not named: "
            f"{missing_from_report}.\nOutput:\n{combined}"
        )
    finally:
        _BUILD_PHASES_PY.write_text(original_text, encoding="utf-8")
