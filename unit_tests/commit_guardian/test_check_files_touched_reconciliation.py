"""
MODULE: test_check_files_touched_reconciliation
GOAL: Unit tests for the generated-file and lockfile exemptions added in
    AC BP-1100e-1-i to check_files_touched_reconciliation.py.
BUSINESS CONTEXT: Verifies that out_of_scope entries, generated artifacts,
    and lock-files are never flagged as undeclared source changes, while
    genuinely undeclared source files are still caught.
ARCHITECTURE: Tests import the hook module dynamically via importlib so the
    tests remain independent of the package install path.  All tests exercise
    the pure helper functions (_is_generated_file, _is_lockfile) and the
    integration function (_compute_undeclared) directly — no git subprocess
    calls are made.
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
        "check_files_touched_reconciliation", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


_hook = _load_hook()


# ---------------------------------------------------------------------------
# Tests: _is_generated_file
# ---------------------------------------------------------------------------


class TestIsGeneratedFile(unittest.TestCase):
    """Tests for the _is_generated_file pure helper."""

    def test_generated_directory_segment_flagged(self) -> None:
        """A file under a 'generated/' directory segment is a generated file."""
        self.assertTrue(_hook._is_generated_file("scripts/generated/paths_index.py"))

    def test_double_underscore_generated_flagged(self) -> None:
        """A file under '__generated__/' is a generated file."""
        self.assertTrue(_hook._is_generated_file("src/__generated__/types.ts"))

    def test_hidden_generated_flagged(self) -> None:
        """A file under '.generated/' is a generated file."""
        self.assertTrue(_hook._is_generated_file(".generated/schema.py"))

    def test_dist_directory_flagged(self) -> None:
        """A file under 'dist/' is a generated artifact."""
        self.assertTrue(_hook._is_generated_file("dist/bundle.js"))

    def test_generated_stem_suffix_dot_flagged(self) -> None:
        """A filename containing '.generated.' is a generated file."""
        self.assertTrue(_hook._is_generated_file("src/schema.generated.ts"))

    def test_generated_stem_suffix_underscore_flagged(self) -> None:
        """A filename containing '_generated.' is a generated file."""
        self.assertTrue(_hook._is_generated_file("scripts/client_generated.py"))

    def test_regular_source_file_not_flagged(self) -> None:
        """A regular source file is NOT flagged as generated."""
        self.assertFalse(_hook._is_generated_file("scripts/build_phases.py"))

    def test_not_generated_substring_not_flagged(self) -> None:
        """A path containing 'generated' as a word-interior substring is NOT flagged.

        'not_generated/foo.py' should not match the '/generated/' segment marker.
        """
        self.assertFalse(_hook._is_generated_file("not_generated/foo.py"))

    def test_nested_regular_file_not_flagged(self) -> None:
        """A deeply nested regular .py file is NOT flagged as generated."""
        self.assertFalse(_hook._is_generated_file("src/api/v2/client.py"))


# ---------------------------------------------------------------------------
# Tests: _is_lockfile
# ---------------------------------------------------------------------------


class TestIsLockfile(unittest.TestCase):
    """Tests for the _is_lockfile pure helper."""

    def test_poetry_lock_flagged(self) -> None:
        """poetry.lock is a lockfile."""
        self.assertTrue(_hook._is_lockfile("poetry.lock"))

    def test_poetry_lock_nested_flagged(self) -> None:
        """poetry.lock nested in a subdirectory is still a lockfile."""
        self.assertTrue(_hook._is_lockfile("subproject/poetry.lock"))

    def test_package_lock_json_flagged(self) -> None:
        """package-lock.json is a lockfile."""
        self.assertTrue(_hook._is_lockfile("package-lock.json"))

    def test_yarn_lock_flagged(self) -> None:
        """yarn.lock is a lockfile."""
        self.assertTrue(_hook._is_lockfile("yarn.lock"))

    def test_pnpm_lock_yaml_flagged(self) -> None:
        """pnpm-lock.yaml is a lockfile."""
        self.assertTrue(_hook._is_lockfile("pnpm-lock.yaml"))

    def test_uv_lock_flagged(self) -> None:
        """uv.lock is a lockfile."""
        self.assertTrue(_hook._is_lockfile("uv.lock"))

    def test_go_sum_flagged(self) -> None:
        """go.sum is a lockfile."""
        self.assertTrue(_hook._is_lockfile("go.sum"))

    def test_cargo_lock_flagged(self) -> None:
        """Cargo.lock is a lockfile."""
        self.assertTrue(_hook._is_lockfile("Cargo.lock"))

    def test_regular_py_file_not_flagged(self) -> None:
        """A regular .py file is NOT a lockfile."""
        self.assertFalse(_hook._is_lockfile("scripts/build.py"))

    def test_regular_json_file_not_flagged(self) -> None:
        """A regular .json config file is NOT a lockfile."""
        self.assertFalse(_hook._is_lockfile("config/settings.json"))


# ---------------------------------------------------------------------------
# Tests: _compute_undeclared (integration — AC BP-1100e-1-i scenarios)
# ---------------------------------------------------------------------------


class TestComputeUndeclared(unittest.TestCase):
    """Tests for _compute_undeclared exercising AC BP-1100e-1-i scenarios."""

    def _call(
        self,
        declared: set[str],
        branch: frozenset[str],
        staged: list[str],
    ) -> list[str]:
        """Thin wrapper so test bodies stay concise."""
        return _hook._compute_undeclared(declared, branch, staged)

    # --- AC scenario: out_of_scope entries are not flagged ---

    def test_out_of_scope_file_not_flagged(self) -> None:
        """A file declared in out_of_scope (in declared set) is NOT flagged.

        The declared set is files_touched UNION out_of_scope, so
        'scripts/legacy_shim.py' in out_of_scope must not appear as undeclared.
        """
        declared = {
            "scripts/build_phases.py",
            "scripts/legacy_shim.py",  # out_of_scope entry
        }
        branch = frozenset({"scripts/legacy_shim.py"})
        result = self._call(declared, branch, [])
        self.assertEqual(result, [])

    # --- AC scenario: lockfiles are not flagged ---

    def test_lockfile_not_flagged(self) -> None:
        """poetry.lock is not flagged even when it appears in the branch diff."""
        declared: set[str] = {"scripts/build_phases.py"}
        branch = frozenset({"poetry.lock"})
        result = self._call(declared, branch, [])
        self.assertEqual(result, [])

    def test_package_lock_not_flagged(self) -> None:
        """package-lock.json is not flagged even when changed."""
        declared: set[str] = {"src/index.ts"}
        branch = frozenset({"package-lock.json"})
        result = self._call(declared, branch, [])
        self.assertEqual(result, [])

    # --- AC scenario: generated files are not flagged ---

    def test_generated_directory_file_not_flagged(self) -> None:
        """A .py file under scripts/generated/ is not flagged as undeclared."""
        declared: set[str] = {"scripts/build_phases.py"}
        branch = frozenset({"scripts/generated/paths_index.py"})
        result = self._call(declared, branch, [])
        self.assertEqual(result, [])

    def test_generated_stem_file_not_flagged(self) -> None:
        """A .ts file with a .generated. stem is not flagged as undeclared."""
        declared: set[str] = {"src/api.ts"}
        branch = frozenset({"src/schema.generated.ts"})
        result = self._call(declared, branch, [])
        self.assertEqual(result, [])

    # --- AC scenario: genuine undeclared sources ARE still flagged ---

    def test_undeclared_source_is_flagged(self) -> None:
        """A real source file absent from the declared set IS flagged."""
        declared: set[str] = {"scripts/build_phases.py"}
        branch = frozenset({"scripts/new_module.py"})
        result = self._call(declared, branch, [])
        self.assertEqual(result, ["scripts/new_module.py"])

    def test_declared_source_not_flagged(self) -> None:
        """A source file present in the declared set is NOT flagged."""
        declared: set[str] = {"scripts/build_phases.py"}
        branch = frozenset({"scripts/build_phases.py"})
        result = self._call(declared, branch, [])
        self.assertEqual(result, [])

    # --- Full AC scenario: all three exemption types together ---

    def test_full_ac_scenario(self) -> None:
        """AC BP-1100e-1-i: combined exemptions + a genuine undeclared file.

        Changed files:
          - scripts/legacy_shim.py  (out_of_scope → not flagged)
          - poetry.lock             (lockfile → not flagged)
          - scripts/generated/paths_index.py  (generated → not flagged)
          - scripts/sneaky_new.py   (undeclared source → FLAGGED)
        """
        declared = {
            "scripts/build_phases.py",
            "scripts/legacy_shim.py",
        }
        branch = frozenset({
            "scripts/legacy_shim.py",
            "poetry.lock",
            "scripts/generated/paths_index.py",
            "scripts/sneaky_new.py",
        })
        result = self._call(declared, branch, [])
        self.assertEqual(result, ["scripts/sneaky_new.py"])

    def test_staged_files_included_in_computation(self) -> None:
        """Files in staged_files (not in branch diff) are still checked."""
        declared: set[str] = {"scripts/build_phases.py"}
        branch: frozenset[str] = frozenset()
        staged = ["scripts/another_undeclared.py"]
        result = self._call(declared, branch, staged)
        self.assertEqual(result, ["scripts/another_undeclared.py"])

    def test_no_changed_files_returns_empty(self) -> None:
        """Empty branch diff + no staged files → empty result."""
        declared: set[str] = {"scripts/build_phases.py"}
        result = self._call(declared, frozenset(), [])
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
