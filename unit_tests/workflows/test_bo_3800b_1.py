"""BO-3800b-1: on the refusal path the restructuring specialist is actually engaged
by the run, and engaged before delivery is attempted again.

AC declares no test_spec, so this file writes the floor (criterion + reachability)
plus the two angles the AC's named mutations demand (discrimination: the paired
disposition arm; failure: the inert ask). Every test EXECUTES the real driver's
top-level body through the driver harness (TWIN_DRIVERS) and reads the ordered
record of parties the run engaged -- never a template, workflow file or prompt.

Mutations these tests must catch (each must go RED on the named wrong build):
  (1) INERT ASK    -- print the specialist's name, engage nobody, retry anyway.
  (2) LATE ASK     -- attempt delivery again first, engage the specialist after.
  (3) DISPOSITION IGNORED -- engage the specialist on every refusal.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bo3800b_support as S  # noqa: E402

H = S.H
TWINS = list(H.TWIN_DRIVERS)

pytestmark = pytest.mark.skipif(not S.node_available(), reason="node is not on PATH")


@pytest.fixture
def worktree():
    path = S.make_worktree()
    yield path
    S.drop_worktree(path)


def _specialist_decl():
    # check-file-size, disposition engage-specialist, party = the specialist
    # (GE-127f-3's shape, supplied by the fixture: the seed names python-coder).
    return S.declaration("check-file-size", agent=S.SPECIALIST, skills=[])


def _author_decl():
    return S.declaration("check-file-size", disposition="author-clears", agent=None, skills=[])


@pytest.mark.parametrize("driver", TWINS)
def test_ac1_specialist_engaged_after_refusal_and_before_the_second_attempt(driver, worktree):
    # covers: BO-3800b-1
    # angle: criterion
    """AC-1: the run engages the restructuring specialist, in the ordered record,
    after the refusal and BEFORE the second delivery attempt (kills the LATE ASK)."""
    obs, _ = S.drive(driver, worktree, _specialist_decl(), S.size_demand(lines=120))
    ls = S.labels(obs)
    assert S.SPECIALIST in ls, f"specialist never engaged: {ls}"
    assert ls.count("commit") == 2, f"delivery was not retried exactly once: {ls}"
    first_commit = ls.index("commit")
    second_commit = ls.index("commit", first_commit + 1)
    assert first_commit < ls.index(S.SPECIALIST) < second_commit, ls
    # alongside the parties engaged BEFORE the refusal, in order
    assert ls[:first_commit] == ["test-writer", "python-coder"], ls


@pytest.mark.parametrize("driver", TWINS)
def test_ac1_engagement_is_a_dispatch_the_run_made_not_a_printed_line(driver, worktree):
    # covers: BO-3800b-1
    # angle: failure
    # must_catch: THE INERT ASK -- the name and demand are written to output, nobody engaged
    """AC-1 (failure): the engagement must be a real dispatch whose party is the
    specialist, carrying the demand, and its sign-off must land in the ticket record.
    A run that only logs the specialist's name fails every clause here."""
    obs, path = S.drive(driver, worktree, _specialist_decl(), S.size_demand(lines=120))
    dispatches = S.specialist_dispatches(obs)
    assert len(dispatches) == 1, S.labels(obs)
    assert dispatches[0]["agent_type"] in (S.SPECIALIST, None), dispatches[0]
    assert "scripts/big_module.py" in dispatches[0]["prompt"], dispatches[0]["prompt"]
    assert "120" in dispatches[0]["prompt"], dispatches[0]["prompt"]
    record = H.read_record(path)
    assert S.SPECIALIST in record["signed_off_agents"], record["signed_off_agents"]


@pytest.mark.parametrize("driver", TWINS)
def test_ac1_party_engaged_is_the_specialist_and_no_other(driver, worktree):
    # covers: BO-3800b-1
    # angle: criterion
    """AC-1: the party engaged between refusal and retry is the specialist and
    not some other party the run had to hand."""
    obs, _ = S.drive(driver, worktree, _specialist_decl(), S.size_demand(lines=120))
    assert S.between_refusal_and_retry(obs) == [S.SPECIALIST], S.labels(obs)


@pytest.mark.parametrize("driver", TWINS)
def test_ac1_engagement_moves_with_the_stated_disposition(driver, worktree):
    # covers: BO-3800b-1
    # angle: discrimination
    # must_catch: THE DISPOSITION IGNORED -- engage the specialist on every refusal
    """AC-1 (paired): the SAME refusal with only the disposition changed
    (author-clearable) must not engage the specialist, and the specialist run
    must. A single-run assertion cannot catch an always-on or never-on build."""
    wt_a = worktree
    wt_b = S.make_worktree()
    try:
        obs_spec, _ = S.drive(driver, wt_a, _specialist_decl(), S.size_demand(lines=120))
        obs_auth, _ = S.drive(driver, wt_b, _author_decl(), S.size_demand(lines=20))
    finally:
        S.drop_worktree(wt_b)
    assert S.SPECIALIST in S.labels(obs_spec), S.labels(obs_spec)
    assert S.SPECIALIST not in S.labels(obs_auth), S.labels(obs_auth)
    assert S.labels(obs_spec) != S.labels(obs_auth), "engagement did not move with the disposition"


def test_ac1_reachability_from_the_drivers_top_level_body_the_result_is_consumed(worktree):
    # covers: BO-3800b-1
    # angle: reachability
    """AC-1 (reachability): started at the production entry point (build-feature.js
    executed through the harness with real argv-equivalent args) the specialist's
    engagement occurs AND its result is consumed in control flow: the retried
    delivery runs after it and the ticket completes in the same run."""
    obs, path = S.drive("build-feature.js", worktree, _specialist_decl(), S.size_demand(lines=120))
    result = obs["result"] or {}
    assert S.SPECIALIST in S.labels(obs), (S.labels(obs), result)
    assert result.get("status") != "blocked", result
    assert S.commit_attempts(obs) == 2, S.labels(obs)
    assert S.completed(path), "the ticket did not complete after the specialist's work"
    assert obs.get("error") is None, obs.get("error")
