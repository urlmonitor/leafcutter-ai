"""
MODULE: unit_tests/ac_store/test_bo_2900a_1_ii.py
COVERS: BO-2900a-1

GOAL: The remaining BO-2900a-1 test cases split out of test_bo_2900a_1.py
    once that file exceeded check_file_size.py's 400-content-line new-file
    limit (426 lines) after the cross-file fixture (formerly "Test 5") was
    added on the first rework round:

    - The REQUIRED reachability test driving the real, deployed
      check_done_proof.py CLI (formerly "Test 4").
    - The cross-file fixture proving entry-point detection resolves modules
      a linked test imports, not merely the test file itself (formerly
      "Test 5").
    - NEW this round: the divergent-definition guard test. pr-reviewer's
      2026-09-25 13:21 finding (independently reproduced by ac-validator's
      13:24 comment) found that ``_apply_reachability_gate`` (the sibling
      BO-2900a-3 no-way-in-anywhere gate, scripts/ac_store/done_proof.py)
      has no ``if not verdict.get("eligible"): return verdict`` guard, so
      an already-refused BO-2900a-1 verdict fed into it at
      done_proof.py:2303-2309 can be silently OVERWRITTEN with a different,
      wrong ``refusal_cause`` -- exactly the "two disjoint refusal_cause
      values, never one merged verdict" outcome this AC's own constraint
      forbids. This happens because the two gates use DIFFERENT
      definitions of "has a way in of its own":

        - BO-2900a-1's ``_module_defines_main`` (AST): does the module
          define a function literally named ``main``?
        - BO-2900a-3's ``_has_entry_point_of_its_own`` (regex): does the
          module's source TEXT contain an
          ``if __name__ == "__main__":`` guard?

    A module that defines ``main(argv)`` WITHOUT that exact guard text, and
    is imported by no other project file, satisfies BO-2900a-1's detection
    (so the a-1 gate correctly refuses with "proof_not_through_entry_point")
    but ALSO satisfies BO-2900a-3's "no way in of its own" test (so the a-3
    gate, given no eligibility guard, treats the a-1 refusal as if it were
    still ``eligible: True`` and overwrites it with its own
    "no_entry_point_reaches_code" verdict, discarding the a-1 refusal's
    unit/entry_point/offending_test fields).

    Shared fixture helpers live in unit_tests/ac_store/_bo_2900a_1_fixtures.py
    (write_ac, write_fixture_file, init_git_fixture_project,
    CHECK_DONE_PROOF_SCRIPT); see that module and test_bo_2900a_1.py's own
    docstring for the AC and interface contract this whole family proves.

=== Red baseline (this round) ===

    The new divergent-definition test below calls the REAL, unmodified
    ``verify_done_eligible``. Today, with no eligibility guard in
    ``_apply_reachability_gate``, the a-1 refusal
    (``refusal_cause: "proof_not_through_entry_point"``) IS produced first,
    but is then unconditionally overwritten by ``_apply_reachability_gate``
    with ``refusal_cause: "no_entry_point_reaches_code"`` -- so the test's
    assertion that the ORIGINAL refusal_cause survives is RED today.
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bo_2900a_1_fixtures import (  # noqa: E402
    CHECK_DONE_PROOF_SCRIPT,
    init_git_fixture_project,
    write_ac,
    write_fixture_file,
)

import yaml  # noqa: E402

from done_proof import verify_done_eligible  # noqa: E402

# BO-2900a-1's rule was SUSPENDED to report-only on 2026-09-30 (see
# scripts/ac_store/_done_proof_entry_point_gate.py DECISION HISTORY): it announces its
# findings and returns the verdict unchanged, so nothing it judges is refused. Every
# assertion below that expects a REFUSAL therefore fails, and a-1 is `work_status: todo`
# for exactly that reason. The three tests are marked expected-failure rather than
# rewritten, so the record of what a-1 demands survives the suspension.
#
# SELF-CLEANING, do not soften: `expectedFailure` reports an unexpected PASS as a
# failure, so re-arming the rule turns this file red until the markers come off. CI runs
# AC_ENFORCE_STRICT=1 (.github/workflows/ci.yml), so the AC-enforcement plugin does NOT
# mask these on the strength of a-1 being todo -- these markers are what keep the
# required pytest gate both honest and green.
_SUSPENDED_RULE = "BO-2900a-1 rule suspended to report-only; see a-1-ii / a-1-iii"


# ---------------------------------------------------------------------------
# Test 4 -- reachability: the REAL deployed CLI entry point, via subprocess
# ---------------------------------------------------------------------------


class TestBo2900a1ReachableFromEntryPoint(unittest.TestCase):
    """REQUIRED reachability test (BP-1100g-2 / this ticket's Test
    Requirements): invokes the real, deployed check_done_proof.py CLI --
    the registered "check-done-proof" pre-commit hook and required CI
    done-proof job's own entry point -- as a subprocess, and asserts the new
    BO-2900a-1 behaviour actually occurs through that surface. Never
    imports verify_done_eligible and calls it directly for this assertion."""

    def setUp(self) -> None:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        init_git_fixture_project(self.root)
        self.ac_dir = self.root / "docs" / "acceptance-criteria"
        self.test_dir = self.root / "tests"
        self.fixture_ac_id = "BO-TEST-2900A1-CLI"

        data = {
            "id": self.fixture_ac_id,
            "title": f"Fixture record for {self.fixture_ac_id}",
            "component": "build-orchestration",
            "components": ["build_orchestration"],
            "status": "active",
            "work_status": "done",
            "readiness": "reviewed",
            "priority": "medium",
            "criteria": (
                "Given a fixture unit with a genuine argparse main()\n"
                "When the real check-done-proof CLI evaluates it\n"
                "Then a direct-import proof is reported as a violation\n"
            ),
        }
        (self.ac_dir / f"{self.fixture_ac_id}.yaml").write_text(
            yaml.safe_dump(data, sort_keys=False), encoding="utf-8"
        )

        self.module_name = "test_bo2900a1_cli_direct_import_fixture"
        write_fixture_file(
            self.test_dir,
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
    def test_bo_2900a_1_reachable_from_entry_point(self) -> None:
        # covers: BO-2900a-1
        # angle: reachability
        """Drives the REAL check_done_proof.py CLI (--mode ci) as a
        subprocess -- the registered pre-commit hook and required CI
        done-proof job's own runner -- over a fixture 'done' AC whose only
        covers-tagged proof direct-imports the implementing function past a
        genuine argparse main(). Asserts the CLI itself refuses (non-zero
        exit) and names the offending AC in its own printed output, so the
        new behaviour is proven reachable through the real operator surface,
        not merely importable."""
        self.assertTrue(
            CHECK_DONE_PROOF_SCRIPT.is_file(),
            f"deployed guard script not found: {CHECK_DONE_PROOF_SCRIPT} -- "
            f"run `python scripts/build.py --target-dir .` first",
        )
        result = subprocess.run(
            [
                sys.executable,
                str(CHECK_DONE_PROOF_SCRIPT),
                "--mode",
                "ci",
                "--ac-root",
                str(self.ac_dir),
                "--test-root",
                str(self.test_dir),
            ],
            cwd=str(self.root),
            capture_output=True,
            text=True,
            check=False,
        )
        combined = result.stdout + result.stderr

        self.assertNotEqual(
            result.returncode,
            0,
            f"expected the real CLI to refuse a direct-import proof over an "
            f"entry-point unit. exit={result.returncode}\nstdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}",
        )
        self.assertIn(
            self.fixture_ac_id,
            combined,
            f"the CLI's own output must name the refused AC:\n{combined}",
        )
        self.assertIn(
            "direct import",
            combined.lower(),
            f"the CLI's own output must state the direct-import cause:\n{combined}",
        )


# ---------------------------------------------------------------------------
# Test 5 -- cross-file fixture: implementing code + main(argv) live in a
# SEPARATE module from the covers-tagged proof test (mirrors fast_lane.main,
# scripts/build_orchestration/fast_lane.py -- a production module distinct
# from its own test file).
# ---------------------------------------------------------------------------


class TestCrossFileDirectImportProofIsRefusedWhenUnitHasAnEntryPoint(unittest.TestCase):
    """BO-2900a-1, cross-file case: the implementing module (with its own
    ``main(argv)``) lives in a SEPARATE file from the covers-tagged proof
    test that imports it -- the codebase's real test/implementation split,
    not the single-file fixture convention test_bo_2900a_1.py's tests use.
    The proof reaches ``_run_the_task`` by importing the implementation
    module directly and calling the function, never through ``main``.
    """

    def setUp(self) -> None:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.impl_dir = root / "impl"
        self.fixture_ac_id = "BO-TEST-2900A1-CROSSFILE"
        write_ac(self.ac_root, self.fixture_ac_id)

        self.impl_module_name = "fixture_bo2900a1_crossfile_impl"
        write_fixture_file(
            self.impl_dir,
            f"{self.impl_module_name}.py",
            """\
            import argparse


            def _run_the_task():
                \"\"\"The implementing code under proof -- lives in its OWN
                module, separate from the covers-tagged test file, mirroring
                fast_lane.main (scripts/build_orchestration/fast_lane.py) --
                a production module distinct from its own test.\"\"\"
                return "task-complete"


            def main(argv=None):
                parser = argparse.ArgumentParser(prog="fixture-crossfile-unit")
                parser.add_argument("action")
                args = parser.parse_args(argv)
                if args.action == "run":
                    return _run_the_task()
                return None


            if __name__ == "__main__":
                main()
            """,
        )

        self.module_name = "test_bo2900a1_crossfile_direct_import_fixture"
        write_fixture_file(
            self.test_root,
            f"{self.module_name}.py",
            f"""\
            import sys

            sys.path.insert(0, {str(self.impl_dir)!r})

            import {self.impl_module_name}


            # covers: {self.fixture_ac_id}
            def test_proof_imports_the_function_directly():
                result = {self.impl_module_name}._run_the_task()
                assert result == "task-complete"
            """,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    @unittest.expectedFailure  # _SUSPENDED_RULE
    def test_cross_file_direct_import_proof_is_refused_when_unit_has_an_entry_point(
        self,
    ) -> None:
        # covers: BO-2900a-1
        # angle: criterion
        """AC BO-2900a-1, cross-file scenario: ``main(argv)`` lives in a
        module SEPARATE from the covers-tagged proof test that imports it
        directly without ever calling ``main`` -- the codebase's real
        test/implementation split (fast_lane.main-style). The reported
        ``entry_point`` must name the IMPLEMENTATION module, not the test
        file, since the test file itself defines no ``main`` at all.
        """
        verdict = verify_done_eligible(
            self.fixture_ac_id,
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        self.assertFalse(
            verdict.get("eligible"),
            f"expected ineligible (cross-file direct import), got: {verdict}",
        )
        reason = verdict.get("reason", "").lower()
        self.assertIn("direct import", reason)
        self.assertEqual(
            verdict.get("refusal_cause"),
            "proof_not_through_entry_point",
            f"expected the 'proof_not_through_entry_point' cause, got: {verdict}",
        )
        self.assertTrue(
            verdict.get("unit"),
            f"verdict must name the unit that was never entered, got: {verdict}",
        )
        self.assertIn(
            self.impl_module_name,
            str(verdict.get("unit", "")),
            f"verdict's 'unit' must name the IMPLEMENTATION module "
            f"({self.impl_module_name}), not the test file, got: {verdict}",
        )
        entry_point = verdict.get("entry_point") or ""
        self.assertIn(
            "main",
            entry_point,
            f"verdict must name the un-entered entry point, got: {verdict}",
        )
        self.assertIn(
            self.impl_module_name,
            entry_point,
            f"entry_point must name the IMPLEMENTATION module "
            f"({self.impl_module_name}), not the test file that imports it, "
            f"got: {verdict}",
        )
        offending_test = verdict.get("offending_test") or ""
        self.assertIn(
            "test_proof_imports_the_function_directly",
            offending_test,
            f"verdict must name the offending test nodeid, got: {verdict}",
        )


# ---------------------------------------------------------------------------
# Test 6 -- NEW this round: an a-1 refusal must survive being passed through
# _apply_reachability_gate (BO-2900a-3) unchanged, even when the two gates'
# divergent "has a way in of its own" definitions disagree about the SAME
# unit. Added per ticket-supervisor's 2026-09-25 14:07 rework-round-2
# handoff, routing pr-reviewer's 13:21 finding (independently reproduced by
# ac-validator's 13:24 comment).
# ---------------------------------------------------------------------------


class TestA1RefusalSurvivesTheA3GateWhenTheTwoDefinitionsDiverge(unittest.TestCase):
    """The implementing module defines ``main(argv)`` (so BO-2900a-1's AST
    check, ``_module_defines_main``, detects a way in and the a-1 gate
    refuses) but has NO ``if __name__ == "__main__":`` guard text and is
    imported by no other project file (so BO-2900a-3's regex-based
    ``_has_entry_point_of_its_own`` / ``_is_imported_elsewhere`` checks
    independently conclude the SAME unit has "no way in of its own" and
    ``_apply_reachability_gate`` would refuse it too, for a DIFFERENT
    reason). The AC's own constraint ("THE SCOPE FENCE IS MECHANICAL ...
    Two disjoint refusal_cause values, never one merged 'unreachable'
    verdict") requires the a-1 gate's refusal -- computed first -- to win
    outright: its refusal_cause, unit, entry_point and offending_test must
    reach the caller unchanged, never be silently overwritten by the a-3
    gate's own, different verdict.
    """

    def setUp(self) -> None:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.impl_dir = root / "impl"
        self.fixture_ac_id = "BO-TEST-2900A1-DIVERGENT"
        write_ac(self.ac_root, self.fixture_ac_id)

        # Deliberately NO `if __name__ == "__main__":` guard below -- that is
        # the whole point of this fixture. BO-2900a-1's AST check
        # (`_module_defines_main`) still finds `main`, but BO-2900a-3's
        # regex check (`_has_entry_point_of_its_own`) does not, and this
        # module is imported by no other project file
        # (`_is_imported_elsewhere` is also False), so the a-3 gate's own,
        # independent notion of "no way in of its own" fires on this same
        # unit too.
        self.impl_module_name = "fixture_bo2900a1_divergent_impl"
        write_fixture_file(
            self.impl_dir,
            f"{self.impl_module_name}.py",
            """\
            import argparse


            def _run_the_task():
                \"\"\"The implementing code under proof -- must NOT be reached
                by direct import in this fixture. This module defines
                main(argv) but has no `if __name__` guard, on purpose.\"\"\"
                return "task-complete"


            def main(argv=None):
                parser = argparse.ArgumentParser(prog="fixture-divergent-unit")
                parser.add_argument("action")
                args = parser.parse_args(argv)
                if args.action == "run":
                    return _run_the_task()
                return None
            """,
        )

        self.module_name = "test_bo2900a1_divergent_direct_import_fixture"
        write_fixture_file(
            self.test_root,
            f"{self.module_name}.py",
            f"""\
            import sys

            sys.path.insert(0, {str(self.impl_dir)!r})

            import {self.impl_module_name}


            # covers: {self.fixture_ac_id}
            def test_proof_imports_the_function_directly():
                result = {self.impl_module_name}._run_the_task()
                assert result == "task-complete"
            """,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    @unittest.expectedFailure  # _SUSPENDED_RULE
    def test_a1_refusal_survives_the_a3_gate_when_the_two_definitions_diverge(
        self,
    ) -> None:
        # covers: BO-2900a-1
        # angle: boundary
        """RED today: ``_apply_reachability_gate`` has no
        ``if not verdict.get("eligible"): return verdict`` guard, so the a-1
        gate's refusal (``proof_not_through_entry_point``) is silently
        overwritten by the a-3 gate's OWN, different refusal
        (``no_entry_point_reaches_code``) for this same unit -- discarding
        the a-1 refusal's unit/entry_point/offending_test fields. This test
        asserts the a-1 refusal_cause, and its identifying fields, survive
        unchanged; must go green once python-coder restores
        ``_apply_reachability_gate``'s documented
        "only called when verdict is already eligible: True" precondition
        (or reconciles the two gates' divergent "has a way in" checks).
        """
        verdict = verify_done_eligible(
            self.fixture_ac_id,
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        self.assertFalse(
            verdict.get("eligible"),
            f"expected ineligible (direct import, divergent-definition unit), "
            f"got: {verdict}",
        )
        self.assertEqual(
            verdict.get("refusal_cause"),
            "proof_not_through_entry_point",
            "the BO-2900a-1 refusal must survive being passed through the "
            "BO-2900a-3 gate unchanged -- it must NOT be silently overwritten "
            f"with 'no_entry_point_reaches_code', got: {verdict}",
        )
        self.assertIn(
            self.impl_module_name,
            str(verdict.get("unit", "")),
            f"the a-1 refusal's 'unit' field must survive unchanged, got: {verdict}",
        )
        entry_point = verdict.get("entry_point") or ""
        self.assertIn(
            self.impl_module_name,
            entry_point,
            f"the a-1 refusal's 'entry_point' field must survive unchanged, "
            f"got: {verdict}",
        )
        offending_test = verdict.get("offending_test") or ""
        self.assertIn(
            "test_proof_imports_the_function_directly",
            offending_test,
            f"the a-1 refusal's 'offending_test' field must survive unchanged, "
            f"got: {verdict}",
        )


if __name__ == "__main__":
    unittest.main()
