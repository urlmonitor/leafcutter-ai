"""
MODULE: unit_tests/build_orchestration/test_tq500g1viii_records_cli.py
GOAL: RED test for TQ-500g-1-viii, the seam between the gate CLIs that WRITE the records (``heavy_lane_gate``, the
    runner's run step, the finish wrapper, each with ``--record <ticket-key>``) and the hook that READS them.
BUSINESS CONTEXT: The hook is only as good as the records it is fed, and they must come from the CLIs themselves,
    never from the supervisor. Everything here runs as subprocesses on real sandboxes. The records the CLIs wrote
    are piped into the real hook (B1, B5 accepted; a real stop, and the same stop rewritten to read 'passed',
    blocked). Today argparse rejects ``--record`` (exit 2, no JSON), so the first run fails an assertion.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from types import SimpleNamespace

import unit_tests.build_orchestration._tq500g1ix_fixtures as ix
import unit_tests.build_orchestration._tq500g1v_gate_fixtures as g
import unit_tests.build_orchestration._tq500g1viii_fixtures as fx
import unit_tests.build_orchestration._tq500g1x_fixtures as x
import unit_tests.commit_guardian._tq500g1viii_fixtures as hk

HL_KEY, NA_KEY, PASS_KEY, STOP_KEY, STOPPED_KEY, DIRECT_KEY, PAIR_KEY = (
    "01_hl_ticket", "02_na_ticket", "07_seam_ticket", "08_survivor_ticket", "09_stopped_ticket", "10_direct_ticket", "11_pair_ticket")
UNVERIFIED = re.compile(r"(?<!not )(?<!un)verified", re.IGNORECASE)
ISO_UTC = re.compile(r"\d{4}-\d\d-\d\dT[\d:.]+(Z|\+00:00)")


def _hook_after(work: Path, key: str, *stage: str):
    """Open the marker with the module's own CLI, stage the ticket file plus *stage*, run the real hook, then undo."""
    hk.open_marker(work, key)
    hk.write_bytes(work / hk.ticket_rel(key), hk.TICKET_V1)
    hk.stage(work, hk.ticket_rel(key), *stage)
    try:
        return hk.run_hook(work)
    finally:
        (fx.gate_dir(work) / key / "open.json").unlink(missing_ok=True)  # the pinned marker file; records stay
        hk.git(["reset", "-q"], work)


def _sha(work: Path, rel: str) -> str:
    return hashlib.sha256((work / rel).read_bytes()).hexdigest()


def _heavy_records(work: Path, ac_root: Path) -> None:
    """heavy_lane_gate, with and without ids: the record's verdict is the CLI's own JSON verbatim."""
    _, plain = fx.heavy(work, ac_root, fx.HL_AC)  # what it printed before --record existed
    assert fx.listing(work) == set(), "without --record nothing is written under gate-verdicts"
    proc, printed = fx.heavy(work, ac_root, fx.HL_AC, record=HL_KEY)
    rec = fx.read_record(work, HL_KEY, "red_baseline")
    assert rec is not None, f"--record was ignored: no red_baseline.json after the run (rc={proc.returncode})"
    assert (rec["gate"], rec["ticket_key"], rec["ids"]) == ("red_baseline", HL_KEY, [fx.HL_AC]), rec
    assert ISO_UTC.fullmatch(rec["written_at"]), rec["written_at"]
    assert rec["verdict"] == plain, "the record's verdict must be the CLI's own JSON verbatim"
    assert {k: printed[k] for k in plain} == plain, "with --record the CLI prints the same JSON as without it"
    fx.heavy(work, ac_root, None, record=NA_KEY)
    rec_na = fx.read_record(work, NA_KEY, "red_baseline")
    assert rec_na is not None and rec_na["ids"] == [] and rec_na["verdict"]["applicable"] is False, rec_na
    assert rec_na["verdict"]["outcome"] == fx.RB_NA and rec_na["verdict"]["verified"] is False, "not-applicable is recorded, never as verified"
    both = {f"{HL_KEY}/red_baseline.json", f"{NA_KEY}/red_baseline.json"}
    assert fx.listing(work) == both, fx.listing(work)
    fx.heavy(work, ac_root, fx.HL_AC)
    assert fx.listing(work) == both, "a run without --record wrote a record"


def _runner_record(tmp_path: Path, work: Path, ac_root: Path) -> None:
    """The runner's run step: its record is its own printed verdict (ids absent: not applicable); the hook accepts it (B1)."""
    manifest = tmp_path / "empty_manifest.json"
    manifest.write_text(json.dumps({"work_key": ix.WORK_KEY, "entries": []}), encoding="utf-8")
    hl_sb = SimpleNamespace(work=work, ac_root=ac_root, base_sha="HEAD")
    _, direct = fx.runner(hl_sb, manifest, record=HL_KEY, ids=False)
    rec_run = fx.read_record(work, HL_KEY, "wrong_version")
    assert rec_run is not None and rec_run["verdict"] == direct and direct["applicable"] is False, rec_run
    assert rec_run["verdict"]["outcome"] == g.NO_SOURCE_OUTCOME and rec_run["ids"] == [], "no source requirement: recorded as not applicable"
    proc, text = _hook_after(work, HL_KEY)  # applicable + verified red baseline, not-applicable runs
    assert proc.returncode == 0, f"the hook refused the records the CLIs wrote for the heavy-lane ticket: rc={proc.returncode} {text!r}"


def _finish_record(sb) -> None:
    """finish passes --record to the runner: the record is the runner's own, over the code as it stood."""
    proc, out = fx.finish(sb, g.reply_text(), record=PASS_KEY)
    g.assert_shape(proc, out)
    assert out["gate_passed"] is True and out["stopped_at"] is None, out
    rec = fx.read_record(sb.work, PASS_KEY, "wrong_version")
    assert rec is not None, "finish dropped --record: the runner wrote no wrong_version.json"
    assert (rec["gate"], rec["ticket_key"], rec["ids"], rec["base_ref"]) == ("wrong_version", PASS_KEY, [ix.AC_ID], sb.base_sha), rec
    assert rec["verdict"] == out["verdict"], "the record finish leaves must be the runner's own verdict (finish's verdict field)"
    for rel in ("refresh_config.py", "retry_policy.py", x.TEST_FILE):
        assert rec["paths"].get(rel) == _sha(sb.work, rel), f"paths[{rel}]: {rec['paths']}"
    assert rec["paths"].get("legacy_refresh.py", "absent") is None, "a path deleted since the base ref is recorded as null"
    assert re.fullmatch(r"[0-9a-f]{64}", rec["code_digest"]), rec["code_digest"]


def _hook_accepts(sb) -> None:
    """The hook accepts what the CLIs wrote for the staged code (B1), and a not-applicable pair (B5)."""
    fx.heavy(sb.work, sb.ac_root, None, record=PASS_KEY)
    proc, text = _hook_after(sb.work, PASS_KEY, x.TEST_FILE, "retry_policy.py")
    assert proc.returncode == 0, f"the hook refused records the CLIs wrote for the staged code: rc={proc.returncode} {text!r}"
    fx.heavy(sb.work, sb.ac_root, None, record=PAIR_KEY)
    fx.finish(sb, "", ac_ids=None, record=PAIR_KEY)
    proc, text = _hook_after(sb.work, PAIR_KEY, x.TEST_FILE)
    assert proc.returncode == 0 and not UNVERIFIED.search(text), f"B5 from real records must go on, never as verified: rc={proc.returncode} {text!r}"


def _stop_blocks(sb) -> None:
    """A real stop blocks, and so does the same record rewritten to read 'passed'."""
    proc, out = fx.finish(sb, fx.survivor_reply(), record=STOP_KEY)
    assert out["gate_passed"] is False and out["stopped_at"] is None and out["verdict"]["survivors"], out
    stop = fx.read_record(sb.work, STOP_KEY, "wrong_version")
    assert stop is not None and stop["verdict"] == out["verdict"], "a stop is recorded too, on every outcome"
    fx.heavy(sb.work, sb.ac_root, None, record=STOP_KEY)
    proc, text = _hook_after(sb.work, STOP_KEY, x.TEST_FILE, "retry_policy.py")
    assert proc.returncode != 0 and x.N1 in text, f"a recorded stop must block, naming the survivor: rc={proc.returncode} {text!r}"
    stop["verdict"].update(gate_passed=True, reason=None, outcome="wrong-version runs passed: every wrong version was caught")
    (fx.gate_dir(sb.work) / STOP_KEY / "wrong_version.json").write_text(json.dumps(stop), encoding="utf-8")
    proc, text = _hook_after(sb.work, STOP_KEY, x.TEST_FILE, "retry_policy.py")
    assert proc.returncode != 0, f"a stop rewritten to read 'passed' (rows still show the survivor) must still block: {text!r}"


def _writer_stop_leaves_no_record(sb) -> None:
    """A writer stop leaves NO wrong-version record: not a stale one, not a new one."""
    assert fx.read_record(sb.work, PASS_KEY, "wrong_version") is not None
    proc, out = fx.finish(sb, "", record=PASS_KEY)
    assert out["stopped_at"] == "write" and out["gate_passed"] is False, out
    assert fx.read_record(sb.work, PASS_KEY, "wrong_version") is None, "the record of the earlier passing finish survived a writer stop"
    proc, out = fx.finish(sb, "", record=STOPPED_KEY)
    assert out["stopped_at"] == "write" and fx.read_record(sb.work, STOPPED_KEY, "wrong_version") is None, "finish wrote a record after the writer stopped"


def _no_record_changes_nothing(sb) -> None:
    """Without --record the finish step prints the same JSON as with it, and writes nothing."""
    before = fx.listing(sb.work)
    _, plain_na = fx.finish(sb, "", ac_ids=None)
    assert fx.listing(sb.work) == before, "a finish without --record wrote a record"
    _, recorded_na = fx.finish(sb, "", ac_ids=None, record=DIRECT_KEY)
    assert plain_na == recorded_na, "--record changed what finish prints"
    assert fx.listing(sb.work) - before == {f"{DIRECT_KEY}/wrong_version.json"}, "only the recorded run may write a record"


def test_records_written_by_gate_clis_themselves(tmp_path: Path):
    # covers: TQ-500g-1-viii, TQ-500g-1-vii, TQ-500f-3-iv
    # angle: seam
    # must_catch: record option ignored, so the CLI writes no record
    # must_catch: finish drops the record option instead of passing it to the runner
    # must_catch: finish writes a record after the writer stopped
    # must_catch: stale record from an earlier finish survives a writer stop
    work, ac_root = fx.heavy_sandbox(tmp_path / "hl")
    _heavy_records(work, ac_root)
    _runner_record(tmp_path, work, ac_root)
    sb = x.build(tmp_path / "x")
    _finish_record(sb)
    _hook_accepts(sb)
    _stop_blocks(sb)
    _writer_stop_leaves_no_record(sb)
    _no_record_changes_nothing(sb)
