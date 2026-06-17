"""
MODULE: test_build_guard_real_package
GOAL: Regression guard tests that exercise _check_script_reference_guard() and
    _get_source_deployable_scripts() against the REAL package source — not a
    synthetic manifest — so that any future manifest-drift is caught by CI before
    a release.
BUSINESS CONTEXT: The original defect (EPIC-BuildGuardFalsePositive) shipped
    because all existing tests used synthetic manifests. This file adds a
    positive-control test (guard exits 0 on the clean package), a negative-control
    test (guard exits 1 when a broken reference is injected), and two manifest-
    derivation tests confirming _get_source_deployable_scripts() returns a superset
    of the scripts deployed by build_commit_guardian and build_feedback.
    AC BP-900-Fix-4, AC-2, AC-3, AC-4.
ARCHITECTURE: Tests import build.py directly via sys.path setup. The negative-
    control test creates a temporary templates/agents/ directory containing a
    synthetic .md file with a nonexistent script reference, then passes that
    synthetic package_root to _check_script_reference_guard(). Stderr is captured
    during the negative-control run to assert the JSONL output names the expected
    missing script path.
"""
# @ac-tag: BP-900-Fix-4
# @ac-tag: BP-900-Fix-4-AC-2
# @ac-tag: BP-900-Fix-4-AC-3
# @ac-tag: BP-900-Fix-4-AC-4

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Path setup — make scripts/ importable regardless of working directory.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import build as _build  # noqa: E402 — after sys.path setup

# The real package_root used throughout these tests.
_REAL_PACKAGE_ROOT = _REPO_ROOT


# ---------------------------------------------------------------------------
# AC BP-900-Fix-4 (positive-control): guard exits 0 on the clean package
# ---------------------------------------------------------------------------


def test_guard_exits_0_on_clean_package() -> None:
    """_check_script_reference_guard() must return 0 on the clean, unmodified package.

    This test exercises the REAL guard against the REAL package source —
    including the REAL _get_source_deployable_scripts() derivation — so that
    any future manifest-drift causes CI to fail rather than shipping silently.

    AC BP-900-Fix-4: the test MUST NOT be marked xfail or skipped; the positive-
    control assertion depends on tickets 02 and 03 being applied first (which they
    are — this ticket is declared to depend_on both).
    """
    result = _build._check_script_reference_guard(_REAL_PACKAGE_ROOT)
    assert result == 0, (
        f"_check_script_reference_guard() returned {result!r} on the clean package. "
        "Expected 0 (no broken references). "
        "This means a template references a script that _get_source_deployable_scripts() "
        "does not include. Check that all scripts referenced in templates/agents/ and "
        "templates/skills/ are deployed by a build phase or listed in EXTERNAL_DEPENDENCY_ALLOWLIST."
    )


# ---------------------------------------------------------------------------
# AC-2 (negative-control): guard exits 1 on a broken reference
# ---------------------------------------------------------------------------


def test_guard_exits_1_on_broken_ref(tmp_path: Path) -> None:
    """_check_script_reference_guard() must return 1 when a template references
    a nonexistent script, and the JSONL output must name that script path.

    This test injects a synthetic templates/agents/ directory containing a single
    .md file that references scripts/does_not_exist.py.  It then calls the guard
    with the synthetic package_root and asserts:
    - return value is 1
    - the JSONL line written to stderr names scripts/does_not_exist.py as
      missing_path
    """
    # Build a minimal synthetic package root with:
    #   templates/agents/synthetic_broken.md  — references scripts/does_not_exist.py
    # No scripts/commit_guardian/, scripts/feedback/, etc. are needed because the
    # guard only checks whether referenced paths are DEPLOYABLE (derived from source)
    # not whether they are actually installed.
    synthetic_root = tmp_path / "synthetic_pkg"
    agents_dir = synthetic_root / "templates" / "agents"
    agents_dir.mkdir(parents=True)

    # Write a template that invokes the nonexistent script via python3 — this
    # matches the _PYTHON_INVOKE_RE pattern in build_referential_integrity.
    broken_template = agents_dir / "synthetic_broken.md"
    broken_template.write_text(
        "python3 scripts/does_not_exist.py --flag value\n",
        encoding="utf-8",
    )

    # Capture stderr so we can inspect the JSONL output.
    captured_stderr = io.StringIO()
    with patch("sys.stderr", captured_stderr):
        result = _build._check_script_reference_guard(synthetic_root)

    assert result == 1, (
        f"_check_script_reference_guard() returned {result!r} on a package that "
        "references scripts/does_not_exist.py. Expected 1 (broken reference detected). "
        "The guard failed to flag a script reference that has no corresponding deployable script."
    )

    stderr_output = captured_stderr.getvalue()
    assert stderr_output.strip(), (
        "Guard returned 1 but wrote nothing to stderr. "
        "The guard must emit JSONL to stderr naming the broken reference (AC BP-900c-2)."
    )

    # Parse the JSONL and assert that scripts/does_not_exist.py is named.
    missing_paths: list[str] = []
    for line in stderr_output.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        missing_path = obj.get("missing_path", "")
        if missing_path:
            missing_paths.append(missing_path)

    assert "scripts/does_not_exist.py" in missing_paths, (
        f"JSONL output from the guard does not name scripts/does_not_exist.py. "
        f"Found missing_path values: {missing_paths!r}. "
        "The guard must emit missing_path = 'scripts/does_not_exist.py' in the "
        "JSONL report (AC-2, AC BP-900c-2)."
    )


# ---------------------------------------------------------------------------
# AC-3 / AC-4: manifest-derivation tests confirm drift-proof derivation
# ---------------------------------------------------------------------------


def test_manifest_covers_commit_guardian_scripts() -> None:
    """_get_source_deployable_scripts() must include all scripts/commit_guardian/*.py
    files present in the real package source.

    This test calls the REAL _get_source_deployable_scripts() with the REAL
    package_root — it does NOT construct the deployable set manually — and then
    asserts that every .py file under templates/scripts/commit_guardian/ (or the
    legacy templates/commit-guardian/ directory) appears in the returned set.

    If a new .py file is added to scripts/commit_guardian/ in a future change
    without updating the manifest derivation, this test fails and names the
    missing script path.
    """
    deployable = _build._get_source_deployable_scripts(_REAL_PACKAGE_ROOT)

    # Discover the expected set by scanning the same source directories that
    # _manifest_commit_guardian_scripts() scans.
    expected: set[str] = set()
    for src in (
        _REAL_PACKAGE_ROOT / "templates" / "scripts" / "commit_guardian",
        _REAL_PACKAGE_ROOT / "templates" / "commit-guardian",
    ):
        if src.is_dir():
            for f in src.rglob("*"):
                if f.is_file() and f.suffix == ".py":
                    expected.add(f"scripts/commit_guardian/{f.relative_to(src).as_posix()}")

    missing = expected - deployable
    assert not missing, (
        f"_get_source_deployable_scripts() is missing {len(missing)} "
        f"scripts/commit_guardian/ script(s): {sorted(missing)}. "
        "Add a deploy phase or extend _manifest_commit_guardian_scripts() to "
        "cover these scripts, or this test will continue to fail as a drift sentinel."
    )


def test_manifest_covers_full_feedback_set() -> None:
    """_get_source_deployable_scripts() must include aggregate.py and resolve_feedback.py.

    These two scripts were the Class A false-positives from the original defect:
    the hardcoded manifest did not include them, causing the guard to flag
    legitimate references as broken. After the fix (ticket 02), the manifest
    is derived dynamically from scripts/feedback/ and both scripts are present.

    This test uses the REAL _get_source_deployable_scripts() against the REAL
    package_root — it does NOT construct the deployable set manually (AC-4).
    """
    deployable = _build._get_source_deployable_scripts(_REAL_PACKAGE_ROOT)

    for script_name in ("aggregate.py", "resolve_feedback.py"):
        expected_key = f"scripts/feedback/{script_name}"
        assert expected_key in deployable, (
            f"_get_source_deployable_scripts() does not include {expected_key!r}. "
            f"This was one of the Class A false-positives from the original defect. "
            f"Verify that scripts/feedback/{script_name} exists in the source package "
            f"and that _manifest_feedback_scripts() scans scripts/feedback/ dynamically."
        )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-06-17 [python-coder/EPIC-BuildGuardFalsePositive/04]: Initial implementation.
#   Added four regression-guard tests targeting AC BP-900-Fix-4, AC-2, AC-3, AC-4.
#   Positive-control test uses the REAL package_root (not a synthetic manifest) so
#   any future manifest-drift causes CI to fail. Negative-control injects a synthetic
#   template with a nonexistent script ref and captures stderr to assert JSONL output.
#   Manifest-derivation tests call _get_source_deployable_scripts() directly against
#   the real package and assert all commit_guardian .py files + aggregate.py +
#   resolve_feedback.py are present.
#   Design choice: synthetic package_root (tmp_path) for AC-2 to avoid polluting the
#   real templates dir; real package_root (_REPO_ROOT) for all positive-control tests.
#   (#EPIC-BuildGuardFalsePositive/04)
# ====================================================================
