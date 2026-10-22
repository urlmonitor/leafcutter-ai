"""
MODULE: unit_tests/workflows/test_tq500g1viii_epic_drive_head.py
GOAL: RED test for TQ-500g-1-viii, the drive head of templates/workflows-js/build-epic.js: the wrong-version
    runner's recover step (``be-wv-recover``) runs ONCE per drive, before the epic planner and never per ticket,
    and fails closed: no unusable reply lets a ticket-supervisor be dispatched.
BUSINESS CONTEXT: Recover closes EVERY open journal in the worktree, so a per-ticket recover inside a parallel
    chunk would put back a sibling's in-flight alteration. The TEMPLATE runs under unit_tests/_workflow_engine_harness.py
    (concurrent parallel(), as the real engine); assertions are on the recorded dispatches and the terminal payload.
    Today build-epic.js dispatches no command step, so the first assertion about the recorded dispatches fails.
"""

from __future__ import annotations

import sys
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

import workflows._tq500g1v_fixtures as v  # noqa: E402
import workflows._tq500g1viii_fixtures as fx  # noqa: E402


def test_build_epic_recovers_once_at_drive_head_and_fails_closed():
    # covers: TQ-500g-1-viii
    # angle: failure
    # must_catch: recover ok false ignored
    # must_catch: recover dispatched per ticket instead of once at the drive head
    two_batches = [[fx.ticket(1, []), fx.ticket(2, [])], [fx.ticket(3, [])]]
    result = fx.run_epic(two_batches)
    labels = fx.labels_of(result)
    recovers = fx.calls(result, fx.RECOVER)
    assert len(recovers) == 1, f"recover must run once per drive, however many batches and tickets: {labels}"
    # The workspace guard (workspace-*) runs first by design; recover is the first step after it.
    after_guard = [x for x in labels if not x.startswith("workspace-")]
    assert after_guard[0] == fx.RECOVER, f"recover must be the first dispatch after the workspace guard: {labels}"
    assert labels.index(fx.RECOVER) < labels.index(fx.PLANNER), f"recover must run before the epic planner: {labels}"
    assert recovers[0].agent_type == fx.EXECUTOR, f"recover goes to command-step-runner, not status-checker: {recovers[0].agent_type}"
    assert fx.command_of(recovers[0]) == fx.recover_command(), f"recover command: {fx.command_of(recovers[0])!r}"
    request = fx.request_of(recovers[0])
    assert request == {"step": fx.RECOVER, "command": fx.recover_command(), "target": {"workspace": fx.WT, "run_id": "drive-head"}}, request
    closes = fx.calls(result, fx.CLOSE_ALL)
    assert len(closes) == 1 and fx.command_of(closes[0]) == fx.close_all_command(), f"stale-marker close: {labels}"
    assert labels.index(fx.RECOVER) < labels.index(fx.CLOSE_ALL) < labels.index(fx.PLANNER), f"drive-head order: {labels}"
    assert (result.result or {}).get("status") == "ok", f"the green drive must complete: {result.result}"
    assert len(fx.supervisor_calls(result)) == 3, f"every ticket is dispatched: {labels}"

    reply_obj = {"restored": [], "ok": False, "copy_dir": None, "detail": "an alteration could not be put back"}
    bad = {"ok false": v.ran(reply_obj, 1), "declined": v.declined(), "not json": v.ran("this is not json"),
           "ok missing": v.ran({"restored": []}), "ok a string": v.recover_reply("true"), "null": None}
    for name, reply in bad.items():
        stopped = fx.run_epic(two_batches, {fx.RECOVER: reply})
        where, labels = f"recover {name}", fx.labels_of(stopped)
        assert not fx.supervisor_calls(stopped), f"{where}: a ticket-supervisor was dispatched: {labels}"
        assert fx.PLANNER not in labels and fx.OPEN not in labels, f"{where}: the drive went on past the halt: {labels}"
        keys = fx.blocked_keys(stopped)
        assert keys["status"] == "blocked" and keys["gate"] == "wrong_version_gate", f"{where}: terminal payload {stopped.result}"
        assert keys["wrong_version_step"] == "recover", f"{where}: wrong_version_step {keys['wrong_version_step']!r}"
        if name == "ok false":
            assert keys["wrong_version_detail"] == reply_obj, f"{where}: detail {keys['wrong_version_detail']!r}"
