"""
MODULE: unit_tests/build_orchestration/test_bo2400f_13ii_foreign_occupant.py
GOAL: RED behavioral tests for BO-2400f-13-ii — an occupant that is NOT this
      lane's own earlier attempt at the criterion (a bare unregistered
      directory, or a registered worktree on an unrelated branch) must be
      classified `foreign`, named without entering/moving/clearing it, and
      offered ONLY non-destructive options.

=== Live defect confirmed by direct execution (2026-09-07) ===

Both shapes reproduced against a real temporary repo:

  1. A bare, unregistered directory at worktrees/<slug>:
         $ python3 setup_ticket_worktree.py create-fastlane-worktree <slug>
     -> exit 1, stderr: "fatal: '<path>' already exists"
     -> no JSON payload at all.

  2. A registered worktree on an unrelated branch (feature/other-thing) at
     worktrees/<slug>:
     -> exit 1, stderr: "fatal: '<path>' already exists"
     -> no JSON payload at all.

Every test below is RED because `payload` is None in every case today — no
`occupant: "foreign"` classification exists in any form.

=== Real-artifact mandate ===

Every occupant here is REAL: a real non-empty directory nobody registered as
a git worktree at all (the exact KI-BO-015 shape), and a real `git worktree
add` on a distinct, real branch.
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

    def _attempt(self, slug: str) -> dict | None:
        proc = fx.run_create_fastlane_worktree(self.script_path, slug)
        return fx.parse_json_stdout(proc)


class TestBareDirectoryOccupantIsForeign(_RealRepoCase):
    def test_bare_directory_occupant_is_refused_as_foreign(self) -> None:
        # covers: BO-2400f-13-ii
        # angle: real_artifact
        slug = "bare-dir-foreign-slug"
        occupant = fx.make_occupied_bare_directory(self.worktrees_dir, slug)

        payload = self._attempt(slug)
        self.assertIsNotNone(
            payload,
            "Expected a discriminated refusal payload for a bare-directory "
            "occupant (the exact KI-BO-015 shape); today there is none.",
        )
        refusal = payload.get("refusal") or {}
        self.assertEqual(refusal.get("occupant"), "foreign", f"Got: {refusal}")
        self.assertEqual(
            refusal.get("occupant_kind"),
            "unregistered_directory",
            f"Got: {refusal}",
        )
        self.assertEqual(
            refusal.get("occupied_path"),
            str(occupant),
            f"Got: {refusal}",
        )


class TestRegisteredWorktreeOnAnotherBranchIsForeign(_RealRepoCase):
    def test_registered_worktree_on_another_branch_is_refused_as_foreign(self) -> None:
        # covers: BO-2400f-13-ii
        # angle: real_artifact
        slug = "other-branch-foreign-slug"
        fx.make_registered_worktree_on_other_branch(
            self.repo_root, self.worktrees_dir, slug, branch="feature/unrelated-work"
        )

        payload = self._attempt(slug)
        self.assertIsNotNone(payload)
        refusal = payload.get("refusal") or {}
        self.assertEqual(refusal.get("occupant"), "foreign", f"Got: {refusal}")
        self.assertEqual(
            refusal.get("occupant_kind"),
            "registered_worktree_other_branch",
            f"Got: {refusal}",
        )
        self.assertEqual(
            refusal.get("occupant_branch"),
            "feature/unrelated-work",
            f"The refusal must name the branch the occupying work belongs to. "
            f"Got: {refusal}",
        )


class TestForeignAndOwnRefusalsAreDistinguishable(_RealRepoCase):
    def test_foreign_and_own_refusals_are_distinguishable_from_the_payload_alone(self) -> None:
        # covers: BO-2400f-13-ii
        # angle: criterion
        own_slug = "distinguish-own-slug"
        fx.make_fresh_fastlane_worktree(self.script_path, own_slug)
        own_payload = self._attempt(own_slug)

        foreign_slug = "distinguish-foreign-slug"
        fx.make_occupied_bare_directory(self.worktrees_dir, foreign_slug)
        foreign_payload = self._attempt(foreign_slug)

        self.assertIsNotNone(own_payload, "Expected a payload for the own-leftover case.")
        self.assertIsNotNone(foreign_payload, "Expected a payload for the foreign case.")

        own_refusal = own_payload.get("refusal") or {}
        foreign_refusal = foreign_payload.get("refusal") or {}
        self.assertNotEqual(
            own_refusal.get("occupant"),
            foreign_refusal.get("occupant"),
            f"The two refusals must differ in 'occupant'. Own: {own_refusal}, "
            f"Foreign: {foreign_refusal}",
        )
        self.assertNotEqual(
            [o.get("destructive") for o in (own_refusal.get("options") or [])],
            [o.get("destructive") for o in (foreign_refusal.get("options") or [])],
            "The two refusals must differ in option set (own may offer a "
            "destructive clear; foreign never does).",
        )


class TestForeignRefusalOffersNoDestructiveOption(_RealRepoCase):
    def test_foreign_refusal_offers_no_destructive_option(self) -> None:
        # covers: BO-2400f-13-ii
        # angle: criterion
        slug = "no-destructive-foreign-slug"
        fx.make_occupied_bare_directory(self.worktrees_dir, slug)

        payload = self._attempt(slug)
        self.assertIsNotNone(payload)
        refusal = payload.get("refusal") or {}
        options = refusal.get("options") or []
        self.assertTrue(options, f"Expected at least one option. Got: {refusal}")
        for opt in options:
            self.assertFalse(
                opt.get("destructive", True),
                f"No option on a foreign refusal may be destructive. Got: {opt}",
            )
            action = (opt.get("action") or "").lower()
            for forbidden_verb in ("clear", "remove", "force", "move", "prune"):
                self.assertNotIn(
                    forbidden_verb,
                    action,
                    f"Option action must not name a destructive verb. Got: {opt}",
                )


class TestUnclassifiableOccupantDefaultsToForeign(_RealRepoCase):
    def test_unclassifiable_occupant_defaults_to_foreign(self) -> None:
        # covers: BO-2400f-13-ii
        # angle: failure
        """A detached-HEAD occupant at the target path cannot establish
        branch identity and must default to foreign, never own_prior_attempt."""
        slug = "detached-head-slug"
        target = self.worktrees_dir / slug
        # Register a real worktree directly in detached-HEAD state (--detach)
        # — "main" is already checked out in repo_root itself, so a plain
        # `worktree add <path> main` would collide on that branch instead of
        # producing the detached-HEAD occupant this test needs.
        fx.run_git(["worktree", "add", "--detach", str(target), "main"], self.repo_root)

        payload = self._attempt(slug)
        self.assertIsNotNone(payload)
        refusal = payload.get("refusal") or {}
        self.assertEqual(
            refusal.get("occupant"),
            "foreign",
            f"A detached-HEAD occupant must default to foreign. Got: {refusal}",
        )
        for opt in refusal.get("options") or []:
            self.assertFalse(opt.get("destructive", True))


class TestUnreadableWorktreeListingRefusesAsForeign(_RealRepoCase):
    def test_unreadable_worktree_listing_refuses_as_foreign(self) -> None:
        # covers: BO-2400f-13-ii
        # angle: failure
        """FAIL CLOSED on the lookup itself: corrupt the main repo's .git
        directory pointer used by `git worktree list --porcelain` so the
        listing itself cannot succeed, and confirm the run still refuses
        (foreign / unclassifiable) rather than reporting 'no occupant' and
        proceeding to the failing open."""
        slug = "unreadable-listing-slug"
        fx.make_occupied_bare_directory(self.worktrees_dir, slug)
        # Corrupt the repo's HEAD so most git plumbing commands (including
        # `git worktree list`) fail loudly rather than silently no-op.
        head_file = self.repo_root / ".git" / "HEAD"
        original = head_file.read_text(encoding="utf-8")
        head_file.write_text("ref: refs/heads/\x00corrupted\n", encoding="utf-8")
        try:
            payload = self._attempt(slug)
        finally:
            head_file.write_text(original, encoding="utf-8")

        self.assertIsNotNone(
            payload,
            "A failing `git worktree list --porcelain` must still yield a "
            "discriminated refusal (occupant foreign / occupant_kind "
            "unclassifiable), never a crash or a false 'opened'.",
        )
        self.assertEqual(payload.get("outcome"), "refused", f"Got: {payload}")
        refusal = payload.get("refusal") or {}
        self.assertEqual(refusal.get("occupant"), "foreign", f"Got: {refusal}")


if __name__ == "__main__":
    unittest.main()
