"""
MODULE: unit_tests/workflows/test_tq500g1viii_epic_batches.py
GOAL: RED test for TQ-500g-1-viii, how templates/workflows-js/build-epic.js chunks a batch: one ticket per chunk
    (``runs_alone: true`` in the dispatch prompt) when any ticket of the batch owes wrong-version runs or its
    source_ac cannot be read, and one parallel chunk (``runs_alone: false``) when every ticket reports ``[]``.
BUSINESS CONTEXT: The commit lock serialises commit phases only, and the finish step builds "the fix undone" from
    ALL uncommitted changes in the worktree, so a sibling's coder in flight would be judged, reverted or
    overwritten. The TEMPLATE runs under unit_tests/_workflow_engine_harness.py with its parallel() made
    concurrent as in the real engine (the stock mock awaits the thunks one by one and could not tell a parallel
    chunk from a serial one). Today build-epic.js has no source_ac and no marker, so the first assertion fails.
"""

from __future__ import annotations

import sys
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

import workflows._tq500g1viii_fixtures as fx  # noqa: E402


def _starts(result, item) -> int:
    """Index of the first dispatch of *item*: its marker open, which the AC puts before its supervisor."""
    return fx.index_of(result, fx.OPEN, fx.key_of(item))


def _drive(items):
    result = fx.run_epic([items])
    assert len(fx.supervisor_calls(result)) == len(items), f"every ticket is dispatched: {fx.labels_of(result)}"
    return result


def _runs_alone(result, item) -> str | None:
    call = next(c for c in fx.supervisor_calls(result) if c.label == f"ticket:{item['path']}")
    return fx.prompt_field(call, "runs_alone")


def test_build_epic_serialises_batches_that_owe_runs():
    # covers: TQ-500g-1-viii, TQ-500g-1-vii
    # angle: discrimination
    # must_catch: parallel chunk kept when a ticket owes wrong-version runs
    # must_catch: missing source_ac read as no source requirement
    # must_catch: every batch serialised, including one that owes no runs
    cases = {
        "one ticket owes runs": [fx.ticket(1, ["X-1"]), fx.ticket(2, []), fx.ticket(3, [])],
        "the owing ticket is last": [fx.ticket(1, []), fx.ticket(2, []), fx.ticket(3, ["X-1"])],
        "source_ac key missing": [fx.ticket(1), fx.ticket(2, []), fx.ticket(3, [])],
        "source_ac not an array": [fx.ticket(1, "X-1"), fx.ticket(2, []), fx.ticket(3, [])],
        "source_ac null": [fx.ticket(1, None), fx.ticket(2, []), fx.ticket(3, [])],
    }
    for name, items in cases.items():
        result = _drive(items)
        labels = fx.labels_of(result)
        for n, item in enumerate(items):
            assert _runs_alone(result, item) == "true", f"{name}: ticket {n + 1} runs alone in its chunk: {labels}"
        for n in range(len(items) - 1):
            closed = fx.index_of(result, fx.CLOSE, fx.key_of(items[n]))
            assert closed < _starts(result, items[n + 1]), f"{name}: ticket {n + 2} started before ticket {n + 1} was finished: {labels}"

    # Control: three tickets that all carry source_ac [] stay ONE parallel chunk, as today.
    control = [fx.ticket(1, []), fx.ticket(2, []), fx.ticket(3, [])]
    result = _drive(control)
    labels = fx.labels_of(result)
    first_close = min(fx.index_of(result, fx.CLOSE, fx.key_of(i)) for i in control)
    assert max(_starts(result, i) for i in control) < first_close, f"control: a batch owing no runs must stay one parallel chunk: {labels}"
    assert all(_runs_alone(result, i) == "false" for i in control), f"control: runs_alone must be false for a shared chunk: {labels}"

    # The planner is asked for source_ac on every ticket item, always (an empty array when there is none).
    items_schema = fx.calls(result, fx.PLANNER)[0].opts["schema"]["properties"]["batches"]["items"]["properties"]["tickets"]["items"]
    assert items_schema["properties"].get("source_ac", {}).get("type") == "array", f"PLANNER_SCHEMA ticket items: {items_schema['properties']}"
    assert items_schema["properties"]["source_ac"].get("items", {}).get("type") == "string", items_schema["properties"]["source_ac"]
    assert "source_ac" in items_schema.get("required", []), "source_ac must be required: it is ALWAYS returned, [] when none"
