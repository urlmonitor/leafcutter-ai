"""
MODULE: unit_tests/build_orchestration/test_tq500f3i_h2_declared_name_matching_bug.py
GOAL: RED regression tests for pr-reviewer finding H-2 against the TQ-500f-3-i
    declared-name matching in
    scripts/build_orchestration/_fl_red_baseline_support.py
    ``_refuse_absence_only_declared_reds``.

THE BUG: declared-name matching compares the BARE ``test_spec[].name`` string
    against ``nodeid.rsplit("::", 1)[-1]`` verbatim. A parametrized test's
    trailing nodeid segment carries its parametrize id in brackets --
    ``test_t1[case0]`` -- which never equals the bare declared name
    ``test_t1``, so a parametrized declared test is SILENTLY ACCEPTED as
    ordinary red evidence instead of refused. Class-based nodeids
    (``TestX::test_y``) happen to still work today (rsplit's LAST segment is
    already just ``test_y``) -- pinned here as a control the eventual fix
    must not regress while it learns to strip parametrize brackets.

    Two further gaps in the same declared-name matching layer, not caused by
    the bracket-stripping bug itself but by the same "silent miss" failure
    mode: a declared test_spec entry with NO corresponding newly-added test
    at all contributes nothing and is never flagged: the gate can pass on an
    unrelated red test while the SPECIFIC wrong-version guard the ticket
    claims to have written was never actually written. And when --ac-root is
    supplied but the named AC record cannot be loaded at all, the declared
    set silently becomes empty (fail OPEN) instead of failing the gate
    closed -- an unreadable declaration is treated exactly like no
    declaration at all, which is the opposite of TQ-500f-3-i's own
    fail-closed posture ("a declared test whose kind of red cannot be
    determined is not accepted as red evidence").

AC: docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500f-3-i.yaml
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_MODULE_DIR = Path(__file__).resolve().parent.parent.parent / "scripts" / "build_orchestration"
sys.path.insert(0, str(_MODULE_DIR))

from fast_lane import verify_red_baseline  # noqa: E402

import unit_tests.build_orchestration._tq500f3i_fixtures as fx  # noqa: E402

REFUSAL_REASON = "declared_test_refused_absence_only_red"
# Proposed, stable tokens this file pins for the two new fail-closed gaps
# (H-2 c/d) -- any distinct reason satisfies the AC's fail-closed posture,
# but the assertions below need concrete values to check against.
DECLARED_MISSING_REASON = "declared_test_missing_no_matching_test"
AC_RECORD_UNAVAILABLE_REASON = "declared_ac_record_unavailable"


class _H2Case(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)
        self.ac_root = self.tmp_root / "ac_store"

    def tearDown(self) -> None:
        self._tmp.cleanup()


class TestH2aParametrizedDeclaredNotMatched(_H2Case):
    def test_h2a_parametrized_declared_absence_only_test_is_refused(self) -> None:
        # covers: TQ-500f-3-i
        # angle: boundary
        """A declared (must_catch) test written with
        ``@pytest.mark.parametrize`` -- nodeid ``test_param[case0]`` -- whose
        only red is a function-level absence must be REFUSED exactly like an
        unparametrized declared test. The bug's bare-name comparison misses
        the bracketed suffix and silently accepts it instead.
        """
        ac_id = "TQ-H2A-001"
        t_name = "test_param_absence_declared"
        fx.write_ac_yaml(
            self.ac_root, ac_id, [{"name": t_name, "must_catch": [fx.MUST_CATCH_REVERT_FIX]}]
        )
        work_dir, _base_sha = fx.make_worktree(self.tmp_root)
        test_root = work_dir / "tests"
        fx.write(
            test_root / "test_param.py",
            f"""\
            import pytest

            @pytest.mark.parametrize("case", ["case0"])
            def {t_name}(case):
                # covers: {ac_id}
                from doesnotexist_h2a_mod import thing
                thing()
            """,
        )

        verdict = verify_red_baseline(ac_ids=[ac_id], test_root=test_root, ac_root=self.ac_root)

        refused_names = {
            e.get("nodeid", "").rsplit("::", 1)[-1] for e in verdict.get("refused") or []
        }
        self.assertTrue(
            any(name.startswith(t_name) for name in refused_names),
            f"The parametrized declared test ({t_name}[case0]) must be "
            f"refused -- the parametrize suffix must not defeat declared-"
            f"name matching; verdict={verdict!r}.",
        )
        self.assertFalse(verdict.get("gate_passed"))
        self.assertEqual(verdict.get("reason"), REFUSAL_REASON)


class TestH2bClassBasedStillMatches(_H2Case):
    def test_h2b_class_based_declared_test_is_matched_by_bare_name(self) -> None:
        # covers: TQ-500f-3-i
        # angle: criterion
        """CONTROL: a class-based test (nodeid ``TestX::test_y``) declared
        by its bare method name ``test_y`` must still be refused when its
        only red is absence -- proving the eventual bracket-stripping fix
        does not regress this already-working case.
        """
        ac_id = "TQ-H2B-001"
        t_name = "test_y_absence_declared"
        fx.write_ac_yaml(
            self.ac_root, ac_id, [{"name": t_name, "must_catch": [fx.MUST_CATCH_REVERT_FIX]}]
        )
        work_dir, _base_sha = fx.make_worktree(self.tmp_root)
        test_root = work_dir / "tests"
        fx.write(
            test_root / "test_classbased.py",
            f"""\
            class TestX:
                def {t_name}(self):
                    # covers: {ac_id}
                    from doesnotexist_h2b_mod import thing
                    thing()
            """,
        )

        verdict = verify_red_baseline(ac_ids=[ac_id], test_root=test_root, ac_root=self.ac_root)

        self.assertIsNotNone(
            fx.find_by_name(verdict.get("refused"), t_name),
            f"A class-based declared test must still be matched and refused "
            f"by its bare method name; verdict={verdict!r}.",
        )
        self.assertFalse(verdict.get("gate_passed"))


class TestH2cDeclaredButNeverWritten(_H2Case):
    def test_h2c_declared_test_with_no_matching_new_test_fails_closed(self) -> None:
        # covers: TQ-500f-3-i
        # angle: failure
        """The AC declares (must_catch) a test named ``test_declared_but_
        absent`` that NO newly-added covering test actually implements --
        only an unrelated, undeclared red test exists in the batch. The gate
        must fail closed with a DISTINCT reason naming the missing
        declaration, not silently pass on the unrelated red test as if
        nothing had been declared at all.
        """
        ac_id = "TQ-H2C-001"
        missing_name = "test_declared_but_absent"
        other_name = "test_other_ordinary_red"
        fx.write_ac_yaml(
            self.ac_root,
            ac_id,
            [{"name": missing_name, "must_catch": [fx.MUST_CATCH_REVERT_FIX]}],
        )
        work_dir, _base_sha = fx.make_worktree(self.tmp_root)
        test_root = work_dir / "tests"
        fx.write(
            test_root / "test_other.py",
            f"""\
            def {other_name}():
                # covers: {ac_id}
                assert False, "unrelated ordinary red, not the declared guard"
            """,
        )

        verdict = verify_red_baseline(ac_ids=[ac_id], test_root=test_root, ac_root=self.ac_root)

        self.assertFalse(
            verdict.get("gate_passed"),
            f"A declared test_spec entry with no corresponding newly-added "
            f"test at all must fail the gate closed rather than silently "
            f"pass on an unrelated red test; verdict={verdict!r}.",
        )
        self.assertEqual(
            verdict.get("reason"),
            DECLARED_MISSING_REASON,
            f"The reason must be a DISTINCT token naming the missing "
            f"declared test, not the generic absence-refusal reason (no "
            f"absence red was even observed here) and not None; "
            f"verdict={verdict!r}.",
        )


class TestH2dUnloadableAcRecordFailsClosed(_H2Case):
    def test_h2d_ac_root_given_but_record_unloadable_fails_closed(self) -> None:
        # covers: TQ-500f-3-i
        # angle: failure
        """--ac-root is supplied (opting into TQ-500f-3-i's rule), but the
        named AC's YAML record does not exist in that store at all. The
        gate must fail closed -- never silently treat "record unloadable"
        the same as "nothing was declared", which would let a genuinely
        undeclared-looking absence red through unchallenged when the real
        declaration (unreadable) might have refused it.
        """
        ac_id = "TQ-H2D-001"  # deliberately never written to self.ac_root
        self.ac_root.mkdir(parents=True, exist_ok=True)
        t_name = "test_absence_under_unloadable_ac"
        work_dir, _base_sha = fx.make_worktree(self.tmp_root)
        test_root = work_dir / "tests"
        fx.write(
            test_root / "test_unloadable.py",
            f"""\
            def {t_name}():
                # covers: {ac_id}
                from doesnotexist_h2d_mod import thing
                thing()
            """,
        )

        verdict = verify_red_baseline(ac_ids=[ac_id], test_root=test_root, ac_root=self.ac_root)

        self.assertFalse(
            verdict.get("gate_passed"),
            f"--ac-root supplied but the AC record cannot be loaded must "
            f"fail the gate closed, never silently accept the absence red "
            f"as if nothing were declared; verdict={verdict!r}.",
        )
        self.assertEqual(
            verdict.get("reason"),
            AC_RECORD_UNAVAILABLE_REASON,
            f"The reason must be a DISTINCT token naming the unloadable AC "
            f"record; verdict={verdict!r}.",
        )


if __name__ == "__main__":
    unittest.main()
