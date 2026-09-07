"""
MODULE: unit_tests/portability/test_bp_900h6ii.py
GOAL: RED test-first stubs for AC BP-900h-6-ii — "The executed-guard record
    accounts for the guard population the adopter would really face, and a
    narrowed run cannot report an unqualified pass".
AC: docs/acceptance-criteria/build_pipeline/BP-900-deployment-completeness/BP-900h-6-ii.yaml

CONTRACT UNDER TEST (fixed here because no accounting of the deployed-vs-
executed guard population exists yet in scripts/ci/_use_install_step.py —
confirmed by Read: run_use_install_step() narrows the registry to the
self-healing hook plus any hook invoking check_identifier_uniqueness BEFORE
the executed-guard record is captured, and format_executed_guards_line()
prints only the guards that ran — there is no "deployed count", no "withheld"
list, and no distinction between a qualified and an unqualified pass):

    1. A narrowed run must state the deployed guard count (taken from the
       registry BEFORE the step's own narrowing), name every withheld guard
       with a reason, and the union of executed + withheld names must equal
       the deployed names with no overlap and no gap.
    2. A narrowed run and a full run (nothing withheld) must not produce the
       same verdict line — the full run gets the unqualified pass, the
       narrowed run a textually distinct qualified verdict.
    3. A guard withheld with no recorded reason, or a deployed guard that
       appears in neither the executed nor the withheld list, must fail the
       job and name the unaccounted guard.
    4. The accounting must appear in what the exact command
       .github/workflows/ci.yml parses for the consumer-simulation step
       actually emits — not just in the module. RED BY DESIGN at
       AC-authoring time since that command carries no --use-install flag.

Every entry is invoked through the real subprocess entry point
(``scripts/ci/check_consumer_install.py``) — never by calling a
report-formatting helper directly — per this AC's REACHABILITY clause.

RED AT AUTHORING TIME: none of the deployed-count / withheld / qualified-
verdict reporting described above exists. All four entries are expected to
fail.
"""
from __future__ import annotations

import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _ge122_build_commit_helpers import strip_environment_confound_hooks  # noqa: E402

_WORKTREE_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_PATH = _WORKTREE_ROOT / "scripts" / "ci" / "check_consumer_install.py"
_CI_YML_PATH = _WORKTREE_ROOT / ".github" / "workflows" / "ci.yml"

_HOOK_ID_PATTERN = re.compile(r"      - id: (\S+)")
# The always-kept whitelist id the current (pre-fix) narrowing preserves —
# see _use_install_step.py's _ALWAYS_KEEP_HOOK_IDS. Used here only to build
# an independent, test-side fixture (a registry that ALREADY equals what the
# step's own narrowing would keep), never to assert against.
_ALWAYS_KEEP_HOOK_IDS = {"ensure-precommit-config"}

_CI_STEP_PATTERN = re.compile(
    r"- name: Run consumer install simulation\n(?:\s*#.*\n)*\s*run:\s*(?P<cmd>.+)"
)


def _run_check_consumer_install(
    target_dir: Path, extra_args: list[str]
) -> subprocess.CompletedProcess[str]:
    argv = [
        sys.executable,
        str(_SCRIPT_PATH),
        "--package-dir",
        str(_WORKTREE_ROOT),
        "--target-dir",
        str(target_dir),
        *extra_args,
    ]
    return subprocess.run(argv, capture_output=True, text=True, timeout=180, check=False)


def _deployed_hook_ids(target_dir: Path) -> set[str]:
    registry_text = (target_dir / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    return set(_HOOK_ID_PATTERN.findall(registry_text))


def _extract_ci_command() -> str:
    text = _CI_YML_PATH.read_text(encoding="utf-8")
    match = _CI_STEP_PATTERN.search(text)
    if not match:
        raise AssertionError(
            "Could not locate the 'Run consumer install simulation' step's run: "
            f"line in {_CI_YML_PATH}"
        )
    return match.group("cmd").strip()


def _has_qualified_marker(text: str) -> bool:
    return bool(re.search(r"qualified", text, re.IGNORECASE))


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False)


_DECOY_HOOK_ID = "bp900h6ii-decoy-kept-but-skipped"
_DECOY_HOOK_BLOCK = (
    f"      - id: {_DECOY_HOOK_ID}\n"
    "        name: BP-900h-6-ii decoy guard (test fixture; never matches staged files)\n"
    "        entry: python .leafcutter/scripts/commit_guardian/run_hook.py "
    ".leafcutter/scripts/commit_guardian/check_identifier_uniqueness.py --bp900h6ii-decoy\n"
    "        language: system\n"
    r"        files: ^this-file-will-never-be-staged\.txt$" "\n"
    "        stages: [pre-commit]\n"
    "        pass_filenames: false\n"
)


def _inject_kept_but_skipped_decoy_hook(target_dir: Path) -> str:
    """Add a synthetic hook the step's own keep-filter classifies as KEPT
    (its ``entry`` contains ``check_identifier_uniqueness``, the same
    substring ``_use_install_step._RELEVANT_ENTRY_SUBSTRING`` matches on),
    but whose ``files:`` pattern can never match the adopter's staged
    change — so pre-commit reports it ``Skipped`` rather than
    ``Passed``/``Failed``.

    This is a real, on-disk induction of BP-900h-6-ii's second failure
    shape — "a deployed guard appears in neither the executed nor the
    withheld list" — built entirely from the test side, through the real
    keep/withhold seam the production code already exposes (a block's
    entry text), without touching a single line of ``_use_install_step.py``.

    Returns:
        The injected hook's id, so the caller can assert it is the one
        named in the job's UNACCOUNTED GUARDS output.
    """
    real_config_path = (target_dir / ".pre-commit-config.yaml").resolve()
    original_text = real_config_path.read_text(encoding="utf-8")
    first_hook_match = _HOOK_ID_PATTERN.search(original_text)
    if first_hook_match is None:
        raise AssertionError(
            f"Could not locate any hook id in {real_config_path} to inject the decoy before."
        )
    insertion_point = first_hook_match.start()
    new_text = original_text[:insertion_point] + _DECOY_HOOK_BLOCK + original_text[insertion_point:]
    real_config_path.write_text(new_text, encoding="utf-8")
    return _DECOY_HOOK_ID


def _break_narrowing_write_permission(target_dir: Path) -> None:
    """Make the deployed pre-commit registry read-only so the step's own
    narrowing write (``_use_install_step._write_registry_inside_target_root``)
    fails with a real ``PermissionError`` — the exact ``OSError`` branch
    ``_isolate_precommit_registry_for_scratch_fixture`` already carries for
    this case, confirmed by Read of the production module.

    When the write fails, the on-disk registry is left completely unchanged
    (the FULL, un-narrowed set of guards), while ``withheld_guard_ids`` comes
    back empty — no guard is EVER assigned a withheld reason on this run.
    Several guards in that full registry are documented (KI-CG-017 and
    siblings, see ``_use_install_step.py``'s ARCHITECTURE note) to misfire
    against a first-commit scratch project; ``fail_fast: true`` then halts
    the run before most of the registry is even attempted. Every guard
    that never got a turn is neither executed nor withheld-with-a-reason —
    this is the closest real, reachable proof this codebase can offer that
    a narrowing which fails to record itself must still fail the job,
    rather than the AC's literal "withheld yet its own reasons dict is
    missing an entry" state, which the current (correct) implementation
    makes structurally unreachable: every id in ``withheld_guard_ids`` is
    assigned the identical ``_WITHHELD_REASON`` unconditionally, so there is
    no legitimate input that withholds a guard while omitting its reason.
    """
    real_config_path = (target_dir / ".pre-commit-config.yaml").resolve()
    real_config_path.chmod(0o444)


class TestBp900h6iiAccounting(unittest.TestCase):
    """Entries 1-3: deployed-count accounting, verdict distinguishability,
    and the must-block silent/unaccounted-narrowing case.

    A single golden build is produced once in setUpClass and copied fresh
    into each test's own scratch directory, since scripts/build.py takes
    several real seconds per invocation and none of these three entries need
    a fresh build of their own — only a fresh, isolated COPY of one.
    """

    _golden_tmp: tempfile.TemporaryDirectory[str]
    _golden_dir: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls._golden_tmp = tempfile.TemporaryDirectory()
        cls._golden_dir = Path(cls._golden_tmp.name) / "golden_install"
        build_result = subprocess.run(
            [sys.executable, str(_WORKTREE_ROOT / "scripts" / "build.py"),
             "--target-dir", str(cls._golden_dir)],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        if build_result.returncode != 0:
            raise RuntimeError(
                "Precondition failed: could not build the golden install fixture.\n"
                f"stdout:\n{build_result.stdout}\nstderr:\n{build_result.stderr}"
            )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._golden_tmp.cleanup()

    def _fresh_copy(self, dest: Path) -> None:
        shutil.copytree(self._golden_dir, dest)

    def test_bp900h6ii_narrowed_run_names_every_withheld_guard_and_states_the_deployed_count(
        self,
    ) -> None:
        # covers: BP-900h-6-ii
        # angle: criterion
        """The stated deployed count must match the registry BEFORE the
        step's own narrowing; executed + withheld names must partition the
        deployed names exactly; each withheld guard must carry a reason.
        """
        with tempfile.TemporaryDirectory() as tmp:
            target_dir = Path(tmp) / "narrowed_install"
            self._fresh_copy(target_dir)

            deployed_ids = _deployed_hook_ids(target_dir)
            self.assertGreater(
                len(deployed_ids),
                2,
                msg=(
                    "Precondition: the deployed registry must carry more than the 2 hooks "
                    "the current narrowing keeps, or this test cannot distinguish a "
                    "narrowed run from a full one."
                ),
            )

            result = _run_check_consumer_install(target_dir, ["--skip-build", "--use-install"])
            combined = result.stdout + result.stderr

            deployed_count_match = re.search(r"DEPLOYED GUARDS:\s*(\d+)", combined)
            self.assertIsNotNone(
                deployed_count_match,
                msg=(
                    "Expected a stated 'DEPLOYED GUARDS: <N>' count in the report, taken "
                    "from the registry BEFORE narrowing (here N should be "
                    f"{len(deployed_ids)}). Today the report carries no deployed-count "
                    f"line at all.\nOutput:\n{combined}"
                ),
            )
            assert deployed_count_match is not None  # narrows type for the static checker
            self.assertEqual(str(len(deployed_ids)), deployed_count_match.group(1))

            withheld_match = re.search(r"WITHHELD GUARDS:\s*(.*)", combined)
            self.assertIsNotNone(
                withheld_match,
                msg=f"Expected a 'WITHHELD GUARDS: ...' line in the report.\nOutput:\n{combined}",
            )
            assert withheld_match is not None
            withheld_names = {n.strip() for n in withheld_match.group(1).split(",") if n.strip()}

            executed_match = re.search(r"EXECUTED GUARDS:\s*(.*)", combined)
            self.assertIsNotNone(executed_match, msg=f"Expected an EXECUTED GUARDS line.\n{combined}")
            assert executed_match is not None
            executed_names = {n.strip() for n in executed_match.group(1).split(",") if n.strip()}

            self.assertEqual(
                deployed_ids,
                executed_names | withheld_names,
                msg="The union of executed + withheld guard names must equal the deployed names.",
            )
            self.assertEqual(
                set(),
                executed_names & withheld_names,
                msg="No guard may appear in both the executed and withheld sets.",
            )
            for name in withheld_names:
                self.assertIn(
                    f"{name}:",
                    combined,
                    msg=f"Withheld guard {name!r} must carry a recorded reason.\n{combined}",
                )

    def test_bp900h6ii_a_narrowed_run_and_a_full_run_do_not_produce_the_same_verdict(self) -> None:
        # covers: BP-900h-6-ii
        # angle: boundary
        """A run in which nothing was withheld gets the unqualified pass; a
        run in which guards were withheld gets a textually distinct
        qualified verdict. Both commits succeed, so exit status alone cannot
        separate them.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            # "Full" run: pre-narrow the registry (test-side, via the shared
            # GE-122 fixture helper) to exactly what the step's own
            # narrowing would keep, so its narrowing is a no-op and every
            # guard this run considers "deployed" is active.
            full_target = tmp_path / "full_run_install"
            self._fresh_copy(full_target)
            strip_environment_confound_hooks(full_target)

            # "Narrowed" run: leave the richer registry build.py produced,
            # so the step's own narrowing withholds guards.
            narrowed_target = tmp_path / "narrowed_run_install"
            self._fresh_copy(narrowed_target)

            full_result = _run_check_consumer_install(full_target, ["--skip-build", "--use-install"])
            narrowed_result = _run_check_consumer_install(
                narrowed_target, ["--skip-build", "--use-install"]
            )

            self.assertEqual(
                0,
                full_result.returncode,
                msg=(
                    "Precondition failed: the full (nothing-withheld) run must itself "
                    f"complete.\nstdout:\n{full_result.stdout}\nstderr:\n{full_result.stderr}"
                ),
            )
            self.assertEqual(
                0,
                narrowed_result.returncode,
                msg=(
                    "Precondition failed: the narrowed run must itself complete.\n"
                    f"stdout:\n{narrowed_result.stdout}\nstderr:\n{narrowed_result.stderr}"
                ),
            )

            full_combined = full_result.stdout + full_result.stderr
            narrowed_combined = narrowed_result.stdout + narrowed_result.stderr

            self.assertFalse(
                _has_qualified_marker(full_combined),
                msg=(
                    "A run in which nothing was withheld must emit the UNQUALIFIED pass.\n"
                    f"Output:\n{full_combined}"
                ),
            )
            self.assertTrue(
                _has_qualified_marker(narrowed_combined),
                msg=(
                    "A run in which guards were withheld must emit a QUALIFIED verdict, "
                    "textually distinct from the unqualified pass. Today the report never "
                    "distinguishes the two — both would print the same "
                    f"'EXECUTED GUARDS: ...' line with no qualifier.\nOutput:\n{narrowed_combined}"
                ),
            )
            self.assertNotEqual(
                full_combined.strip(),
                narrowed_combined.strip(),
                msg="A narrowed run and a full run must not produce the same verdict output.",
            )

    def test_bp900h6ii_a_silent_or_unaccounted_narrowing_fails_the_job(self) -> None:
        # covers: BP-900h-6-ii
        # angle: failure
        """Must-block case, driven through TWO induced configurations per
        this AC's test_spec descriptor — a deployed guard withheld with no
        recorded reason, and (separately) a deployed guard that appears in
        neither the executed nor the withheld list. Both must fail the job
        and name the offending guard.

        POST-FIX RE-AUTHORING NOTE (classification: test_drift). The
        original version of this test asserted that the step's *default*
        narrowing (no induced input at all) must fail — that was true
        pre-fix, when every withheld guard was dropped with no reason
        recorded anywhere. Read of scripts/ci/_use_install_step.py today
        shows `run_use_install_step` now assigns `_WITHHELD_REASON`
        unconditionally to every id in `withheld_guard_ids`
        (`{hook_id: _WITHHELD_REASON for hook_id in withheld_ids}`), so the
        default narrowing legitimately completes with a QUALIFIED verdict
        (exit 0) — exactly what
        `test_bp900h6ii_a_narrowed_run_and_a_full_run_do_not_produce_the_same_verdict`
        (the sibling test, left untouched) asserts. Production is correct;
        the old assertion was stale. This version induces the two failure
        configurations the descriptor actually calls for, rather than
        relying on the default path being broken.

        Configuration 1 — "withheld with no recorded reason" (closest real,
        reachable analogue). Under the current, correct implementation the
        literal state — an id present in `withheld_guard_ids` whose entry is
        missing from `withheld_guard_reasons` — is structurally unreachable
        by design (see `_break_narrowing_write_permission`'s docstring): the
        reason dict is built as a total function over `withheld_ids` with a
        single constant reason, so there is no legitimate input that
        withholds a guard while omitting its reason. What CAN be induced
        honestly is the step's own narrowing-write failing outright (a real
        `PermissionError`, the exact `OSError` branch the production code
        already carries): every guard the step meant to withhold then gets
        NO reason recorded anywhere (not even the defensive
        '(no reason recorded)' fallback text, since it never enters
        `withheld_guard_ids` at all) — the report must still refuse to pass.

        Configuration 2 — "appears in neither the executed nor the withheld
        list", constructed directly and literally: a synthetic hook is
        injected whose entry matches the step's own KEEP criterion (contains
        "check_identifier_uniqueness"), so the real narrowing keeps it, but
        whose `files:` pattern can never match the adopter's staged change,
        so pre-commit reports it Skipped rather than Passed/Failed. A kept
        guard that never runs is deployed, not withheld, and never executed.

        Reason-integrity check (added, no induced failure at all): because
        neither configuration above exercises the normal reason-population
        line itself, a THIRD block runs the step against a plain narrowed
        install and asserts no withheld guard's line falls back to the
        report's own '(no reason recorded)' default text. This is the
        assertion that actually goes red if a future change drops one
        withheld guard's recorded reason while still counting it correctly
        as withheld — the literal mutation this test must be able to catch.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            # --- Configuration 1: narrowing-write failure -> no reason is
            # ever recorded for any guard the step meant to withhold. -----
            no_reason_target = tmp_path / "no_reason_recorded_install"
            self._fresh_copy(no_reason_target)

            deployed_ids = _deployed_hook_ids(no_reason_target)
            withheld_candidates = deployed_ids - _ALWAYS_KEEP_HOOK_IDS
            self.assertGreater(
                len(withheld_candidates),
                0,
                msg=(
                    "Precondition: the deployed registry must carry a hook the step's "
                    "current whitelist would withhold, or configuration 1 below proves "
                    "nothing."
                ),
            )
            never_recorded_example = sorted(withheld_candidates)[0]

            _break_narrowing_write_permission(no_reason_target)

            no_reason_result = _run_check_consumer_install(
                no_reason_target, ["--skip-build", "--use-install"]
            )
            no_reason_combined = no_reason_result.stdout + no_reason_result.stderr

            self.assertNotEqual(
                0,
                no_reason_result.returncode,
                msg=(
                    "Configuration 1: when the step's own narrowing-write fails, every "
                    "guard it meant to withhold ends up with NO recorded reason anywhere "
                    "— the run must fail rather than silently pass.\n"
                    f"Output:\n{no_reason_combined}"
                ),
            )
            unaccounted_match_1 = re.search(r"UNACCOUNTED GUARDS:\s*(.*)", no_reason_combined)
            self.assertIsNotNone(
                unaccounted_match_1,
                msg=(
                    "Configuration 1 must surface an UNACCOUNTED GUARDS line naming what "
                    f"the failed narrowing-write left with no recorded reason.\n"
                    f"Output:\n{no_reason_combined}"
                ),
            )
            assert unaccounted_match_1 is not None
            self.assertIn(
                never_recorded_example,
                unaccounted_match_1.group(1),
                msg=(
                    f"Guard {never_recorded_example!r}, which the step would ordinarily "
                    "have withheld (with a reason), must be named in the UNACCOUNTED "
                    f"GUARDS line once the narrowing-write itself fails.\n"
                    f"Output:\n{no_reason_combined}"
                ),
            )

            # --- Configuration 2: a KEPT guard that pre-commit Skips ----
            # (never Passed/Failed) -> deployed, not withheld, not executed.
            neither_list_target = tmp_path / "neither_list_install"
            self._fresh_copy(neither_list_target)

            decoy_id = _inject_kept_but_skipped_decoy_hook(neither_list_target)

            neither_list_result = _run_check_consumer_install(
                neither_list_target, ["--skip-build", "--use-install"]
            )
            neither_list_combined = neither_list_result.stdout + neither_list_result.stderr

            self.assertNotEqual(
                0,
                neither_list_result.returncode,
                msg=(
                    "Configuration 2: a deployed guard the step's own keep-filter chose to "
                    "keep, but which never actually executed (Skipped, not Passed/Failed), "
                    f"must fail the job.\nOutput:\n{neither_list_combined}"
                ),
            )
            unaccounted_match_2 = re.search(r"UNACCOUNTED GUARDS:\s*(.*)", neither_list_combined)
            self.assertIsNotNone(
                unaccounted_match_2,
                msg=(
                    "Configuration 2 must surface an UNACCOUNTED GUARDS line naming the "
                    f"kept-but-never-run decoy guard.\nOutput:\n{neither_list_combined}"
                ),
            )
            assert unaccounted_match_2 is not None
            self.assertIn(
                decoy_id,
                unaccounted_match_2.group(1),
                msg=(
                    f"The decoy guard {decoy_id!r} — kept by the narrowing but Skipped by "
                    "pre-commit — must be named in the UNACCOUNTED GUARDS line.\n"
                    f"Output:\n{neither_list_combined}"
                ),
            )

            # --- Reason-integrity check (a normal, non-induced narrowed
            # run): every withheld guard's recorded reason must be real,
            # never the report's own silent-failure fallback text. Neither
            # configuration above exercises the reason-population line
            # itself (configuration 1 bypasses it via a write failure;
            # configuration 2's decoy is KEPT, never withheld), so without
            # this check a regression that drops one withheld guard's
            # recorded reason — while leaving it correctly counted as
            # withheld — would slip past both. This is the assertion that
            # must go red under exactly that mutation.
            reason_integrity_target = tmp_path / "reason_integrity_install"
            self._fresh_copy(reason_integrity_target)

            reason_integrity_result = _run_check_consumer_install(
                reason_integrity_target, ["--skip-build", "--use-install"]
            )
            reason_integrity_combined = reason_integrity_result.stdout + reason_integrity_result.stderr

            reason_withheld_match = re.search(r"WITHHELD GUARDS:\s*(.*)", reason_integrity_combined)
            self.assertIsNotNone(
                reason_withheld_match,
                msg=(
                    "Expected a WITHHELD GUARDS line in a normal narrowed run.\n"
                    f"Output:\n{reason_integrity_combined}"
                ),
            )
            assert reason_withheld_match is not None
            reason_withheld_names = {
                n.strip() for n in reason_withheld_match.group(1).split(",") if n.strip()
            }
            self.assertGreater(
                len(reason_withheld_names),
                0,
                msg=(
                    "Precondition: a normal run must withhold at least one guard for this "
                    "reason-integrity check to mean anything."
                ),
            )
            for name in reason_withheld_names:
                self.assertNotIn(
                    f"{name}: (no reason recorded)",
                    reason_integrity_combined,
                    msg=(
                        f"Guard {name!r} is withheld but its recorded reason fell back to "
                        "the report's own '(no reason recorded)' default — a narrowing "
                        f"must never go unrecorded.\nOutput:\n{reason_integrity_combined}"
                    ),
                )


class TestBp900h6iiReachability(unittest.TestCase):
    def test_bp900h6ii_the_verdict_is_read_from_the_output_of_the_command_the_workflow_runs(
        self,
    ) -> None:
        # covers: BP-900h-6-ii
        # angle: reachability
        """The accounting must appear in what the exact command ci.yml
        parses for the consumer-simulation step actually emits. RED BY
        DESIGN: that command carries no --use-install flag today, so nothing
        in CI reaches the use-install step, let alone its accounting.
        """
        ci_command = _extract_ci_command()

        with tempfile.TemporaryDirectory() as tmp:
            workspace_dir = Path(tmp) / "ci_workspace"
            workspace_dir.mkdir()
            (workspace_dir / "leafcutter-ai").symlink_to(_WORKTREE_ROOT)

            argv = shlex.split(ci_command)
            argv[0] = sys.executable  # adapt the interpreter binary only; arguments unchanged
            result = subprocess.run(
                argv, cwd=str(workspace_dir), capture_output=True, text=True, timeout=180,
                check=False,
            )
            combined = result.stdout + result.stderr

            self.assertIn(
                "DEPLOYED GUARDS",
                combined,
                msg=(
                    "The accounting (deployed-guard count / executed / withheld) must "
                    "appear in what the job the runner actually invokes emits. RED TODAY "
                    "BY DESIGN: ci.yml's command carries no --use-install flag, so the "
                    "use-install step — and any accounting inside it — never runs at all.\n"
                    f"Parsed command: {ci_command!r}\nstdout:\n{result.stdout}\n"
                    f"stderr:\n{result.stderr}"
                ),
            )


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-31 [test-writer/BP-900h-6-ii]: Initial RED test-first stubs for
#   all four test_spec descriptors. All four are expected to fail today —
#   see the red_baseline in this ticket's sign-off comment. The "full run"
#   fixture in entry 2 reuses strip_environment_confound_hooks from the
#   shared _ge122_build_commit_helpers test module (test-side fixture prep,
#   independent of the code under test) to pre-narrow a registry to exactly
#   what the step's own current whitelist would keep, so that run's
#   narrowing step is a no-op and every guard it considers "deployed" is
#   active — the only way to construct a genuine "nothing withheld" run
#   through the real subprocess entry point today, since no CLI knob to
#   disable narrowing exists.
# - 2026-08-31 [test-writer/BP-900h-6-ii, re-authoring pass]: (classification:
#   test_drift). Production landed and 7/8 tests went strict-green; the 8th
#   — test_bp900h6ii_a_silent_or_unaccounted_narrowing_fails_the_job — and
#   test_bp900h6ii_a_narrowed_run_and_a_full_run_do_not_produce_the_same_verdict
#   made contradictory assertions about the SAME default-narrowing input
#   (assertEqual(0, ...) vs assertNotEqual(0, ...)), because the original
#   silent-narrowing test was authored pre-fix, when the default narrowing
#   dropped every withheld guard with no reason recorded anywhere. Read of
#   scripts/ci/_use_install_step.py confirms `run_use_install_step` now
#   assigns `_WITHHELD_REASON` unconditionally to every withheld id, so the
#   default narrowing legitimately produces the QUALIFIED pass the sibling
#   test correctly asserts — production is correct, the silent-narrowing
#   test's premise was stale. Re-authored it to construct the two
#   configurations its own test_spec descriptor names (a guard withheld with
#   no recorded reason; a guard in neither the executed nor withheld list)
#   rather than relying on the default path being broken: configuration 1
#   forces the step's own narrowing-write to fail (chmod 0o444 on the real,
#   symlink-resolved registry file) so the OSError branch
#   `_isolate_precommit_registry_for_scratch_fixture` already carries fires
#   for real, leaving every guard the step meant to withhold with no
#   recorded reason at all; configuration 2 injects a synthetic hook whose
#   entry matches the step's own KEEP criterion but whose `files:` pattern
#   never matches the adopter's staged change, so it is kept yet Skipped —
#   present in neither the executed nor withheld list. Neither touches
#   scripts/ci/_use_install_step.py or any other production file; both drive
#   the real subprocess entry point per this AC's REACHABILITY clause. The
#   sibling verdict-distinguishability test and the other five tests in this
#   file were left untouched — they pass and their premises are correct.
# ====================================================================
