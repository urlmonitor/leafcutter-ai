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
    asserts that every .py file under templates/scripts/commit_guardian/ (canonical)
    appears in the returned set.

    If a new .py file is added to scripts/commit_guardian/ in a future change
    without updating the manifest derivation, this test fails and names the
    missing script path.
    """
    deployable = _build._get_source_deployable_scripts(_REAL_PACKAGE_ROOT)

    # Discover the expected set by scanning the canonical source directory that
    # _manifest_commit_guardian_scripts() scans.
    expected: set[str] = set()
    src = _REAL_PACKAGE_ROOT / "templates" / "scripts" / "commit_guardian"
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


# ---------------------------------------------------------------------------
# BP-900d: onboard_hook_opt_in.py must be deployable so the preflight does not
# abort. Regression for the /debug-diagnosed defect where the script lived only
# in scripts/ (package-dev tree) and was never promoted into templates/scripts/,
# causing `python scripts/build.py --target-dir <dir>` to exit 1 on the
# reference in templates/agents/onboard.md.
# ---------------------------------------------------------------------------


def test_onboard_hook_opt_in_is_deployable() -> None:
    """_get_source_deployable_scripts() must include scripts/onboard_hook_opt_in.py.

    onboard.md instructs end users to run `python scripts/onboard_hook_opt_in.py`,
    so the script is consumer-facing and must ship via templates/scripts/. Before
    the fix the script existed only under scripts/ (package-dev tree) and was not
    listed as deployable, so the preflight guard flagged the onboard.md reference
    as broken and build.py aborted with exit 1.

    AC BP-900d.
    """
    # covers: BP-900d
    deployable = _build._get_source_deployable_scripts(_REAL_PACKAGE_ROOT)

    assert "scripts/onboard_hook_opt_in.py" in deployable, (
        "_get_source_deployable_scripts() does not include "
        "'scripts/onboard_hook_opt_in.py'. onboard.md (a consumer-facing template) "
        "references it, so it must be promoted into templates/scripts/ to be "
        "deployable. Without it, _check_script_reference_guard() exits 1 and "
        "build.py aborts before writing any output (AC BP-900d)."
    )


# ---------------------------------------------------------------------------
# BP-1200a-1-ii: fresh-clone collection sentinel
# ---------------------------------------------------------------------------


def test_feedback_scripts_tracked_in_templates() -> None:
    """templates/scripts/feedback/ must contain the canonical feedback scripts.

    On a fresh clone the gitignored ``scripts/feedback/`` build-output directory
    is absent.  Per ADR-016 the tracked source lives under
    ``templates/scripts/feedback/`` so that ``build_feedback()`` can deploy it
    and ``_manifest_feedback_scripts()`` reports it as deployable — preventing
    the ``_check_script_reference_guard`` from aborting build.py with exit 1.

    This test asserts that the canonical set of feedback scripts required by
    agent/skill templates are present in the tracked template source.  If any
    script is missing the guard will abort the build on every fresh clone.

    AC BP-1200a-1-ii.
    """
    # covers: BP-1200a-1-ii
    templates_feedback = _REAL_PACKAGE_ROOT / "templates" / "scripts" / "feedback"

    assert templates_feedback.is_dir(), (
        f"templates/scripts/feedback/ does not exist at {templates_feedback}. "
        "The canonical tracked source for feedback scripts is missing. "
        "On a fresh clone this causes build.py to exit 1 (broken script references). "
        "See ADR-016 for the source-of-truth policy."
    )

    required_scripts = [
        "submit_feedback.py",
        "aggregate.py",
        "resolve_feedback.py",
        "emit_hook_finding.py",
        "list_tags.py",
    ]
    for script_name in required_scripts:
        script_path = templates_feedback / script_name
        assert script_path.is_file(), (
            f"templates/scripts/feedback/{script_name} is missing. "
            f"This script is referenced by agent/skill templates and must be "
            f"present in the tracked source so build.py deploys it on a fresh "
            f"clone. Without it _check_script_reference_guard() exits 1. "
            f"(AC BP-1200a-1-ii)"
        )


def test_fresh_clone_build_guard_exits_0() -> None:
    """_check_script_reference_guard() must return 0 simulating a fresh-clone state.

    On a fresh clone ``scripts/feedback/`` is absent (gitignored build output).
    After PR #164 removed the tracked source, the guard found no deployable
    feedback scripts and aborted with exit 1 — breaking all CI test collection.

    This test verifies that with ``templates/scripts/feedback/`` present as the
    tracked canonical source (ADR-016), the guard returns 0 even when
    ``scripts/feedback/`` is absent.  It calls the REAL guard against the REAL
    package root — same as ``test_guard_exits_0_on_clean_package`` but named
    explicitly to document the fresh-clone regression scenario.

    AC BP-1200a-1-ii: zero collection errors on a fresh clone.
    """
    # covers: BP-1200a-1-ii
    result = _build._check_script_reference_guard(_REAL_PACKAGE_ROOT)
    assert result == 0, (
        f"_check_script_reference_guard() returned {result!r}. "
        "Expected 0 — no broken script references — so build.py does not exit 1 "
        "on a fresh clone. "
        "Check that templates/scripts/feedback/ contains all scripts referenced in "
        "agent/skill templates and that _manifest_feedback_scripts() scans "
        "templates/scripts/feedback/ (not the gitignored scripts/feedback/). "
        "(AC BP-1200a-1-ii)"
    )


# ---------------------------------------------------------------------------
# BP-1200a-1-ii follow-up: commit_guardian scripts must be in templates/
# ---------------------------------------------------------------------------


def test_commit_guardian_missing_scripts_in_templates() -> None:
    """templates/scripts/commit_guardian/ must contain the 3 previously-missing scripts.

    After PR #180 restored templates/scripts/feedback/, three scripts were still
    missing from templates/scripts/commit_guardian/:
    - known_failing_tests.py
    - transform_decision_history.py
    - check_test_fixture_bloat.py

    Their absence caused ModuleNotFoundError at pytest collection time for:
    - tests/test_known_failing_tests.py
    - tests/test_transform_decision_history.py
    - unit_tests/commit_guardian/test_check_test_fixture_bloat.py

    This test asserts that all 3 files are present in the tracked template source
    so that build.py deploys them and they remain importable after a fresh clone.

    AC BP-1200a-1-ii (follow-up: zero collection errors).
    """
    # covers: BP-1200a-1-ii
    templates_commit_guardian = _REAL_PACKAGE_ROOT / "templates" / "scripts" / "commit_guardian"

    assert templates_commit_guardian.is_dir(), (
        f"templates/scripts/commit_guardian/ does not exist at {templates_commit_guardian}. "
        "The canonical tracked source for commit_guardian scripts is missing."
    )

    required_scripts = [
        "known_failing_tests.py",
        "transform_decision_history.py",
        "check_test_fixture_bloat.py",
    ]
    for script_name in required_scripts:
        script_path = templates_commit_guardian / script_name
        assert script_path.is_file(), (
            f"templates/scripts/commit_guardian/{script_name} is missing. "
            f"This script is imported by tests and must be present in the tracked "
            f"template source so build.py deploys it on a fresh clone. "
            f"Without it, pytest --collect-only fails with ModuleNotFoundError. "
            f"(AC BP-1200a-1-ii follow-up)"
        )

# ---------------------------------------------------------------------------
# BP-900f wire-up integration: main() must call _check_tracked_source_guard
# (pr-reviewer H-1 repair — 2026-06-24)
# ---------------------------------------------------------------------------


def test_main_calls_tracked_source_guard_when_sources_untracked(
    tmp_path: Path,
) -> None:
    """main() must exit 1 when _check_tracked_source_guard() returns 1.

    This test exercises the build entry point (main()) — not the guard function
    directly — to confirm the wiring added in the pr-reviewer H-1 repair.  It
    mocks _check_tracked_source_guard to return 1 (simulating untracked sources)
    and asserts that main() propagates the non-zero exit without writing any
    output files.

    AC BP-900f-2: build exits non-zero and writes no partial deployment.
    AC BP-900f-3: the guard runs before any deployment output is written.
    """
    # Point --target-dir at a fresh temp directory so no real output is
    # written even if the mock somehow does not fire.
    target_dir = tmp_path / "deploy_target"
    target_dir.mkdir()

    # Patch _check_tracked_source_guard inside the build module so that the
    # integration test does not require untracked files in the real working
    # tree (which would vary by developer environment and CI state).
    with patch.object(_build, "_check_tracked_source_guard", return_value=1):
        result = _build.main(["--target-dir", str(target_dir)])

    assert result != 0, (
        "main() returned 0 (success) even though _check_tracked_source_guard() "
        "returned 1 (untracked sources detected). "
        "The tracked-source guard must be wired into main() so that a non-zero "
        "guard return causes main() to propagate the exit code (AC BP-900f-2). "
        "This test exercises main() — not _check_tracked_source_guard() in "
        "isolation — to verify the wiring, not just the guard function."
    )

    # No deployment output must have been written (guard runs before _run_phases).
    output_files = list(target_dir.rglob("*"))
    assert not output_files, (
        f"main() wrote {len(output_files)} output file(s) after the guard returned 1. "
        "The guard must abort before any deployment output is written (AC BP-900f-3). "
        f"Unexpected files: {[str(p) for p in output_files[:5]]}"
    )


def test_main_does_not_call_tracked_source_guard_under_validate_only(
    tmp_path: Path,
) -> None:
    """Under --validate-only, main() must NOT invoke _check_tracked_source_guard.

    The guard is a deployment preflight, not a config-correctness check.
    Running it under --validate-only would produce false-positives on machines
    that have not checked out all sources.  The guard is skipped by the
    ``if not args.validate_only:`` block that wraps both preflight guards.
    """
    call_count: list[int] = [0]

    def _counting_guard(package_root: Path) -> int:  # noqa: ARG001
        call_count[0] += 1
        return 0  # returning 0 so if it IS called it would not abort main

    with patch.object(_build, "_check_tracked_source_guard", side_effect=_counting_guard):
        _build.main(["--validate-only"])

    assert call_count[0] == 0, (
        f"_check_tracked_source_guard() was called {call_count[0]} time(s) under "
        "--validate-only. It must be skipped in --validate-only mode because it is "
        "a deployment preflight, not a config-correctness check."
    )


# ---------------------------------------------------------------------------
# H-4: Real-package positive-control tests for _check_tracked_source_guard
# ---------------------------------------------------------------------------


def test_tracked_source_guard_exits_0_on_real_package() -> None:
    """_check_tracked_source_guard() must return 0 on the clean committed worktree.

    This is the key positive-control test (H-4): it calls the REAL guard against
    the REAL package root with NO subprocess mock.  All source paths returned by
    _get_source_paths_for_guard() are committed to git in the worktree, so the
    guard must pass without error.

    If this test fails, a source file that the build deploys is missing from the
    git index — the exact defect the guard is designed to catch.
    """
    result = _build._check_tracked_source_guard(_REAL_PACKAGE_ROOT)
    assert result == 0, (
        f"_check_tracked_source_guard() returned {result!r} on the real package. "
        "Expected 0 (all source paths tracked). "
        "A deployable script's SOURCE file is missing from the git index. "
        "Run: python scripts/build.py --dry-run to see which path is flagged."
    )


def test_tracked_source_guard_nonzero_on_untracked_source(tmp_path: Path) -> None:
    """_check_tracked_source_guard() must return non-zero and name an untracked source.

    Injects a synthetic package root where templates/scripts/feedback/ exists
    (satisfying _manifest_feedback_scripts) but git ls-files returns empty.
    The guard must return 1 and write the untracked source path to stderr.
    """
    from unittest.mock import MagicMock, patch

    pkg = tmp_path / "fake_pkg"
    fb_src = pkg / "templates" / "scripts" / "feedback"
    fb_src.mkdir(parents=True)
    (fb_src / "submit_feedback.py").write_text("# stub\n", encoding="utf-8")

    captured = io.StringIO()
    # _is_git_repo must return True so the guard doesn't short-circuit.
    with patch.object(_build, "_is_git_repo", return_value=True):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            with patch("sys.stderr", captured):
                result = _build._check_tracked_source_guard(pkg)

    assert result != 0, (
        "_check_tracked_source_guard() returned 0 despite git ls-files being empty "
        "(all source paths untracked). Expected non-zero (H-4 negative control)."
    )
    stderr_text = captured.getvalue()
    assert "templates/scripts/feedback/submit_feedback.py" in stderr_text, (
        "Guard returned non-zero but stderr does not name the untracked source path "
        "'templates/scripts/feedback/submit_feedback.py'. "
        f"Actual stderr: {stderr_text!r}"
    )


def test_tracked_source_guard_noop_on_non_git_root(tmp_path: Path) -> None:
    """_check_tracked_source_guard() must return 0 (no-op) for a non-git package root.

    Consumer installs (tarball/pip/vendored) are not git repositories.  The guard
    must detect this and skip silently rather than raising RuntimeError or returning 1
    (H-3 fix: ADR-001 requires build.py to work identically for consumers).
    """
    # tmp_path is guaranteed not to be inside the worktree's git repo.
    pkg = tmp_path / "consumer_install"
    pkg.mkdir()
    # Minimal structure so _get_source_paths_for_guard doesn't raise RuntimeError.
    fb_src = pkg / "templates" / "scripts" / "feedback"
    fb_src.mkdir(parents=True)
    (fb_src / "submit_feedback.py").write_text("# stub\n", encoding="utf-8")

    # Do NOT mock _is_git_repo — let it run for real against tmp_path.
    # tmp_path is under /tmp which is never inside the worktree git index.
    result = _build._check_tracked_source_guard(pkg)

    assert result == 0, (
        f"_check_tracked_source_guard() returned {result!r} for a non-git directory. "
        "Expected 0 (no-op for consumer installs). "
        "The guard must detect that the package root is not a git repository and "
        "skip the check gracefully (H-3 / ADR-001)."
    )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-06-29 [python-coder/TICKET-20260629-BP-1200a-1-ii follow-up]: Added
#   test_commit_guardian_missing_scripts_in_templates. Root cause: 3 scripts
#   (known_failing_tests.py, transform_decision_history.py,
#   check_test_fixture_bloat.py) were absent from
#   templates/scripts/commit_guardian/, causing pytest --collect-only to fail
#   with ModuleNotFoundError for 3 test files. Fix: recovered from git history
#   (83737a44^) and restored to templates/; build.py now deploys them.
#   (#BP-1200a-1-ii)
# - 2026-06-29 [python-coder/TICKET-20260629-BP-1200a-1-ii]: Added
#   test_feedback_scripts_tracked_in_templates and
#   test_fresh_clone_build_guard_exits_0 (AC BP-1200a-1-ii).
#   Root cause: PR #164 untracked scripts/feedback/ (converting it to a
#   gitignored build output) but left no tracked source for fresh clones.
#   Fix: templates/scripts/feedback/ is now the canonical source
#   (mirrors templates/scripts/commit_guardian/ pattern).
#   _manifest_feedback_scripts() and build_feedback() now read from there.
#   See ADR-016 for the policy. (#BP-1200a-1-ii)
# - 2026-06-29 [python-coder/BP-900-guard]: Added H-4 tests:
#   test_tracked_source_guard_exits_0_on_real_package (positive control, no mock),
#   test_tracked_source_guard_nonzero_on_untracked_source (negative control,
#   mocks _is_git_repo=True + subprocess for empty git ls-files output),
#   test_tracked_source_guard_noop_on_non_git_root (H-3 consumer-install no-op,
#   real _is_git_repo against tmp_path which is never a git repo).
#   (#BP-900-guard H-4)
# - 2026-06-24 [python-coder/TICKET-20260624-BP-900f-1/retry]: Added
#   test_main_calls_tracked_source_guard_when_sources_untracked and
#   test_main_does_not_call_tracked_source_guard_under_validate_only.
#   Both tests exercise main() through the build entry point (not the guard
#   function in isolation) to confirm the wiring added in the pr-reviewer H-1
#   repair. The positive test mocks _check_tracked_source_guard to return 1
#   and asserts main() exits non-zero with no output written. The negative test
#   asserts the guard is not called under --validate-only. (#BP-900f-2, #BP-900f-3)
# - 2026-06-22 [debug/quick-fix]: Added test_onboard_hook_opt_in_is_deployable
#   (AC BP-900d). Regression sentinel for the script-promotion gap that made
#   `build.py --target-dir` abort on the onboard.md reference. Asserts the
#   real _get_source_deployable_scripts() lists the promoted script. Pairs with
#   the broad test_guard_exits_0_on_clean_package positive control. (#BP-900d)
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
