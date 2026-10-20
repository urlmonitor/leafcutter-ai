"""
MODULE: unit_tests/commit_guardian/test_acs_900d_4_iv_retired_child_composite.py
GOAL: RED tests for ACS-900d-4-iv -- a retired child neither blocks nor proves its
    parent's done claim, on BOTH composite paths (the pre-commit rollup,
    _unproven_composite_children, and the CI rollup, _resolve_all_child_ids).

The two paths have diverged before (KI-ACS-016), so every gate scenario asserts both:
check_done_proof.py runs as a real subprocess in --mode precommit (the staged parent),
then --mode ci-changed and --mode ci after the parent is committed. The two "unit"
tests call the real rollup functions in a fresh process (no sys.path pollution here).

User decision 2 (zero live children): a live parent whose children are ALL retired falls
back to the leaf rule. It needs its own '# covers: <parent>' tag; it is never proven
vacuously and is not refused unconditionally either.

Named wrong versions caught: a composite with zero live children is vacuously proven; a
retired child's done+covered state counts as proof for the parent; a composite with zero
live children is refused even with its own covering test (today's behaviour); the walk
keeps the old "any non-empty superseded_by" test.

DECISION HISTORY
- 2026-10-15 [test-writer/ACS-900d-4-iv]: Initial RED authoring.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _acs_900d_4_fixtures as fx  # noqa: E402

P = fx.PARENT_ID
K1, K2, K3 = fx.KIDS


def _run(tmp_path: Path, name: str, states: tuple[str, str, str], *, parent_cover: bool = False):
    """Build the composite scenario and run every done-proof path over the staged parent."""
    repo = fx.make_repo(tmp_path / name)
    parent = fx.composite_scenario(repo, states, parent_cover=parent_cover)
    return repo, parent, fx.run_all_done_proof_paths(repo)


def _assert_no_refusal(results: dict) -> None:
    for path_name, proc in results.items():
        assert proc.returncode == 0, f"{path_name} refused the parent (exit {proc.returncode}): {fx.out(proc)!r}"
        assert not fx.done_proof_refusals(proc), f"{path_name} named a record: {fx.out(proc)!r}"


def test_retired_todo_child_does_not_block_parent_on_both_paths(tmp_path: Path) -> None:
    # covers: ACS-900d-4-iv
    # angle: criterion
    """P-1 and P-2 live, done, covered; P-3 retired at todo. P is not refused on any path."""
    _, _, results = _run(tmp_path, "todo_child", ("live_done", "live_done", "retired_todo"))

    _assert_no_refusal(results)


def test_parent_proven_from_live_children_only(tmp_path: Path) -> None:
    # covers: ACS-900d-4-iv
    # angle: criterion
    """Both rollup functions leave P-3 out and judge P proven from P-1 and P-2."""
    repo = fx.make_repo(tmp_path / "live_only")
    parent = fx.composite_scenario(repo, ("live_done", "live_done", "retired_todo"))
    verdicts = fx.composite_verdicts(repo, parent)

    assert verdicts["precommit"] == [], f"pre-commit rollup left the parent unproven: {verdicts}"
    assert verdicts["ci"] == [K1, K2], f"CI rollup did not resolve exactly the live children: {verdicts}"


def test_only_live_child_unfinished_refused_and_named(tmp_path: Path) -> None:
    # covers: ACS-900d-4-iv
    # angle: criterion
    """P-1 and P-2 retired, P-3 live at todo: P is refused naming P-3 and neither retired child."""
    _, _, results = _run(tmp_path, "one_live", ("retired_todo", "retired_done", "live_todo"))

    for path_name in ("precommit", "ci_changed", "ci"):
        proc = results[path_name]
        reason = fx.done_proof_refusals(proc).get(P)
        assert proc.returncode != 0 and reason, f"{path_name} did not refuse {P}: {fx.out(proc)!r}"
        assert fx.mentions(reason, K3), f"{path_name} refusal does not name the live child {K3}: {reason!r}"
        assert not fx.mentions(reason, K1) and not fx.mentions(reason, K2), (
            f"{path_name} refusal names a retired child: {reason!r}"
        )


def test_all_children_retired_parent_without_own_cover_refused(tmp_path: Path) -> None:
    # covers: ACS-900d-4-iv
    # angle: discrimination
    """Every child retired (some done and covered), P done with no tag of its own: refused for the tag.

    Wrong versions caught: zero live children treated as vacuously proven; a retired child's
    done+covered state counted as proof. The leaf rule's own message is required, not the
    composite 'unproven' wording, because the parent now falls back to the leaf rule.
    """
    states = ("retired_done", "retired_done", "retired_todo")
    _, _, results = _run(tmp_path, "all_retired", states)

    pre = fx.done_proof_refusals(results["precommit"]).get(P, "")
    assert results["precommit"].returncode != 0 and f"covers: {P}" in pre, (
        f"pre-commit did not apply the leaf rule to {P}: {fx.out(results['precommit'])!r}"
    )
    for path_name in ("ci_changed", "ci"):
        reason = fx.done_proof_refusals(results[path_name]).get(P, "")
        assert f"no linked test found for {P}" in reason, (
            f"{path_name} did not refuse {P} for its missing covering test: {fx.out(results[path_name])!r}"
        )


def test_all_children_retired_parent_with_own_cover_passes(tmp_path: Path) -> None:
    # covers: ACS-900d-4-iv
    # angle: boundary
    """Every child retired and a '# covers: P' test present: P passes on both paths.

    Wrong version caught: a composite with zero live children refused unconditionally
    (the current behaviour, which ignores P's own covering test).
    """
    states = ("retired_done", "retired_done", "retired_todo")
    _, _, results = _run(tmp_path, "all_retired_covered", states, parent_cover=True)

    _assert_no_refusal(results)


def test_structurally_invalid_retired_child_counts_as_live(tmp_path: Path) -> None:
    # covers: ACS-900d-4-iv
    # angle: discrimination
    """A child whose supersession names a missing successor is live, so its todo refuses the parent.

    Wrong version caught: the composite walk keeps the old 'any non-empty superseded_by' test.
    """
    repo = fx.make_repo(tmp_path / "invalid_child")
    parent = fx.composite_scenario(repo, ("live_done", "live_done", "bad_retired_todo"))
    verdicts = fx.composite_verdicts(repo, parent)

    assert verdicts["precommit"] == [K3], f"pre-commit rollup skipped the invalid supersession: {verdicts}"
    assert verdicts["ci"] == [K1, K2, K3], f"CI rollup skipped the invalid supersession: {verdicts}"
