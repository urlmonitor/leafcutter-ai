"""
MODULE: unit_tests/test_goal_to_epic.py
GOAL: Regression tests for BP-901 — goal_to_epic.py main() must NOT call
    _find_worktree_root() when both --store-root and --inbox-dir are supplied.
BUSINESS CONTEXT: goal_to_epic.py is deployed to .leafcutter/scripts/ac_store/
    (outside any git worktree). When the caller supplies both --store-root and
    --inbox-dir explicitly, walking the filesystem from __file__ to find .git
    raises FileNotFoundError and exits 1 even though the worktree root is never
    needed for path construction. The fix guards the _find_worktree_root() call
    behind a condition: it is only invoked when at least one default path is needed.
ARCHITECTURE: Uses unittest.mock.patch to substitute _find_worktree_root and run()
    so the test can assert call-count without performing real filesystem traversal
    or ticket generation. The AC-store root is materialised as a real tmp directory
    so main()'s existence-check passes. The test is import-safe: goal_to_epic.py
    has no module-level I/O side-effects (only path math at module scope).

DECISION HISTORY
- 2026-07-08 [BP-901/python-coder]: Initial implementation. GREEN because the
  fix is already applied in main(); this test is a regression guard against future
  regressions that re-introduce an unconditional _find_worktree_root() call.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import goal_to_epic


class TestMainSkipsWorktreeRootWhenBothPathsSupplied(unittest.TestCase):
    """BP-901: _find_worktree_root() must NOT be called when both
    --store-root and --inbox-dir are supplied on the command line."""

    def test_find_worktree_root_not_called_when_both_paths_explicit(
        self,
    ) -> None:
        # covers: BP-901
        """When both --store-root and --inbox-dir are explicit, _find_worktree_root()
        is never invoked — even though it would raise in a non-git tree.

        The fix in main() checks 'if args.store_root and args.inbox_dir' and
        takes the direct-path branch instead of the worktree-detection branch.
        """
        with tempfile.TemporaryDirectory() as tmp_root:
            store_root = Path(tmp_root) / "docs" / "acceptance-criteria"
            store_root.mkdir(parents=True)
            inbox_dir = Path(tmp_root) / "tickets" / "00_inbox"
            inbox_dir.mkdir(parents=True)

            with patch.object(goal_to_epic, "_find_worktree_root") as mock_fwr:
                with patch.object(
                    goal_to_epic, "run", return_value=Path(tmp_root)
                ):
                    result = goal_to_epic.main(
                        [
                            "--ac",
                            "ACD-001",
                            "--store-root",
                            str(store_root),
                            "--inbox-dir",
                            str(inbox_dir),
                        ]
                    )

        mock_fwr.assert_not_called()
        self.assertEqual(result, 0)

    def test_find_worktree_root_not_called_raises_does_not_crash_main(
        self,
    ) -> None:
        # covers: BP-901
        """If _find_worktree_root() were called and raised FileNotFoundError,
        it would exit 1. When both paths are explicit the guard prevents the call,
        so even a mocked raise-on-call implementation must not propagate.

        This test verifies the fix by making _find_worktree_root() unconditionally
        raise FileNotFoundError and asserting main() still returns 0.
        """
        with tempfile.TemporaryDirectory() as tmp_root:
            store_root = Path(tmp_root) / "docs" / "ac"
            store_root.mkdir(parents=True)
            inbox_dir = Path(tmp_root) / "tickets" / "00_inbox"
            inbox_dir.mkdir(parents=True)

            def _always_raise(start: Path) -> Path:
                raise FileNotFoundError(  # noqa: TRY003
                    "worktree root must not be needed when both paths are explicit"
                )

            with patch.object(
                goal_to_epic, "_find_worktree_root", side_effect=_always_raise
            ):
                with patch.object(goal_to_epic, "run", return_value=Path(tmp_root)):
                    result = goal_to_epic.main(
                        [
                            "--ac",
                            "ACD-001",
                            "--store-root",
                            str(store_root),
                            "--inbox-dir",
                            str(inbox_dir),
                        ]
                    )

        self.assertEqual(
            result,
            0,
            msg=(
                "main() returned non-zero even though both --store-root and "
                "--inbox-dir were supplied. This means _find_worktree_root() was "
                "called (and its FileNotFoundError propagated). BP-901 fix not active."
            ),
        )


class TestMainCallsWorktreeRootWhenPathsMissing(unittest.TestCase):
    """Negative test: _find_worktree_root() IS called when at least one
    path arg is absent, confirming the guard is conditional, not unconditional."""

    def test_find_worktree_root_called_when_no_paths_supplied(self) -> None:
        # covers: BP-901
        """Without explicit --store-root or --inbox-dir, main() enters the
        worktree-detection branch and calls _find_worktree_root().

        This verifies the guard is conditional: the protection only activates when
        BOTH args are present, not unconditionally.
        """
        with tempfile.TemporaryDirectory() as tmp_root:
            store_root = Path(tmp_root) / "docs" / "acceptance-criteria"
            store_root.mkdir(parents=True)
            inbox_dir = Path(tmp_root) / "tickets" / "00_inbox"
            inbox_dir.mkdir(parents=True)

            with patch.object(
                goal_to_epic, "_find_worktree_root", return_value=Path(tmp_root)
            ) as mock_fwr:
                with patch.object(goal_to_epic, "run", return_value=Path(tmp_root)):
                    result = goal_to_epic.main(["--ac", "ACD-001"])

        mock_fwr.assert_called_once()
        self.assertEqual(result, 0)

    def test_find_worktree_root_called_when_only_store_root_supplied(
        self,
    ) -> None:
        # covers: BP-901
        """When only --store-root is supplied (not --inbox-dir), _find_worktree_root()
        is called to derive the default --inbox-dir path."""
        with tempfile.TemporaryDirectory() as tmp_root:
            store_root = Path(tmp_root) / "docs" / "acceptance-criteria"
            store_root.mkdir(parents=True)
            inbox_dir = Path(tmp_root) / "tickets" / "00_inbox"
            inbox_dir.mkdir(parents=True)

            with patch.object(
                goal_to_epic, "_find_worktree_root", return_value=Path(tmp_root)
            ) as mock_fwr:
                with patch.object(goal_to_epic, "run", return_value=Path(tmp_root)):
                    result = goal_to_epic.main(
                        [
                            "--ac",
                            "ACD-001",
                            "--store-root",
                            str(store_root),
                            # --inbox-dir is absent → must call _find_worktree_root
                        ]
                    )

        mock_fwr.assert_called_once()
        self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
