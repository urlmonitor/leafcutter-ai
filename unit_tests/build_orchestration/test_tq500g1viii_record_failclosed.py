"""
MODULE: unit_tests/build_orchestration/test_tq500g1viii_record_failclosed.py
GOAL: RED test for TQ-500g-1-viii, the fail-closed edges of the record writing: a --record / --ticket-key value that
    is not one plain path segment is refused with nothing written (and nothing deleted), a record write that cannot
    complete turns the CLI's own result into gate_passed false, and a write cut short before the record is moved
    into place leaves no record at its name.
BUSINESS CONTEXT: The key becomes a folder name under <git-dir>/leafcutter/gate-verdicts/, and ``close`` removes
    files there, so an unchecked ``..`` or ``a/b`` writes or deletes outside the folder. Every run is a subprocess
    of the real CLI. Each refusal case is paired with a positive control (a valid key writes its record) so a CLI
    that merely does not exist cannot satisfy it. Today argparse rejects ``--record`` (exit 2, no JSON).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import unit_tests.build_orchestration._tq500f3i_fixtures as gitfx
import unit_tests.build_orchestration._tq500g1ix_fixtures as ix
import unit_tests.build_orchestration._tq500g1viii_fixtures as fx
import unit_tests.build_orchestration._tq500g1x_fixtures as x
import unit_tests.commit_guardian._tq500g1viii_fixtures as hk

BAD_KEYS = ("..", ".", "a/b", "x;y", "a\\b", "")
RECORD_FILES = {"open.json", "red_baseline.json", "wrong_version.json"}
GOOD_KEY = "01_ok_ticket"
CRASH = (
    "import os, pathlib, runpy, shutil, sys\n"
    "def boom(*a, **k):\n    raise OSError('simulated interruption before the record was moved into place')\n"
    "if os.environ.get('TQ_CRASH') == '1':\n"
    "    os.replace = os.rename = shutil.move = boom\n    pathlib.Path.replace = pathlib.Path.rename = boom\n"
    "script = sys.argv[1]\nsys.argv = sys.argv[1:]\nsys.path.insert(0, os.path.dirname(script))\n"
    "runpy.run_path(script, run_name='__main__')\n"
)


def _stray(work: Path) -> set[str]:
    """Every record-named file anywhere in the git dir, plus the top-level names under <git-dir>/leafcutter."""
    gd = hk.git_dir(work)
    found = {p.relative_to(gd).as_posix() for p in gd.rglob("*.json") if p.name in RECORD_FILES}
    top = gd / "leafcutter"
    return found | ({f"top:{p.name}" for p in top.iterdir()} if top.is_dir() else set())


def _text(proc) -> str:
    return proc.stdout + proc.stderr


def _opened(proc) -> bool:
    try:
        return json.loads(proc.stdout.strip()).get("opened") is True
    except (ValueError, AttributeError):
        return False


def _records(work: Path, args: list[str]) -> subprocess.CompletedProcess:
    return hk.run_py(hk.RECORDS, args, work, source_tree=False)


def _crash_heavy(work: Path, ac_root: Path, key: str, crash: bool):
    cmd = [sys.executable, "-c", CRASH, str(gitfx.GATE_SCRIPT), "heavy_lane_gate", "--test-root", str(work),
           "--ac-root", str(ac_root), "--record", key]
    env = hk.env(source_tree=False) | {"TQ_CRASH": "1" if crash else "0"}
    return subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=120, env=env)


def _gate_false(proc, who: str, out: dict, *, named: bool = True) -> None:
    assert proc.returncode != 0 and out.get("gate_passed") is False, f"{who}: must fail closed, gate_passed false: rc={proc.returncode} {out}"
    assert not named or re.search(r"(?i)record|ticket.?key", json.dumps(out) + _text(proc)), f"{who}: the failure must name the record or key: {out} {_text(proc)[-300:]!r}"


def test_record_key_and_write_fail_closed(tmp_path: Path):
    # covers: TQ-500g-1-viii
    # angle: failure
    # must_catch: ticket key used as a path without the one-segment check
    # must_catch: failed record write reported as a pass
    work, ac_root = fx.heavy_sandbox(tmp_path / "keys")
    sb = x.build(tmp_path / "x")
    manifest = x.full_manifest(sb)

    # Positive controls: a valid key opens a marker and every CLI writes its record (a missing CLI cannot pass below).
    hk.open_marker(work, GOOD_KEY)
    _, out = fx.heavy(work, ac_root, None, record=GOOD_KEY)
    assert out["gate_passed"] is True and fx.read_record(work, GOOD_KEY, "red_baseline") is not None, "control: heavy_lane_gate wrote no record"
    _, out = fx.finish(sb, "", ac_ids=None, record=GOOD_KEY)
    assert out["gate_passed"] is True and fx.read_record(sb.work, GOOD_KEY, "wrong_version") is not None, "control: finish wrote no record"
    _, out = fx.runner(sb, manifest, record="02_ok_run", ids=False)
    assert fx.read_record(sb.work, "02_ok_run", "wrong_version") is not None, "control: the runner wrote no record"
    sentinel = fx.gate_dir(work) / "sentinel.txt"
    sentinel.write_text("must survive a close with a bad key", encoding="utf-8")
    before, before_x = _stray(work), _stray(sb.work)

    for key in BAD_KEYS:
        where = f"key {key!r}"
        proc = _records(work, ["open", "--worktree", str(work), "--ticket-key", key, "--ticket-path", hk.ticket_rel(GOOD_KEY)])
        assert proc.returncode != 0 and not _opened(proc), f"{where}: open must refuse: {_text(proc)!r}"
        proc = _records(work, ["close", "--worktree", str(work), "--ticket-key", key])
        assert proc.returncode != 0, f"{where}: close must refuse a key that is not one plain segment: {_text(proc)!r}"
        proc, out = fx.heavy(work, ac_root, None, record=key)
        _gate_false(proc, f"heavy_lane_gate {where}", out)
        proc, out = fx.finish(sb, "", ac_ids=None, record=key)
        _gate_false(proc, f"finish {where}", out, named=False)  # finish's usual failure shape carries no reason text
        proc, out = fx.runner(sb, manifest, record=key, ids=False)
        _gate_false(proc, f"runner {where}", out)
        assert _stray(work) == before and _stray(sb.work) == before_x, f"{where}: a CLI wrote outside its own key folder: {_stray(work) ^ before}"
        assert sentinel.is_file() and (fx.gate_dir(work) / GOOD_KEY / "red_baseline.json").is_file(), f"{where}: close deleted outside its key folder"

    # A record write that cannot complete: <git-dir>/leafcutter/gate-verdicts is a FILE, so no folder can be made.
    blocked, ac2 = fx.heavy_sandbox(tmp_path / "blocked")
    (hk.git_dir(blocked) / "leafcutter").mkdir(parents=True, exist_ok=True)
    (hk.git_dir(blocked) / "leafcutter" / "gate-verdicts").write_text("not a folder", encoding="utf-8")
    proc, out = fx.heavy(blocked, ac2, None, record=GOOD_KEY)
    _gate_false(proc, "heavy_lane_gate with an unwritable record folder", out)
    sb2 = x.build(tmp_path / "x2")
    (hk.git_dir(sb2.work) / "leafcutter").mkdir(parents=True, exist_ok=True)
    (hk.git_dir(sb2.work) / "leafcutter" / "gate-verdicts").write_text("not a folder", encoding="utf-8")
    proc, out = fx.finish(sb2, "", ac_ids=None, record=GOOD_KEY)
    _gate_false(proc, "finish with an unwritable record folder", out)

    # A write cut short before the record is moved into place: nothing at the record's name, and the CLI fails closed.
    cut, ac3 = fx.heavy_sandbox(tmp_path / "cut")
    ok = _crash_heavy(cut, ac3, GOOD_KEY, crash=False)
    assert fx.read_record(cut, GOOD_KEY, "red_baseline") is not None, f"control: the wrapper run wrote no record: {_text(ok)[-300:]!r}"
    crashed = _crash_heavy(cut, ac3, "02_cut_ticket", crash=True)
    folder = fx.gate_dir(cut) / "02_cut_ticket"
    assert not (folder / "red_baseline.json").exists(), "an interrupted write left a record at its final name (the write is not temp-then-replace)"
    assert crashed.returncode != 0 and '"gate_passed": false' in crashed.stdout, f"a failed write must fail closed: rc={crashed.returncode} {crashed.stdout!r}"
    leftovers = [p for p in (folder.iterdir() if folder.is_dir() else [])]
    for p in leftovers:  # whatever is left must not be a record that parses as a different thing than a complete one
        try:
            body = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            continue
        assert set(body) >= {"gate", "ticket_key", "ids", "written_at", "verdict"}, f"{p.name}: a parseable but incomplete record was left behind: {body}"
    assert ix.parse_one_json(crashed, "heavy_lane_gate")["gate_passed"] is False
