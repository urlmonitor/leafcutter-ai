"""
MODULE: unit_tests/build_guards/_bp1300f_ratchet_fixture.py
GOAL: Shared scaffolding for the BP-1300f-1 mypy-ratchet tests. Each test gets a
    REAL temporary git repository with a base commit on ``main`` and a head commit
    on a ``feature`` branch, and runs the REAL scripts/ci/mypy_ratchet.py against it
    as a subprocess, with the real mypy. Nothing is stubbed: the merge base, the
    rename detection and both mypy verdicts come from git and mypy themselves.
SPEED: a cold mypy run analyses the standard-library stubs from scratch (3 s on a
    quiet machine, 12 s measured on a loaded one). The first call warms ONE mypy
    cache by running the ratchet itself on a throwaway repository holding a single
    clean, uniquely named module, so the cache is written with the ratchet's own
    flags and holds nothing but typeshed modules plus that one name. Every test then
    starts from a private copy of it: no test ever sees another test's project
    modules, so a cached clean file can never stand in for a test's own file.
    The tests never spawn build.py.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parents[2]
RATCHET = REPO_ROOT / "scripts" / "ci" / "mypy_ratchet.py"
PATHSPECS = ("scripts/*.py", "scripts/**/*.py")
TIMEOUT = 600
_IDENTITY = (
    "-c", "user.name=BP-1300f-1 fixture",
    "-c", "user.email=bp-1300f-1@example.invalid",
    "-c", "commit.gpgsign=false",
)
_WARM_MODULE = "scripts/bp1300f_cache_warmer.py"
_SUMMARY = re.compile(
    r"mypy ratchet(?P<failed> FAILED)?: (?P<files>\d+) files?, (?P<new>\d+) new errors? "
    r"\((?P<existing>\d+) existing errors? untouched, (?P<removed>\d+) removed\), "
    r"(?P<ignores>\d+) new type-ignores?"
)

_template_state: dict[str, object] = {}


class RatchetRun(NamedTuple):
    code: int
    out: str


def git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    """Run a real git command in *cwd*; raise on failure so setup errors are loud."""
    return subprocess.run(
        ["git", *_IDENTITY, *args], cwd=str(cwd), capture_output=True, text=True,
        timeout=TIMEOUT, check=True,
    )


def run_ratchet(repo: Path, cache_dir: Path | None, base: str = "main",
                pathspecs: tuple[str, ...] = PATHSPECS,
                env: dict[str, str] | None = None) -> RatchetRun:
    """Run the real module as CI does: --base, then the pathspecs after --."""
    argv = [sys.executable, str(RATCHET), "--repo", str(repo), "--base", base]
    if cache_dir is not None:
        argv += ["--cache-dir", str(cache_dir)]
    argv += ["--", *pathspecs]
    done = subprocess.run(argv, cwd=str(repo), capture_output=True, text=True,
                          timeout=TIMEOUT, env=env)
    return RatchetRun(done.returncode, done.stdout + done.stderr)


def summary(out: str) -> dict[str, int] | None:
    """The counts of the one summary line, or None when no summary was printed."""
    match = _SUMMARY.search(out)
    if match is None:
        return None
    counts = {k: int(v) for k, v in match.groupdict().items() if k != "failed"}
    counts["failed"] = int(match.group("failed") is not None)
    return counts


def _template_cache() -> Path | None:
    """The shared template cache, warmed on first use; None when warming failed."""
    if "cache" not in _template_state:
        holder = tempfile.TemporaryDirectory(prefix="bp1300f-template-")
        _template_state["holder"] = holder  # keeps the directory alive for the process
        _template_state["cache"] = _warm_template(Path(holder.name))
    cache = _template_state["cache"]
    return cache if isinstance(cache, Path) else None


def _warm_template(root: Path) -> Path | None:
    """Run the ratchet once on a throwaway repository so its own flags fill the cache."""
    repo = root / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts" / "keep.py").write_text("KEEP = 1\n", encoding="utf-8")
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    git(repo, "checkout", "-q", "-b", "feature")
    (repo / _WARM_MODULE).write_text("WARM = 1\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "head")
    warmed = run_ratchet(repo, root / "cache")
    if warmed.code != 0 or not (root / "cache" / "head").is_dir():
        return None
    return root / "cache"


class RatchetRepoCase(unittest.TestCase):
    """A real git repository per test, plus a private copy of the warm mypy cache."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="bp1300f-case-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "repo"
        self.root.mkdir()
        self.cache = Path(tmp.name) / "cache"
        template = _template_cache()
        if template is not None:
            shutil.copytree(template / "head", self.cache / "head")
            shutil.copytree(template / "head", self.cache / "base")
        git(self.root, "init", "-q", "-b", "main")

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit_base(self, files: dict[str, str]) -> None:
        """Write *files* and commit them on main: this commit is the merge base."""
        for rel, text in files.items():
            self.write(rel, text)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "base")

    def commit_head(self, files: dict[str, str], renames: dict[str, str] | None = None) -> None:
        """On a feature branch, apply *renames* with git mv, write *files*, commit."""
        git(self.root, "checkout", "-q", "-b", "feature")
        for old, new in (renames or {}).items():
            git(self.root, "mv", old, new)
        for rel, text in files.items():
            self.write(rel, text)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "head")

    def ratchet(self, base: str = "main", env: dict[str, str] | None = None) -> RatchetRun:
        return run_ratchet(self.root, self.cache, base=base, env=env)

    def assert_passed(self, run: RatchetRun) -> dict[str, int]:
        counts = summary(run.out)
        self.assertEqual(run.code, 0, run.out)
        self.assertIsNotNone(counts, f"no summary line in:\n{run.out}")
        assert counts is not None
        self.assertEqual(counts["failed"], 0, run.out)
        return counts

    def assert_failed(self, run: RatchetRun) -> dict[str, int]:
        counts = summary(run.out)
        self.assertEqual(run.code, 1, run.out)
        self.assertIsNotNone(counts, f"no summary line in:\n{run.out}")
        assert counts is not None
        self.assertEqual(counts["failed"], 1, run.out)
        return counts

    def lines_with(self, out: str, *needles: str) -> list[str]:
        """Output lines containing every needle."""
        return [line for line in out.splitlines() if all(n in line for n in needles)]
