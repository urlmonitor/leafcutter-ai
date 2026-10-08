"""
MODULE: unit_tests/build_orchestration/test_tq_500g_1_review_gate.py
GOAL: RED regression tests for the review findings on the wrong-version runner's put-back
    (TQ-500g-1-iii, plus the deleted-directory case of TQ-500g-1-i): a failed put-back that
    hides behind an unexpected exception, a journal that outlives its run, an unreadable
    file treated as absent, a lost file mode, a deleted directory, and stray temp files.
BUSINESS CONTEXT: The code must be put back exactly, and a run that cannot guarantee it must
    stop loudly. Each test goes red on an ASSERTION today; behaviour that raises today is
    caught (rv.attempt) and asserted on.
ARCHITECTURE: Real git sandboxes (see _tq500g1_review_fixtures.py). In-process where a
    private function or a monkeypatched failure is needed, the CLI where the finding is about
    the CLI contract.
"""

from __future__ import annotations

import io
import json
import os
import stat
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

import unit_tests.build_orchestration._tq500g1_fixtures as fx
import unit_tests.build_orchestration._tq500g1_review_fixtures as rv

SHAPE = {"gate_passed", "applicable", "verified", "outcome", "reason", "results", "survivors", "unfinished"}


def _one_wv_sandbox(root):
    return fx.build_sandbox(root, tests=("T1",), t1_must_catch=(fx.WV_DROP,), new_file_only=True)


def test_putback_failure_surfaces_when_run_raises_unexpected_error(tmp_path, monkeypatch):
    # covers: TQ-500g-1-iii
    # angle: failure
    # Catches: 'the put-back result is only checked after the try block, so an exception type
    # outside the except list (TypeError) skips the PutBackFailed check and run_runner raises
    # without saying the code may still be altered'.
    sb = _one_wv_sandbox(tmp_path)
    monkeypatch.chdir(sb.work)
    real, calls = rv.wvr.run_selected, []

    def flaky(nodes):
        calls.append(1)
        if len(calls) == 1:
            return real(nodes)
        os.remove(sb.target)
        os.mkdir(sb.target)  # the put-back cannot write over a directory
        msg = "boom mid-run"
        raise TypeError(msg)

    monkeypatch.setattr(rv.wvr, "run_selected", flaky)
    verdict, exc = rv.attempt(rv.inproc, sb)
    assert exc is None, f"run_runner raised {exc!r} instead of returning the verdict shape"
    assert set(verdict) == SHAPE and verdict["gate_passed"] is False
    text = rv.text_of(verdict)
    assert "may still be altered" in text, text
    assert fx.norm(str(sb.gate_dir)) in text, "the kept copy's path must be named"


def test_unexpected_exception_types_still_print_the_json_shape(tmp_path, monkeypatch):
    # covers: TQ-500g-1-iii
    # angle: failure
    # Catches: 'run_runner / main only catch GateError, OSError, ValueError, KeyError, RuntimeError',
    # so a TypeError or yaml.YAMLError ends in a traceback and no JSON for the build route.
    # Real inputs: an AC whose test_spec is not a list, and a manifest whose files is not a list.
    sb = fx.build_sandbox(tmp_path / "ac", tests=("T1",))
    fx.gitfx.write_ac_yaml(sb.ac_root, fx.AC_ID, 5)  # test_spec: 5 -- parseable, wrong shape
    proc, verdict = fx.run_runner(sb)
    assert set(verdict) == SHAPE and verdict["gate_passed"] is False and proc.returncode == 1
    sb2 = _one_wv_sandbox(tmp_path / "mf")
    sb2.manifest.write_text(json.dumps({"entries": [{"name": fx.WV_DROP, "status": "prepared", "files": 5}]}))
    proc2, verdict2 = fx.run_runner(sb2)
    assert set(verdict2) == SHAPE and verdict2["gate_passed"] is False and proc2.returncode == 1
    # In-process: other exception types out of scope loading, through main() with real argv.
    import yaml

    for error in (TypeError("x"), yaml.YAMLError("bad yaml")):
        def boom(*_a, _e=error, **_k):
            raise _e

        with monkeypatch.context() as m:
            m.setattr(rv.wvr, "resolve_scope", boom)
            monkeypatch.chdir(sb2.work)
            out, exc = io.StringIO(), None
            argv = ["run", "--ac-ids", fx.AC_ID, "--test-root", str(sb2.test_root), "--ac-root", str(sb2.ac_root)]
            with redirect_stdout(out):
                code, exc = rv.attempt(rv.wvr.main, argv)
            sys.stdout.flush()
        assert exc is None, f"{type(error).__name__} escaped main(): {exc!r}"
        assert code == 1


def _close_run_but_leave_files(monkeypatch, strip_copies: bool):
    def leave(path, *_a, **_k):
        if strip_copies:
            for p in Path(path).iterdir():
                if p.name != rv.gate_mod.JOURNAL_NAME:
                    p.unlink()
    monkeypatch.setattr(rv.gate_mod.shutil, "rmtree", leave)


def test_closed_run_with_left_over_journal_never_overwrites_developer_edit(tmp_path, monkeypatch):
    # covers: TQ-500g-1-iii
    # angle: discrimination
    # Catches: 'clear_run_dir swallows an rmtree failure (ignore_errors=True), so a CLOSED run keeps
    # a live journal; the next recover() "restores" the old as-written copy over the developer's
    # later edit of refresh_config.py'.
    sb = fx.build_sandbox(tmp_path, tests=("T1",), t1_must_catch=(fx.WV_DROP,))
    monkeypatch.chdir(sb.work)
    with monkeypatch.context() as m:
        _close_run_but_leave_files(m, strip_copies=False)
        verdict = rv.inproc(sb)
    assert verdict["gate_passed"] is True and sb.target.read_bytes() == sb.as_written
    edited = sb.as_written + b"# the developer edits this after the run\n"
    sb.target.write_bytes(edited)
    result = rv.wvr.recover(sb.work)
    assert sb.target.read_bytes() == edited, "recover overwrote the developer's edit with an old copy"
    assert result["restored"] == [], result


def test_closed_run_whose_copies_are_gone_does_not_block_forever(tmp_path, monkeypatch):
    # covers: TQ-500g-1-iii
    # angle: failure
    # Catches: 'a journal whose copies were deleted reports "has no readable copy" on every
    # invocation', so the runner stops permanently on a clean worktree.
    sb = fx.build_sandbox(tmp_path, tests=("T1",), t1_must_catch=(fx.WV_DROP,))
    monkeypatch.chdir(sb.work)
    with monkeypatch.context() as m:
        _close_run_but_leave_files(m, strip_copies=True)
        rv.inproc(sb)
    assert (sb.gate_dir).exists() and sb.target.read_bytes() == sb.as_written
    result = rv.wvr.recover(sb.work)
    assert result["ok"] is True, f"a closed/stale run must not be a failure: {result}"
    assert sb.target.read_bytes() == sb.as_written
    again = rv.wvr.recover(sb.work)
    assert again["ok"] is True, again


def test_unreadable_target_is_never_treated_as_absent(tmp_path, monkeypatch):
    # covers: TQ-500g-1-iii
    # angle: failure
    # Catches: '_read_or_none / _as_written map PermissionError to None (absent)': no copy is
    # taken, the file is altered, and the put-back then UNLINKS the developer's file.
    sb = _one_wv_sandbox(tmp_path)
    monkeypatch.chdir(sb.work)
    target, real = sb.target.resolve(), Path.read_bytes

    def deny(self):
        if self.name == "refresh_config.py" and self.resolve() == target:
            raise PermissionError(13, "denied")
        return real(self)

    with monkeypatch.context() as m:
        m.setattr(Path, "read_bytes", deny)
        verdict, exc = rv.attempt(rv.inproc, sb)
    after = rv.read_or_none(sb.target)
    assert after == sb.as_written, f"the file was altered or removed (now {after!r}); run raised {exc!r}"
    assert verdict is not None and verdict["gate_passed"] is False, verdict
    drop = fx.rows(verdict, fx.T1, fx.WV_DROP)
    assert [r["result"] for r in drop] in (["invalid"], ["not_run"]) and drop[0]["detail"], drop


@pytest.mark.skipif(sys.platform == "win32", reason="the executable bit / core.fileMode only exist on POSIX")
def test_putback_keeps_executable_mode(tmp_path):
    # covers: TQ-500g-1-iii
    # angle: real_artifact
    # Catches: 'atomic_write_bytes writes a fresh temp file (mode 0644) and replaces the target',
    # so an executable refresh_config.py loses its bit and git status shows a mode change.
    sb = fx.build_sandbox(tmp_path, tests=("T1",), t1_must_catch=(fx.WV_DROP,))
    rv.gitfx.run_git(["config", "core.fileMode", "true"], cwd=sb.work)
    os.chmod(sb.target, 0o755)
    rv.gitfx.commit_all(sb.work, "make executable")
    before = rv.status(sb.work)
    _proc, _verdict = fx.run_runner(sb)
    assert stat.S_IMODE(os.stat(sb.target).st_mode) == 0o755
    assert rv.status(sb.work) == before == ""


_PKG_TEST = '''\
from pathlib import Path
WORK = {work!r}


def test_pkg_is_gone():
    # covers: TQ-9101
    assert not Path(WORK, "pkg", "mod.py").exists()
'''


def test_fix_undone_can_recreate_a_deleted_directory_and_put_it_back(tmp_path):
    # covers: TQ-500g-1-i
    # angle: boundary
    # Catches: 'the fix undone cannot write pkg/mod.py because pkg/ no longer exists': the run
    # crashes to not_run instead of catching, or the put-back leaves pkg/ behind.
    sb = rv.plain_sandbox(
        tmp_path, base={"pkg/mod.py": "VALUE = 1\n"}, final={"pkg": None},
        tests={"test_pkg.py": _PKG_TEST.format(work=str(tmp_path / "work"))},
        must_catch={"test_pkg_is_gone": [fx.WV_ALIAS]})
    before = rv.status(sb.work)
    proc, verdict = fx.run_runner(sb)
    rows = fx.rows(verdict, "test_pkg_is_gone", fx.WV_UNDONE)
    assert [r["result"] for r in rows] == ["caught"], verdict["results"]
    assert not (sb.work / "pkg").exists(), "the directory is gone again after the put-back"
    assert rv.status(sb.work) == before and proc.returncode == 0


def test_stray_temp_file_from_a_hard_kill_is_swept(tmp_path, monkeypatch):
    # covers: TQ-500g-1-iii
    # angle: failure
    # Catches: 'a kill between open() and os.replace() leaves .refresh_config.py.wvr-tmp next to
    # the journaled path and nothing ever removes it', so git status shows an untracked file.
    # (A path a later put-back or run rewrites is swept by accident: they reuse the temp name.)
    sb = fx.build_sandbox(tmp_path, tests=("T1",), t1_must_catch=(fx.WV_DROP,))
    helper = sb.work / "helper_mod.py"  # a path no later run alters, so no run sweeps it by accident
    helper.write_bytes(b"VALUE = 1\n")
    rv.gitfx.commit_all(sb.work, "helper")
    monkeypatch.chdir(sb.work)
    gate = rv.gate_mod.RunGate(sb.work, sb.gate_dir / "killed-run")
    gate.apply(fx.WV_DROP, {"helper_mod.py": b"VALUE = 2\n"})
    helper.write_bytes(b"VALUE = 1\n")  # killed before the replace: the target is untouched
    stray = sb.work / ".helper_mod.py.wvr-tmp"
    stray.write_bytes(b"half written")
    rv.wvr.recover(sb.work)
    if stray.exists():  # either the recovery or the start of a run may sweep it
        rv.inproc(sb)
    assert helper.read_bytes() == b"VALUE = 1\n"
    assert not stray.exists(), "stray temp file survived recover / run"
    assert "wvr-tmp" not in rv.status(sb.work)
