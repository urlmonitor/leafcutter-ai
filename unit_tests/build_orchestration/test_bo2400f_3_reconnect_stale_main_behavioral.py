"""
MODULE: unit_tests/build_orchestration/test_bo2400f_3_reconnect_stale_main_behavioral.py
GOAL: RED behavioural tests for BO-2400f-3 — a fast-lane re-run whose
      worktree was pruned must rebuild from the LATEST origin/main, never
      from the stale local branch tip it left behind.

=== Live defect being pinned (docs/acceptance-criteria/build-orchestration/
    BO-2400-fast-lane-build/BO-2400f-3.yaml, work_status: todo,
    covered_by: []) ===

scripts/setup_ticket_worktree.py::_create_fastlane_worktree (mirrored in
templates/scripts/setup_ticket_worktree.py — confirmed byte-identical in this
region by direct diff) has two branches:

    branch_already_exists = _branch_exists(full_branch, repo_root)
    if branch_already_exists:
        # RECONNECT — defective:
        subprocess.run(["git", "-C", repo_root, "worktree", "add",
                        str(worktree_path), full_branch])   # NO start point!
    else:
        # FRESH — correct:
        subprocess.run(["git", "-C", repo_root, "worktree", "add", "-b",
                        full_branch, str(worktree_path), "origin/main"])

The reconnect branch passes no start point, so ``git worktree add <path>
<branch>`` simply checks out the branch at whatever commit it already points
to — the stale tip from the prior (now-pruned) run. Only the fresh-branch
`else` arm ever cuts from `origin/main`.

=== Why the existing coverage misses it ===

unit_tests/build_orchestration/test_fastlane_worktree_mode.py::
TestFastlaneWorktreeGitArgvShape.test_ac3_git_worktree_add_uses_fast_lane_branch_and_origin_main
is the only origin/main-related test for this function, and its mock
subprocess.run stubs `git branch --list` to ALWAYS return empty output —
literally commented "branch doesn't exist -> use -b form" (test file
line ~383). That forces every run through the `else` (fresh) arm; the
defective `if branch_already_exists:` arm is never entered by any test in
the suite. `BO-2400f-3.covered_by` is `[]` in the AC store, so the record was
never linked to that suite regardless.

=== Behavioural approach (not a mock) ===

Per the ticket's own instruction, this uses a REAL temporary git repository
rather than stubbing `_branch_exists` — the stub is precisely what hid the
defect. A real "origin" repo advances past the point where a stale local
branch was cut, the local repo fetches that advance, and the actual
`_create_fastlane_worktree` (no subprocess mocking at all) is invoked against
the real repo. The resulting worktree's on-disk HEAD and file content are
read back and compared against the real, current `origin/main` commit — a
real-artifact round-trip, not a call-args assertion.

=== Red baseline ===

RED today: the reconnect branch checks out the stale local `fast-lane/<slug>`
tip, so the resulting worktree's HEAD equals the OLD commit and lacks the
file introduced by the newer origin/main commit — not the new one.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

_IMPORT_OK = False
_IMPORT_ERR = ""
_create_fastlane_worktree = None  # type: ignore[assignment]
_branch_exists = None  # type: ignore[assignment]

try:
    from setup_ticket_worktree import (  # type: ignore[import]
        _branch_exists,
        _create_fastlane_worktree,
    )
    _IMPORT_OK = True
except (ImportError, ModuleNotFoundError) as _exc:
    _IMPORT_ERR = str(_exc)


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=True,
    )


def _init_repo_with_commit(path: Path, filename: str, content: str, message: str) -> str:
    """Create a real git repo at *path* on branch 'main' with one commit.

    Returns the new commit SHA.
    """
    path.mkdir(parents=True, exist_ok=True)
    _run_git(["init", "-q", "-b", "main"], path)
    _run_git(["config", "user.email", "red-baseline@example.com"], path)
    _run_git(["config", "user.name", "Red Baseline"], path)
    (path / filename).write_text(content, encoding="utf-8")
    _run_git(["add", filename], path)
    _run_git(["commit", "-q", "-m", message], path)
    return _run_git(["rev-parse", "HEAD"], path).stdout.strip()


def _add_commit(path: Path, filename: str, content: str, message: str) -> str:
    (path / filename).write_text(content, encoding="utf-8")
    _run_git(["add", filename], path)
    _run_git(["commit", "-q", "-m", message], path)
    return _run_git(["rev-parse", "HEAD"], path).stdout.strip()


@unittest.skipUnless(_IMPORT_OK, f"setup_ticket_worktree import failed: {_IMPORT_ERR}")
class TestReconnectRebuildsFromLatestOriginMain(unittest.TestCase):
    """BO-2400f-3: reconnecting a pruned fast-lane worktree must rebuild from
    the CURRENT origin/main, not the stale local branch tip left behind."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)

        # 1. A real "origin" repo, with an initial commit (the state the prior,
        #    now-pruned fast-lane run was cut from).
        self.origin = self.tmp_path / "origin"
        self.stale_sha = _init_repo_with_commit(
            self.origin, "README.md", "stale content\n", "initial commit"
        )

        # 2. A real local repo_root cloned from origin — this stands in for the
        #    main repo the fast-lane build operates from. Cloning wires up the
        #    'origin' remote and refs/remotes/origin/main automatically.
        self.repo_root = self.tmp_path / "repo_root"
        _run_git(
            ["clone", "-q", str(self.origin), str(self.repo_root)], self.tmp_path
        )
        _run_git(["config", "user.email", "red-baseline@example.com"], self.repo_root)
        _run_git(["config", "user.name", "Red Baseline"], self.repo_root)

        self.slug = "bo2400f3-red-baseline"
        self.full_branch = f"fast-lane/{self.slug}"

        # 3. Simulate the PRIOR fast-lane run: create the branch (rooted at the
        #    stale commit) and a real worktree for it, exactly as
        #    _create_fastlane_worktree's fresh-branch arm would have done.
        self.worktrees_dir = self.tmp_path / "worktrees"
        self.worktrees_dir.mkdir()
        prior_worktree_path = self.worktrees_dir / self.slug
        _run_git(
            ["worktree", "add", "-b", self.full_branch, str(prior_worktree_path), "main"],
            self.repo_root,
        )

        # 4. Simulate the worktree being PRUNED (the exact scenario BO-2400f-3
        #    describes): remove the worktree directory and prune its
        #    registration, but the branch ref itself survives — which is
        #    exactly what makes _branch_exists() return True on the next run.
        import shutil

        shutil.rmtree(prior_worktree_path)
        _run_git(["worktree", "prune"], self.repo_root)

        self.assertTrue(
            _branch_exists(self.full_branch, self.repo_root),
            "Test precondition failed: the branch must still exist locally after the "
            "worktree is pruned — this is exactly the branch-without-worktree scenario "
            "BO-2400f-3 is about. If this fails, the test setup itself is wrong.",
        )

        # 5. Advance the REAL origin past the point the stale branch was cut
        #    from — this is the "latest origin/main" the AC says a re-run must
        #    rebuild from.
        self.fresh_sha = _add_commit(
            self.origin, "NEW_FILE.txt", "fresh content from advanced origin/main\n",
            "advance origin/main past the stale fast-lane branch tip",
        )
        self.assertNotEqual(
            self.stale_sha, self.fresh_sha,
            "Test precondition failed: origin must have moved.",
        )

        # 6. Fetch in repo_root, exactly as cmd_create_fastlane_worktree's
        #    caller-level _fetch_origin(main_repo) does before ever calling
        #    _create_fastlane_worktree. After this, refs/remotes/origin/main
        #    points at fresh_sha while the local fast-lane/<slug> branch still
        #    points at stale_sha — the precise divergence BO-2400f-3 exists to
        #    close.
        _run_git(["fetch", "-q", "origin"], self.repo_root)
        origin_main_sha = _run_git(
            ["rev-parse", "origin/main"], self.repo_root
        ).stdout.strip()
        self.assertEqual(
            origin_main_sha, self.fresh_sha,
            "Test precondition failed: repo_root's origin/main ref did not advance.",
        )
        branch_tip_sha = _run_git(
            ["rev-parse", self.full_branch], self.repo_root
        ).stdout.strip()
        self.assertEqual(
            branch_tip_sha, self.stale_sha,
            "Test precondition failed: the local fast-lane branch must still be at the "
            "stale commit before reconnecting — otherwise this test cannot distinguish "
            "'rebuilt from origin/main' from 'happened to already be there'.",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ac_bo2400f3_reconnected_worktree_head_matches_latest_origin_main(self) -> None:
        # covers: BO-2400f-3
        """After reconnecting a pruned-but-branched fast-lane worktree, the
        resulting worktree's HEAD must equal the CURRENT origin/main commit —
        not the stale branch tip the prior run left behind.

        RED today: _create_fastlane_worktree's reconnect arm runs
        `git worktree add <path> <branch>` with no start point, so it checks
        out the branch at its existing (stale) tip. HEAD in the resulting
        worktree equals stale_sha, not fresh_sha.
        """
        new_worktree_path = _create_fastlane_worktree(
            self.slug, self.worktrees_dir, self.repo_root
        )

        self.assertTrue(
            new_worktree_path.exists(),
            f"_create_fastlane_worktree must produce a real worktree directory on disk. "
            f"Got: {new_worktree_path}",
        )

        actual_head = _run_git(["rev-parse", "HEAD"], new_worktree_path).stdout.strip()

        self.assertEqual(
            actual_head,
            self.fresh_sha,
            "A reconnected fast-lane worktree must rebuild from the LATEST origin/main "
            f"({self.fresh_sha}), not the stale local branch tip ({self.stale_sha}) it "
            f"was left pointing at when its previous worktree was pruned. "
            f"Actual worktree HEAD: {actual_head}.",
        )

    def test_ac_bo2400f3_reconnected_worktree_contains_the_newer_origin_file(self) -> None:
        # covers: BO-2400f-3
        """Real-artifact round-trip: the file introduced by the newer
        origin/main commit must actually be present and readable on disk in
        the reconnected worktree — not merely inferrable from a SHA.

        RED today: because the reconnect arm checks out the stale branch tip,
        NEW_FILE.txt (introduced only in the newer origin/main commit) is
        absent from the resulting worktree.
        """
        new_worktree_path = _create_fastlane_worktree(
            self.slug, self.worktrees_dir, self.repo_root
        )

        new_file = new_worktree_path / "NEW_FILE.txt"
        self.assertTrue(
            new_file.exists(),
            "The file introduced by the newer origin/main commit "
            f"({self.fresh_sha}) must be present in the reconnected worktree at "
            f"{new_file}, proving the worktree was rebuilt from current origin/main "
            "rather than the stale branch tip. It is absent — the reconnect arm "
            "checked out the stale tip instead.",
        )
        if new_file.exists():
            self.assertEqual(
                new_file.read_text(encoding="utf-8"),
                "fresh content from advanced origin/main\n",
            )

    def test_ac_bo2400f3_branch_ref_itself_advances_to_origin_main(self) -> None:
        # covers: BO-2400f-3
        """The local fast-lane/<slug> branch ref must itself be advanced to
        the current origin/main — a genuinely rebuilt branch, not merely a
        detached-HEAD worktree layered over the still-stale ref.

        RED today: the reconnect arm never touches the branch ref at all; it
        stays at the stale commit it already held.
        """
        _create_fastlane_worktree(self.slug, self.worktrees_dir, self.repo_root)

        branch_tip_after = _run_git(
            ["rev-parse", self.full_branch], self.repo_root
        ).stdout.strip()

        self.assertEqual(
            branch_tip_after,
            self.fresh_sha,
            f"The '{self.full_branch}' branch ref must be advanced to the current "
            f"origin/main ({self.fresh_sha}) on reconnect, not left at the stale "
            f"commit ({self.stale_sha}) from the pruned prior run. "
            f"Branch tip after reconnect: {branch_tip_after}.",
        )


if __name__ == "__main__":
    unittest.main()
