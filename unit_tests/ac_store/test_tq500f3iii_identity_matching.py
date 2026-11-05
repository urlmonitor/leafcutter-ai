"""
MODULE: unit_tests/ac_store/test_tq500f3iii_identity_matching.py
GOAL: RED tests for TQ-500f-3-iii -- a covering tag is matched to the ONE test
    it sits on (full identity: path within the test root + class chain +
    function name), so two tests sharing a name never lend each other their
    result.
AC: docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500f-3-iii.yaml

Every test here is declared with ``must_catch`` or ``angle: discrimination`` in
the AC's test_spec, so each must fail by REACHING the existing production code
(done_proof.verify_done_eligible, the check_done_proof hook) and observing the
collapsed verdict -- never by importing a name that does not exist yet. The
new shared-matcher module's name is not pinned by the AC; its existence is
proven through behaviour (same verdicts via both lanes, the deployed copies
importing it cleanly), not by importing it here.

Fixtures are real test files run by the real pytest (nodeids from real pytest
output) and AC records from yaml.safe_dump.
"""

from __future__ import annotations

import subprocess
import sys

from unit_tests.ac_store import _tq500f3iii_fixtures as fx

_DONE_PROOF_REASON_AMBIGUOUS = "ambiguous_test_identity"


def _forward(tmp_path):
    root = tmp_path / "repo"
    expected = fx.build_collision_repo(root)
    ac_root = tmp_path / "ac_store"
    fx.write_ac_store(ac_root, fx.T1_T4_IDS)
    return root, ac_root, expected


def _judge(tmp_path, root, ac_root, ac_ids=fx.T1_T4_IDS):
    return fx.run_done_proof_driver(fx.SOURCE_SCRIPTS, ac_root, root, ac_ids, tmp_path)


def test_full_identity_matching_separates_same_name_tests(tmp_path):
    # covers: TQ-500f-3-iii
    # angle: criterion
    """T1/T2 (one file, two classes, one function name) and T3/T4 (same file
    basename in two packages, one function name) are each judged on their OWN
    result: T1 and T4 (failing) not eligible, T2 and T3 (passing) eligible, and
    every tag resolves to exactly one nodeid -- its own.

    Wrong versions caught: match by file basename + function name; match by bare
    function name ignoring the class; first/last result wins on a collision.
    """
    root, ac_root, expected = _forward(tmp_path)
    verdicts = _judge(tmp_path, root, ac_root)

    assert fx.eligible_map(verdicts) == fx.EXPECTED_ELIGIBLE, verdicts
    attribution = fx.attribution_from_done_proof(verdicts)
    for ac_id, want in expected.items():
        got = attribution[ac_id]
        assert len(got) == 1 and fx.nodeid_matches(got[0], want), (ac_id, got, want)
    for ac_id, verdict in verdicts.items():
        assert _DONE_PROOF_REASON_AMBIGUOUS not in str(verdict.get("reason", "")), (ac_id, verdict)
    # control: the failing T1 is refused naming ITS class, not the passing sibling's
    assert "TestRetryGate" in verdicts[fx.T1]["reason"] and "TestExportGate" not in verdicts[fx.T1]["reason"]


def test_done_proof_entry_point_judges_colliding_tags_by_full_identity(tmp_path):
    # covers: TQ-500f-3-iii
    # angle: reachability
    """The check_done_proof hook (production entry point, subprocess, ci mode)
    over the real T1..T4 files and a real AC store flags exactly TQ-9001 and
    TQ-9004 and exits 1; TQ-9002 and TQ-9003 are not flagged. The exit code and
    the violation lines are the consumed result.

    Wrong versions caught: done_proof keeps its old in-file matcher and never
    calls the shared module; match by file basename + function name.
    """
    root, ac_root, _ = _forward(tmp_path)
    proc = fx.run_check_done_proof_ci(fx.SOURCE_CHECK_DONE_PROOF, ac_root, root)

    assert fx.violated_ids(proc) == {fx.T1, fx.T4}, (proc.stdout, proc.stderr[-800:])
    assert proc.returncode == 1


def test_deployed_done_proof_and_fast_lane_import_shared_matcher(tmp_path):
    # covers: TQ-500f-3-iii
    # angle: deployed
    """build.py into a temp target; in fresh subprocesses the DEPLOYED
    done_proof and the DEPLOYED fast_lane.py verify_red_baseline both run over
    the T1..T4 fixture without ModuleNotFoundError and give the verdicts the
    criteria state (T1/T4 not eligible and red; T2/T3 eligible and green).

    Wrong version caught: the new matcher module missing from the build deploy
    map (the deployed gate would die on import).
    """
    target = tmp_path / "deploy"
    target.mkdir()
    build = subprocess.run(
        [sys.executable, str(fx.REPO_ROOT / "scripts" / "build.py"), "--target-dir", str(target)],
        capture_output=True, text=True, timeout=600, cwd=str(fx.REPO_ROOT),
    )
    assert build.returncode == 0, build.stderr[-1500:]
    deployed_scripts = target / ".leafcutter" / "scripts"
    assert (deployed_scripts / "ac_store" / "done_proof.py").is_file()

    root, ac_root, expected = _forward(tmp_path)
    verdicts = fx.run_done_proof_driver(deployed_scripts, ac_root, root, fx.T1_T4_IDS, tmp_path)
    assert fx.eligible_map(verdicts) == fx.EXPECTED_ELIGIBLE, verdicts

    # red-baseline lane: needs a git worktree whose tests are newly added
    from unit_tests.build_orchestration import _tq500f3i_fixtures as gfx

    work_dir, base_sha = gfx.make_worktree(tmp_path / "git")
    fx.build_collision_repo(work_dir)
    verdict = fx.run_verify_red_baseline(
        deployed_scripts / "build_orchestration" / "fast_lane.py", fx.T1_T4_IDS, work_dir, ac_root, base_ref=base_sha
    )
    assert verdict.get("reason") != _DONE_PROOF_REASON_AMBIGUOUS, verdict
    red = fx.entry_nodeids(verdict.get("red"))
    green = fx.entry_nodeids(verdict.get("green_at_baseline"))
    assert set(red) == {fx.T1, fx.T4} and set(green) == {fx.T2, fx.T3}, verdict
    for ac_id, nodeids in {**red, **green}.items():
        assert len(nodeids) == 1 and fx.nodeid_matches(nodeids[0], expected[ac_id]), (ac_id, nodeids)


def test_verdicts_unchanged_when_run_reports_tests_in_reverse_order(tmp_path):
    # covers: TQ-500f-3-iii
    # angle: discrimination
    """Forward and reversed arrangements of the T1..T4 results (classes swapped
    in the file; T3/T4 swapped between the two packages, so pytest reports them
    in the opposite order) give identical verdicts and each tag keeps resolving
    to its own single nodeid.

    Wrong versions caught: order-dependent verdict; last result wins; first
    result wins.
    """
    results = {}
    for name, reverse in (("forward", False), ("reversed", True)):
        base = tmp_path / name
        root = base / "repo"
        expected = fx.build_collision_repo(root, reverse=reverse)
        ac_root = base / "ac_store"
        fx.write_ac_store(ac_root, fx.T1_T4_IDS)
        verdicts = fx.run_done_proof_driver(fx.SOURCE_SCRIPTS, ac_root, root, fx.T1_T4_IDS, base)
        attribution = fx.attribution_from_done_proof(verdicts)
        for ac_id, want in expected.items():
            assert len(attribution[ac_id]) == 1 and fx.nodeid_matches(attribution[ac_id][0], want), (name, ac_id, attribution)
        results[name] = fx.eligible_map(verdicts)

    assert results["forward"] == fx.EXPECTED_ELIGIBLE, results
    assert results["reversed"] == fx.EXPECTED_ELIGIBLE, results
    # the matcher itself, fed one run's results in both report orders
    _assert_matcher_order_independent(tmp_path / "order")


def test_parametrised_same_name_tests_judged_per_identity_across_all_cases(tmp_path):
    # covers: TQ-500f-3-iii
    # angle: boundary
    """Two parametrised tests with one function name in two classes of one
    file: class A has one failing case among passing ones, class B's cases all
    pass. Only A's requirement is refused (naming the failing case); B's is
    eligible and is judged across exactly its own three cases.

    Wrong versions caught: only the first reported parametrised case is read
    (ACS-200f-2 regression); B's cases are counted toward A's tag.
    """
    root = tmp_path / "repo"
    fx.init_packages(root, "unit_tests/ac_store")
    fx.write_pytest_ini(root)
    fx.write(
        root / "unit_tests/ac_store/test_cases.py",
        """\
        import pytest


        class TestAlpha:
            @pytest.mark.parametrize("n", [1, 2, 3])
            def test_handles_case(self, n):
                # covers: TQ-9011
                assert n != 2


        class TestBeta:
            @pytest.mark.parametrize("n", [1, 2, 3])
            def test_handles_case(self, n):
                # covers: TQ-9012
                assert n > 0
        """,
    )
    ac_root = tmp_path / "ac_store"
    fx.write_ac_store(ac_root, ("TQ-9011", "TQ-9012"))
    verdicts = _judge(tmp_path, root, ac_root, ("TQ-9011", "TQ-9012"))

    assert fx.eligible_map(verdicts) == {"TQ-9011": False, "TQ-9012": True}, verdicts
    reason = verdicts["TQ-9011"]["reason"]
    assert "TestAlpha" in reason and "[2]" in reason and "TestBeta" not in reason, reason
    beta = verdicts["TQ-9012"]
    assert len(beta["passing_tests"]) == 3 and not beta["failing_tests"], beta
    assert all("TestBeta" in n for n in beta["passing_tests"]), beta


# --- H-1: nodeids with ``..`` components (test files outside the pytest rootdir) ---

_OUTSIDE_SOURCE = """\
class TestAbsence:
    def test_shared_name(self):
        # covers: TQ-9021
        assert False, "absence-side"


class TestAssertion:
    def test_shared_name(self):
        # covers: TQ-9022
        assert False, "assertion-side"
"""


def _outside_rootdir_case(tmp_path, sep):
    """A real test file written under ``work/tests`` and nodeids spelled the way
    pytest spells them when its rootdir is a SIBLING directory: a ``..``-relative
    path (relpath from the rootdir to the file), joined with *sep*."""
    import os
    from pathlib import Path

    from scripts.ac_store import covers_tag_identity as cti

    test_file = tmp_path / "work" / "tests" / "test_s.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text(_OUTSIDE_SOURCE, encoding="utf-8")
    rel = os.path.relpath(test_file, tmp_path / "rootdir" / "sub").replace(os.sep, sep)
    assert rel.startswith(".."), rel
    results = {f"{rel}::TestAbsence::test_shared_name": "FAILED", f"{rel}::TestAssertion::test_shared_name": "PASSED"}
    return cti, Path(test_file), results


def _tag(test_file, ac_id, line):
    return {"ac_id": ac_id, "file": test_file, "function": "test_shared_name", "location": f"{test_file}:{line}"}


def _assert_each_tag_resolves_to_its_own_test(cti, test_file, results):
    own = {"TQ-9021": "TestAbsence", "TQ-9022": "TestAssertion"}
    for ac_id, line in (("TQ-9021", 4), ("TQ-9022", 10)):
        units, ambiguous = cti.resolve_tag(_tag(test_file, ac_id, line), results)
        assert not ambiguous, (ac_id, ambiguous)
        assert len(units) == 1 and len(units[0]) == 1 and f"::{own[ac_id]}::" in units[0][0], (ac_id, units)
    passing, failing = cti.judge_tag(_tag(test_file, "TQ-9021", 4), results)
    assert not passing and len(failing) == 1 and "TestAbsence" in failing[0], (passing, failing)
    passing, failing = cti.judge_tag(_tag(test_file, "TQ-9022", 10), results)
    assert len(passing) == 1 and "TestAssertion" in passing[0] and not failing, (passing, failing)


def test_dotdot_relative_windows_nodeids_resolve_each_tag_to_its_own_test(tmp_path):
    # covers: TQ-500f-3-iii
    # angle: boundary
    """pytest run with a rootdir that is a sibling of the tagged file reports
    ``..`` + backslash-separated work, tests and test_s.py nodeid parts (Windows form).
    Each of the two same-named tags resolves to its OWN single test, never
    ``ambiguous_test_identity``.

    Wrong version caught: ``_same_file`` treats a ``..``-prefixed nodeid path as
    a different file and falls back to name-only matching.
    """
    cti, test_file, results = _outside_rootdir_case(tmp_path, "\\")
    _assert_each_tag_resolves_to_its_own_test(cti, test_file, results)


def test_dotdot_relative_posix_nodeids_resolve_each_tag_to_its_own_test(tmp_path):
    # covers: TQ-500f-3-iii
    # angle: boundary
    """Same as the Windows case with POSIX separators:
    ``../work/tests/test_s.py::TestAbsence::test_shared_name``.

    Wrong version caught: ``..`` components compared literally against the
    tagged file's path components.
    """
    cti, test_file, results = _outside_rootdir_case(tmp_path, "/")
    _assert_each_tag_resolves_to_its_own_test(cti, test_file, results)


_ORDER_SOURCE = """class _Mixin:
    def test_inh(self):
        pass


class TestA(_Mixin):
    pass


class TestB(_Mixin):
    pass
"""


def _assert_matcher_order_independent(tmp_path):
    """An inherited, parametrised test (two collected classes, two non-passing
    cases each with different outcomes) resolves and is judged identically
    whether the run reports its results forwards or backwards: the same units in
    the same order and the same case standing for each class."""
    from pathlib import Path

    from scripts.ac_store import covers_tag_identity as cti

    test_file = tmp_path / "tests" / "test_o.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text(_ORDER_SOURCE, encoding="utf-8")
    tag = {"ac_id": "TQ-9040", "file": Path(test_file), "function": "test_inh", "location": f"{test_file}:2"}
    forward = {
        "tests/test_o.py::TestA::test_inh[p1]": "FAILED",
        "tests/test_o.py::TestA::test_inh[p2]": "ERROR",
        "tests/test_o.py::TestB::test_inh[p1]": "ERROR",
        "tests/test_o.py::TestB::test_inh[p2]": "FAILED",
    }
    backward = dict(reversed(list(forward.items())))
    seen = []
    for results in (forward, backward):
        units, ambiguous = cti.resolve_tag(tag, results)
        assert not ambiguous and len(units) == 2, (units, ambiguous)
        seen.append((units, [cti.aggregate_unit(c, results) for c in units], cti.judge_tag(tag, results)))
    assert seen[0] == seen[1], seen
