"""
MODULE: test_ge_120f_1
AC: GE-120f-1 -- "A check's refusal is established by putting its declared
    known-bad input through the entry point the protected surface uses, and
    the record says what was observed rather than what was declared."
GOAL: Failing (RED) test stubs for the negative-control liveness runner this
    AC requires. Written BEFORE python-coder exists to satisfy them, per this
    ticket's dispatch order (test-writer runs before python-coder). Every
    test in this file is expected to fail today -- there is no runner yet --
    and the failure mode MUST be "the behaviour / entry point is missing"
    (ModuleNotFoundError / FileNotFoundError / a non-zero exit reporting "No
    such file"), never a syntax or import error in THIS file.

    Shared fixture helpers (fixture check scripts, fixture manifest
    builders, the runner's entry-shape constants, and its output-parsing
    regex) live in the sibling module `_ge_120f_1_fixtures.py`, imported
    below as `fx`, per the file-size gate split -- see that module's own
    DECISION HISTORY. No test function, test name, `# covers:` / `# angle:`
    tag, or assertion moved or changed as part of that split.

====================================================================
THE CONTRACT PYTHON-CODER MUST IMPLEMENT (test-writer's authoritative design
-- see this ticket's own note: "If the tests must import a module whose
final name python-coder has not chosen yet, design them so the red failure
is a clear 'behaviour/entry point missing' failure, and state in sign-off
exactly which name/entry point the coder must provide.")
====================================================================

FILE / LOCATION (fixed by this test file, not a placeholder here):
    templates/scripts/commit_guardian/check_negative_control_liveness.py
    -- inside templates/scripts/commit_guardian/ per the ticket's own HOST
    AND DEPLOYMENT constraint, so build_commit_guardian() copies it verbatim
    and no scripts/build_phases.py deploy-map entry is required, PROVIDED
    every module it imports also lives inside that same directory (any
    import from outside it needs its own deploy-map entry -- see
    test_ge120f1_deployed_runner_and_every_module_it_imports_load_in_a_cold_process
    below, which exists to catch exactly that gap). The check_*.py name
    pulls this module into hook_parity.hook_script_patterns's census per the
    ticket's own naming-consequence note -- python-coder MUST give it a real
    hooks_manifest entry (the reachability test below exercises the
    run_hook.py-wrapped form of that entry) or a grounded declared-non-gate
    record; it may NOT be silently invisible to that census.

CLI CONTRACT:
    python check_negative_control_liveness.py --manifest PATH
        [--check-id ID [--check-id ID ...]]
    python check_negative_control_liveness.py --selftest

    --manifest PATH   Required unless --selftest. PATH is a commit_guardian.json
                       -shaped JSON file (top-level "hooks_manifest": {"hooks": [...]})
                       -- either the real deployed manifest or a standalone
                       fixture file; the runner must not care which.
    --check-id ID     Repeatable. When given at least once, ONLY hooks whose
                       id is listed are EXAMINED (put through their declared
                       negative_control) this run. Every other hook entry
                       that carries a negative_control is left UNEXAMINED --
                       untouched if it already has no `currently` block
                       (test_ge120f1_never_attempted_and_observed_are_produced_in_one_run_over_the_same_surface
                       covers exactly this case), and this is a legitimate,
                       intentional exclusion mechanism (a run examining a
                       subset), not an error.
                       Omitted entirely = examine every hook entry in the
                       manifest that carries a `negative_control` key.
    --selftest        Print exactly "NEGATIVE_CONTROL_LIVENESS_SELFTEST_OK"
                       to stdout and exit 0 WITHOUT reading --manifest or
                       touching any file. Exists solely so a cold-process
                       import/load check (test 4 below) can prove the
                       deployed script and every module it imports load
                       successfully without needing a real manifest or
                       running any real check.

    For a hook entry with `negative_control: {input, command, expected_result}`
    (the falsifiable shape -- see config/verification_flow.schema.json
    $defs/negative_control, copied verbatim per this AC's own
    config_schema_fragment) that IS examined this run:
      1. Actually run `command` as a real subprocess (never read/parse it as
         text, never infer the answer from the declaration -- see this AC's
         own constraint "THE VALUE IS PRODUCED BY EXECUTION AND MAY COME
         FROM NOWHERE ELSE").
      2. `expected_result` value "non-zero exit" means: the check REJECTS
         (the declared rejection was observed) iff the subprocess's exit
         code is non-zero.
      3. Write `negative_control.currently` back into the SAME hooks entry,
         in the SAME manifest file, at the SAME path (never a copy, never a
         different file -- this is what
         test_ge120f1_record_moves_under_alter_and_revert_while_the_declaration_stays_byte_identical
         below is checking), as:
           {"state": "passing" | "failing" | "blocked",
            "observed": "YYYY-MM-DD",
            "evidence": [{"command": <the real command run>,
                          "output": <its real combined stdout+stderr>,
                          "exit_code": <int>}]}
         state="passing"  -- command ran, exit code non-zero -- rejection OBSERVED.
         state="failing"  -- command ran, exit code zero -- rejection NOT observed.
         state="blocked"  -- command could not be run to a verdict at all
                             (subprocess could not start, timed out, etc).
         Reuse these four schema state values VERBATIM; never synonyms.
      4. `negative_control.currently` must NEVER be derived from `input` /
         `command` / `expected_result` alone -- those three keys (the
         DECLARATION) must be byte-for-byte unchanged by any run.
    For a hook entry with a `negative_control` key that is NOT examined this
    run (excluded via --check-id) and that carries no pre-existing
    `currently` block: write `currently = {"state": "unverified", ...}` (the
    honest "attempt has never been made" placeholder) -- never omit the
    block, and never a state other than "unverified" for a check that was
    never put through anything.

    For EVERY hook entry that carries a `negative_control` key (examined or
    not), whether this run touches it or not, print exactly one line to
    stdout, of the exact form:
        NEGATIVE_CONTROL_RESULT check_id=<id> state=<state> entry_point=<entry_point> command=<command>
    where <entry_point> is the entry point the invocation actually performed,
    never the hook's declared `entry_point`/`entry` field, and <command> is the REAL command that
    was (or, for an unexamined/unverified entry, WOULD BE) run -- i.e.
    `negative_control.command` resolved to the literal string actually
    passed to subprocess. No hook may produce two such lines; a hook with no
    `negative_control` key produces none.

    Exit code: 0 iff every EXAMINED hook this run ended in state "passing".
    Non-zero iff at least one EXAMINED hook ended in "failing" or "blocked".
    Hooks left at "unverified" because they were not examined this run do
    NOT affect exit code.

WINDOWS NOTE FOR PYTHON-CODER: this repository's CI and this worktree run on
    win32. `negative_control.command` strings in this file's fixtures are
    built from `sys.executable` plus a bare filesystem Path (backslash
    separators) -- if the runner tokenizes `command` with `shlex.split()`
    without `posix=False` on Windows, backslashes will be mis-escaped.
    Tokenize with `shlex.split(command, posix=(os.name != "nt"))` or avoid
    shlex entirely (e.g. a simple `.split()` is sufficient for every fixture
    command in this file, which never contains quoted arguments).

DECISION HISTORY
====================================================================
- 2026-09-25 [test-writer/EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs/01,
  GE-120f-1]: Initial red stubs. All 6 descriptors from this AC's own
  test_spec written against the CLI contract documented above (test-writer's
  own design decision, since the runner does not exist yet and its name was
  left as an explicit placeholder by architect-review). Extends
  _deployed_check_harness.py (GE-120c-1) rather than duplicating it, per
  this ticket's own constraint. Uses a standalone FIXTURE manifest file
  (never the real 72-entry templates/scripts/commit_guardian/commit_guardian.json)
  for every descriptor except the last, which the AC's own test_spec
  explicitly directs at "the repository's REAL registration surface".
- 2026-09-25 [test-writer, same ticket]: check_file_size.py refused this
  file at 515 counted lines (limit 400: TestGE120f1NegativeControlLiveness
  alone counted 368). Moved every module-level fixture helper and constant
  into the new `_ge_120f_1_fixtures.py` sibling module (imported as `fx`
  below) -- no test function, name, tag, or assertion changed. See that
  module's own DECISION HISTORY. python-coder subsequently implemented the
  runner; all 6 tests here now PASS (coordinator-verified: this file plus
  test_ge_120c_1.py -> 13 passed, 2 subtests). A second trim (removing a
  redundant un-stripped `#`-comment DECISION HISTORY block that duplicated
  this docstring's own content) was needed to clear the 400-line limit --
  see the one-line pointer comment at the bottom of this file.
====================================================================
"""
# @ac-tag: GE-120f-1

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


class TestGE120f1NegativeControlLiveness(unittest.TestCase):
    """Shared, expensive fixture: build ONE real deployed-only working copy
    via the real scripts/build.py ONCE for the whole class, per this AC's
    own RUNTIME BUDGET requirement ("Build the copy ONCE per sweep, never
    once per check")."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        tmp_root = Path(cls._tmp.name)
        cls.copy_dir = tmp_root / "copy"
        cls.harness = dch.DeployedCheckHarness(repo_root=_REPO_ROOT)
        cls.harness.create_second_copy(cls.copy_dir)
        cls.deployed_cg_dir = cls.copy_dir / ".leafcutter" / "scripts" / "commit_guardian"
        cls.fixtures_dir = cls.copy_dir / "_ge120f1_fixtures"

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    # covers: GE-120f-1
    def test_ge120f1_record_moves_under_alter_and_revert_while_the_declaration_stays_byte_identical(
        self,
    ) -> None:
        """AC-1/AC-2/AC-4/AC-5/AC-6/AC-7. THE DECISIVE ANTI-DECLARATION DESCRIPTOR. Run 1: fixture check
        genuinely rejects -> observed. Run 2: alter the DEPLOYED copy the
        run loads so it no longer rejects, declaration untouched -> not
        observed. Run 3: revert, nothing else changes -> observed again.
        The declaration bytes must be identical across all three runs, and
        the altered file must be the same path the run reported loading."""
        # covers: GE-120f-1
        # angle: real_artifact
        check_id = "ge120f1-fixture-alter-revert"
        script_path = self.deployed_cg_dir / "_ge120f1_alter_revert_check.py"
        manifest_path = self.fixtures_dir / "alter_revert_manifest.json"

        reject_content = fx.reject_script("ALTER_REVERT")
        allow_content = fx.always_allow_script("ALTER_REVERT")

        fx.write_script(script_path, reject_content)
        fx.write_fixture_manifest(manifest_path, [fx.fixture_hook(check_id, script_path)])

        def _run() -> tuple[dch.CopyCheckOutcome, dict]:
            outcome = self.harness.invoke_check(
                self.copy_dir,
                fx.RUNNER_ENTRY_DIRECT,
                ["--manifest", str(manifest_path), "--check-id", check_id],
            )
            manifest_after = fx.read_manifest(manifest_path)
            return outcome, manifest_after

        # ---- Run 1: genuinely rejects -> observed ----
        outcome_1, manifest_1 = _run()
        self.assertEqual(outcome_1.exit_code, 0, outcome_1.output)
        hook_1 = fx.hook_by_id(manifest_1, check_id)
        self.assertEqual(
            hook_1["negative_control"]["currently"]["state"], "passing",
            "Run 1: a check whose declared input genuinely produces its "
            f"declared rejection must record the rejection observed. Output:\n{outcome_1.output}",
        )
        declaration_1 = fx.declaration_only(hook_1)

        # ---- Alter the DEPLOYED copy the run loads (same script_path) ----
        fx.write_script(script_path, allow_content)
        self.assertEqual(
            script_path.read_text(encoding="utf-8"), allow_content,
            "Precondition: the alteration must land in the exact file the "
            "run's own command references.",
        )

        # ---- Run 2: same input no longer rejected -> not observed ----
        outcome_2, manifest_2 = _run()
        hook_2 = fx.hook_by_id(manifest_2, check_id)
        self.assertEqual(
            hook_2["negative_control"]["currently"]["state"], "failing",
            "Run 2: after altering the DEPLOYED copy so the declared input "
            "no longer produces the declared rejection (declaration left "
            f"byte-identical), the record must read not-observed. Output:\n{outcome_2.output}",
        )
        declaration_2 = fx.declaration_only(hook_2)
        self.assertEqual(
            declaration_1, declaration_2,
            "The declaration (input/command/expected_result) must be "
            "byte-identical across runs -- only `currently` may move.",
        )

        # ---- Revert; nothing else changes ----
        fx.write_script(script_path, reject_content)

        # ---- Run 3: observed again ----
        outcome_3, manifest_3 = _run()
        hook_3 = fx.hook_by_id(manifest_3, check_id)
        self.assertEqual(
            hook_3["negative_control"]["currently"]["state"], "passing",
            "Run 3: after reverting the alteration with nothing else "
            f"changed, the record must read observed again. Output:\n{outcome_3.output}",
        )
        declaration_3 = fx.declaration_only(hook_3)
        self.assertEqual(declaration_1, declaration_3, "Declaration must still be byte-identical.")

        # ---- The altered file is the same path the run reported loading ----
        results_2 = fx.parse_results(outcome_2.output)
        self.assertIn(check_id, results_2, f"No NEGATIVE_CONTROL_RESULT line for {check_id} in:\n{outcome_2.output}")
        self.assertIn(
            str(script_path), results_2[check_id]["command"],
            "The run must report the SAME path that was altered -- an "
            "alteration applied to a copy the run does not load fails "
            f"GREEN, which this assertion exists to catch. Reported command: {results_2[check_id]['command']!r}",
        )

    # covers: GE-120f-1
    def test_ge120f1_never_attempted_and_observed_are_produced_in_one_run_over_the_same_surface(
        self,
    ) -> None:
        """AC-1/AC-2/AC-3. THE PAIRING. One run over a fixture registration surface holding
        (a) a check with a complete declaration the run is PREVENTED from
        invoking (excluded via --check-id), and (b) a check whose declared
        input genuinely produces its declared rejection. In that SAME run,
        (a) must record never-attempted and (b) must record observed.

        NAMED MUTATION (documented for whoever implements/reviews): an
        implementation that writes the record FROM THE DECLARATION -- i.e.
        treats a well-formed declaration as itself sufficient evidence of
        observation -- would report (a) as "passing" even though it was
        never examined this run. This assertion is written specifically so
        that injection flips it RED: it asserts (a)'s state is "unverified"
        BECAUSE (a) was excluded from --check-id, not because of anything in
        its declaration."""
        # covers: GE-120f-1
        # angle: criterion
        prevented_id = "ge120f1-fixture-pairing-never-attempted"
        observed_id = "ge120f1-fixture-pairing-observed"
        prevented_script = self.deployed_cg_dir / "_ge120f1_pairing_prevented_check.py"
        observed_script = self.deployed_cg_dir / "_ge120f1_pairing_observed_check.py"
        manifest_path = self.fixtures_dir / "pairing_manifest.json"

        # (a) would genuinely reject if invoked -- but this run never invokes it.
        fx.write_script(prevented_script, fx.reject_script("PAIRING_PREVENTED"))
        # (b) genuinely rejects and WILL be invoked.
        fx.write_script(observed_script, fx.reject_script("PAIRING_OBSERVED"))

        fx.write_fixture_manifest(
            manifest_path,
            [
                fx.fixture_hook(prevented_id, prevented_script),
                fx.fixture_hook(observed_id, observed_script),
            ],
        )

        outcome = self.harness.invoke_check(
            self.copy_dir,
            fx.RUNNER_ENTRY_DIRECT,
            # Only (b) is put through the entry point this run; (a) is
            # deliberately excluded -- "prevented from invoking".
            ["--manifest", str(manifest_path), "--check-id", observed_id],
        )
        self.assertEqual(outcome.exit_code, 0, outcome.output)

        manifest_after = fx.read_manifest(manifest_path)
        hook_prevented = fx.hook_by_id(manifest_after, prevented_id)
        hook_observed = fx.hook_by_id(manifest_after, observed_id)

        self.assertEqual(
            hook_prevented["negative_control"]["currently"]["state"], "unverified",
            "(a) has a complete, well-formed declaration but was never put "
            "through the entry point this run -- its record MUST say the "
            "attempt has never been made, regardless of how well-formed its "
            f"declaration is. Output:\n{outcome.output}",
        )
        self.assertEqual(
            hook_observed["negative_control"]["currently"]["state"], "passing",
            f"(b) genuinely rejects its declared input -- must record observed. Output:\n{outcome.output}",
        )

        results = fx.parse_results(outcome.output)
        self.assertEqual(results.get(prevented_id, {}).get("state"), "unverified")
        self.assertEqual(results.get(observed_id, {}).get("state"), "passing")

    # covers: GE-120f-1
    def test_ge120f1_a_check_added_to_the_registration_surface_gets_a_record_of_its_own(
        self,
    ) -> None:
        """AC-2/AC-3 (population read from the surface at run time). Add one further declared check to a FIXTURE registration surface,
        change nothing else, and re-run (scoped via --check-id to ONLY the
        new check): the new check has its own record, written from its own
        observation, and the pre-existing check's record is UNTOUCHED --
        byte-identical to before the second run. Establishes the declaration
        population is read from the surface at run time (the new check's id
        cannot come from a list hard-coded inside the runner, since it did
        not exist during the first run)."""
        # covers: GE-120f-1
        # angle: seam
        existing_id = "ge120f1-fixture-seam-existing"
        new_id = "ge120f1-fixture-seam-added"
        existing_script = self.deployed_cg_dir / "_ge120f1_seam_existing_check.py"
        new_script = self.deployed_cg_dir / "_ge120f1_seam_added_check.py"
        manifest_path = self.fixtures_dir / "seam_manifest.json"

        fx.write_script(existing_script, fx.reject_script("SEAM_EXISTING"))
        fx.write_fixture_manifest(manifest_path, [fx.fixture_hook(existing_id, existing_script)])

        outcome_1 = self.harness.invoke_check(
            self.copy_dir,
            fx.RUNNER_ENTRY_DIRECT,
            ["--manifest", str(manifest_path), "--check-id", existing_id],
        )
        self.assertEqual(outcome_1.exit_code, 0, outcome_1.output)
        manifest_after_1 = fx.read_manifest(manifest_path)
        existing_record_1 = json.dumps(
            fx.hook_by_id(manifest_after_1, existing_id)["negative_control"], sort_keys=True,
        )

        # Add the new check to the SAME surface, changing nothing else.
        fx.write_script(new_script, fx.reject_script("SEAM_ADDED"))
        manifest_current = fx.read_manifest(manifest_path)
        manifest_current["hooks_manifest"]["hooks"].append(fx.fixture_hook(new_id, new_script))
        manifest_path.write_text(json.dumps(manifest_current, indent=2) + "\n", encoding="utf-8")

        outcome_2 = self.harness.invoke_check(
            self.copy_dir,
            fx.RUNNER_ENTRY_DIRECT,
            # Scoped to ONLY the new check -- the existing check's record
            # must stay untouched by this run.
            ["--manifest", str(manifest_path), "--check-id", new_id],
        )
        self.assertEqual(outcome_2.exit_code, 0, outcome_2.output)
        manifest_after_2 = fx.read_manifest(manifest_path)

        new_hook = fx.hook_by_id(manifest_after_2, new_id)
        self.assertEqual(
            new_hook["negative_control"]["currently"]["state"], "passing",
            "A check added to the registration surface after the first run "
            f"must get its own record from its own observation. Output:\n{outcome_2.output}",
        )

        existing_record_2 = json.dumps(
            fx.hook_by_id(manifest_after_2, existing_id)["negative_control"], sort_keys=True,
        )
        self.assertEqual(
            existing_record_1, existing_record_2,
            "Adding a new check to the surface and re-running (scoped to "
            "the new check) must not change the pre-existing check's "
            "record at all.",
        )

        results_2 = fx.parse_results(outcome_2.output)
        self.assertIn(
            new_id, results_2,
            "The new check's id must appear in this run's output -- it can "
            "only have come from reading the manifest at run time, since it "
            f"did not exist during the first run. Output:\n{outcome_2.output}",
        )

    # covers: GE-120f-1
    def test_ge120f1_deployed_runner_and_every_module_it_imports_load_in_a_cold_process(
        self,
    ) -> None:
        """AC-2 (deployed entry point, not a source-tree import). After `python scripts/build.py --target-dir <copy>`, the DEPLOYED
        runner and every module it imports load and execute in a cold
        process with the source tree off the import path (PYTHONPATH
        scrubbed, interpreter isolated -I, cwd not the source tree). A
        helper placed outside templates/scripts/commit_guardian/ without a
        scripts/build_phases.py deploy-map entry surfaces here as
        ModuleNotFoundError instead of passing."""
        # covers: GE-120f-1
        # angle: deployed
        self.assertTrue(
            self.harness.deployed_layout_present(self.copy_dir),
            "Precondition: scripts/build.py must have produced a real "
            ".leafcutter/scripts/commit_guardian/ layout in the deployed copy.",
        )

        os.environ["AC_ENFORCE_STRICT"] = os.environ.get("AC_ENFORCE_STRICT", "1")
        outcome = self.harness.invoke_check(self.copy_dir, fx.RUNNER_ENTRY_DIRECT, ["--selftest"])

        self.assertEqual(
            outcome.exit_code, 0,
            "The DEPLOYED runner (and every module it imports) must load "
            "and execute in a cold process -- source tree off the import "
            "path, PYTHONPATH scrubbed, isolated interpreter, cwd is the "
            f"deployed copy, not this repository's source tree. Output:\n{outcome.output}",
        )
        self.assertIn(
            "NEGATIVE_CONTROL_LIVENESS_SELFTEST_OK", outcome.output,
            f"Expected the runner's own cold-load marker. Output:\n{outcome.output}",
        )
        self.assertNotIn(
            "ModuleNotFoundError", outcome.output,
            "A helper imported from outside templates/scripts/commit_guardian/ "
            "with no scripts/build_phases.py deploy-map entry raises "
            f"ModuleNotFoundError in the deployed copy. Output:\n{outcome.output}",
        )

    # covers: GE-120f-1
    def test_ge120f1_the_runs_refusal_changes_the_verdict_of_the_gate_that_invokes_it(
        self,
    ) -> None:
        """AC-2 (the entry point the protected surface uses; reachability floor). PRODUCTION ENTRY POINT. Invoke the runner exactly the way the
        chosen gate invokes it (a hooks_manifest entry line invoked via
        `python .leafcutter/scripts/commit_guardian/run_hook.py`, per this
        AC's own test_spec `surface_invoked`) and assert the GATE's own
        outcome moves: non-zero over a fixture population containing a
        check whose rejection was not observed, zero over one where every
        examined check demonstrated. A runner whose refusal does not change
        any gate's verdict is inert -- KI-CG-021's shape."""
        # covers: GE-120f-1
        # angle: reachability
        broken_id = "ge120f1-fixture-gate-broken"
        clean_id = "ge120f1-fixture-gate-clean"
        broken_script = self.deployed_cg_dir / "_ge120f1_gate_broken_check.py"
        clean_script = self.deployed_cg_dir / "_ge120f1_gate_clean_check.py"

        # ---- Population 1: contains a check whose rejection is NOT observed. ----
        fx.write_script(broken_script, fx.always_allow_script("GATE_BROKEN"))
        broken_manifest_path = self.fixtures_dir / "gate_broken_manifest.json"
        fx.write_fixture_manifest(broken_manifest_path, [fx.fixture_hook(broken_id, broken_script)])

        broken_run_outcome = self.harness.invoke_check(
            self.copy_dir,
            fx.RUNNER_ENTRY_WRAPPED,
            ["--manifest", str(broken_manifest_path), "--check-id", broken_id],
        )
        self.assertNotEqual(
            broken_run_outcome.exit_code, 0,
            "Over a fixture population containing a check whose rejection "
            "was not observed, the GATE's own outcome (run_hook.py-wrapped "
            f"invocation) must be non-zero. Output:\n{broken_run_outcome.output}",
        )

        # ---- Population 2: every examined check demonstrated its rejection. ----
        fx.write_script(clean_script, fx.reject_script("GATE_CLEAN"))
        clean_manifest_path = self.fixtures_dir / "gate_clean_manifest.json"
        fx.write_fixture_manifest(clean_manifest_path, [fx.fixture_hook(clean_id, clean_script)])

        clean_run_outcome = self.harness.invoke_check(
            self.copy_dir,
            fx.RUNNER_ENTRY_WRAPPED,
            ["--manifest", str(clean_manifest_path), "--check-id", clean_id],
        )
        self.assertEqual(
            clean_run_outcome.exit_code, 0,
            "Over a population where every examined check demonstrated its "
            f"rejection, the GATE's own outcome must be zero. Output:\n{clean_run_outcome.output}",
        )

    # covers: GE-120f-1
    def test_ge120f1_every_check_on_the_real_registration_surface_receives_exactly_one_record(
        self,
    ) -> None:
        """AC-1/AC-2 (over the real surface). Over the repository's REAL registration surface and the deployed
        copy: every check the surface names that carries a negative_control
        has exactly one record, every record's state is one of the schema's
        four values, and the run states per check which entry point the
        input travelled through. Asserted by count-and-membership over the
        run's own emitted output -- never a hard-coded list of today's
        checks. Most records are expected to read `unverified` (never
        attempted) on day one; that is the true state and must not be
        pre-suppressed."""
        # covers: GE-120f-1
        # angle: real_artifact
        real_manifest_path = self.harness.deployed_manifest_path(self.copy_dir)
        self.assertTrue(
            real_manifest_path.is_file(),
            f"Precondition: the real deployed manifest must exist at {real_manifest_path}.",
        )

        outcome = self.harness.invoke_check(
            self.copy_dir, fx.RUNNER_ENTRY_DIRECT, ["--manifest", str(real_manifest_path)],
        )
        self.assertEqual(
            outcome.exit_code, 0,
            "A sweep over the real registration surface -- where most "
            "checks have no negative_control declared yet (day-one blast "
            "radius) and are therefore simply not examined -- must not "
            f"itself crash with a non-zero exit. Output:\n{outcome.output}",
        )

        result_lines = [
            line for line in outcome.output.splitlines() if line.strip().startswith("NEGATIVE_CONTROL_RESULT")
        ]
        parsed_ids = [
            m.group("check_id") for m in (fx.RESULT_LINE_RE.match(ln.strip()) for ln in result_lines) if m
        ]

        # No check has two records.
        self.assertEqual(
            len(parsed_ids), len(set(parsed_ids)),
            f"Every reported check must appear exactly once. Duplicates found in:\n{outcome.output}",
        )

        results = fx.parse_results(outcome.output)
        for check_id, record in results.items():
            with self.subTest(check_id=check_id):
                self.assertIn(
                    record["state"], fx.VALID_STATES,
                    f"{check_id}'s state {record['state']!r} must be one of {fx.VALID_STATES}.",
                )
                self.assertTrue(
                    record["entry_point"],
                    f"{check_id}'s record must state which entry point the input travelled through.",
                )

        manifest_after = fx.read_manifest(real_manifest_path)
        real_hooks_with_negative_control = [
            hook for hook in manifest_after["hooks_manifest"]["hooks"] if "negative_control" in hook
        ]
        # Membership: every hook carrying a negative_control key must be
        # represented in the run's own output.
        for hook in real_hooks_with_negative_control:
            nc = hook["negative_control"]
            if nc.get("not_applicable"):
                continue
            self.assertIn(
                hook["id"], results,
                f"Hook {hook['id']!r} declares a negative_control but produced "
                f"no NEGATIVE_CONTROL_RESULT line. Output:\n{outcome.output}",
            )


if __name__ == "__main__":
    unittest.main()

# DECISION HISTORY: see the module docstring at the top of this file --
# duplicating it down here in un-stripped `#` comments is what pushed this
# file over check_file_size.py's limit the first time; keep it in the one
# (stripped, free) docstring copy only.
