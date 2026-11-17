"""BO-3800b-2: the coder that authored the work is not engaged to discharge a
demand the refusal handed to a specialist, and nobody is engaged in its place.

AC declares no test_spec: floor (criterion + reachability) plus the paired
discrimination arm and the named mutations. Every test drives the real driver
twins through the harness and reads the parties the run actually engaged.

Mutations that must go RED:
  (1) BELT AND BRACES -- engage the specialist AND re-engage the originating coder.
  (2) DISPOSITION IGNORED -- engage the specialist on every refusal, never the coder.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bo3800b_support as S  # noqa: E402

H = S.H
TWINS = list(H.TWIN_DRIVERS)
CODERS = ["python-coder", "sql-coder", "frontend-coder"]

pytestmark = pytest.mark.skipif(not S.node_available(), reason="node is not on PATH")


@pytest.fixture
def worktree():
    path = S.make_worktree()
    yield path
    S.drop_worktree(path)


def _specialist_decl():
    return S.declaration("check-file-size", agent=S.SPECIALIST, skills=[])


def _author_decl(coder):
    return S.declaration("check-file-size", disposition="author-clears", agent=None, skills=[])


@pytest.mark.parametrize("coder", CODERS)
@pytest.mark.parametrize("driver", TWINS)
def test_ac2_between_refusal_and_retry_only_the_specialist_is_engaged(driver, coder, worktree):
    # covers: BO-3800b-2
    # angle: criterion
    # must_catch: BELT AND BRACES -- the originating coder is re-engaged alongside the specialist
    """AC-2: the coder (whatever its type) appears in the record before the refusal;
    between the refusal and the second attempt the record contains the specialist,
    does NOT contain that coder, and no other party engaged in its place."""
    obs, _ = S.drive(driver, worktree, _specialist_decl(), S.size_demand(lines=120), coder=coder)
    ls = S.labels(obs)
    assert coder in ls[: ls.index("commit")], ls
    between = S.between_refusal_and_retry(obs)
    assert S.SPECIALIST in between, ls
    assert coder not in between, ls
    assert between == [S.SPECIALIST], f"a party other than the specialist was engaged: {ls}"
    assert S.commit_attempts(obs) == 2, ls


@pytest.mark.parametrize("driver", TWINS)
def test_ac2_party_engaged_moves_when_the_disposition_moves(driver, worktree):
    # covers: BO-3800b-2
    # angle: discrimination
    # must_catch: DISPOSITION IGNORED -- the specialist on every refusal; and a coder on every refusal
    """AC-2 (paired): same run, only the disposition changed. Specialist case:
    specialist in, coder out. Author-clearable case: coder in, specialist out. The
    answer must MOVE; a hard-coded selector passes every single-run assertion."""
    wt_b = S.make_worktree()
    try:
        obs_spec, _ = S.drive(driver, worktree, _specialist_decl(), S.size_demand(lines=120))
        obs_auth, _ = S.drive(driver, wt_b, _author_decl("python-coder"), S.size_demand(lines=20))
    finally:
        S.drop_worktree(wt_b)
    spec_between = S.between_refusal_and_retry(obs_spec)
    auth_between = S.between_refusal_and_retry(obs_auth)
    assert S.SPECIALIST in spec_between and "python-coder" not in spec_between, S.labels(obs_spec)
    assert "python-coder" in auth_between and S.SPECIALIST not in auth_between, S.labels(obs_auth)
    assert spec_between != auth_between


@pytest.mark.parametrize("driver", TWINS)
def test_ac2_nobody_engaged_in_the_specialists_place_when_it_is_missing(driver, worktree):
    # covers: BO-3800b-2
    # angle: failure
    """AC-2 (failure): a specialist-disposition refusal must never be silently
    served by the author or by anyone else. With the specialist's dispatch
    failing, the run must stop without re-engaging the coder and without a second
    delivery attempt that pretends the demand was discharged."""
    path = H.write_ticket_record(
        worktree, S.TICKET, ["test-writer", "python-coder", "commit"],
        extra_frontmatter={"component": "build-orchestration"},
    )
    decl = _specialist_decl()
    cfg = {
        "title": "specialist fails", "phases": ["test-writer", "python-coder", "commit"],
        "has_test_requirements": True,
        "results": {
            "commit": [S.refusal_reply(decl, S.size_demand(lines=120)), {"status": "ok"}],
            S.SPECIALIST: {"status": "failed", "message": "could not restructure"},
        },
    }
    scenario = H.single_ticket_scenario(worktree, path, cfg)
    scenario["remedy_declarations"] = {decl["hook_id"]: decl}
    obs = H.run_driver(H.TWIN_DRIVERS[driver], scenario)
    ls = S.labels(obs)
    assert S.SPECIALIST in ls, f"specialist was not asked at all: {ls}"
    assert ls.count("python-coder") == 1, f"the author was engaged in its place: {ls}"
    assert S.commit_attempts(obs) == 1, f"delivery retried after the specialist failed: {ls}"
    assert not S.completed(path)


def test_ac2_reachability_from_the_drivers_top_level_body(worktree):
    # covers: BO-3800b-2
    # angle: reachability
    """AC-2 (reachability): driven from build-feature.js's own top-level body, the
    absence of the author is a property of the run and the run still completes
    because the specialist's engagement was consumed in control flow."""
    obs, path = S.drive("build-feature.js", worktree, _specialist_decl(), S.size_demand(lines=120))
    assert S.between_refusal_and_retry(obs) == [S.SPECIALIST], S.labels(obs)
    assert S.completed(path), S.labels(obs)
    assert obs.get("error") is None, obs.get("error")
