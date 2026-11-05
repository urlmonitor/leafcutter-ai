"""
MODULE: unit_tests/build_orchestration/test_tq500g3i_unlisted_edits.py
GOAL: RED tests for scripts/build_orchestration/consumer_sweep.py check (TQ-500g-3-i): an edit to
    an existing test or fixture that no recorded sweep entry names stops the work; W2 is the control.
BUSINESS CONTEXT: Real temp git repos with a real base commit; lists go through the real record
    step. The module does not exist yet, so every run prints no JSON and the shared parse helper
    raises an AssertionError: red on an assertion, never on an import.
"""

from __future__ import annotations

from pathlib import Path

import unit_tests.build_orchestration._tq500g3i_fixtures as fx


def test_w1_unlisted_edit_stops_naming_file_and_tests(tmp_path: Path):
    # covers: TQ-500g-3-i
    # angle: criterion
    # must_catch: file-level comparison passes W1 because other files are listed
    # must_catch: writer's 'list complete' claim trusted
    repo = fx.build(tmp_path)
    # The stdin carries a completeness claim; the check must ignore it.
    fx.recorded(repo, [dict(e, complete=True) for e in fx.W1_LIST], fx.W1_KEY)
    proc, out = fx.check(repo)
    fx.assert_check_shape(proc, out)
    assert out["passed"] is False and out["reason"] == "unlisted", out
    assert fx.pairs(out["unlisted"]) == {
        (fx.EXPORT, "test_export_csv"), (fx.EXPORT, "test_export_json"), (fx.CONFTEST, fx.FIXTURE)}, out["unlisted"]
    # Exact set above: listed edits and the unchanged test_export_empty are not reported.
    assert out["applicable"] is True and out["error"] is None, out
    # Same file, two edited tests, only one listed (fresh): the other is still reported, by file and test.
    sib = fx.build(tmp_path / "sibling", edits=("export_csv", "export_json"))
    fx.recorded(sib, [fx.entry(fx.EXPORT, "test_export_csv")], fx.W1_KEY)
    proc, out = fx.check(sib)
    fx.assert_check_shape(proc, out)
    assert out["passed"] is False and out["reason"] == "unlisted", out
    assert fx.pairs(out["unlisted"]) == {(fx.EXPORT, "test_export_json")}, out["unlisted"]


def test_w2_complete_list_goes_on(tmp_path: Path):
    # covers: TQ-500g-3-i
    # angle: discrimination
    # must_catch: any edit to an existing test stops the work
    repo = fx.build(tmp_path / "w2")
    fx.recorded(repo, fx.W2_LIST, fx.W2_KEY)
    proc, out = fx.check(repo)
    fx.assert_check_shape(proc, out)
    assert out["passed"] is True and proc.returncode == 0, out
    assert out["applicable"] is True and out["unlisted"] == [], out
    # Control of the control: the same work with W1's list does stop (the pass is not vacuous).
    other = fx.build(tmp_path / "w1")
    fx.recorded(other, fx.W1_LIST, fx.W1_KEY)
    _, stopped = fx.check(other)
    assert stopped["passed"] is False and stopped["unlisted"], stopped


def test_new_test_file_not_treated_as_existing(tmp_path: Path):
    # covers: TQ-500g-3-i
    # angle: boundary
    # must_catch: new file treated as existing because it matches test_*.py
    w1 = fx.build(tmp_path / "w1")
    fx.recorded(w1, fx.W1_LIST, fx.W1_KEY)
    w2 = fx.build(tmp_path / "w2")
    fx.recorded(w2, fx.W2_LIST, fx.W2_KEY)
    for label, repo in (("W1", w1), ("W2", w2)):
        assert repo.path(fx.GATE_FILE).is_file(), "the new test file must be in the working tree"
        proc, out = fx.check(repo)
        fx.assert_check_shape(proc, out)
        assert all(item["file"] != fx.GATE_FILE for item in out["unlisted"]), (label, out["unlisted"])
    # Only the new file was added: nothing existing was edited, so no list is needed.
    only_new = fx.build(tmp_path / "only_new", edits=())
    proc, out = fx.check(only_new)
    fx.assert_check_shape(proc, out)
    assert out["passed"] is True and out["applicable"] is False and out["unlisted"] == [], out


def test_unlisted_fixture_edit_stops_naming_symbol(tmp_path: Path):
    # covers: TQ-500g-3-i
    # angle: boundary
    # must_catch: only test functions compared, fixtures and helpers ignored
    # must_catch: conftest.py excluded from the existing-test set
    repo = fx.build(tmp_path / "fixture", edits=("fixture",))
    proc, out = fx.check(repo)
    fx.assert_check_shape(proc, out)
    assert out["passed"] is False, out
    assert fx.pairs(out["unlisted"]) == {(fx.CONFTEST, fx.FIXTURE)}, out["unlisted"]
    # The same change recorded in the list passes.
    fx.recorded(repo, [fx.entry(fx.CONFTEST, fx.FIXTURE, note="fixture gained a limit key")], fx.W2_KEY)
    proc2, out2 = fx.check(repo)
    fx.assert_check_shape(proc2, out2)
    assert out2["passed"] is True and out2["unlisted"] == [], out2
    # A helper function and a pytestmark added to an existing test file behave the same.
    helper = fx.build(tmp_path / "helper", edits=())
    src = fx.read(helper.path(fx.REFRESH))
    fx.write(helper.path(fx.REFRESH),
             "import pytest\n\npytestmark = pytest.mark.slow\n\n\ndef _helper():\n    return 1\n\n\n" + src)
    proc3, out3 = fx.check(helper)
    fx.assert_check_shape(proc3, out3)
    assert out3["passed"] is False, out3
    symbols = {t for f, t in fx.pairs(out3["unlisted"]) if f == fx.REFRESH}
    assert {"pytestmark", "_helper"} <= symbols, out3["unlisted"]
