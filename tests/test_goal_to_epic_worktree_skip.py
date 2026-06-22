"""
MODULE: test_goal_to_epic_worktree_skip
GOAL: Regression test for BP-901 — main() must NOT call _find_worktree_root()
    when both --store-root and --inbox-dir are supplied explicitly, because the
    worktree value is only needed to construct the default paths.

BUSINESS CONTEXT: When goal_to_epic.py is deployed to .leafcutter/scripts/
    (a location outside any git worktree) the unconditional call to
    _find_worktree_root(Path(__file__)) raises FileNotFoundError and exits 1,
    even though the caller has provided both explicit paths. This test will be
    RED against the unmodified code and GREEN after the conditional-call fix.

ARCHITECTURE: Pure unit test using unittest.TestCase + unittest.mock.
    No database. No network. No filesystem writes beyond tempfile.
    Must complete in < 5 seconds.

Tests in this file:
  - test_ac_bp901_main_skips_worktree_when_both_paths_supplied
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Bootstrap: add scripts/ to sys.path so goal_to_epic can be imported.
# goal_to_epic imports from sibling scripts (scan_ac_store, etc.) at runtime,
# but those imports happen inside run() — not at module load time — so just
# putting scripts/ on the path is sufficient for tests that stub run().
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_GOAL_TO_EPIC_PATH = _SCRIPTS_DIR / "goal_to_epic.py"


def _load_goal_to_epic():
    """Load goal_to_epic from scripts/ into sys.modules (idempotent)."""
    if str(_SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_DIR))

    module_name = "goal_to_epic"
    if module_name in sys.modules:
        return sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, _GOAL_TO_EPIC_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMainSkipsWorktreeWhenBothPathsSupplied(unittest.TestCase):
    """BP-901: main() must not resolve the worktree when both CLI paths are given.

    Simulates a deployment of goal_to_epic.py outside the git tree by
    monkeypatching _find_worktree_root to raise FileNotFoundError — the exact
    error that occurs when no .git marker is found walking upward.

    Because both --store-root and --inbox-dir are supplied explicitly, main()
    should proceed to run() without ever touching the worktree resolver.
    """

    def setUp(self) -> None:
        self._goal_to_epic = _load_goal_to_epic()
        # A temporary directory stands in for both the AC store root and the
        # tickets inbox.  Using a real directory avoids the ac_store_root.exists()
        # guard inside main() from rejecting the path.
        self._tmp = tempfile.TemporaryDirectory()
        self._tmp_path = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ac_bp901_main_skips_worktree_when_both_paths_supplied(self) -> None:
        # covers: BP-901
        """AC BP-901: main() must NOT call _find_worktree_root when --store-root
        and --inbox-dir are both supplied, even when the script lives outside
        a git tree (i.e. _find_worktree_root would raise FileNotFoundError).

        Symptom being reproduced: on unpatched code, main() calls
        _find_worktree_root(Path(__file__)) unconditionally at line ~1711,
        which raises FileNotFoundError and exits 1 before the user-supplied
        paths are ever used.

        Fix target: defer/condition the _find_worktree_root() call so it only
        executes when at least one of --store-root / --inbox-dir is absent.
        """
        goal_to_epic = self._goal_to_epic

        # Arrange — stub _find_worktree_root to raise, simulating a deployment
        # path that has no .git ancestor.
        worktree_raiser = MagicMock(
            side_effect=FileNotFoundError(
                "Could not locate worktree root from /opt/deployed/scripts/goal_to_epic.py"
            )
        )

        # Arrange — stub run() so the test stays fast and isolated.
        # We will inspect its call arguments to confirm the supplied paths
        # were forwarded correctly.
        run_stub = MagicMock(return_value=self._tmp_path / "EPIC-Stub")

        with patch.object(goal_to_epic, "_find_worktree_root", worktree_raiser):
            with patch.object(goal_to_epic, "run", run_stub):
                # Act — pass both explicit paths so worktree resolution is unnecessary.
                exit_code = goal_to_epic.main(
                    [
                        "--ac", "GOAL-001",
                        "--store-root", str(self._tmp_path),
                        "--inbox-dir", str(self._tmp_path),
                    ]
                )

        # Assert 1: main() must return 0 (not exit 1 due to FileNotFoundError).
        self.assertEqual(
            exit_code,
            0,
            msg=(
                "main() returned non-zero. "
                "The worktree resolver raised FileNotFoundError even though "
                "--store-root and --inbox-dir were both supplied. "
                "Fix: defer _find_worktree_root() so it only runs when a "
                "default path is actually needed (BP-901)."
            ),
        )

        # Assert 2: _find_worktree_root must NOT have been called.
        # (Once the fix lands, the call is skipped entirely.)
        # This assertion documents the intended contract; it will fail on current
        # code because the call happens unconditionally (and raises, causing exit 1).
        worktree_raiser.assert_not_called()

        # Assert 3: run() must have been called exactly once with the supplied paths.
        run_stub.assert_called_once()
        call_kwargs = run_stub.call_args
        # Support both positional and keyword argument styles.
        supplied_store_root = (
            call_kwargs.kwargs.get("ac_store_root")
            or (call_kwargs.args[1] if len(call_kwargs.args) > 1 else None)
        )
        supplied_inbox_dir = (
            call_kwargs.kwargs.get("inbox_dir")
            or (call_kwargs.args[2] if len(call_kwargs.args) > 2 else None)
        )
        self.assertEqual(
            Path(supplied_store_root),
            self._tmp_path,
            msg="run() was not called with the --store-root value passed to main().",
        )
        self.assertEqual(
            Path(supplied_inbox_dir),
            self._tmp_path,
            msg="run() was not called with the --inbox-dir value passed to main().",
        )


if __name__ == "__main__":
    unittest.main()
