"""
MODULE: test_ge_120f_1_reachability_and_regressions
AC: GE-120f-1 — "A check's refusal is established by putting its declared
    known-bad input through the entry point the protected surface uses, and
    the record says what was observed rather than what was declared."
GOVERNING ADR: docs/architecture/adrs/ADR-045-observed-refusal-establishes-protection.md
    (binding) — §6b fixes the runner's own registration/reachability guard,
    independent of its own regime; the two H-1 regressions below pin
    pr-reviewer's rework of `_observe()`'s launch-failure discrimination.

SPLIT NOTE: one of three files carved out of the former monolithic
    test_ge_120f_1.py — see _ge120f1_harness.py's module docstring for the
    shared fixture/copy-provisioning rationale and the sibling files
    test_ge_120f_1_alter_and_pairing.py and
    test_ge_120f_1_deployed_and_gate.py. All three tests here share the
    SHARED `pairing_copy()`.

RUN THIS FILE WITH AC_ENFORCE_STRICT=1 (ticket + ADR-045 Operational note):
        AC_ENFORCE_STRICT=1 python -m pytest unit_tests/portability/test_ge_120f_1_reachability_and_regressions.py -v

See test_ge_120f_1_deployed_and_gate.py's module docstring for the
"IMPLEMENTATION CONTRACT ASSUMED BY THIS TEST SUITE" this whole family pins
for python-coder (not repeated in every split file).
"""
# @ac-tag: GE-120f-1

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent.parent  # unit_tests/portability/ -> worktree root
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from _ge120f1_harness import (  # noqa: E402
    hook_entry,
    hook_from_manifest,
    make_argparse_check_script,
    make_argv_check_script,
    pairing_copy,
    run_negative_control_runner,
    shared_harness,
    upsert_hooks,
    write_check_script,
)


class TestGE120f1ReachabilityAndRegressions(unittest.TestCase):
    """All three tests share `pairing_copy()` — each upserts by id against
    disjoint fixture ids, so none interferes with another (see
    _ge120f1_harness.py's ARCHITECTURE)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.harness = shared_harness()
        cls.copy_pairing = pairing_copy()

    def test_ge120f1_runner_is_registered_and_reachable_independently_of_its_own_regime(
        self,
    ) -> None:
        """Ticket Implementation Notes DECISION block / ADR-045 §6b — the
        load-bearing half of the two-guard rule: the runner's own
        existence, registration, and reachability must be pinned by
        assertions that do NOT ask the liveness run itself to prove it.
        Guarding the runner only by its own regime is circular: if the
        runner silently stops running, the thing that would report that is
        the thing that stopped."""
        # covers: GE-120f-1
        # angle: reachability
        source_manifest_path = (
            _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "commit_guardian.json"
        )
        source_hooks = json.loads(source_manifest_path.read_text(encoding="utf-8"))[
            "hooks_manifest"
        ]["hooks"]
        runner_hooks = [
            h for h in source_hooks if "check_negative_controls.py" in h.get("entry", "")
        ]
        self.assertTrue(
            runner_hooks,
            "check_negative_controls.py must be registered as its own "
            "real hooks_manifest entry (ADR-045 §4/§6a) -- it is not "
            "registered yet.",
        )
        self.assertIn(
            "negative_control", runner_hooks[0],
            f"The runner's OWN hooks_manifest entry "
            f"{runner_hooks[0].get('id')!r} must carry its own "
            f"negative_control (ADR-045 §6a): a liveness checker that "
            f"proves every other check can refuse, while carrying no "
            f"declaration of its own, is the precise asymmetry KI-CG-021 "
            f"already cost this repository once.",
        )

        source_script = (
            _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_negative_controls.py"
        )
        self.assertTrue(
            source_script.is_file(),
            f"The runner must exist at its registered source path "
            f"{source_script} (ADR-045 §4).",
        )

        # Reachability, independent of the liveness regime: invoke the
        # runner through run_hook.py exactly as its own entry line does,
        # and assert the PROCESS reaches it -- never by asking the
        # liveness run's own sweep output whether it examined anything.
        outcome = run_negative_control_runner(self.harness, self.copy_pairing)
        self.assertNotIn(
            "could_not_start", outcome.output,
            f"run_hook.py must actually reach check_negative_controls.py "
            f"-- a 'could_not_start' not-run report means the entry line "
            f"never launched the runner at all. Output: {outcome.output}",
        )
        self.assertNotEqual(
            outcome.status, "could_not_check",
            f"Invoking the runner via run_hook.py must produce a genuine "
            f"observable result (clean or violation), not a "
            f"could-not-check outcome such as ModuleNotFoundError. "
            f"Output: {outcome.output}",
        )

    def test_ge120f1_a_same_basename_sibling_disabled_blocks_the_control_rather_than_failing_it(
        self,
    ) -> None:
        """PR-REVIEW REGRESSION (H-1a). Two hooks_manifest entries can share
        a script basename -- run_hook.py's own _is_target_disabled() matches
        by basename, not hook id (mirrors the real check-ac-tree-limits /
        check-ticket-ac-limits collision already present in
        commit_guardian.json). Disabling one must not silently misreport
        the OTHER, enabled entry's own negative control as 'failing': that
        entry's own process never launches at all -- run_hook.py itself
        reports 'RESULT: not_run ... reason=disabled' and exits 0 before
        the check's own process starts -- so the record must read
        'blocked' (the attempt could not be run to a verdict), never
        'failing' (a check that ran and did not reject its input). A
        pre-fix runner records this 'failing', which would block every
        future commit on an operator's routine enable/disable decision on
        an unrelated sibling."""
        # covers: GE-120f-1
        # angle: boundary
        copy_dir = self.copy_pairing  # disjoint fixture ids; no interference
        shared_script = "_ge120f1_h1_shared_basename_check.py"
        disabled_id = "ge120f1-h1-basename-sibling-disabled"
        enabled_id = "ge120f1-h1-basename-sibling-enabled"

        write_check_script(copy_dir, shared_script, make_argv_check_script(rejects=True))
        disabled_hook = hook_entry(disabled_id, shared_script, enabled=False)
        enabled_hook = hook_entry(enabled_id, shared_script, enabled=True)
        upsert_hooks(copy_dir, [disabled_hook, enabled_hook])

        outcome = run_negative_control_runner(self.harness, copy_dir)

        enabled_state = hook_from_manifest(copy_dir, enabled_id)[
            "negative_control"
        ]["currently"]["state"]
        self.assertEqual(
            enabled_state, "blocked",
            f"'{enabled_id}' is itself enabled and its declared command "
            f"genuinely rejects its input, but it shares a script basename "
            f"with '{disabled_id}', which IS disabled -- run_hook.py's own "
            f"_is_target_disabled() matches by basename, so invoking "
            f"'{enabled_id}''s negative control never launches its own "
            f"process at all. The record must read 'blocked' (the attempt "
            f"could not be run to a verdict), never 'failing' (which would "
            f"misreport a check that never ran as having run and failed to "
            f"reject its input, blocking every future commit on an "
            f"unrelated sibling's disablement). Runner output: "
            f"{outcome.output}",
        )

    def test_ge120f1_a_real_argparse_usage_error_blocks_the_control_rather_than_passing_it(
        self,
    ) -> None:
        """PR-REVIEW REGRESSION (H-1b). A real argparse-based check that has
        not declared a positional argument treats the appended known-bad
        input as an unrecognised CLI token: argparse's own
        ArgumentParser.error() rejects it with a 'usage: ...' line and
        Python's hard-coded parser-error exit code (2), BEFORE the check's
        own examination logic ever runs. A non-marker-matching non-zero
        exit must not be read as a genuine 'passing' rejection -- that
        would certify logic that was never actually exercised against the
        declared input. The record must read 'blocked'."""
        # covers: GE-120f-1
        # angle: boundary
        copy_dir = self.copy_pairing  # disjoint fixture ids; no interference
        script_name = "_ge120f1_h1_argparse_usage_error_check.py"
        hook_id = "ge120f1-h1-argparse-usage-error"

        write_check_script(copy_dir, script_name, make_argparse_check_script())
        hook = hook_entry(hook_id, script_name, enabled=True)
        upsert_hooks(copy_dir, [hook])

        outcome = run_negative_control_runner(self.harness, copy_dir)

        state = hook_from_manifest(copy_dir, hook_id)["negative_control"]["currently"]["state"]
        self.assertEqual(
            state, "blocked",
            f"'{hook_id}' is a real argparse-based check with no "
            f"positional argument declared. Fed its declared bad input, "
            f"argparse's own parser rejects it as an unrecognised argument "
            f"(a 'usage: ...' line, exit code 2) before the check's own "
            f"logic ever runs. The record must read 'blocked' -- a "
            f"matching non-zero exit code alone is not evidence the check "
            f"evaluated its declared input, only that its own CLI layer "
            f"rejected the token first. Recording this as 'passing' would "
            f"certify logic that was never actually exercised against the "
            f"declared input. Runner output: {outcome.output}",
        )


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-21 [test-writer/GE-120f-1]: The reachability test was authored
#   as part of the original 7-test RED stub set in the (now split)
#   monolithic test_ge_120f_1.py, before python-coder implemented
#   check_negative_controls.py.
# - 2026-09-21 [python-coder/GE-120f-1, pr-reviewer rework]: Added the two
#   H-1 regression tests
#   (test_ge120f1_a_same_basename_sibling_disabled_blocks_the_control_rather_than_failing_it
#   and
#   test_ge120f1_a_real_argparse_usage_error_blocks_the_control_rather_than_passing_it)
#   plus the make_argparse_check_script() fixture helper (now in
#   _ge120f1_harness.py). Confirmed RED against the pre-fix runner via an
#   independent ad hoc real-artifact script BEFORE authoring these tests
#   (not committed; see the python-coder sign-off comment on the ticket for
#   the verbatim red output) -- both scenarios reproduced exactly: the
#   same-basename sibling scenario recorded 'failing' instead of 'blocked',
#   and the argparse usage-error scenario recorded 'passing' instead of
#   'blocked'. Both are GREEN against the fixed runner
#   (_parse_not_run_reason() + _looks_like_argparse_usage_error()).
# - 2026-09-21 [python-coder/GE-120f-1, file-size split]: Carved into this
#   file (unchanged assertions and names) from the monolithic
#   test_ge_120f_1.py, which exceeded the 400-line check-file-size budget
#   at 673 counted lines. The former exclusive copy_clean/copy_pairing
#   fixtures for these three tests are consolidated onto the shared
#   pairing_copy() per pr-reviewer's settled decision.
# ====================================================================
