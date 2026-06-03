"""
Tests for check_ticket_no_branch_move.py.

These are TDD stubs written BEFORE python-coder implements the hook.
All new tests in this file are expected to be RED (failing) until python-coder
creates templates/hooks/check_ticket_no_branch_move.py with the full
implementation.

Tests use unittest.mock.patch to avoid filesystem or subprocess calls.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parent.parent
_HOOK_PATH = _REPO_ROOT / "templates" / "hooks" / "check_ticket_no_branch_move.py"


def _load_hook_module():
    """Load check_ticket_no_branch_move from its absolute path."""
    hooks_dir = str(_REPO_ROOT / "templates" / "hooks")
    if hooks_dir not in sys.path:
        sys.path.insert(0, hooks_dir)
    spec = importlib.util.spec_from_file_location(
        "check_ticket_no_branch_move", _HOOK_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_ticket_no_branch_move"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestBlocksTicketRenameOnFeatureBranch(unittest.TestCase):
    """Hook blocks ticket renames on non-main branches."""

    def test_blocks_ticket_rename_on_feature_branch(self):
        """
        Given a non-main branch,
         And the staged index contains a rename of a ticket file,
        When main() is called,
        Then the process exits with code 1
         And the output includes "no-branch-ticket-move".
        """
        mod = _load_hook_module()

        with (
            patch.object(mod, "_current_branch", return_value="feature/my-branch"),
            patch.object(
                mod,
                "_get_staged_renames",
                return_value=[
                    ("tickets/00_inbox/T.md", "tickets/01_todo/T.md"),
                ],
            ),
            self.assertRaises(SystemExit) as cm,
            patch("builtins.print") as mock_print,
        ):
            mod.main()

        self.assertEqual(cm.exception.code, 1)
        printed = " ".join(str(a) for call in mock_print.call_args_list for a in call[0])
        self.assertIn("no-branch-ticket-move", printed)


class TestAllowsTicketRenameOnMain(unittest.TestCase):
    """Hook allows ticket renames on the main branch."""

    def test_allows_ticket_rename_on_main(self):
        """
        Given the main branch,
         And the staged index contains a rename of a ticket file,
        When main() is called,
        Then the process exits with code 0.
        """
        mod = _load_hook_module()

        with (
            patch.object(mod, "_current_branch", return_value="main"),
            patch.object(
                mod,
                "_get_staged_renames",
                return_value=[
                    ("tickets/00_inbox/T.md", "tickets/01_todo/T.md"),
                ],
            ),
        ):
            try:
                mod.main()
            except SystemExit as exc:
                self.assertEqual(exc.code, 0)


class TestAllowsNonTicketRenameOnFeatureBranch(unittest.TestCase):
    """Hook allows non-ticket renames on non-main branches."""

    def test_allows_non_ticket_rename_on_feature_branch(self):
        """
        Given a non-main branch,
         And the staged index contains renames of non-ticket files,
        When main() is called,
        Then the process exits with code 0.
        """
        mod = _load_hook_module()

        with (
            patch.object(mod, "_current_branch", return_value="feature/my-branch"),
            patch.object(
                mod,
                "_get_staged_renames",
                return_value=[
                    ("docs/README.md", "docs/GUIDE.md"),
                ],
            ),
        ):
            try:
                mod.main()
            except SystemExit as exc:
                self.assertEqual(exc.code, 0)


class TestAllowsNoRenames(unittest.TestCase):
    """Hook exits 0 when no renames are staged."""

    def test_allows_no_renames(self):
        """
        Given a non-main branch,
         And the staged index has no renames,
        When main() is called,
        Then the process exits with code 0.
        """
        mod = _load_hook_module()

        with (
            patch.object(mod, "_current_branch", return_value="feature/my-branch"),
            patch.object(mod, "_get_staged_renames", return_value=[]),
        ):
            try:
                mod.main()
            except SystemExit as exc:
                self.assertEqual(exc.code, 0)


class TestBlocksOnMasterBranchRename(unittest.TestCase):
    """Hook blocks ticket renames on branches other than main/master."""

    def test_blocks_on_non_main_branch_rename_to_done(self):
        """
        Given a branch named 'not-main',
         And the staged index contains a rename with destination in tickets/99_done/,
        When main() is called,
        Then the process exits with code 1.
        """
        mod = _load_hook_module()

        with (
            patch.object(mod, "_current_branch", return_value="not-main"),
            patch.object(
                mod,
                "_get_staged_renames",
                return_value=[
                    (
                        "tickets/01_todo/T.md",
                        "tickets/99_done/T.md",
                    ),
                ],
            ),
            self.assertRaises(SystemExit) as cm,
            patch("builtins.print"),
        ):
            mod.main()

        self.assertEqual(cm.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
