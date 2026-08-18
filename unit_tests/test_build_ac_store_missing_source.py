"""
MODULE: unit_tests/test_build_ac_store_missing_source.py
GOAL: Red-baseline behavioral tests for BP-900a-1-1 -- build.py must fail loudly
    (non-zero exit, before writing any partial ac_store output) when one of the
    13 expected scripts/ac_store/ source scripts is missing, instead of the
    current "warn and skip" behaviour in build_ac_store() (build_phases.py).
BUSINESS CONTEXT: build_ac_store() currently logs a WARNING and silently skips
    a missing source file (build_phases.py, "source script not found,
    skipping"), then returns a written-count as if nothing were wrong.
    build.py's top-level exit code is otherwise derived only from explicit
    guard failures (see _check_script_reference_guard / _check_tracked_source_guard
    in scripts/build.py). Those guards only catch a missing source when some
    template *invokes* it via a `python3 scripts/...` pattern. A deploy_map
    entry that is not referenced that way (e.g. scripts/ac_store/__init__.py)
    slips through both existing guards AND the ac_store phase itself, producing
    a SILENT partial deployment with exit code 0. AC BP-900a-1-1 requires
    build.py to detect this class of gap and hard-fail before writing any
    ac_store output, naming the missing file.

    These tests use scripts/ac_store/__init__.py as the missing file because it
    is a real deploy_map entry (build_phases.build_ac_store) that NO template
    references via a `python3 scripts/...` invocation pattern -- confirmed by
    `grep -rn "ac_store/__init__" templates/` returning nothing, and by manual
    reproduction against the current (pre-fix) build_phases.py: removing
    __init__.py from a synthetic copy of the package and running
    `python build.py --target-dir <dir>` against it exits 0 and deploys a
    PARTIAL scripts/ac_store/ directory (e.g. scan_ac_store.py lands,
    __init__.py does not). This is the exact bug this AC closes.

ARCHITECTURE: These are real-artifact, real-subprocess behavioral tests
    (BP-1100f-2 real-effect round trip). They invoke the ACTUAL
    `python <synthetic_pkg>/scripts/build.py --target-dir <target>` entry
    point as a subprocess against a REAL on-disk synthetic package copy (built
    from the real templates/scripts/config/changelogs/docs-product-truth
    trees, minus one file), then read back the REAL target directory's
    deployed scripts/ac_store/ contents. No internal function is mocked; no
    dispatch-only / call_args assertion is made -- the test round-trips a real
    file on a real filesystem.

These tests are INTENTIONALLY RED before python-coder's fix: today
build_ac_store() warns and skips, build.py exits 0, and a partial
scripts/ac_store/ directory is written to the target.

AC mapping:
  BP-900a-1-1 (test_spec):
    test_build_exits_nonzero_when_an_ac_store_source_is_missing
    test_missing_source_error_names_the_missing_file
    test_no_partial_output_written_when_a_source_is_missing
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent

# The deploy_map entry we remove to simulate "one of the 13 expected files is
# missing". __init__.py is a real scripts/ac_store/ deploy_map source
# (build_phases.build_ac_store) that no template references via a
# `python3 scripts/...` invocation pattern, so it is NOT caught by the
# pre-existing _check_script_reference_guard() in scripts/build.py -- this
# isolates the exact gap BP-900a-1-1 closes: build_ac_store()'s OWN pre-write
# source-existence check, independent of the template-reference guard.
_MISSING_RELPATH = "scripts/ac_store/__init__.py"

# Top-level package directories build.py / build_phases.py read via
# PACKAGE_ROOT at runtime. docs/ is intentionally narrowed to product-truth/
# only (the one subtree build_phases.py reads unconditionally) to keep the
# synthetic package copy fast -- the full docs/ tree is ~20MB and irrelevant
# to this scenario.
_DIRS_TO_COPY = ("templates", "scripts", "config", "changelogs")


def _build_synthetic_package(dest_root: Path, *, omit_relpath: str) -> Path:
    """Copy the real package's build-relevant trees into dest_root, omitting one file.

    Copies templates/, scripts/, config/, changelogs/, and docs/product-truth/
    -- the subset of top-level directories build.py and build_phases.py read
    via PACKAGE_ROOT -- then deletes ``omit_relpath`` (relative to dest_root)
    to simulate a missing source script.
    """
    for name in _DIRS_TO_COPY:
        src = _REPO_ROOT / name
        if src.is_dir():
            shutil.copytree(src, dest_root / name)

    product_truth_src = _REPO_ROOT / "docs" / "product-truth"
    if product_truth_src.is_dir():
        shutil.copytree(product_truth_src, dest_root / "docs" / "product-truth")

    missing_path = dest_root / omit_relpath
    assert missing_path.is_file(), (
        f"Fixture setup error: {omit_relpath} was not found in the copied "
        f"synthetic package at {missing_path}. Cannot simulate its absence."
    )
    missing_path.unlink()
    return dest_root


def _run_build(synthetic_pkg: Path, target_dir: Path) -> subprocess.CompletedProcess:
    """Invoke the REAL build.py entry point as a subprocess against target_dir."""
    build_script = synthetic_pkg / "scripts" / "build.py"
    return subprocess.run(
        [sys.executable, str(build_script), "--target-dir", str(target_dir)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


@pytest.fixture
def synthetic_pkg_missing_source(tmp_path: Path) -> Path:
    """A real on-disk copy of the package with scripts/ac_store/__init__.py removed."""
    pkg_dir = tmp_path / "synthetic_pkg"
    pkg_dir.mkdir()
    return _build_synthetic_package(pkg_dir, omit_relpath=_MISSING_RELPATH)


class TestBuildAcStoreMissingSource:
    """BP-900a-1-1: build.py must hard-fail when a scripts/ac_store/ deploy
    source is missing, instead of build_ac_store()'s current warn-and-skip."""

    def test_build_exits_nonzero_when_an_ac_store_source_is_missing_MANUAL(
        self, synthetic_pkg_missing_source: Path, tmp_path: Path
    ) -> None:
        # covers: BP-900a-1-1
        """Given scripts/ac_store/__init__.py is missing from the source package,
        when build.py is invoked with --target-dir, the process must exit non-zero.

        Currently (pre-fix) build_ac_store() logs a warning and continues, so
        build.py exits 0 -- this test is RED until python-coder adds the
        pre-write source-existence check inside build_ac_store().

        _MANUAL: this is a real-subprocess, real-artifact behavioral test that
        copies templates/scripts/config/changelogs/docs-product-truth into a
        synthetic package and runs the actual build.py entry point end to end
        (self-description validation, doc scanning, hook wiring checks, etc.
        all execute for real). Measured ~20-25s per invocation on this
        machine -- well over testing_context.max_test_duration_seconds (5s) --
        so it is excluded from the fast default suite by naming convention.
        Verified red via direct invocation with AC_ENFORCE_STRICT=1 during
        test-writer authoring (see ticket Comments red_baseline).
        """
        target_dir = tmp_path / "consumer_target"
        target_dir.mkdir()

        result = _run_build(synthetic_pkg_missing_source, target_dir)

        assert result.returncode != 0, (
            "build.py exited 0 despite scripts/ac_store/__init__.py being "
            "absent from the source package. Expected non-zero exit "
            f"(AC BP-900a-1-1).\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_missing_source_error_names_the_missing_file_MANUAL(
        self, synthetic_pkg_missing_source: Path, tmp_path: Path
    ) -> None:
        # covers: BP-900a-1-1
        """The failure output (stdout or stderr) must name the specific missing
        source file (__init__.py / scripts/ac_store/__init__.py), not just a
        generic 'build failed' message.

        _MANUAL: same real-subprocess build.py invocation as the sibling test
        in this file (~20-25s); see that docstring for the full rationale.
        """
        target_dir = tmp_path / "consumer_target"
        target_dir.mkdir()

        result = _run_build(synthetic_pkg_missing_source, target_dir)

        # This assertion is intentionally paired with the non-zero exit check:
        # the current (pre-fix) code already prints "source script not found,
        # skipping: .../__init__.py" as a WARNING while still exiting 0, so a
        # naming-only assertion would pass today without any fix landing. The
        # AC requires the file to be named AS PART OF a hard failure, not as a
        # soft warning on an otherwise-successful (exit 0) run.
        assert result.returncode != 0, (
            "build.py exited 0 while reporting the missing source only as a "
            "WARNING. Expected the missing-source report to be part of a hard, "
            f"non-zero-exit failure (AC BP-900a-1-1).\nstdout:\n{result.stdout}"
            f"\nstderr:\n{result.stderr}"
        )

        combined_output = result.stdout + result.stderr
        assert "__init__.py" in combined_output, (
            "build.py's failure output does not name the missing source file "
            "'__init__.py' (or its scripts/ac_store/ path). Expected the error "
            "message to identify the specific missing file to aid debugging "
            f"(AC BP-900a-1-1).\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_no_partial_output_written_when_a_source_is_missing_MANUAL(
        self, synthetic_pkg_missing_source: Path, tmp_path: Path
    ) -> None:
        # covers: BP-900a-1-1
        """No scripts/ac_store/ files must be deployed to the target when the
        build aborts on a missing source -- no partial deployment.

        Currently (pre-fix) build_ac_store() writes every OTHER deploy_map
        entry before returning, so e.g. scan_ac_store.py lands in
        <target>/.leafcutter/scripts/ac_store/ even though __init__.py is
        missing. This is the exact "ships half-deployed" failure mode the AC
        closes (see AC notes: "that skip is exactly how a capability ships
        half-deployed").

        _MANUAL: same real-subprocess build.py invocation as the sibling tests
        in this file (~20-25s); see the first test's docstring for the full
        rationale.
        """
        target_dir = tmp_path / "consumer_target"
        target_dir.mkdir()

        _run_build(synthetic_pkg_missing_source, target_dir)

        # Search both the legacy scripts/ac_store/ location and the default
        # .leafcutter/scripts/ac_store/ consolidated output location, since the
        # output_root name is a config value (defaults to ".leafcutter").
        deployed_ac_store_files: list[Path] = []
        for candidate_dir in (
            target_dir / "scripts" / "ac_store",
            target_dir / ".leafcutter" / "scripts" / "ac_store",
        ):
            if candidate_dir.is_dir():
                deployed_ac_store_files.extend(
                    p for p in candidate_dir.rglob("*") if p.is_file()
                )

        assert not deployed_ac_store_files, (
            f"build.py wrote {len(deployed_ac_store_files)} scripts/ac_store/ "
            "file(s) to the target despite scripts/ac_store/__init__.py being "
            f"missing from the source: "
            f"{[str(p) for p in deployed_ac_store_files[:10]]}. "
            "Expected zero ac_store files written -- the build must validate "
            "all sources exist BEFORE writing any of them (AC BP-900a-1-1)."
        )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-18 [test-writer/TICKET-20260611-BP-900a-1-1]: Initial red-baseline
#   tests. Uses a real subprocess invocation of the actual build.py entry
#   point against a real on-disk synthetic package copy (real-artifact
#   behavioral test per BP-1100f-2) rather than mocking build_ac_store() or
#   asserting on call_args -- no internal function name is assumed, so these
#   tests constrain the OBSERVABLE contract (exit code, error message, target
#   filesystem state) regardless of which internal mechanism python-coder
#   picks (raise vs. sys.exit vs. a new pre-flight guard function) to satisfy
#   the AC's it_requirements n_location_rule ("1 -- the pre-write
#   source-existence check in build_ac_store()").
# ====================================================================
