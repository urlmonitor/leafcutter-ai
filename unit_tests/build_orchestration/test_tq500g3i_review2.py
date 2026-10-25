# covers: TQ-500g-3-i
"""
MODULE: unit_tests/build_orchestration/test_tq500g3i_review2.py
GOAL: Second-review fix tests for consumer_sweep.py / wrong_version_gate.py: M-1 non-.py test files
    compared as raw bytes, M-2 a list stays valid when HEAD advances by an unrelated commit, L-1 the
    gate must not leak PYTHONUTF8=1 into the writer / runner children.
BUSINESS CONTEXT: Real scratch git repos and the real CLIs; L-1 observes the env each child gets.
"""

from __future__ import annotations

import importlib
import json
import subprocess
from pathlib import Path

import unit_tests.build_orchestration._tq500g3i_fixtures as fx

BLOB = "tests/blob.bin"
_BIN_BASE, _BIN_NOW = b"\x00\xff\xfe\x01base", b"\x00\xff\xfe\x02work"


def _git(repo: fx.Repo, *args: str) -> str:
    return fx.gitfx.run_git(list(args), cwd=repo.root)


def _commit_doc(repo: fx.Repo, rel: str, message: str) -> None:
    """Commit only one new docs file, leaving the uncommitted test edit alone."""
    fx.write(repo.path(rel), "an unrelated doc\n")
    _git(repo, "add", rel)
    _git(repo, "commit", "-q", "-m", message)


def _blob_repo(tmp: Path, *, with_py_edit: bool = False) -> fx.Repo:
    """A repo whose base commit tracks tests/blob.bin (non-UTF-8 bytes); the work changes it."""
    repo = fx.build(tmp, edits=(), add_new_file=False)
    repo.path(BLOB).write_bytes(_BIN_BASE)
    fx.gitfx.commit_all(repo.root, "base with a binary test asset")
    repo.path(BLOB).write_bytes(_BIN_NOW)
    if with_py_edit:
        fx.edit(repo, "refresh")
    return repo


def test_m1_binary_test_file_without_any_list_stops_as_sweep_list_missing(tmp_path: Path):
    # covers: TQ-500g-3-i
    # angle: failure
    # must_catch: a non-.py file is decoded as UTF-8 and reported inconclusive instead of compared as raw bytes
    repo = _blob_repo(tmp_path)
    proc, out = fx.check(repo)
    fx.assert_check_shape(proc, out)
    assert out["passed"] is False and out["reason"] == "sweep list missing", out
    assert out["inconclusive"] == [], out["inconclusive"]
    assert fx.pairs(out["unlisted"]) == {(BLOB, "blob.bin")}, out["unlisted"]


def test_m1_binary_test_file_with_a_list_for_another_symbol_stops_as_unlisted(tmp_path: Path):
    # covers: TQ-500g-3-i
    # angle: discrimination
    # must_catch: any list at all excuses a changed binary asset
    repo = _blob_repo(tmp_path, with_py_edit=True)
    fx.recorded(repo, [fx.entry(fx.REFRESH, "test_refresh_on")], fx.W2_KEY)
    proc, out = fx.check(repo)
    fx.assert_check_shape(proc, out)
    assert out["passed"] is False and out["reason"] == "unlisted", out
    assert fx.pairs(out["unlisted"]) == {(BLOB, "blob.bin")}, out["unlisted"]
    assert out["inconclusive"] == [], out["inconclusive"]


def test_m1_recording_the_binary_entry_lets_the_check_pass(tmp_path: Path):
    # covers: TQ-500g-3-i
    # angle: criterion
    # must_catch: the binary entry is accepted at record time but never matches at check time
    repo = _blob_repo(tmp_path)
    fx.recorded(repo, [fx.entry(BLOB, "blob.bin")], fx.W2_KEY)
    proc, out = fx.check(repo)
    fx.assert_check_shape(proc, out)
    assert out["passed"] is True and out["unlisted"] == [] and out["inconclusive"] == [], out
    repo.path(BLOB).write_bytes(_BIN_NOW + b"more")  # control: a later byte change is a new, unlisted edit
    again = fx.check(repo)[1]
    assert again["passed"] is False and fx.pairs(again["unlisted"]) == {(BLOB, "blob.bin")}, again


def test_m1_python_test_files_that_cannot_be_read_stay_inconclusive(tmp_path: Path):
    # covers: TQ-500g-3-i
    # angle: boundary
    # must_catch: the raw-bytes fallback is widened to .py files and hides a file the check cannot parse
    bad_utf8 = fx.build(tmp_path / "u", edits=(), add_new_file=False)
    bad_utf8.path(fx.REFRESH).write_bytes(b"def test_refresh_on():\n    assert '\xff\xfe' == 1\n")
    out = fx.check(bad_utf8)[1]
    assert out["passed"] is False and out["reason"] == "inconclusive", out
    assert any(fx.REFRESH in str(i.get("file")) for i in out["inconclusive"]), out
    broken = fx.build(tmp_path / "s", edits=(), add_new_file=False)
    fx.write(broken.path(fx.REFRESH), "def test_refresh_on(:\n    assert 1\n")
    out2 = fx.check(broken)[1]
    assert out2["passed"] is False and out2["reason"] == "inconclusive", out2
    assert any(fx.REFRESH in str(i.get("file")) for i in out2["inconclusive"]), out2


def test_m2_list_survives_an_unrelated_commit_that_advances_head(tmp_path: Path):
    # covers: TQ-500g-3-i
    # angle: discrimination
    # must_catch: a list is honoured only when its recorded base equals the current base sha exactly
    repo = fx.build(tmp_path, edits=("refresh",), add_new_file=False)
    fx.recorded(repo, [fx.entry(fx.REFRESH, "test_refresh_on")], fx.W2_KEY)  # recorded against B
    assert fx.check(repo)[1]["passed"] is True, "control: the list excuses the edit at B"
    _commit_doc(repo, "docs/note.md", "unrelated docs commit (B+1)")  # the test edit stays uncommitted
    proc, out = fx.check(repo)  # --base-ref HEAD is now B+1
    fx.assert_check_shape(proc, out)
    assert out["passed"] is True and out["unlisted"] == [], ("list recorded at B ignored at B+1", out)
    fx.edit(repo, "retry")  # control: an edit the list does not name still stops
    again = fx.check(repo)[1]
    assert again["passed"] is False and (fx.RETRY, "test_retry_limit") in fx.pairs(again["unlisted"]), again


def test_m2_list_from_a_base_that_is_not_an_ancestor_is_ignored(tmp_path: Path):
    # covers: TQ-500g-3-i
    # angle: failure
    # must_catch: any recorded base is accepted, so a list from a side line excuses the main line's edit
    repo = fx.build(tmp_path, edits=("refresh",), add_new_file=False)
    _git(repo, "checkout", "-q", "-b", "side")  # the uncommitted edit comes along
    _commit_doc(repo, "docs/side.md", "side commit S")
    fx.recorded(repo, [fx.entry(fx.REFRESH, "test_refresh_on")], fx.W2_KEY)  # recorded against S
    _git(repo, "checkout", "-q", "main")
    _commit_doc(repo, "docs/main.md", "main commit M1 (S is not its ancestor)")
    proc, out = fx.check(repo)
    fx.assert_check_shape(proc, out)
    assert out["passed"] is False and (fx.REFRESH, "test_refresh_on") in fx.pairs(out["unlisted"]), out


def _fake_run(calls: list):
    """A subprocess.run stand-in that records (script, env) and answers each child with passing JSON."""
    answers = {"consumer_sweep.py": {"passed": True},
               "wrong_version_writer.py": {"written": True, "manifest_path": "m.json"},
               "wrong_version_runner.py": {"gate_passed": True}}

    def run(cmd, *_a, **kw):
        script = Path(cmd[1]).name
        calls.append((script, kw.get("env")))
        return subprocess.CompletedProcess(cmd, 0, json.dumps(answers[script]).encode("utf-8"), b"")

    return run


def test_l1_finish_does_not_inject_pythonutf8_into_writer_and_runner(tmp_path: Path, monkeypatch):
    # covers: TQ-500g-3-i
    # angle: discrimination
    # must_catch: _call builds every child env with PYTHONUTF8=1, so the writer and the runner run under it
    monkeypatch.syspath_prepend(str(fx.SCRIPTS))
    monkeypatch.delenv("PYTHONUTF8", raising=False)
    gate = importlib.import_module("wrong_version_gate")
    calls: list = []
    monkeypatch.setattr(gate.subprocess, "run", _fake_run(calls))
    args = gate._parser().parse_args(["finish", "--work-key", "w", "--reply", "-", "--ac-root", str(tmp_path),  # noqa: SLF001
                                      "--test-root", str(tmp_path)])
    assert gate.finish(args, b"")["gate_passed"] is True
    # TQ-500g-1-xi: the pin step (the writer again) runs after the runner.
    assert [s for s, _ in calls] == ["consumer_sweep.py", "wrong_version_writer.py", "wrong_version_runner.py",
                                     "wrong_version_writer.py"], calls
    for script, env in calls[1:]:
        assert env is None or env.get("PYTHONUTF8") != "1", f"{script} got PYTHONUTF8=1 injected by finish"
