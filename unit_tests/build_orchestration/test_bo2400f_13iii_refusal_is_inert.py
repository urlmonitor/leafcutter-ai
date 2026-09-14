"""
MODULE: unit_tests/build_orchestration/test_bo2400f_13iii_refusal_is_inert.py
GOAL: RED behavioral tests for BO-2400f-13-iii's Python-side properties — a
      refusing `create-fastlane-worktree` run must create no new branch and
      no new per-slug directory, must leave any real occupant byte-identical,
      must leave the AC store untouched, and must be byte-stable across two
      consecutive refusals against unchanged conditions.

The JS-side zero-dispatch and no-release-step properties are covered in
unit_tests/workflows/test_bo2400f_13_workspace_refusal_workflow.py
(TestOccupiedWorkspaceRefusesBeforeAnyDispatch,
TestOccupiedRefusalDoesNotInvokeRelease) — not duplicated here.

=== Live defect confirmed by direct execution (2026-09-07) ===

For the registered-occupant scenario, today's reconnect arm actually DOES
attempt `git worktree add -B fast-lane/<slug> <path> origin/main` BEFORE
discovering the collision — confirmed live: the branch name is computed, the
force-reset flag `-B` is used, and only then does the `git worktree add`
call itself fail with exit 128 ("already used by worktree at"). Since `-B`
resets the branch ref as part of the same atomic git command that then fails,
whether the branch ref itself moves before the failure is exactly the kind
of half-fix this AC's own test_rationale warns can only be caught by
comparing real repository state before and after — not by reading the code.

=== Real-artifact mandate ===

Every assertion compares REAL repository state (branch list, registered
worktree list, occupant file content, AC store bytes) captured before and
after a REAL subprocess invocation.
"""
from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

import _bo2400f13_fixtures as fx  # noqa: E402


def _hash_tree(root: Path) -> str:
    """Stable content hash of every regular file under *root* (name + bytes)."""
    hasher = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            hasher.update(str(path.relative_to(root)).encode("utf-8"))
            hasher.update(path.read_bytes())
    return hasher.hexdigest()


class _RealRepoCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.origin = self.tmp_path / "origin"
        fx.init_origin_repo(self.origin)
        self.repo_root = fx.clone_repo_root(self.origin, self.tmp_path)
        self.worktrees_dir = self.tmp_path / "worktrees"
        self.worktrees_dir.mkdir()
        self.script_path = fx.stage_script(self.repo_root, source=fx.DEPLOYED_SCRIPT)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _branch_set(self) -> set[str]:
        result = fx.run_git(["branch", "--list"], self.repo_root)
        return {line.strip().lstrip("* ").strip() for line in result.stdout.splitlines() if line.strip()}

    def _registered_worktree_paths(self) -> set[str]:
        result = fx.run_git(["worktree", "list", "--porcelain"], self.repo_root)
        return {
            line[len("worktree "):].strip()
            for line in result.stdout.splitlines()
            if line.startswith("worktree ")
        }


class TestRefusingRunCreatesNoBranchAndNoWorkspace(_RealRepoCase):
    def test_refusing_run_creates_no_branch_and_no_workspace(self) -> None:
        # covers: BO-2400f-13-iii
        # angle: real_artifact
        slug = "no-new-branch-slug"
        fx.make_occupied_bare_directory(self.worktrees_dir, slug)

        branches_before = self._branch_set()
        worktrees_before = self._registered_worktree_paths()

        proc = fx.run_create_fastlane_worktree(self.script_path, slug)
        payload = fx.parse_json_stdout(proc)

        branches_after = self._branch_set()
        worktrees_after = self._registered_worktree_paths()

        self.assertIsNotNone(
            payload,
            "Expected a discriminated refusal payload; today there is none.",
        )
        self.assertEqual(
            branches_before,
            branches_after,
            f"No new branch may exist as a result of a refusing run. "
            f"Before: {branches_before}, after: {branches_after}",
        )
        self.assertEqual(
            worktrees_before,
            worktrees_after,
            f"No new registered worktree may exist as a result of a refusing "
            f"run. Before: {worktrees_before}, after: {worktrees_after}",
        )
        self.assertNotIn(
            f"fast-lane/{slug}",
            branches_after,
            f"fast-lane/{slug} must not exist after a refusal on a bare-"
            f"directory occupant. Got: {branches_after}",
        )


class TestRefusingRunLeavesOccupantUntouched(_RealRepoCase):
    def test_refusing_run_leaves_the_occupant_untouched(self) -> None:
        # covers: BO-2400f-13-iii
        # angle: real_artifact
        slug = "occupant-untouched-slug"
        occupant = fx.make_fresh_fastlane_worktree(self.script_path, slug)
        before_hash = _hash_tree(occupant)
        before_head = fx.run_git(["rev-parse", "HEAD"], occupant).stdout.strip()
        before_branch = fx.run_git(
            ["rev-parse", "--abbrev-ref", "HEAD"], occupant
        ).stdout.strip()

        proc = fx.run_create_fastlane_worktree(self.script_path, slug)
        payload = fx.parse_json_stdout(proc)

        self.assertIsNotNone(payload, "Expected a discriminated refusal payload.")
        after_hash = _hash_tree(occupant)
        after_head = fx.run_git(["rev-parse", "HEAD"], occupant).stdout.strip()
        after_branch = fx.run_git(
            ["rev-parse", "--abbrev-ref", "HEAD"], occupant
        ).stdout.strip()

        self.assertEqual(before_hash, after_hash, "Occupant contents must not change.")
        self.assertEqual(before_head, after_head, "Occupant HEAD must not move.")
        self.assertEqual(
            before_branch, after_branch, "Occupant's checked-out branch must not change."
        )


class TestRefusingRunLeavesAcStoreByteIdentical(_RealRepoCase):
    def test_refusing_run_leaves_the_ac_store_byte_identical(self) -> None:
        # covers: BO-2400f-13-iii
        # angle: real_artifact
        slug = "ac-store-identical-slug"
        fx.make_occupied_bare_directory(self.worktrees_dir, slug)

        ac_store = self.repo_root / "docs" / "acceptance-criteria" / "test-component"
        ac_store.mkdir(parents=True)
        ac_file = ac_store / "FLT-STUB-1.yaml"
        ac_file.write_text("id: FLT-STUB-1\nwork_status: todo\n", encoding="utf-8")
        before_hash = _hash_tree(self.repo_root / "docs" / "acceptance-criteria")

        proc = fx.run_create_fastlane_worktree(self.script_path, slug)
        payload = fx.parse_json_stdout(proc)

        self.assertIsNotNone(payload, "Expected a discriminated refusal payload.")
        after_hash = _hash_tree(self.repo_root / "docs" / "acceptance-criteria")
        self.assertEqual(
            before_hash,
            after_hash,
            "Every file under docs/acceptance-criteria/ must be byte-"
            "identical before and after a refusing run.",
        )


class TestRepeatedRefusalIsByteStable(_RealRepoCase):
    def test_repeated_refusal_is_byte_stable(self) -> None:
        # covers: BO-2400f-13-iii
        # angle: boundary
        slug = "repeated-refusal-slug"
        occupant = fx.make_fresh_fastlane_worktree(self.script_path, slug)

        proc1 = fx.run_create_fastlane_worktree(self.script_path, slug)
        payload1 = fx.parse_json_stdout(proc1)
        branches_1 = self._branch_set()
        worktrees_1 = self._registered_worktree_paths()
        occupant_hash_1 = _hash_tree(occupant)

        proc2 = fx.run_create_fastlane_worktree(self.script_path, slug)
        payload2 = fx.parse_json_stdout(proc2)
        branches_2 = self._branch_set()
        worktrees_2 = self._registered_worktree_paths()
        occupant_hash_2 = _hash_tree(occupant)

        self.assertIsNotNone(payload1, "Expected a discriminated refusal payload (run 1).")
        self.assertIsNotNone(payload2, "Expected a discriminated refusal payload (run 2).")

        refusal1 = payload1.get("refusal") or {}
        refusal2 = payload2.get("refusal") or {}
        self.assertEqual(
            refusal1.get("occupant"),
            refusal2.get("occupant"),
            f"Both refusals must name the same occupant classification. "
            f"Got {refusal1} vs {refusal2}",
        )
        self.assertEqual(
            refusal1.get("reason"),
            refusal2.get("reason"),
            f"Both refusals must give the same reason. Got {refusal1} vs {refusal2}",
        )
        self.assertEqual(
            branches_1, branches_2, "The branch set must be identical after each refusal."
        )
        self.assertEqual(
            worktrees_1,
            worktrees_2,
            "The registered-worktree set must be identical after each refusal.",
        )
        self.assertEqual(
            occupant_hash_1,
            occupant_hash_2,
            "The occupant's contents must be identical after each refusal.",
        )


if __name__ == "__main__":
    unittest.main()
