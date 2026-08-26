"""
MODULE: test_ge_120a_1
AC: GE-120a-1 — "A check that could not perform its inspection reports a
    degraded outcome, not a clean pass"
GOAL: TDD red-baseline tests for the AC-parent-covered-by pre-commit check's
    cannot-run path. Today, when
    templates/scripts/commit_guardian/check_ac_parent_covered_by.py cannot
    reach scripts/ac_store/ac_parent_id.py's derive_parent_id() (e.g. a
    working copy that exposes only the check script, not the sibling
    ac_store/ directory), it prints exactly one line to stderr —
    "cannot import derive_parent_id ...; skipping check (fail-open)" — and
    returns an ORDINARY SUCCESS (exit 0), indistinguishable from a real
    clean pass. This AC requires that cannot-run condition to surface a
    DISTINCT, machine-readable "could-not-check" outcome that names the
    unreachable prerequisite and the unverified scope (the staged file
    count), and requires the legacy silent-fail-open shape to stop being
    produced.

WHY THIS MUST BE EXERCISED FOR REAL, OUT OF PROCESS (per the AC's own
    coverage note and test_rationale): "this criterion is covered only by a
    test that EXECUTES the check under a genuine cannot-reach condition and
    asserts on the observed result value and output text. A test that
    searches the check's source for a warning string does not cover it."
    The defect is a path-resolution failure that does NOT reproduce when the
    check module is imported in-process from the source tree (every existing
    unit test for this check runs that way) — it only reproduces when the
    check is run as a real subprocess from a working copy where the sibling
    scripts/ac_store/ directory is genuinely absent from disk. Every test
    below therefore builds a REAL isolated working copy on disk (via
    tempfile + shutil.copy2 of the real, unmodified check script and, for
    the "reachable" scenario, the real ac_parent_id.py) and invokes the
    check as a separate `python <script>.py` process — the exact shape
    documented in the check's own module docstring
    ("python scripts/commit_guardian/run_hook.py
    scripts/commit_guardian/check_ac_parent_covered_by.py"; run_hook.py
    itself only resolves which interpreter to use and forwards argv/env
    verbatim, so `python <check>.py` IS the real entry point, not a
    simplification of it). No check module is imported directly by these
    tests, and PYTHONPATH is deliberately NOT inherited from the test
    process, so the real repository's own scripts/ package can never leak in
    and mask the condition under test.

CONTRACT THIS TEST FILE ESTABLISHES for whoever implements GE-120a-1 (the
    "shared outcome vocabulary" module the AC's it_requirements calls for,
    "declared ONCE... that every check imports"):

    templates/scripts/commit_guardian/check_outcome.py
        OUTCOME_OK = "ok"
        OUTCOME_COULD_NOT_CHECK = "could_not_check"
        (a third OUTCOME_DEGRADED value is GE-120a-1-ii's concern, not
        required by this file)

    check_ac_parent_covered_by.py's main(), on the cannot-run branch (today
    at ~line 646-654, the `except ImportError` around `_get_derive_parent_id()`):
      - catches ImportError (and, per the AC's error-handling note, OSError)
      - counts the staged files via the same staged-file detection the
        normal path already uses (so the count is accurate whether staged
        files come from HOOK_TEST_FILES or `git diff --cached`)
      - prints, to stderr, text that (a) names "derive_parent_id" as the
        unreachable prerequisite and (b) names the unverified scope using
        the AC's own example wording, "N staged files" (this file asserts
        literally on "6 staged files" for its 6-file fixture)
      - prints a machine-readable, non-prose result line to stdout in the
        form ``RESULT: <value>`` using the OUTCOME_* constants above — a
        fixed-format line a caller can `str.startswith("RESULT: ")` on
        without parsing prose, independent of exit code (GE-120a-2 may make
        an "announce" disposition still exit 0, so exit code alone cannot
        carry this distinction — see the AC's own it_requirements)
      - no longer prints the legacy line "skipping check (fail-open)"
      - does NOT change the exit code semantics on the reachable path: with
        the prerequisite reachable, the existing blocked-with-violations
        behaviour (exit 1, `_emit_violations` text) is unchanged.

    This file does not require an explicit ``RESULT: ok`` line on every
    silent-clean-pass code path — only that ``RESULT: could_not_check`` is
    never emitted when nothing was actually wrong (test 5 below) and that a
    genuine cannot-reach condition does emit it (tests 1-3). Whether ordinary
    clean passes gain an explicit ``RESULT: ok`` line is left to whoever
    implements the shared vocabulary; test 5 does not depend on it.

    Neither templates/scripts/commit_guardian/check_outcome.py nor the
    updated cannot-run branch exists yet at test-writer time — confirmed: no
    check_outcome.py anywhere in the tree, and
    check_ac_parent_covered_by.py's cannot-run branch still prints the
    legacy line verbatim (see its current source, ~line 650). This is the
    valid RED state: every test below runs the CURRENT, unmodified check and
    is expected to FAIL because the legacy fail-open line is still produced
    and no ``RESULT: could_not_check`` line exists.

====================================================================
DECISION HISTORY
====================================================================
- 2026-08-25 [EPIC-TrustThatAGreenCheckActuallyChecked/01, GE-120a-1]:
  Initial TDD red-baseline. Chose a self-contained fixture strategy (copy
  ONLY the real check script into an isolated tempdir for the "cannot-reach"
  scenario; additionally copy the real ac_parent_id.py into the expected
  sibling location for the "reachable" scenario) rather than depending on
  GE-120c-1's not-yet-built shared out-of-process harness
  (unit_tests/portability/_deployed_check_harness.py / harness.py — neither
  exists yet per GE-120c-1-i's and GE-120e-2-i's own red-baseline notes in
  this same directory). This keeps GE-120a-1's tests independently
  executable without a cross-ticket dependency on GE-120c-1 landing first.
  If GE-120c-1's harness lands with equivalent guarantees (real second
  copy, real subprocess, source tree off the import path), a follow-up may
  migrate these tests onto it — that migration is out of scope here.
====================================================================
"""
# @ac-tag: GE-120a-1

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Path setup — locate the real, unmodified production files this ticket's
# fix will touch. No check module is ever imported in-process: only copied
# to disk and executed as a subprocess, per the AC's coverage note.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]  # unit_tests/portability/ -> worktree root
_REAL_CHECK_SCRIPT = (
    _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_ac_parent_covered_by.py"
)
_REAL_AC_PARENT_ID = _REPO_ROOT / "scripts" / "ac_store" / "ac_parent_id.py"

_SUBPROCESS_TIMEOUT_SECONDS = 15
_VIOLATION_PAIR_COUNT = 6


def _fixture_precondition_ok() -> str | None:
    """Return an error message if the real source files this test depends on
    are missing, else None. A missing source file is a fixture problem, not
    a normal red state, and must be reported distinctly."""
    if not _REAL_CHECK_SCRIPT.exists():
        return f"Fixture precondition failed: {_REAL_CHECK_SCRIPT} does not exist."
    if not _REAL_AC_PARENT_ID.exists():
        return f"Fixture precondition failed: {_REAL_AC_PARENT_ID} does not exist."
    return None


def _write_violating_pairs(ac_store_dir: Path, count: int) -> list[str]:
    """Write *count* real parent/child AC YAML file pairs to ac_store_dir,
    each pair a genuine covered_by violation (parent's covered_by omits the
    child), serialized via yaml.safe_dump (never a hand-typed literal, per
    the Fixture Authenticity Rule).

    Returns:
        Absolute path strings of the *count* child YAML files (the "staged"
        files for HOOK_TEST_FILES).
    """
    ac_store_dir.mkdir(parents=True, exist_ok=True)
    child_paths: list[str] = []
    for i in range(count):
        parent_id = f"ZQ-9{i:02d}"  # matches root pattern [A-Z]{2,6}-[0-9]{3,}
        child_id = f"{parent_id}a"  # matches alpha-sublevel pattern

        parent_path = ac_store_dir / f"{parent_id}.yaml"
        parent_path.write_text(
            yaml.safe_dump({"id": parent_id, "covered_by": []}),
            encoding="utf-8",
        )

        child_path = ac_store_dir / f"{child_id}.yaml"
        child_path.write_text(
            yaml.safe_dump({"id": child_id, "depends_on": [parent_id]}),
            encoding="utf-8",
        )
        child_paths.append(str(child_path.resolve()))
    return child_paths


def _build_working_copy_with_corrupt_prerequisite(tmp_root: Path) -> Path:
    """Build a REAL isolated working copy where scripts/ac_store/ac_parent_id.py
    exists as a DIRECTORY instead of a file — a genuinely corrupted / half
    -deployed layout (e.g. a partial rsync, a broken symlink target replaced
    by an empty dir) rather than the fully-absent case the other tests use.
    Loading it raises a real IsADirectoryError (an OSError subclass), which
    is the SECOND specific exception type this AC's error-handling note
    requires the cannot-run branch to catch ("ImportError / OSError") —
    distinct from the ImportError case the other four tests exercise.

    Confirmed by direct execution against the real, unmodified check (see
    this ticket's DECISION HISTORY): today this raises uncaught out of
    _get_derive_parent_id(), is not caught by main()'s `except ImportError`,
    and falls through to the generic `except Exception` at the bottom of the
    file, producing "unexpected error (fail-open): IsADirectoryError: ..."
    on stderr and exit 0 — a second, differently-shaped instance of the same
    silent-fail-open defect this AC exists to close.

    Returns:
        Absolute path to the copied check script.
    """
    commit_guardian_dir = tmp_root / "scripts" / "commit_guardian"
    commit_guardian_dir.mkdir(parents=True, exist_ok=True)
    check_copy = commit_guardian_dir / "check_ac_parent_covered_by.py"
    shutil.copy2(_REAL_CHECK_SCRIPT, check_copy)

    ac_store_code_dir = tmp_root / "scripts" / "ac_store"
    ac_store_code_dir.mkdir(parents=True, exist_ok=True)
    (ac_store_code_dir / "ac_parent_id.py").mkdir()  # directory, not a file

    return check_copy


def _build_working_copy(tmp_root: Path, *, expose_deployed_layout: bool) -> Path:
    """Build a REAL isolated working copy on disk containing only the real,
    unmodified check_ac_parent_covered_by.py (copied via shutil.copy2 — never
    re-typed), and, when expose_deployed_layout is True, the real
    ac_parent_id.py at the sibling location the check's own
    _get_derive_parent_id() strategy 2 looks for
    (<copy>/scripts/ac_store/ac_parent_id.py relative to
    <copy>/scripts/commit_guardian/check_ac_parent_covered_by.py).

    When expose_deployed_layout is False, the copy exposes ONLY the check
    script — no sibling ac_store/ directory at all — reproducing "the
    working copy it runs from does not expose the deployed layout" exactly
    as this AC's criteria describe it.

    Returns:
        Absolute path to the copied check script.
    """
    commit_guardian_dir = tmp_root / "scripts" / "commit_guardian"
    commit_guardian_dir.mkdir(parents=True, exist_ok=True)
    check_copy = commit_guardian_dir / "check_ac_parent_covered_by.py"
    shutil.copy2(_REAL_CHECK_SCRIPT, check_copy)

    if expose_deployed_layout:
        ac_store_code_dir = tmp_root / "scripts" / "ac_store"
        ac_store_code_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_REAL_AC_PARENT_ID, ac_store_code_dir / "ac_parent_id.py")

    return check_copy


def _run_check(check_script: Path, cwd: Path, hook_root: Path, staged_files: list[str]):
    """Run the check as a REAL separate process — `python <check_script>` —
    the shape the check's own module docstring documents as its usage, with
    PYTHONPATH deliberately absent so the real repository's scripts/ package
    can never leak into the subprocess and mask the condition under test.

    Returns:
        subprocess.CompletedProcess with captured text stdout/stderr.
    """
    import os

    env = {
        "HOOK_ROOT": str(hook_root),
        "HOOK_TEST_FILES": "\n".join(staged_files),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    for passthrough in ("PATH", "HOME", "SYSTEMROOT"):
        if passthrough in os.environ:
            env[passthrough] = os.environ[passthrough]

    return subprocess.run(
        [sys.executable, str(check_script)],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )


class TestCannotRunEmitsCouldNotCheckNotSuccess(unittest.TestCase):
    """GE-120a-1: a check that cannot reach its prerequisite must emit a
    distinct could-not-check outcome, not the ordinary success value."""

    def setUp(self) -> None:
        precondition_error = _fixture_precondition_ok()
        if precondition_error:
            self.fail(precondition_error)
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ge120a1_cannot_run_emits_could_not_check_not_success(self) -> None:
        # covers: GE-120a-1
        """AC-3/AC-4: the outcome is a distinct could-not-check result value,
        not the same success value a clean run produces, when the working
        copy does not expose the deployed layout (genuine cannot-reach
        condition, executed out of process)."""
        ac_store_dir = self.tmp_root / "docs" / "acceptance-criteria" / "fixture_component"
        staged = _write_violating_pairs(ac_store_dir, _VIOLATION_PAIR_COUNT)
        check_script = _build_working_copy(self.tmp_root, expose_deployed_layout=False)

        result = _run_check(check_script, cwd=self.tmp_root, hook_root=self.tmp_root, staged_files=staged)
        combined = result.stdout + "\n" + result.stderr

        self.assertIn(
            "RESULT: could_not_check",
            combined,
            "A genuine cannot-reach condition must emit a distinct, "
            "machine-readable RESULT: could_not_check line — the check's "
            "own module docstring's cannot-run branch (the shared outcome "
            "vocabulary GE-120a-1 introduces) does not exist yet. "
            f"Full output was:\n{combined}",
        )
        self.assertNotIn(
            "RESULT: ok",
            combined,
            "The could-not-check outcome must not coexist with the "
            "ordinary success value in the same run.",
        )


class TestOutputNamesPrerequisiteAndUnverifiedScope(unittest.TestCase):
    """GE-120a-1: the output must name BOTH the unreachable prerequisite
    (derive_parent_id) and the unverified scope (the staged file count)."""

    def setUp(self) -> None:
        precondition_error = _fixture_precondition_ok()
        if precondition_error:
            self.fail(precondition_error)
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ge120a1_output_names_prerequisite_and_unverified_scope(self) -> None:
        # covers: GE-120a-1
        """AC-2: the output states that it did not inspect the staged
        files, names the prerequisite it could not reach (derive_parent_id),
        and names what was consequently left unverified (6 staged files, per
        the AC's own example wording)."""
        ac_store_dir = self.tmp_root / "docs" / "acceptance-criteria" / "fixture_component"
        staged = _write_violating_pairs(ac_store_dir, _VIOLATION_PAIR_COUNT)
        check_script = _build_working_copy(self.tmp_root, expose_deployed_layout=False)

        result = _run_check(check_script, cwd=self.tmp_root, hook_root=self.tmp_root, staged_files=staged)
        combined = result.stdout + "\n" + result.stderr

        self.assertIn(
            "derive_parent_id",
            combined,
            f"Output must name the unreachable prerequisite by name. Full output:\n{combined}",
        )
        self.assertRegex(
            combined,
            re.compile(r"6\s+staged\s+files", re.IGNORECASE),
            "Output must name the unverified scope using the AC's own "
            "example wording, 'N staged files', with N == 6 for this "
            f"fixture's 6 staged files. Full output:\n{combined}",
        )


class TestLegacyFailOpenShapeNoLongerSatisfiesContract(unittest.TestCase):
    """GE-120a-1: the behaviour observed today — a single stderr line
    'cannot import derive_parent_id ...; skipping check (fail-open)'
    followed by an ordinary success result — no longer satisfies the
    check's contract."""

    def setUp(self) -> None:
        precondition_error = _fixture_precondition_ok()
        if precondition_error:
            self.fail(precondition_error)
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ge120a1_legacy_failopen_shape_no_longer_satisfies_contract(self) -> None:
        # covers: GE-120a-1
        """AC-4: the observed skipping-check fail-open line followed by an
        ordinary success result is no longer produced by the cannot-run
        path."""
        ac_store_dir = self.tmp_root / "docs" / "acceptance-criteria" / "fixture_component"
        staged = _write_violating_pairs(ac_store_dir, _VIOLATION_PAIR_COUNT)
        check_script = _build_working_copy(self.tmp_root, expose_deployed_layout=False)

        result = _run_check(check_script, cwd=self.tmp_root, hook_root=self.tmp_root, staged_files=staged)
        combined = result.stdout + "\n" + result.stderr

        self.assertNotIn(
            "skipping check (fail-open)",
            combined,
            "The legacy fail-open line must no longer be produced by the "
            f"cannot-run path. Full output:\n{combined}",
        )
        self.assertFalse(
            result.returncode == 0 and "RESULT: could_not_check" not in combined,
            "A cannot-reach run must not silently report an ordinary "
            "success (exit 0, no could-not-check marker) — that is exactly "
            f"the legacy shape this AC forbids. Full output:\n{combined}",
        )


class TestReachablePrerequisiteStillBlocksWithSixViolations(unittest.TestCase):
    """GE-120a-1: main-checkout behaviour must be unchanged — with the
    prerequisite reachable, the same staged set still blocks with the same
    6 violations (GE-118a-1 backward-compatibility precedent)."""

    def setUp(self) -> None:
        precondition_error = _fixture_precondition_ok()
        if precondition_error:
            self.fail(precondition_error)
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ge120a1_reachable_prerequisite_still_blocks_with_six_violations(self) -> None:
        # covers: GE-120a-1
        """AC-5 boundary check: this criterion does not by itself decide
        blocking, but it must not regress the existing reachable-and-blocked
        path — same staged set, same 6 violations, when the prerequisite IS
        reachable."""
        ac_store_dir = self.tmp_root / "docs" / "acceptance-criteria" / "fixture_component"
        staged = _write_violating_pairs(ac_store_dir, _VIOLATION_PAIR_COUNT)
        check_script = _build_working_copy(self.tmp_root, expose_deployed_layout=True)

        result = _run_check(check_script, cwd=self.tmp_root, hook_root=self.tmp_root, staged_files=staged)
        combined = result.stdout + "\n" + result.stderr

        self.assertEqual(
            1,
            result.returncode,
            f"Reachable prerequisite + 6 genuine violations must still block "
            f"(exit 1), unchanged from today's behaviour. Full output:\n{combined}",
        )
        self.assertIn("BLOCKED", combined)
        violation_mentions = combined.count("is staged but parent AC")
        self.assertEqual(
            _VIOLATION_PAIR_COUNT,
            violation_mentions,
            "All 6 genuine violations must be reported — main-checkout "
            f"behaviour must be unchanged. Full output:\n{combined}",
        )
        self.assertNotIn(
            "RESULT: could_not_check",
            combined,
            "A run where the prerequisite IS reachable must never report "
            f"could-not-check. Full output:\n{combined}",
        )


class TestReachableFromEntryPoint(unittest.TestCase):
    """GE-120a-1 reachability floor (mandatory per this ticket's Test
    Requirements): invoke the production entry point — `python
    check_ac_parent_covered_by.py`, the shape the check's own module
    docstring documents — as a real subprocess, and assert the NEW
    behaviour actually occurs, for the SECOND specific exception type the
    AC's error-handling note names (OSError, distinct from the ImportError
    case tests 1-3 exercise): a corrupted prerequisite (ac_parent_id.py
    present as a directory, not a file) must also be converted to the
    could-not-check outcome, not left to fall through to the generic
    catch-all at the bottom of the file. Importing the check's functions
    directly does not satisfy this floor; this test never imports the check
    module."""

    def setUp(self) -> None:
        precondition_error = _fixture_precondition_ok()
        if precondition_error:
            self.fail(precondition_error)
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ge_120a_1_reachable_from_entry_point(self) -> None:
        # covers: GE-120a-1
        """Reachability + error-handling policy: run the real entry point
        against a genuinely corrupted prerequisite (ac_parent_id.py exists
        as a directory, raising a real IsADirectoryError/OSError today) and
        assert the NEW could-not-check outcome fires for this second
        exception type too — not just for the missing-file ImportError case
        the other tests use. Today this falls through uncaught to the
        generic `except Exception` catch-all and prints a differently
        shaped message with no RESULT: line at all; this must change."""
        ac_store_dir = self.tmp_root / "docs" / "acceptance-criteria" / "fixture_component"
        staged = _write_violating_pairs(ac_store_dir, _VIOLATION_PAIR_COUNT)
        check_script = _build_working_copy_with_corrupt_prerequisite(self.tmp_root)

        result = _run_check(check_script, cwd=self.tmp_root, hook_root=self.tmp_root, staged_files=staged)
        combined = result.stdout + "\n" + result.stderr

        self.assertIn(
            "RESULT: could_not_check",
            combined,
            "A corrupted prerequisite (OSError family, not ImportError) "
            "must ALSO produce the could-not-check outcome via the "
            "cannot-run branch's own specific exception handling — not "
            "fall through to the generic catch-all at the bottom of the "
            f"file. Full output:\n{combined}",
        )
        self.assertNotIn(
            "unexpected error (fail-open)",
            combined,
            "The generic bottom-of-file catch-all message must not be what "
            "reports this condition — it is a SPECIFIC, anticipated "
            f"cannot-run condition, not an unexpected crash. Full output:\n{combined}",
        )


if __name__ == "__main__":
    unittest.main()
