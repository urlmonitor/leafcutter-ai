"""Tests for scripts/ci/check_fixture_orphans.py.

Each test constructs a synthetic directory tree using pytest's tmp_path fixture
and invokes the script as a subprocess so the exit-code contract is verified
independently of the implementation's internal structure.
"""
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SCRIPT_PATH = (
    Path(__file__).parent.parent.parent / "scripts" / "ci" / "check_fixture_orphans.py"
)


def _run(fixtures_dir: Path, tests_dir: Path) -> subprocess.CompletedProcess:
    """Invoke check_fixture_orphans.py with explicit --fixtures-dir / --tests-dir."""
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--fixtures-dir",
            str(fixtures_dir),
            "--tests-dir",
            str(tests_dir),
        ],
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_orphan_detected(tmp_path: Path) -> None:
    """Fixture dir exists but no corresponding test file → exits 1, prints ORPHAN."""
    fixtures_dir = tmp_path / "fixtures"
    tests_dir = tmp_path / "tests"
    fixtures_dir.mkdir()
    tests_dir.mkdir()

    # Create an orphan fixture directory with no matching test file
    (fixtures_dir / "removed_module").mkdir()

    result = _run(fixtures_dir, tests_dir)

    assert result.returncode == 1, (
        f"Expected exit 1 for orphan dir; got {result.returncode}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "ORPHAN" in result.stdout, (
        f"Expected 'ORPHAN' in stdout; got:\n{result.stdout}"
    )
    assert "removed_module" in result.stdout


def test_no_orphan_when_test_exists(tmp_path: Path) -> None:
    """Fixture dir and corresponding test file both exist → exits 0, no ORPHAN line."""
    fixtures_dir = tmp_path / "fixtures"
    tests_dir = tmp_path / "tests"
    fixtures_dir.mkdir()
    tests_dir.mkdir()

    (fixtures_dir / "build_clean").mkdir()
    (tests_dir / "test_build_clean.py").touch()

    result = _run(fixtures_dir, tests_dir)

    assert result.returncode == 0, (
        f"Expected exit 0 for matched fixture; got {result.returncode}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "ORPHAN" not in result.stdout


def test_shared_dir_excluded(tmp_path: Path) -> None:
    """_shared/ directory is excluded from orphan checks even without a test file."""
    fixtures_dir = tmp_path / "fixtures"
    tests_dir = tmp_path / "tests"
    fixtures_dir.mkdir()
    tests_dir.mkdir()

    (fixtures_dir / "_shared").mkdir()
    # No test_*_shared*.py file exists — should still pass

    result = _run(fixtures_dir, tests_dir)

    assert result.returncode == 0, (
        f"Expected exit 0 when only _shared/ present; got {result.returncode}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "ORPHAN" not in result.stdout


def test_pycache_excluded(tmp_path: Path) -> None:
    """__pycache__/ entries are excluded from orphan checking."""
    fixtures_dir = tmp_path / "fixtures"
    tests_dir = tmp_path / "tests"
    fixtures_dir.mkdir()
    tests_dir.mkdir()

    (fixtures_dir / "__pycache__").mkdir()

    result = _run(fixtures_dir, tests_dir)

    assert result.returncode == 0, (
        f"Expected exit 0 when only __pycache__/ present; got {result.returncode}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "ORPHAN" not in result.stdout


def test_empty_fixtures_dir(tmp_path: Path) -> None:
    """Empty fixtures directory → no orphans → exits 0."""
    fixtures_dir = tmp_path / "fixtures"
    tests_dir = tmp_path / "tests"
    fixtures_dir.mkdir()
    tests_dir.mkdir()

    result = _run(fixtures_dir, tests_dir)

    assert result.returncode == 0, (
        f"Expected exit 0 for empty fixtures dir; got {result.returncode}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    # The success message should be present
    assert "No orphan" in result.stdout


def test_multiple_orphans(tmp_path: Path) -> None:
    """Multiple orphan dirs are all reported and exit code is 1."""
    fixtures_dir = tmp_path / "fixtures"
    tests_dir = tmp_path / "tests"
    fixtures_dir.mkdir()
    tests_dir.mkdir()

    (fixtures_dir / "old_module_a").mkdir()
    (fixtures_dir / "old_module_b").mkdir()

    result = _run(fixtures_dir, tests_dir)

    assert result.returncode == 1
    assert result.stdout.count("ORPHAN") == 2


def test_files_in_fixtures_dir_not_flagged(tmp_path: Path) -> None:
    """Regular files (not directories) under fixtures/ are ignored."""
    fixtures_dir = tmp_path / "fixtures"
    tests_dir = tmp_path / "tests"
    fixtures_dir.mkdir()
    tests_dir.mkdir()

    (fixtures_dir / "some_data.json").touch()

    result = _run(fixtures_dir, tests_dir)

    assert result.returncode == 0, (
        f"Expected exit 0; files in fixtures/ should not be flagged.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "ORPHAN" not in result.stdout
