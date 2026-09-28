"""
MODULE: unit_tests/build_orchestration/test_tq500f3i_h1_kind_pairing_bug.py
GOAL: RED regression tests for pr-reviewer finding H-1 against the TQ-500f-3-i
    absence/assertion kind classifier (scripts/ac_store/_done_proof_kind_support.py
    ``_pair_failure_kinds_with_nodeids``).

THE BUG: the classifier pairs ``E   <ExceptionType>:`` lines scraped from a
    ``pytest -v --tb=line`` run's stdout POSITIONALLY against the ordered list
    of failing nodeids, and falls back to "no kinds determined for the whole
    batch" (an empty dict) whenever the two counts disagree:

        1. A bare ``assert x == 1`` (no message) prints ``E   assert 1 == 2``
           under ``--tb=line`` -- no colon after the first word, so the
           ``^E\\s+(\\w+):`` regex never matches this line at all. One fewer
           regex match than failing nodeid, so the WHOLE BATCH'S kinds
           collapse to ``{}`` -- every declared test in the batch becomes
           "undetermined", not just the bare-assert one.
        2. A chained exception (``raise X from Y``) prints TWO ``E   <Type>:``
           lines for ONE failing nodeid (the original cause, then the
           re-raised exception) -- again shifting every subsequent count out
           of alignment for the whole batch.

    Reproduced by pr-reviewer: T1 (declared, absence) + T2 (declared, bare
    assert) in one run -> kinds {}, red [], refused [], halt reason
    "all_new_tests_green_at_baseline" (a lie -- nothing was green; both were
    FAILED and silently dropped).

THE PINNED FIX this file's tests target:
    * A test's kind is classified from its FINAL raised exception only (the
      last ``E   <Type>:`` line in its own failure block) -- never a naive
      global positional zip. Chain depth or a message-less assert on ONE
      test must never corrupt classification for OTHER tests in the same
      batch.
    * A declared test whose kind genuinely cannot be determined must fail
      the gate closed with a DISTINCT reason -- this file pins
      ``"declared_test_kind_undetermined"`` (a proposed, stable token; any
      distinct reason satisfies TQ-500f-3-i's own "never silently drops it
      or reports green" requirement, but the assertions below need a
      concrete value to check against) -- never silently reported as
      "all_new_tests_green_at_baseline" or dropped with no trace at all.

AC: docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500f-3-i.yaml
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_MODULE_DIR = Path(__file__).resolve().parent.parent.parent / "scripts" / "build_orchestration"
sys.path.insert(0, str(_MODULE_DIR))

from fast_lane import verify_red_baseline  # noqa: E402

import unit_tests.build_orchestration._tq500f3i_fixtures as fx  # noqa: E402

REFUSAL_REASON = "declared_test_refused_absence_only_red"
UNDETERMINED_REASON = "declared_test_kind_undetermined"


class _H1Case(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)
        self.ac_root = self.tmp_root / "ac_store"

    def tearDown(self) -> None:
        self._tmp.cleanup()


class TestH1aMixedDeclaredBatchWithBareAssert(_H1Case):
    def test_h1a_declared_absence_plus_declared_bare_assert_in_one_batch(self) -> None:
        # covers: TQ-500f-3-i
        # angle: criterion
        """T1 (declared, function-level absence) + T2 (declared, bare
        ``assert x == 2`` with no message) in ONE batch: T1 is refused, T2
        stays red (kept, not dropped), and the gate fails closed with the
        REFUSAL reason -- never the misleading "all green" reason the bug
        reports, and never an empty refused/red pair for the whole batch.
        """
        ac_id = "TQ-H1A-001"
        t1_name = "test_t1_absence_declared"
        t2_name = "test_t2_bare_assert_declared"
        fx.write_ac_yaml(
            self.ac_root,
            ac_id,
            [
                {"name": t1_name, "must_catch": [fx.MUST_CATCH_REVERT_FIX]},
                {"name": t2_name, "must_catch": [fx.MUST_CATCH_REVERT_FIX]},
            ],
        )
        work_dir, _base_sha = fx.make_worktree(self.tmp_root)
        test_root = work_dir / "tests"
        fx.write(
            test_root / "test_t1.py",
            f"""\
            def {t1_name}():
                # covers: {ac_id}
                from doesnotexist_h1a_mod import thing
                thing()
            """,
        )
        fx.write(
            test_root / "test_t2.py",
            f"""\
            def {t2_name}():
                # covers: {ac_id}
                assert 1 == 2
            """,
        )

        verdict = verify_red_baseline(ac_ids=[ac_id], test_root=test_root, ac_root=self.ac_root)

        self.assertEqual(
            verdict.get("reason"),
            REFUSAL_REASON,
            f"T1's absence red must still be refused even with T2's bare "
            f"assert in the same batch -- got reason={verdict.get('reason')!r}, "
            f"NOT the misleading 'all_new_tests_green_at_baseline' the "
            f"positional-pairing bug produces; verdict={verdict!r}.",
        )
        self.assertIsNotNone(
            fx.find_by_name(verdict.get("refused"), t1_name),
            f"T1 must be refused; verdict={verdict!r}.",
        )
        self.assertIn(
            t2_name,
            fx.names(verdict.get("red")),
            f"T2 (bare assert, an assertion red) must be KEPT in 'red', not "
            f"silently dropped as undetermined; verdict={verdict!r}.",
        )
        self.assertFalse(verdict.get("gate_passed"))


class TestH1bBareAssertAlone(_H1Case):
    def test_h1b_declared_bare_assert_alone_is_accepted(self) -> None:
        # covers: TQ-500f-3-i
        # angle: boundary
        """A declared test whose ONLY red is a message-less bare
        ``assert x == 2`` (no colon-bearing exception-type line under
        --tb=line) is an ASSERTION red -- accepted, gate passes. The bug
        reads zero regex matches against one failing nodeid and drops it as
        undetermined instead.
        """
        ac_id = "TQ-H1B-001"
        t_name = "test_bare_assert_only_declared"
        fx.write_ac_yaml(
            self.ac_root, ac_id, [{"name": t_name, "must_catch": [fx.MUST_CATCH_REVERT_FIX]}]
        )
        work_dir, _base_sha = fx.make_worktree(self.tmp_root)
        test_root = work_dir / "tests"
        fx.write(
            test_root / "test_bare.py",
            f"""\
            def {t_name}():
                # covers: {ac_id}
                assert 1 == 2
            """,
        )

        verdict = verify_red_baseline(ac_ids=[ac_id], test_root=test_root, ac_root=self.ac_root)

        self.assertTrue(
            verdict.get("gate_passed") is True,
            f"A bare, message-less assert is a genuine assertion red and "
            f"must be accepted (gate_passed=True); verdict={verdict!r}.",
        )
        self.assertIn(t_name, fx.names(verdict.get("red")))
        self.assertEqual(verdict.get("refused"), [])


class TestH1cChainedExceptionFinalTypeRule(_H1Case):
    def test_h1c_chained_final_exception_is_assertion_stays_red(self) -> None:
        # covers: TQ-500f-3-i
        # angle: boundary
        """``raise AssertionError(...) from ImportError(...)``: the FINAL
        raised exception is AssertionError -- an assertion red, kept in
        'red', gate passes. Not refused merely because an ImportError sits
        earlier in the chain.
        """
        ac_id = "TQ-H1C-001"
        t_name = "test_chained_assertion_final"
        fx.write_ac_yaml(
            self.ac_root, ac_id, [{"name": t_name, "must_catch": [fx.MUST_CATCH_REVERT_FIX]}]
        )
        work_dir, _base_sha = fx.make_worktree(self.tmp_root)
        test_root = work_dir / "tests"
        fx.write(
            test_root / "test_chain_assert_final.py",
            f"""\
            def {t_name}():
                # covers: {ac_id}
                try:
                    raise ImportError("boom")
                except ImportError as exc:
                    raise AssertionError("wrapped") from exc
            """,
        )

        verdict = verify_red_baseline(ac_ids=[ac_id], test_root=test_root, ac_root=self.ac_root)

        self.assertTrue(
            verdict.get("gate_passed") is True,
            f"Final exception is AssertionError -- an assertion red, must "
            f"be accepted, not refused; verdict={verdict!r}.",
        )
        self.assertIn(t_name, fx.names(verdict.get("red")))
        self.assertEqual(verdict.get("refused"), [])

    def test_h1c_chained_final_exception_is_absence_is_refused(self) -> None:
        # covers: TQ-500f-3-i
        # angle: failure
        """``raise ImportError(...) from AssertionError(...)``: the FINAL
        raised exception is ImportError -- an absence red, refused.
        """
        ac_id = "TQ-H1C-002"
        t_name = "test_chained_import_final"
        fx.write_ac_yaml(
            self.ac_root, ac_id, [{"name": t_name, "must_catch": [fx.MUST_CATCH_REVERT_FIX]}]
        )
        work_dir, _base_sha = fx.make_worktree(self.tmp_root)
        test_root = work_dir / "tests"
        fx.write(
            test_root / "test_chain_import_final.py",
            f"""\
            def {t_name}():
                # covers: {ac_id}
                try:
                    raise AssertionError("boom")
                except AssertionError as exc:
                    raise ImportError("wrapped") from exc
            """,
        )

        verdict = verify_red_baseline(ac_ids=[ac_id], test_root=test_root, ac_root=self.ac_root)

        self.assertFalse(
            verdict.get("gate_passed"),
            f"Final exception is ImportError -- an absence red for a "
            f"declared test, must be refused; verdict={verdict!r}.",
        )
        self.assertEqual(verdict.get("reason"), REFUSAL_REASON)
        refused_entry = fx.find_by_name(verdict.get("refused"), t_name)
        self.assertIsNotNone(refused_entry, f"verdict={verdict!r}.")
        if refused_entry is not None:
            self.assertEqual(refused_entry.get("kind"), "absence")


class TestH1dUndeterminedKindFailsClosed(_H1Case):
    def test_h1d_declared_test_kind_undetermined_fails_closed_with_distinct_reason(self) -> None:
        # covers: TQ-500f-3-i
        # angle: failure
        """When a declared test's kind cannot be determined from the run's
        own output at all (simulated here at the seam
        ``_run_pytest_and_parse_with_kind`` -- the exact contract a genuinely
        ambiguous real run degrades to), the gate fails closed with a
        DISTINCT reason -- never silently drops the entry with no trace, and
        never reports the misleading "all_new_tests_green_at_baseline".
        """
        ac_id = "TQ-H1D-001"
        t_name = "test_kind_cannot_be_determined"
        fx.write_ac_yaml(
            self.ac_root, ac_id, [{"name": t_name, "must_catch": [fx.MUST_CATCH_REVERT_FIX]}]
        )
        work_dir, _base_sha = fx.make_worktree(self.tmp_root)
        test_root = work_dir / "tests"
        fx.write(
            test_root / "test_undetermined.py",
            f"""\
            def {t_name}():
                # covers: {ac_id}
                assert False
            """,
        )
        nodeid = f"{test_root / 'test_undetermined.py'}::{t_name}"

        with patch(
            "fast_lane._run_pytest_and_parse_with_kind",
            return_value=({nodeid: "FAILED"}, {}),
        ):
            verdict = verify_red_baseline(
                ac_ids=[ac_id], test_root=test_root, ac_root=self.ac_root
            )

        self.assertFalse(
            verdict.get("gate_passed"),
            f"An undetermined-kind declared test must fail the gate closed; "
            f"verdict={verdict!r}.",
        )
        self.assertEqual(
            verdict.get("reason"),
            UNDETERMINED_REASON,
            f"The reason must be a DISTINCT token naming the undetermined "
            f"kind -- never 'all_new_tests_green_at_baseline' (the entry was "
            f"FAILED, not green) and never 'no_red_outcome_among_new_tests' "
            f"(that reason means literally nothing was red, which is false "
            f"here); verdict={verdict!r}.",
        )
        self.assertNotIn(
            t_name,
            fx.names(verdict.get("green_at_baseline")),
            f"An undetermined-kind FAILED test must never be reported as "
            f"green; verdict={verdict!r}.",
        )


if __name__ == "__main__":
    unittest.main()
