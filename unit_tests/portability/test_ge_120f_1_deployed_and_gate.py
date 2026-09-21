"""
MODULE: test_ge_120f_1_deployed_and_gate
AC: GE-120f-1 — "A check's refusal is established by putting its declared
    known-bad input through the entry point the protected surface uses, and
    the record says what was observed rather than what was declared."
GOVERNING ADR: docs/architecture/adrs/ADR-045-observed-refusal-establishes-protection.md
    (binding) — §4 fixes the runner's path/registration and deployment;
    §7 fixes the zero-population refusal; §8 fixes that the runner's
    refusal must move a real gate's verdict.

SPLIT NOTE: one of three files carved out of the former monolithic
    test_ge_120f_1.py — see _ge120f1_harness.py's module docstring for the
    shared fixture/copy-provisioning rationale and the sibling files
    test_ge_120f_1_alter_and_pairing.py and
    test_ge_120f_1_reachability_and_regressions.py. This file carries the
    cold-process deployment test and the real-registration-surface
    count-and-membership test (both on the SHARED `pairing_copy()`), plus
    the one test that needs the EXCLUSIVE `gate_copy()` (its
    `replace_hooks()` calls wipe the whole hooks list, per pr-reviewer's
    settled decision — see _ge120f1_harness.py's ARCHITECTURE section for
    why this one test cannot share).

RUN THIS FILE WITH AC_ENFORCE_STRICT=1 (ticket + ADR-045 Operational note):
        AC_ENFORCE_STRICT=1 python -m pytest unit_tests/portability/test_ge_120f_1_deployed_and_gate.py -v

====================================================================
IMPLEMENTATION CONTRACT ASSUMED BY THIS TEST SUITE (pins the whole family,
authored once here — not repeated in the sibling files)
====================================================================
The ticket and ADR-045 fix the vocabulary and the deployment/registration
rules, but leave the runner's exact I/O shape to the implementer. This test
family pins down the following so python-coder has an unambiguous target —
each clause is grounded in a specific ticket/ADR clause cited inline:

1. PATH + REGISTRATION (ADR-045 §4): the runner lives at
   `templates/scripts/commit_guardian/check_negative_controls.py`, is
   deployed verbatim by `build_commit_guardian`'s directory copy (no
   `build_phases.py` deploy-map entry needed), and is itself registered as
   a `hooks_manifest` entry invoked through `run_hook.py`.

2. POPULATION (ADR-045 §2): on each run, the runner re-reads
   `hooks_manifest.hooks` from the deployed `commit_guardian.json` beside
   it — never a list held inside the runner — restricted to entries that
   carry a real `entry` string.

3. PER-CHECK EXECUTION AND STATE (ADR-045 §1/§3): for each hook that
   declares a `negative_control` of the `{input, command, expected_result,
   currently}` shape, the runner executes `negative_control["command"]` as
   a real subprocess and derives the state PURELY from what that subprocess
   did, writing it back into THAT SAME hook's `negative_control.currently`
   block in the deployed `commit_guardian.json`.

4. GATE VERDICT (ADR-045 §8): the runner process itself exits non-zero
   whenever any EXAMINED check recorded `"failing"` this run, and exits
   zero when every examined check recorded `"passing"`.

5. OUTPUT (ticket test descriptor 6): for every hook it examines, the
   runner's own stdout/stderr carries one line naming that hook's id, its
   resulting state, and the entry point used.
====================================================================
"""
# @ac-tag: GE-120f-1

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent.parent  # unit_tests/portability/ -> worktree root
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import _deployed_check_harness as dch  # type: ignore[import]  # noqa: E402
from _ge120f1_harness import (  # noqa: E402
    gate_copy,
    hook_entry,
    make_argv_check_script,
    pairing_copy,
    read_manifest,
    replace_hooks,
    run_negative_control_runner,
    shared_harness,
    write_check_script,
)


class TestGE120f1DeployedAndGate(unittest.TestCase):
    """Two tests share `pairing_copy()`; one uses the exclusive `gate_copy()`
    — see _ge120f1_harness.py's ARCHITECTURE for the consolidation
    rationale. `pairing_copy()`/`gate_copy()` build lazily on first use, so
    running this file alone (without the sibling files) still builds both
    copies exactly once."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.harness = shared_harness()
        cls.copy_pairing = pairing_copy()
        cls.copy_gate = gate_copy()

    def test_ge120f1_deployed_runner_and_every_module_it_imports_load_in_a_cold_process(
        self,
    ) -> None:
        """After `python scripts/build.py --target-dir <copy>`, the
        DEPLOYED runner and every module it imports load and execute in a
        cold process with the source tree off the import path (PYTHONPATH
        scrubbed, interpreter isolated, cwd not the source tree). A helper
        placed outside templates/scripts/commit_guardian/ without a
        scripts/build_phases.py deploy-map entry surfaces here as
        ModuleNotFoundError instead of passing."""
        # covers: GE-120f-1
        # angle: deployed
        copy_dir = self.copy_pairing
        deployed_runner = copy_dir / dch._DEPLOYED_CG_REL / "check_negative_controls.py"  # noqa: SLF001
        self.assertTrue(
            deployed_runner.is_file(),
            f"The runner must be deployed verbatim by build_commit_guardian's "
            f"directory copy of templates/scripts/commit_guardian/ at "
            f"{deployed_runner} (ADR-045 §4) -- it is not there yet.",
        )

        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        proc = subprocess.run(  # noqa: S603
            [sys.executable, "-I", str(deployed_runner)],
            cwd=str(copy_dir),
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        self.assertNotIn(
            "ModuleNotFoundError", output,
            f"The deployed runner and every module it imports must load in "
            f"a cold process with the source tree off the import path "
            f"(PYTHONPATH scrubbed, -I isolated, cwd={copy_dir} not the "
            f"source tree). A helper imported from outside "
            f"templates/scripts/commit_guardian/ with no build_phases.py "
            f"deploy-map entry surfaces here as ModuleNotFoundError. "
            f"Output:\n{output}",
        )
        self.assertNotIn(
            "Traceback (most recent call last)", output,
            f"The runner must not raise uncaught in a cold process. Output:\n{output}",
        )

    def test_ge120f1_the_runs_refusal_changes_the_verdict_of_the_gate_that_invokes_it(
        self,
    ) -> None:
        """PRODUCTION ENTRY POINT. Invoke the runner exactly the way the
        chosen gate invokes it (the real run_hook.py-wrapped hooks_manifest
        entry line, per ADR-045 §4) and assert the GATE's own outcome
        moves: non-zero over a fixture population containing a check whose
        rejection was not observed, zero over one where every examined
        check demonstrated. A runner whose refusal does not change any
        gate's verdict is inert (KI-CG-021's shape)."""
        # covers: GE-120f-1
        # angle: reachability
        copy_dir = self.copy_gate

        fail_id = "ge120f1-fixture-gate-fail-check"
        fail_script = "_ge120f1_gate_fail_check.py"
        write_check_script(copy_dir, fail_script, make_argv_check_script(rejects=False))
        replace_hooks(copy_dir, [hook_entry(fail_id, fail_script)])

        fail_outcome = run_negative_control_runner(self.harness, copy_dir)
        self.assertNotEqual(
            fail_outcome.exit_code, 0,
            f"The run_hook.py-wrapped entry line a real pre-commit "
            f"invocation executes must itself exit non-zero when the "
            f"examined fixture population contains a check whose "
            f"rejection was not observed. Output: {fail_outcome.output}",
        )

        pass_id = "ge120f1-fixture-gate-pass-check"
        pass_script = "_ge120f1_gate_pass_check.py"
        write_check_script(copy_dir, pass_script, make_argv_check_script(rejects=True))
        replace_hooks(copy_dir, [hook_entry(pass_id, pass_script)])

        pass_outcome = run_negative_control_runner(self.harness, copy_dir)
        self.assertEqual(
            pass_outcome.exit_code, 0,
            f"Over a fixture population where every examined check "
            f"demonstrated its declared rejection, the SAME entry line "
            f"must exit zero. Output: {pass_outcome.output}",
        )

    def test_ge120f1_every_check_on_the_real_registration_surface_receives_exactly_one_record(
        self,
    ) -> None:
        """Over the repository's REAL registration surface and the
        deployed copy: every check the surface names and that an entry
        line invokes has exactly one record, no check has two, every
        record's state is one of the schema's four values, and the run
        states per check which entry point the input travelled through.
        Count-and-membership over the run's own emitted output -- never a
        hard-coded list of today's checks. Expect most records to read
        never-attempted on day one; that is the true state."""
        # covers: GE-120f-1
        # angle: real_artifact
        copy_dir = self.copy_pairing
        hooks_before = read_manifest(copy_dir)["hooks_manifest"]["hooks"]
        population_ids = {h["id"] for h in hooks_before if h.get("id") and h.get("entry")}
        self.assertTrue(
            population_ids,
            "Precondition: the real deployed manifest must name at least "
            "one hook with a real entry line, or this sweep examines "
            "nothing and the test proves nothing (ADR-045 §7's governing "
            "requirement that a sweep must not silently examine nothing).",
        )

        outcome = run_negative_control_runner(self.harness, copy_dir)

        hooks_after = read_manifest(copy_dir)["hooks_manifest"]["hooks"]
        valid_states = {"passing", "failing", "blocked", "unverified"}
        seen_ids: list[str] = []
        for hook in hooks_after:
            hook_id = hook.get("id")
            if hook_id not in population_ids:
                continue
            seen_ids.append(hook_id)
            record = hook.get("negative_control", {}).get("currently")
            self.assertIsNotNone(
                record,
                f"'{hook_id}' is on the real registration surface with a "
                f"real entry line but carries no currently record after "
                f"the run -- 'unverified' must be recorded rather than "
                f"the block being omitted (ADR-045 §3). Runner output: "
                f"{outcome.output}",
            )
            self.assertIn(
                record["state"], valid_states,
                f"'{hook_id}' recorded state {record.get('state')!r}, not "
                f"one of the schema's four values (passing/failing/"
                f"blocked/unverified).",
            )
            self.assertIn(
                "entry_point", hook,
                f"'{hook_id}' must state the entry point the input "
                f"travelled through.",
            )

        self.assertEqual(
            set(seen_ids), population_ids,
            f"Every check named on the real registration surface with a "
            f"real entry line must receive EXACTLY ONE record. Missing: "
            f"{population_ids - set(seen_ids)}. Unexpected: "
            f"{set(seen_ids) - population_ids}.",
        )
        self.assertEqual(
            len(seen_ids), len(set(seen_ids)),
            f"No check may receive two records. Seen ids: {seen_ids}",
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
#   at 673 counted lines. The former exclusive copy_clean is consolidated
#   onto the shared pairing_copy() (read-only / count-and-membership tests,
#   no interference); copy_gate stays exclusive per pr-reviewer's settled
#   decision (its replace_hooks() calls wipe the whole hooks list).
# ====================================================================
