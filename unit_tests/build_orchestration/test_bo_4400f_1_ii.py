"""
MODULE: test_bo_4400f_1_ii
GOAL: Red-first behavioural tests for BO-4400f-1-ii -- the change-stash
    patch files the commit-check tool (pre-commit) leaves in its own cache
    folder expire like any other scratch, while its installed hook
    environments in the same folder are never touched.
PROOF SHAPE: a temporary pre-commit cache with four real patch files (two 3
    days old, two 1 hour old), two real hook-environment folders with content
    (as old as the old patches, so age alone would condemn them), the tool's
    database and two near-miss decoys; the DEPLOYED sweep runs as a separate
    process. Every environment file is hashed before and after.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from ._bo4400f1_helpers import backdate, make_sandbox, tree_digest

OLD_PATCHES = ("patch1728000000-4242", "patch1728000007-77")
RECENT_PATCHES = ("patch1728900000-5151", "patch1728900009")
OLD_HOURS, RECENT_HOURS = 72, 1


@pytest.fixture
def sandbox(shared_reference_layout):
    box, holder = make_sandbox(Path(shared_reference_layout) / ".leafcutter" / "scripts")
    yield box
    holder.cleanup()


def _populate(cache: Path) -> list[Path]:
    """Fill ``cache`` like a real pre-commit home; return the untouchable entries."""
    keep = []
    for env in ("repo3k2l9x0a", "repoq81mz7pf"):
        hook_env = cache / env
        (hook_env / "py_env-python3" / "bin").mkdir(parents=True)
        (hook_env / ".pre-commit-hooks.yaml").write_text("- id: ruff\n", encoding="utf-8")
        (hook_env / "py_env-python3" / "bin" / "ruff").write_bytes(b"\x7fELF fake binary")
        keep.append(hook_env)
    (cache / "db.db").write_bytes(b"SQLite format 3\x00")
    (cache / "patch1728000001").mkdir()  # a DIRECTORY named like a patch: never a candidate
    (cache / "patch-notes.txt").write_text("not a stash file\n", encoding="utf-8")
    keep += [cache / "db.db", cache / "patch1728000001", cache / "patch-notes.txt"]
    for entry in keep:
        backdate(entry, OLD_HOURS)
    for name in OLD_PATCHES:
        (cache / name).write_text(f"diff --git a/{name} b/{name}\n", encoding="utf-8")
        backdate(cache / name, OLD_HOURS)
    for name in RECENT_PATCHES:
        (cache / name).write_text(f"diff --git a/{name} b/{name}\n", encoding="utf-8")
        backdate(cache / name, RECENT_HOURS)
    return keep


def _sweep_explicit_home(sandbox) -> tuple[Path, list[Path], dict, dict]:
    cache = sandbox.base / "pre-commit-home"
    cache.mkdir()
    keep = _populate(cache)
    before = {entry: tree_digest(entry) if entry.is_dir() else entry.read_bytes() for entry in keep}
    report = sandbox.sweep({"PRE_COMMIT_HOME": str(cache)})
    return cache, keep, before, report


@pytest.mark.shared_layout_reader
def test_old_pre_commit_stash_files_removed_and_counted(sandbox):
    # covers: BO-4400f-1-ii
    # angle: criterion
    cache, _keep, _before, report = _sweep_explicit_home(sandbox)
    for name in OLD_PATCHES:
        assert not (cache / name).exists(), f"{name} (3 days old) was not removed"
        assert str(cache / name) in report["removed_paths"], report
    assert report["removed"]["scratch"] == 2, report

    # Without PRE_COMMIT_HOME the tool's cache is <user cache dir>/pre-commit.
    default_cache = sandbox.home / ".cache" / "pre-commit"
    default_cache.mkdir(parents=True)
    _populate(default_cache)
    report = sandbox.sweep()
    assert report["removed"]["scratch"] == 2, report
    assert not any((default_cache / name).exists() for name in OLD_PATCHES)


@pytest.mark.shared_layout_reader
def test_recent_pre_commit_stash_files_kept(sandbox):
    # covers: BO-4400f-1-ii
    # angle: boundary
    cache, _keep, _before, report = _sweep_explicit_home(sandbox)
    for name in RECENT_PATCHES:
        assert (cache / name).is_file(), f"{name} (1 hour old) was removed"
        assert str(cache / name) not in report["removed_paths"], report


@pytest.mark.shared_layout_reader
def test_pre_commit_hook_environments_untouched(sandbox):
    # covers: BO-4400f-1-ii
    # angle: discrimination
    # must_catch: clearing the whole pre-commit cache
    cache, keep, before, report = _sweep_explicit_home(sandbox)
    assert report["removed"]["scratch"] == 2, "the sweep must have run and removed the old patches"
    for entry in keep:
        assert entry.exists(), f"{entry.name} was removed from the pre-commit cache"
        after = tree_digest(entry) if entry.is_dir() else entry.read_bytes()
        assert after == before[entry], f"{entry.name} is not byte-identical after the sweep"
    assert sorted(p.name for p in cache.iterdir()) == sorted(
        [e.name for e in keep] + list(RECENT_PATCHES)
    )
