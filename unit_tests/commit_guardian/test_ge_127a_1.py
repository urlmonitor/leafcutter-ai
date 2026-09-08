"""
MODULE: unit_tests/commit_guardian/test_ge_127a_1.py
COVERS: GE-127a-1 -- "The change that takes a file past its permitted length
    is refused at the moment it is committed"

GOAL: RED test-first stubs for the CROSSING-refusal behaviour: a change that
    takes a covered file from below its permitted length to above it must be
    refused at an ORDINARY commit; a change that leaves a covered file below
    its limit must complete silently; and a commit mixing one offender with
    one compliant file must name only the offender.

THE DEFECT THIS FILE IS RED AGAINST IS REGISTRATION, NOT THE COMPARISON
    LOGIC. Read templates/scripts/commit_guardian/check_file_size.py's
    ``_classify_file`` before assuming otherwise: the crossing comparison
    (``if lines > limit: return "too_large"``) is ALREADY CORRECT today, and
    invoking check_file_size.py DIRECTLY as a subprocess already refuses a
    crossing commit, names the file, and states both the measured and
    permitted length -- verified in this worktree at authoring time. A test
    that only invokes the script directly would therefore be GREEN on
    arrival, which is not a valid red baseline.

    The actual gap, per GE-127a-1's own doc_link on
    templates/scripts/commit_guardian/check_file_size.py and its notes
    ("the incumbent guard... its threshold comparison is already correct for
    the crossing case; what does not exist is any commit at which it runs"),
    is that ``check-file-size`` has NO entry in
    templates/scripts/commit_guardian/commit_guardian.json's
    ``hooks_manifest.hooks`` -- confirmed absent in this worktree at
    authoring time, despite templates/scripts/commit_guardian/README.md
    line 41 already documenting it as a live "Blocking" gate. Because
    ``.pre-commit-config.yaml`` is generated FROM ``hooks_manifest.hooks``,
    the built config carries no entry for this gate either, and an ORDINARY
    commit -- one routed through the real pre-commit hook-execution engine,
    which is what git actually invokes -- never calls check_file_size.py at
    all, regardless of how oversized the staged file is.

EXERCISE STRATEGY -- WHY THIS DIFFERS FROM THE SIBLING RATCHET TESTS IN THIS
    SAME DIRECTORY (test_ge_127b_1.py): that file's population (the
    already-oversized-file ratchet) genuinely does not exist in the script
    yet, so direct invocation is a valid red baseline for it. This AC's
    population (the crossing case) already has correct logic, so the only
    way to observe the real, currently-missing behaviour -- "an ordinary
    commit is refused" -- is to invoke the REAL commit-time entry point: the
    ``pre-commit`` CLI itself, running against the REAL, currently-built
    ``.pre-commit-config.yaml``, in a repository seeded by a REAL
    ``build.py`` deploy. This is a stronger, not a weaker, standard than the
    sibling tests' direct-script-invocation idiom: it is the actual
    mechanism a real `git commit` triggers once hooks are installed, and it
    is blind to source-tree fixes that were never rebuilt or never
    registered -- exactly the two failure modes GE-127a-1's own constraints
    warn about.

    Per CLAUDE.md "Gate / Workflow ACs -- Verify Behaviorally, Not by Grep"
    and this AC's own doc_link ("If a criterion here is satisfiable by
    inspecting a registration surface rather than by attempting a commit, it
    has been mis-decomposed"), this file never reads commit_guardian.json's
    hooks_manifest to check for the id's presence -- every assertion is made
    by running ``pre-commit run check-file-size`` (no ``--all-files``, no
    ``--files`` -- the default scope is the currently staged files, which is
    exactly what an ordinary `git commit` presents) against a REAL git
    repository seeded from a REAL ``build.py`` output, and reading the real
    process exit code and combined stdout/stderr.

    ``pre-commit run check-file-size`` is chosen over a full
    ``pre-commit run --all-files`` / real ``git commit`` round-trip because
    this worktree has an unrelated, pre-existing ``check-build-drift``
    failure when ``build.py``'s own output is used as a *nested* build
    target (a known self-hosting artefact of building into an isolated temp
    dir, unrelated to file-size at all) -- running the full hook suite would
    make every descriptor here permanently red for a reason that has nothing
    to do with this AC, and would stay red even after python-coder's fix.
    Targeting the hook by its registered id runs the REAL pre-commit
    hook-execution engine against the REAL deployed config for THIS gate
    specifically, without that collateral failure, and is confirmed in this
    worktree to already produce "No hook with id `check-file-size` in stage
    `pre-commit`" today for this exact reason -- the reason itself IS the
    defect being tested.

    ``build.py`` is invoked ONCE per test module (setUpModule), and each
    test copies that shared deployed tree into its own fresh temp dir before
    ``git init`` -- avoids five separate ~10-20s ``build.py`` runs while
    still exercising a REAL deploy for every descriptor (mirrors the intent
    of test_ge_127b_1.py's per-test ``build.py`` call, adapted for this
    file's heavier per-test git/pre-commit setup).

DECISION HISTORY
- 2026-09-07 [GE-127a-1/test-writer]: Initial authoring of all five RED test
    stubs per GE-127a-1's test_spec. Verified RED via
    `python -m unittest discover -s unit_tests/commit_guardian -t . -p
    "test_ge_127a_1.py"` -- see the test-writer sign-off comment on the
    ticket for the exact captured failures.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_CHECK_FILE_SIZE = _COMMIT_GUARDIAN_DIR / "check_file_size.py"
_BUILD_PY = _REPO_ROOT / "scripts" / "build.py"
_CONFIG_PATH = _COMMIT_GUARDIAN_DIR / "commit_guardian.json"

_PYTHON = sys.executable
_SUBPROCESS_TIMEOUT_SECONDS = 60
_BUILD_TIMEOUT_SECONDS = 180

# Read the REAL per-extension limit from the real config, rather than
# hardcoding a number that could silently drift out of sync with it.
_CONFIG = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
_PY_LIMIT = _CONFIG["file_size"]["line_limits"][".py"]

# ---------------------------------------------------------------------------
# Module-level shared deploy: build ONCE, copy per test (see module docstring).
# ---------------------------------------------------------------------------

_SHARED_BUILD_DIR: Path | None = None


def setUpModule() -> None:  # noqa: N802 -- unittest module-level hook name
    """Build the project once into a shared temp dir for every test to copy."""
    global _SHARED_BUILD_DIR
    base = Path(tempfile.mkdtemp(prefix="ge127a1_build_"))
    result = subprocess.run(
        [_PYTHON, str(_BUILD_PY), "--target-dir", str(base)],
        capture_output=True,
        text=True,
        timeout=_BUILD_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        shutil.rmtree(base, ignore_errors=True)
        raise RuntimeError(
            f"build.py itself failed during setUpModule: "
            f"stdout={result.stdout} stderr={result.stderr}"
        )
    _SHARED_BUILD_DIR = base


def tearDownModule() -> None:  # noqa: N802 -- unittest module-level hook name
    """Remove the shared build output after every test in this module has run."""
    if _SHARED_BUILD_DIR is not None:
        shutil.rmtree(_SHARED_BUILD_DIR, ignore_errors=True)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    """Run a real git command in *cwd*."""
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        check=check,
    )


def _init_repo(root: Path) -> None:
    """Initialize a real git repository with a deterministic committer identity."""
    _git(["init", "-q"], root)
    _git(["config", "user.email", "test-writer@example.com"], root)
    _git(["config", "user.name", "GE-127a-1 test fixture"], root)


def _commit_all(root: Path, message: str) -> None:
    """Stage everything and make a real commit."""
    _git(["add", "-A"], root)
    _git(["commit", "-q", "-m", message], root)


def _stage_all(root: Path) -> None:
    """Stage everything without committing."""
    _git(["add", "-A"], root)


def _content(n_lines: int, tag: str = "v") -> str:
    """Build deterministic, docstring-free plain-text file content counting as n_lines."""
    return "\n".join(f"{tag}_{i:06d} = {i}" for i in range(n_lines)) + "\n"


def _fresh_deployed_repo() -> Path:
    """Copy the shared build.py output into a fresh temp dir and return its path.

    Returns:
        Path to a new directory containing a full, real ``build.py`` deploy
        (including the currently-generated ``.pre-commit-config.yaml``),
        not yet a git repository.
    """
    assert _SHARED_BUILD_DIR is not None, "setUpModule must run before any test"
    dst = Path(tempfile.mkdtemp(prefix="ge127a1_repo_"))
    shutil.copytree(_SHARED_BUILD_DIR, dst, dirs_exist_ok=True)
    return dst


def _run_registered_hook(cwd: Path) -> subprocess.CompletedProcess:
    """Invoke the REAL pre-commit CLI, targeting the ``check-file-size`` hook
    id, against the REAL deployed ``.pre-commit-config.yaml`` in *cwd*.

    No ``--files``/``--all-files`` flag is passed -- the default scope is the
    currently staged files, which is exactly what an ordinary `git commit`
    presents to its installed hooks. This is the REAL production entry point
    an ordinary commit invokes; it is NOT a source-grep or a
    hooks_manifest-JSON read.

    Args:
        cwd: A real git repository seeded from a real ``build.py`` deploy.

    Returns:
        The completed pre-commit process.
    """
    return subprocess.run(
        ["pre-commit", "run", "check-file-size"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def _run_direct(cwd: Path) -> subprocess.CompletedProcess:
    """Invoke check_file_size.py directly (bypassing pre-commit entirely).

    Used only as a fixture-sanity / contrast check -- this already succeeds
    today (see module docstring) and is never the primary red assertion in
    this file.
    """
    return subprocess.run(
        [_PYTHON, str(_CHECK_FILE_SIZE)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


class DeployedRepoTestCase(unittest.TestCase):
    """Shared per-test scaffolding: a fresh copy of the shared deploy, as a real git repo."""

    def setUp(self) -> None:
        self.root = _fresh_deployed_repo()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        _init_repo(self.root)
        # Establish the deployed tree itself as HEAD, so later commits are
        # ordinary incremental commits, not the repo's very first commit.
        _commit_all(self.root, "initial deploy")


# ---------------------------------------------------------------------------
# 1. The crossing case names both the file and both lengths
# ---------------------------------------------------------------------------


class TestCrossingFileRefusesCommitNamingBothLengths(DeployedRepoTestCase):
    def test_ge_127a_1_a_change_taking_a_file_over_its_limit_refuses_the_commit_naming_both_lengths(self):
        # covers: GE-127a-1
        # covers: GE-127a
        # angle: criterion
        """THE RED BASELINE FOR THE WHOLE TREE. A covered file below its
        permitted length, committed to HEAD, then staged so it now exceeds
        its permitted length, must be refused at an ORDINARY commit -- and
        the outcome must name the file, the length the standard measured it
        at, and the length permitted for its kind.

        RED TODAY: check-file-size has no entry in
        commit_guardian.json's hooks_manifest.hooks, so the REAL, currently
        built .pre-commit-config.yaml carries no such hook, and
        `pre-commit run check-file-size` reports "No hook with id
        `check-file-size`" rather than ever executing the gate -- nothing
        about the file, its measured length, or its permitted length is
        ever printed, and the run's failure has nothing to do with file
        size. Confirmed in this worktree at authoring time.
        """
        before = 50
        after = _PY_LIMIT + 50
        big = self.root / "oversized_probe.py"
        big.write_text(_content(before), encoding="utf-8")
        _commit_all(self.root, "establish under-limit file")

        big.write_text(_content(after), encoding="utf-8")
        _stage_all(self.root)

        result = _run_registered_hook(self.root)

        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "An ordinary commit that takes a covered file from under to "
                f"over its limit must be refused. stdout={result.stdout!r} "
                f"stderr={result.stderr!r}"
            ),
        )
        combined = result.stdout + result.stderr
        self.assertIn("oversized_probe.py", combined, msg=f"Outcome must name the file. Got: {combined!r}")
        self.assertIn(
            str(after),
            combined,
            msg=f"Outcome must state the length the standard measured ({after}). Got: {combined!r}",
        )
        self.assertIn(
            str(_PY_LIMIT),
            combined,
            msg=f"Outcome must state the permitted length ({_PY_LIMIT}). Got: {combined!r}",
        )


# ---------------------------------------------------------------------------
# 2. The silence arm -- a file that stays under its limit is not reported
# ---------------------------------------------------------------------------


class TestUnderLimitFileProducesNoLengthOutput(DeployedRepoTestCase):
    def test_ge_127a_1_a_file_left_under_its_limit_produces_no_output_about_its_length(self):
        # covers: GE-127a-1
        # angle: criterion
        """A staged change leaving a covered file still below its permitted
        length must commit cleanly and produce no warning, no note, and no
        refusal naming that file.

        NAMED MUTATION (BA's injection 1, per the AC -- to be executed by
        python-coder/pr-reviewer against the real implementation once it
        exists, per this AC's test_rationale): change the length comparison
        so a file at or below its permitted length is refused alongside one
        above it. Under that injection this descriptor must go RED, failing
        BY THE COMMIT OUTCOME (a non-zero exit) as well as by the text, and
        must return to green on revert. The injection can only turn this
        descriptor red once the gate genuinely runs at commit time -- which
        is exactly why this descriptor is ALSO red today for the
        registration reason documented in the module docstring, rather than
        vacuously green the way a direct-invocation test of this same clause
        would be.

        RED TODAY: `pre-commit run check-file-size` reports "No hook with
        id `check-file-size`" and exits non-zero regardless of the staged
        content -- an under-limit-only commit is refused today for a reason
        that has nothing to do with its length, which is exactly as wrong as
        refusing it for being oversized. This descriptor is only correctly
        green once the gate is BOTH registered AND correctly silent on this
        input.
        """
        small = self.root / "small_probe.py"
        small.write_text(_content(50), encoding="utf-8")
        _commit_all(self.root, "establish under-limit file")

        small.write_text(_content(60), encoding="utf-8")
        _stage_all(self.root)

        result = _run_registered_hook(self.root)

        self.assertEqual(
            0,
            result.returncode,
            msg=(
                "A commit that leaves a covered file under its limit must "
                f"complete cleanly. stdout={result.stdout!r} stderr={result.stderr!r}"
            ),
        )
        combined = result.stdout + result.stderr
        self.assertNotIn(
            "small_probe.py",
            combined.split("PASSED", 1)[0] if "PASSED" in combined else combined,
            msg=(
                "An under-limit file must not be named in any refusal/warning "
                f"context. Got: {combined!r}"
            ),
        )


# ---------------------------------------------------------------------------
# 3. First-offender-only -- a compliant file in the same commit is silent
# ---------------------------------------------------------------------------


class TestOnlyOverLimitFileIsNamedAlongsideCompliantFile(DeployedRepoTestCase):
    def test_ge_127a_1_only_the_over_limit_file_is_named_when_a_compliant_file_is_in_the_same_commit(self):
        # covers: GE-127a-1
        # angle: seam
        """A commit staging one over-limit covered file and one comfortably
        compliant covered file must be refused, and the reported offender
        must be the first file only -- the compliant file's presence neither
        excuses the offender nor is itself reported as a problem.

        NAMED MUTATION (BA's injection 2, per the AC): include every staged
        file of a covered kind in the reported set regardless of its
        measured length. Under that injection this descriptor must go RED
        naming the compliant second file, and return to green on revert.

        RED TODAY: `pre-commit run check-file-size` reports "No hook with
        id `check-file-size`" regardless of the staged content -- neither
        file's length is ever compared, so the assertion that ONLY the
        offender is named cannot yet be satisfied by anything the gate
        actually does at commit time.
        """
        offender = self.root / "big_probe.py"
        compliant = self.root / "small_probe.py"
        offender.write_text(_content(50), encoding="utf-8")
        compliant.write_text(_content(50), encoding="utf-8")
        _commit_all(self.root, "establish two under-limit files")

        offender.write_text(_content(_PY_LIMIT + 50), encoding="utf-8")
        compliant.write_text(_content(60), encoding="utf-8")
        _stage_all(self.root)

        result = _run_registered_hook(self.root)

        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "A commit with one over-limit covered file must be refused, "
                f"even alongside a compliant one. stdout={result.stdout!r} "
                f"stderr={result.stderr!r}"
            ),
        )
        combined = result.stdout + result.stderr
        self.assertIn("big_probe.py", combined, msg=f"The offender must be named. Got: {combined!r}")
        failure_section = combined.split("PASSED", 1)[0] if "PASSED" in combined else combined
        self.assertNotIn(
            "small_probe.py",
            failure_section,
            msg=(
                "The compliant file must not appear as a reported problem "
                f"alongside the offender. Got: {combined!r}"
            ),
        )


# ---------------------------------------------------------------------------
# 4. Reachability -- contrasting direct invocation against the registered path
# ---------------------------------------------------------------------------


class TestRefusalReachesRegisteredHookEntryPoint(DeployedRepoTestCase):
    def test_ge_127a_1_the_refusal_is_emitted_through_the_registered_hook_entry_point(self):
        # covers: GE-127a-1
        # angle: reachability
        """PRODUCTION ENTRY POINT, PROVED BY CONTRAST. The SAME crossing
        scenario is run two ways: (a) invoking check_file_size.py directly,
        and (b) through the real, registered pre-commit hook path. A verdict
        computed by a function nothing at commit time calls is inert -- this
        is the defect this whole tree exists to close, and the two-way
        contrast is what makes it visible: (a) already succeeds today
        (proving the comparison logic itself is not the problem), while (b)
        does not (proving the entry point is).

        RED TODAY: (a) already refuses (exit != 0) -- this is a
        fixture-sanity assertion, not the primary signal. (b) does not
        reach the gate at all ("No hook with id `check-file-size`"), so the
        assertion that (b) ALSO refuses, naming the file, is what fails.
        """
        before = 50
        after = _PY_LIMIT + 50
        big = self.root / "oversized_probe.py"
        big.write_text(_content(before), encoding="utf-8")
        _commit_all(self.root, "establish under-limit file")

        big.write_text(_content(after), encoding="utf-8")
        _stage_all(self.root)

        direct_result = _run_direct(self.root)
        self.assertNotEqual(
            0,
            direct_result.returncode,
            msg=(
                "Fixture sanity: direct invocation of check_file_size.py "
                "must already refuse this crossing case (the comparison "
                f"logic is not what this record is red for). Got: "
                f"stdout={direct_result.stdout!r} stderr={direct_result.stderr!r}"
            ),
        )

        registered_result = _run_registered_hook(self.root)
        self.assertNotEqual(
            0,
            registered_result.returncode,
            msg=(
                "The SAME crossing case must ALSO be refused through the "
                "real, registered pre-commit hook path -- a verdict only "
                "the direct invocation can produce is inert at an ordinary "
                f"commit. stdout={registered_result.stdout!r} "
                f"stderr={registered_result.stderr!r}"
            ),
        )
        combined = registered_result.stdout + registered_result.stderr
        self.assertIn(
            "oversized_probe.py",
            combined,
            msg=f"The registered path's own output must name the file. Got: {combined!r}",
        )


# ---------------------------------------------------------------------------
# 5. Deployed -- the cold, freshly-built copy refuses the crossing commit
# ---------------------------------------------------------------------------


class TestDeployedCopyRefusesCrossingCommitInColdProcess(DeployedRepoTestCase):
    def test_ge_127a_1_the_deployed_copy_refuses_the_crossing_commit_in_a_cold_process(self):
        # covers: GE-127a-1
        # angle: deployed
        """After a REAL build.py deploy, in a cold process, over a REAL git
        repository seeded from that deploy: a crossing commit must be
        refused through the deployed, registered hook path, and the deployed
        script and every module it imports must load without
        ModuleNotFoundError. Source-tree greenness cannot substitute here --
        this repo is built fresh from the shared setUpModule deploy, never
        the source tree directly.

        RED TODAY: the deployed `.pre-commit-config.yaml` is generated from
        the SAME source hooks_manifest.hooks that lacks a `check-file-size`
        entry, so the deployed copy is exactly as unreachable at an ordinary
        commit as the source tree's would be. Confirmed in this worktree
        at authoring time: `pre-commit run check-file-size` in the deployed,
        cold repo reports "No hook with id `check-file-size`".
        """
        deployed_check = self.root / "scripts" / "commit_guardian" / "check_file_size.py"
        self.assertTrue(
            deployed_check.exists(),
            msg=f"{deployed_check} was not deployed by build.py.",
        )

        before = 50
        after = _PY_LIMIT + 50
        big = self.root / "oversized_probe.py"
        big.write_text(_content(before), encoding="utf-8")
        _commit_all(self.root, "establish under-limit file")

        big.write_text(_content(after), encoding="utf-8")
        _stage_all(self.root)

        result = _run_registered_hook(self.root)

        combined = result.stdout + result.stderr
        self.assertNotIn(
            "ModuleNotFoundError",
            combined,
            msg=f"Deployed check-file-size crashed importing a dependency. Got: {combined!r}",
        )
        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "The deployed, cold-process copy must refuse a crossing "
                f"commit through the registered hook path. stdout={result.stdout!r} "
                f"stderr={result.stderr!r}"
            ),
        )
        self.assertIn("oversized_probe.py", combined, msg=f"Outcome must name the file. Got: {combined!r}")


if __name__ == "__main__":
    unittest.main()
