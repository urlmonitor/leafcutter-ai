"""
MODULE: unit_tests/workflows/test_tq500g1viii_epic_marker.py
GOAL: RED test for TQ-500g-1-viii, the per-ticket gate marker of templates/workflows-js/build-epic.js: the marker
    is opened (``be-gate-marker-open``) before each ticket-supervisor dispatch with the key and path quoted, closed
    after it, the dispatch prompt carries ticket_key and runs_alone, and a refused or unparseable open reply or an
    unsafe ticket stem means that ticket-supervisor is never dispatched.
BUSINESS CONTEXT: The marker is what arms the commit-time hook for this ticket, so a ticket driven without it
    would commit unchecked. The TEMPLATE runs under unit_tests/_workflow_engine_harness.py; assertions are on the
    recorded dispatches (order, exact command lines, prompt fields) and the terminal payload. Today build-epic.js
    dispatches no command step, so the first assertion about the recorded dispatches fails.
"""

from __future__ import annotations

import sys
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

import workflows._tq500g1v_fixtures as v  # noqa: E402
import workflows._tq500g1viii_fixtures as fx  # noqa: E402


def test_build_epic_opens_marker_before_each_ticket_and_fails_closed():
    # covers: TQ-500g-1-viii
    # angle: reachability
    # must_catch: marker step refused but the ticket dispatched anyway
    # must_catch: unsafe ticket key pasted into a command
    pair = [fx.ticket(1, []), fx.ticket(2, [])]
    result = fx.run_epic([pair])
    labels = fx.labels_of(result)
    for item in pair:
        key = fx.key_of(item)
        label = f"ticket:{item['path']}"
        opens = [c for c in fx.calls(result, fx.OPEN) if fx.request_of(c)["target"]["run_id"] == key]
        assert len(opens) == 1, f"{key}: one marker open per ticket: {labels}"
        assert fx.command_of(opens[0]) == fx.open_command(key, item["path"]), f"{key}: open command {fx.command_of(opens[0])!r}"
        assert opens[0].agent_type == fx.EXECUTOR and fx.request_of(opens[0])["step"] == fx.OPEN, fx.request_of(opens[0])
        assert fx.request_of(opens[0])["target"] == {"workspace": fx.WT, "run_id": key}, fx.request_of(opens[0])
        opened_at, dispatched = fx.index_of(result, fx.OPEN, key), labels.index(label)
        assert opened_at < dispatched, f"{key}: the marker must be open before its ticket-supervisor is dispatched: {labels}"
        closed_at = fx.index_of(result, fx.CLOSE, key)
        assert closed_at > dispatched, f"{key}: the marker is closed after its ticket-supervisor returns: {labels}"
        assert fx.command_of(result.agent_calls[closed_at]) == fx.close_command(key), fx.command_of(result.agent_calls[closed_at])
        prompt = result.agent_calls[dispatched]
        assert fx.prompt_field(prompt, "ticket_key") == key, f"{key}: the dispatch prompt must carry ticket_key: {prompt.prompt!r}"
        assert fx.prompt_field(prompt, "runs_alone") == "false", f"{key}: two tickets share the chunk, runs_alone is false: {prompt.prompt!r}"
    alone = fx.run_epic([[fx.ticket(1, [])]])
    assert fx.prompt_field(fx.supervisor_calls(alone)[0], "runs_alone") == "true", "a chunk holding one ticket runs alone"

    # A refused or unparseable open reply: that ticket-supervisor is never dispatched, and the epic halts as blocked.
    one = [fx.ticket(1, [])]
    bad_open = {"opened false": fx.opened(False), "declined": v.declined(), "not json": v.ran("this is not json"),
                "opened a string": v.ran({"opened": "true"}), "opened missing": v.ran({"ticket_key": "x"}), "null": None}
    for name, reply in bad_open.items():
        stopped = fx.run_epic([one], {fx.OPEN: reply})
        where, labels = f"open {name}", fx.labels_of(stopped)
        assert fx.calls(stopped, fx.OPEN), f"{where}: the marker was never opened: {labels}"
        assert not fx.supervisor_calls(stopped), f"{where}: the ticket-supervisor was dispatched without a marker: {labels}"
        assert (stopped.result or {}).get("status") == "blocked", f"{where}: the epic must halt as blocked: {stopped.result}"
        entry = (fx.halted(stopped) or [{}])[0]
        assert entry.get("gate") == "gate_verdict_marker" and entry.get("marker_step") == "open", f"{where}: halted_tickets entry {entry}"
        assert "marker_detail" in entry, f"{where}: the halted entry must carry the reply it saw: {entry}"

    # An unsafe ticket stem or path: no command carries it, that ticket is not dispatched, and the epic is blocked.
    unsafe = {"stem with a shell command": fx.ticket(1, [], stem="a;rm -rf x"), "stem with a quote": fx.ticket(1, [], stem='a"b'),
              "stem with a dollar": fx.ticket(1, [], stem="a$(id)"), "stem with a backtick": fx.ticket(1, [], stem="a`id`"),
              "stem with a newline": fx.ticket(1, [], stem="a\nb")}
    for name, item in unsafe.items():
        stopped = fx.run_epic([[item]])
        where, labels = f"{name}", fx.labels_of(stopped)
        assert fx.calls(stopped, fx.RECOVER), f"{where}: the drive head did not run, so the test proves nothing: {labels}"
        assert not fx.supervisor_calls(stopped), f"{where}: the ticket-supervisor was dispatched: {labels}"
        assert not fx.calls(stopped, fx.OPEN), f"{where}: a marker command was built from an unsafe value: {labels}"
        pasted = [fx.command_of(c) for c in fx.executor_calls(stopped) if any(bad in fx.command_of(c) for bad in ("rm -rf", "$(id)", "`id`", 'a"b', "a\nb"))]
        assert not pasted, f"{where}: an unsafe value reached a command line: {pasted}"
        assert (stopped.result or {}).get("status") == "blocked", f"{where}: the epic must halt as blocked: {stopped.result}"
        entry = (fx.halted(stopped) or [{}])[0]
        assert entry.get("gate") == "gate_verdict_marker" and entry.get("marker_step") == "input-check", f"{where}: halted_tickets entry {entry}"
