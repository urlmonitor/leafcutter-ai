"""
MODULE: unit_tests/build_orchestration/test_tq500g3i_review_robust.py
GOAL: Review-fix tests (H-3 .. H-6) for consumer_sweep.py check: an unreadable base is inconclusive,
    a list from an older finished work excuses nothing, locale and binary files do not leak into the
    verdict, and an unexpected exception still prints one JSON object.
BUSINESS CONTEXT: Real scratch git repos; in-process runs patch exactly one internal.
"""

from __future__ import annotations

from pathlib import Path

import unit_tests.build_orchestration._tq500g3i_fixtures as fx
import unit_tests.build_orchestration._tq500g3i_review_fixtures as rfx

_K_BASE = "def test_k():\n    assert 1 == 1\n\n\ndef test_keep():\n    assert 2 == 2\n"
_K_GONE = "def test_keep():\n    assert 2 == 2\n"
_K = "tests/test_k.py"


def test_h3_unreadable_base_of_modified_file_is_inconclusive(tmp_path: Path, monkeypatch, capsys):
    # covers: TQ-500g-3-i
    # angle: failure
    # must_catch: a base read that fails is treated as 'file is new' and the file is skipped
    sweep, edits_mod = rfx.load_sweep(monkeypatch)
    repo = fx.build(tmp_path, edits=("refresh",), add_new_file=False)
    monkeypatch.setattr(edits_mod, "_read_file_at_ref", lambda *_a, **_k: None)
    code, out = rfx.run_main(sweep, capsys, repo)
    assert code != 0 and out["passed"] is False and out["reason"] == "inconclusive", out
    assert any(fx.REFRESH in str(i.get("file")) or fx.REFRESH in str(i.get("detail")) for i in out["inconclusive"]), out


def test_h4_older_works_list_does_not_excuse_a_later_removal(tmp_path: Path):
    # covers: TQ-500g-3-i
    # angle: discrimination
    # must_catch: lists matched by (file, test, fingerprint) only, with no tie to the base they were recorded at
    repo = rfx.with_base(tmp_path, _K, _K_BASE, _K_GONE)  # W0 removes test_k at base B0
    fx.recorded(repo, [fx.entry(_K, "test_k", "removed", "dropped as obsolete")], "work-w0")
    _, w0 = fx.check(repo)
    assert w0["passed"] is True, ("control: W0's own list excuses its own removal", w0)
    fx.gitfx.commit_all(repo.root, "W0 finished")
    fx.write(repo.path(_K), _K_BASE)
    fx.gitfx.commit_all(repo.root, "B1 re-adds test_k")
    fx.write(repo.path(_K), _K_GONE)  # W1 removes it again, with no list of its own
    proc, out = fx.check(repo)
    fx.assert_check_shape(proc, out)
    assert out["passed"] is False and (_K, "test_k") in fx.pairs(out["unlisted"]), ("stale W0 list excused W1", out)
    # Q4 control: a sibling work's list recorded against THIS base still excuses the edit.
    fx.recorded(repo, [fx.entry(_K, "test_k", "removed", "dropped again")], "work-w2")
    proc2, out2 = fx.check(repo)
    assert out2["passed"] is True and out2["unlisted"] == [], out2


def test_h5_non_utf8_locale_reports_only_the_changed_listed_test(tmp_path: Path):
    # covers: TQ-500g-3-i
    # angle: boundary
    # must_catch: text decoding with the locale encoding mangles a non-ASCII test and reports it as changed
    base = "def test_cafe():\n    assert 'é' == 'é'\n\n\ndef test_plain():\n    assert 1 == 1\n"
    repo = rfx.with_base(tmp_path, fx.REFRESH, base, base.replace("assert 1 == 1", "assert 2 == 2"))
    fx.recorded(repo, [fx.entry(fx.REFRESH, "test_plain")], fx.W2_KEY)
    proc, out = rfx.run_cli(repo, rfx.check_args(repo), env_extra={"PYTHONUTF8": "0", "PYTHONIOENCODING": "cp1252"})
    fx.assert_check_shape(proc, out)
    assert out["passed"] is True and out["unlisted"] == [] and out["inconclusive"] == [], out
    assert out["applicable"] is True, "control: test_plain did change, so the check applied"


def test_h5_unchanged_binary_fixture_causes_no_inconclusive(tmp_path: Path):
    # covers: TQ-500g-3-i
    # angle: boundary
    # must_catch: every file under tests/ is decoded as text, so a binary fixture is inconclusive
    repo = fx.build(tmp_path, edits=(), add_new_file=False)
    (repo.root / "tests" / "data.bin").write_bytes(bytes([0xFF, 0xFE, 0x00, 0x81, 0x8F, 0x90]))
    fx.gitfx.commit_all(repo.root, "binary fixture joins the base")
    fx.edit(repo, "retry")
    fx.recorded(repo, [fx.entry(fx.RETRY, "test_retry_limit")], fx.W2_KEY)
    proc, out = rfx.run_cli(repo, rfx.check_args(repo), env_extra={"PYTHONUTF8": "0"})
    fx.assert_check_shape(proc, out)
    assert out["passed"] is True and out["inconclusive"] == [], out


def test_h6_unexpected_exception_prints_one_json_object(tmp_path: Path, monkeypatch, capsys):
    # covers: TQ-500g-3-i
    # angle: failure
    # must_catch: only OSError / ValueError caught in main, a RuntimeError escapes as a traceback
    sweep, edits_mod = rfx.load_sweep(monkeypatch)
    repo = fx.build(tmp_path, edits=("refresh",), add_new_file=False)

    def boom(*_a, **_k):
        raise RuntimeError("boom")

    monkeypatch.setattr(edits_mod, "compare_file", boom)
    code, out = rfx.run_main(sweep, capsys, repo)
    assert code != 0 and out["passed"] is False, out
    assert out["error"] and "boom" in str(out["error"]), out
