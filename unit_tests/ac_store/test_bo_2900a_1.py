"""
MODULE: unit_tests/ac_store/test_bo_2900a_1.py
COVERS: BO-2900a-1

GOAL: RED test stubs for BO-2900a-1 -- "A proof that reached the code by
    direct import does not make a criterion done when the code has a real
    way in".

=== AC under test ===

    id: BO-2900a-1 (L2, build-orchestration)
    Given an acceptance criterion whose implementing code lives in a unit
    that exposes a runtime way in -- a module-level ``main(argv)`` an
    operator invokes with a named action -- and the criterion's
    covers-tagged proof test is present, executes real code, and passes,
    and that test reaches the implementing function by importing it
    directly, so the way in is never entered while the test runs,
    then the criterion is rejected as not eligible, and the rejection names
    the unit, the un-entered way in, and the offending test; and with no
    other change to the code and no additional assertion, the same
    criterion becomes eligible once the proof instead drives the same
    behaviour through the way in; and a unit that exposes no way in at all
    is not judged by this rule.

=== Interface contract under test ===

    Location: scripts/ac_store/done_proof.py

        verify_done_eligible(ac_id, *, ac_root, test_root) -> dict

    NO new keyword argument is introduced by this AC -- unlike its sibling
    BO-2900a-1-i (opt-in ``reachability_spec=``), this rule must fire
    MECHANICALLY, with the exact call signature check_done_proof.py already
    uses today (``verify_done_eligible(ac_id, ac_root=ac_root,
    test_root=test_root)`` -- see .leafcutter/scripts/commit_guardian/
    check_done_proof.py:755 and :830, neither of which passes
    reachability_spec).

    "The unit exposes a runtime way in" is decided mechanically (AC
    constraints): the module holding the implementing code -- here, the SAME
    file as the covers-tagged proof test, matching this AC family's
    single-file fixture convention (test_bo2900a_1_i_reached_through.py) --
    defines a module-level callable ``main(argv)``. When it does, and the
    covers-tagged proof test's own run never enters that ``main``, the
    criterion is refused with the NEW-this-AC ``refusal_cause``
    "proof_not_through_entry_point" and a reason naming "direct import".

Returned dict gains three new keys, additive only (existing
``eligible``/``reason``/``passing_tests``/``failing_tests``/``dangling_tags``
unchanged per the delivers_to contract):

    "unit"           str | None  -- the unit that was never entered.
    "entry_point"    str | None  -- the un-entered "<module>:main".
    "offending_test" str | None  -- nodeid of the test that reached the
                                    code by direct import instead.

=== File split note ===

    This file originally held five tests (the reachability CLI test and the
    cross-file fixture pushed it to 426 content-lines, over
    check_file_size.py's 400-line new-file limit). Tests 4-6 now live in
    the sibling unit_tests/ac_store/test_bo_2900a_1_ii.py; shared fixture
    helpers live in unit_tests/ac_store/_bo_2900a_1_fixtures.py. This file
    keeps only tests 1-3 (the same-file fixture convention core cases).

=== Fixture authenticity mandate ===

  All AC YAML fixtures are written with ``yaml.safe_dump`` (never a
  hand-typed YAML literal). All fixture "command surface" modules are real,
  importable .py files with a genuine ``argparse``-based ``main(argv)``
  dispatcher -- reachability is exercised by ACTUALLY calling ``main()`` (or
  the implementing function directly), never asserted from a hand-fed
  boolean.

=== Red baseline ===

  Tests 1-3 call the REAL, UNMODIFIED ``verify_done_eligible`` with no
  ``reachability_spec`` argument -- exactly as every real caller does today.
  Today, with no reachability_spec supplied, verify_done_eligible applies
  only the pre-existing pass/fail gate: both fixtures' proof tests PASS, so
  today's (pre-implementation) verdict is ``eligible: True`` for BOTH the
  direct-import fixture (test 1, wrongly -- red) and the entry-point-driven
  fixture (test 2, coincidentally correctly). Test 3's own invariant ("this
  rule never fires for a no-way-in unit") also coincidentally holds today,
  since no mechanism exists yet to fire it at all.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bo_2900a_1_fixtures import write_ac, write_fixture_file  # noqa: E402

from done_proof import verify_done_eligible  # noqa: E402

# BO-2900a-1's rule was SUSPENDED to report-only on 2026-09-30 (see
# scripts/ac_store/_done_proof_entry_point_gate.py DECISION HISTORY): it announces
# its findings and returns the verdict unchanged, so nothing it judges is refused.
# The assertions below state what a-1 REQUIRES, which is currently unmet -- a-1 is
# `work_status: todo` for exactly that reason. They are marked expected-failure
# rather than rewritten, because rewriting them to assert the weaker report-only
# behaviour would erase the record of what a-1 actually demands.
#
# These markers are SELF-CLEANING and must not be made lenient: `expectedFailure`
# reports an unexpected PASS as a failure, so re-arming the rule turns this file red
# until the markers are removed. That is the intended signal. CI runs with
# AC_ENFORCE_STRICT=1 (.github/workflows/ci.yml), so the AC-enforcement plugin does
# NOT mask these on the strength of a-1 being todo -- the marker is what keeps the
# required pytest gate honest and green at the same time.
_SUSPENDED_RULE = "BO-2900a-1 rule suspended to report-only; see a-1-ii / a-1-iii"


# ---------------------------------------------------------------------------
# Test 1 -- direct-import proof over a unit with a genuine entry point
# ---------------------------------------------------------------------------


class TestDirectImportProofIsRefusedWhenUnitHasAnEntryPoint(unittest.TestCase):
    """BO-2900a-1 core case: the way in is never entered, so the criterion
    is refused even though the proof executes real code and passes."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.fixture_ac_id = "BO-TEST-2900A1-DIRECT"
        write_ac(self.ac_root, self.fixture_ac_id)
        self.module_name = "test_bo2900a1_direct_import_fixture"
        write_fixture_file(
            self.test_root,
            f"{self.module_name}.py",
            f"""\
            import argparse


            def _run_the_task():
                \"\"\"The implementing code under proof -- must NOT be reached
                by direct import in this fixture.\"\"\"
                return "task-complete"


            def main(argv=None):
                parser = argparse.ArgumentParser(prog="fixture-unit")
                parser.add_argument("action")
                args = parser.parse_args(argv)
                if args.action == "run":
                    return _run_the_task()
                return None


            # covers: {self.fixture_ac_id}
            def test_proof_imports_the_function_directly():
                result = _run_the_task()
                assert result == "task-complete"
            """,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    @unittest.expectedFailure  # _SUSPENDED_RULE
    def test_direct_import_proof_is_refused_when_unit_has_an_entry_point(self) -> None:
        # covers: BO-2900a-1
        # angle: criterion
        """AC BO-2900a-1: main(argv) exists, the proof never calls it => ineligible.

        The fixture proof test direct-imports and calls ``_run_the_task``
        without ever going through ``main``. Because the fixture module
        defines a genuine argparse ``main(argv)``, verify_done_eligible must
        mechanically detect the entry point and refuse eligibility, naming
        the unit, the un-entered entry point, and the offending test.
        """
        verdict = verify_done_eligible(
            self.fixture_ac_id,
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        self.assertFalse(
            verdict.get("eligible"),
            f"expected ineligible (reached by direct import), got: {verdict}",
        )
        reason = verdict.get("reason", "").lower()
        self.assertIn("direct import", reason)
        self.assertEqual(
            verdict.get("refusal_cause"),
            "proof_not_through_entry_point",
            f"expected the BO-2900e-1 'proof_not_through_entry_point' cause, got: {verdict}",
        )
        self.assertTrue(
            verdict.get("unit"),
            f"verdict must name the unit that was never entered, got: {verdict}",
        )
        self.assertIn(self.module_name, str(verdict.get("unit", "")))
        entry_point = verdict.get("entry_point") or ""
        self.assertIn(
            "main",
            entry_point,
            f"verdict must name the un-entered entry point, got: {verdict}",
        )
        offending_test = verdict.get("offending_test") or ""
        self.assertIn(
            "test_proof_imports_the_function_directly",
            offending_test,
            f"verdict must name the offending test nodeid, got: {verdict}",
        )


# ---------------------------------------------------------------------------
# Test 2 -- identical unit, proof rewritten to drive the entry point
# ---------------------------------------------------------------------------


class TestSameCriterionBecomesEligibleOnceTheProofDrivesTheEntryPoint(unittest.TestCase):
    """Same fixture surface; the proof now invokes main() with a real action."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.fixture_ac_id = "BO-TEST-2900A1-VIAMAIN"
        write_ac(self.ac_root, self.fixture_ac_id)
        self.module_name = "test_bo2900a1_via_main_fixture"
        write_fixture_file(
            self.test_root,
            f"{self.module_name}.py",
            f"""\
            import argparse


            def _run_the_task():
                \"\"\"The implementing code under proof -- IS reached, through
                main(), in this fixture.\"\"\"
                return "task-complete"


            def main(argv=None):
                parser = argparse.ArgumentParser(prog="fixture-unit")
                parser.add_argument("action")
                args = parser.parse_args(argv)
                if args.action == "run":
                    return _run_the_task()
                return None


            # covers: {self.fixture_ac_id}
            def test_proof_invokes_the_entry_point():
                result = main(["run"])
                assert result == "task-complete"
            """,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_same_criterion_becomes_eligible_once_the_proof_drives_the_entry_point(
        self,
    ) -> None:
        # covers: BO-2900a-1
        # angle: criterion
        """AC BO-2900a-1: invoking main() with the real action makes the
        identical criterion eligible, with no code change and no added
        assertion -- only the proof's own invocation shape differs from
        test 1 above."""
        verdict = verify_done_eligible(
            self.fixture_ac_id,
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        self.assertTrue(
            verdict.get("eligible"),
            f"expected eligible (entry point driven), got: {verdict}",
        )
        self.assertEqual(verdict.get("reason", ""), "")
        self.assertIsNone(verdict.get("refusal_cause"))


# ---------------------------------------------------------------------------
# Test 3 -- a unit with no entry point at all is not judged by this rule
# ---------------------------------------------------------------------------


class TestUnitWithNoEntryPointIsNotJudgedByThisRule(unittest.TestCase):
    """The scope fence: no main(argv) anywhere means this rule never fires."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.fixture_ac_id = "BO-TEST-2900A1-NOENTRY"
        write_ac(self.ac_root, self.fixture_ac_id)
        self.module_name = "test_bo2900a1_no_entry_point_fixture"
        write_fixture_file(
            self.test_root,
            f"{self.module_name}.py",
            f"""\
            def _do_the_thing():
                \"\"\"The implementing code under proof -- no way in exists
                anywhere in this fixture unit.\"\"\"
                return "done"


            # covers: {self.fixture_ac_id}
            def test_proof_imports_the_function_directly():
                result = _do_the_thing()
                assert result == "done"
            """,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_unit_with_no_entry_point_is_not_judged_by_this_rule(self) -> None:
        # covers: BO-2900a-1
        # angle: criterion
        """AC BO-2900a-1's final clause (scope fence, not an escape hatch):
        a fixture unit exposing no main() anywhere must NEVER receive the
        'proof_not_through_entry_point' refusal_cause from this rule -- that
        case is decided separately (BO-2900a-3)."""
        verdict = verify_done_eligible(
            self.fixture_ac_id,
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        self.assertNotEqual(
            verdict.get("refusal_cause"),
            "proof_not_through_entry_point",
            f"scope fence violated -- this rule must not judge a unit with "
            f"no way in at all, got: {verdict}",
        )


if __name__ == "__main__":
    unittest.main()
