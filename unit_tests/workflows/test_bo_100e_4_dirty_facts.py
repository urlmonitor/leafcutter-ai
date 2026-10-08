"""Real-git tests for the ``dirty`` subcommand of worktree_repo_facts.py (BO-100e-4).

Covers:
  BO-100e-4 -- before an epic run continues past a halted ticket, the driver
               reads the worktree's staged / unstaged / untracked paths ONCE
               through ``worktree_repo_facts.py dirty`` (F4 Option A: staged
               leftovers stop the run; an unreadable state stops it too).

Every case runs the REAL script as a subprocess against a REAL temporary git
repository built with the real ``git`` binary -- no mocked ``git status``
text, which would only prove the parser agrees with its own author's idea of
the porcelain format.

Contract pinned here (the driver side requires it, see
test_bo_100e_4_continue_past_halt.py): one JSON object on stdout with
``readable: true`` and three array-typed lists of repo-relative, forward-slash,
unquoted paths. A state git could not report is NEVER a clean-looking answer:
it is a non-zero exit or ``readable`` other than true.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "templates" / "scripts" / "worktree_repo_facts.py"

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not on PATH")


@pytest.fixture
def sandbox():
    """A temp folder; the git ceiling stops discovery from reaching a parent repo."""
    root = Path(tempfile.mkdtemp(prefix="bo100e4_dirty_"))
    yield root
    shutil.rmtree(root, ignore_errors=True)


def _env(root: Path) -> dict:
    env = dict(os.environ)
    env["GIT_CEILING_DIRECTORIES"] = str(root.parent)
    return env


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-c", "core.autocrlf=false", "-c", "commit.gpgsign=false", *args],
        cwd=repo, capture_output=True, text=True, check=True, env=_env(repo),
    )
    return done.stdout


def make_repo(root: Path, tracked=("staged.txt", "unstaged.txt")) -> Path:
    """A repository with one commit holding ``tracked`` files."""
    repo = root / "repo"
    (repo / "pkg").mkdir(parents=True)
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "t@example.invalid")
    git(repo, "config", "user.name", "Test")
    for name in tracked:
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"{name} v1\n", encoding="utf-8", newline="\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "initial")
    return repo


def write(repo: Path, name: str, text: str = "changed\n") -> None:
    target = repo / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="\n")


def run_dirty(path: Path, root: Path):
    """Run the real script; return (process, parsed JSON or None).

    A reply that is not one JSON object is a failed assertion here, never a
    parse error, so a missing subcommand reads as a red test with its cause.
    """
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "dirty", str(path)],
        capture_output=True, text=True, check=False, env=_env(root),
    )
    try:
        data = json.loads(proc.stdout)
    except ValueError:
        data = None
    assert isinstance(data, dict), (
        f"`dirty` printed no JSON object: rc={proc.returncode} out={proc.stdout!r} err={proc.stderr!r}"
    )
    return proc, data


def test_dirty_subcommand_reports_staged_unstaged_untracked(sandbox):
    # covers: BO-100e-4
    # angle: real_artifact
    """One staged, one unstaged-modified and one untracked file are named in
    exactly the right lists, and the command exits 0 with readable true."""
    repo = make_repo(sandbox)
    write(repo, "staged.txt")
    git(repo, "add", "staged.txt")
    write(repo, "unstaged.txt")
    write(repo, "untracked.txt")
    proc, data = run_dirty(repo, sandbox)
    assert proc.returncode == 0, proc.stderr
    assert data["readable"] is True
    assert data["staged"] == ["staged.txt"]
    assert data["unstaged"] == ["unstaged.txt"]
    assert data["untracked"] == ["untracked.txt"]


def test_dirty_subcommand_outside_a_repo_reports_unreadable(sandbox):
    # covers: BO-100e-4
    # angle: failure
    """A folder that is not a git repository is reported as UNREADABLE, never as
    clean. Like every sibling subcommand the script answers a not-a-checkout
    outcome IN its JSON result (readable false), so the driver fails closed."""
    plain = sandbox / "not_a_repo"
    plain.mkdir()
    _, data = run_dirty(plain, sandbox)
    assert data.get("readable") is False, f"a non-repo was not reported unreadable: {data}"
    assert not any(data.get(key) for key in ("staged", "unstaged", "untracked")), data


def test_dirty_subcommand_reports_a_clean_repository_as_readable_and_empty(sandbox):
    # covers: BO-100e-4
    # angle: boundary
    """The empty pole: nothing dirty is a readable answer with three empty lists,
    distinct from the unreadable answer above."""
    repo = make_repo(sandbox)
    proc, data = run_dirty(repo, sandbox)
    assert proc.returncode == 0, proc.stderr
    assert (data["readable"], data["staged"], data["unstaged"], data["untracked"]) == (True, [], [], [])


def test_dirty_subcommand_expands_untracked_directories_to_files(sandbox):
    # covers: BO-100e-4
    # angle: boundary
    """A file in a new directory is named as a file (with a forward slash), never
    as its directory, or an overlap check against a file path would miss it."""
    repo = make_repo(sandbox)
    write(repo, "newdir/sub/x.txt")
    write(repo, "newdir/y.txt")
    _, data = run_dirty(repo, sandbox)
    assert sorted(data["untracked"]) == ["newdir/sub/x.txt", "newdir/y.txt"]


def test_dirty_subcommand_names_the_new_path_of_a_staged_rename(sandbox):
    # covers: BO-100e-4
    # angle: boundary
    """A staged rename is reported as a path, never as the raw 'old -> new' text."""
    repo = make_repo(sandbox)
    git(repo, "mv", "unstaged.txt", "pkg/renamed.txt")
    _, data = run_dirty(repo, sandbox)
    assert "pkg/renamed.txt" in data["staged"], data
    assert not any("->" in path for key in ("staged", "unstaged", "untracked") for path in data[key])


def test_dirty_subcommand_reports_a_file_staged_and_then_modified_in_both_lists(sandbox):
    # covers: BO-100e-4
    # angle: boundary
    """A staged file edited again afterwards has staged AND unstaged changes."""
    repo = make_repo(sandbox)
    write(repo, "staged.txt", "first\n")
    git(repo, "add", "staged.txt")
    write(repo, "staged.txt", "second\n")
    _, data = run_dirty(repo, sandbox)
    assert data["staged"] == ["staged.txt"]
    assert data["unstaged"] == ["staged.txt"]


@pytest.mark.parametrize("name", ["my file.txt", "café.txt"])
def test_dirty_subcommand_reports_awkward_filenames_unquoted(sandbox, name):
    # covers: BO-100e-4
    # angle: boundary
    """git quotes a path with a space or non-ASCII characters in its default
    porcelain output; the answer must carry the real, unquoted name."""
    repo = make_repo(sandbox)
    write(repo, name)
    _, data = run_dirty(repo, sandbox)
    assert data["untracked"] == [name], data


def test_dirty_subcommand_is_read_only(sandbox):
    # covers: BO-100e-4
    # angle: criterion
    """Reading the state never stages, unstages or otherwise changes it (F4
    Option A forbids touching the halted ticket's leftovers)."""
    repo = make_repo(sandbox)
    write(repo, "staged.txt")
    git(repo, "add", "staged.txt")
    write(repo, "unstaged.txt")
    write(repo, "untracked.txt")
    before = git(repo, "status", "--porcelain=v1", "-z", "-uall")
    run_dirty(repo, sandbox)
    assert git(repo, "status", "--porcelain=v1", "-z", "-uall") == before
