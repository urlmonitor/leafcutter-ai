"""
MODULE: test_check_components_merge_guard
GOAL: Unit tests for the merge-in-progress guard added to
      check_components_integrity.py per ACS-300g-5.
BUSINESS CONTEXT: Verifies that the hook exits 0 immediately when MERGE_HEAD is
      present (a git merge is in progress) and that it still runs the full
      new-component existence check for normal (non-merge) commits. This prevents
      false-positive "new component" failures during merge commits where merged-in
      components are legitimately absent from the current HEAD's components.json.
ARCHITECTURE: Tests mock subprocess.run to control the MERGE_HEAD return code
      without requiring a real git repository. _is_merge_in_progress and main()
      are imported directly from the deployed hook script via importlib to keep
      tests fast and deterministic.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

HOOK_SCRIPT = (
    Path(__file__).parent.parent.parent
    / "scripts"
    / "commit_guardian"
    / "check_components_integrity.py"
)


def _load_module():
    """Load check_components_integrity as a module without executing main()."""
    spec = importlib.util.spec_from_file_location(
        "check_components_integrity", HOOK_SCRIPT
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Load once at import time for performance.
try:
    _mod = _load_module()
    MODULE_AVAILABLE = True
    _load_error = ""
except Exception as exc:  # noqa: BLE001 — discovery error, not runtime error
    MODULE_AVAILABLE = False
    _load_error = str(exc)


def _make_subprocess_result(returncode: int) -> MagicMock:
    """Build a mock CompletedProcess with the given returncode."""
    mock_result = MagicMock()
    mock_result.returncode = returncode
    return mock_result


@unittest.skipUnless(
    MODULE_AVAILABLE, f"module load failed: {_load_error}"
)
class TestIsMergeInProgress(unittest.TestCase):
    """Tests for the _is_merge_in_progress() helper function."""

    def test_returns_true_when_merge_head_exists(self):
        """When git rev-parse exits 0 (MERGE_HEAD found), returns True."""
        with patch(
            "subprocess.run", return_value=_make_subprocess_result(0)
        ) as mock_run:
            result = _mod._is_merge_in_progress()

        self.assertTrue(result)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertIn("MERGE_HEAD", args)

    def test_returns_false_when_no_merge_head(self):
        """When git rev-parse exits non-zero (no MERGE_HEAD), returns False."""
        with patch(
            "subprocess.run", return_value=_make_subprocess_result(1)
        ):
            result = _mod._is_merge_in_progress()

        self.assertFalse(result)

    def test_returns_false_when_git_not_found(self):
        """When git is not found (OSError), returns False without raising."""
        with patch("subprocess.run", side_effect=OSError("git not found")):
            import warnings

            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                result = _mod._is_merge_in_progress()

        self.assertFalse(result)
        # A RuntimeWarning must have been emitted
        runtime_warnings = [w for w in caught if issubclass(w.category, RuntimeWarning)]
        self.assertTrue(
            runtime_warnings,
            "Expected a RuntimeWarning to be emitted when git is not found",
        )

    def test_returncode_128_is_not_merge(self):
        """git rev-parse exits 128 for invalid ref — not a merge."""
        with patch(
            "subprocess.run", return_value=_make_subprocess_result(128)
        ):
            result = _mod._is_merge_in_progress()

        self.assertFalse(result)


@unittest.skipUnless(
    MODULE_AVAILABLE, f"module load failed: {_load_error}"
)
class TestMainMergeGuard(unittest.TestCase):
    """Tests for the merge guard path in main()."""

    def test_main_exits_0_when_merge_in_progress(self):
        """main() returns 0 immediately when a merge is in progress."""
        with patch.object(_mod, "_is_merge_in_progress", return_value=True):
            # _is_components_json_staged must NOT be called (merge guard fires first)
            with patch.object(
                _mod, "_is_components_json_staged"
            ) as mock_staged:
                exit_code = _mod.main()

        self.assertEqual(exit_code, 0)
        mock_staged.assert_not_called()

    def test_main_prints_merge_message_when_merge_in_progress(self):
        """main() prints the merge-skip message when MERGE_HEAD is present."""
        with patch.object(_mod, "_is_merge_in_progress", return_value=True):
            with patch("builtins.print") as mock_print:
                _mod.main()

        printed = " ".join(str(a) for call in mock_print.call_args_list for a in call[0])
        self.assertIn("merge in progress", printed)

    def test_main_proceeds_to_full_check_when_no_merge(self):
        """main() calls _is_components_json_staged when no merge is active."""
        with patch.object(_mod, "_is_merge_in_progress", return_value=False):
            with patch.object(
                _mod, "_is_components_json_staged", return_value=False
            ) as mock_staged:
                exit_code = _mod.main()

        self.assertEqual(exit_code, 0)
        mock_staged.assert_called_once()

    def test_main_blocks_new_component_when_no_merge(self):
        """On a normal commit with a new invalid component, main() returns 1."""
        # Simulate: no merge, components.json staged, new component added
        # with a missing detail_ref
        fake_before = '{"components": {}}'
        fake_after = '{"components": {"new_comp": {"detail_ref": null}}}'

        with patch.object(_mod, "_is_merge_in_progress", return_value=False):
            with patch.object(
                _mod, "_is_components_json_staged", return_value=True
            ):
                with patch.object(
                    _mod, "_git_show", side_effect=[fake_before, fake_after]
                ):
                    exit_code = _mod.main()

        self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
