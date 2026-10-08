"""
MODULE: unit_tests/ac_store/_tq500g4_fixtures.py
GOAL: Shared REAL-run fixtures for the TQ-500g-4 / TQ-500g-4-i test family
    (a test failed in any sub-case is read as failed; a run that reports
    failure with no failing test is inconclusive).
BUSINESS CONTEXT: The defect lives in one line format of REAL pytest output
    (SUBFAILED lines), so every fixture here is a real test module that a real
    child pytest process runs -- never a hand-typed stdout string. The runs
    named in the ACs are built as real files in a real git clone (so the
    red-baseline gate's newly-added partition works) plus a real AC YAML store
    written through yaml.safe_dump (Fixture Authenticity Rule, 2h.2).
ARCHITECTURE: Not a test file (leading underscore). Reuses the git helpers of
    unit_tests/build_orchestration/_tq500f3i_fixtures.py rather than copying them.
    Runs: S (S1/S2/S3 gates module), R1 (conftest forces exit 1 over all-PASSED
    tests), R2 (clean passing), R3 (plain failing test_refresh_gate).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import unit_tests.build_orchestration._tq500f3i_fixtures as gitfx

REPO_ROOT = gitfx.REPO_ROOT
AC_STORE_DIR = REPO_ROOT / "scripts" / "ac_store"
FAST_LANE = REPO_ROOT / "scripts" / "build_orchestration" / "fast_lane.py"
MARK_DONE = AC_STORE_DIR / "mark_ac_done.py"

# One AC id per scenario test so a requirement is "covered only by" one test.
AC_S1, AC_S2, AC_S3 = "FXA-101", "FXA-102", "FXA-103"
ALL_ACS = [AC_S1, AC_S2, AC_S3]
SUBCASE = "retry_due unset"

_GATES_SOURCE = f'''\
import unittest


class TestGates(unittest.TestCase):
    def test_refresh_gate(self):
        # covers: {AC_S1}
        for case in ("{SUBCASE}", "retry_due set"):
            with self.subTest(msg=case):
                self.assertNotEqual(case, "{SUBCASE}")

    def test_export_gate(self):
        # covers: {AC_S2}
        for case in ("csv", "json"):
            with self.subTest(msg=case):
                self.assertTrue(case)

    def test_window_gate(self):
        # covers: {AC_S3}
        self.fail("window closed")
'''

_ALL_PASS_SOURCE = f'''\
def test_refresh_gate():
    # covers: {AC_S1}
    assert True


def test_export_gate():
    # covers: {AC_S2}
    assert True
'''

_R3_SOURCE = f'''\
def test_refresh_gate():
    # covers: {AC_S1}
    assert 1 == 2, "refresh gate failed"


def test_export_gate():
    # covers: {AC_S2}
    assert True
'''

# R1: every test line reads PASSED, yet the session exits 1 -- no hand-typed output.
_EXIT_ONE_CONFTEST = '''\
def pytest_sessionfinish(session, exitstatus):
    session.exitstatus = 1
'''

RUNS = {
    "S": {"test_gates.py": _GATES_SOURCE},
    "R1": {"test_gates.py": _ALL_PASS_SOURCE, "conftest.py": _EXIT_ONE_CONFTEST},
    "R2": {"test_gates.py": _ALL_PASS_SOURCE},
    "R3": {"test_gates.py": _R3_SOURCE},
}


def build_run(tmp_root: Path, run: str) -> tuple[Path, Path, Path]:
    """Build a git clone holding run *run*'s files uncommitted (newly added).

    Returns:
        ``(work_dir, test_root, ac_root)``.
    """
    work_dir, _base = gitfx.make_worktree(tmp_root)
    test_root = work_dir / "fx_tests"
    for rel, source in RUNS[run].items():
        gitfx.write(test_root / rel, source)
    ac_root = work_dir / "ac_store"
    for ac_id in ALL_ACS:
        gitfx.write_ac_yaml(ac_root, ac_id, [], work_status="in_progress")
    return work_dir, test_root, ac_root


def import_readers():
    """Import the production readers from the real scripts/ac_store tree."""
    if str(AC_STORE_DIR) not in sys.path:
        sys.path.insert(0, str(AC_STORE_DIR))
    import done_proof  # noqa: PLC0415
    import done_proof_kind_support  # noqa: PLC0415

    return done_proof, done_proof_kind_support


def test_files(test_root: Path) -> list[Path]:
    return sorted(p for p in test_root.glob("test_*.py"))


def read_through_done_proof(test_root: Path) -> dict[str, str]:
    done_proof, _ = import_readers()
    return done_proof._run_pytest_and_parse(test_files(test_root))


def read_through_kind_plugin(test_root: Path) -> dict[str, str]:
    _, kind = import_readers()
    outcomes, _kinds = kind._run_pytest_and_parse_with_kind(test_files(test_root))
    return outcomes


def outcome_by_name(outcomes: dict[str, str]) -> dict[str, str]:
    """Map trailing test function name -> outcome (sentinel keys kept as-is)."""
    return {k.rsplit("::", 1)[-1]: v for k, v in outcomes.items()}


def run_red_baseline_cli(
    work_dir: Path, test_root: Path, ac_ids: list[str], script: Path = FAST_LANE
) -> tuple[int, dict]:
    """Run ``fast_lane.py verify_red_baseline`` as a subprocess; return (rc, verdict)."""
    proc = subprocess.run(
        [sys.executable, str(script), "verify_red_baseline",
         "--ac-ids", ",".join(ac_ids), "--test-root", str(test_root)],
        cwd=work_dir, capture_output=True, text=True, timeout=180,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    try:
        verdict = json.loads(proc.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError) as exc:
        raise AssertionError(
            f"verify_red_baseline printed no JSON verdict (rc={proc.returncode}): "
            f"stdout={proc.stdout!r} stderr={proc.stderr[-800:]!r}"
        ) from exc
    return proc.returncode, verdict


def run_mark_done_cli(work_dir: Path, ac_root: Path, test_root: Path, ac_id: str):
    """Run the done-proof production CLI (mark_ac_done.py --test-root) for *ac_id*."""
    return subprocess.run(
        [sys.executable, str(MARK_DONE), "--ac", ac_id, "--ac-root", str(ac_root),
         "--test-root", str(test_root), "--dry-run"],
        cwd=work_dir, capture_output=True, text=True, timeout=180,
    )


def bucket_names(verdict: dict, bucket: str) -> set[str]:
    return gitfx.names(verdict.get(bucket))
