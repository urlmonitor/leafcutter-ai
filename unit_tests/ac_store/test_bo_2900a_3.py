"""
MODULE: unit_tests/ac_store/test_bo_2900a_3.py
COVERS: BO-2900a-3

GOAL: Behavioral, REAL-verify_done_eligible tests for "Code that no way of
    running the product can reach cannot be marked done, however many tests
    pass" — the second refusal cause (refusal_cause: 'no_entry_point_reaches_
    code') that gates an otherwise-eligible leaf AC when its implementing
    code has no runtime way in of its own, is imported by nothing that does,
    and is run by no automation.

CURRENT STATE (2026-09-25): The refusal machinery
    (`_apply_reachability_gate` / `_find_no_entry_point_unit` in
    scripts/ac_store/done_proof.py) already exists in this worktree and
    already produces `refusal_cause: "no_entry_point_reaches_code"` for the
    PLAIN "no other file mentions the unit at all" case. That plain case is
    therefore NOT a reliable red signal on its own.

    The AC's own it_requirements constraint is explicit and load-bearing:

        "(2) no module that DOES define one reaches the code — established
        from the import graph built by importing candidate modules, never
        from a text scan of import statements"

    `_is_imported_elsewhere` (done_proof.py) is, TODAY, exactly the
    forbidden shape: a bare regex search for the text `import <module_name>`
    / `from <module_name> import` across every other project file — it never
    imports anything and never distinguishes a real import statement from
    the same text appearing inside a comment or a docstring. Every fixture
    below therefore plants a DECOY file that mentions the target module's
    import spelling only inside a docstring (never a real `import` or `from
    ... import` statement, confirmed by not appearing as an ast.Import /
    ast.ImportFrom node were the decoy file parsed) — `no_entry_unit.py` has
    no way in of its own, and nothing REAL imports it, so every test below
    expects a refusal. Confirmed empirically before writing this file: the
    unmodified `verify_done_eligible()` returns `eligible: True` for this
    exact fixture shape today (the decoy text fools the regex into
    concluding "imported elsewhere"), and the deployed check_done_proof.py
    CLI reports zero violations for the identical fixture (exit 0) — both
    are the WRONG answer per the AC's own Gherkin ("the criterion is
    rejected as not eligible"). These are the two real, current red
    baselines this file targets; a coder satisfies them by replacing the
    text-scan with a genuine import-graph check (e.g. actually importing
    candidate modules, or an AST-based whole-project import analysis) per
    the AC's constraint — not by special-casing this fixture's decoy text.

ENTRY POINT (reachability test only): the REAL, deployed
    scripts/commit_guardian/check_done_proof.py CLI, run via subprocess with
    --mode ci — the registered "check-done-proof" pre-commit hook
    (config/commit_guardian.json) and the CI-authoritative done-proof job —
    never imported and called directly.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bo_2900a_1_fixtures import (  # noqa: E402
    CHECK_DONE_PROOF_SCRIPT,
    init_git_fixture_project,
    write_ac,
    write_fixture_file,
)

from done_proof import verify_done_eligible  # noqa: E402


def _write_no_way_in_fixture(
    root: Path,
    ac_id: str,
    *,
    work_status: str = "todo",
    unit_filename: str = "no_entry_unit.py",
    decoy_filename: str = "other_unit.py",
    test_filename: str = "test_direct_import.py",
) -> tuple[Path, Path, Path]:
    """Build a fixture unit with no way in of its own, a decoy file that
    ONLY mentions the unit's import spelling inside a docstring (never a
    real import statement), and a covers-tagged test that imports the unit
    directly and passes.

    Returns (ac_root, test_root, unit_path).
    """
    ac_root = root / "acs"
    test_root = root / "tests"
    src_dir = root / "src"
    write_ac(ac_root, ac_id, work_status=work_status)

    module_name = unit_filename[: -len(".py")]
    unit_path = write_fixture_file(
        src_dir,
        unit_filename,
        "def do_thing():\n    return 42\n",
    )
    # Decoy: mentions "import <module_name>" only inside a docstring — a
    # regex text-scan for the literal words matches this; a real import
    # graph (actually importing candidate modules, or AST-parsing every
    # candidate) does not, because no ast.Import / ast.ImportFrom node for
    # this module exists anywhere in this file.
    write_fixture_file(
        src_dir,
        decoy_filename,
        f'"""Unrelated helper. Historical note: import {module_name} was '
        f'considered here and rejected — this sentence is NOT Python '
        f'syntax, just prose that happens to contain the words \'import '
        f'{module_name}\'."""\n\n\ndef unrelated():\n    return 1\n',
    )
    write_fixture_file(
        test_root,
        test_filename,
        "import sys\n"
        f"sys.path.insert(0, {str(src_dir)!r})\n"
        f"from {module_name} import do_thing\n\n\n"
        "def test_fixture_unit_via_direct_import():\n"
        f"    # covers: {ac_id}\n"
        "    assert do_thing() == 42\n",
    )
    return ac_root, test_root, unit_path


def _refusal_shape(verdict: dict) -> dict:
    """The subset of a verdict dict that must stay stable regardless of how
    many passing tests are linked — excludes `passing_tests`/`failing_tests`/
    `dangling_tags`, which legitimately grow when a second test is added."""
    return {
        "eligible": verdict.get("eligible"),
        "reason": verdict.get("reason"),
        "refusal_cause": verdict.get("refusal_cause"),
        "unit": verdict.get("unit"),
    }


class TestUnitWithNoWayInIsRefusedDespiteAPassingProof(unittest.TestCase):
    """test_unit_with_no_way_in_is_refused_despite_a_passing_proof
    (BO-2900a-3 test_spec #1)."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        init_git_fixture_project(self.root)
        self.ac_id = "BO-TEST-2900A3-1"
        self.ac_root, self.test_root, self.unit_path = _write_no_way_in_fixture(
            self.root, self.ac_id
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_unit_with_no_way_in_is_refused_despite_a_passing_proof(self) -> None:
        # covers: BO-2900a-3
        # angle: criterion
        """Runs the REAL verify_done_eligible over a fixture unit with no
        main() of its own, no module that genuinely imports it (only a
        decoy docstring mention), and no automation invocation, whose
        covers-tagged proof passes. Asserts eligible False, refusal_cause
        'no_entry_point_reaches_code', and that the message names the
        unit."""
        verdict = verify_done_eligible(
            self.ac_id, ac_root=self.ac_root, test_root=self.test_root
        )
        self.assertFalse(
            verdict.get("eligible"),
            f"expected the unreachable unit to be refused, got: {verdict}",
        )
        self.assertEqual(
            verdict.get("refusal_cause"),
            "no_entry_point_reaches_code",
            f"expected the BO-2900a-3 refusal_cause, got: {verdict}",
        )
        self.assertIn(
            "no_entry_unit",
            str(verdict.get("unit", "")),
            f"the verdict must name the unreachable unit, got: {verdict}",
        )
        self.assertIn(
            "no_entry_unit",
            verdict.get("reason", ""),
            f"the refusal message must name the unit, got: {verdict}",
        )


class TestAddingAnotherPassingTestLeavesTheVerdictUnchanged(unittest.TestCase):
    """test_adding_another_passing_test_leaves_the_verdict_unchanged
    (BO-2900a-3 test_spec #2 — the anti-ritual invariant)."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        init_git_fixture_project(self.root)
        self.ac_id = "BO-TEST-2900A3-2"
        self.ac_root, self.test_root, self.unit_path = _write_no_way_in_fixture(
            self.root, self.ac_id
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_adding_another_passing_test_leaves_the_verdict_unchanged(self) -> None:
        # covers: BO-2900a-3
        # angle: criterion
        """Adds a second passing covers-tagged test over the same fixture
        code and re-runs the real evaluation; asserts the refusal shape
        (eligible/reason/refusal_cause/unit) is identical before and after,
        proving the predicate reads no test-derived term (test count is not
        one of the three enumerated conditions)."""
        verdict_before = verify_done_eligible(
            self.ac_id, ac_root=self.ac_root, test_root=self.test_root
        )
        expected_shape = {
            "eligible": False,
            "reason": verdict_before.get("reason"),
            "refusal_cause": "no_entry_point_reaches_code",
            "unit": verdict_before.get("unit"),
        }
        self.assertEqual(
            _refusal_shape(verdict_before),
            expected_shape,
            f"expected an ineligible refusal BEFORE adding a second test, "
            f"got: {verdict_before}",
        )

        # A second, independent covers-tagged test importing the SAME unit
        # — adding it must be structurally incapable of flipping the
        # verdict (the AC's own anti-ritual clause).
        write_fixture_file(
            self.test_root,
            "test_direct_import_second.py",
            "import sys\n"
            f"sys.path.insert(0, {str(self.unit_path.parent)!r})\n"
            "from no_entry_unit import do_thing\n\n\n"
            "def test_fixture_unit_via_direct_import_again():\n"
            f"    # covers: {self.ac_id}\n"
            "    assert do_thing() == 42\n",
        )

        verdict_after = verify_done_eligible(
            self.ac_id, ac_root=self.ac_root, test_root=self.test_root
        )
        self.assertEqual(
            _refusal_shape(verdict_after),
            _refusal_shape(verdict_before),
            f"adding a second passing test must leave the refusal shape "
            f"unchanged. before={verdict_before} after={verdict_after}",
        )


class TestVerdictFlipsOnlyOnEntryPointOrExemption(unittest.TestCase):
    """test_verdict_flips_only_when_an_entry_point_is_added_or_an_exemption_
    is_recorded (BO-2900a-3 test_spec #3)."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        init_git_fixture_project(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_verdict_flips_only_when_an_entry_point_is_added_or_an_exemption_is_recorded(
        self,
    ) -> None:
        # covers: BO-2900a-3
        # angle: criterion
        """Three assertions in one test, all required together so neither a
        pass-everything nor a refuse-everything implementation can satisfy
        the set: (1) the untouched fixture is refused, (2) giving the SAME
        unit its own main() flips it to eligible, and (3) — on a FRESH copy
        of the same no-way-in fixture — recording an exemption for the
        exact unit path also flips it to eligible."""
        # --- (1) untouched refusal ---
        ac_id_main = "BO-TEST-2900A3-3A"
        ac_root_main, test_root_main, unit_path_main = _write_no_way_in_fixture(
            self.root / "main-branch", ac_id_main
        )
        verdict_initial = verify_done_eligible(
            ac_id_main, ac_root=ac_root_main, test_root=test_root_main
        )
        self.assertFalse(
            verdict_initial.get("eligible"),
            f"expected the untouched fixture to be refused, got: {verdict_initial}",
        )
        self.assertEqual(
            verdict_initial.get("refusal_cause"),
            "no_entry_point_reaches_code",
            f"expected the BO-2900a-3 refusal_cause, got: {verdict_initial}",
        )

        # --- (2) giving the SAME unit a real main() of its own flips it ---
        unit_path_main.write_text(
            "def do_thing():\n"
            "    return 42\n\n\n"
            "if __name__ == \"__main__\":\n"
            "    do_thing()\n",
            encoding="utf-8",
        )
        verdict_with_main = verify_done_eligible(
            ac_id_main, ac_root=ac_root_main, test_root=test_root_main
        )
        self.assertTrue(
            verdict_with_main.get("eligible"),
            f"giving the unit its own main() must flip the verdict to "
            f"eligible, got: {verdict_with_main}",
        )

        # --- (3) a FRESH copy of the same no-way-in fixture, released only
        # by a recorded exemption for the exact unit path ---
        ac_id_exempt = "BO-TEST-2900A3-3B"
        ac_root_exempt, test_root_exempt, unit_path_exempt = _write_no_way_in_fixture(
            self.root / "exempt-branch", ac_id_exempt
        )
        verdict_before_exemption = verify_done_eligible(
            ac_id_exempt, ac_root=ac_root_exempt, test_root=test_root_exempt
        )
        self.assertFalse(
            verdict_before_exemption.get("eligible"),
            f"expected the fresh copy to be refused before any exemption, "
            f"got: {verdict_before_exemption}",
        )
        exempted_item = verdict_before_exemption.get("unit")
        self.assertTrue(
            exempted_item,
            f"the refusal must name a unit to exempt, got: "
            f"{verdict_before_exemption}",
        )
        registry_path = (
            self.root / "exempt-branch" / "config" / "reachability_exemptions.yaml"
        )
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(
            yaml.safe_dump(
                {
                    "exemptions": [
                        {
                            "item": exempted_item,
                            "kind": "unit",
                            "reason": "test-writer fixture: deliberately unreached",
                            "recorded": "2026-09-25",
                            "recorded_by": "test-writer-fixture",
                        }
                    ]
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        verdict_with_exemption = verify_done_eligible(
            ac_id_exempt, ac_root=ac_root_exempt, test_root=test_root_exempt
        )
        self.assertTrue(
            verdict_with_exemption.get("eligible"),
            f"a recorded exemption for the exact unit path must flip the "
            f"verdict to eligible, got: {verdict_with_exemption}",
        )


class TestBo2900a3ReachableFromEntryPoint(unittest.TestCase):
    """test_bo_2900a_3_reachable_from_entry_point — REQUIRED reachability
    test (BO-2900a-3 test_spec #4, angle: reachability). Invokes the REAL,
    deployed check_done_proof.py CLI (--mode ci) as a subprocess — the
    registered pre-commit hook and required CI done-proof job's own runner
    — and asserts the new refusal behaviour actually occurs through that
    real operator surface. Never imports verify_done_eligible and calls it
    directly for this assertion."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        init_git_fixture_project(self.root)
        self.ac_id = "BO-TEST-2900A3-CLI"
        self.ac_root, self.test_root, self.unit_path = _write_no_way_in_fixture(
            self.root, self.ac_id, work_status="done"
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_bo_2900a_3_reachable_from_entry_point(self) -> None:
        # covers: BO-2900a-3
        # angle: reachability
        self.assertTrue(
            CHECK_DONE_PROOF_SCRIPT.is_file(),
            f"deployed guard script not found: {CHECK_DONE_PROOF_SCRIPT} — "
            f"run `python scripts/build.py --target-dir .` first",
        )
        result = subprocess.run(
            [
                sys.executable,
                str(CHECK_DONE_PROOF_SCRIPT),
                "--mode",
                "ci",
                "--ac-root",
                str(self.ac_root),
                "--test-root",
                str(self.test_root),
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
            f"expected the real CLI to refuse a 'done' AC whose only "
            f"implementing unit has no runtime way in. "
            f"exit={result.returncode}\nstdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}",
        )
        self.assertIn(
            self.ac_id,
            combined,
            f"the CLI's own output must name the refused AC:\n{combined}",
        )
        self.assertIn(
            "no_entry_unit",
            combined,
            f"the CLI's own output must name the unreachable unit:\n{combined}",
        )
        self.assertIn(
            "no_entry_point_reaches_code",
            combined,
            f"the CLI's own output must state the refusal_cause:\n{combined}",
        )


if __name__ == "__main__":
    unittest.main()
