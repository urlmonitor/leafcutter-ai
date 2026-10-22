"""
MODULE: unit_tests/workflows/test_tq500g1vi_route_batch.py
GOAL: RED tests for TQ-500g-1-vi, how templates/workflows-js/build-feature.js orders the wrong-version runs
    among the tickets of one epic batch: the sequence rides inside the commit lane for a batch that stays
    parallel, and a batch in which any ticket owes runs (or cannot be read) is driven one ticket at a time.
BUSINESS CONTEXT: The TEMPLATE runs under unit_tests/_workflow_engine_harness.py with its parallel() made
    concurrent as in the real engine (see _tq500g1vi_fixtures.engine_like_harness; the stock mock awaits the
    thunks one by one, which could not tell a parallel chunk from a serial one). Assertions are on the order of
    the recorded dispatches. Today the twin dispatches no wrong-version step and drives every batch in chunks
    of up to 12, so each test fails on an assertion about the recorded dispatches.
"""

from __future__ import annotations

import sys
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

import workflows._tq500g1v_fixtures as v  # noqa: E402
import workflows._tq500g1vi_fixtures as fx  # noqa: E402

ROUTE = fx.BF
LANE_TURN = [ROUTE.finish, fx.STAGE, fx.COMMIT, fx.OBSERVE]


def _drive_epic(items: list[dict], overrides: dict | None = None):
    labels = fx.epic_labels(items, phases=("commit",), ticket_source_ac=())
    labels.update(overrides or {})
    return fx.run_script(ROUTE.script, labels, {"target": fx.EPIC})


def _commit_index(result, path: str) -> int:
    hits = [i for i in fx.mentions(result, path) if result.agent_calls[i].label == fx.COMMIT]
    assert len(hits) == 1, f"expected one commit dispatch for {path}, recorded labels: {fx.labels_of(result)}"
    return hits[0]


def test_parallel_batch_never_overlaps_finish_with_a_sibling_commit():
    # covers: TQ-500g-1-vi
    # angle: seam
    # must_catch: finish dispatched while a sibling's commit is in flight
    # must_catch: sequence run outside the commitLane turn
    items = [fx.epic_item(1, []), fx.epic_item(2, [])]  # source_ac [] on both: the only batch that stays parallel
    result = _drive_epic(items)
    labels = fx.labels_of(result)
    firsts = [min(fx.mentions(result, i["path"])) for i in items]
    commits = [_commit_index(result, i["path"]) for i in items]
    assert max(firsts) < min(commits), f"the batch was not driven as one parallel chunk: {labels}"
    finishes = [i for i, label in enumerate(labels) if label == ROUTE.finish]
    assert len(finishes) == 2, f"each ticket makes its finish call: {labels}"
    assert all(fx.flag(fx.command_of(result.agent_calls[i]), "ac-ids") is None for i in finishes), "no --ac-ids without source_ac"
    first = min(finishes)
    window = labels[first:labels.index(fx.OBSERVE, first) + 1]
    assert window == LANE_TURN, f"the first ticket's finish..observe is broken by another dispatch: {labels}"
    end = first + len(LANE_TURN)
    assert max(finishes) >= end and max(commits) >= end and min(commits) == first + 2, f"the sibling's finish or commit is inside the turn: {labels}"
    # a halt in the first ticket's finish records no stage, commit or observe for it; the sibling still proceeds
    halting = v.finish_reply(v.verdict_f2())
    after = _drive_epic(items, {ROUTE.finish: {"__sequence__": [halting, v.finish_reply(v.verdict_f1())]}})
    ls = fx.labels_of(after)
    assert ls.count(ROUTE.finish) == 2, f"the sibling made no finish call: {ls}"
    assert ls.count(fx.STAGE) == ls.count(fx.COMMIT) == ls.count(fx.OBSERVE) == 1, f"the halted ticket was staged or committed: {ls}"
    committed = [i["path"] for i in items if any(after.agent_calls[j].label == fx.COMMIT for j in fx.mentions(after, i["path"]))]
    assert committed == [items[1]["path"]], f"the sibling did not proceed alone to commit: {committed}"


def test_batch_with_source_ac_runs_one_ticket_at_a_time():
    # covers: TQ-500g-1-vi
    # angle: discrimination
    # must_catch: parallel chunk kept when a ticket owes wrong-version runs
    # must_catch: unreadable source_ac treated as none
    cases = {
        "one ticket owes runs": [fx.epic_item(1, ["TQ-X-1"]), fx.epic_item(2, []), fx.epic_item(3, [])],
        "the owing ticket is last": [fx.epic_item(1, []), fx.epic_item(2, []), fx.epic_item(3, ["TQ-X-1"])],
        "source_ac key missing": [fx.epic_item(1), fx.epic_item(2, []), fx.epic_item(3, [])],
        "source_ac not an array": [fx.epic_item(1, "TQ-X-1"), fx.epic_item(2, []), fx.epic_item(3, [])],
        "source_ac null": [fx.epic_item(1, None), fx.epic_item(2, []), fx.epic_item(3, [])],
    }
    for name, items in cases.items():
        result = _drive_epic(items)
        labels = fx.labels_of(result)
        paths = [i["path"] for i in items]
        firsts = [min(fx.mentions(result, p)) for p in paths]
        commits = [_commit_index(result, p) for p in paths]
        assert firsts == sorted(firsts), f"{name}: tickets were not started in order: {labels}"
        for n in range(len(paths) - 1):
            assert commits[n] < firsts[n + 1], f"{name}: ticket {n + 2} started before ticket {n + 1} reached commit: {labels}"
    # control: the same three tickets with source_ac [] on each stay one parallel chunk, as today
    control_items = [fx.epic_item(n, []) for n in (1, 2, 3)]
    control = _drive_epic(control_items)
    paths = [i["path"] for i in control_items]
    firsts = [min(fx.mentions(control, p)) for p in paths]
    commits = [_commit_index(control, p) for p in paths]
    assert max(firsts) < min(commits), f"control: a batch with no source_ac must stay one parallel chunk: {fx.labels_of(control)}"
