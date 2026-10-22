"""
MODULE: unit_tests/build_orchestration/test_tq500g3ii_scope.py
GOAL: Tests for TQ-500g-3-ii scope: which unchanged test files the base-vs-now runs also cover (a changed
    conftest.py or pytest.ini widens the scope) and that a helpers-only test file is no inconclusive run.
BUSINESS CONTEXT: Real scratch git repos, real pytest on both sides, the real consumer_sweep.py CLIs.
"""

from __future__ import annotations

from pathlib import Path

import unit_tests.build_orchestration._tq500g3i_fixtures as fx
import unit_tests.build_orchestration._tq500g3ii_fixtures as ix

SUB = "tests/sub/test_inner.py"
SUB_CONF = "tests/sub/conftest.py"
INNER = "test_inner_ok"
GATE = "gate"
HELPERS = "tests/test_helpers.py"
CONF_OK = "import pytest\n\n\n@pytest.fixture(autouse=True)\ndef gate():\n    yield\n"
CONF_SKIP = "import pytest\n\n\n@pytest.fixture(autouse=True)\ndef gate():\n    pytest.skip('gated off')\n"
INI = "pytest.ini"


def write_ini(repo: fx.Repo, text: str) -> None:
    """A new pytest.ini in the work, staged like the work's other new files."""
    fx.write(repo.path(INI), text)
    fx.gitfx.run_git(["add", INI], cwd=repo.root)


def test_conftest_edit_widens_scope_to_unchanged_test_in_its_folder(tmp_path: Path):
    # covers: TQ-500g-3-ii
    # angle: discrimination
    # must_catch: only the changed test files are run, so a conftest edit that skips an unchanged test is missed
    base = {**ix.BASE, SUB_CONF: CONF_OK, SUB: ix.HEAD + f"def {INNER}():\n    assert 3 == 3\n"}
    work = {SUB_CONF: lambda _t: CONF_SKIP}
    repo = ix.scenario(tmp_path, work, base=base)
    fx.recorded(repo, [ix.listed(SUB_CONF, GATE)])
    proc, out = ix.run_check(repo)
    fx.assert_check_shape(proc, out)
    assert out["unlisted"] == [] and out["inconclusive"] == [], out
    # SUB is unchanged and sits under the conftest's folder: reported. The other base tests (outside the
    # folder, same suite, passing before and now) are the control: not reported.
    assert ix.whats(out) == {INNER: "skipped"}, out["weakened"]
    assert fx.pairs(out["weakened"]) == {(SUB, INNER)}, out["weakened"]
    assert out["passed"] is False and out["reason"] == "weakened" and proc.returncode == 1, (proc.returncode, out)


def test_config_edit_widens_scope_and_benign_config_edit_does_not_report(tmp_path: Path):
    # covers: TQ-500g-3-ii
    # angle: discrimination
    # must_catch: a changed pytest.ini is not a reason to run the unchanged test files
    # must_catch: any config change is reported as weakened
    # (1) addopts "-m slow" deselects every unmarked test: the unchanged tests are gone now.
    bad = ix.scenario(tmp_path / "bad", {})
    write_ini(bad, "[pytest]\naddopts = -m slow\nmarkers =\n    slow: slow tests\n")
    proc, out = ix.run_check(bad)
    fx.assert_check_shape(proc, out)
    assert out["unlisted"] == [], out["unlisted"]
    assert ix.whats(out) == {ix.A: "removed", ix.D: "removed", ix.B: "removed", ix.C: "removed",
                             "test_export_body": "removed", ix.E: "removed", "test_legacy_noop": "removed"}, out
    assert out["passed"] is False and out["reason"] == "weakened" and proc.returncode == 1, (proc.returncode, out)
    # (2) control: a benign config change keeps every test passing, so the same scope finds nothing.
    ok = ix.scenario(tmp_path / "ok", {})
    write_ini(ok, "[pytest]\nmarkers =\n    slow: slow tests\n")
    proc, out = ix.run_check(ok)
    fx.assert_check_shape(proc, out)
    assert out["applicable"] is True and out["passed"] is True, out
    assert out["weakened"] == [] and out["inconclusive"] == [] and out["removed"] == [], out


def test_helpers_only_test_file_is_not_inconclusive(tmp_path: Path):
    # covers: TQ-500g-3-ii
    # angle: boundary
    # must_catch: pytest exit 5 (nothing collected) on both sides read as a run that did not finish
    helpers = "import pytest\n\n\n@pytest.fixture\ndef helper_value():\n    return 1\n"
    repo = ix.scenario(tmp_path, {HELPERS: lambda t: ix.sub(t, "return 1", "return 2")}, base={HELPERS: helpers})
    fx.recorded(repo, [ix.listed(HELPERS, "helper_value")])
    proc, out = ix.run_check(repo)
    fx.assert_check_shape(proc, out)
    assert out["inconclusive"] == [] and out["weakened"] == [] and out["unlisted"] == [], out
    assert out["applicable"] is True and out["passed"] is True and proc.returncode == 0, (proc.returncode, out)
