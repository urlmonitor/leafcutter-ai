"""
MODULE: unit_tests/workflows/test_tq_500g_1_xi.py
GOAL: RED tests for the route side of TQ-500g-1-xi: build-feature.js, build-ticket.js and
    fast-lane-ship.js send the test-breaker only the names the list step says need preparing
    (``to_prepare``), dispatch it not at all when that array is empty, pass ``--work-key`` to the list
    step with the same key finish gets, and halt when ``to_prepare`` is missing or not an array.
BUSINESS CONTEXT: Every test runs the TEMPLATE under unit_tests/_workflow_engine_harness.py (the shared
    WRONG-VERSION-RUNS block is filled from templates/workflows-js/_shared/ by the harness, never a deployed
    copy) and asserts on the recorded dispatches, never on the source text. The list replies are built by
    ``_tq500g1v_fixtures.list_reply``. Today no route reads ``to_prepare``, so each test fails on an
    assertion about the recorded dispatches, never on an import.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

import workflows._tq500g1v_fixtures as v  # noqa: E402
import workflows._tq500g1vi_fixtures as fx  # noqa: E402


@dataclass(frozen=True)
class Lane:
    """One route under test: its drive, its four dispatch labels, its commit labels and its work key."""

    name: str
    drive: Callable[[dict], object]
    list_label: str
    breaker: str
    finish: str
    shipped: tuple[str, ...]
    work_key: str


def _fast_lane() -> Lane:
    return Lane("fast-lane-ship.js", lambda overrides: v.run_lane(overrides), v.LIST, v.BREAKER, v.FINISH,
                (v.COMMIT, v.PR), v.AC)


def _heavy(route: fx.Route) -> Lane:
    return Lane(route.script_name, lambda overrides: fx.run_route(route, overrides), route.list, route.breaker,
                route.finish, (fx.COMMIT,), fx.STEM)


LANES = (_fast_lane(), _heavy(fx.BF), _heavy(fx.BT))

N_A, N_B, N_C = "drop the retry_due condition", "the gate always allows", "refresh twice"
OWED_TWO = [v.owed_item(N_A, ["refresh_config.py"]), v.owed_item(N_B, ["refresh_config.py", "settings.py"])]
ITEM_DECLARED = v.owed_item("Zeta wrong VERSION ", ["z_second.py", "a_first.py"], "declared")
ITEM_DERIVED = {**v.owed_item("alpha wrong version", ["m_only.py"], "derived"), "blocking": False, "origin": "to_run_later"}
OWED_THREE = [v.owed_item(N_C, ["refresh_config.py"]), ITEM_DECLARED, ITEM_DERIVED]


def _once(result, label: str):
    found = v.calls(result, label)
    assert len(found) == 1, f"expected exactly one {label!r} dispatch, recorded labels: {v.labels_of(result)}"
    return found[0]


def test_nothing_to_prepare_dispatches_no_test_breaker(tmp_path: Path):
    # covers: TQ-500g-1-xi
    # angle: criterion
    # must_catch: test-breaker dispatched whenever owed is non-empty
    # must_catch: list command built without --work-key
    for lane in LANES:
        result = lane.drive({lane.list_label: v.list_reply(OWED_TWO, to_prepare=[])})
        labels = v.labels_of(result)
        assert len(OWED_TWO) == 2 and not v.calls(result, lane.breaker), (
            f"{lane.name}: test-breaker was dispatched with nothing to prepare (two names owed): {labels}")
        listing, finish = _once(result, lane.list_label), _once(result, lane.finish)
        list_key, finish_key = v.flag(v.command_of(listing), "work-key"), v.flag(v.command_of(finish), "work-key")
        assert list_key == lane.work_key, f"{lane.name}: the list command carries --work-key {list_key!r}: {v.command_of(listing)}"
        assert finish_key == list_key, f"{lane.name}: finish gets work key {finish_key!r}, list got {list_key!r}"
        assert labels.index(lane.list_label) < labels.index(lane.finish) < min(labels.index(s) for s in lane.shipped if s in labels), labels
        scratch = tmp_path / lane.name
        scratch.mkdir()
        script, saved = v.stdin_capture_gate(scratch)
        done = v.run_recorded(finish, script, scratch)  # the recorded finish command, in a real shell
        assert done.returncode == 0 and saved.is_file(), (lane.name, done.returncode, done.stderr[-300:])
        assert saved.read_bytes().strip() == b"", f"{lane.name}: finish got stdin {saved.read_bytes()!r} with nothing to prepare"
        control = lane.drive({lane.list_label: v.list_reply(OWED_TWO)})  # to_prepare == owed: the breaker still runs
        assert len(v.calls(control, lane.breaker)) == 1, f"{lane.name}: control: {v.labels_of(control)}"


def test_to_prepare_reaches_test_breaker_unchanged():
    # covers: TQ-500g-1-xi
    # angle: seam
    # must_catch: owed sent to test-breaker instead of to_prepare
    # must_catch: to_prepare items filtered, reordered or stripped of keys
    to_prepare = [ITEM_DERIVED, ITEM_DECLARED]  # not in owed order on purpose: any re-sorting shows
    for lane in LANES:
        result = lane.drive({lane.list_label: v.list_reply(OWED_THREE, to_prepare=to_prepare)})
        sent = v.breaker_input(_once(result, lane.breaker))
        assert sent is not None, f"{lane.name}: the test-breaker dispatch carries no wrong_versions input"
        assert sent["wrong_versions"] == to_prepare, f"{lane.name}: {sent['wrong_versions']}"
        assert sent["wrong_versions"] != OWED_THREE, f"{lane.name}: the owed array was sent, not to_prepare"
        assert [list(i) for i in sent["wrong_versions"]] == [list(i) for i in to_prepare], f"{lane.name}: key sets or order differ"
        assert len(sent["wrong_versions"]) == 2 and sent["work_key"] == lane.work_key, f"{lane.name}: {sent}"


def test_list_reply_without_to_prepare_halts():
    # covers: TQ-500g-1-xi
    # angle: failure
    # must_catch: a missing to_prepare read as nothing to prepare
    bad = {
        "no to_prepare key": v.ran({"owed": OWED_TWO, "decisions": [], "error": None}),
        "to_prepare a string": v.ran({"owed": OWED_TWO, "to_prepare": "nothing", "decisions": [], "error": None}),
        "to_prepare an object": v.ran({"owed": OWED_TWO, "to_prepare": {}, "decisions": [], "error": None}),
        "to_prepare null": v.ran({"owed": OWED_TWO, "to_prepare": None, "decisions": [], "error": None}),
    }
    for lane in LANES:
        for case, reply in bad.items():
            where = f"{lane.name}/{case}"
            result = lane.drive({lane.list_label: reply})
            labels = v.labels_of(result)
            out = result.result or {}
            assert out.get("status") == "blocked" and out.get("wrong_version_step") == "list", f"{where}: {out}"
            assert not v.calls(result, lane.breaker) and not v.calls(result, lane.finish), f"{where}: ran on past the halt: {labels}"
            assert not [s for s in lane.shipped if v.calls(result, s)], f"{where}: shipped after the halt: {labels}"
