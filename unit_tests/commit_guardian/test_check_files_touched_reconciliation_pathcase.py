"""
MODULE: test_check_files_touched_reconciliation_pathcase
GOAL: Unit tests for case-folding path normalisation added in AC BP-1100e-1-ii
    to check_files_touched_reconciliation.py.
BUSINESS CONTEXT: Verifies that paths differing only by case are treated as
    matching on case-insensitive filesystems (NTFS/APFS via git core.ignoreCase),
    and correctly treated as distinct on case-sensitive filesystems (Linux ext4).
    Also verifies that backslash separator normalisation and case-folding compose
    correctly when both apply simultaneously.
ARCHITECTURE: Tests import the hook module dynamically via importlib so they
    remain independent of the package install path.  _is_case_insensitive_fs()
    is monkey-patched on the loaded module object to avoid subprocess calls.
    _FS_CASE_INSENSITIVE is reset between tests to prevent cache bleed-through.
"""

from __future__ import annotations

import importlib.util
import types
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Module loader
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = (
    REPO_ROOT
    / "templates"
    / "scripts"
    / "commit_guardian"
    / "hooks"
    / "check_files_touched_reconciliation.py"
)


def _load_hook() -> types.ModuleType:
    """Dynamically load the hook module from its template path.

    Returns:
        Loaded module object.

    Raises:
        ImportError: When the hook script does not exist.
    """
    if not HOOK_PATH.exists():
        msg = f"Hook not found at {HOOK_PATH}. Implement it (python-coder phase)."
        raise ImportError(msg)
    spec = importlib.util.spec_from_file_location(
        "check_files_touched_reconciliation_pathcase", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


_hook = _load_hook()


# ---------------------------------------------------------------------------
# Tests: _normalise_path with case-folding
# ---------------------------------------------------------------------------


class TestNormalisePathCaseFolding(unittest.TestCase):
    """Tests for case-folding in _normalise_path (AC BP-1100e-1-ii).

    Each test monkey-patches _is_case_insensitive_fs on the loaded module
    to control the filesystem detection result without spawning subprocess calls.
    """

    def setUp(self) -> None:
        """Save original function and reset the FS cache before each test."""
        self._original_fn = _hook._is_case_insensitive_fs
        _hook._FS_CASE_INSENSITIVE = None

    def tearDown(self) -> None:
        """Restore original function and reset FS cache after each test."""
        _hook._is_case_insensitive_fs = self._original_fn
        _hook._FS_CASE_INSENSITIVE = None

    def _patch_fs_case(self, is_case_insensitive: bool) -> None:
        """Replace _is_case_insensitive_fs with a lambda returning a fixed value.

        Args:
            is_case_insensitive: Value to return from the patched function.
        """
        _hook._is_case_insensitive_fs = lambda: is_case_insensitive

    # --- Case-insensitive filesystem ---

    def test_same_path_different_case_lowercased_on_case_insensitive_fs(self) -> None:
        """On a case-insensitive FS, 'Scripts/Build_Phases.py' normalises to lowercase.

        Both the directory component ('Scripts' -> 'scripts') and the filename
        component ('Build_Phases.py' -> 'build_phases.py') must be lowercased.
        """
        self._patch_fs_case(True)
        result = _hook._normalise_path("Scripts/Build_Phases.py")
        self.assertEqual(result, "scripts/build_phases.py")

    def test_already_lowercase_path_unchanged_on_case_insensitive_fs(self) -> None:
        """A path already in lowercase normalises identically on any FS."""
        self._patch_fs_case(True)
        result = _hook._normalise_path("scripts/build_phases.py")
        self.assertEqual(result, "scripts/build_phases.py")

    def test_backslash_with_different_case_normalises_on_case_insensitive_fs(
        self,
    ) -> None:
        """On case-insensitive FS, backslash separator + case difference both normalise.

        'Scripts\\Build_Phases.py' must first have backslashes converted to forward
        slashes and then be lowercased, yielding 'scripts/build_phases.py'.
        """
        self._patch_fs_case(True)
        result = _hook._normalise_path("Scripts\\Build_Phases.py")
        self.assertEqual(result, "scripts/build_phases.py")

    def test_leading_dot_slash_stripped_and_lowercased_on_case_insensitive_fs(
        self,
    ) -> None:
        """Leading ./ is stripped and remaining path is lowercased on case-insensitive FS."""
        self._patch_fs_case(True)
        result = _hook._normalise_path("./Scripts/Build_Phases.py")
        self.assertEqual(result, "scripts/build_phases.py")

    # --- Case-sensitive filesystem ---

    def test_different_case_path_preserves_case_on_case_sensitive_fs(self) -> None:
        """On a case-sensitive FS, 'Scripts/Build_Phases.py' keeps its original case.

        The path must NOT be lowercased, so it will NOT match the declared
        lowercase entry 'scripts/build_phases.py'.
        """
        self._patch_fs_case(False)
        result = _hook._normalise_path("Scripts/Build_Phases.py")
        self.assertEqual(result, "Scripts/Build_Phases.py")

    def test_lowercase_path_unchanged_on_case_sensitive_fs(self) -> None:
        """A lowercase path normalises identically on case-sensitive FS."""
        self._patch_fs_case(False)
        result = _hook._normalise_path("scripts/build_phases.py")
        self.assertEqual(result, "scripts/build_phases.py")

    def test_backslash_converted_but_case_preserved_on_case_sensitive_fs(
        self,
    ) -> None:
        """On case-sensitive FS, backslashes are converted but case is preserved."""
        self._patch_fs_case(False)
        result = _hook._normalise_path("Scripts\\Build_Phases.py")
        self.assertEqual(result, "Scripts/Build_Phases.py")


# ---------------------------------------------------------------------------
# Tests: _compute_undeclared with case-folding (integration)
# ---------------------------------------------------------------------------


class TestComputeUndeclaredCaseFolding(unittest.TestCase):
    """Integration tests for _compute_undeclared with case-folding (BP-1100e-1-ii).

    Each test verifies that the declared-scope comparison inside _compute_undeclared
    correctly treats case-different paths as matching/non-matching depending on
    the detected filesystem type.
    """

    def setUp(self) -> None:
        """Save original function and reset FS cache before each test."""
        self._original_fn = _hook._is_case_insensitive_fs
        _hook._FS_CASE_INSENSITIVE = None

    def tearDown(self) -> None:
        """Restore original function and reset FS cache after each test."""
        _hook._is_case_insensitive_fs = self._original_fn
        _hook._FS_CASE_INSENSITIVE = None

    def _patch_fs_case(self, is_case_insensitive: bool) -> None:
        """Replace _is_case_insensitive_fs with a lambda returning a fixed value.

        Args:
            is_case_insensitive: Value to return from the patched function.
        """
        _hook._is_case_insensitive_fs = lambda: is_case_insensitive

    def _declared(self, *paths: str) -> set[str]:
        """Build a normalised declared set from raw path strings.

        Args:
            paths: Raw path strings as they would appear in files_touched.

        Returns:
            Set of normalised path strings.
        """
        return {_hook._normalise_path(p) for p in paths}

    # --- Case-insensitive FS: case-different paths must NOT be flagged ---

    def test_case_different_path_matches_declared_on_case_insensitive_fs(
        self,
    ) -> None:
        """On case-insensitive FS, 'Scripts/Build_Phases.py' matches 'scripts/build_phases.py'.

        The actual diff reports 'Scripts/Build_Phases.py' (NTFS/APFS casing).
        The ticket declares 'scripts/build_phases.py'.  The reconciliation must
        treat them as the same file and NOT flag the path as undeclared.
        """
        self._patch_fs_case(True)
        declared = self._declared("scripts/build_phases.py")
        branch = frozenset({"Scripts/Build_Phases.py"})
        result = _hook._compute_undeclared(declared, branch, [])
        self.assertEqual(result, [])

    def test_backslash_and_case_both_match_on_case_insensitive_fs(self) -> None:
        """On case-insensitive FS, backslash separator + case difference both normalise.

        'Scripts\\Build_Phases.py' (Windows NTFS path from git output) must
        match declared 'scripts/build_phases.py' after both separator and case
        normalisation.
        """
        self._patch_fs_case(True)
        declared = self._declared("scripts/build_phases.py")
        branch = frozenset({"Scripts\\Build_Phases.py"})
        result = _hook._compute_undeclared(declared, branch, [])
        self.assertEqual(result, [])

    def test_staged_file_with_different_case_matches_on_case_insensitive_fs(
        self,
    ) -> None:
        """On case-insensitive FS, a staged file with different case still matches."""
        self._patch_fs_case(True)
        declared = self._declared("scripts/build_phases.py")
        staged = ["Scripts/Build_Phases.py"]
        result = _hook._compute_undeclared(declared, frozenset(), staged)
        self.assertEqual(result, [])

    # --- Case-sensitive FS: case-different paths must still be flagged ---

    def test_case_different_path_flagged_on_case_sensitive_fs(self) -> None:
        """On case-sensitive FS, 'Scripts/Build_Phases.py' does NOT match 'scripts/build_phases.py'.

        The paths have different cases and the filesystem treats them as distinct.
        The reconciliation must flag 'Scripts/Build_Phases.py' as undeclared.
        """
        self._patch_fs_case(False)
        declared = self._declared("scripts/build_phases.py")
        branch = frozenset({"Scripts/Build_Phases.py"})
        result = _hook._compute_undeclared(declared, branch, [])
        self.assertEqual(result, ["Scripts/Build_Phases.py"])

    def test_exact_case_match_not_flagged_on_case_sensitive_fs(self) -> None:
        """On case-sensitive FS, an exact case match is still not flagged."""
        self._patch_fs_case(False)
        declared = self._declared("scripts/build_phases.py")
        branch = frozenset({"scripts/build_phases.py"})
        result = _hook._compute_undeclared(declared, branch, [])
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
