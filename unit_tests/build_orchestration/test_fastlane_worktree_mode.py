"""
MODULE: unit_tests/build_orchestration/test_fastlane_worktree_mode.py
GOAL: RED test stubs for BO-2400f-3 (auto-create an isolated worktree off the
      latest origin/main) — specifically the setup_ticket_worktree.py extension
      that implements the create-fastlane-worktree subcommand.

=== Interface contract defined by these tests (for python-coder to implement) ===

Location: scripts/setup_ticket_worktree.py

1. New subcommand registered in _build_parser():
       create-fastlane-worktree <slug>

   Parses a positional slug argument and sets a func= handler on the namespace
   (same pattern as create-ac-worktree).

2. New pure helper:
       _fastlane_branch(slug: str) -> str
           Returns "fast-lane/<slug>".
           Makes the prefix explicit and testable in isolation.

3. New implementation helper (mirrors _create_ac_worktree):
       _create_fastlane_worktree(slug: str, worktrees_dir: Path, repo_root: Path) -> Path
           Creates a git worktree on branch fast-lane/<slug> rooted at origin/main.
           Calls: git worktree add -b fast-lane/<slug> <path> origin/main

4. New command handler:
       cmd_create_fastlane_worktree(args: argparse.Namespace) -> None
           Fetches origin, creates the worktree, bootstraps it, prints JSON:
               {"worktree_path": str, "branch": str, "ac_store_path": str, "created": bool}

=== Rationale for fast-lane/ prefix ===

BO-2400f-3 requires the branch name to be "distinct from ac-authoring branches".
The ac-authoring subcommand uses "ac-authoring/<slug>"; feature branches use
"feature/<slug>".  The fast-lane worktree must use "fast-lane/<slug>" so that
git worktree list shows the intent unambiguously.

=== No real git operations ===

These tests do NOT create real git worktrees.  They test:
  - Argparse acceptability of the new subcommand (parser-level).
  - Branch name construction via the pure _fastlane_branch() helper.
  - Git argv shape via a fully-mocked subprocess.run (no real git side effects).

The first two tests will fail with SystemExit or ImportError/AttributeError
(intended red states) until the coder adds the subcommand and helper.
The subprocess mock test fails with ImportError until the coder implements
_create_fastlane_worktree.

=== Red baseline ===

All tests are RED:
  - Parser tests: SystemExit(2) because create-fastlane-worktree is not in _build_parser().
  - Helper tests: ImportError/AttributeError because _fastlane_branch does not exist yet.
  - Subprocess mock test: ImportError because _create_fastlane_worktree does not exist yet.
"""
from __future__ import annotations

import sys
import tempfile
import subprocess
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

# ---------------------------------------------------------------------------
# Repo path wiring
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# ---------------------------------------------------------------------------
# Import _build_parser (exists today).
# ---------------------------------------------------------------------------

_BUILD_PARSER_OK = False
_BUILD_PARSER_ERR = ""
_build_parser = None  # type: ignore[assignment]

try:
    from setup_ticket_worktree import _build_parser  # type: ignore[import]
    _BUILD_PARSER_OK = True
except (ImportError, ModuleNotFoundError) as _exc:
    _BUILD_PARSER_ERR = str(_exc)

# ---------------------------------------------------------------------------
# Import _fastlane_branch — new helper, not yet implemented.
# ImportError IS the intended red state for helper tests.
# ---------------------------------------------------------------------------

_FASTLANE_BRANCH_OK = False
_FASTLANE_BRANCH_ERR = ""
_fastlane_branch = None  # type: ignore[assignment]

try:
    from setup_ticket_worktree import _fastlane_branch  # type: ignore[import]
    _FASTLANE_BRANCH_OK = True
except (ImportError, ModuleNotFoundError, AttributeError) as _exc:
    _FASTLANE_BRANCH_ERR = str(_exc)

# ---------------------------------------------------------------------------
# Import _create_fastlane_worktree — new implementation helper, not yet implemented.
# ImportError IS the intended red state for the subprocess mock test.
# ---------------------------------------------------------------------------

_CREATE_FASTLANE_OK = False
_CREATE_FASTLANE_ERR = ""
_create_fastlane_worktree = None  # type: ignore[assignment]

try:
    from setup_ticket_worktree import _create_fastlane_worktree  # type: ignore[import]
    _CREATE_FASTLANE_OK = True
except (ImportError, ModuleNotFoundError, AttributeError) as _exc:
    _CREATE_FASTLANE_ERR = str(_exc)


# ---------------------------------------------------------------------------
# Parser-level tests — BO-2400f-3
# ---------------------------------------------------------------------------


class TestFastlaneWorktreeParser(unittest.TestCase):
    """Argparse-level tests for the create-fastlane-worktree subcommand.

    BO-2400f-3: the operator does not create the worktree by hand — the command
    exists and handles the slug argument.

    RED state: _build_parser() does not yet register 'create-fastlane-worktree',
    so parse_args(['create-fastlane-worktree', 'my-slug']) raises SystemExit(2).
    """

    def test_ac3_parser_accepts_create_fastlane_worktree_subcommand(self) -> None:
        # covers: BO-2400f-3
        """_build_parser() must register 'create-fastlane-worktree' as a valid subcommand.

        Parsing ['create-fastlane-worktree', 'my-slug'] must succeed (no SystemExit).
        The current _build_parser() has three subcommands:
            setup-ticket, create-only, create-ac-worktree.
        The coder must add a fourth: create-fastlane-worktree.

        To make this green:
          1. Add a subparsers.add_parser('create-fastlane-worktree', ...) call.
          2. Add a positional 'slug' argument to it.
          3. Set func=cmd_create_fastlane_worktree on it.
        """
        if not _BUILD_PARSER_OK:
            self.fail(
                f"Could not import _build_parser from setup_ticket_worktree: "
                f"{_BUILD_PARSER_ERR}"
            )

        parser = _build_parser()
        try:
            args = parser.parse_args(["create-fastlane-worktree", "my-slug"])
        except SystemExit as exc:
            self.fail(
                f"_build_parser() must accept 'create-fastlane-worktree' as a "
                f"valid subcommand, but parse_args raised SystemExit({exc.code}). "
                f"The 'create-fastlane-worktree' subcommand is not yet registered "
                f"in _build_parser() (BO-2400f-3). "
                f"Coder must add: subparsers.add_parser('create-fastlane-worktree', ...)"
            )

        # The slug 'my-slug' must be captured in the parsed namespace.
        ns_values = list(vars(args).values())
        self.assertIn(
            "my-slug",
            ns_values,
            f"The slug argument 'my-slug' must be captured in the parsed namespace. "
            f"Got namespace: {vars(args)} — "
            f"coder must add a positional 'slug' argument to the subparser.",
        )

    def test_ac3_parser_slug_is_accessible_on_namespace(self) -> None:
        # covers: BO-2400f-3
        """The slug positional argument must be accessible via args.slug (or similar).

        Parsing ['create-fastlane-worktree', 'bo-2400f-build'] must capture
        the slug so cmd_create_fastlane_worktree can derive fast-lane/<slug>.

        To make this green, add the slug argument as a required positional:
            p_fl.add_argument('slug', help='Short slug for the fast-lane session.')
        """
        if not _BUILD_PARSER_OK:
            self.fail(
                f"Could not import _build_parser: {_BUILD_PARSER_ERR}"
            )

        parser = _build_parser()
        try:
            args = parser.parse_args(["create-fastlane-worktree", "bo-2400f-build"])
        except SystemExit as exc:
            self.fail(
                f"Parsing 'create-fastlane-worktree bo-2400f-build' raised "
                f"SystemExit({exc.code}) — subcommand not yet registered (BO-2400f-3)."
            )

        ns = vars(args)
        self.assertIn(
            "bo-2400f-build",
            list(ns.values()),
            f"Slug 'bo-2400f-build' must appear in the namespace. Got: {ns}",
        )

    def test_ac3_parser_create_fastlane_worktree_has_func_set(self) -> None:
        # covers: BO-2400f-3
        """The create-fastlane-worktree subparser must set a func= handler on the namespace.

        This follows the same pattern as create-ac-worktree:
            p_ac.set_defaults(func=cmd_create_ac_worktree)
        The handler is invoked by main() via args.func(args).

        To make this green, add: p_fl.set_defaults(func=cmd_create_fastlane_worktree)
        """
        if not _BUILD_PARSER_OK:
            self.fail(f"Could not import _build_parser: {_BUILD_PARSER_ERR}")

        parser = _build_parser()
        try:
            args = parser.parse_args(["create-fastlane-worktree", "test-slug"])
        except SystemExit as exc:
            self.fail(
                f"Parsing 'create-fastlane-worktree test-slug' raised SystemExit({exc.code}) "
                f"— subcommand not registered (BO-2400f-3)."
            )

        self.assertTrue(
            hasattr(args, "func") and callable(getattr(args, "func", None)),
            f"The create-fastlane-worktree subparser must set a callable func= handler "
            f"on the namespace via set_defaults(func=cmd_create_fastlane_worktree). "
            f"Got namespace: {vars(args)}",
        )


# ---------------------------------------------------------------------------
# Branch helper tests — BO-2400f-3
# ---------------------------------------------------------------------------


class TestFastlaneBranchHelper(unittest.TestCase):
    """Tests for the _fastlane_branch() pure helper — BO-2400f-3.

    RED state: _fastlane_branch does not yet exist in setup_ticket_worktree.py,
    so the import fails with ImportError.
    """

    def test_ac3_fastlane_branch_returns_fast_lane_prefix(self) -> None:
        # covers: BO-2400f-3
        """_fastlane_branch(slug) must return 'fast-lane/<slug>'.

        The branch name for a fast-lane worktree must be prefixed with 'fast-lane/'
        to make it visually distinct from feature/, ticket/, and ac-authoring/
        branches in git worktree list output (BO-2400f-3).

        The coder must add to setup_ticket_worktree.py:
            def _fastlane_branch(slug: str) -> str:
                return f"fast-lane/{slug}"

        To make this green: implement _fastlane_branch and re-run.
        """
        if not _FASTLANE_BRANCH_OK:
            self.fail(
                f"_fastlane_branch is not importable from setup_ticket_worktree — "
                f"ImportError is the intended red state. "
                f"Coder must add: def _fastlane_branch(slug: str) -> str "
                f"to setup_ticket_worktree.py (BO-2400f-3). "
                f"Import error: {_FASTLANE_BRANCH_ERR}"
            )

        result = _fastlane_branch("my-feature")
        self.assertEqual(
            result,
            "fast-lane/my-feature",
            "Branch name for slug 'my-feature' must be 'fast-lane/my-feature' "
            "(BO-2400f-3: branch prefixed for build, distinct from ac-authoring branches). "
            f"Got: {result!r}",
        )

    def test_ac3_fastlane_branch_various_slugs(self) -> None:
        # covers: BO-2400f-3
        """_fastlane_branch returns 'fast-lane/<slug>' for any slug string."""
        if not _FASTLANE_BRANCH_OK:
            self.fail(
                f"_fastlane_branch not importable — ImportError is the red state. "
                f"Error: {_FASTLANE_BRANCH_ERR}"
            )

        cases = [
            ("bo-2400f-1", "fast-lane/bo-2400f-1"),
            ("test-build", "fast-lane/test-build"),
            ("2026-07-23-run", "fast-lane/2026-07-23-run"),
            ("my-feature-slug", "fast-lane/my-feature-slug"),
        ]
        for slug, expected in cases:
            with self.subTest(slug=slug):
                self.assertEqual(
                    _fastlane_branch(slug),
                    expected,
                    f"_fastlane_branch({slug!r}) must return {expected!r} (BO-2400f-3).",
                )

    def test_ac3_fastlane_branch_does_not_return_feature_prefix(self) -> None:
        # covers: BO-2400f-3
        """_fastlane_branch must NOT use the 'feature/' prefix (wrong prefix).

        Fast-lane worktrees must be distinct from regular feature branches.
        The coder must ensure the prefix is 'fast-lane/' not 'feature/'.
        """
        if not _FASTLANE_BRANCH_OK:
            self.fail(
                f"_fastlane_branch not importable — ImportError is the red state. "
                f"Error: {_FASTLANE_BRANCH_ERR}"
            )

        result = _fastlane_branch("some-slug")
        self.assertFalse(
            result.startswith("feature/"),
            f"_fastlane_branch must NOT return a 'feature/' prefix — "
            f"fast-lane branches must be distinct from regular feature branches "
            f"(BO-2400f-3). Got: {result!r}",
        )
        self.assertTrue(
            result.startswith("fast-lane/"),
            f"_fastlane_branch must return a 'fast-lane/' prefix. Got: {result!r}",
        )


# ---------------------------------------------------------------------------
# Subprocess mock test — git argv shape
# ---------------------------------------------------------------------------


class TestFastlaneWorktreeGitArgvShape(unittest.TestCase):
    """Test the git worktree add argv shape via a mocked subprocess.run — BO-2400f-3.

    RED state: _create_fastlane_worktree does not yet exist, so the import
    fails with ImportError (intended red state).
    """

    def test_ac3_git_worktree_add_uses_fast_lane_branch_and_origin_main(self) -> None:
        # covers: BO-2400f-3
        """_create_fastlane_worktree must call git worktree add -b fast-lane/<slug> ... origin/main.

        With subprocess.run fully mocked (no real git side-effects), verify:
        1. At least one call to subprocess.run includes 'worktree' and 'add'.
        2. The git worktree add call includes 'fast-lane/<slug>' as the branch name.
        3. The git worktree add call includes 'origin/main' as the base ref (not 'main').

        BO-2400f-3 requires: "creates a dedicated worktree on a fresh branch cut from
        the latest origin/main (never from stale local main)".

        To make this green:
        1. Add _create_fastlane_worktree(slug, worktrees_dir, repo_root) to
           setup_ticket_worktree.py.
        2. Implement it analogously to _create_ac_worktree but with fast-lane/ prefix
           and origin/main as the base.
        """
        if not _CREATE_FASTLANE_OK:
            self.fail(
                f"_create_fastlane_worktree is not importable from setup_ticket_worktree — "
                f"ImportError is the intended red state. "
                f"Coder must implement _create_fastlane_worktree(slug, worktrees_dir, "
                f"repo_root) in setup_ticket_worktree.py (BO-2400f-3). "
                f"Import error: {_CREATE_FASTLANE_ERR}"
            )

        slug = "test-fastlane-slug"
        worktree_calls: list[list[str]] = []

        def _mock_subprocess_run(cmd, *args, **kwargs):
            """Intercept all subprocess.run calls; capture worktree add calls."""
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            cmd_parts = [str(c) for c in cmd]
            cmd_str = " ".join(cmd_parts)
            if "branch" in cmd_str and "--list" in cmd_str:
                # _branch_exists check: return empty -> branch doesn't exist -> use -b form
                mock_result.stdout = ""
            if "worktree" in cmd_str and "add" in cmd_str:
                worktree_calls.append(cmd_parts)
            return mock_result

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            worktrees_dir = tmp / "worktrees"
            worktrees_dir.mkdir()
            repo_root = tmp / "fake-repo"
            repo_root.mkdir()

            with patch("subprocess.run", side_effect=_mock_subprocess_run):
                try:
                    _create_fastlane_worktree(slug, worktrees_dir, repo_root)
                except (subprocess.SubprocessError, OSError):
                    # Real filesystem / subprocess side-effects may raise after the
                    # git worktree add call has been captured by the mock (e.g. the
                    # fake repo_root has no real git metadata).  We only care that
                    # the git worktree add call was issued correctly; other exceptions
                    # (ValueError, AttributeError, etc.) propagate as test failures.
                    pass

        # Assert: at least one git worktree add was captured
        self.assertTrue(
            worktree_calls,
            "_create_fastlane_worktree must issue a 'git worktree add' subprocess call "
            "(BO-2400f-3). No worktree-add call was captured by the mock.",
        )

        # Join all captured argv strings for easy substring searching
        all_argv_joined = " ".join(
            " ".join(parts) for parts in worktree_calls
        )

        # Assert: the branch name contains 'fast-lane/<slug>'
        self.assertIn(
            f"fast-lane/{slug}",
            all_argv_joined,
            f"The git worktree add call must include branch name 'fast-lane/{slug}'. "
            f"Captured git worktree add calls: {worktree_calls} "
            f"(BO-2400f-3: branch name is derived from the slug with fast-lane/ prefix).",
        )

        # Assert: origin/main is the base ref (not local 'main')
        self.assertIn(
            "origin/main",
            all_argv_joined,
            "The git worktree add call must include 'origin/main' as the base ref "
            "(BO-2400f-3: 'never from stale local main'). "
            f"Captured calls: {worktree_calls}",
        )


if __name__ == "__main__":
    unittest.main()
