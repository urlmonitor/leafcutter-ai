"""
MODULE: test_ge_120f_1_i
AC: GE-120f-1-i -- "A refusal produced by reaching inside a check is not a
    demonstration -- the run states the entry point it used, and only the
    entry point the protected surface invokes counts."
GOAL: Failing (RED) test stubs for this AC's `demonstration` classification
    (entry_point | reach_inside | n/a) and its stated-entry-point rule, per
    architect-review's own design (fb_2026-09-25_7560dc1f, Q1/Q2). Written
    BEFORE python-coder implements the classification. Ground truth for
    "the entry point the protected surface invokes" is the hook's own
    registered `entry` field (never `entry_point`, which is human prose on
    today's real registration surface). Shared fixture helpers live in the
    sibling modules `_ge_120f_1_fixtures.py` (imported as `fx` -- the
    shared, load-bearing RESULT_LINE_RE/parse_results parser, extended in
    place with an OPTIONAL `demonstration=` group so test_ge_120f_1.py stays
    green) and `_ge_120f_1_i_fixtures.py` (imported as `fxi` -- the
    reach-inside/entry-point fixture SHAPES this record's own descriptors
    need).

CONTRACT PYTHON-CODER MUST IMPLEMENT (architect-review's own Q1/Q2 design):
    Extend `check_negative_control_liveness.py`'s per-check record with a
    new field `demonstration` (values: "entry_point" | "reach_inside" |
    "n/a"), built by comparing the hook's own `entry` field (ground truth)
    against the tokens `_run_negative_control_command` actually performed
    for `negative_control.command`, tolerant of the `run_hook.py <target>`
    wrapper shape. Composition rule: `state` is "passing" ONLY when
    `demonstration == "entry_point"` AND the subprocess exited non-zero;
    every other examined-and-ran case (including a reach-inside command
    that itself exits non-zero) is "failing". `blocked`/`unverified` keep
    their existing meaning; `demonstration` for those is "n/a". The
    existing `NEGATIVE_CONTROL_RESULT` stdout line's `entry_point=` value
    must be rebuilt from the invocation ACTUALLY PERFORMED (a single
    space-free token, e.g. a resolved script basename), never echoed from
    the hook's declared `entry_point`/`entry` field, with a new
    `demonstration=` token inserted before `command=`.

DECISION HISTORY
====================================================================
- 2026-09-25 [test-writer/EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs/02,
  GE-120f-1-i]: Initial red stubs. All 6 descriptors from this AC's own
  test_spec, written against architect-review's binding Q1/Q2 design
  (fb_2026-09-25_7560dc1f) since python-coder has not yet implemented the
  `demonstration` field. Every descriptor executes the real runner as a
  real subprocess and reads its emitted output -- none asserts on source
  text (per CLAUDE.md's grep rule, restated in this AC's own
  test_rationale).
====================================================================
"""
# @ac-tag: GE-120f-1-i

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent.parent  # unit_tests/portability/ -> worktree root

sys.path.insert(0, str(_THIS_DIR))

import _ge_120f_1_base as base  # type: ignore[import]  # noqa: E402
import _ge_120f_1_fixtures as fx  # type: ignore[import]  # noqa: E402
import _ge_120f_1_i_fixtures as fxi  # type: ignore[import]  # noqa: E402


class TestGE120f1iEntryPointDemonstration(base.GE120f1DeployedCopyTestCase):
    """Shared, expensive fixture: build ONE real deployed-only working copy
    via the real scripts/build.py ONCE for the whole class -- mirrors
    test_ge_120f_1.py's own RUNTIME BUDGET convention. setUpClass/
    tearDownClass live on the shared
    `_ge_120f_1_base.GE120f1DeployedCopyTestCase` -- only the fixtures
    subdirectory varies here."""

    fixtures_subdir = "_ge120f1i_fixtures"

    # covers: GE-120f-1-i
    def test_ge120f1i_a_reach_inside_refusal_and_an_entry_point_refusal_are_distinguished_in_one_run(
        self,
    ) -> None:
        """AC-1/AC-3. THE PAIRING -- both halves in one invocation. Check A:
        readme_read_guard shape (probe_script) -- its entry point never
        rejects; a reach-inside driver script (importing it and calling
        decide()) DOES. Check B: genuinely rejects through its own entry
        point. NAMED MUTATION: today's runner (GE-120f-1, unextended) has
        no entry-point comparison at all -- it treats negative_control.
        command's own exit code as the observation. That IS the injection
        this AC names ("obtain the observation by importing the check and
        calling the part of it that decides"); this assertion is written to
        go red naming A under exactly that current behaviour."""
        # covers: GE-120f-1-i
        # angle: criterion
        a_id = "ge120f1i-fixture-pairing-reach-inside"
        b_id = "ge120f1i-fixture-pairing-entry-point"
        probe_path = self.deployed_cg_dir / "_ge120f1i_pairing_probe.py"
        driver_path = self.deployed_cg_dir / "_ge120f1i_pairing_driver.py"
        b_script_path = self.deployed_cg_dir / "_ge120f1i_pairing_b.py"
        manifest_path = self.fixtures_dir / "pairing_manifest.json"

        fx.write_script(probe_path, fxi.probe_script("PAIRING_A"))
        fx.write_script(driver_path, fxi.reach_inside_driver_script(self.deployed_cg_dir, probe_path.stem))
        fx.write_script(b_script_path, fx.reject_script("PAIRING_B"))

        hook_a = fxi.hook_with(
            a_id, entry=fxi.direct_command(probe_path), command=fxi.direct_command(driver_path),
            accept_command=fxi.direct_command(driver_path, "GOODINPUT"),
        )
        hook_b = fxi.hook_with(
            b_id, entry=fxi.direct_command(b_script_path), command=fxi.direct_command(b_script_path),
            accept_command=fxi.direct_command(b_script_path, "GOODINPUT"),
        )
        fx.write_fixture_manifest(manifest_path, [hook_a, hook_b])

        outcome = self.harness.invoke_check(
            self.copy_dir, fx.RUNNER_ENTRY_DIRECT,
            ["--manifest", str(manifest_path), "--check-id", a_id, "--check-id", b_id],
        )
        results = fx.parse_results(outcome.output)
        self.assertIn(a_id, results, f"No record for A. Output:\n{outcome.output}")
        self.assertIn(b_id, results, f"No record for B. Output:\n{outcome.output}")

        self.assertEqual(
            results[a_id]["demonstration"], "reach_inside",
            "A's declared rejection is reachable only by importing and "
            "calling decide() -- its entry point never produces it -- so it "
            f"must be NAMED as a reach-inside refusal. Output:\n{outcome.output}",
        )
        self.assertEqual(
            results[a_id]["state"], "failing",
            "A's record must say the rejection was NOT observed via the "
            "entry point, even though the reach-inside driver itself exits "
            f"non-zero. Output:\n{outcome.output}",
        )
        self.assertEqual(
            results[b_id]["demonstration"], "entry_point",
            f"B genuinely rejects through its own entry point. Output:\n{outcome.output}",
        )
        self.assertEqual(
            results[b_id]["state"], "passing",
            f"B's rejection must be recorded observed. Output:\n{outcome.output}",
        )

    # covers: GE-120f-1-i
    def test_ge120f1i_the_stated_entry_point_is_the_one_invoked_not_the_one_declared(
        self,
    ) -> None:
        """AC-2. A fixture check whose declared `entry_point` NAMES entry
        point X (misleading human prose) while `entry`/`negative_control.
        command` both really invoke script Y. Assert the run STATES Y.
        NAMED MUTATION: today's runner builds the stated entry_point
        verbatim from the hook's own declared `entry_point` field
        (`_entry_point_of()`); this descriptor is written to go red naming
        X under exactly that current behaviour."""
        # covers: GE-120f-1-i
        # angle: seam
        check_id = "ge120f1i-fixture-stated-not-declared"
        script_path = self.deployed_cg_dir / "_ge120f1i_stated_script.py"
        manifest_path = self.fixtures_dir / "stated_manifest.json"
        declared_x = "declared-entry-point-X-human-prose-not-a-real-path"

        fx.write_script(script_path, fx.reject_script("STATED"))
        real_command = fxi.direct_command(script_path)
        hook = fxi.hook_with(
            check_id, entry=real_command, command=real_command, entry_point=declared_x,
            accept_command=fxi.direct_command(script_path, "GOODINPUT"),
        )
        fx.write_fixture_manifest(manifest_path, [hook])

        outcome = self.harness.invoke_check(
            self.copy_dir, fx.RUNNER_ENTRY_DIRECT,
            ["--manifest", str(manifest_path), "--check-id", check_id],
        )
        results = fx.parse_results(outcome.output)
        self.assertIn(check_id, results, f"No record. Output:\n{outcome.output}")

        stated = results[check_id]["entry_point"]
        self.assertNotEqual(
            stated, declared_x,
            "The stated entry_point must come from the invocation actually "
            "performed, never from the declared entry_point field, even "
            f"when the declaration is well-formed prose. Output:\n{outcome.output}",
        )
        self.assertIn(
            script_path.stem, stated,
            f"The stated entry_point must identify the real script actually "
            f"invoked ({script_path.stem}). Stated: {stated!r}. Output:\n{outcome.output}",
        )

    # covers: GE-120f-1-i
    def test_ge120f1i_the_entry_point_for_any_named_check_is_recoverable_from_the_report_alone(
        self,
    ) -> None:
        """AC-4. Parse ONLY the run's emitted output -- no manifest re-read,
        no registry, no declaration file opened after the run -- and
        recover the entry point used for every named check. Compared
        against identity captured INDEPENDENTLY in local variables at
        fixture-construction time, never re-derived from a post-run file
        read."""
        # covers: GE-120f-1-i
        # angle: criterion
        entry_id_1 = "ge120f1i-fixture-recover-one"
        entry_id_2 = "ge120f1i-fixture-recover-two"
        reach_id = "ge120f1i-fixture-recover-reach"
        script_1 = self.deployed_cg_dir / "_ge120f1i_recover_one.py"
        script_2 = self.deployed_cg_dir / "_ge120f1i_recover_two.py"
        probe = self.deployed_cg_dir / "_ge120f1i_recover_probe.py"
        driver = self.deployed_cg_dir / "_ge120f1i_recover_driver.py"
        manifest_path = self.fixtures_dir / "recover_manifest.json"

        fx.write_script(script_1, fx.reject_script("RECOVER1"))
        fx.write_script(script_2, fx.reject_script("RECOVER2"))
        fx.write_script(probe, fxi.probe_script("RECOVERP"))
        fx.write_script(driver, fxi.reach_inside_driver_script(self.deployed_cg_dir, probe.stem))

        # Captured independently, BEFORE the run -- never re-derived from a
        # post-run file read.
        expected_identity = {entry_id_1: script_1.stem, entry_id_2: script_2.stem, reach_id: driver.stem}

        fx.write_fixture_manifest(
            manifest_path,
            [
                fxi.hook_with(
                    entry_id_1, entry=fxi.direct_command(script_1), command=fxi.direct_command(script_1),
                    accept_command=fxi.direct_command(script_1, "GOODINPUT"),
                ),
                fxi.hook_with(
                    entry_id_2, entry=fxi.direct_command(script_2), command=fxi.direct_command(script_2),
                    accept_command=fxi.direct_command(script_2, "GOODINPUT"),
                ),
                fxi.hook_with(
                    reach_id, entry=fxi.direct_command(probe), command=fxi.direct_command(driver),
                    accept_command=fxi.direct_command(driver, "GOODINPUT"),
                ),
            ],
        )

        outcome = self.harness.invoke_check(
            self.copy_dir, fx.RUNNER_ENTRY_DIRECT,
            [
                "--manifest", str(manifest_path),
                "--check-id", entry_id_1, "--check-id", entry_id_2, "--check-id", reach_id,
            ],
        )

        # Parse ONLY the run's own emitted output.
        results = fx.parse_results(outcome.output)
        self.assertTrue(results, f"Recovered set must be non-empty. Output:\n{outcome.output}")

        for check_id, expected_stem in expected_identity.items():
            with self.subTest(check_id=check_id):
                self.assertIn(check_id, results, f"Output:\n{outcome.output}")
                stated = results[check_id]["entry_point"]
                self.assertTrue(stated, f"{check_id} has no stated entry_point. Output:\n{outcome.output}")
                self.assertIn(
                    expected_stem, stated,
                    f"{check_id}'s stated entry_point ({stated!r}) must recover "
                    f"the actually-invoked script identity ({expected_stem}) from "
                    f"the report alone. Output:\n{outcome.output}",
                )

        recovered_ids = set(results.keys()) & set(expected_identity.keys())
        self.assertEqual(
            recovered_ids, set(expected_identity.keys()),
            f"The recovered set must equal the set actually invoked. Output:\n{outcome.output}",
        )

    # covers: GE-120f-1-i
    def test_ge120f1i_in_process_invocation_by_the_protected_surface_is_not_penalised(
        self,
    ) -> None:
        """AC-1/AC-3. THE PROXY THAT MUST NOT BECOME THE CRITERION. Legit:
        `entry` declares the DIRECT form; `negative_control.command` wraps
        the SAME script through the real deployed run_hook.py (an EXTRA
        process hop) -- architect-review's own tolerated wrapper shape.
        Illegit: `entry` declares a DIFFERENT check's own direct entry;
        `negative_control.command` is a plain, SINGLE-hop direct call --
        the SAME literal shape as any legitimate direct entry -- but
        targets a script neither this hook's `entry` nor the protected
        surface ever names. A process-boundary-counting implementation
        misjudges BOTH at once: the wrapped-but-same-target legit case as a
        mismatch, and the simple-but-different-target illegit case as a
        match."""
        # covers: GE-120f-1-i
        # angle: boundary
        legit_id = "ge120f1i-fixture-boundary-legit"
        illegit_id = "ge120f1i-fixture-boundary-illegit"
        legit_script = self.deployed_cg_dir / "_ge120f1i_boundary_legit.py"
        illegit_entry_script = self.deployed_cg_dir / "_ge120f1i_boundary_illegit_entry.py"
        illegit_other_script = self.deployed_cg_dir / "_ge120f1i_boundary_illegit_other.py"
        run_hook_path = self.deployed_cg_dir / "run_hook.py"
        manifest_path = self.fixtures_dir / "boundary_manifest.json"

        fx.write_script(legit_script, fx.reject_script("BOUNDARY_LEGIT"))
        fx.write_script(illegit_entry_script, fx.reject_script("BOUNDARY_ILLEGIT_ENTRY"))
        fx.write_script(illegit_other_script, fx.reject_script("BOUNDARY_ILLEGIT_OTHER"))
        self.assertTrue(run_hook_path.is_file(), "Precondition: the deployed run_hook.py must exist.")

        legit_hook = fxi.hook_with(
            legit_id,
            entry=fxi.direct_command(legit_script),
            command=f"{sys.executable} {run_hook_path} {legit_script} BADINPUT",
            accept_command=f"{sys.executable} {run_hook_path} {legit_script} GOODINPUT",
        )
        illegit_hook = fxi.hook_with(
            illegit_id, entry=fxi.direct_command(illegit_entry_script), command=fxi.direct_command(illegit_other_script),
            accept_command=fxi.direct_command(illegit_other_script, "GOODINPUT"),
        )
        fx.write_fixture_manifest(manifest_path, [legit_hook, illegit_hook])

        outcome = self.harness.invoke_check(
            self.copy_dir, fx.RUNNER_ENTRY_DIRECT,
            ["--manifest", str(manifest_path), "--check-id", legit_id, "--check-id", illegit_id],
        )
        results = fx.parse_results(outcome.output)
        self.assertIn(legit_id, results, f"Output:\n{outcome.output}")
        self.assertIn(illegit_id, results, f"Output:\n{outcome.output}")

        self.assertEqual(
            results[legit_id]["demonstration"], "entry_point",
            "An extra process hop through the recognised run_hook.py "
            "wrapper must not defeat identity matching against the SAME "
            f"target script. Output:\n{outcome.output}",
        )
        self.assertEqual(
            results[legit_id]["state"], "passing",
            f"Legit check genuinely rejects via its own entry point. Output:\n{outcome.output}",
        )
        self.assertEqual(
            results[illegit_id]["demonstration"], "reach_inside",
            "A single-hop direct command targeting a DIFFERENT script than "
            "this hook's own `entry` must be classified reach-inside, "
            f"whatever its literal shape resembles. Output:\n{outcome.output}",
        )
        self.assertEqual(
            results[illegit_id]["state"], "failing",
            "The illegit invocation must record NOT observed even though "
            f"the way-in-nobody-uses script itself genuinely rejects. Output:\n{outcome.output}",
        )

    # covers: GE-120f-1-i
    def test_ge120f1i_deployed_runner_states_entry_points_when_loaded_in_a_cold_process(
        self,
    ) -> None:
        """AC-2. After build.py, the DEPLOYED runner emits the per-check
        entry-point/demonstration statement in a cold process with the
        source tree off the import path. A resolver helper placed outside
        templates/scripts/commit_guardian/ with no scripts/build_phases.py
        deploy-map entry surfaces here as ModuleNotFoundError rather than
        passing."""
        # covers: GE-120f-1-i
        # angle: deployed
        self.assertTrue(
            self.harness.deployed_layout_present(self.copy_dir),
            "Precondition: scripts/build.py must have produced a real "
            ".leafcutter/scripts/commit_guardian/ layout in the deployed copy.",
        )
        os.environ["AC_ENFORCE_STRICT"] = os.environ.get("AC_ENFORCE_STRICT", "1")

        check_id = "ge120f1i-fixture-deployed-cold"
        script_path = self.deployed_cg_dir / "_ge120f1i_deployed_script.py"
        manifest_path = self.fixtures_dir / "deployed_manifest.json"
        fx.write_script(script_path, fx.reject_script("DEPLOYED_COLD"))
        command = fxi.direct_command(script_path)
        hook = fxi.hook_with(
            check_id, entry=command, command=command,
            accept_command=fxi.direct_command(script_path, "GOODINPUT"),
        )
        fx.write_fixture_manifest(manifest_path, [hook])

        outcome = self.harness.invoke_check(
            self.copy_dir, fx.RUNNER_ENTRY_DIRECT,
            ["--manifest", str(manifest_path), "--check-id", check_id],
        )
        self.assertNotIn(
            "ModuleNotFoundError", outcome.output,
            "A resolver helper imported from outside "
            "templates/scripts/commit_guardian/ with no "
            "scripts/build_phases.py deploy-map entry raises "
            f"ModuleNotFoundError in the deployed copy. Output:\n{outcome.output}",
        )
        results = fx.parse_results(outcome.output)
        self.assertIn(check_id, results, f"Output:\n{outcome.output}")
        self.assertEqual(
            results[check_id]["demonstration"], "entry_point",
            f"The deployed cold-process copy must classify a genuine "
            f"entry-point demonstration correctly. Output:\n{outcome.output}",
        )
        self.assertTrue(
            results[check_id]["entry_point"],
            f"The deployed copy must state a non-empty entry point. Output:\n{outcome.output}",
        )

    # covers: GE-120f-1-i
    def test_ge_120f_1_i_reachable_from_entry_point(self) -> None:
        """AC-2/AC-3, reachability floor. PRODUCTION ENTRY POINT resolved
        per this ticket's own Reachability Entry-Point Resolution
        procedure: the check-negative-control-liveness hook's own
        registered `entry` (commit_guardian.json) is `python run_hook.py
        check_negative_control_liveness.py --manifest ...` -- the
        run_hook.py-wrapped pre-commit-hook form, mirroring
        test_ge_120f_1.py's own precedent
        (test_ge120f1_the_runs_refusal_changes_the_verdict_of_the_gate_that_invokes_it),
        the stronger proof: it shows the `demonstration` classification is
        CONSUMED in control flow by the gate that invokes it, not merely
        computed and ignored. Over a population containing only a
        reach-inside-classified check whose OWN reach-inside command exits
        non-zero, the GATE's exit code must still be non-zero -- proving
        `demonstration`, not the raw subprocess exit code, drives the
        gate's real verdict."""
        # covers: GE-120f-1-i
        # angle: reachability
        reach_id = "ge120f1i-fixture-reachable-reach-inside"
        probe = self.deployed_cg_dir / "_ge120f1i_reachable_probe.py"
        driver = self.deployed_cg_dir / "_ge120f1i_reachable_driver.py"
        fx.write_script(probe, fxi.probe_script("REACHABLE"))
        fx.write_script(driver, fxi.reach_inside_driver_script(self.deployed_cg_dir, probe.stem))
        reach_manifest_path = self.fixtures_dir / "reachable_reach_manifest.json"
        fx.write_fixture_manifest(
            reach_manifest_path,
            [fxi.hook_with(
                reach_id, entry=fxi.direct_command(probe), command=fxi.direct_command(driver),
                accept_command=fxi.direct_command(driver, "GOODINPUT"),
            )],
        )

        reach_outcome = self.harness.invoke_check(
            self.copy_dir, fx.RUNNER_ENTRY_WRAPPED,
            ["--manifest", str(reach_manifest_path), "--check-id", reach_id],
        )
        self.assertNotEqual(
            reach_outcome.exit_code, 0,
            "The GATE's own exit code (run_hook.py-wrapped invocation) must "
            "be non-zero over a population whose only examined check is a "
            "reach-inside refusal, even though the reach-inside command "
            f"itself exits non-zero. Output:\n{reach_outcome.output}",
        )

        clean_id = "ge120f1i-fixture-reachable-entry-point"
        clean_script = self.deployed_cg_dir / "_ge120f1i_reachable_clean.py"
        fx.write_script(clean_script, fx.reject_script("REACHABLE_CLEAN"))
        clean_manifest_path = self.fixtures_dir / "reachable_clean_manifest.json"
        clean_command = fxi.direct_command(clean_script)
        fx.write_fixture_manifest(clean_manifest_path, [fxi.hook_with(
            clean_id, entry=clean_command, command=clean_command,
            accept_command=fxi.direct_command(clean_script, "GOODINPUT"),
        )])

        clean_outcome = self.harness.invoke_check(
            self.copy_dir, fx.RUNNER_ENTRY_WRAPPED,
            ["--manifest", str(clean_manifest_path), "--check-id", clean_id],
        )
        self.assertEqual(
            clean_outcome.exit_code, 0,
            "Over a population where the only examined check is a genuine "
            f"entry-point demonstration, the GATE's own exit must be zero. Output:\n{clean_outcome.output}",
        )


if __name__ == "__main__":
    unittest.main()
