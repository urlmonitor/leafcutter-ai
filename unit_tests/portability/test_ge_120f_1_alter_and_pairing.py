"""
MODULE: test_ge_120f_1_alter_and_pairing
AC: GE-120f-1 — "A check's refusal is established by putting its declared
    known-bad input through the entry point the protected surface uses, and
    the record says what was observed rather than what was declared."
GOVERNING ADR: docs/architecture/adrs/ADR-045-observed-refusal-establishes-protection.md
    (binding). Read it before touching this file — §1 fixes "observation,
    never declaration"; §2 fixes the population source (hooks_manifest.hooks,
    read at run time); §3 fixes the four-value state vocabulary reused
    verbatim from config/verification_flow.schema.json; §5 fixes
    out-of-process/deployed execution via _deployed_check_harness.py.

SPLIT NOTE: one of three files carved out of the former monolithic
    test_ge_120f_1.py (673 counted lines, over the check-file-size 400-line
    budget) — see _ge120f1_harness.py's module docstring for the shared
    fixture/copy-provisioning rationale and the sibling files
    test_ge_120f_1_deployed_and_gate.py and
    test_ge_120f_1_reachability_and_regressions.py. This file carries the
    three tests that exercise the SHARED `pairing_copy()` with disjoint
    fixture ids and additive `upsert_hooks()` calls only (never
    `replace_hooks()`), per pr-reviewer's settled consolidation decision.

REAL-ARTIFACT / OUT-OF-PROCESS NOTE: every test here uses
    `_deployed_check_harness.DeployedCheckHarness` (GE-120c-1) via
    `_ge120f1_harness`'s shared provisioning, per ADR-045 §5. Each fixture
    "check" is a REAL script deployed into a REAL second working copy (a
    real `git init` plus a real `scripts/build.py --target-dir` run),
    invoked as a REAL subprocess through the REAL `run_hook.py` wrapper —
    never imported, never mocked. Declarations and observed records are
    read back from the REAL on-disk `commit_guardian.json` in that deployed
    copy, never a hand-authored fixture standing in for it.

RUN THIS FILE WITH AC_ENFORCE_STRICT=1 (ticket + ADR-045 Operational note):
    without it, `pytest_ac_enforcement` xfail-masks every test below.
        AC_ENFORCE_STRICT=1 python -m pytest unit_tests/portability/test_ge_120f_1_alter_and_pairing.py -v

See test_ge_120f_1_deployed_and_gate.py's module docstring for the
"IMPLEMENTATION CONTRACT ASSUMED BY THIS TEST SUITE" this whole family pins
for python-coder (not repeated in every split file).
"""
# @ac-tag: GE-120f-1

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import _deployed_check_harness as dch  # type: ignore[import]  # noqa: E402
from _ge120f1_harness import (  # noqa: E402
    declaration_fingerprint,
    declaration_only_state,
    hook_entry,
    hook_from_manifest,
    make_argv_check_script,
    pairing_copy,
    run_negative_control_runner,
    shared_harness,
    upsert_hooks,
    write_check_script,
)


class TestGE120f1AlterAndPairing(unittest.TestCase):
    """Uses the ONE shared `pairing_copy()` — see _ge120f1_harness's module
    docstring for why sharing it across these three tests (and the sibling
    files' pairing-copy tests) is safe: every one of them upserts by id
    against disjoint fixture ids and disjoint fixture script filenames."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.harness = shared_harness()
        cls.copy_pairing = pairing_copy()

    def test_ge120f1_record_moves_under_alter_and_revert_while_the_declaration_stays_byte_identical(
        self,
    ) -> None:
        """THE DECISIVE ANTI-DECLARATION DESCRIPTOR. Run 1: a fixture check
        that genuinely rejects its declared bad input records the rejection
        observed. Run 2: the DEPLOYED copy the run loads is altered so the
        same input no longer produces the rejection, leaving the
        declaration byte-identical — the record must read not-observed.
        Run 3: revert, change nothing else — the record must read observed
        again. No implementation that reads the declaration can pass this,
        because the declaration never changes."""
        # covers: GE-120f-1
        # angle: real_artifact
        copy_dir = self.copy_pairing
        hook_id = "ge120f1-fixture-alterable-check"
        script_name = "_ge120f1_alterable_check.py"

        write_check_script(copy_dir, script_name, make_argv_check_script(rejects=True))
        upsert_hooks(copy_dir, [hook_entry(hook_id, script_name)])

        declaration_run1 = declaration_fingerprint(hook_from_manifest(copy_dir, hook_id))

        outcome1 = run_negative_control_runner(self.harness, copy_dir)
        state1 = hook_from_manifest(copy_dir, hook_id)["negative_control"]["currently"]["state"]
        self.assertEqual(
            state1, "passing",
            f"Run 1: the fixture check genuinely rejects its declared bad "
            f"input, so the record must read 'passing' (observed). Runner "
            f"output: {outcome1.output}",
        )

        # ALTER THE DEPLOYED COPY THE RUN LOADS -- never the declaration.
        altered_path = copy_dir / dch._DEPLOYED_CG_REL / script_name  # noqa: SLF001
        loaded_copy_dir = copy_dir  # the exact object passed to invoke_check
        self.assertEqual(
            altered_path.parent,
            loaded_copy_dir / dch._DEPLOYED_CG_REL,  # noqa: SLF001
            "The file being altered must live inside the SAME copy the "
            "runner is invoked against, or the alter-and-revert evidence "
            "is theatre (ADR-045 §5 / ticket Implementation Notes).",
        )
        altered_path.write_text(make_argv_check_script(rejects=False), encoding="utf-8")

        declaration_run2 = declaration_fingerprint(hook_from_manifest(copy_dir, hook_id))
        self.assertEqual(
            declaration_run2, declaration_run1,
            "The negative_control DECLARATION (input/command/expected_result) "
            "must be byte-identical after altering only the check's own "
            "behaviour -- this is the discriminator ADR-045 §1 requires.",
        )

        outcome2 = run_negative_control_runner(self.harness, copy_dir)
        state2 = hook_from_manifest(copy_dir, hook_id)["negative_control"]["currently"]["state"]
        self.assertEqual(
            state2, "failing",
            f"Run 2: the SAME byte-identical declaration now points at a "
            f"check that no longer rejects anything -- the record must "
            f"move to 'failing' (not observed). No implementation that "
            f"reads the declaration can explain this move. Runner output: "
            f"{outcome2.output}",
        )

        # REVERT -- change nothing else.
        altered_path.write_text(make_argv_check_script(rejects=True), encoding="utf-8")
        declaration_run3 = declaration_fingerprint(hook_from_manifest(copy_dir, hook_id))
        self.assertEqual(declaration_run3, declaration_run1)

        outcome3 = run_negative_control_runner(self.harness, copy_dir)
        state3 = hook_from_manifest(copy_dir, hook_id)["negative_control"]["currently"]["state"]
        self.assertEqual(
            state3, "passing",
            f"Run 3: reverted, nothing else changed -- the record must "
            f"read 'passing' again. Runner output: {outcome3.output}",
        )

    def test_ge120f1_never_attempted_and_observed_are_produced_in_one_run_over_the_same_surface(
        self,
    ) -> None:
        """THE PAIRING. One run over a fixture registration surface holding
        (a) a check with a complete, well-formed declaration that the run
        is prevented from invoking (disabled), and (b) a check whose
        declared input genuinely produces its declared rejection. Both
        halves must be true of the SAME run. NAMED MUTATION (run it below):
        a runner that reads the declaration back as its own answer would
        wrongly report (a) as observed."""
        # covers: GE-120f-1
        # angle: criterion
        copy_dir = self.copy_pairing
        prevented_id = "ge120f1-fixture-prevented-check"
        observed_id = "ge120f1-fixture-observed-check"
        prevented_script = "_ge120f1_prevented_check.py"
        observed_script = "_ge120f1_observed_check.py"

        write_check_script(copy_dir, prevented_script, make_argv_check_script(rejects=True))
        write_check_script(copy_dir, observed_script, make_argv_check_script(rejects=True))

        prevented_hook = hook_entry(prevented_id, prevented_script, enabled=False)
        observed_hook = hook_entry(observed_id, observed_script, enabled=True)
        upsert_hooks(copy_dir, [prevented_hook, observed_hook])

        outcome = run_negative_control_runner(self.harness, copy_dir)

        prevented_state = hook_from_manifest(copy_dir, prevented_id)[
            "negative_control"
        ]["currently"]["state"]
        observed_state = hook_from_manifest(copy_dir, observed_id)[
            "negative_control"
        ]["currently"]["state"]

        # NAMED MUTATION (mandatory, run it): a runner that treats a
        # complete, well-formed declaration as evidence of an observed
        # rejection would report "passing" for the PREVENTED check purely
        # because its declaration is complete. Demonstrate this concretely
        # so the assertion below is provably discriminating, not vibes.
        buggy_answer = declaration_only_state(prevented_hook)
        self.assertEqual(
            buggy_answer, "passing",
            "Sanity check on the named-mutation reference function itself: "
            "a declaration-only reader must produce 'passing' for a "
            "complete declaration, or this mutation demonstration proves "
            "nothing about the real assertion below.",
        )

        self.assertEqual(
            prevented_state, "unverified",
            f"'{prevented_id}' is disabled -- the run is PREVENTED from "
            f"invoking it -- so its record MUST read 'unverified' (never "
            f"attempted), however complete its declaration is written. A "
            f"runner shaped like the NAMED MUTATION above would wrongly "
            f"report {buggy_answer!r} here; this assertion must go RED "
            f"under that bug and GREEN once corrected. Runner output: "
            f"{outcome.output}",
        )
        self.assertEqual(
            observed_state, "passing",
            f"'{observed_id}' genuinely rejects its declared bad input and "
            f"is enabled -- in the SAME run, its record must read "
            f"'passing' (observed). Split apart, the assertion above alone "
            f"is satisfied by a runner that records never-attempted for "
            f"EVERYTHING; pairing both in one run rules that out. Runner "
            f"output: {outcome.output}",
        )

    def test_ge120f1_a_check_added_to_the_registration_surface_gets_a_record_of_its_own(
        self,
    ) -> None:
        """Add one further declared check to a FIXTURE registration
        surface, change nothing else, and re-run: the new check has its
        own record, written from its own observation, and no existing
        record changes. Establishes the declaration population is read
        from the surface at run time, not a list inside the runner."""
        # covers: GE-120f-1
        # angle: seam
        copy_dir = self.copy_pairing  # disjoint fixture ids; no interference
        x_id = "ge120f1-fixture-preexisting-check"
        x_script = "_ge120f1_preexisting_check.py"
        write_check_script(copy_dir, x_script, make_argv_check_script(rejects=True))
        upsert_hooks(copy_dir, [hook_entry(x_id, x_script)])

        run_negative_control_runner(self.harness, copy_dir)
        x_record_before = hook_from_manifest(copy_dir, x_id)["negative_control"]["currently"]
        self.assertEqual(
            x_record_before["state"], "passing",
            "Precondition: the pre-existing fixture check must have a "
            "genuine observed record before the new check is added.",
        )

        y_id = "ge120f1-fixture-newly-added-check"
        y_script = "_ge120f1_newly_added_check.py"
        write_check_script(copy_dir, y_script, make_argv_check_script(rejects=True))
        upsert_hooks(copy_dir, [hook_entry(y_id, y_script)])

        run_negative_control_runner(self.harness, copy_dir)

        y_record = hook_from_manifest(copy_dir, y_id)["negative_control"]["currently"]
        self.assertEqual(
            y_record["state"], "passing",
            "The newly added check must get its OWN record, written from "
            "its own observation, without being pre-seeded into the "
            "runner ahead of time.",
        )

        x_record_after = hook_from_manifest(copy_dir, x_id)["negative_control"]["currently"]
        self.assertEqual(
            x_record_after, x_record_before,
            "Adding a further check to the registration surface must not "
            "change any EXISTING check's record -- the population is read "
            "from the surface at run time, never recited from a list held "
            "inside the runner.",
        )


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-21 [test-writer/GE-120f-1]: These three tests were authored as
#   part of the original 7-test RED stub set in the (now split) monolithic
#   test_ge_120f_1.py, before python-coder implemented
#   check_negative_controls.py. See the ticket's python-coder sign-off
#   comment for the original red_baseline errors.
# - 2026-09-21 [python-coder/GE-120f-1, file-size split]: Carved into this
#   file (unchanged assertions and names) from the monolithic
#   test_ge_120f_1.py, which exceeded the 400-line check-file-size budget
#   at 673 counted lines. Consolidated the former exclusive copy_alter /
#   copy_pairing fixtures onto ONE shared pairing_copy() per pr-reviewer's
#   settled decision (see _ge120f1_harness.py's ARCHITECTURE section) —
#   safe because both tests upsert-by-id against disjoint fixture ids.
# ====================================================================
