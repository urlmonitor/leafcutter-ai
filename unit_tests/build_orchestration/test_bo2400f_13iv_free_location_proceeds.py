"""
MODULE: unit_tests/build_orchestration/test_bo2400f_13iv_free_location_proceeds.py
GOAL: RED behavioral tests for BO-2400f-13-iv — the counterweight to
      BO-2400f-13: a genuinely free location (including the two states a
      naive refusal gate over-refuses on — an existing EMPTY directory, and
      the residual branch-exists-but-no-worktree state every finished prior
      run leaves behind) must NEVER be refused, and the resulting "opened"
      payload must report whether the workspace is new and which mainline
      commit it actually sits on.

=== Live behavior confirmed by direct execution (2026-09-07) ===

Both "must not refuse" cases ALREADY succeed today (exit 0, JSON payload) —
today's code has no occupancy gate at all, so it cannot over-refuse on them.
What is RED is the SHAPE of the success payload: it has no `outcome` key,
no `base_commit`, and no `base_matches_origin_main` in any form — the
`it_requirements.config_schema_fragment.fastlane_opened_workspace_report`
this AC specifies does not exist yet.

=== Real-artifact mandate ===

Every scenario here is built and asserted against a REAL temporary git repo
and a REAL subprocess invocation of the CLI.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

import _bo2400f13_fixtures as fx  # noqa: E402


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


class TestResidualBranchWithoutRegisteredWorktreeIsNotRefused(_RealRepoCase):
    def test_residual_branch_without_a_registered_worktree_is_not_refused(self) -> None:
        # covers: BO-2400f-13-iv
        # angle: boundary
        slug = "residual-branch-slug"
        worktree_path = fx.make_fresh_fastlane_worktree(self.script_path, slug)
        # Simulate a finished-and-cleaned-up prior run: remove the worktree
        # directory and prune its registration, but the branch survives —
        # the state every finished prior run leaves behind.
        shutil.rmtree(worktree_path)
        fx.run_git(["worktree", "prune"], self.repo_root)
        self.assertTrue(
            fx.run_git(["branch", "--list", f"fast-lane/{slug}"], self.repo_root).stdout.strip(),
            "Precondition: the branch must still exist after prune.",
        )

        proc = fx.run_create_fastlane_worktree(self.script_path, slug)
        payload = fx.parse_json_stdout(proc)

        self.assertEqual(
            proc.returncode,
            0,
            f"A residual branch (no registered worktree) must NOT be refused. "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}",
        )
        self.assertIsNotNone(payload)
        self.assertEqual(
            payload.get("outcome"),
            "opened",
            f"Expected outcome: 'opened' — today's payload has no 'outcome' "
            f"key at all. Got: {payload}",
        )


class TestExistingEmptyDirectoryIsNotRefused(_RealRepoCase):
    def test_existing_empty_directory_at_the_location_is_not_refused(self) -> None:
        # covers: BO-2400f-13-iv
        # angle: boundary
        slug = "empty-dir-open-slug"
        (self.worktrees_dir / slug).mkdir()

        proc = fx.run_create_fastlane_worktree(self.script_path, slug)
        payload = fx.parse_json_stdout(proc)

        self.assertEqual(proc.returncode, 0, f"stderr={proc.stderr!r}")
        self.assertIsNotNone(payload)
        self.assertEqual(
            payload.get("outcome"),
            "opened",
            f"An existing EMPTY directory must yield outcome: 'opened'. Got: {payload}",
        )


class TestOpenedPayloadReportsWhetherWorkspaceIsNew(_RealRepoCase):
    def test_opened_payload_reports_whether_the_workspace_is_new(self) -> None:
        # covers: BO-2400f-13-iv
        # angle: real_artifact
        slug = "created-flag-slug"
        proc = fx.run_create_fastlane_worktree(self.script_path, slug)
        payload = fx.parse_json_stdout(proc)

        self.assertEqual(proc.returncode, 0, f"stderr={proc.stderr!r}")
        self.assertIsNotNone(payload)
        self.assertIn(
            "outcome",
            payload,
            f"Expected an 'outcome' discriminant on every payload. Got: {payload}",
        )
        self.assertIs(
            payload.get("created"),
            True,
            f"A workspace this run made must report created: true. Got: {payload}",
        )


class TestOpenedPayloadNamesActualCommit(_RealRepoCase):
    def test_opened_payload_names_the_commit_the_workspace_actually_sits_on(self) -> None:
        # covers: BO-2400f-13-iv
        # angle: real_artifact
        slug = "base-commit-slug"
        proc = fx.run_create_fastlane_worktree(self.script_path, slug)
        payload = fx.parse_json_stdout(proc)

        self.assertEqual(proc.returncode, 0, f"stderr={proc.stderr!r}")
        self.assertIsNotNone(payload)
        worktree_path = Path(payload["worktree_path"])
        actual_head = fx.run_git(["rev-parse", "HEAD"], worktree_path).stdout.strip()
        origin_main = fx.run_git(["rev-parse", "origin/main"], self.repo_root).stdout.strip()

        self.assertEqual(
            payload.get("base_commit"),
            actual_head,
            f"base_commit must equal the workspace's real HEAD. Got: {payload}",
        )
        self.assertIs(
            payload.get("base_matches_origin_main"),
            True,
            f"A fresh workspace's base must match origin/main. Got: {payload}",
        )
        self.assertEqual(actual_head, origin_main)


class TestDivergentBaseIsReportedNotCorrected(_RealRepoCase):
    def test_divergent_base_is_reported_rather_than_corrected(self) -> None:
        # covers: BO-2400f-13-iv
        # angle: failure
        slug = "divergent-base-slug"
        worktree_path = fx.make_fresh_fastlane_worktree(self.script_path, slug)
        stale_sha = fx.run_git(["rev-parse", "HEAD"], worktree_path).stdout.strip()

        # Simulate the residual state (worktree pruned, branch survives) and
        # advance the real origin past the stale branch tip.
        shutil.rmtree(worktree_path)
        fx.run_git(["worktree", "prune"], self.repo_root)
        fresh_sha = fx.advance_origin(
            self.origin, "NEW_FILE.txt", "fresh content\n", "advance past the stale tip"
        )
        fx.run_git(["fetch", "origin"], self.repo_root)

        proc = fx.run_create_fastlane_worktree(self.script_path, slug)
        payload = fx.parse_json_stdout(proc)

        self.assertEqual(proc.returncode, 0, f"stderr={proc.stderr!r}")
        self.assertIsNotNone(payload)
        self.assertEqual(payload.get("outcome"), "opened", f"Got: {payload}")

        new_worktree_path = Path(payload["worktree_path"])
        actual_head = fx.run_git(["rev-parse", "HEAD"], new_worktree_path).stdout.strip()

        # BO-2400f-3's already-fixed reconnect logic rebuilds from the fresh
        # origin/main tip, so actual_head should equal fresh_sha, not stale_sha
        # — this assertion documents that expectation without re-testing
        # BO-2400f-3 itself. What THIS AC adds and what is RED today is the
        # explicit base_commit / base_matches_origin_main reporting:
        self.assertEqual(
            payload.get("base_commit"),
            actual_head,
            f"base_commit must be read from the real workspace HEAD, not "
            f"templated. Got: {payload}",
        )
        self.assertIn(
            "base_matches_origin_main",
            payload,
            f"The payload must explicitly say whether the base matches "
            f"origin/main, so a divergence is visible rather than silent. "
            f"Got: {payload}",
        )
        self.assertNotEqual(stale_sha, fresh_sha)


class TestCompletedAndCleanedUpPriorRunDoesNotBlockNext(_RealRepoCase):
    def test_a_completed_and_cleaned_up_prior_run_does_not_block_the_next(self) -> None:
        # covers: BO-2400f-13-iv
        # angle: criterion
        slug = "full-cycle-slug"
        worktree_path = fx.make_fresh_fastlane_worktree(self.script_path, slug)
        full_branch = f"fast-lane/{slug}"

        # Fully clean up: remove worktree, prune, delete the branch too.
        fx.run_git(["worktree", "remove", "--force", str(worktree_path)], self.repo_root)
        fx.run_git(["branch", "-D", full_branch], self.repo_root)

        proc = fx.run_create_fastlane_worktree(self.script_path, slug)
        payload = fx.parse_json_stdout(proc)

        self.assertEqual(
            proc.returncode,
            0,
            f"A fully cleaned-up prior run must not block the next. stderr={proc.stderr!r}",
        )
        self.assertIsNotNone(payload)
        self.assertEqual(
            payload.get("outcome"),
            "opened",
            f"Expected outcome: 'opened' on a full re-run for a fully "
            f"cleaned-up criterion. Got: {payload}",
        )


class TestFreeLocationReachesRealEntryPointDeployed(_RealRepoCase):
    def test_free_location_run_reaches_the_workspace_command_through_its_real_entry_point(self) -> None:
        # covers: BO-2400f-13-iv
        # angle: reachability
        """Run against the DEPLOYED copy — the one build.py produces and the
        lane actually invokes — with the exact argv the lane composes."""
        deployed_script = fx.stage_script(self.repo_root, source=fx.DEPLOYED_SCRIPT)
        slug = "deployed-reachability-slug"

        proc = fx.run_create_fastlane_worktree(deployed_script, slug)
        payload = fx.parse_json_stdout(proc)

        self.assertEqual(proc.returncode, 0, f"stderr={proc.stderr!r}")
        self.assertIsNotNone(payload)
        self.assertEqual(
            payload.get("outcome"),
            "opened",
            f"Expected the discriminated 'opened' outcome from the deployed "
            f"copy via its real CLI entry point. Got: {payload}",
        )
        for field in ("created", "base_commit", "base_matches_origin_main"):
            self.assertIn(field, payload, f"Missing {field!r} in: {payload}")


if __name__ == "__main__":
    unittest.main()
