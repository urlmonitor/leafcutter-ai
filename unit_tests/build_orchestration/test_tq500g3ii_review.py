"""
MODULE: unit_tests/build_orchestration/test_tq500g3ii_review.py
GOAL: Review-fix tests for TQ-500g-3-ii: a module-level skip is 'skipped' (never 'removed', and a recorded
    'removed' entry never excuses it); a base commit holding symlinks is still exported and compared; a
    nested unrelated config file does not widen the scope of the runs.
BUSINESS CONTEXT: Real scratch git repos, real pytest on both sides, the real consumer_sweep.py CLIs; the
    scope rule is also called in-process on a representative changed-paths list.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

import unit_tests.build_orchestration._tq500g3i_fixtures as fx
import unit_tests.build_orchestration._tq500g3ii_fixtures as ix

_NOTE = "the requirement dropped this check"
_MOD_SKIPS = {
    "skip_call": 'pytest.skip("x", allow_module_level=True)\n',
    "importorskip": 'pytest.importorskip("no_such_mod_tq500g3ii")\n',
}
_LINKS = {"assets/link_in": "keep.txt", "assets/link_out": "../../outside"}


def _module_skip(line: str):
    """A text edit adding *line* (a module-level skip) right after the ``import pytest`` line."""
    return lambda text: ix.sub(text, "import pytest\n", "import pytest\n" + line)


def _record_unlisted_then_removed(repo: fx.Repo, tests: list[str]) -> dict:
    """Record the edits the first check reports (as strengthened) plus a 'removed' entry per test; re-check."""
    _proc, first = ix.run_check(repo)
    listed = [ix.listed(i["file"], i["test"]) for i in first["unlisted"]]
    listed += [ix.listed(ix.REFRESH, t, "removed", _NOTE) for t in tests]
    fx.recorded(repo, listed)
    proc, out = ix.run_check(repo)
    fx.assert_check_shape(proc, out)
    return out


@pytest.mark.parametrize("variant", sorted(_MOD_SKIPS))
def test_h1_module_level_skip_is_skipped_and_removed_entry_does_not_excuse_it(tmp_path: Path, variant: str):
    # covers: TQ-500g-3-ii
    # angle: discrimination
    # must_catch: a module-level skip reports what 'removed' because the file yields no test items
    # must_catch: a recorded 'removed' entry with a note excuses the module-level skip as a removal
    repo = ix.scenario(tmp_path, {ix.REFRESH: _module_skip(_MOD_SKIPS[variant])})
    out = _record_unlisted_then_removed(repo, [ix.A, ix.D])
    assert out["unlisted"] == [], f"TQ-500g-3-i must pass here so only the runs decide: {out['unlisted']}"
    assert ix.whats(out) == {ix.A: "skipped", ix.D: "skipped"}, (variant, out["weakened"])
    assert out["removed"] == [], (variant, out["removed"])
    assert out["passed"] is False and out["reason"] == "weakened", (variant, out)
    assert fx.pairs(out["weakened"]) == {(ix.REFRESH, ix.A), (ix.REFRESH, ix.D)}, out["weakened"]


def _blob(repo: fx.Repo, content: str) -> str:
    """The id of a blob holding *content* (no trailing newline), written into the repo."""
    raw = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=repo.root, input=content.encode(),
                         capture_output=True, check=True)
    return raw.stdout.decode().strip()


def _commit_symlinks(repo: fx.Repo) -> None:
    """Commit symlink entries (mode 120000) without needing an OS symlink: the blob is the target path text."""
    fx.write(repo.path("assets/keep.txt"), "kept\n")
    ix.git_text(repo, "add", "assets/keep.txt")
    for rel, target in _LINKS.items():
        ix.git_text(repo, "update-index", "--add", "--cacheinfo", f"120000,{_blob(repo, target)},{rel}")
    ix.git_text(repo, "commit", "-m", "base with symlinks")
    modes = ix.git_text(repo, "ls-tree", "-r", "HEAD", "--", "assets")
    assert modes.count("120000") == len(_LINKS), f"the base commit must hold the symlink entries: {modes!r}"


def test_m3_symlinks_in_base_commit_do_not_make_the_export_inconclusive(tmp_path: Path):
    # covers: TQ-500g-3-ii
    # angle: failure
    # must_catch: a symlink entry pointing outside the checkout aborts the base export, so the check goes inconclusive
    # must_catch: a symlink entry inside the repo aborts the base export
    repo = ix.scenario(tmp_path, {})
    _commit_symlinks(repo)
    fx.write(repo.path(ix.REFRESH), ix.skip_a(fx.read(repo.path(ix.REFRESH))))
    fx.recorded(repo, [ix.listed(ix.REFRESH, ix.A)])
    proc, out = ix.run_check(repo)
    fx.assert_check_shape(proc, out)
    assert not any("could not be exported" in str(i["detail"]) for i in out["inconclusive"]), out["inconclusive"]
    assert out["inconclusive"] == [], f"the export must not fail on symlinks: {out['inconclusive']}"
    assert ix.whats(out) == {ix.A: "skipped"}, out
    assert out["passed"] is False and out["reason"] == "weakened", out


def _runs():
    """Import _cs_runs in-process (its siblings are bare imports)."""
    if str(fx.SCRIPTS) not in sys.path:
        sys.path.insert(0, str(fx.SCRIPTS))
    return importlib.import_module("_cs_runs")


_CHANGED = ("M", "unit_tests/test_c.py")
_BASE_PLUS = ["unit_tests/test_a.py", "unit_tests/sub/test_b.py", "tools/x/test_t.py", "unit_tests/test_c.py"]
_UNDER_ROOT = ["unit_tests/sub/test_b.py", "unit_tests/test_a.py", "unit_tests/test_c.py"]


@pytest.mark.parametrize("nested", ["docs/pyproject.toml", "tools/x/setup.cfg", "docs/deep/tox.ini"])
def test_m4_nested_unrelated_config_does_not_widen_the_scope(nested: str):
    # covers: TQ-500g-3-ii
    # angle: boundary
    # must_catch: any changed config file anywhere widens the runs to the whole test root
    runs = _runs()
    assert runs.scope_files([_CHANGED, ("M", nested)], _BASE_PLUS, "unit_tests") == ["unit_tests/test_c.py"], nested
    assert runs.scope_files([("M", nested)], _BASE_PLUS, "unit_tests") == [], nested


@pytest.mark.parametrize("config", ["pytest.ini", "pyproject.toml", "setup.cfg", "tox.ini"])
def test_m4_config_at_or_above_the_test_root_still_widens(config: str):
    # covers: TQ-500g-3-ii
    # angle: discrimination
    # must_catch: the nested-config fix drops the widening for a config that really governs the tests
    runs = _runs()
    assert runs.scope_files([_CHANGED, ("M", config)], _BASE_PLUS, "unit_tests") == _UNDER_ROOT, config
    assert runs.scope_files([("M", "unit_tests/" + config)], _BASE_PLUS, "unit_tests") == _UNDER_ROOT, config
