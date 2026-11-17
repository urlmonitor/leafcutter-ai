"""Shared helpers for test_bo_4400f_2.py: run a REAL pytest session on a
synthetic three-test suite (two pass, one fails, each writes 10 MB) using the
repo's own pytest.ini and plugins, with HOME / XDG_CACHE_HOME / TMPDIR
redirected, and inspect disk afterwards.

ASSUMED PRODUCTION CONTRACT (python-coder implements against exactly this):
    * pytest.ini registers a plugin via ``-p`` in addopts and sets
      ``tmp_path_retention_policy = failed``.
    * With no --basetemp the plugin picks a per-run unique folder inside the
      one scratch location (under ``$XDG_CACHE_HOME/leafcutter/scratch``).
    * A --basetemp (argv or PYTEST_ADDOPTS) inside a durable folder
      (``test-logs``, ``debugging/logs``) or anywhere in the project tree stops
      the run before collection with a usage error naming the folder as durable.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTEST_INI = REPO_ROOT / "pytest.ini"
DURABLE_DIRS = (REPO_ROOT / "test-logs", REPO_ROOT / "debugging" / "logs")
TEN_MB = 10 * 1024 * 1024
FILES = {
    "pass_one": "scratch_pass_one.bin",
    "pass_two": "scratch_pass_two.bin",
    "fail": "scratch_fail.bin",
}

SUITE_SOURCE = '''
import os
from pathlib import Path

TEN_MB = 10 * 1024 * 1024


def _mark_ran():
    sentinel = os.environ.get("BO4400F2_SENTINEL")
    if sentinel:
        with open(sentinel, "a") as handle:
            handle.write("ran\\n")


def test_pass_one(tmp_path):
    _mark_ran()
    (tmp_path / "scratch_pass_one.bin").write_bytes(b"\\0" * TEN_MB)


def test_pass_two(tmp_path):
    _mark_ran()
    (tmp_path / "scratch_pass_two.bin").write_bytes(b"\\0" * TEN_MB)


def test_fail(tmp_path):
    _mark_ran()
    (tmp_path / "scratch_fail.bin").write_bytes(b"\\0" * TEN_MB)
    assert False, "deliberate failure to exercise retention"
'''


_HOLDERS: list[tempfile.TemporaryDirectory] = []


@dataclass
class Run:
    """One real pytest session and the places it was allowed to touch."""

    result: subprocess.CompletedProcess
    home: Path
    temp_standin: Path
    sentinel: Path
    project_before: set[str]
    project_after: set[str]

    @property
    def output(self) -> str:
        return self.result.stdout + self.result.stderr

    @property
    def tests_that_ran(self) -> int:
        if not self.sentinel.exists():
            return 0
        return len(self.sentinel.read_text(encoding="utf-8").splitlines())


def snapshot_project() -> set[str]:
    """Top-level project entries plus every entry inside the durable folders."""
    seen = {f"top:{name}" for name in os.listdir(REPO_ROOT)}
    for durable in DURABLE_DIRS:
        if durable.exists():
            for dirpath, dirnames, filenames in os.walk(durable):
                for name in dirnames + filenames:
                    seen.add(f"durable:{Path(dirpath, name)}")
        seen.add(f"durable-exists:{durable}:{durable.exists()}")
    return seen


def find_files(roots: list[Path], name: str) -> list[Path]:
    """Every file called ``name`` under any of ``roots`` (skipping .git)."""
    found: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules")]
            if name in filenames:
                found.append(Path(dirpath, name))
    return found


def run_session(
    extra_args: list[str] | None = None,
    pytest_addopts: str | None = None,
    keep: list[tempfile.TemporaryDirectory] | None = None,
) -> Run:
    """Run the synthetic suite in a real pytest subprocess under the repo ini."""
    holder = tempfile.TemporaryDirectory(prefix="bo4400f2_")
    _HOLDERS.append(holder)  # keep alive so the inspected disk is not reaped
    if keep is not None:
        keep.append(holder)
    base = Path(holder.name)
    home = base / "home"
    temp_standin = base / "systemtmp"
    suite = base / "suite"
    for folder in (home, temp_standin, suite):
        folder.mkdir()
    (suite / "test_synthetic_scratch.py").write_text(SUITE_SOURCE, encoding="utf-8")
    sentinel = base / "sentinel.txt"
    env = {
        **{k: v for k, v in os.environ.items() if k != "PYTEST_ADDOPTS"},
        "HOME": str(home),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "TMPDIR": str(temp_standin),
        "TEMP": str(temp_standin),
        "TMP": str(temp_standin),
        "BO4400F2_SENTINEL": str(sentinel),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(REPO_ROOT),
    }
    if pytest_addopts:
        env["PYTEST_ADDOPTS"] = pytest_addopts
    argv = [
        sys.executable, "-m", "pytest", "-c", str(PYTEST_INI),
        "--rootdir", str(REPO_ROOT), "-p", "no:cacheprovider", str(suite),
        *(extra_args or []),
    ]
    before = snapshot_project()
    result = subprocess.run(  # noqa: S603
        argv, cwd=suite, env=env, capture_output=True, text=True,
        timeout=300, check=False,
    )
    return Run(result, home, temp_standin, sentinel, before, snapshot_project())


_CACHED: list[Run] = []


def default_run() -> Run:
    """The one default-settings session shared by the first three tests."""
    if not _CACHED:
        _CACHED.append(run_session(keep=_HOLDERS))
    return _CACHED[0]
