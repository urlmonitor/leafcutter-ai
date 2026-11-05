"""
MODULE: unit_tests/build_orchestration/test_tq500f3iii_red_baseline_identity.py
GOAL: RED tests for TQ-500f-3-iii, red-baseline side -- verify_red_baseline
    attributes every outcome to the same test the proof-of-done check does,
    judges an inherited test across every inheriting class, and refuses (never
    guesses) a tag it cannot tie to exactly one test.
AC: docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500f-3-iii.yaml

Every test is declared with ``must_catch`` in the AC's test_spec, so each must
fail by reaching the existing readers (``fast_lane.py verify_red_baseline`` as
a subprocess, ``done_proof.verify_done_eligible`` in a fresh subprocess) and
observing a wrong verdict, not by importing a name that does not exist yet.
Fixtures are real test files run by the real pytest; AC records come from
yaml.safe_dump.
"""

from __future__ import annotations

from unit_tests.ac_store import _tq500f3iii_fixtures as fx
from unit_tests.build_orchestration import _tq500f3i_fixtures as gfx

AMBIGUOUS = "ambiguous_test_identity"


def _red_baseline(tmp_path, ac_ids, ac_root, build) -> dict:
    """Make a git worktree, let *build(work_dir)* write the tests, run the CLI."""
    work_dir, base_sha = gfx.make_worktree(tmp_path / "git")
    build(work_dir)
    return work_dir, fx.run_verify_red_baseline(fx.SOURCE_FAST_LANE, ac_ids, work_dir, ac_root, base_ref=base_sha)


def test_red_baseline_reader_attributes_same_tests_as_done_proof(tmp_path):
    # covers: TQ-500f-3-iii
    # angle: seam
    """Over the SAME T1..T4 files and run, verify_red_baseline attributes each
    of the four outcomes to the same nodeid the done-proof check does, and none
    of the four is reported ambiguous.

    Wrong versions caught: the reader keeps its own copy of the matching; the
    reader still matches by basename + function name; the reader reports a
    colliding pair as ambiguous_test_identity.
    """
    ac_root = tmp_path / "ac_store"
    fx.write_ac_store(ac_root, fx.T1_T4_IDS)
    work_dir, verdict = _red_baseline(tmp_path, fx.T1_T4_IDS, ac_root, fx.build_collision_repo)
    expected = fx.FORWARD_NODEIDS

    assert verdict.get("reason") != AMBIGUOUS, verdict
    assert verdict.get("gate_passed") is True, verdict
    red = fx.entry_nodeids(verdict.get("red"))
    green = fx.entry_nodeids(verdict.get("green_at_baseline"))
    assert set(red) == {fx.T1, fx.T4} and set(green) == {fx.T2, fx.T3}, verdict

    done_proof = fx.run_done_proof_driver(fx.SOURCE_SCRIPTS, ac_root, work_dir, fx.T1_T4_IDS, tmp_path)
    dp_map = fx.attribution_from_done_proof(done_proof)
    rb_map = fx.attribution_from_red_baseline(verdict)
    for ac_id in fx.T1_T4_IDS:
        assert len(rb_map[ac_id]) == 1 and len(dp_map[ac_id]) == 1, (ac_id, rb_map, dp_map)
        assert fx.norm(rb_map[ac_id][0]) == fx.norm(dp_map[ac_id][0]), (ac_id, rb_map, dp_map)
        assert fx.nodeid_matches(rb_map[ac_id][0], expected[ac_id]), (ac_id, rb_map)


_MIXIN = """\
class SharedChecks:
    def test_shared(self):
        # covers: TQ-9020
        assert self.load() == 1


class TestA(SharedChecks):
    def load(self):
{a}


class TestB(SharedChecks):
    def load(self):
{b}
"""

_ONE = "        return 1"
_TWO = "        return 2"
_MISSING = "        import doesnotexist_tq500f3iii_mod\n        return doesnotexist_tq500f3iii_mod.value"


def _write_mixin(root, a_body, b_body):
    fx.init_packages(root, "unit_tests/build_orchestration")
    fx.write_pytest_ini(root)
    # not dedented through fx.write: the bodies carry their own indentation
    path = root / "unit_tests/build_orchestration/test_inherit.py"
    path.write_text(_MIXIN.format(a=a_body, b=b_body), encoding="utf-8")


def test_inherited_test_judged_across_every_inheriting_class(tmp_path):
    # covers: TQ-500f-3-iii
    # angle: boundary
    """test_shared is defined once in a mixin (one covers tag) and inherited,
    not overridden, by TestA and TestB. (a) one inheriting class fails, either
    one: not eligible, naming that class's nodeid; (b) both pass: eligible,
    judged on exactly two nodeids; (c) the entry declares must_catch, TestB's
    only red is an ImportError and TestA's an AssertionError: verify_red_baseline
    refuses it. In no case is the reason ambiguous_test_identity.

    Wrong versions caught: judged by only one subclass; nodeids collapsed (first
    or last wins); refused as ambiguous although it has one definition; an
    absence-only red in one inheriting class ignored for a declared test.
    """
    ac_ids = ("TQ-9020",)

    # (a) + (a'): the failing inheriting class is named, whichever one it is.
    for label, a_body, b_body, failing in (("B fails", _ONE, _TWO, "TestB"), ("A fails", _TWO, _ONE, "TestA")):
        base = tmp_path / label.replace(" ", "_")
        root = base / "repo"
        _write_mixin(root, a_body, b_body)
        ac_root = base / "ac_store"
        fx.write_ac_store(ac_root, ac_ids)
        verdict = fx.run_done_proof_driver(fx.SOURCE_SCRIPTS, ac_root, root, ac_ids, base)["TQ-9020"]
        assert verdict["eligible"] is False, (label, verdict)
        assert f"{failing}::test_shared" in verdict["reason"], (label, verdict)
        assert AMBIGUOUS not in verdict["reason"], (label, verdict)
        assert len(verdict["passing_tests"]) + len(verdict["failing_tests"]) == 2, (label, verdict)

    # (b) both pass: eligible, both inheriting nodeids judged.
    base = tmp_path / "both_pass"
    root = base / "repo"
    _write_mixin(root, _ONE, _ONE)
    ac_root = base / "ac_store"
    fx.write_ac_store(ac_root, ac_ids)
    verdict = fx.run_done_proof_driver(fx.SOURCE_SCRIPTS, ac_root, root, ac_ids, base)["TQ-9020"]
    assert verdict["eligible"] is True, verdict
    assert len(verdict["passing_tests"]) == 2 and not verdict["failing_tests"], verdict

    # (c) red-baseline, declared test, absence-only red in TestB: refused.
    base = tmp_path / "absence_in_b"
    ac_root = base / "ac_store"
    spec = {"TQ-9020": [{"name": "test_shared", "must_catch": ["judged by only one inheriting class"]}]}
    fx.write_ac_store(ac_root, ac_ids, work_status="todo", test_spec_by_id=spec)
    _, verdict = _red_baseline(base, ac_ids, ac_root, lambda w: _write_mixin(w, _TWO, _MISSING))
    assert verdict.get("reason") != AMBIGUOUS, verdict
    assert verdict.get("gate_passed") is False, verdict
    refused = [r.get("nodeid", "") for r in verdict.get("refused", [])]
    assert any("TestB::test_shared" in n for n in refused), verdict

    # (a) on the red-baseline lane: a failing inheriting class is plain red, never ambiguous.
    base = tmp_path / "rb_b_fails"
    ac_root = base / "ac_store"
    fx.write_ac_store(ac_root, ac_ids, work_status="todo")
    _, verdict = _red_baseline(base, ac_ids, ac_root, lambda w: _write_mixin(w, _ONE, _TWO))
    assert verdict.get("reason") != AMBIGUOUS, verdict
    assert verdict.get("gate_passed") is True, verdict
    assert any("TestB::test_shared" in e["nodeid"] for e in verdict.get("red", [])), verdict


def _write_duplicate_collection(root, *, passing: bool):
    """One tagged test collected twice (the same file under a second root)."""
    fx.init_packages(root, "unit_tests/ac_store")
    fx.write_pytest_ini(root)
    fx.write(
        root / "conftest.py",
        """\
        import copy


        def pytest_collection_modifyitems(items):
            items.extend(_second_root_copy(item) for item in list(items))


        def _second_root_copy(item):
            clone = copy.copy(item)
            clone._nodeid = "second_root/" + item.nodeid
            return clone
        """,
    )
    check = "assert 1 == 1" if passing else 'assert 1 == 2, "amb fails"'
    fx.write(
        root / "unit_tests/ac_store/test_dup.py",
        f"""\
        def test_amb():
            # covers: TQ-9030
            {check}
        """,
    )


def test_tag_without_unique_identity_is_refused_never_guessed(tmp_path):
    # covers: TQ-500f-3-iii
    # angle: failure
    """A tag whose test matches two result nodeids at full identity (the same
    file collected under two roots) is refused by verify_red_baseline with
    reason ambiguous_test_identity (gate does not pass), and the done-proof
    check refuses the covered requirement naming the tag and BOTH candidates --
    even when both candidates pass (never a guessed pass).

    Wrong versions caught: guessing instead of refusing; removing the
    ambiguous_test_identity refusal; refusing without naming every candidate.
    """
    first = "unit_tests/ac_store/test_dup.py::test_amb"
    second = "second_root/" + first
    ac_ids = ("TQ-9030",)

    # red-baseline lane (failing duplicate): refuse, do not guess.
    base = tmp_path / "rb"
    ac_root = base / "ac_store"
    fx.write_ac_store(ac_root, ac_ids, work_status="todo")
    _, verdict = _red_baseline(base, ac_ids, ac_root, lambda w: _write_duplicate_collection(w, passing=False))
    assert verdict.get("gate_passed") is False, verdict
    assert verdict.get("reason") == AMBIGUOUS, verdict

    # done-proof lane: refuse and name the tag and every candidate, pass or fail.
    for label, passing in (("failing", False), ("passing", True)):
        dbase = tmp_path / f"dp_{label}"
        root = dbase / "repo"
        _write_duplicate_collection(root, passing=passing)
        dac = dbase / "ac_store"
        fx.write_ac_store(dac, ac_ids)
        dp = fx.run_done_proof_driver(fx.SOURCE_SCRIPTS, dac, root, ac_ids, dbase)["TQ-9030"]
        assert dp["eligible"] is False, (label, dp)
        reason = fx.norm(dp["reason"])
        # *second* contains *first*, so count: both candidates must be named on their own
        assert "TQ-9030" in reason and second in reason and reason.count(first) >= 2, (label, dp)
