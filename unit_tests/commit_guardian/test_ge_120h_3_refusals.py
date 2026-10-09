"""
MODULE: unit_tests/commit_guardian/test_ge_120h_3_refusals.py
COVERS: GE-120h-3 -- arm 4, the anti-theatre clause: "given, for each of the
    five, an input that check exists to refuse, under the settings that arm
    it ... the check refuses it and names what it objected to."

WHY FIVE TESTS, NOT ONE. GE-120h-3's own test_spec describes this arm as a
    single test asserting a uniform "is refused and the objection is named"
    for all five checks. That description does not hold for check-ac-done-
    -on-merge, which this repo's own implementation notes and constraints
    establish CANNOT refuse: main() returns 0 unconditionally and its
    __main__ guard swallows OSError/ValueError into sys.exit(0). Per this
    worktree's CLAUDE.md ("Gate / Workflow ACs -- Verify Behaviorally, Not
    by Grep": "This rule outranks the ticket's own test_spec"), this file
    writes the four-plus-one shape the ticket's dispatch brief calls for
    instead of forcing a fifth check through a refusal it structurally
    cannot produce.

WHAT WAS EMPIRICALLY FOUND BEFORE WRITING THESE TESTS (see the sign-off
    comment on TICKET-20260930-GE-120h-3.md for full probe transcripts):
      - check_folder_density.py has a genuine, previously undiscovered
        defect: its "before" snapshot is computed from `git ls-files`,
        which already reflects the CURRENT INDEX -- i.e. it already
        includes whatever this same commit just staged. So a folder that
        crosses the limit because of files staged IN THIS COMMIT is
        misclassified as PRE-EXISTING (a warning) rather than a violation,
        and the commit is wrongly allowed through. GE-120h-3's own
        constraint forbids "tidying" the pre-existing-warning behaviour
        (arm 2, already landed) -- it says nothing about fixing this
        separate before-computation bug, which is what arm 4's first test
        is RED against.
      - check_sql_complexity.py, check_debug_scripts.py, and
        check_test_fixture_bloat.py (once armed) already correctly refuse
        their respective known-bad inputs through the registered
        run_hook.py path. Their underlying validation logic pre-dates this
        AC; only registration was missing, and PR #808 already supplied
        that. These three tests are expected to be GREEN already -- that is
        a legitimate outcome (see this ticket's dispatch brief: "a test
        that is green before the coder runs is either already-satisfied
        behaviour"), and they still matter because no test previously
        existed to prove the refusal through the REGISTERED path rather
        than by import.
      - check-ac-done-on-merge has never had its negative_control declared
        anywhere. The fifth test below is RED against that absence.
"""

from __future__ import annotations

import json
import sys
import shutil
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_120h_3_fixture as fx  # noqa: E402


class TestCheckFolderDensityRefusesANewlyDenseFolder(unittest.TestCase):
    def setUp(self) -> None:
        self.root = fx.fresh_repo_dir("ge120h3_density_refuse_")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        fx.init_repo(self.root)

    def test_ge120h3_check_folder_density_refuses_a_newly_dense_folder(self):
        # covers: GE-120h-3
        # angle: failure
        """A folder that is AT the limit (15) before this commit and is
        pushed OVER it (16) by files this SAME commit stages must be
        classified as a violation (blocking, exit 1) -- not a warning, and
        pre-existing over-limit directories (arm 2, already landed) must
        still classify as warnings, unaffected by this test.

        RED TODAY: empirically verified via a real two-commit sequence
        (establish 15 files in a new dir as its own commit, then stage one
        more) driven through run_hook.py -- the check reports
        "PRE-EXISTING DENSITY" and returns 0, because its before-count is
        computed from `git ls-files`, which already reflects the file just
        staged. See this file's module docstring.
        """
        folder = self.root / "newdir"
        folder.mkdir()
        for i in range(15):
            (folder / f"f{i}.txt").write_text(f"content {i}\n", encoding="utf-8")
        fx.commit_all(self.root, "establish at-limit dir")

        (folder / "f_extra.txt").write_text("extra\n", encoding="utf-8")
        fx.stage_all(self.root)

        result = fx.run_via_hook(fx.FOLDER_DENSITY, self.root)
        combined = result.stdout + result.stderr

        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "A folder crossing the density limit WITHIN this commit must "
                f"be refused as a violation, not reported as pre-existing. Got: {combined!r}"
            ),
        )
        self.assertIn(
            "FOLDER TOO DENSE",
            combined,
            msg=f"The refusal must name the violation. Got: {combined!r}",
        )
        self.assertNotIn(
            "PRE-EXISTING",
            combined,
            msg=f"A newly-crossed folder must not be reported as pre-existing. Got: {combined!r}",
        )


class TestCheckSqlComplexityRefusesAnOvercomplexFile(unittest.TestCase):
    def setUp(self) -> None:
        self.root = fx.fresh_repo_dir("ge120h3_sql_refuse_")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        fx.init_repo(self.root)

    def test_ge120h3_check_sql_complexity_refuses_an_overcomplex_sql_file(self):
        # covers: GE-120h-3
        # angle: failure
        """A staged .sql file whose keyword-derived complexity score exceeds
        sql_complexity.max_score (75) must be refused through the registered
        run_hook.py path, naming the file and its score.
        """
        (self.root / "complex.sql").write_text(fx.make_overcomplex_sql(), encoding="utf-8")
        fx.stage_all(self.root)

        result = fx.run_via_hook(fx.SQL_COMPLEXITY, self.root)
        combined = result.stdout + result.stderr

        self.assertNotEqual(
            0,
            result.returncode,
            msg=f"An over-complex SQL file must be refused. Got: {combined!r}",
        )
        self.assertIn(
            "complex.sql",
            combined,
            msg=f"The refusal must name the offending file. Got: {combined!r}",
        )


class TestCheckDebugScriptsRefusesAnUntaggedScript(unittest.TestCase):
    def setUp(self) -> None:
        self.root = fx.fresh_repo_dir("ge120h3_debug_refuse_")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        fx.init_repo(self.root)

    def test_ge120h3_check_debug_scripts_refuses_an_untagged_debug_script(self):
        # covers: GE-120h-3
        # angle: failure
        """A staged file under debugging/scripts/ missing its required tags
        must be refused through the registered run_hook.py path, naming the
        file."""
        scripts_dir = self.root / "debugging" / "scripts" / "misc"
        scripts_dir.mkdir(parents=True)
        (scripts_dir / "untagged.py").write_text(
            fx.make_untagged_debug_script(), encoding="utf-8"
        )
        fx.stage_all(self.root)

        result = fx.run_via_hook(fx.DEBUG_SCRIPTS, self.root)
        combined = result.stdout + result.stderr

        self.assertNotEqual(
            0,
            result.returncode,
            msg=f"An untagged debug script must be refused. Got: {combined!r}",
        )
        self.assertIn(
            "untagged.py",
            combined,
            msg=f"The refusal must name the offending file. Got: {combined!r}",
        )


@pytest.mark.shared_layout_mutator
def test_ge120h3_check_test_fixture_bloat_refuses_when_armed_via_private_config(
    shared_reference_layout: Path,
) -> None:
    # covers: GE-120h-3
    # angle: failure
    """check-test-fixture-bloat ships INERT (config key absent, `enabled`
    defaults False) -- GE-120h-3's own constraints forbid adding
    `test_fixture_bloat` to the TRACKED commit_guardian.json, since that
    would arm a check nobody has decided to arm. The only seam that can
    demonstrate "this check CAN still say no" without doing that is a
    private, mutated DEPLOYED copy: `shared_reference_layout` under
    `@pytest.mark.shared_layout_mutator` hands this test its own fresh,
    unshared, already-built copy (never the tracked template, never the one
    shared reference layout other tests read), whose commit_guardian.json
    this test then edits in place before staging a bloated test_*.py fixture
    and driving the DEPLOYED check_test_fixture_bloat.py through the
    DEPLOYED run_hook.py -- config.py's own load_config() caches per-process
    from a fixed __file__-relative path, so only a fresh subprocess against
    a genuinely different on-disk config can arm it; an in-process override
    cannot (see this AC's own it_requirements).
    """
    cfg_path = shared_reference_layout / "scripts" / "commit_guardian" / "commit_guardian.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg["test_fixture_bloat"] = {
        "_comment": "TEST-ONLY private arming for GE-120h-3 arm4 refusal proof",
        "enabled": True,
        "max_test_file_lines": 500,
        "max_inline_dict_keys": 5,
        "max_parametrize_rows": 3,
        "grandfathered_paths": [],
    }
    cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    fx.init_repo(shared_reference_layout)
    bloat_path = shared_reference_layout / "test_bloat_fixture.py"
    bloat_path.write_text(fx.make_bloated_test_file(), encoding="utf-8")
    fx.stage_all(shared_reference_layout)

    deployed_run_hook = shared_reference_layout / "scripts" / "commit_guardian" / "run_hook.py"
    deployed_check = (
        shared_reference_layout / "scripts" / "commit_guardian" / "check_test_fixture_bloat.py"
    )
    import subprocess

    result = subprocess.run(
        [fx._PYTHON, str(deployed_run_hook), str(deployed_check)],
        cwd=str(shared_reference_layout),
        capture_output=True,
        text=True,
        timeout=fx._SUBPROCESS_TIMEOUT_SECONDS,
    )
    combined = result.stdout + result.stderr

    assert result.returncode != 0, (
        f"An armed check-test-fixture-bloat must refuse a bloated fixture. Got: {combined!r}"
    )
    assert "test_bloat_fixture.py" in combined, (
        f"The refusal must name the offending file. Got: {combined!r}"
    )


class TestCheckAcDoneOnMergeDeclaresNegativeControlNotApplicable(unittest.TestCase):
    def test_ge120h3_check_ac_done_on_merge_declares_negative_control_not_applicable(self):
        # covers: GE-120h-3
        # angle: criterion
        """check-ac-done-on-merge CANNOT refuse anything: its main() returns
        0 unconditionally and its __main__ guard swallows OSError/ValueError
        into sys.exit(0) (verified on disk, not assumed). Per this ticket's
        dispatch brief, arm 4's demonstration for this one check is not a
        refusal but a well-formed `negative_control` declaration on its
        hooks_manifest entry, shaped per config/verification_flow.schema.json's
        $defs/negative_control not_applicable branch
        ({"not_applicable": true, "reason": "..."}), whose reason states the
        STRUCTURAL ground (never produces a non-zero exit; it is a
        fire-and-forget AC-closer, not a gate) -- not a placeholder string.

        RED TODAY: the hooks_manifest entry for check-ac-done-on-merge
        carries no `negative_control` key at all.
        """
        entry = fx.get_hook_entry("check-ac-done-on-merge")
        self.assertIsNotNone(
            entry, msg="check-ac-done-on-merge must still be registered in hooks_manifest.hooks."
        )

        negative_control = entry.get("negative_control")
        self.assertIsInstance(
            negative_control,
            dict,
            msg=(
                "check-ac-done-on-merge's hooks_manifest entry must carry a "
                f"structured negative_control declaration. Got: {negative_control!r}"
            ),
        )
        self.assertIs(
            negative_control.get("not_applicable"),
            True,
            msg=f"negative_control.not_applicable must be true. Got: {negative_control!r}",
        )
        reason = negative_control.get("reason", "")
        self.assertIsInstance(reason, str)
        self.assertTrue(reason.strip(), msg="negative_control.reason must be non-empty.")

        reason_lower = reason.lower()
        names_exit_ground = "non-zero" in reason_lower or "unconditionally" in reason_lower
        names_role_ground = "fire-and-forget" in reason_lower or "gate" in reason_lower
        self.assertTrue(
            names_exit_ground and names_role_ground,
            msg=(
                "negative_control.reason must state the STRUCTURAL ground "
                "(never produces a non-zero exit; a fire-and-forget AC-closer, "
                f"not a gate) rather than a generic placeholder. Got: {reason!r}"
            ),
        )


class TestOnlyTheNonRefusableCheckIsExcusedByDeclaration(unittest.TestCase):
    def test_ge120h3_only_ac_done_on_merge_carries_not_applicable(self):
        # covers: GE-120h-3
        # angle: discrimination
        """Arm 4 as amended: a refusable check cannot be excused by
        declaration. Of the five ids, exactly check-ac-done-on-merge carries
        negative_control.not_applicable: true; the four refusable checks
        carry none. Reads the real manifest. Goes red if a refusable check
        gains a not_applicable declaration, or the fifth loses it."""
        ids = (
            "check-folder-density", "check-sql-complexity", "check-debug-scripts",
            "check-test-fixture-bloat", "check-ac-done-on-merge",
        )
        declared = []
        for hook_id in ids:
            entry = fx.get_hook_entry(hook_id)
            self.assertIsNotNone(entry, msg=f"{hook_id} not registered")
            control = entry.get("negative_control")
            if isinstance(control, dict) and control.get("not_applicable") is True:
                declared.append(hook_id)
        self.assertEqual(["check-ac-done-on-merge"], declared, msg=f"declared: {declared}")
        for hook_id in ids[:4]:
            self.assertNotIn(
                "not_applicable",
                fx.get_hook_entry(hook_id).get("negative_control") or {},
                msg=f"{hook_id} must not carry a not_applicable declaration",
            )


if __name__ == "__main__":
    unittest.main()
