"""
MODULE: unit_tests/ac_driven_dev/test_acd_2100a_2.py
GOAL: RED integration tests for ACD-2100a-2 -- "The setup step finds the
    repository it operates on even when the script itself lives outside it."

BUSINESS CONTEXT: ``_git_toplevel()`` in
    templates/scripts/setup_ticket_worktree.py resolves the repository it
    operates on by anchoring on ``Path(__file__).resolve().parent`` with no
    fallback. When the script's own directory is not inside any git
    repository (the deployed-copy layout under self-hosting, or any consumer
    layout where the script has been copied out of the repo it targets), that
    anchor call fails and the whole setup step crashes -- even when the
    intended target repository is unambiguously discoverable one level below
    the current working directory. This AC requires a bounded fallback: when
    the anchor yields no repository, search the *immediate* subdirectories of
    the starting directory; if exactly one of them is a git repository,
    resolve to it, use it to create the requested worktree, and announce on
    stderr that the selection came from a search rather than from the
    script's own location. An explicit caller-supplied repository location
    must bypass both the anchor and the search entirely.

WHY THESE TESTS ARE BUILT THE WAY THEY ARE (see AC test_rationale, and
    docs/reference/fixture-policy.md): the pre-existing tests for this script
    invoke it from a tmp_path fixture that IS itself a git repository, so the
    default anchor always resolves and the fallback path is never exercised.
    Reusing that fixture shape here would prove nothing. Instead, every test
    below constructs a directory that is genuinely NOT a git repository (no
    repository among its ancestors either -- these live under the system tmp
    root, well outside this checkout), copies the real
    templates/scripts/setup_ticket_worktree.py source into a location outside
    the target repository, and invokes it as a real subprocess with real
    argv (never by importing an internal resolver function) so the
    reachability claim is genuine: an imported resolver can be correct while
    the command-line entry point still crashes on __file__-anchoring.

REAL-ARTIFACT BEHAVIORAL COVERAGE (CLAUDE.md "Real-artifact behavioral
    spot-check", BP-1100f-2): no part of git or the subprocess is mocked.
    Every fixture repository is created with real `git init`/`git commit`,
    the script under test is invoked as a real child process, and the
    resulting worktree is verified to exist by asking the *candidate
    repository itself* (`git worktree list --porcelain`) whether it knows
    about it -- not by inspecting call args or trusting the JSON payload
    alone.

INTERFACE CONTRACT ASSUMED BY THESE TESTS (not yet implemented -- this is
    the target the coder phase must satisfy): the ``create-only`` subcommand
    gains an optional ``--repo-root <path>`` flag (matching the
    ``--repo-root`` naming convention already used across this repo's other
    scripts, e.g. glossary_bootstrap.py, run_ci_local.py,
    check_component_vocab.py) that supplies an explicit repository location.
    When present, it must be used verbatim -- no anchor probe, no search, no
    stderr search announcement.

TICKET: 02_TICKET-20260826-ACD-2100a-2.md
COVERS: ACD-2100a-2
"""

from __future__ import annotations

import json
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
    """Initialise a real, minimally-bootstrappable git repository at *repo_dir*.

    Includes a ``.pre-commit-config.yaml`` placeholder so that
    ``_establish_pre_commit_config``'s idempotent no-op guard fires
    immediately (the fixture repo has no ``.leafcutter/`` build output, and
    without this file the real ``_bootstrap()`` AC-5 safety net would raise
    ``BootstrapError`` for a reason unrelated to what this ticket tests).
    """
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

    *dest_dir* must not itself be, or be inside, a git repository -- that is
    the whole point of the AC (the script's own location no longer anchors
    the resolution).
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "setup_ticket_worktree.py"
    shutil.copy(_SCRIPT_SRC, dest)
    return dest


def _worktree_registered(repo_dir: Path, worktree_path: Path) -> bool:
    """Return True iff *repo_dir*'s own git metadata knows about *worktree_path*.

    Verified by asking the candidate repository itself via
    ``git worktree list --porcelain`` rather than trusting the script's JSON
    payload or the mere existence of a directory on disk.
    """
    result = _run_git(["worktree", "list", "--porcelain"], repo_dir)
    target = str(worktree_path.resolve())
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            registered = str(Path(line[len("worktree "):]).resolve())
            if registered == target:
                return True
    return False


class _IsolatedNonRepoScenarioTestCase(unittest.TestCase):
    """Shared setUp: a real, non-repository base directory under system tmp."""

    def setUp(self) -> None:
        self._base_dir = Path(tempfile.mkdtemp(prefix="acd2100a2-"))
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

    def _run_script(self, args: list[str], cwd: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(self._script_copy), *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )


class TestRepositoryResolvedBySearchWhenScriptLivesOutsideAnyRepo(_IsolatedNonRepoScenarioTestCase):
    """AC-1/AC-2/AC-3: exactly one candidate repo among immediate subdirs;
    the step resolves to it and the requested worktree lands on disk under it."""

    def setUp(self) -> None:
        super().setUp()
        # AC-1's Given: exactly one git repository among the immediate
        # subdirectories of the (non-repository) starting directory.
        self._repo_dir = self._base_dir / "the-only-candidate-repo"
        _init_repo(self._repo_dir)
        # The script itself lives outside the repo it operates on -- copied
        # into a sibling, non-repository directory.
        self._script_copy = _copy_script_outside(self._base_dir / "script-location")

    def test_repository_resolved_by_search_when_script_lives_outside_any_repo(self):
        # covers: ACD-2100a-2
        """AC-1/AC-2/AC-3: resolves to the one candidate repo; worktree exists on disk under it.

        Invokes ``create-only`` from the non-repository *base_dir* with no
        explicit repository location supplied. The current implementation
        anchors _git_toplevel() on the script's own (non-repository)
        directory with no fallback, so this call is expected to fail (RED)
        until the search fallback is implemented.
        """
        result = self._run_script(
            ["create-only", "acd2100a2-search-branch"],
            cwd=self._base_dir,
        )

        self.assertEqual(
            result.returncode,
            0,
            f"expected success once the search fallback resolves the one "
            f"candidate repo; stdout={result.stdout!r} stderr={result.stderr!r}",
        )

        payload = json.loads(result.stdout)
        worktree_path = Path(payload["worktree_path"])
        self.assertTrue(
            worktree_path.exists(),
            f"worktree_path {worktree_path} reported by the script does not exist on disk",
        )
        self.assertTrue(
            _worktree_registered(self._repo_dir, worktree_path),
            f"the resolved repository {self._repo_dir} does not list "
            f"{worktree_path} among its own registered worktrees -- the "
            "worktree was not actually created under the repository the "
            "search should have selected",
        )


class TestSetupStepResolvesFromItsRealCommandLineEntryPoint(_IsolatedNonRepoScenarioTestCase):
    """AC-2/AC-3 (reachability angle): exercised via the real CLI entry point,
    in a fresh subprocess, not by importing the resolver."""

    def setUp(self) -> None:
        super().setUp()
        self._repo_dir = self._base_dir / "the-only-candidate-repo"
        _init_repo(self._repo_dir)
        self._script_copy = _copy_script_outside(self._base_dir / "script-location")

    def test_setup_step_resolves_from_its_real_command_line_entry_point(self):
        # covers: ACD-2100a-2
        """AC-2/AC-3: the script's own CLI entry point (subprocess, real argv) exits 0.

        Deliberately does NOT import any resolver function -- per the AC's
        test_rationale, an imported resolver can be correct while the
        command-line path still anchors on __file__ and crashes. Only a
        subprocess invocation of the real entry point proves reachability.
        """
        result = self._run_script(
            ["create-only", "acd2100a2-reachability-branch"],
            cwd=self._base_dir,
        )

        self.assertEqual(
            result.returncode,
            0,
            "the real command-line entry point must exit successfully when "
            f"run from a non-repository cwd with exactly one candidate "
            f"repo among its immediate subdirectories; "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )


class TestSearchFallbackAnnouncesTheRepositoryItSelected(_IsolatedNonRepoScenarioTestCase):
    """AC-4: stderr names the selected repository and marks the selection as
    coming from a search rather than from the script's own location."""

    def setUp(self) -> None:
        super().setUp()
        self._repo_dir = self._base_dir / "the-only-candidate-repo"
        _init_repo(self._repo_dir)
        self._script_copy = _copy_script_outside(self._base_dir / "script-location")

    def test_search_fallback_announces_the_repository_it_selected(self):
        # covers: ACD-2100a-2
        """AC-4: the diagnostic stream names the repository and attributes it to a search.

        The AC text is explicit that a silent fallback is unacceptable: the
        message must (a) name the repository actually selected and (b) state
        that the selection came from a search, not from the script's own
        location -- so the two are distinguishable by a future operator
        debugging a wrong-repository incident.
        """
        result = self._run_script(
            ["create-only", "acd2100a2-announce-branch"],
            cwd=self._base_dir,
        )

        self.assertEqual(
            result.returncode,
            0,
            f"setup must succeed before its stderr announcement can be "
            f"checked; stdout={result.stdout!r} stderr={result.stderr!r}",
        )

        stderr_lower = result.stderr.lower()
        self.assertIn(
            str(self._repo_dir.resolve()).lower(),
            stderr_lower,
            "stderr must name the specific repository that was selected "
            f"({self._repo_dir}); got stderr={result.stderr!r}",
        )
        self.assertIn(
            "search",
            stderr_lower,
            "stderr must state that the selection came from a search "
            f"(not from the script's own location); got stderr={result.stderr!r}",
        )


class TestExplicitRepositoryLocationBypassesTheSearchUnchanged(_IsolatedNonRepoScenarioTestCase):
    """AC boundary: an explicit repository location wins outright, even when
    the search would find a different candidate, and emits no search
    announcement."""

    def setUp(self) -> None:
        super().setUp()
        # The candidate the (unused) search would find if it ran.
        self._wrong_repo_dir = self._base_dir / "the-search-would-find-this-one"
        _init_repo(self._wrong_repo_dir)

        # The repository explicitly supplied by the caller -- deliberately
        # NOT among base_dir's immediate subdirectories, so a passing test
        # can only mean the explicit value was honoured, never that the
        # search accidentally matched it too.
        explicit_parent = Path(tempfile.mkdtemp(prefix="acd2100a2-explicit-"))
        self.addCleanup(shutil.rmtree, explicit_parent, ignore_errors=True)
        self._explicit_repo_dir = explicit_parent / "explicit-repo"
        _init_repo(self._explicit_repo_dir)

        self._script_copy = _copy_script_outside(self._base_dir / "script-location")

    def test_explicit_repository_location_bypasses_the_search_unchanged(self):
        # covers: ACD-2100a-2
        """AC boundary: --repo-root wins over search; no search announcement is made.

        Assumes the interface contract documented in the module docstring:
        an optional ``--repo-root`` flag on the ``create-only`` subcommand.
        This flag does not exist yet, so this call is expected to fail (RED)
        with an argparse "unrecognized arguments" error until it is added.
        """
        result = self._run_script(
            [
                "create-only",
                "acd2100a2-explicit-branch",
                "--repo-root",
                str(self._explicit_repo_dir),
            ],
            cwd=self._base_dir,
        )

        self.assertEqual(
            result.returncode,
            0,
            "an explicit --repo-root must be honoured outright, bypassing "
            f"both the anchor and the search; stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )

        payload = json.loads(result.stdout)
        worktree_path = Path(payload["worktree_path"])

        self.assertTrue(
            _worktree_registered(self._explicit_repo_dir, worktree_path),
            f"the explicitly-supplied repository {self._explicit_repo_dir} "
            f"does not list {worktree_path} among its registered worktrees "
            "-- the explicit location was not honoured",
        )
        self.assertFalse(
            _worktree_registered(self._wrong_repo_dir, worktree_path),
            f"the worktree was created under {self._wrong_repo_dir}, the "
            "candidate the search would have found -- the explicit "
            "--repo-root value did not bypass the search as required",
        )
        self.assertNotIn(
            "search",
            result.stderr.lower(),
            "no search announcement should be emitted when an explicit "
            f"repository location is supplied; got stderr={result.stderr!r}",
        )


if __name__ == "__main__":
    unittest.main()
