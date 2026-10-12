"""
MODULE: unit_tests/ac_driven_dev/test_acd_2100a_2_ii.py
GOAL: RED integration tests for ACD-2100a-2-ii -- "Every worktree-creating
    subcommand uses the same repository resolution, not just create-only."

BUSINESS CONTEXT: ACD-2100a-2 added ``_resolve_repository_with_search_fallback()``
    to templates/scripts/setup_ticket_worktree.py and wired it into
    ``cmd_create_only()`` ONLY. ``cmd_create_ac_worktree()`` (~line 1943) and
    ``cmd_create_fastlane_worktree()`` (~line 2043) still call the bare
    ``_git_toplevel()`` with no fallback, so both ``/plan-feature`` (AC
    authoring, Stage 0) and the fast lane's ``create-fastlane-worktree``
    crash with "Could not resolve a git repository from any candidate anchor"
    whenever the deployed copy of the script lives outside the repository it
    manages -- exactly the self-hosting dev layout where ``<repo>/.leafcutter``
    is a symlink to the untracked workspace parent (ADR-001). Reproduced
    2026-09-30 against origin/main ee47a88e.

WHY THESE TESTS ARE BUILT THE WAY THEY ARE (mirrors
    unit_tests/ac_driven_dev/test_acd_2100a_2.py's rationale, and
    docs/reference/fixture-policy.md): a tmp_path fixture that IS itself a
    git repository never exercises the fallback, because the default anchor
    always resolves. Every test below constructs a directory that is
    genuinely NOT a git repository (no repository among its ancestors
    either -- these live under the system tmp root), copies the real
    templates/scripts/setup_ticket_worktree.py source into a location outside
    the target repository, and invokes it as a real subprocess with real
    argv (never by importing an internal resolver function) so the
    reachability claim is genuine: an imported resolver can be correct while
    the command-line entry point for a given subcommand still anchors on
    __file__ and crashes.

REAL-ARTIFACT BEHAVIORAL COVERAGE (CLAUDE.md "Real-artifact behavioral
    spot-check", BP-1100f-2): no part of git or the subprocess is mocked.
    Every fixture repository is created with real `git init`/`git clone`/
    `git commit`, the script under test is invoked as a real child process,
    and the resulting worktree is verified to exist by asking the *candidate
    repository itself* (`git worktree list --porcelain`) whether it knows
    about it -- not by inspecting call args or trusting the JSON payload
    alone.

``cmd_create_ac_worktree()`` and ``cmd_create_fastlane_worktree()`` both root
their new branch at ``origin/main``, so every fixture repository here is a
real clone of a real "origin" repository (mirroring
unit_tests/build_orchestration/test_bo2400f_3_reconnect_stale_main_behavioral.py's
approach) rather than a bare `git init` -- a bare-init repo has no
`origin/main` ref and both subcommands would fail for an unrelated reason.

DISCRIMINATION (see the companion module
    test_acd_2100a_2_ii_more.py::TestSubcommandsFailWhenResolutionIsLeftAnchoredOnly):
    the cheapest passing implementation of this AC is a one-site substitution
    (fixing only ``cmd_create_ac_worktree`` OR only
    ``cmd_create_fastlane_worktree``, not both). A test that greps the file
    for ``_resolve_repository_with_search_fallback`` would pass on that
    half-fix, and even on a version where the helper is merely mentioned in
    a comment while the executed call is still the bare anchor. Running BOTH
    real command-line entry points in one assertion set is what closes that
    gap: fixing only one site leaves the other subcommand's subprocess exit
    non-zero, which that test catches directly.

MODULE SPLIT (check-file-size, GE-127a-1/b-1): this file and its companion
    test_acd_2100a_2_ii_more.py together cover ACD-2100a-2-ii. Both files
    exist purely to satisfy the repo's 400-line file-size gate -- they are
    not two ACs and do not use the "-i"/"-ii" AC-id suffix convention (see
    CLAUDE.md "AC-store commits") for their own naming; the companion module
    imports the shared fixture helpers and base test case defined below
    rather than redefining them, so there is exactly one implementation of
    each helper across the pair.

TICKET: (quick-fix; no ticket file -- authored directly against the AC)
COVERS: ACD-2100a-2-ii
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
# Shared with the companion module test_acd_2100a_2_ii_more.py via import.
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


def _init_repo_with_origin(repo_dir: Path, origin_parent: Path) -> Path:
    """Create *repo_dir* as a real clone of a fresh, real "origin" repository.

    Both ``cmd_create_ac_worktree`` and ``cmd_create_fastlane_worktree`` root
    their new branch at ``origin/main`` (unrelated to the AC ACD-2100a-2-ii
    defect itself), so a plain ``git init`` fixture -- sufficient for
    ``create-only`` -- is not sufficient here: it has no ``origin`` remote
    and no ``origin/main`` ref. Cloning from a real "origin" repository wires
    both up automatically, exactly mirroring
    unit_tests/build_orchestration/test_bo2400f_3_reconnect_stale_main_behavioral.py.

    Includes a ``.pre-commit-config.yaml`` placeholder so ``_bootstrap``'s
    AC-5 safety net is satisfied by the checked-out file, not because
    build.py ran (it doesn't, in this fixture).
    """
    origin_dir = origin_parent / f"{repo_dir.name}-origin"
    origin_dir.mkdir(parents=True, exist_ok=True)
    _run_git(["init", "-q", "-b", "main"], origin_dir)
    _run_git(["config", "user.email", "test@example.com"], origin_dir)
    _run_git(["config", "user.name", "Test User"], origin_dir)
    (origin_dir / ".pre-commit-config.yaml").write_text("repos: []\n", encoding="utf-8")
    (origin_dir / "README.md").write_text("fixture repo\n", encoding="utf-8")
    _run_git(["add", "-A"], origin_dir)
    _run_git(["commit", "-q", "-m", "initial commit", "--no-gpg-sign"], origin_dir)

    repo_dir.parent.mkdir(parents=True, exist_ok=True)
    _run_git(["clone", "-q", str(origin_dir), str(repo_dir)], repo_dir.parent)
    _run_git(["config", "user.email", "test@example.com"], repo_dir)
    _run_git(["config", "user.name", "Test User"], repo_dir)
    return repo_dir


def _copy_script_outside(dest_dir: Path) -> Path:
    """Copy the real script under test into *dest_dir* and return its path.

    *dest_dir* must not itself be, or be inside, a git repository -- that is
    the whole point of the AC (the script's own location no longer anchors
    the resolution, so the bounded search must run instead).
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "setup_ticket_worktree.py"
    shutil.copy(_SCRIPT_SRC, dest)
    return dest


def _copy_script_inside(repo_dir: Path) -> Path:
    """Copy the real script into a subdirectory of *repo_dir* itself.

    Used by the boundary test: when the script's own directory already
    resolves via the anchor (the dominant, pre-existing code path), the
    search must never run and no search announcement may be emitted.
    """
    dest_dir = repo_dir / "vendored-scripts"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "setup_ticket_worktree.py"
    shutil.copy(_SCRIPT_SRC, dest)
    return dest


def _parse_json_payload(stdout: str) -> dict:
    """Parse the script's JSON payload from *stdout*, tolerant of a leading leak.

    ``_create_ac_worktree`` and ``_create_fastlane_worktree`` invoke
    ``git worktree add`` (fresh-branch path) WITHOUT ``capture_output=True``,
    so git's own "branch '...' set up to track '...'." / "HEAD is now at ..."
    informational lines leak onto this script's stdout ahead of its own
    ``json.dumps(payload)`` line. That is a real, pre-existing, and separate
    defect from ACD-2100a-2-ii (which is only about repository resolution) --
    it is not this AC's fix target, so these tests must not fail on it.
    ``json.dumps`` is always the LAST line this script prints on success, so
    taking the last non-blank line is a faithful, minimal accommodation.
    """
    lines = [line for line in stdout.splitlines() if line.strip()]
    assert lines, f"expected at least one line of stdout containing JSON; got stdout={stdout!r}"
    return json.loads(lines[-1])


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
    """Shared setUp: a real, non-repository base directory under system tmp.

    Shared with the companion module test_acd_2100a_2_ii_more.py via import.
    """

    # Assigned dynamically in each subclass's own setUp() (never here in the
    # base class), but referenced by `_run_script` below -- declared here so
    # mypy recognises it as a real attribute of the base class rather than
    # reporting attr-defined.
    _script_copy: Path

    def setUp(self) -> None:
        self._base_dir = Path(tempfile.mkdtemp(prefix="acd2100a2ii-"))
        self.addCleanup(shutil.rmtree, self._base_dir, ignore_errors=True)

        self._origin_parent = Path(tempfile.mkdtemp(prefix="acd2100a2ii-origin-"))
        self.addCleanup(shutil.rmtree, self._origin_parent, ignore_errors=True)

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

    def _run_script(self, script_copy: Path, args: list[str], cwd: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(script_copy), *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )


class TestAcWorktreeSubcommandResolvesRepositoryBySearch(_IsolatedNonRepoScenarioTestCase):
    """test_spec: test_ac_worktree_subcommand_resolves_repository_by_search_when_script_lives_outside_any_repo"""

    def setUp(self) -> None:
        super().setUp()
        self._repo_dir = self._base_dir / "the-only-candidate-repo"
        _init_repo_with_origin(self._repo_dir, self._origin_parent)
        self._script_copy = _copy_script_outside(self._base_dir / "script-location")

    def test_ac_worktree_subcommand_resolves_repository_by_search_when_script_lives_outside_any_repo(self):
        # covers: ACD-2100a-2-ii
        # angle: criterion
        """AC: create-ac-worktree resolves the one candidate repo; the worktree exists under it.

        RED today: cmd_create_ac_worktree() calls the bare _git_toplevel()
        with no fallback, so this call fails with "Could not resolve a git
        repository from any candidate anchor" (the exact bug symptom) until
        the call site is switched to _resolve_repository_with_search_fallback().
        """
        result = self._run_script(
            self._script_copy,
            ["create-ac-worktree", "acd2100a2ii-ac-search-session"],
            cwd=self._base_dir,
        )

        self.assertEqual(
            result.returncode,
            0,
            f"expected success once create-ac-worktree resolves the one "
            f"candidate repo via the bounded search; stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )

        payload = _parse_json_payload(result.stdout)
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


class TestFastlaneWorktreeSubcommandResolvesRepositoryBySearch(_IsolatedNonRepoScenarioTestCase):
    """test_spec: test_fastlane_worktree_subcommand_resolves_repository_by_search_when_script_lives_outside_any_repo"""

    def setUp(self) -> None:
        super().setUp()
        self._repo_dir = self._base_dir / "the-only-candidate-repo"
        _init_repo_with_origin(self._repo_dir, self._origin_parent)
        self._script_copy = _copy_script_outside(self._base_dir / "script-location")

    def test_fastlane_worktree_subcommand_resolves_repository_by_search_when_script_lives_outside_any_repo(self):
        # covers: ACD-2100a-2-ii
        # angle: criterion
        """AC: create-fastlane-worktree resolves the one candidate repo; the worktree exists under it.

        RED today: cmd_create_fastlane_worktree() calls the bare
        _git_toplevel() with no fallback -- the identical hole named in the
        bug symptom's second sentence -- so this call fails until the call
        site is switched to _resolve_repository_with_search_fallback().
        """
        result = self._run_script(
            self._script_copy,
            ["create-fastlane-worktree", "acd2100a2ii-fl-search-slug"],
            cwd=self._base_dir,
        )

        self.assertEqual(
            result.returncode,
            0,
            f"expected success once create-fastlane-worktree resolves the "
            f"one candidate repo via the bounded search; "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )

        payload = _parse_json_payload(result.stdout)
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


class TestBothSubcommandsReachedThroughRealCommandLineEntryPoints(_IsolatedNonRepoScenarioTestCase):
    """test_spec: test_both_subcommands_reached_through_their_real_command_line_entry_points"""

    def setUp(self) -> None:
        super().setUp()
        self._repo_dir = self._base_dir / "the-only-candidate-repo"
        _init_repo_with_origin(self._repo_dir, self._origin_parent)
        self._script_copy = _copy_script_outside(self._base_dir / "script-location")

    def test_both_subcommands_reached_through_their_real_command_line_entry_points(self):
        # covers: ACD-2100a-2-ii
        # angle: reachability
        """AC (reachability): both subcommands' real CLI entry points exit 0.

        Deliberately does NOT import any resolver function -- per the AC's
        test_rationale, an imported resolver can be correct while the
        command-line path for a given subcommand still anchors on __file__
        and crashes. Only a subprocess invocation of each real entry point
        proves reachability, surface: "templates/scripts/setup_ticket_worktree.py
        invoked as a subprocess with real argv for the create-ac-worktree and
        create-fastlane-worktree subcommands".
        """
        result_ac = self._run_script(
            self._script_copy,
            ["create-ac-worktree", "acd2100a2ii-reach-ac"],
            cwd=self._base_dir,
        )
        self.assertEqual(
            result_ac.returncode,
            0,
            "the real create-ac-worktree command-line entry point must exit "
            f"successfully from a non-repository cwd with exactly one "
            f"candidate repo among its immediate subdirectories; "
            f"stdout={result_ac.stdout!r} stderr={result_ac.stderr!r}",
        )

        result_fl = self._run_script(
            self._script_copy,
            ["create-fastlane-worktree", "acd2100a2ii-reach-fl"],
            cwd=self._base_dir,
        )
        self.assertEqual(
            result_fl.returncode,
            0,
            "the real create-fastlane-worktree command-line entry point must "
            f"exit successfully from a non-repository cwd with exactly one "
            f"candidate repo among its immediate subdirectories; "
            f"stdout={result_fl.stdout!r} stderr={result_fl.stderr!r}",
        )


if __name__ == "__main__":
    unittest.main()
