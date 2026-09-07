"""
MODULE: unit_tests/commit_guardian/test_bp_100n_4.py
GOAL: BP-100n-4 — the population of commit gates the reachability check walks
    must be taken from the gate scripts present ON DISK (recursive listing,
    identity by path beneath the gate directory, never by bare filename), and
    the invoking population must be taken from the entry lines the generated
    commit-time configuration actually emits (last-.py-token extraction,
    never the last whitespace token, never a kebab-cased id comparison). A
    script no registry entry names must be reported by name, and the run must
    fail.
BUSINESS CONTEXT: KI-CG-20260831-hook-scripts-never-invoked. The incumbent
    check_hook_trigger_reachability.py (BP-100k-4) walks only
    hooks_manifest.hooks — its input IS the registry, so a script that was
    never registered at all is invisible to it. This AC widens the census to
    include the disk side, so the guard can finally detect the gate class it
    was blind to: a script nobody wired up at all.
    See docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/BP-100n-4.yaml
    and docs/known-issues/commit-guardian.md.

NEW PRODUCTION BEHAVIOUR THIS TEST FILE SPECIFIES (does not exist yet, in
    templates/scripts/commit_guardian/check_hook_trigger_reachability.py and
    templates/scripts/commit_guardian/_hook_trigger_reachability_helpers.py):

    Disk-side enumeration: recursively list every ``check_*.py``-shaped gate
    script beneath the directory holding check_hook_trigger_reachability.py
    itself (subdirectories included), identified by its path relative to
    that directory — never by bare filename, so
    ``hooks/check_ac_limits.py`` and ``check_ac_limits.py`` are two distinct
    population members.

    Invoking-side enumeration: build the generated commit-time configuration
    (the entry lines pre-commit would actually run) from the loaded
    registry, and for each entry take the LAST TOKEN ENDING IN ``.py`` (never
    the last whitespace-delimited token, which misreads a trailing flag such
    as check-done-proof's ``--test-root .`` as the invoked script).

    Reported classes (new RESULT line fields, extending the existing
    ``check-hook-trigger-reachability: RESULT total=... unreachable=...
    exempt=... nothing_to_match=...`` line in place):
      ``compared=<n>``    — gate scripts found on disk (BP-100n-4-ii).
      ``registered=<n>``  — registry entries read (BP-100n-4-ii).
      ``unreferenced=<n>`` — scripts on disk that no emitted entry line
                             invokes (this AC).
      ``declared_non_gate=<n>`` — BP-100n-4-i's register size.
    Per-script diagnostic lines this AC introduces:
      ``UNREFERENCED: <path> reason=<free text>`` — one per script no
          emitted entry line invokes.
      ``SWITCHED-OFF: <path> reason=<free text>`` — one per script named
          only by a registry entry carrying ``enabled: false`` (registered
          and deliberately off is a third state, distinct from invoked and
          from absent).
    A script named by an EMITTED entry line is reported in NEITHER class —
    "not reported at all" is the correct, silent outcome for it.

    TEST INTERFACE CONTRACT (mirrors the existing HOOK_TEST_CONFIG
    convention already established by this same script for BP-100k-4):
      ``HOOK_TEST_GATE_DIR`` (env var) — when set, the disk-side census
      walks THIS directory instead of the directory holding the running
      script. Used only by BP-100n-4-ii's indeterminate-path tests to make
      the disk listing genuinely unlistable / genuinely empty without
      disturbing the script's own directory (which must remain listable for
      the interpreter to load the script at all). Production code never
      sets this variable.

SPLIT NOTE (check-file-size, BP-100n-4 itself): this module originally held
    all eight test_spec descriptors for this AC. Splitting purely to keep
    this NEW file under check-file-size's absolute 400-counted-line cap for
    new files, two sibling modules were split off, each named for the
    property it covers rather than "_part2" (mirroring this same directory's
    established test_bp_100k_4_ii.py / test_bp_100k_4_ii_registry_shapes.py
    convention: shared fixtures are IMPORTED via importlib under a private
    module name, never copy-pasted — see each sibling's own docstring):
      - test_bp_100n_4_unreferenced_and_switched_off.py — test_spec 2 (the
        decisive anti-grep synthetic-unregistered-script injection) and
        test_spec 4 (the disabled/"switched-off" third state).
      - test_bp_100n_4_execution_surfaces.py — test_spec 6 (the registered
        hook entry point) and test_spec 7 (the deployed copy).
    This module keeps test_spec 1 (both the top-level and subdirectory
    variants), test_spec 3, and test_spec 5 — the population-enumeration and
    invoking-side token-extraction core that the other two modules' fixtures
    are borrowed from.

RED BASELINE (expected, captured before this AC's disk-side enumeration is
    written): every test below is RED. The incumbent implementation has no
    disk side at all, so the extended RESULT line fields
    (compared=/registered=/unreferenced=/declared_non_gate=) never appear —
    every regex search against them returns None, which every assertion
    below turns into either an explicit AssertionError (assertIsNotNone) or
    an AttributeError if a test tries to read a capture group off a None
    match. Both are legitimate red states per the test-writer contract.

    Per CLAUDE.md "Gate / Workflow ACs — Verify Behaviorally, Not by Grep":
    every test executes the real check_hook_trigger_reachability.py as a
    subprocess against a REAL fixture copy of
    templates/scripts/commit_guardian/ (never a grep of the guard's source
    or of commit_guardian.json's text).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CG_TEMPLATES_SRC = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_BUILD_SCRIPT = _REPO_ROOT / "scripts" / "build.py"
_REACHABILITY_HOOK_NAME = "check_hook_trigger_reachability.py"

_SUBPROCESS_TIMEOUT_SECONDS = 30
_BUILD_TIMEOUT_SECONDS = 180

# Extended RESULT line contract this AC family introduces (see module
# docstring). Group 1=compared, 2=registered, 3=unreferenced,
# 4=declared_non_gate.
_RESULT_LINE_RE = re.compile(
    r"check-hook-trigger-reachability:\s*RESULT\b"
    r".*?\bcompared=(\d+)\b"
    r".*?\bregistered=(\d+)\b"
    r".*?\bunreferenced=(\d+)\b"
    r".*?\bdeclared_non_gate=(\d+)\b",
    re.IGNORECASE | re.DOTALL,
)


# ---------------------------------------------------------------------------
# Shared helpers (also imported, read-only, by this AC's sibling modules —
# see the SPLIT NOTE above)
# ---------------------------------------------------------------------------


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run a git subcommand against *cwd* and return the completed process."""
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )


def _init_repo(repo: Path) -> None:
    """Initialize a fresh, minimally-configured git repo at *repo*."""
    repo.mkdir(parents=True, exist_ok=True)
    _git(["init", "-b", "main"], repo)
    _git(["config", "user.email", "bp100n4test@example.com"], repo)
    _git(["config", "user.name", "BP-100n-4 Test"], repo)


def _commit_all(repo: Path, message: str) -> None:
    """Stage everything currently on disk under *repo* and commit it."""
    _git(["add", "-A"], repo)
    _git(["commit", "-m", message], repo)


def _deploy_gate_dir_copy(workspace: Path) -> Path:
    """Copy the REAL, unmodified templates/scripts/commit_guardian/ tree.

    This is the "fixture copy of the real gate-script directory and the real
    registry" the AC's own test_spec descriptors require — never a
    hand-authored subset.
    """
    dest = workspace / "commit_guardian_copy"
    shutil.copytree(_CG_TEMPLATES_SRC, dest, ignore=shutil.ignore_patterns("__pycache__"))
    return dest


def _run_reachability_hook(
    script_path: Path, cwd: Path, env_overrides: dict | None = None
) -> subprocess.CompletedProcess:
    """Execute check_hook_trigger_reachability.py as a subprocess."""
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )


def _write_gate_script(path: Path) -> None:
    """Write a minimal, real, executable-shaped gate script fixture file."""
    path.write_text("#!/usr/bin/env python3\nimport sys\n\nsys.exit(0)\n", encoding="utf-8")


class _FixtureRepoTestCase(unittest.TestCase):
    """Shared setUp: a real, committed git repo holding a real fixture copy
    of the gate-script directory and its real registry."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self._tmp.name)
        _init_repo(self.workspace)
        self.gate_dir = _deploy_gate_dir_copy(self.workspace)
        self.script_path = self.gate_dir / _REACHABILITY_HOOK_NAME
        _commit_all(self.workspace, "initial real gate-directory fixture copy")

    def tearDown(self) -> None:
        self._tmp.cleanup()


# ---------------------------------------------------------------------------
# test_spec 1: added gate script is reported and the compared count rises.
# ---------------------------------------------------------------------------


class TestAddedGateScriptRaisesComparedCount(_FixtureRepoTestCase):
    def test_bp_100n_4_added_gate_script_is_reported_and_the_compared_count_rises_by_one(
        self,
    ) -> None:
        # covers: BP-100n-4
        # angle: real_artifact
        """THE DECISIVE ANTI-GREP DESCRIPTOR. Over a real fixture copy of the
        gate-script directory and the real registry, capture the stated
        compared count and the reported-unreferenced set from the check's
        own output, add ONE new gate script file, run again, and require the
        new script's name to appear in the reported set and the compared
        count to rise by exactly one. No implementation carrying a literal
        list of script names can pass this — the population must be
        enumerated from the tree at run time.
        """
        first = _run_reachability_hook(self.script_path, self.workspace)
        first_output = first.stdout + first.stderr
        first_match = _RESULT_LINE_RE.search(first_output)
        self.assertIsNotNone(
            first_match,
            "expected a RESULT line stating compared=/registered=/"
            f"unreferenced=/declared_non_gate= counts; got: {first_output!r}",
        )
        first_compared = int(first_match.group(1))

        _write_gate_script(self.gate_dir / "check_bp_100n_4_novel_fixture.py")

        second = _run_reachability_hook(self.script_path, self.workspace)
        second_output = second.stdout + second.stderr
        second_match = _RESULT_LINE_RE.search(second_output)
        self.assertIsNotNone(
            second_match, f"expected a RESULT line on the second run; got: {second_output!r}"
        )
        second_compared = int(second_match.group(1))

        self.assertEqual(
            second_compared,
            first_compared + 1,
            "adding one gate script must raise the stated compared count by exactly one",
        )
        self.assertIn(
            "check_bp_100n_4_novel_fixture.py",
            second_output,
            "the newly added, unregistered script must be named in the check's own output",
        )


class TestAddedGateScriptInSubdirectoryAlsoRaisesComparedCount(_FixtureRepoTestCase):
    def test_bp_100n_4_added_gate_script_inside_a_subdirectory_also_raises_compared_count(
        self,
    ) -> None:
        # covers: BP-100n-4
        # angle: boundary
        """The recursion clause has no red baseline unless a subdirectory
        addition is exercised separately from a top-level one: a gate the
        check cannot see is a gate the check cannot report, and a population
        that stops at the top level silently excuses every gate held below
        it.
        """
        first = _run_reachability_hook(self.script_path, self.workspace)
        first_match = _RESULT_LINE_RE.search(first.stdout + first.stderr)
        self.assertIsNotNone(first_match, "expected a RESULT line on the first run")
        first_compared = int(first_match.group(1))

        subdir = self.gate_dir / "hooks"
        subdir.mkdir(parents=True, exist_ok=True)
        _write_gate_script(subdir / "check_bp_100n_4_subdir_fixture.py")

        second = _run_reachability_hook(self.script_path, self.workspace)
        second_output = second.stdout + second.stderr
        second_match = _RESULT_LINE_RE.search(second_output)
        self.assertIsNotNone(second_match, f"expected a RESULT line; got {second_output!r}")
        second_compared = int(second_match.group(1))

        self.assertEqual(
            second_compared,
            first_compared + 1,
            "a gate script added inside a subdirectory of the gate directory "
            "must raise the compared count exactly as a top-level addition does",
        )
        self.assertIn("check_bp_100n_4_subdir_fixture.py", second_output)


# ---------------------------------------------------------------------------
# test_spec 3: a script on an emitted entry line is not reported at all.
# ---------------------------------------------------------------------------


class TestRegisteredInvokedScriptIsNeverReported(_FixtureRepoTestCase):
    def test_bp_100n_4_a_script_on_an_emitted_entry_line_is_not_reported_at_all(
        self,
    ) -> None:
        # covers: BP-100n-4
        # angle: seam
        """check_ac_limits.py is registered and runs under the id
        check-ac-tree-limits (an entry-line-vs-id distinction, not a
        filename-vs-id one — see KI-CG-20260831-hook-scripts-never-invoked's
        Method section). Pipes the REAL registry's real emitted entry line
        directly into the REAL disk enumeration and asserts the consuming
        side (the printed report) never names that script.
        """
        result = _run_reachability_hook(self.script_path, self.workspace)
        output = result.stdout + result.stderr
        match = _RESULT_LINE_RE.search(output)
        self.assertIsNotNone(
            match,
            f"expected the extended RESULT line to exist at all; got {output!r}",
        )
        self.assertNotRegex(
            output,
            r"UNREFERENCED:\s*\S*check_ac_limits\.py",
            "check_ac_limits.py is invoked by an emitted entry line under "
            "id check-ac-tree-limits and must never appear in the "
            "unreferenced/invoked-by-nothing report",
        )


# ---------------------------------------------------------------------------
# test_spec 5: a registered script invoked on no entry line is reported the
# same way as an unreferenced one — the last-.py-token extraction rule.
# ---------------------------------------------------------------------------


class TestTrailingArgsEntryLineStillCountsAsInvoking(_FixtureRepoTestCase):
    def test_bp_100n_4_a_registered_script_invoked_on_no_entry_line_is_reported_the_same_way(
        self,
    ) -> None:
        # covers: BP-100n-4
        # angle: seam
        """check-done-proof's real registry entry line ends
        "check_done_proof.py --test-root ." — a trailing flag AFTER the
        script name. The invoking population must be built by taking the
        LAST TOKEN THAT ENDS IN .py from each generated entry line, never
        the last whitespace-delimited token (which reads as the flag and
        would falsely report check_done_proof.py — a registered, invoked,
        required gate — as invoked by nothing).
        """
        result = _run_reachability_hook(self.script_path, self.workspace)
        output = result.stdout + result.stderr
        match = _RESULT_LINE_RE.search(output)
        self.assertIsNotNone(match, f"expected the extended RESULT line; got {output!r}")
        self.assertNotRegex(
            output,
            r"UNREFERENCED:\s*\S*check_done_proof\.py",
            "check_done_proof.py's entry line carries a trailing flag after "
            "the script name; it must never be reported as invoked by "
            f"nothing. Got: {output!r}",
        )


if __name__ == "__main__":
    unittest.main()
