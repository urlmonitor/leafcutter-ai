"""
MODULE: unit_tests/build_orchestration/test_bo2400f_13i_own_leftover_report.py
GOAL: RED behavioral tests for BO-2400f-13-i — when the occupant at a fast-
      lane workspace location is this lane's OWN earlier attempt at the same
      acceptance criterion, the refusal must report (read from the real
      occupant, never templated): whether it holds uncommitted changes,
      whether it was pushed, and at least three next-step options with only
      the clearing option marked destructive.

=== Live defect confirmed by direct execution (2026-09-07) ===

Re-running `create-fastlane-worktree <slug>` against an already-registered
fast-lane/<slug> worktree exits 1 with a raw git diagnostic
("fatal: '<branch>' is already used by worktree at '<path>'") and NO JSON
payload at all — so none of this AC's reporting fields exist today in any
form. Every test below is RED for that reason: `payload` is None.

=== Real-artifact mandate ===

Every scenario here creates a REAL prior fast-lane worktree via the REAL CLI,
then mutates it with REAL git operations (an uncommitted edit, a real push to
a real local 'origin' remote) before re-invoking the REAL CLI as a subprocess
against it. Nothing here is a hand-made dict standing in for a real occupant.
"""
from __future__ import annotations

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

    def _make_leftover(self, slug: str) -> Path:
        return fx.make_fresh_fastlane_worktree(self.script_path, slug)

    def _refuse_again(self, slug: str) -> dict | None:
        proc = fx.run_create_fastlane_worktree(self.script_path, slug)
        return fx.parse_json_stdout(proc)


class TestUncommittedLeftoverReportedAsHoldingWork(_RealRepoCase):
    def test_leftover_holding_an_uncommitted_change_is_reported_as_holding_work(self) -> None:
        # covers: BO-2400f-13-i
        # angle: real_artifact
        slug = "dirty-leftover-slug"
        leftover = self._make_leftover(slug)
        (leftover / "uncommitted_change.txt").write_text("edited but not committed\n", encoding="utf-8")

        payload = self._refuse_again(slug)
        self.assertIsNotNone(
            payload,
            "Expected a discriminated refusal payload for an own-leftover "
            "occupant; today there is none at all (raw git diagnostic instead).",
        )
        refusal = payload.get("refusal") or {}
        self.assertIs(
            refusal.get("uncommitted_changes"),
            True,
            f"An uncommitted edit in the leftover must be reported true. Got: {refusal}",
        )


class TestCleanLeftoverReportedAsClean(_RealRepoCase):
    def test_clean_leftover_is_reported_as_clean(self) -> None:
        # covers: BO-2400f-13-i
        # angle: real_artifact
        """The load-bearing PAIR with the test above: only together do the
        two prove the value was READ, not templated."""
        slug = "clean-leftover-slug"
        self._make_leftover(slug)

        payload = self._refuse_again(slug)
        self.assertIsNotNone(payload, "Expected a discriminated refusal payload.")
        refusal = payload.get("refusal") or {}
        self.assertIs(
            refusal.get("uncommitted_changes"),
            False,
            f"A clean leftover must be reported false, not merely 'not True'. Got: {refusal}",
        )


class TestLeftoverOnOwnBranchClassifiesAsOwnPriorAttempt(_RealRepoCase):
    def test_leftover_on_the_criterions_own_branch_classifies_as_own_prior_attempt(self) -> None:
        # covers: BO-2400f-13-i
        # angle: criterion
        slug = "own-branch-slug"
        self._make_leftover(slug)

        payload = self._refuse_again(slug)
        self.assertIsNotNone(payload)
        refusal = payload.get("refusal") or {}
        self.assertEqual(
            refusal.get("occupant"),
            "own_prior_attempt",
            f"A worktree registered on refs/heads/fast-lane/{slug} for this "
            f"AC id must classify as own_prior_attempt. Got: {refusal}",
        )
        self.assertNotIn(
            "unexplained",
            (refusal.get("message") or "").lower(),
        )


class TestUnreadableOccupantReportsUndetermined(_RealRepoCase):
    def test_unreadable_occupant_reports_uncommitted_state_as_undetermined_not_clean(self) -> None:
        # covers: BO-2400f-13-i
        # angle: failure
        """FAIL CLOSED: make `git status` inside the occupant impossible by
        corrupting its .git file, then confirm the refusal reports null
        (undetermined) rather than defaulting to false (clean)."""
        slug = "unreadable-leftover-slug"
        leftover = self._make_leftover(slug)
        git_file = leftover / ".git"
        # A worktree's .git is a FILE pointing at the real gitdir. Replacing
        # its content with garbage makes `git status` inside it fail while
        # leaving the directory itself present and non-empty (still an
        # occupant, just an unreadable one).
        self.assertTrue(git_file.is_file(), "Precondition: worktree .git must be a file.")
        git_file.write_text("gitdir: /nonexistent/corrupted/path\n", encoding="utf-8")

        payload = self._refuse_again(slug)
        self.assertIsNotNone(payload)
        refusal = payload.get("refusal") or {}
        self.assertIsNone(
            refusal.get("uncommitted_changes"),
            f"An unreadable occupant must report null (undetermined), never "
            f"False (clean) or True. Got: {refusal}",
        )
        options = refusal.get("options") or []
        self.assertTrue(
            options,
            f"Expected a non-empty, well-formed options list even when the "
            f"uncommitted-changes read failed. Got: {refusal}",
        )
        for opt in options:
            self.assertIn(
                "destructive",
                opt,
                f"Every option must explicitly declare 'destructive'. Got: {opt}",
            )


class TestPushedPriorAttemptDistinguishedFromUnpushed(_RealRepoCase):
    def test_pushed_prior_attempt_is_distinguished_from_an_unpushed_one(self) -> None:
        # covers: BO-2400f-13-i
        # angle: real_artifact
        slug = "pushed-leftover-slug"
        leftover = self._make_leftover(slug)
        full_branch = f"fast-lane/{slug}"
        # Push the leftover's branch to the real local 'origin' remote —
        # purely local, deterministic, no network.
        fx.run_git(["push", "origin", f"{full_branch}:{full_branch}"], leftover)

        payload = self._refuse_again(slug)
        self.assertIsNotNone(payload)
        refusal = payload.get("refusal") or {}
        published = refusal.get("published") or {}
        self.assertIs(
            published.get("pushed"),
            True,
            f"A pushed leftover branch must report published.pushed true. Got: {refusal}",
        )

        # The unpushed sibling, same test for contrast.
        slug2 = "unpushed-leftover-slug"
        self._make_leftover(slug2)
        payload2 = self._refuse_again(slug2)
        self.assertIsNotNone(payload2)
        refusal2 = payload2.get("refusal") or {}
        published2 = refusal2.get("published") or {}
        self.assertIs(
            published2.get("pushed"),
            False,
            f"An unpushed leftover branch must report published.pushed false. Got: {refusal2}",
        )


class TestPrLookupFailureReportedAsUnavailable(_RealRepoCase):
    def test_pr_lookup_failure_is_reported_as_unavailable_not_as_no_pull_request(self) -> None:
        # covers: BO-2400f-13-i
        # angle: failure
        """With `gh` unreachable (no PATH override needed — a throwaway repo
        has no real GitHub remote for `gh pr list` to succeed against
        regardless), pr_url is null AND pr_lookup is 'unavailable' or
        'not_attempted' — never silently read as 'no pull request was
        opened'."""
        slug = "pr-lookup-slug"
        self._make_leftover(slug)

        payload = self._refuse_again(slug)
        self.assertIsNotNone(payload)
        refusal = payload.get("refusal") or {}
        published = refusal.get("published") or {}
        self.assertIn(
            published.get("pr_lookup"),
            ("unavailable", "not_attempted"),
            f"Got: {refusal}",
        )
        self.assertNotIn(
            "no pull request was opened",
            (refusal.get("message") or "").lower(),
            f"Got: {refusal}",
        )


class TestRefusalOffersAtLeastThreeOptions(_RealRepoCase):
    def test_refusal_offers_at_least_three_named_next_steps_with_only_clearing_destructive(self) -> None:
        # covers: BO-2400f-13-i
        # angle: criterion
        slug = "three-options-slug"
        self._make_leftover(slug)

        payload = self._refuse_again(slug)
        self.assertIsNotNone(payload)
        refusal = payload.get("refusal") or {}
        options = refusal.get("options") or []
        self.assertGreaterEqual(
            len(options), 3, f"Expected at least 3 options. Got: {refusal}"
        )
        destructive_count = sum(1 for opt in options if opt.get("destructive"))
        self.assertEqual(
            destructive_count,
            1,
            f"Exactly the clearing option should be destructive. Got: {options}",
        )


class TestRefusingRunNeitherEntersNorClearsLeftover(_RealRepoCase):
    def test_refusing_run_neither_enters_updates_nor_clears_the_leftover(self) -> None:
        # covers: BO-2400f-13-i
        # angle: real_artifact
        slug = "untouched-leftover-slug"
        leftover = self._make_leftover(slug)
        before_head = fx.run_git(["rev-parse", "HEAD"], leftover).stdout.strip()
        before_branch = fx.run_git(
            ["rev-parse", "--abbrev-ref", "HEAD"], leftover
        ).stdout.strip()
        marker = leftover / "leave_me_alone.txt"
        marker.write_text("do not touch\n", encoding="utf-8")

        payload = self._refuse_again(slug)

        # This is the discriminated-payload half of the assertion — RED today
        # because the run does not yet produce any refusal payload at all
        # (raw git diagnostic on stderr, nothing on stdout). Combined with the
        # untouched-occupant checks below, this ties "the refusal is inert"
        # to "the refusal actually exists", so this test cannot pass merely
        # because today's unrelated git-safety behavior happens to leave the
        # occupant alone for a different reason.
        self.assertIsNotNone(
            payload,
            "Expected a discriminated refusal payload reporting the leftover "
            "was left untouched; today there is none at all.",
        )

        self.assertTrue(leftover.exists(), "The leftover must still exist after a refusal.")
        after_head = fx.run_git(["rev-parse", "HEAD"], leftover).stdout.strip()
        after_branch = fx.run_git(
            ["rev-parse", "--abbrev-ref", "HEAD"], leftover
        ).stdout.strip()
        self.assertEqual(before_head, after_head, "HEAD must not move on a refusing run.")
        self.assertEqual(
            before_branch, after_branch, "The checked-out branch must not change."
        )
        self.assertTrue(
            marker.exists(),
            "The refusing run must not have removed the operator's untracked file.",
        )
        self.assertEqual(marker.read_text(encoding="utf-8"), "do not touch\n")


if __name__ == "__main__":
    unittest.main()
