"""
MODULE: unit_tests/commit_guardian/test_tq500g1viii_hook_scope.py
GOAL: RED test for TQ-500g-1-viii, where the new hook applies: nowhere without an open marker (a commit outside
    /build-epic is unaffected and costs one git call), and always when one is open (a code commit that stages no
    marked ticket cannot be attributed, so it is refused and the message says to stage the ticket file, with no close command).
BUSINESS CONTEXT: Real subprocess runs of templates/scripts/commit_guardian/check_build_epic_gate_verdicts.py in a
    real git repo. Today the hook file is missing, so the first assertion (exit 0 with no marker) fails.
"""

from __future__ import annotations

import re
from pathlib import Path

import unit_tests.commit_guardian._tq500g1viii_fixtures as fx

TICKET_A, TICKET_B = "01_first_ticket", "02_second_ticket"


def test_commit_without_open_marker_is_unaffected(tmp_path: Path):
    # covers: TQ-500g-1-viii
    # angle: boundary
    # must_catch: hook applies to every commit and blocks non-/build-epic work
    # must_catch: unattributed commit passes while a marker is open
    ac_id, rb_pass, _ = fx.real_red_baseline_verdicts()

    # No marker: code and a ticket file staged, no record anywhere -> exit 0 after at most one git call.
    work = fx.make_repo(tmp_path / "plain", TICKET_A)
    fx.stage_work(work, TICKET_A)
    trace = tmp_path / "plain_trace.json"
    proc, text = fx.run_hook(work, trace=trace)
    assert proc.returncode == 0, f"a commit with no open marker was blocked or the hook did not run: rc={proc.returncode} {text!r}"
    assert len(fx.git_commands(trace)) <= 1, f"the no-marker path must cost at most one git call: {fx.git_commands(trace)}"
    assert not (fx.git_dir(work) / "leafcutter" / "gate-verdicts").exists(), "the hook created state in a worktree that has no marker"

    # A closed marker leaves its records behind; with no OPEN marker even a broken record must not matter.
    fx.write_record(work, TICKET_A, "red_baseline", rb_pass, ids=[ac_id], cut=True)
    proc, text = fx.run_hook(work)
    assert proc.returncode == 0, f"a record with no open marker must be ignored: rc={proc.returncode} {text!r}"

    # Marker open, only code staged (the marked ticket file is not): refused, naming the marker and the close command.
    work = fx.make_repo(tmp_path / "attrib", TICKET_A)
    fx.open_marker(work, TICKET_A)
    fx.write_bytes(work / fx.CODE, fx.CODE_V1)
    fx.stage(work, fx.CODE)
    proc, text = fx.run_hook(work)
    assert proc.returncode != 0, f"code staged under an open marker with no marked ticket must be refused: {text!r}"
    assert TICKET_A in text, f"the message must name the open marker {TICKET_A!r}: {text!r}"
    # must_catch: unattributed-commit message prints a runnable close command (H-2: running it would lift the block)
    assert "gate_verdict_records.py" not in text and not re.search(r"\bclose\b.*--ticket-key", text), f"no runnable close command: {text!r}"
    assert re.search(r"stage the ticket file", text, re.IGNORECASE), f"the message must tell the agent to stage the ticket file: {text!r}"

    # Two open markers: the message names every one of them.
    fx.write_bytes(work / fx.ticket_rel(TICKET_B), fx.TICKET_V0)
    fx.open_marker(work, TICKET_B)
    proc, text = fx.run_hook(work)
    assert proc.returncode != 0 and TICKET_A in text and TICKET_B in text, f"every open marker must be named: {text!r}"
