"""
MODULE: unit_tests/commit_guardian/test_tq500g1viii_hook_verdicts.py
GOAL: RED test for TQ-500g-1-viii, what the new pre-commit hook templates/scripts/commit_guardian/
    check_build_epic_gate_verdicts.py DECIDES for tickets B1 to B6 of the AC's criteria.
BUSINESS CONTEXT: The hook runs as a real subprocess in a real git repo (cwd = the repo, a real index with the
    ticket file and a code file staged, a real marker opened by the record module's own CLI) and reads the
    records the gate CLIs leave under <git-dir>/leafcutter/gate-verdicts/<ticket-key>/. Today the hook file is
    missing, so B1 (which must exit 0) fails on an assertion about the exit code, never on an import.
"""

from __future__ import annotations

import re
from pathlib import Path

import unit_tests.commit_guardian._tq500g1viii_fixtures as fx


def _case(tmp_path: Path, name: str, key: str):
    work = fx.make_repo(tmp_path / name, key)
    fx.open_marker(work, key)
    paths = fx.stage_work(work, key)
    return work, paths


def _records(work: Path, key: str) -> dict[str, bytes]:
    folder = fx.verdict_dir(work, key)
    return {p.name: p.read_bytes() for p in sorted(folder.iterdir()) if p.name != "open.json"}


def test_hook_verdicts_for_b1_to_b6(tmp_path: Path):
    # covers: TQ-500g-1-viii, TQ-500g-1-vii, TQ-500f-3-iv
    # angle: criterion
    # must_catch: missing wrong-version record treated as a pass
    # must_catch: truncated record read as an empty pass
    # must_catch: stop verdict ignored
    ac_id, rb_pass, rb_na = fx.real_red_baseline_verdicts()

    # B1: both verdicts on record and fresh -> the commit goes on. Asserted first so a hook that does not exist
    # (exit 2, "can't open file") cannot satisfy any of the blocking cases below by merely failing.
    work, paths = _case(tmp_path, "b1", "01_b1_ticket")
    fx.write_record(work, "01_b1_ticket", "red_baseline", rb_pass, ids=[ac_id])
    fx.write_record(work, "01_b1_ticket", "wrong_version", fx.wv_pass(), ids=[ac_id], paths=paths)
    proc, text = fx.run_hook(work)
    assert proc.returncode == 0, f"B1 (both verdicts on record, fresh) was blocked or the hook did not run: rc={proc.returncode} {text!r}"

    # B2: the red-baseline verdict is on record, the wrong-version one is not -> blocked, naming the missing one.
    work, paths = _case(tmp_path, "b2", "02_b2_ticket")
    fx.write_record(work, "02_b2_ticket", "red_baseline", rb_pass, ids=[ac_id])
    proc, text = fx.run_hook(work)
    assert proc.returncode != 0 and fx.names_reason(text, r"wrong[-_ ]?version", r"missing"), (
        f"B2 must be blocked naming the missing wrong-version verdict: rc={proc.returncode} {text!r}")
    assert not fx.names_reason(text, r"out of date"), f"B2 is missing, not stale: {text!r}"

    # B3: wrong-version verdict on record; the red-baseline record is present but cut off part way -> unreadable.
    work, paths = _case(tmp_path, "b3", "03_b3_ticket")
    fx.write_record(work, "03_b3_ticket", "red_baseline", rb_pass, ids=[ac_id], cut=True)
    fx.write_record(work, "03_b3_ticket", "wrong_version", fx.wv_pass(), ids=[ac_id], paths=paths)
    proc, text = fx.run_hook(work)
    assert proc.returncode != 0 and fx.names_reason(text, r"red[-_ ]?baseline", r"unreadable"), (
        f"B3 must be blocked naming the red-baseline verdict as unreadable: rc={proc.returncode} {text!r}")

    # B4: both on record, the wrong-version one is a stop; the staged ticket's own text says it is ready.
    work, paths = _case(tmp_path, "b4", "04_b4_ticket")
    assert "ready for commit" in (work / fx.ticket_rel("04_b4_ticket")).read_text(encoding="utf-8")
    fx.write_record(work, "04_b4_ticket", "red_baseline", rb_pass, ids=[ac_id])
    fx.write_record(work, "04_b4_ticket", "wrong_version", fx.wv_stop(), ids=[ac_id], paths=paths)
    proc, text = fx.run_hook(work)
    assert proc.returncode != 0 and fx.WRONG in text, (
        f"B4 must be blocked naming the surviving wrong version {fx.WRONG!r}: rc={proc.returncode} {text!r}")

    # B5: no source requirement, both verdicts read not-applicable -> goes on, and is never recorded as verified.
    work, paths = _case(tmp_path, "b5", "05_b5_ticket")
    fx.write_record(work, "05_b5_ticket", "red_baseline", rb_na)
    fx.write_record(work, "05_b5_ticket", "wrong_version", fx.wv_na(), paths={})  # staged code is not in `paths`: no staleness rule
    before = _records(work, "05_b5_ticket")
    proc, text = fx.run_hook(work)
    assert proc.returncode == 0, f"B5 (both not applicable) must go on to its commit: rc={proc.returncode} {text!r}"
    assert _records(work, "05_b5_ticket") == before, "the hook rewrote a record: it must only read them"
    assert rb_na["verified"] is False and fx.wv_na()["verified"] is False, "the not-applicable verdicts are never verified"
    assert not re.search(r"(?<!not )(?<!un)verified", text, re.IGNORECASE), f"B5 must not be reported as verified: {text!r}"

    # B6: both on record and applicable, but the staged code is not the code the runner ran against.
    work, paths = _case(tmp_path, "b6", "06_b6_ticket")
    fx.write_record(work, "06_b6_ticket", "red_baseline", rb_pass, ids=[ac_id])
    fx.write_record(work, "06_b6_ticket", "wrong_version", fx.wv_pass(), ids=[ac_id], paths=paths)
    fx.write_bytes(work / fx.CODE, fx.CODE_V2)
    fx.stage(work, fx.CODE)  # the coder's retry, after the runs
    proc, text = fx.run_hook(work)
    assert proc.returncode != 0 and fx.names_reason(text, r"wrong[-_ ]?version", r"out of date"), (
        f"B6 must be blocked naming the wrong-version verdict as out of date: rc={proc.returncode} {text!r}")
