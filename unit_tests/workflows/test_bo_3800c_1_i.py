"""BO-3800c-1-i: a refusal that hands the work to a specialist but carries no usable
demand stops the run and reproduces what it was given, rather than supplying a
demand of its own.

AC declares no test_spec, so this file writes the floor (criterion + reachability)
plus the angles the AC's named mutation (THE HELPFUL DEFAULT) demands: a paired
control run in which a WELL-FORMED refusal does engage the specialist (so "nobody
engaged" is a fact, not a tautology), and the could-not-read vs read-and-empty
distinction. Every test EXECUTES the real drivers (build-feature.js and
build-ticket.js, TWIN_DRIVERS) through the driver harness and reads what the run
actually dispatched and reported.

Mutation these tests must catch:
  THE HELPFUL DEFAULT -- when the demand is unusable, engage the specialist anyway
  with the demand omitted (or a placeholder, or one recovered by re-running the standard).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bo3800b_support as S  # noqa: E402

H = S.H
TWINS = list(H.TWIN_DRIVERS)
BIG = "scripts/big_module.py"
NOT_A_QUANTITY = "lots-of-lines"

pytestmark = pytest.mark.skipif(not S.node_available(), reason="node is not on PATH")

# (id, demand) -- every shape the AC names: file unnamed; quantity absent, empty, blank, not a quantity
UNUSABLE = [
    ("file_unnamed_empty", [{"path": "", "lines_to_remove": 120}]),
    ("file_unnamed_absent", [{"lines_to_remove": 120}]),
    ("quantity_absent", [{"path": BIG}]),
    ("quantity_empty", [{"path": BIG, "lines_to_remove": ""}]),
    ("quantity_blank", [{"path": BIG, "lines_to_remove": "   "}]),
    ("quantity_not_a_quantity", [{"path": BIG, "lines_to_remove": NOT_A_QUANTITY}]),
    ("demand_list_empty", []),
]


@pytest.fixture
def worktree():
    path = S.make_worktree()
    yield path
    S.drop_worktree(path)


def _decl():
    return S.declaration("check-file-size", agent=S.SPECIALIST, skills=[])


def _message(obs) -> str:
    return str((obs.get("result") or {}).get("message") or "")


def _assert_stopped_nobody_engaged(obs, path):
    result = obs.get("result") or {}
    ls = S.labels(obs)
    assert S.SPECIALIST not in ls, f"the specialist was engaged on an unusable demand: {ls}"
    assert S.specialist_dispatches(obs) == [], ls
    assert result.get("status") == "blocked", result
    assert S.commit_attempts(obs) == 1, f"delivery was attempted again: {ls}"
    assert not S.completed(path), "the ticket completed despite the stop"


@pytest.mark.parametrize("driver", TWINS)
@pytest.mark.parametrize("case,demand", UNUSABLE, ids=[c for c, _ in UNUSABLE])
def test_c1i_unusable_demand_engages_nobody_stops_and_says_so(driver, case, demand, worktree):
    # covers: BO-3800c-1-i
    # angle: criterion
    # must_catch: THE HELPFUL DEFAULT -- engage the specialist anyway, demand omitted
    """No specialist is engaged, the run stops, delivery is not attempted again, and the
    stop says the refusal was read and carried no usable demand."""
    obs, path = S.drive(driver, worktree, _decl(), demand)
    _assert_stopped_nobody_engaged(obs, path)
    message = _message(obs)
    assert "no usable demand" in message.lower(), message
    assert "could not be read" not in message.lower(), message


@pytest.mark.parametrize("driver", TWINS)
def test_c1i_stop_reproduces_the_value_it_was_given(driver, worktree):
    # covers: BO-3800c-1-i
    # angle: boundary
    # must_catch: a stop that substitutes a quantity (a default, the file's size, a re-run)
    """The unusable quantity is reproduced verbatim in the stop, and no number is
    supplied in its place."""
    obs, path = S.drive(driver, worktree, _decl(), [{"path": BIG, "lines_to_remove": NOT_A_QUANTITY}])
    _assert_stopped_nobody_engaged(obs, path)
    message = _message(obs)
    assert NOT_A_QUANTITY in message, f"the stop did not reproduce the value it was given: {message!r}"
    assert BIG in message, message


@pytest.mark.parametrize("driver", TWINS)
def test_c1i_well_formed_control_engages_where_unusable_does_not(driver, worktree):
    # covers: BO-3800c-1-i
    # angle: discrimination
    # must_catch: THE NEVER-ENGAGE BUILD -- nobody engaged is a tautology without a paired engaging run
    """Paired runs, one input changed: the well-formed demand engages the specialist
    and the run completes; the unusable demand engages nobody and stops."""
    other = S.make_worktree()
    try:
        good, good_path = S.drive(driver, worktree, _decl(), S.size_demand(path=BIG, lines=120))
        bad, bad_path = S.drive(driver, other, _decl(), [{"path": BIG, "lines_to_remove": ""}])
    finally:
        S.drop_worktree(other)
    assert S.SPECIALIST in S.labels(good), S.labels(good)
    assert S.completed(good_path)
    _assert_stopped_nobody_engaged(bad, bad_path)
    assert S.labels(good) != S.labels(bad)


@pytest.mark.parametrize("driver", TWINS)
def test_c1i_complexity_refusal_with_no_structured_demand_stops(driver, worktree):
    # covers: BO-3800c-1-i
    # angle: failure
    # must_catch: THE HELPFUL DEFAULT -- complexity flavour, an empty demand list
    """A check-complexity refusal handing work to the specialist but carrying an empty
    demand list is the same stop (BO-3800c-2 constraint): nobody engaged, no demand built."""
    obs, path = S.drive(driver, worktree, S.declaration("check-complexity"), [])
    _assert_stopped_nobody_engaged(obs, path)
    assert "no usable demand" in _message(obs).lower(), _message(obs)


@pytest.mark.parametrize("driver", TWINS)
def test_c1i_read_and_empty_is_reported_apart_from_could_not_be_read(driver, worktree):
    # covers: BO-3800c-1-i
    # angle: boundary
    # must_catch: collapsing the two stops into one message
    """A refusal that was read and said nothing usable, and a refusal whose
    declaration could not be read at all, both stop with nobody engaged -- and the
    two reports are distinguishable, in neither direction mistaken for the other."""
    decl = _decl()
    unreadable = S.refusal_reply(decl, S.size_demand(path=BIG, lines=120))
    unreadable["remedy"]["hook_id"] = "check-no-such-hook"  # no declaration the run can read
    other = S.make_worktree()
    try:
        empty_obs, empty_path = S.drive(driver, worktree, decl, [])
        unread_obs, unread_path = S.drive(driver, other, decl, [], reply=unreadable)
    finally:
        S.drop_worktree(other)
    _assert_stopped_nobody_engaged(empty_obs, empty_path)
    _assert_stopped_nobody_engaged(unread_obs, unread_path)
    empty_msg, unread_msg = _message(empty_obs).lower(), _message(unread_obs).lower()
    assert "no usable demand" in empty_msg and "no usable demand" not in unread_msg, (empty_msg, unread_msg)
    assert "could not be read" in unread_msg and "could not be read" not in empty_msg, (empty_msg, unread_msg)


def test_c1i_reachability_the_stop_is_consumed_by_the_drivers_control_flow(worktree):
    # covers: BO-3800c-1-i
    # angle: reachability
    """Reachability: started at the production entry point (build-feature.js executed
    through the harness) an unusable demand halts the run before the specialist and
    before the retried delivery, and the ticket record is left unfinished."""
    obs, path = S.drive("build-feature.js", worktree, _decl(), [])
    _assert_stopped_nobody_engaged(obs, path)
    assert obs.get("error") is None, obs.get("error")
    assert json.dumps(obs.get("result") or {}).count("no usable demand") >= 1, obs.get("result")
