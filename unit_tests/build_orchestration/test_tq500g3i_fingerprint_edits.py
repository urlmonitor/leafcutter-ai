"""
MODULE: unit_tests/build_orchestration/test_tq500g3i_fingerprint_edits.py
GOAL: RED tests for how consumer_sweep.py decides "listed" (TQ-500g-3-i): by a fingerprint the
    record step computes from the working tree, never by name, status or the writer's claim; and
    that a decorator-only edit is an edit.
BUSINESS CONTEXT: The two ways a per-name comparison would let an edit through (a stale entry, a
    forged fingerprint) and the one way a body-only comparison would (a decorator change).
"""

from __future__ import annotations

import json
from pathlib import Path

import unit_tests.build_orchestration._tq500g3i_fixtures as fx

_LATER = ("assert 4 - 1 == 3", "assert 4 - 1 == 3\n    assert 5 - 2 == 3")


def _edit_again(repo: fx.Repo) -> None:
    """The coder's later edit to test_retry_limit."""
    fx.write(repo.path(fx.RETRY), fx.read(repo.path(fx.RETRY)).replace(*_LATER))


def test_stale_or_unaffected_entry_does_not_excuse_edit(tmp_path: Path):
    # covers: TQ-500g-3-i
    # angle: boundary
    # must_catch: list membership checked by file and name only
    # must_catch: writer-supplied fingerprint trusted
    only = ("retry",)
    expect = {(fx.RETRY, "test_retry_limit")}
    # (a) stale: recorded, then the same test is edited again.
    stale = fx.build(tmp_path / "stale", edits=only)
    fx.recorded(stale, [fx.entry(fx.RETRY, "test_retry_limit")], fx.W2_KEY)
    _, fresh = fx.check(stale)
    assert fresh["passed"] is True, ("control: a fresh entry must excuse its edit", fresh)
    _edit_again(stale)
    proc, out = fx.check(stale)
    fx.assert_check_shape(proc, out)
    assert out["passed"] is False and out["reason"] == "unlisted", out
    assert fx.pairs(out["unlisted"]) == expect, out["unlisted"]
    # (b) an 'unaffected' entry never excuses an edit.
    unaffected = fx.build(tmp_path / "unaffected", edits=only)
    fx.recorded(unaffected, [fx.entry(fx.RETRY, "test_retry_limit", "unaffected", "not touched")], fx.W2_KEY)
    proc, out = fx.check(unaffected)
    fx.assert_check_shape(proc, out)
    assert out["passed"] is False and fx.pairs(out["unlisted"]) == expect, out
    # (c) a forged fingerprint in stdin is ignored: the record step computes its own.
    forged = fx.build(tmp_path / "forged", edits=only)
    fx.recorded(forged, [fx.entry(fx.RETRY, "test_retry_limit", fingerprint="0" * 64)], fx.W2_KEY)
    _edit_again(forged)
    proc, out = fx.check(forged)
    fx.assert_check_shape(proc, out)
    assert out["passed"] is False and fx.pairs(out["unlisted"]) == expect, out
    # (d) a future fingerprint offered in stdin is not stored: the record computes the CURRENT one.
    # The twin repo gets the final edit first; its recorded fingerprint is what the real file will hold.
    twin = fx.build(tmp_path / "twin", edits=only)
    _edit_again(twin)
    _, rec = fx.record(twin, [fx.entry(fx.RETRY, "test_retry_limit")], "twin-key")
    stored = json.loads(fx.read(Path(rec["path"])))["entries"]
    future = stored[0]["fingerprint"]
    assert len(future) == 64 and future != "absent", stored  # a real digest of the edited test
    early = fx.build(tmp_path / "early", edits=only)
    _, rec = fx.record(early, [fx.entry(fx.RETRY, "test_retry_limit", fingerprint=future)], fx.W2_KEY)
    kept = json.loads(fx.read(Path(rec["path"])))["entries"][0]["fingerprint"]
    assert kept != future, "the record must store the fingerprint of the content at record time"
    _edit_again(early)  # now the file holds exactly the content `future` was computed from
    proc, out = fx.check(early)
    fx.assert_check_shape(proc, out)
    assert out["passed"] is False and out["reason"] == "unlisted", out
    assert fx.pairs(out["unlisted"]) == expect, out["unlisted"]


def test_decorator_only_edit_is_an_edit(tmp_path: Path):
    # covers: TQ-500g-3-i
    # angle: boundary
    # must_catch: test source compared without its decorators
    skip = fx.build(tmp_path / "skip", edits=())
    src = fx.read(skip.path(fx.REFRESH)).replace("def test_refresh_on", "@pytest.mark.skip\ndef test_refresh_on")
    fx.write(skip.path(fx.REFRESH), "import pytest\n\n\n" + src)
    proc, out = fx.check(skip)
    fx.assert_check_shape(proc, out)
    assert out["passed"] is False, out
    found = fx.pairs(out["unlisted"])
    assert (fx.REFRESH, "test_refresh_on") in found, out["unlisted"]
    assert (fx.REFRESH, "test_refresh_off") not in found, out["unlisted"]  # control: undecorated, unchanged

    # Dropping one case from a parametrize list, body unchanged; the base already has the decorator.
    param = fx.build(tmp_path / "param", edits=())
    param_src = "import pytest\n\n\n@pytest.mark.parametrize('n', [1, 2, 3])\ndef test_param(n):\n    assert n > 0\n"
    fx.write(param.path(fx.RETRY), param_src)
    fx.gitfx.commit_all(param.root, "base with a parametrized test")
    fx.write(param.path(fx.RETRY), param_src.replace("[1, 2, 3]", "[1, 2]"))
    proc, out = fx.check(param)
    fx.assert_check_shape(proc, out)
    assert out["passed"] is False, out
    assert (fx.RETRY, "test_param") in fx.pairs(out["unlisted"]), out["unlisted"]
