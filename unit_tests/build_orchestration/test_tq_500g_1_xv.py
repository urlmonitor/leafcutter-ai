"""
MODULE: unit_tests/build_orchestration/test_tq_500g_1_xv.py
GOAL: RED tests for TQ-500g-1-xv: every verdict row names the exact alteration it judged (identity taken from
    the replacements alone) and where that alteration came from, and earlier manifests are kept under
    ``history/<NNNN>/`` so rounds can be compared; a run's verdict is read from its own manifest only.
BUSINESS CONTEXT: Every test drives the real gate CLI (``wrong_version_gate.py finish``) and, for the
    unreadable-reply and declared cases, the real runner CLI, in fresh subprocesses on the real git sandbox of
    the TQ-500g-1-xi family (``_tq500g1xi_fixtures``). The expected identity is recomputed in the fixtures from
    the spec, never through the module under test. Today rows carry no ``alteration_id``/``source``/
    ``replacements`` and the write step deletes the earlier manifest, so each test fails on an assertion.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

import unit_tests.build_orchestration._tq500g1_fixtures as fx
import unit_tests.build_orchestration._tq500g1ix_fixtures as ix
import unit_tests.build_orchestration._tq500g1v_gate_fixtures as g
import unit_tests.build_orchestration._tq500g1x_fixtures as x
import unit_tests.build_orchestration._tq500g1xi_fixtures as f

ROW_KEYS = {"test", "wrong_version", "result", "blocking", "detail", "alteration_id", "source", "replacements"}
RE_PREPARED_TARGET = "re-prepared: target changed"
EDITED = "if retry_due and refresh_due"  # run 3's code: the pinned old text is edited away
EDITED_AGAIN = "if (retry_due and refresh_due)"  # run 4's code: the run 3 text is edited away too


def _work_dir(sb) -> Path:
    return sb.git_dir / "leafcutter" / "work" / f.WK1


def _current_manifest_path(sb) -> Path:
    return _work_dir(sb) / "alterations.json"


def _history_manifest(sb, number: str) -> Path:
    return _work_dir(sb) / "history" / number / "alterations.json"


def _rows(out: dict, wrong_version: str) -> list[dict]:
    rows = [r for r in out["verdict"]["results"] if r["wrong_version"] == wrong_version]
    assert rows, f"no row for {wrong_version!r}: {out['verdict']['results']}"
    for r in rows:
        assert set(r) == ROW_KEYS, f"row keys are {sorted(r)}, expected {sorted(ROW_KEYS)}"
    return rows


def _run3_entries() -> list[dict]:
    """Run 3's reply: both names prepared again from the code as it now stands (colon form)."""
    return [ix.prep(f.N1, f.repl("if refresh_due:", EDITED + ":")),
            ix.prep(f.ALWAYS, f.repl("if True:", EDITED + ":"))]


def _three_runs(sb) -> tuple[list[dict], list[bytes]]:
    """Run 1 (prepared), a change elsewhere, run 2 (from the pin), run 3 (re-prepared); each passes.

    Returns the three gate outputs and the manifest bytes each run left at the current path.
    """
    outs, kept = [], []
    done1, out1 = f.finish(sb, f.first_entries(), f.WK1)
    assert done1.returncode == 0 and out1["gate_passed"] is True, out1
    outs.append(out1)
    kept.append(_current_manifest_path(sb).read_bytes())
    f.edit_source(sb, f.LOG_OLD, f.LOG_NEW)  # another line of refresh_config.py
    done2, out2 = f.finish(sb, None, f.WK1)
    assert done2.returncode == 0 and out2["gate_passed"] is True, out2
    outs.append(out2)
    kept.append(_current_manifest_path(sb).read_bytes())
    f.edit_source(sb, f.COND, EDITED)  # the pinned old text no longer matches
    done3, out3 = f.finish(sb, _run3_entries(), f.WK1)
    assert done3.returncode == 0 and out3["gate_passed"] is True, out3
    outs.append(out3)
    kept.append(_current_manifest_path(sb).read_bytes())
    return outs, kept


def test_identity_comes_from_the_replacements_alone():
    # covers: TQ-500g-1-xv
    # angle: discrimination
    with tempfile.TemporaryDirectory() as tmp:
        sb = f.build(Path(tmp))
        outs, _ = _three_runs(sb)
        run1, run2, run3 = (_rows(o, f.N1) for o in outs)
        r1 = f.repl_dicts(f.repl(f.COND_ALT))
        r3 = f.repl_dicts(f.repl("if refresh_due:", EDITED + ":"))
        for rows, want in ((run1, r1), (run2, r1), (run3, r3)):
            for r in rows:
                assert set(r) == ROW_KEYS, f"row keys are {sorted(r)}"
                assert r["replacements"] == want, r["replacements"]
                assert r["alteration_id"] == f.alteration_id(want), r["alteration_id"]
        assert run1[0]["replacements"][0]["path"] == f.REFRESH
        assert run1[0]["replacements"][0]["old"] == f.COND and run1[0]["replacements"][0]["new"] == f.COND_ALT
        # Run 2: the file changed elsewhere (the altered copy differs from run 1's), the replacement did not.
        assert run1[0]["alteration_id"] == run2[0]["alteration_id"], "identity followed the altered copy or the diff"
        assert run3[0]["alteration_id"] != run1[0]["alteration_id"], "identity ignored the replacement's text"
        always = [_rows(o, f.ALWAYS)[0]["alteration_id"] for o in outs]
        assert always[0] == always[1] != always[2], always
        assert always[0] != run1[0]["alteration_id"], "two different names carry one identity"


def test_each_row_says_where_its_alteration_came_from():
    # covers: TQ-500g-1-xv
    # angle: criterion
    with tempfile.TemporaryDirectory() as tmp:
        sb = f.build(Path(tmp))
        outs, _ = _three_runs(sb)
        for out, want in zip(outs, (f.NOT_PINNED, f.PINNED, RE_PREPARED_TARGET), strict=True):
            for name in (f.N1, f.ALWAYS):
                assert {r["source"] for r in _rows(out, name)} == {want}, (name, want, _rows(out, name))
        # The fix undone: judged on every run, from git against the base, never named.
        for out in outs:
            undone = _rows(out, fx.WV_UNDONE)
            for r in undone:
                assert r["source"] == "fix undone" and r["replacements"] is None, r
                assert isinstance(r["alteration_id"], str) and re.fullmatch(r"sha256:[0-9a-f]{16}", r["alteration_id"]), r
        # A declared replacement: the runner only copies the source the manifest entry carries.
        proc, verdict = _declared_run(sb)
        assert proc.returncode in (0, 1), proc.stderr[-300:]
        declared = _rows({"verdict": verdict}, f.N1)
        assert {r["source"] for r in declared} == {"declared"}, declared
        assert all(r["replacements"] == f.repl_dicts(_DECLARED) for r in declared), declared


# Against the code as _three_runs leaves it (run 3's text), not the original condition.
_DECLARED = f.repl("if refresh_due:", EDITED + ":")


def _declared_run(sb):
    """The runner CLI on a manifest whose N1 entry says it was declared on the requirement."""
    path = x.hand_manifest(sb, {f.N1: [_DECLARED]}, "declared.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    repls = f.repl_dicts(_DECLARED)
    data["entries"][0].update({"source": "declared", "replacements": repls, "alteration_id": f.alteration_id(repls)})
    path.write_text(json.dumps(data), encoding="utf-8")
    return x.run_runner(sb, path)


def test_every_runs_manifest_is_kept_under_its_own_run():
    # covers: TQ-500g-1-xv
    # angle: criterion
    with tempfile.TemporaryDirectory() as tmp:
        sb = f.build(Path(tmp))
        _, kept = _three_runs(sb)
        assert kept[0] != kept[1] != kept[2], "control: the three runs left different manifests"
        hist1, hist2, hist3 = (_history_manifest(sb, n) for n in ("0001", "0002", "0003"))
        assert hist1.is_file() and hist2.is_file(), "an earlier manifest was deleted, not kept"
        assert hist1.read_bytes() == kept[0], "history/0001 is not run 1's manifest byte for byte"
        assert hist2.read_bytes() == kept[1], "history/0002 is not run 2's manifest byte for byte"
        assert not hist3.exists(), "the current run's manifest was also put in history"
        assert _current_manifest_path(sb).read_bytes() == kept[2]
        assert (_work_dir(sb) / "history" / "0001" / "copies").is_dir(), "the copies of run 1 were not kept with it"
        assert sorted(p.name for p in (_work_dir(sb) / "history").iterdir()) == ["0001", "0002"]
        again, _ = f.finish(sb, None, f.WK1)  # a fourth run keeps all three, never rewriting an earlier folder
        assert again.returncode in (0, 1)
        assert hist1.read_bytes() == kept[0] and hist2.read_bytes() == kept[1], "a later run rewrote history"
        assert _history_manifest(sb, "0003").read_bytes() == kept[2]


def test_unreadable_reply_never_reads_an_earlier_manifest():
    # covers: TQ-500g-1-xv
    # angle: failure
    with tempfile.TemporaryDirectory() as tmp:
        sb = f.build(Path(tmp))
        _, kept = _three_runs(sb)
        f.edit_source(sb, EDITED + ":", EDITED_AGAIN + ":")  # no pin matches: the preparer must be asked
        cut = f.reply_text(f.first_entries(), f.WK1)[:40]
        proc, out = g.run_finish(sb, cut, work_key=f.WK1)
        g.assert_shape(proc, out)
        assert proc.returncode == 1 and out["gate_passed"] is False, out
        assert out["writer"]["written"] is False and out["verdict"] is None, "finish ran the runner after a failed write"
        assert not _current_manifest_path(sb).exists(), "an earlier manifest was left at the current path"
        assert _history_manifest(sb, "0003").is_file(), "run 3's manifest was not moved to history"
        assert _history_manifest(sb, "0003").read_bytes() == kept[2], "history/0003 is not run 3's manifest"
        # The runner, handed the now-absent current path, judges nothing from history.
        proc2, verdict = x.run_runner(sb, _current_manifest_path(sb))
        assert proc2.returncode == 1 and verdict["gate_passed"] is False, verdict
        owed = {u["wrong_version"] for u in verdict["unfinished"]}
        assert {f.N1, f.ALWAYS} <= owed, verdict["unfinished"]
        for r in verdict["results"]:
            if r["wrong_version"] in (f.N1, f.ALWAYS):
                assert r["result"] != "caught" and not r.get("alteration_id"), f"read an earlier manifest: {r}"
        assert sorted(p.name for p in (_work_dir(sb) / "history").iterdir()) == ["0001", "0002", "0003"]


def test_failed_move_never_leaves_the_earlier_manifest_at_the_current_path():
    # covers: TQ-500g-1-xv
    # angle: failure
    # Catches: 'the earlier manifest left at the current path after a failed move'. The copies folder of
    # run 1 cannot be moved (a directory without write permission cannot be renamed to a new parent), so
    # the move to history stops part-way. The manifest moves first, so it is already in history and the
    # current path is empty; the step stops with no new manifest.
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("root may rename a directory without write permission on it")
    with tempfile.TemporaryDirectory() as tmp:
        sb = f.build(Path(tmp))
        done1, out1 = f.finish(sb, f.first_entries(), f.WK1)
        assert done1.returncode == 0 and out1["gate_passed"] is True, out1
        run1 = _current_manifest_path(sb).read_bytes()
        copies = _work_dir(sb) / "copies"
        assert copies.is_dir(), "control: run 1 left its copies"
        copies.chmod(0o555)
        try:
            proc, out = g.run_finish(sb, "", work_key=f.WK1)
        finally:
            copies.chmod(0o755)
            stuck = _work_dir(sb) / "history" / "0001" / "copies"
            if stuck.is_dir():
                stuck.chmod(0o755)
        g.assert_shape(proc, out)
        assert out["writer"]["written"] is False and "could not be moved to history" in out["writer"]["error"], out["writer"]
        assert not _current_manifest_path(sb).exists(), "the earlier manifest was left at the current path"
        assert _history_manifest(sb, "0001").read_bytes() == run1, "run 1's manifest is not in history/0001"


def test_tq_500g_1_xv_reachable_from_entry_point():
    # covers: TQ-500g-1-xv
    # angle: reachability
    # surface_invoked: python scripts/build_orchestration/wrong_version_gate.py finish (CLI via subprocess)
    with tempfile.TemporaryDirectory() as tmp:
        sb = f.build(Path(tmp))
        for entries, want in ((f.first_entries(), f.NOT_PINNED), (None, f.PINNED)):
            cmd = [sys.executable, str(g.GATE), "finish", "--work-key", f.WK1, "--reply", "-", "--ac-ids", ix.AC_ID,
                   "--ac-root", str(sb.ac_root), "--test-root", str(sb.work), "--base-ref", sb.base_sha]
            text = "" if entries is None else f.reply_text(entries, f.WK1)
            raw = subprocess.run(cmd, cwd=sb.work, input=text.encode("utf-8"), capture_output=True, timeout=600, env=x.env())
            out = json.loads(raw.stdout.decode("utf-8").strip())
            assert raw.returncode == 0 and out["gate_passed"] is True, out
            rows = _rows(out, f.N1)
            assert {r["source"] for r in rows} == {want} and all(r["alteration_id"] for r in rows), rows
        assert _history_manifest(sb, "0001").is_file(), "the real gate CLI kept no earlier manifest"
