"""BO-3800c-1: what the restructuring specialist is given is the file and the demand
the refusal stated, and both move when the refusal's do -- never a second derivation.

AC declares no test_spec, so this file writes the floor (criterion + reachability)
plus the two discriminating angles the AC's notes demand (the moving pair, and the
disagreeing-demand arm that a reconstruction cannot satisfy). Every test EXECUTES
the real driver top-level body (build-feature.js / build-ticket.js, TWIN_DRIVERS)
through the driver harness and reads the dispatch the run actually made -- never
driver source, never a briefing helper called directly.

The refusal is an INPUT the test supplies (BO-3800c-1 fixture constraint): the
disagreeing-demand arm states a demand of its own choosing against a file whose
real size would yield a different number, without computing any second demand.

Mutations these tests must catch (each must go RED on the named wrong build):
  (1) THE RECONSTRUCTION -- file only; demand re-derived when the specialist is engaged.
  (2) THE FROZEN BRIEF   -- standing instruction with the file substituted, demand omitted.
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
OTHER = "scripts/other_module.py"

pytestmark = pytest.mark.skipif(not S.node_available(), reason="node is not on PATH")


@pytest.fixture
def worktree():
    path = S.make_worktree()
    yield path
    S.drop_worktree(path)


def _decl():
    return S.declaration("check-file-size", agent=S.SPECIALIST, skills=[])


def _given(driver, worktree, path=BIG, lines=120):
    """What the specialist actually received: (brief, prompt) from the run's dispatch."""
    obs, _ = S.drive(driver, worktree, _decl(), S.size_demand(path=path, lines=lines))
    (disp,) = S.specialist_dispatches(obs)
    brief = disp["opts_brief"]
    assert isinstance(brief, dict), f"no machine-readable brief on the dispatch: {disp}"
    return brief, disp["prompt"]


@pytest.mark.parametrize("driver", TWINS)
def test_c1_specialist_is_given_the_named_file_and_the_stated_demand(driver, worktree):
    # covers: BO-3800c-1
    # angle: criterion
    # must_catch: THE FROZEN BRIEF -- standing instruction, demand omitted
    """Arm 1: refusal names scripts/big_module.py and a demand of 120 measured lines;
    the brief and the prompt the specialist received state exactly that."""
    brief, prompt = _given(driver, worktree)
    assert brief["demand"] == S.size_demand(path=BIG, lines=120), brief
    assert BIG in prompt and "120" in prompt, prompt


@pytest.mark.parametrize("driver", TWINS)
def test_c1_demand_moves_with_the_refusal(driver, worktree):
    # covers: BO-3800c-1
    # angle: discrimination
    # must_catch: a hard-coded or frozen demand (passes every single-run assertion)
    """Arm 2: the same run with only the demand changed to 37 -- the brief states 37
    (and no longer 120), so the demand MOVED with the refusal's."""
    other = S.make_worktree()
    try:
        first, first_prompt = _given(driver, worktree, lines=120)
        second, second_prompt = _given(driver, other, lines=37)
    finally:
        S.drop_worktree(other)
    assert second["demand"] == S.size_demand(path=BIG, lines=37), second
    assert "37" in second_prompt and "120" not in second_prompt, second_prompt
    assert first["demand"] != second["demand"], "the demand did not move"
    assert "120" in first_prompt  # control: the harness can state 120


@pytest.mark.parametrize("driver", TWINS)
def test_c1_file_moves_with_the_refusal(driver, worktree):
    # covers: BO-3800c-1
    # angle: discrimination
    # must_catch: a hard-coded or frozen file name
    """Arm 3: the same run naming a different covered file at the same demand -- the
    file named in what the specialist is given MOVED."""
    other = S.make_worktree()
    try:
        first, first_prompt = _given(driver, worktree, path=BIG)
        second, second_prompt = _given(driver, other, path=OTHER)
    finally:
        S.drop_worktree(other)
    assert second["demand"] == S.size_demand(path=OTHER, lines=120), second
    assert OTHER in second_prompt and BIG not in second_prompt, second_prompt
    assert BIG in first_prompt and OTHER not in first_prompt, first_prompt


@pytest.mark.parametrize("driver", TWINS)
def test_c1_demand_is_the_refusals_not_a_rederivation(driver, worktree):
    # covers: BO-3800c-1
    # angle: discrimination
    # must_catch: THE RECONSTRUCTION -- file only, demand re-derived from the file at engagement
    """Arm 4 (the discriminator): the refusal states 120 against a file that really has
    a handful of lines, so any re-read or re-run of the standard against the file
    disagrees. The brief must state the REFUSAL's 120, and nothing derived from the file."""
    real = Path(worktree) / BIG
    real.parent.mkdir(parents=True, exist_ok=True)
    real.write_text("".join(f"x{i} = {i}\n" for i in range(7)), encoding="utf-8")
    brief, prompt = _given(driver, worktree, lines=120)
    assert brief["demand"] == S.size_demand(path=BIG, lines=120), brief
    assert "120" in prompt, prompt
    assert real.read_text(encoding="utf-8").count("\n") == 7  # control: the file really disagrees
    assert json.dumps(brief["demand"]).count("lines_to_remove") == 1, brief


def test_c1_reachability_demand_travels_from_the_drivers_body_and_is_consumed(worktree):
    # covers: BO-3800c-1
    # angle: reachability
    """Reachability: started at the production entry point (build-feature.js executed
    through the harness) the specialist is engaged WITH the stated demand, and the
    engagement is consumed in control flow: the retried delivery runs after it and
    the ticket completes in the same run."""
    obs, path = S.drive("build-feature.js", worktree, _decl(), S.size_demand(lines=120))
    result = obs["result"] or {}
    assert S.SPECIALIST in S.labels(obs), (S.labels(obs), result)
    (disp,) = S.specialist_dispatches(obs)
    assert disp["opts_brief"]["demand"] == S.size_demand(lines=120), disp["opts_brief"]
    assert result.get("status") != "blocked", result
    assert S.commit_attempts(obs) == 2, S.labels(obs)
    assert S.completed(path), "the ticket did not complete after the specialist's work"
    assert obs.get("error") is None, obs.get("error")
