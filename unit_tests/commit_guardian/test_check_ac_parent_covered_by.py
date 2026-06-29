"""
MODULE: test_check_ac_parent_covered_by
GOAL: Regression tests for check_ac_parent_covered_by.py, the pre-commit hook
    that blocks commits when a child AC's parent does not list it in covered_by.

Includes:
  - Correctness tests: violation detected when parent omits child; clean when
    parent includes child.
  - PERFORMANCE REGRESSION TEST: asserts the AC store is walked at most once
    regardless of how many staged files are checked. The current code calls
    _resolve_parent_file per staged file, which does a full rglob walk per call
    — O(staged_files × store_files). The fix must build an id→file index once
    and do O(1) lookups. This test FAILS against the unmodified hook (red) and
    PASSES after the index-once fix (green).

ARCHITECTURE: Tests call main() directly via importlib so no subprocess is
    needed. HOOK_TEST_FILES and HOOK_ROOT env vars are used for isolation.
    The full-store walk count is instrumented by patching Path.rglob and
    counting how many times the AC store rglob is invoked.

# covers: UNKNOWN
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HOOK_PATH = (
    _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_ac_parent_covered_by.py"
)

# ---------------------------------------------------------------------------
# Load the module under test via importlib (standalone file, no package import)
# ---------------------------------------------------------------------------
try:
    _MODULE_NAME = "check_ac_parent_covered_by_test_shim"
    _spec = importlib.util.spec_from_file_location(_MODULE_NAME, _HOOK_PATH)
    _mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
    sys.modules[_MODULE_NAME] = _mod
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]

    _check_file = _mod._check_file  # type: ignore[attr-defined]
    _resolve_parent_file = _mod._resolve_parent_file  # type: ignore[attr-defined]
    _get_derive_parent_id = _mod._get_derive_parent_id  # type: ignore[attr-defined]
    _main = _mod.main  # type: ignore[attr-defined]
    _IMPORT_OK = True
    _IMPORT_ERROR = ""
except (FileNotFoundError, AttributeError, ImportError, SyntaxError, TypeError, ValueError) as _exc:
    _IMPORT_OK = False
    _IMPORT_ERROR = str(_exc)


def _requires_import(func):
    """Skip test if the hook module failed to import."""
    if not _IMPORT_OK:
        return unittest.skip(
            f"check_ac_parent_covered_by not importable: {_IMPORT_ERROR}"
        )(func)
    return func


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_AC_STORE_REL = "docs/acceptance-criteria"


def _write_yaml(root: Path, rel_path: str, content: str) -> Path:
    """Write a YAML file under root, creating intermediate dirs.

    Args:
        root: Root of the temporary tree.
        rel_path: Path relative to root.
        content: YAML content.

    Returns:
        Absolute Path of the written file.
    """
    target = root / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def _parent_yaml(parent_id: str, covered_by: list[str]) -> str:
    """Return a minimal parent AC YAML string.

    Args:
        parent_id: The id of the parent AC (e.g. 'ACS-100a').
        covered_by: List of child AC IDs this parent covers.

    Returns:
        YAML string with the given id and covered_by list.
    """
    covered_list = "[" + ", ".join(covered_by) + "]"
    return (
        f"id: {parent_id}\n"
        f"title: \"Parent AC {parent_id}\"\n"
        f"component: test\n"
        f"level: L1\n"
        f"status: active\n"
        f"covered_by: {covered_list}\n"
        f"origin_agent: business-analyst-v3\n"
        f"amended_by: []\n"
    )


def _child_yaml(child_id: str, parent_id: str) -> str:
    """Return a minimal child AC YAML string with depends_on the parent.

    Args:
        child_id: The id of the child AC (e.g. 'ACS-100a-1').
        parent_id: The id of the parent AC (e.g. 'ACS-100a').

    Returns:
        YAML string with the given id and depends_on=[parent_id].
    """
    return (
        f"id: {child_id}\n"
        f"title: \"Child AC {child_id}\"\n"
        f"component: test\n"
        f"level: L2\n"
        f"status: active\n"
        f"depends_on: [{parent_id}]\n"
        f"origin_agent: business-analyst-v3\n"
        f"amended_by: []\n"
    )


# ---------------------------------------------------------------------------
# Correctness tests
# ---------------------------------------------------------------------------

class TestCorrectnessViolationDetected(unittest.TestCase):
    """When a parent's covered_by omits the child ID, the hook emits a violation."""

    @_requires_import
    def test_ac_perf_correctness_violation_when_child_missing_from_covered_by(self):
        # covers: UNKNOWN
        """A child AC staged whose parent covered_by does not list it → violation returned.

        This verifies the hook's core detection logic so that any perf fix cannot
        silently break correctness.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            # Parent lists no children in covered_by
            _write_yaml(
                tmp,
                f"{_AC_STORE_REL}/test/ACS-100a.yaml",
                _parent_yaml("ACS-100a", covered_by=[]),
            )
            # Child depends_on the parent but parent does not cover it
            child_path = _write_yaml(
                tmp,
                f"{_AC_STORE_REL}/test/ACS-100a-1.yaml",
                _child_yaml("ACS-100a-1", "ACS-100a"),
            )

            try:
                derive_parent_id = _get_derive_parent_id()
            except ImportError:
                self.skipTest("derive_parent_id not importable in this env")

            old_env = os.environ.copy()
            os.environ["HOOK_ROOT"] = tmpdir
            os.environ["HOOK_TEST_FILES"] = str(child_path)
            try:
                violations = _check_file(str(child_path), derive_parent_id)
            finally:
                os.environ.clear()
                os.environ.update(old_env)

            self.assertGreater(
                len(violations),
                0,
                "Expected a violation when parent's covered_by omits the child ID, "
                f"but got none. child=ACS-100a-1, parent=ACS-100a, violations={violations!r}",
            )
            self.assertIn(
                "ACS-100a-1",
                violations[0],
                "Violation message must name the child ID",
            )

    @_requires_import
    def test_ac_perf_correctness_no_violation_when_child_in_covered_by(self):
        # covers: UNKNOWN
        """A child AC staged whose parent covered_by lists it → no violation returned.

        Verifies the clean (green) path so that the perf fix cannot break it.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            # Parent lists the child in covered_by
            _write_yaml(
                tmp,
                f"{_AC_STORE_REL}/test/ACS-200a.yaml",
                _parent_yaml("ACS-200a", covered_by=["ACS-200a-1"]),
            )
            child_path = _write_yaml(
                tmp,
                f"{_AC_STORE_REL}/test/ACS-200a-1.yaml",
                _child_yaml("ACS-200a-1", "ACS-200a"),
            )

            try:
                derive_parent_id = _get_derive_parent_id()
            except ImportError:
                self.skipTest("derive_parent_id not importable in this env")

            old_env = os.environ.copy()
            os.environ["HOOK_ROOT"] = tmpdir
            os.environ["HOOK_TEST_FILES"] = str(child_path)
            try:
                violations = _check_file(str(child_path), derive_parent_id)
            finally:
                os.environ.clear()
                os.environ.update(old_env)

            self.assertEqual(
                violations,
                [],
                "Expected no violations when parent's covered_by includes the child, "
                f"but got: {violations!r}",
            )


# ---------------------------------------------------------------------------
# Performance regression test
# ---------------------------------------------------------------------------

class TestStoreWalkedAtMostOnce(unittest.TestCase):
    """PERFORMANCE REGRESSION: the AC store must be walked at most once.

    Against the CURRENT (unfixed) code, _resolve_parent_file calls
    ac_store_root.rglob('*.yaml') once per staged file, so with N staged files
    the store is walked N times. This test asserts the walk happens at most once
    regardless of how many staged files are processed, which FAILS (red) until
    the index-once fix is applied.

    Instrumentation: we patch Path.rglob at the module level inside check_ac_parent_covered_by
    and count calls whose argument is '*.yaml' on the AC store path. After the fix,
    the count should be <=1 (index built once, then re-used).
    """

    # Number of child AC files to stage in the batch test.
    # Large enough that the O(N) vs O(1) distinction is clear in counts.
    _N_STAGED_FILES = 8

    def _build_fixture(self, tmp: Path) -> tuple[list[str], Path]:
        """Create a parent AC + N child ACs in a temp AC store.

        All children depend_on the parent; the parent lists all of them in
        covered_by (so there are no violations — we only test the walk count).

        Args:
            tmp: Temporary directory to use as project root.

        Returns:
            Tuple of (list_of_child_absolute_paths, parent_yaml_path).
        """
        n = self._N_STAGED_FILES
        child_ids = [f"ACS-300a-{i}" for i in range(1, n + 1)]

        # Write the parent
        _write_yaml(
            tmp,
            f"{_AC_STORE_REL}/perf/ACS-300a.yaml",
            _parent_yaml("ACS-300a", covered_by=child_ids),
        )

        # Write 20 additional filler files to make the store non-trivially sized.
        # This ensures rglob is doing real work and the count is measurable.
        for j in range(1, 21):
            _write_yaml(
                tmp,
                f"{_AC_STORE_REL}/filler/ACS-900a-{j}.yaml",
                _child_yaml(f"ACS-900a-{j}", "ACS-900a"),
            )

        # Write all child files
        child_paths = []
        for child_id in child_ids:
            p = _write_yaml(
                tmp,
                f"{_AC_STORE_REL}/perf/{child_id}.yaml",
                _child_yaml(child_id, "ACS-300a"),
            )
            child_paths.append(str(p))

        return child_paths, tmp / _AC_STORE_REL / "perf" / "ACS-300a.yaml"

    @_requires_import
    def test_ac_perf_store_walked_at_most_once_for_batch_of_staged_files(self):
        # covers: UNKNOWN
        """PERFORMANCE REGRESSION: store rglob must be called at most once for a
        batch of N staged files, not once-per-staged-file.

        Current code: _resolve_parent_file calls ac_store_root.rglob('*.yaml')
        for every staged file → count == N (FAILS this test).

        After fix: index built once at the start of main() → count == 1 (or 0
        if the parent is located by path convention rather than a walk).

        The assertion:
            rglob_call_count <= 1

        This is the single-walk invariant. Against the current code, the count
        equals the number of staged files (8 in this test) → AssertionError.
        """
        n = self._N_STAGED_FILES

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            child_paths, _ = self._build_fixture(tmp)

            rglob_call_count = 0
            original_rglob = Path.rglob

            def counting_rglob(self_path, pattern, **kwargs):
                # covers: UNKNOWN
                nonlocal rglob_call_count
                # Only count rglob calls on the AC store directory (not on other dirs).
                ac_store_str = str(tmp / _AC_STORE_REL)
                if str(self_path).startswith(ac_store_str) and pattern == "*.yaml":
                    rglob_call_count += 1
                return original_rglob(self_path, pattern, **kwargs)

            old_env = os.environ.copy()
            os.environ["HOOK_ROOT"] = tmpdir
            os.environ["HOOK_TEST_FILES"] = os.pathsep.join(child_paths)
            os.environ.pop("HOOK_NO_GIT", None)

            try:
                with patch.object(Path, "rglob", counting_rglob):
                    _main()
            finally:
                os.environ.clear()
                os.environ.update(old_env)

            self.assertLessEqual(
                rglob_call_count,
                1,
                f"PERFORMANCE REGRESSION DETECTED: ac_store_root.rglob('*.yaml') was called "
                f"{rglob_call_count} times for {n} staged files. "
                f"Expected at most 1 call (index built once). "
                f"Current code walks the full store once per staged file (O(N) × O(store_size)), "
                f"which causes pre-commit timeouts on large AC stores. "
                f"Fix: build an id→file index in a single rglob pass at the start of main(), "
                f"then do O(1) dict lookups in _resolve_parent_file."
            )


class TestModuleImport(unittest.TestCase):
    """Verify the hook module exists and loads without import errors."""

    def test_hook_script_exists_at_template_path(self):
        # covers: UNKNOWN
        """The hook file must exist at templates/scripts/commit_guardian/check_ac_parent_covered_by.py."""
        self.assertTrue(
            _HOOK_PATH.exists(),
            f"Hook script not found at {_HOOK_PATH}. "
            "Ensure templates/scripts/commit_guardian/check_ac_parent_covered_by.py exists.",
        )

    def test_module_imports_successfully(self):
        # covers: UNKNOWN
        """Hook module must import without syntax errors or import failures."""
        self.assertTrue(
            _IMPORT_OK,
            f"Hook module failed to import: {_IMPORT_ERROR}",
        )


if __name__ == "__main__":
    unittest.main()
