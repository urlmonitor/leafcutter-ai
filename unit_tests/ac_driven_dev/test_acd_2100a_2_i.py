"""
MODULE: unit_tests/ac_driven_dev/test_acd_2100a_2_i.py
GOAL: RED integration tests for ACD-2100a-2-i -- "An ambiguous repository
    location stops the setup step instead of being guessed."

BUSINESS CONTEXT: ACD-2100a-2 added a bounded search fallback to
    ``_resolve_repository_with_search_fallback()`` in
    templates/scripts/setup_ticket_worktree.py: when the script's own
    directory does not anchor a git repository, it searches the immediate
    subdirectories of the current working directory for exactly one
    candidate. This record pins the *ambiguous* branch of that same
    contract: when the search finds two or more candidate repositories, the
    step must refuse rather than guess -- exit non-zero, name every
    candidate it found, state that it will not choose between them, and
    leave no branch and no directory behind in ANY candidate repository. The
    dangerous implementation this AC exists to rule out is a search that
    silently returns its first hit: the run succeeds, a worktree appears,
    and it is in the wrong project (AC test_rationale).

WHY THESE TESTS ARE BUILT THE WAY THEY ARE (see AC test_rationale and
    docs/reference/fixture-policy.md): every fixture below constructs a
    directory that is genuinely NOT a git repository (no repository among
    its ancestors either -- these live under the system tmp root, well
    outside this checkout), with TWO real, independently-committed git
    repositories among its immediate subdirectories, and copies the real
    templates/scripts/setup_ticket_worktree.py source into a location
    outside both of them. The step is invoked as a real subprocess with real
    argv (never by importing an internal resolver function), so the
    reachability claim is genuine and the no-residue claim is checked
    against the repositories' own git metadata, not against the script's
    stdout payload (which is never even produced on this path).

REAL-ARTIFACT BEHAVIORAL COVERAGE (CLAUDE.md "Real-artifact behavioral
    spot-check", BP-1100f-2): no part of git or the subprocess is mocked.
    Every fixture repository is created with real `git init`/`git commit`,
    the script under test is invoked as a real child process, and the
    "no residue" claim is verified by asking each candidate repository
    itself (`git worktree list --porcelain`, `git branch --list -a`, and a
    plain directory listing) whether anything changed -- not by trusting the
    absence of a JSON payload alone.

NOT YET IMPLEMENTED (this is the target the coder phase must satisfy):
    ``_resolve_repository_with_search_fallback()`` already raises
    ``subprocess.SubprocessError`` when the bounded search finds zero or
    more than one candidate, and ``main()`` already converts that into a
    clean non-zero exit -- so the exit-status and no-residue tests below may
    already be green (ACD-2100a-2's implementation happened to satisfy them
    as a side effect). The current refusal message enumerates the candidate
    count and the raw candidate list, but does NOT yet contain any phrase
    stating that the step will not choose between them (it says "need
    exactly 1", not a refusal-to-choose statement) -- AC-3 requires exactly
    that statement, so ``test_refusal_names_every_candidate_it_found`` is
    expected to be RED until the message is worded accordingly.

TICKET: 03_TICKET-20260826-ACD-2100a-2-i.md
COVERS: ACD-2100a-2-i
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup: unit_tests/ac_driven_dev/ is 2 levels below the repo root
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT_SRC = _REPO_ROOT / "templates" / "scripts" / "setup_ticket_worktree.py"

_SUBPROCESS_TIMEOUT_SECONDS = 30


# ---------------------------------------------------------------------------
# Fixture helpers -- real git, real files, no mocks (see module docstring).
# ---------------------------------------------------------------------------


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run a git command anchored at *cwd* and return the CompletedProcess."""
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def _init_repo(repo_dir: Path) -> None:
    """Initialise a real, independently-committed git repository at *repo_dir*."""
    repo_dir.mkdir(parents=True, exist_ok=True)
    _run_git(["init", "-b", "main"], repo_dir)
    _run_git(["config", "user.email", "test@example.com"], repo_dir)
    _run_git(["config", "user.name", "Test User"], repo_dir)
    (repo_dir / ".pre-commit-config.yaml").write_text("repos: []\n", encoding="utf-8")
    (repo_dir / "README.md").write_text("fixture repo\n", encoding="utf-8")
    _run_git(["add", "-A"], repo_dir)
    _run_git(["commit", "-m", "initial commit", "--no-gpg-sign"], repo_dir)


def _copy_script_outside(dest_dir: Path) -> Path:
    """Copy the real script under test into *dest_dir* and return its path.

    *dest_dir* must not itself be, or be inside, a git repository -- and it
    must not itself be one of the ambiguous candidates.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "setup_ticket_worktree.py"
    shutil.copy(_SCRIPT_SRC, dest)
    return dest


def _worktree_list_snapshot(repo_dir: Path) -> str:
    """Return the exact ``git worktree list --porcelain`` output for *repo_dir*."""
    return _run_git(["worktree", "list", "--porcelain"], repo_dir).stdout


def _branch_list_snapshot(repo_dir: Path) -> str:
    """Return the exact ``git branch --list -a`` output for *repo_dir*."""
    return _run_git(["branch", "--list", "-a"], repo_dir).stdout


def _top_level_entries(repo_dir: Path) -> set[str]:
    """Return the set of top-level directory-entry names inside *repo_dir*."""
    return {entry.name for entry in repo_dir.iterdir()}


class _AmbiguousTwoCandidateScenarioTestCase(unittest.TestCase):
    """Shared setUp: a non-repository base directory with TWO real,
    independent git repositories among its immediate subdirectories, plus a
    copy of the script under test living outside both of them.
    """

    def setUp(self) -> None:
        self._base_dir = Path(tempfile.mkdtemp(prefix="acd2100a2i-"))
        self.addCleanup(shutil.rmtree, self._base_dir, ignore_errors=True)

        # Sanity-check the Given: the base directory itself must not be
        # inside any git repository (no repo among its ancestors either).
        probe = subprocess.run(
            ["git", "-C", str(self._base_dir), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )
        if probe.returncode == 0:
            self.skipTest(
                f"Test environment invariant violated: {self._base_dir} "
                f"resolves to a git repository ({probe.stdout.strip()!r}); "
                "cannot construct the AC's Given (a genuinely non-repository "
                "starting directory)."
            )

        # AC's Given: two or more git repositories among the immediate
        # subdirectories of the (non-repository) starting directory.
        self._repo_a = self._base_dir / "candidate-repo-a"
        self._repo_b = self._base_dir / "candidate-repo-b"
        _init_repo(self._repo_a)
        _init_repo(self._repo_b)

        # The script itself lives outside both candidates -- copied into a
        # third, non-repository sibling directory.
        self._script_copy = _copy_script_outside(self._base_dir / "script-location")

        # Baseline snapshots taken BEFORE the setup step ever runs, so the
        # no-residue assertions can prove nothing changed, not merely that
        # nothing final-state looks unusual.
        self._before_worktrees = {
            "a": _worktree_list_snapshot(self._repo_a),
            "b": _worktree_list_snapshot(self._repo_b),
        }
        self._before_branches = {
            "a": _branch_list_snapshot(self._repo_a),
            "b": _branch_list_snapshot(self._repo_b),
        }
        self._before_entries = {
            "a": _top_level_entries(self._repo_a),
            "b": _top_level_entries(self._repo_b),
        }

    def _run_script(self, args: list[str], cwd: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(self._script_copy), *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )


class TestTwoCandidateRepositoriesRefuseAndCreateNothing(_AmbiguousTwoCandidateScenarioTestCase):
    """AC-2: two-or-more candidates -> non-zero exit, no worktree created
    under either candidate."""

    def test_two_candidate_repositories_refuse_and_create_nothing(self):
        # covers: ACD-2100a-2-i
        # angle: criterion
        """AC-2: the setup step exits non-zero and creates no worktree under
        either candidate repository when two candidates are found and no
        repository location was supplied by the caller."""
        result = self._run_script(
            ["create-only", "acd2100a2i-ambiguous-branch"],
            cwd=self._base_dir,
        )

        self.assertNotEqual(
            result.returncode,
            0,
            "an ambiguous (two-candidate) repository location must exit "
            f"with a failure status, not proceed by guessing; "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )

        # No worktree was registered against either candidate repository.
        after_a = _worktree_list_snapshot(self._repo_a)
        after_b = _worktree_list_snapshot(self._repo_b)
        self.assertEqual(
            after_a,
            self._before_worktrees["a"],
            f"candidate repo {self._repo_a} gained a registered worktree "
            "from an attempt that should have refused to choose",
        )
        self.assertEqual(
            after_b,
            self._before_worktrees["b"],
            f"candidate repo {self._repo_b} gained a registered worktree "
            "from an attempt that should have refused to choose",
        )


class TestRefusalNamesEveryCandidateItFound(_AmbiguousTwoCandidateScenarioTestCase):
    """AC-3: the failure output names every candidate found and states that
    the step will not choose between them."""

    def test_refusal_names_every_candidate_it_found(self):
        # covers: ACD-2100a-2-i
        # angle: criterion
        """AC-3: failure output contains both candidate locations and an
        explicit statement that the step will not choose between them.

        A bare 'could not determine the repository' is explicitly ruled out
        by the AC's it_requirements -- it sends the operator back to the
        same search by hand and is indistinguishable from a resolver that
        simply failed for an unrelated reason.
        """
        result = self._run_script(
            ["create-only", "acd2100a2i-naming-branch"],
            cwd=self._base_dir,
        )

        self.assertNotEqual(result.returncode, 0)

        combined_output = (result.stdout + result.stderr)
        combined_lower = combined_output.lower()

        self.assertIn(
            str(self._repo_a.resolve()).lower(),
            combined_lower,
            "the failure must name candidate repository A "
            f"({self._repo_a}); got output={combined_output!r}",
        )
        self.assertIn(
            str(self._repo_b.resolve()).lower(),
            combined_lower,
            "the failure must name candidate repository B "
            f"({self._repo_b}); got output={combined_output!r}",
        )
        self.assertIn(
            "not choose",
            combined_lower,
            "the failure must state that the step will not choose between "
            "the candidates it found (a bare candidate count or 'need "
            "exactly 1' is not a refusal-to-choose statement); "
            f"got output={combined_output!r}",
        )


class TestAmbiguousRefusalLeavesNoBranchInAnyCandidate(_AmbiguousTwoCandidateScenarioTestCase):
    """AC-4/failure angle: after the refusal, neither candidate repository
    gained a new branch or a new top-level directory entry."""

    def test_ambiguous_refusal_leaves_no_branch_in_any_candidate(self):
        # covers: ACD-2100a-2-i
        # angle: failure
        """AC-4: no branch and no directory is left behind in any candidate
        repository by the attempt.

        The no-residue claim is asserted independently of the exit code on
        purpose (per the AC's notes): an implementation that creates a
        branch in candidate A before discovering candidate B would still
        exit non-zero while leaving cleanup residue in a repository the
        operator never meant to touch.
        """
        result = self._run_script(
            ["create-only", "acd2100a2i-residue-branch"],
            cwd=self._base_dir,
        )

        self.assertNotEqual(result.returncode, 0)

        after_branches = {
            "a": _branch_list_snapshot(self._repo_a),
            "b": _branch_list_snapshot(self._repo_b),
        }
        after_entries = {
            "a": _top_level_entries(self._repo_a),
            "b": _top_level_entries(self._repo_b),
        }

        self.assertEqual(
            after_branches["a"],
            self._before_branches["a"],
            f"candidate repo {self._repo_a} has a different branch list "
            "after the refused attempt than it had before it",
        )
        self.assertEqual(
            after_branches["b"],
            self._before_branches["b"],
            f"candidate repo {self._repo_b} has a different branch list "
            "after the refused attempt than it had before it",
        )
        self.assertEqual(
            after_entries["a"],
            self._before_entries["a"],
            f"candidate repo {self._repo_a} gained or lost a top-level "
            "directory entry as a result of the refused attempt",
        )
        self.assertEqual(
            after_entries["b"],
            self._before_entries["b"],
            f"candidate repo {self._repo_b} gained or lost a top-level "
            "directory entry as a result of the refused attempt",
        )


class TestRefusalIsReachedThroughTheCommandLineEntryPoint(_AmbiguousTwoCandidateScenarioTestCase):
    """Reachability angle: the refusal is produced by the script's real
    command-line entry point in a fresh process, and its non-zero exit
    status is what the caller observes."""

    def test_refusal_is_reached_through_the_command_line_entry_point(self):
        # covers: ACD-2100a-2-i
        # angle: reachability
        """The refusal must be observable by a caller that only runs the
        script as a subprocess and inspects its exit status -- never by
        importing ``_resolve_repository_with_search_fallback`` (or any other
        internal resolver function) and calling it directly, which would
        prove nothing about whether the real CLI entry point (``main()``)
        actually surfaces the refusal instead of crashing with an uncaught
        traceback or exiting 0.
        """
        result = subprocess.run(
            [
                sys.executable,
                str(self._script_copy),
                "create-only",
                "acd2100a2i-reachability-branch",
            ],
            cwd=str(self._base_dir),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )

        self.assertNotEqual(
            result.returncode,
            0,
            "the real command-line entry point must exit with a failure "
            "status when run from a non-repository cwd with two candidate "
            f"repositories among its immediate subdirectories; "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        # A genuine subprocess exit status, not an uncaught Python traceback
        # masquerading as a non-zero exit for an unrelated reason (e.g. a
        # SyntaxError in the copied script).
        self.assertNotIn(
            "Traceback (most recent call last)",
            result.stderr,
            "the refusal must be a handled, reported failure -- not an "
            f"uncaught exception; got stderr={result.stderr!r}",
        )


if __name__ == "__main__":
    unittest.main()
