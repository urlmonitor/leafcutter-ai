"""
MODULE: test_consumer_simulation
GOAL: RED test stubs for AC BP-900h-1 — a CI-facing consumer-install simulator
    that (1) creates a genuinely empty scratch directory, (2) runs the real
    ``build.py --target-dir`` against it as a real subprocess, (3) asserts the
    deployed output root contains ``scripts/`` and ``agents/``, and (4) reuses
    the existing reference-extraction and broken-reference-report machinery
    (BP-900b-1 / BP-900c-1) to fail the job with the unresolved paths named on
    stderr when any compiled template references a script that does not exist
    in the deployed tree.
TICKET: tickets/00_inbox/epics/EPIC-DeploymentCompleteness/12_TICKET-20260817-BP-900h-1.md
AC: BP-900h-1 (source_ac)

CONTRACT (fixed by the ticket-supervisor's empirical validation — see ticket
    body "CLI contract" section — python-coder implements against this exact
    spec, so this test asserts against it verbatim rather than inventing a
    different CLI):

    python scripts/ci/check_consumer_install.py \
        --package-dir <path-to-leafcutter-ai-checkout> \
        --target-dir <scratch-dir> \
        [--skip-build]

    Exit codes: 0 = OK; 1 = build failed / incomplete deploy / unresolved
    references; 2 = usage/environment error.

    ``scripts/ci/check_consumer_install.py`` does NOT exist yet in this
    worktree (confirmed via ``ls scripts/ci/`` before authoring this file —
    only ``__init__.py`` and ``check_fixture_orphans.py`` are present), so
    both tests below are expected to fail RED at authoring time: the
    subprocess invocation exits non-zero (typically 2, "can't open file") and
    the assertions on exit code / deployed-tree contents never get satisfied.
    python-coder's job is to write the script to this contract and turn both
    tests green.

REAL-ARTIFACT BEHAVIORAL TEST NOTE (BP-1100f-2 / real-effect round-trip):
    Both tests below run the REAL script as a REAL subprocess against a REAL
    ``tmp_path`` scratch directory — never a copy of this repository, per the
    ticket's Implementation Notes ("Build the scratch project from an empty
    directory, never from a copy of this repository"). Neither test mocks the
    build subprocess, the filesystem, or the reference-resolution check. Test
    1 reads the deployed tree back off disk after the script runs
    (``(tmp_path / ".leafcutter").is_dir()`` etc.) — this is the round-trip.
    Test 2 additionally deletes a real deployed file and re-runs the real
    script to prove the negative case actually fires on real output, not on a
    mocked call.
"""
# @ac-tag: BP-900h-1

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup. conftest.py in this directory already inserts the worktree root
# onto sys.path; we additionally need the concrete path to the script under
# test (invoked as a subprocess, so no import is required for it, but we do
# need the worktree root to build --package-dir).
# ---------------------------------------------------------------------------
_WORKTREE_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_PATH = _WORKTREE_ROOT / "scripts" / "ci" / "check_consumer_install.py"

# The exact deployed script path deleted by test 2 to trigger a genuine
# broken-reference finding. Verified empirically by the ticket-supervisor:
# this file IS deployed by a real build.py run, and IS referenced via
# "{{config.output_root}}/scripts/ac_store/ac_prioritizer.py" in
# templates/agents/build-ac.md, so deleting it reliably produces exactly one
# broken-reference entry naming this exact path.
_DELETED_SCRIPT_REL = Path(".leafcutter") / "scripts" / "ac_store" / "ac_prioritizer.py"
_MISSING_REF_STRING = "scripts/ac_store/ac_prioritizer.py"


def _run_check_consumer_install(*extra_args: str) -> subprocess.CompletedProcess[str]:
    """Invoke scripts/ci/check_consumer_install.py as a real subprocess.

    Deliberately does NOT special-case a missing script file: if the script
    does not exist yet, ``subprocess.run`` still returns a CompletedProcess
    (Python's launcher exits with code 2 and prints "can't open file ..." to
    stderr) rather than raising, so callers can assert on ``returncode`` /
    ``stderr`` uniformly whether the script exists or not. This is the
    expected RED path today.
    """
    argv = [sys.executable, str(_SCRIPT_PATH), *extra_args]
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_consumer_simulation_build_succeeds_in_empty_project(tmp_path: Path) -> None:
    """AC BP-900h-1: a genuinely empty scratch dir + real build.py must succeed.

    Given a scratch directory containing no files other than what the script
    itself creates (a minimal skills_config.json), and the package pointed at
    via --package-dir (this worktree root, which contains scripts/build.py),
    when check_consumer_install.py runs, the underlying real build.py
    subprocess must exit 0 and the deployed output root
    (tmp_path/.leafcutter, per the empirically-verified default output_root
    for a minimal `{}` config) must contain both `agents/` and `scripts/`.

    RED at authoring time: scripts/ci/check_consumer_install.py does not
    exist, so this subprocess invocation cannot succeed.
    """
    # covers: BP-900h-1
    target_dir = tmp_path / "consumer_project"

    result = _run_check_consumer_install(
        "--package-dir", str(_WORKTREE_ROOT),
        "--target-dir", str(target_dir),
    )

    assert result.returncode == 0, (
        "check_consumer_install.py did not exit 0 for a real build into an "
        f"empty scratch directory.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    deployed_root = target_dir / ".leafcutter"
    assert deployed_root.is_dir(), (
        f"Expected deployed output root at {deployed_root} after a "
        f"successful check_consumer_install.py run. stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    assert (deployed_root / "scripts").is_dir(), (
        f"Expected {deployed_root / 'scripts'} to exist and be a directory "
        "(AC BP-900h-1: 'the deployed output root exists and contains "
        f"scripts/ and agents/'). stderr:\n{result.stderr}"
    )
    assert (deployed_root / "agents").is_dir(), (
        f"Expected {deployed_root / 'agents'} to exist and be a directory "
        "(AC BP-900h-1: 'the deployed output root exists and contains "
        f"scripts/ and agents/'). stderr:\n{result.stderr}"
    )


def test_consumer_simulation_detects_unresolved_reference(tmp_path: Path) -> None:
    """AC BP-900h-1 negative case: a deleted deployed script must be reported.

    Runs the real script once to get a green deployed tree, deletes one
    deployed script that IS referenced by a real compiled agent template
    (scripts/ac_store/ac_prioritizer.py, referenced by build-ac.md), then
    re-runs the script with --skip-build (so the build step does not silently
    redeploy the file we just deleted) and asserts the job fails, naming the
    missing path on stderr. This is the test that proves the gate can
    actually fail — a purely-positive test suite would pass on a check that
    never runs its own reference-resolution logic.

    RED at authoring time: scripts/ci/check_consumer_install.py does not
    exist, so neither the initial build nor the --skip-build re-run can
    succeed.
    """
    # covers: BP-900h-1
    target_dir = tmp_path / "consumer_project"

    first_run = _run_check_consumer_install(
        "--package-dir", str(_WORKTREE_ROOT),
        "--target-dir", str(target_dir),
    )
    assert first_run.returncode == 0, (
        "Precondition failed: the initial (unmodified) check_consumer_install.py "
        f"run must succeed before the negative case can be exercised.\n"
        f"stdout:\n{first_run.stdout}\nstderr:\n{first_run.stderr}"
    )

    deleted_script = target_dir / _DELETED_SCRIPT_REL
    assert deleted_script.is_file(), (
        f"Expected {deleted_script} to exist after the first real build so "
        "it can be deleted to trigger the negative case. If this path has "
        "moved, update _DELETED_SCRIPT_REL to a script that is both deployed "
        "and referenced by a real compiled agent template."
    )
    deleted_script.unlink()

    second_run = _run_check_consumer_install(
        "--package-dir", str(_WORKTREE_ROOT),
        "--target-dir", str(target_dir),
        "--skip-build",
    )

    assert second_run.returncode != 0, (
        "check_consumer_install.py must fail (non-zero exit) when a script "
        "referenced by a compiled template is missing from the deployed "
        f"tree.\nstdout:\n{second_run.stdout}\nstderr:\n{second_run.stderr}"
    )
    assert _MISSING_REF_STRING in second_run.stderr, (
        f"Expected the missing path {_MISSING_REF_STRING!r} to be named on "
        f"stderr (AC BP-900h-1: 'the job fails with the unresolved paths "
        f"named on stderr'). stderr was:\n{second_run.stderr}"
    )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-26 [test-writer/EPIC-DeploymentCompleteness/12_BP-900h-1]: Initial
#   failing test stubs. scripts/ci/check_consumer_install.py does not exist
#   yet (confirmed via ls scripts/ci/ before authoring). CLI contract, exit
#   codes, and the exact deployed-script/referencing-template pair used in
#   the negative case were fixed by the ticket-supervisor's prior empirical
#   validation in this worktree (real build.py run + real
#   extract_compiled_script_path_refs()/build_broken_ref_report() calls
#   confirmed scripts/ac_store/ac_prioritizer.py is both deployed and
#   referenced by templates/agents/build-ac.md). Both tests invoke the real
#   script as a real subprocess against a real tmp_path scratch directory —
#   no mocking of the build, filesystem, or reference-resolution check
#   (BP-1100f-2 real-effect round-trip). Expected red state: non-zero exit
#   from subprocess.run (Python launcher's "can't open file" behavior, exit
#   code 2) rather than the asserted exit code 0 / stderr content — captured
#   verbatim in the red_baseline below.
# ====================================================================
