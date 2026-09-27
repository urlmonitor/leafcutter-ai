"""
MODULE: test_ge_120f_1_ii
AC: GE-120f-1-ii -- "A check that also refuses the work it is meant to accept
    has demonstrated nothing -- refusing everything is as inert as refusing
    nothing, and is reported under its own wording."
GOAL: Failing (RED) test stubs for this AC's acceptable-input pairing and its
    new `discrimination` field (discriminates | refuses_without_discriminating
    | pair_cannot_discriminate | n/a), per architect-review's binding design
    (fb_2026-09-25_33c1543f, AMENDED by fb_2026-09-25_83f0382e). Written
    BEFORE python-coder implements the pairing logic. Shared fixture helpers
    live in `_ge_120f_1_fixtures.py` (as `fx` -- RESULT_LINE_RE/parse_results,
    extended in place with an OPTIONAL `discrimination=` group so
    test_ge_120f_1.py and test_ge_120f_1_i.py stay green), `_ge_120f_1_i_fixtures.py`
    (as `fxi` -- `hook_with()`/`direct_command()`, reused so `entry` is
    always set correctly for -i's `demonstration`), and `_ge_120f_1_ii_fixtures.py`
    (as `fxii` -- this AC's own pairing SHAPES).

CONTRACT PYTHON-CODER MUST IMPLEMENT (the coordinator's binding design,
fb_2026-09-25_33c1543f AS AMENDED by fb_2026-09-25_83f0382e):
    Add two NEW top-level keys to a hooks_manifest hook entry --
    `command` (string) and `pass_criteria` (string) -- as SIBLINGS of
    `negative_control`, never nested inside it and never a second
    declaration store. Put BOTH the existing `negative_control.command`
    (known-bad input) and the new `command` (acceptable input) through a
    real subprocess IN THE SAME RUN. `currently.state` stays exactly the
    existing 4-value enum (passing/failing/blocked/unverified) -- do NOT
    add new state strings. Add a NEW sibling field `discrimination`
    (values: discriminates | refuses_without_discriminating |
    pair_cannot_discriminate | n/a), living outside `currently`, next to
    -i's `demonstration` field, on the per-check record and on the
    NEGATIVE_CONTROL_RESULT stdout line, in the field order
    `... entry_point=<e> demonstration=<d> discrimination=<x> command=<c>`.
    Mapping: bad rejected + acceptable accepted -> state=passing,
    discrimination=discriminates (ALSO requires demonstration==entry_point).
    Bad rejected + acceptable ALSO rejected -> state=failing,
    discrimination=refuses_without_discriminating. Bad NOT rejected ->
    state=failing (existing wording, unaffected by the acceptable side),
    discrimination=n/a. Declaration-level non-discrimination (missing
    top-level `command`, or `shlex.split(command) == shlex.split(
    negative_control["command"])`) -> state=blocked,
    discrimination=pair_cannot_discriminate, detected BEFORE any subprocess
    is run, reported, and the sweep CONTINUES to the remaining hooks -- it
    never aborts. A failed second (acceptable-input) invocation (timeout /
    OSError) -> state=blocked, discrimination=n/a.

DECISION HISTORY
====================================================================
- 2026-09-25 [test-writer/EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs/03,
  GE-120f-1-ii]: Initial red stubs. All 5 descriptors from this AC's own
  test_spec, plus a 6th reachability descriptor (this ticket's own Test
  Requirements table), written against the coordinator's binding design.
  Every descriptor executes the real runner as a real subprocess and reads
  its emitted output -- none asserts on source text.

  NAMED MUTATIONS -- WHY THEY NEED NO HAND-PATCH HERE: this ticket's two
  mandatory injections ("record the rejection as observed as soon as the
  bad input rejects, without running the acceptable side at all" for test 1,
  and "report refuses-both and refuses-neither under one shared wording"
  for test 2) are, today, simply what the runner does BEFORE this ticket's
  own pairing logic lands -- it has no concept of a second (acceptable
  -input) invocation and no `discrimination` field at all, whether or not
  sibling GE-120f-1-i's own `demonstration` classification has already
  landed (verified: it has, and every red failure below shows
  `demonstration=entry_point` already present on the RESULT line, with
  `discrimination` simply absent). Running these descriptors against
  today's runner therefore reproduces both injections exactly, the same
  precedent test_ge_120f_1_i.py's own DECISION HISTORY established for its
  own NAMED MUTATION. No source file is hand-mutated by this test file.
====================================================================
"""
# @ac-tag: GE-120f-1-ii

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent.parent  # unit_tests/portability/ -> worktree root

sys.path.insert(0, str(_THIS_DIR))

import _deployed_check_harness as dch  # type: ignore[import]  # noqa: E402
import _ge_120f_1_fixtures as fx  # type: ignore[import]  # noqa: E402
import _ge_120f_1_ii_fixtures as fxii  # type: ignore[import]  # noqa: E402


class TestGE120f1iiAcceptableInputPairing(unittest.TestCase):
    """Shared, expensive fixture: build ONE real deployed-only working copy
    via the real scripts/build.py ONCE for the whole class -- mirrors
    test_ge_120f_1.py's and test_ge_120f_1_i.py's own RUNTIME BUDGET
    convention."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        tmp_root = Path(cls._tmp.name)
        cls.copy_dir = tmp_root / "copy"
        cls.harness = dch.DeployedCheckHarness(repo_root=_REPO_ROOT)
        cls.harness.create_second_copy(cls.copy_dir)
        cls.deployed_cg_dir = cls.copy_dir / ".leafcutter" / "scripts" / "commit_guardian"
        cls.fixtures_dir = cls.copy_dir / "_ge120f1ii_fixtures"

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    # covers: GE-120f-1-ii
    def test_ge120f1ii_an_indiscriminate_check_and_a_discriminating_check_are_separated_in_one_run(
        self,
    ) -> None:
        """AC-1/AC-2/AC-3. THE PAIRING -- both halves in one invocation. A
        refuses BOTH its declared inputs; B refuses the bad one and accepts
        the acceptable one. In one run, A must be named
        refuses_without_discriminating (record does NOT say observed), the
        run fails, and B's record DOES say observed."""
        # covers: GE-120f-1-ii
        # angle: criterion
        a_id = "ge120f1ii-fixture-indiscriminate-a"
        b_id = "ge120f1ii-fixture-discriminating-b"
        a_script = self.deployed_cg_dir / "_ge120f1ii_indiscriminate_a.py"
        b_script = self.deployed_cg_dir / "_ge120f1ii_discriminating_b.py"
        manifest_path = self.fixtures_dir / "pairing_manifest.json"

        fx.write_script(a_script, fxii.always_reject_script("PAIR_A"))
        fx.write_script(b_script, fx.reject_script("PAIR_B"))

        hook_a = fxii.refuses_both_hook(a_id, a_script)
        hook_b = fxii.discriminating_hook(b_id, b_script)
        fx.write_fixture_manifest(manifest_path, [hook_a, hook_b])

        outcome = self.harness.invoke_check(
            self.copy_dir, fx.RUNNER_ENTRY_DIRECT,
            ["--manifest", str(manifest_path), "--check-id", a_id, "--check-id", b_id],
        )
        self.assertNotEqual(
            outcome.exit_code, 0,
            f"A check that refuses without discriminating must fail the run. Output:\n{outcome.output}",
        )

        results = fx.parse_results(outcome.output)
        self.assertIn(a_id, results, f"No record for A. Output:\n{outcome.output}")
        self.assertIn(b_id, results, f"No record for B. Output:\n{outcome.output}")

        self.assertEqual(
            results[a_id]["discrimination"], "refuses_without_discriminating",
            f"A refuses both its declared inputs -- must be named a check "
            f"that refuses without discriminating. Output:\n{outcome.output}",
        )
        self.assertNotEqual(
            results[a_id]["state"], "passing",
            f"A's record must NOT say the rejection was observed -- refusing "
            f"everything demonstrates nothing. Output:\n{outcome.output}",
        )
        self.assertEqual(
            results[b_id]["discrimination"], "discriminates",
            f"B genuinely discriminates between its two declared inputs. Output:\n{outcome.output}",
        )
        self.assertEqual(
            results[b_id]["state"], "passing",
            f"B's record must say the rejection was observed. Output:\n{outcome.output}",
        )

    # covers: GE-120f-1-ii
    def test_ge120f1ii_refusing_both_and_refusing_neither_are_reported_under_different_wording(
        self,
    ) -> None:
        """AC-5. A check refusing both inputs and a check refusing neither
        must carry DIFFERENT wording -- opposite remedies (narrow vs widen),
        so a reader can tell which repair each needs."""
        # covers: GE-120f-1-ii
        # angle: seam
        both_id = "ge120f1ii-fixture-wording-refuses-both"
        neither_id = "ge120f1ii-fixture-wording-refuses-neither"
        both_script = self.deployed_cg_dir / "_ge120f1ii_wording_both.py"
        neither_script = self.deployed_cg_dir / "_ge120f1ii_wording_neither.py"
        manifest_path = self.fixtures_dir / "wording_manifest.json"

        fx.write_script(both_script, fxii.always_reject_script("WORDING_BOTH"))
        fx.write_script(neither_script, fx.always_allow_script("WORDING_NEITHER"))

        hook_both = fxii.refuses_both_hook(both_id, both_script)
        hook_neither = fxii.refuses_neither_hook(neither_id, neither_script)
        fx.write_fixture_manifest(manifest_path, [hook_both, hook_neither])

        outcome = self.harness.invoke_check(
            self.copy_dir, fx.RUNNER_ENTRY_DIRECT,
            ["--manifest", str(manifest_path), "--check-id", both_id, "--check-id", neither_id],
        )
        results = fx.parse_results(outcome.output)
        self.assertIn(both_id, results, f"Output:\n{outcome.output}")
        self.assertIn(neither_id, results, f"Output:\n{outcome.output}")

        self.assertNotEqual(
            results[both_id]["state"], "passing",
            f"Refuses-both must not read passing. Output:\n{outcome.output}",
        )
        self.assertNotEqual(
            results[neither_id]["state"], "passing",
            f"Refuses-neither must not read passing. Output:\n{outcome.output}",
        )
        self.assertNotEqual(
            results[both_id]["discrimination"], results[neither_id]["discrimination"],
            "A check that refuses everything and a check that refuses "
            "nothing must be reported under DIFFERENT wording -- one has a "
            "refusal that never stops firing, the other one that never "
            f"fires; they are repaired differently. Output:\n{outcome.output}",
        )
        self.assertEqual(
            results[both_id]["discrimination"], "refuses_without_discriminating",
            f"Output:\n{outcome.output}",
        )

    # covers: GE-120f-1-ii
    def test_ge120f1ii_a_non_discriminating_pair_is_reported_and_the_remaining_checks_are_still_examined(
        self,
    ) -> None:
        """AC-4. (a) declares the same input twice; (b) declares two inputs
        that tokenize identically; (c) is a healthy discriminating check. In
        one run, (a) and (b) are each named pair_cannot_discriminate, the
        run fails, AND (c) still receives its own observed record -- a run
        that aborts on a bad declaration leaves (c) unexamined, which is the
        never-attempted state wearing an error message."""
        # covers: GE-120f-1-ii
        # angle: failure
        same_id = "ge120f1ii-fixture-nondiscrim-same"
        tokenize_id = "ge120f1ii-fixture-nondiscrim-tokenize"
        healthy_id = "ge120f1ii-fixture-nondiscrim-healthy"
        same_script = self.deployed_cg_dir / "_ge120f1ii_nondiscrim_same.py"
        tokenize_script = self.deployed_cg_dir / "_ge120f1ii_nondiscrim_tokenize.py"
        healthy_script = self.deployed_cg_dir / "_ge120f1ii_nondiscrim_healthy.py"
        manifest_path = self.fixtures_dir / "nondiscrim_manifest.json"

        fx.write_script(same_script, fx.reject_script("NONDISCRIM_SAME"))
        fx.write_script(tokenize_script, fx.reject_script("NONDISCRIM_TOKENIZE"))
        fx.write_script(healthy_script, fx.reject_script("NONDISCRIM_HEALTHY"))

        hook_same = fxii.identical_pair_hook(same_id, same_script)
        hook_tokenize = fxii.tokenize_equal_pair_hook(tokenize_id, tokenize_script)
        hook_healthy = fxii.discriminating_hook(healthy_id, healthy_script)
        fx.write_fixture_manifest(manifest_path, [hook_same, hook_tokenize, hook_healthy])

        outcome = self.harness.invoke_check(
            self.copy_dir, fx.RUNNER_ENTRY_DIRECT,
            [
                "--manifest", str(manifest_path),
                "--check-id", same_id, "--check-id", tokenize_id, "--check-id", healthy_id,
            ],
        )
        self.assertNotEqual(
            outcome.exit_code, 0,
            f"A non-discriminating pair must fail the run. Output:\n{outcome.output}",
        )

        results = fx.parse_results(outcome.output)
        for check_id in (same_id, tokenize_id, healthy_id):
            with self.subTest(check_id=check_id):
                self.assertIn(check_id, results, f"Output:\n{outcome.output}")

        self.assertEqual(
            results[same_id]["discrimination"], "pair_cannot_discriminate",
            f"A check declaring the same input twice cannot discriminate. Output:\n{outcome.output}",
        )
        self.assertEqual(
            results[tokenize_id]["discrimination"], "pair_cannot_discriminate",
            "Two declared commands that tokenize identically differ in no "
            f"way the check can act on. Output:\n{outcome.output}",
        )
        self.assertEqual(
            results[healthy_id]["discrimination"], "discriminates",
            "The healthy check must still receive its own observed record "
            "-- a run that aborts on a bad declaration leaves it "
            f"unexamined, which this assertion exists to catch. Output:\n{outcome.output}",
        )
        self.assertEqual(
            results[healthy_id]["state"], "passing",
            f"Output:\n{outcome.output}",
        )

    # covers: GE-120f-1-ii
    def test_ge120f1ii_the_acceptable_input_is_read_from_the_one_declaration_and_not_a_second_store(
        self,
    ) -> None:
        """AC-1/AC-4. Remove the acceptable-input side from a fixture
        check's SINGLE declaration entry, change nothing else, and re-run:
        that check must be reported as a pair that cannot discriminate.
        Then restore it and the check must record observed again."""
        # covers: GE-120f-1-ii
        # angle: seam
        check_id = "ge120f1ii-fixture-single-store"
        script_path = self.deployed_cg_dir / "_ge120f1ii_single_store.py"
        manifest_path = self.fixtures_dir / "single_store_manifest.json"

        fx.write_script(script_path, fx.reject_script("SINGLE_STORE"))
        hook = fxii.discriminating_hook(check_id, script_path)
        fx.write_fixture_manifest(manifest_path, [hook])

        def _run() -> dict:
            outcome = self.harness.invoke_check(
                self.copy_dir, fx.RUNNER_ENTRY_DIRECT,
                ["--manifest", str(manifest_path), "--check-id", check_id],
            )
            return fx.parse_results(outcome.output).get(check_id, {}), outcome

        # ---- Run 1: acceptable side declared -- discriminates. ----
        record_1, outcome_1 = _run()
        self.assertEqual(
            record_1.get("discrimination"), "discriminates",
            f"Output:\n{outcome_1.output}",
        )
        self.assertEqual(record_1.get("state"), "passing", f"Output:\n{outcome_1.output}")

        # ---- Remove the acceptable side from the SINGLE declaration entry. ----
        manifest_current = fx.read_manifest(manifest_path)
        hook_current = fx.hook_by_id(manifest_current, check_id)
        del hook_current["command"]
        del hook_current["pass_criteria"]
        manifest_path.write_text(json.dumps(manifest_current, indent=2) + "\n", encoding="utf-8")

        # ---- Run 2: acceptable side missing -- cannot discriminate. ----
        record_2, outcome_2 = _run()
        self.assertEqual(
            record_2.get("discrimination"), "pair_cannot_discriminate",
            "An implementation reading the acceptable input from a SECOND "
            "store would keep discriminating even after the ONE "
            f"declaration's acceptable side is emptied. Output:\n{outcome_2.output}",
        )

        # ---- Restore; nothing else changes. ----
        manifest_restore = fx.read_manifest(manifest_path)
        hook_restore = fx.hook_by_id(manifest_restore, check_id)
        hook_restore["command"] = hook["command"]
        hook_restore["pass_criteria"] = hook["pass_criteria"]
        manifest_path.write_text(json.dumps(manifest_restore, indent=2) + "\n", encoding="utf-8")

        # ---- Run 3: discriminates again. ----
        record_3, outcome_3 = _run()
        self.assertEqual(
            record_3.get("discrimination"), "discriminates",
            f"Output:\n{outcome_3.output}",
        )
        self.assertEqual(record_3.get("state"), "passing", f"Output:\n{outcome_3.output}")

    # covers: GE-120f-1-ii
    def test_ge120f1ii_deployed_runner_performs_both_invocations_in_a_cold_process(
        self,
    ) -> None:
        """AC-1 (deployed entry point). After build.py, the DEPLOYED runner
        performs BOTH invocations per examined check in a cold process --
        the invocation count observed at the entry point is two per
        examined check, not one. A helper outside
        templates/scripts/commit_guardian/ without a deploy-map entry
        surfaces here as ModuleNotFoundError."""
        # covers: GE-120f-1-ii
        # angle: deployed
        self.assertTrue(
            self.harness.deployed_layout_present(self.copy_dir),
            "Precondition: scripts/build.py must have produced a real "
            ".leafcutter/scripts/commit_guardian/ layout in the deployed copy.",
        )
        os.environ["AC_ENFORCE_STRICT"] = os.environ.get("AC_ENFORCE_STRICT", "1")

        check_id = "ge120f1ii-fixture-deployed-count"
        script_path = self.deployed_cg_dir / "_ge120f1ii_deployed_count.py"
        log_path = self.fixtures_dir / "deployed_count.log"
        manifest_path = self.fixtures_dir / "deployed_count_manifest.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if log_path.exists():
            log_path.unlink()

        fx.write_script(script_path, fxii.counting_script("DEPLOYED_COUNT", log_path))
        bad_command = fxii.bad_command_for(script_path)
        accept_command = fxii.acceptable_command_for(script_path)
        hook = fxii.with_acceptable(
            {"id": check_id, "tier": "judgment", "name": "GE-120f-1-ii deployed count",
             "entry": bad_command, "entry_point": bad_command,
             "negative_control": {"input": "BADINPUT", "command": bad_command, "expected_result": "non-zero exit"}},
            accept_command,
        )
        fx.write_fixture_manifest(manifest_path, [hook])

        outcome = self.harness.invoke_check(
            self.copy_dir, fx.RUNNER_ENTRY_DIRECT,
            ["--manifest", str(manifest_path), "--check-id", check_id],
        )
        self.assertNotIn(
            "ModuleNotFoundError", outcome.output,
            f"A helper imported from outside templates/scripts/commit_guardian/ "
            f"with no deploy-map entry raises ModuleNotFoundError. Output:\n{outcome.output}",
        )

        self.assertTrue(log_path.is_file(), f"Precondition: the fixture check must have logged. Output:\n{outcome.output}")
        lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        self.assertEqual(
            len(lines), 2,
            "One examined check with a declared acceptable-input pair must "
            "produce exactly TWO invocations in the SAME run -- one per "
            f"declared input. Logged invocations: {lines!r}. Output:\n{outcome.output}",
        )
        self.assertEqual(sorted(lines), ["BADINPUT", "GOODINPUT"], f"Logged: {lines!r}")

    # covers: GE-120f-1-ii
    def test_ge_120f_1_ii_reachable_from_entry_point(self) -> None:
        """Reachability floor. PRODUCTION ENTRY POINT resolved per this
        ticket's own Reachability Entry-Point Resolution procedure: the
        check-negative-control-liveness hook's own registered `entry`
        (commit_guardian.json) is `python run_hook.py
        check_negative_control_liveness.py --manifest ...` -- the
        run_hook.py-wrapped pre-commit-hook form, mirroring
        test_ge_120f_1.py's and test_ge_120f_1_i.py's own reachability
        precedent: it shows `discrimination` is CONSUMED in the GATE's own
        control flow (its exit code), not merely computed and printed. Over
        a population containing only a pair-cannot-discriminate check, the
        GATE's exit code must be non-zero; over a population containing
        only a genuinely discriminating check, it must be zero."""
        # covers: GE-120f-1-ii
        # angle: reachability
        cannot_id = "ge120f1ii-fixture-reachable-cannot-discriminate"
        cannot_script = self.deployed_cg_dir / "_ge120f1ii_reachable_cannot.py"
        cannot_manifest_path = self.fixtures_dir / "reachable_cannot_manifest.json"
        fx.write_script(cannot_script, fx.reject_script("REACHABLE_CANNOT"))
        fx.write_fixture_manifest(
            cannot_manifest_path, [fxii.identical_pair_hook(cannot_id, cannot_script)],
        )

        cannot_outcome = self.harness.invoke_check(
            self.copy_dir, fx.RUNNER_ENTRY_WRAPPED,
            ["--manifest", str(cannot_manifest_path), "--check-id", cannot_id],
        )
        self.assertNotEqual(
            cannot_outcome.exit_code, 0,
            "The GATE's own exit code (run_hook.py-wrapped invocation) must "
            "be non-zero over a population whose only examined check cannot "
            f"discriminate. Output:\n{cannot_outcome.output}",
        )

        discriminating_id = "ge120f1ii-fixture-reachable-discriminates"
        discriminating_script = self.deployed_cg_dir / "_ge120f1ii_reachable_discriminates.py"
        discriminating_manifest_path = self.fixtures_dir / "reachable_discriminates_manifest.json"
        fx.write_script(discriminating_script, fx.reject_script("REACHABLE_DISCRIMINATES"))
        fx.write_fixture_manifest(
            discriminating_manifest_path,
            [fxii.discriminating_hook(discriminating_id, discriminating_script)],
        )

        discriminating_outcome = self.harness.invoke_check(
            self.copy_dir, fx.RUNNER_ENTRY_WRAPPED,
            ["--manifest", str(discriminating_manifest_path), "--check-id", discriminating_id],
        )
        self.assertEqual(
            discriminating_outcome.exit_code, 0,
            "Over a population where the only examined check genuinely "
            f"discriminates, the GATE's own exit must be zero. Output:\n{discriminating_outcome.output}",
        )


    # covers: GE-120f-1-ii
    def test_ge120f1ii_a_check_that_declares_no_acceptable_input_is_not_passing(self) -> None:
        """AC-1/AC-2. A hook declaring negative_control with NO top-level
        acceptable-input `command` must record state=blocked,
        discrimination=pair_cannot_discriminate, and fail the run -- while
        a healthy discriminating hook in the SAME run still records
        passing."""
        # covers: GE-120f-1-ii
        # angle: criterion
        no_accept_id = "ge120f1ii-fixture-no-acceptable-input"
        healthy_id = "ge120f1ii-fixture-no-acceptable-healthy"
        no_accept_script = self.deployed_cg_dir / "_ge120f1ii_no_acceptable.py"
        healthy_script = self.deployed_cg_dir / "_ge120f1ii_no_acceptable_healthy.py"
        manifest_path = self.fixtures_dir / "no_acceptable_manifest.json"
        fx.write_script(no_accept_script, fx.reject_script("NO_ACCEPTABLE"))
        fx.write_script(healthy_script, fx.reject_script("NO_ACCEPTABLE_HEALTHY"))
        fx.write_fixture_manifest(manifest_path, [
            fxii.missing_acceptable_hook(no_accept_id, no_accept_script),
            fxii.discriminating_hook(healthy_id, healthy_script),
        ])

        outcome = self.harness.invoke_check(
            self.copy_dir, fx.RUNNER_ENTRY_DIRECT,
            ["--manifest", str(manifest_path), "--check-id", no_accept_id, "--check-id", healthy_id],
        )
        results = fx.parse_results(outcome.output)
        self.assertNotEqual(outcome.exit_code, 0, f"Output:\n{outcome.output}")
        self.assertIn(no_accept_id, results, f"Output:\n{outcome.output}")
        self.assertIn(healthy_id, results, f"Output:\n{outcome.output}")
        self.assertEqual(
            results[no_accept_id]["state"], "blocked",
            f"No acceptable input declared must not read passing. Output:\n{outcome.output}",
        )
        self.assertEqual(results[no_accept_id]["discrimination"], "pair_cannot_discriminate")
        self.assertEqual(results[healthy_id]["state"], "passing", f"Output:\n{outcome.output}")


if __name__ == "__main__":
    unittest.main()
