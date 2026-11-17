"""
MODULE: unit_tests/build_orchestration/test_tq500g3i_review_record.py
GOAL: Review-fix tests (M-1 .. M-5) for consumer_sweep.py: class shell vs first-method decorator,
    nested parametrize ids, record-time refusals, and the shared work-key rule.
BUSINESS CONTEXT: Real scratch git repos and the real CLIs.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import unit_tests.build_orchestration._tq500g3i_fixtures as fx
import unit_tests.build_orchestration._tq500g3i_review_fixtures as rfx


def test_m1_first_method_decorator_edit_reports_only_the_method(tmp_path: Path):
    # covers: TQ-500g-3-i
    # angle: boundary
    # must_catch: the class shell is cut at the first body statement's lineno, which skips its decorators
    base = ("import pytest\n\n\nclass TestK:\n    @pytest.mark.slow\n    def test_m(self):\n        assert 1\n\n"
            "    def test_n(self):\n        assert 2\n")
    repo = rfx.with_base(tmp_path, fx.REFRESH, base, base.replace("mark.slow", "mark.fast"))
    proc, out = fx.check(repo)
    fx.assert_check_shape(proc, out)
    assert fx.pairs(out["unlisted"]) == {(fx.REFRESH, "TestK::test_m")}, out["unlisted"]


def test_m2_nested_bracket_param_id_excuses_a_fresh_edit(tmp_path: Path):
    # covers: TQ-500g-3-i
    # angle: boundary
    # must_catch: the parametrize suffix is stripped with a pattern that stops at the first inner bracket
    repo = fx.build(tmp_path, edits=("refresh",), add_new_file=False)
    fx.recorded(repo, [fx.entry(fx.REFRESH, "test_refresh_on[a[0]]")], fx.W2_KEY)
    proc, out = fx.check(repo)
    fx.assert_check_shape(proc, out)
    assert out["passed"] is True and out["unlisted"] == [], out
    other = fx.build(tmp_path / "ctl", edits=("refresh",), add_new_file=False)  # control: no entry, still stops
    assert fx.check(other)[1]["passed"] is False


def _ok_list(**over) -> str:
    e = fx.entry(fx.REFRESH, "test_refresh_on")
    e.update(over)
    return json.dumps({"entries": [e]})


@pytest.mark.parametrize("key", ["k.", "k ", "CON", "nul", "Com1", "LPT1"])
def test_m3_bad_work_key_is_refused_and_writes_nothing(tmp_path: Path, key: str):
    # covers: TQ-500g-3-i
    # angle: failure
    # must_catch: work key checked only for separators, so a Windows-reserved name becomes a directory
    repo = fx.build(tmp_path, edits=("refresh",), add_new_file=False)
    proc, out = rfx.record_raw(repo, key, _ok_list())
    assert proc.returncode != 0 and out["recorded"] is False and out["error"], (key, out)
    assert rfx.work_dir_empty(repo), f"a refused key {key!r} must write nothing"
    ok, good = rfx.record_raw(repo, "work-ok", _ok_list())  # control: a plain key records
    assert ok.returncode == 0 and good["recorded"] is True, good


@pytest.mark.parametrize("field", ["note", "test"])
def test_m3_carriage_return_in_note_or_test_is_refused(tmp_path: Path, field: str):
    # covers: TQ-500g-3-i
    # angle: failure
    # must_catch: only a line feed is rejected in the one-line note and test name
    repo = fx.build(tmp_path, edits=("refresh",), add_new_file=False)
    value = "test_refresh_on\rx" if field == "test" else "two\rlines"
    proc, out = rfx.record_raw(repo, "work-cr", _ok_list(**{field: value}))
    assert proc.returncode != 0 and out["recorded"] is False, (field, out)
    assert rfx.work_dir_empty(repo)


@pytest.mark.parametrize("path", ["./tests/test_refresh.py", "tests//test_refresh.py"])
def test_m4_non_canonical_path_is_refused(tmp_path: Path, path: str):
    # covers: TQ-500g-3-i
    # angle: failure
    # must_catch: a spelling of the path that never equals the diff's path is stored and excuses nothing
    repo = fx.build(tmp_path, edits=("refresh",), add_new_file=False)
    proc, out = rfx.record_raw(repo, "work-path", _ok_list(file=path))
    assert proc.returncode != 0 and out["recorded"] is False and out["error"], (path, out)
    assert rfx.work_dir_empty(repo)
    ok, good = rfx.record_raw(repo, "work-path", _ok_list())  # control: the canonical spelling records
    assert ok.returncode == 0 and good["recorded"] is True, good


def test_m5_package_import_works_and_work_key_rule_is_shared(tmp_path: Path):
    # covers: TQ-500g-3-i
    # angle: seam
    # must_catch: consumer_sweep re-implements the work-key rule instead of using _wvw_write's
    code = ("import sys; sys.path.insert(0, 'scripts/build_orchestration')\n"
            "from scripts.build_orchestration.consumer_sweep import record, check, main\n"
            "import consumer_sweep, _wvw_write\n"
            "print(consumer_sweep._plain_segment is _wvw_write._plain_segment)\n")
    proc = subprocess.run([sys.executable, "-c", code], cwd=fx.ix.REPO_ROOT, capture_output=True, text=True,
                          timeout=120, encoding="utf-8")
    assert proc.returncode == 0, proc.stderr[-400:]
    assert proc.stdout.strip() == "True", proc.stdout
