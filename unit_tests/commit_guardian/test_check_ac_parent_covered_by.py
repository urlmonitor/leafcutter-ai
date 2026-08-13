"""
MODULE: test_check_ac_parent_covered_by
GOAL: Regression tests for check_ac_parent_covered_by.py, the pre-commit hook
    that blocks commits when a child AC's parent does not list it in covered_by.

Includes:
  - Correctness tests: violation detected when parent omits child; clean when
    parent includes child.
  - PERFORMANCE REGRESSION TEST: asserts the AC store is walked exactly once
    regardless of how many staged files are checked. The current code calls
    _resolve_parent_file per staged file, which does a full rglob walk per call
    — O(staged_files × store_files). The fix must build an id→file index once
    and do O(1) lookups. This test FAILS against the unmodified hook (red) and
    PASSES after the index-once fix (green).

ARCHITECTURE: Tests call main() directly via importlib so no subprocess is
    needed. HOOK_TEST_FILES and HOOK_ROOT env vars are used for isolation.
    The full-store walk count is instrumented by patching Path.rglob and
    counting how many times the AC store rglob is invoked.

Performance-regression guard for check-ac-parent-covered-by — no formal AC.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Repo root and hook path — derived from THIS file's location so resolution is
# stable regardless of pytest's cwd.
# parents[0] = unit_tests/commit_guardian/
# parents[1] = unit_tests/
# parents[2] = worktree root  (contains scripts/, templates/, etc.)
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
_HOOK_PATH = (
    _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_ac_parent_covered_by.py"
)

# ---------------------------------------------------------------------------
# Deterministic import of derive_parent_id — resolved from the known worktree
# path, independent of pytest cwd or sys.path order.
# ---------------------------------------------------------------------------
_AC_PARENT_ID_PATH = _REPO_ROOT / "scripts" / "ac_store" / "ac_parent_id.py"

if not _AC_PARENT_ID_PATH.exists():
    raise ImportError(
        f"ac_parent_id.py not found at {_AC_PARENT_ID_PATH}. "
        "Check that the worktree root is correctly computed from __file__."
    )

_ac_parent_id_spec = importlib.util.spec_from_file_location(
    "ac_parent_id_test_shim", str(_AC_PARENT_ID_PATH)
)
_ac_parent_id_mod = importlib.util.module_from_spec(_ac_parent_id_spec)  # type: ignore[arg-type]
_ac_parent_id_spec.loader.exec_module(_ac_parent_id_mod)  # type: ignore[union-attr]
_derive_parent_id = _ac_parent_id_mod.derive_parent_id

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
        """A child AC staged whose parent covered_by does not list it → violation returned.

        This verifies the hook's core detection logic so that any perf fix cannot
        silently break correctness.

        Uses _derive_parent_id imported deterministically from the worktree's own
        scripts/ac_store/ac_parent_id.py — no cwd dependency, no skipTest fallback.
        """
        # covers: ACS-100i-2
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

            old_env = os.environ.copy()
            os.environ["HOOK_ROOT"] = tmpdir
            os.environ["HOOK_TEST_FILES"] = str(child_path)
            try:
                violations = _check_file(str(child_path), _derive_parent_id)
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
        """A child AC staged whose parent covered_by lists it → no violation returned.

        Verifies the clean (green) path so that the perf fix cannot break it.

        Uses _derive_parent_id imported deterministically from the worktree's own
        scripts/ac_store/ac_parent_id.py — no cwd dependency, no skipTest fallback.
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

            old_env = os.environ.copy()
            os.environ["HOOK_ROOT"] = tmpdir
            os.environ["HOOK_TEST_FILES"] = str(child_path)
            try:
                violations = _check_file(str(child_path), _derive_parent_id)
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

class TestStoreWalkedExactlyOnce(unittest.TestCase):
    """PERFORMANCE REGRESSION: the AC store must be walked exactly once.

    Against the CURRENT (unfixed) code, _resolve_parent_file calls
    ac_store_root.rglob('*.yaml') once per staged file, so with N staged files
    the store is walked N times. This test asserts the walk happens exactly once
    regardless of batch size, which FAILS (red) until the index-once fix is applied.

    Two different batch sizes (N=4 and N=12) each assert == 1.  This rules out
    any hidden O(N) factor that a single-N test with <= 1 could not catch, and a
    count of 0 also fails (positive lower bound), so instrumentation drift is caught.

    Instrumentation: we patch Path.rglob globally and count calls whose argument
    is '*.yaml' on the AC store path prefix. A count of 0 is also a failure —
    it means the filter stopped matching (path refactor, pattern change) and the
    test would give a false green.
    """

    def _build_fixture(self, tmp: Path, n: int) -> list[str]:
        """Create a parent AC + n child ACs in a temp AC store.

        All children depend_on the parent; the parent lists all of them in
        covered_by (so there are no violations — we only test the walk count).

        Args:
            tmp: Temporary directory to use as project root.
            n: Number of child AC files to create and stage.

        Returns:
            List of absolute child path strings.
        """
        child_ids = [f"ACS-300a-{i}" for i in range(1, n + 1)]

        _write_yaml(
            tmp,
            f"{_AC_STORE_REL}/perf/ACS-300a.yaml",
            _parent_yaml("ACS-300a", covered_by=child_ids),
        )

        # 20 filler files make the store non-trivially sized so the walk is
        # doing real work and the count is unambiguously measurable.
        for j in range(1, 21):
            _write_yaml(
                tmp,
                f"{_AC_STORE_REL}/filler/ACS-900a-{j}.yaml",
                _child_yaml(f"ACS-900a-{j}", "ACS-900a"),
            )

        child_paths = []
        for child_id in child_ids:
            p = _write_yaml(
                tmp,
                f"{_AC_STORE_REL}/perf/{child_id}.yaml",
                _child_yaml(child_id, "ACS-300a"),
            )
            child_paths.append(str(p))

        return child_paths

    def _count_store_rglob_calls(self, tmp: Path, child_paths: list[str]) -> int:
        """Run main() with the given staged paths and return the AC-store rglob count.

        The counter increments only for rglob("*.yaml") calls whose self_path
        starts with the AC store root inside tmp.  Any other rglob call (e.g.
        from unrelated stdlib code) is transparent and does not affect the count.

        sys.path is temporarily extended with the worktree's scripts/ directory so
        that the hook's _get_derive_parent_id() can resolve ac_parent_id via Strategy 1
        (package import) regardless of pytest's cwd.  Without this, _get_derive_parent_id
        fails when pytest is run from outside the worktree root, causing main() to exit
        early (fail-open) before _build_parent_index is ever called — making the rglob
        count 0 and giving a spurious "instrumentation broken" failure.

        Args:
            tmp: Temporary project root (contains the AC store).
            child_paths: Absolute paths of staged child AC files to pass via
                HOOK_TEST_FILES.

        Returns:
            Number of times ac_store_root.rglob("*.yaml") was invoked during main().
        """
        rglob_call_count = 0
        original_rglob = Path.rglob
        ac_store_str = str(tmp / _AC_STORE_REL)

        def counting_rglob(self_path, pattern, **kwargs):
            nonlocal rglob_call_count
            if str(self_path).startswith(ac_store_str) and pattern == "*.yaml":
                rglob_call_count += 1
            return original_rglob(self_path, pattern, **kwargs)

        # Patch _get_derive_parent_id on the loaded hook module so that main()
        # receives our deterministically-resolved _derive_parent_id regardless of
        # pytest cwd.  The hook's own import strategies (Strategy 1-3) all rely on
        # cwd or __file__ paths that may not resolve when pytest runs from outside
        # the worktree root; bypassing them here keeps the perf test cwd-agnostic.
        old_env = os.environ.copy()
        os.environ["HOOK_ROOT"] = str(tmp)
        os.environ["HOOK_TEST_FILES"] = os.pathsep.join(child_paths)
        os.environ.pop("HOOK_NO_GIT", None)
        try:
            with patch.object(Path, "rglob", counting_rglob):
                with patch.object(_mod, "_get_derive_parent_id", return_value=_derive_parent_id):
                    _main()
        finally:
            os.environ.clear()
            os.environ.update(old_env)

        return rglob_call_count

    @_requires_import
    def test_ac_perf_store_walked_exactly_once_batch_of_4(self):
        """PERFORMANCE REGRESSION (N=4): store rglob must fire exactly once.

        A count of 0 means the instrumentation filter is broken (false green).
        A count > 1 means the index-once fix is missing (O(N) walk per staged file).
        Exactly 1 is the only acceptable value.
        """
        n = 4
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            child_paths = self._build_fixture(tmp, n)
            count = self._count_store_rglob_calls(tmp, child_paths)

        self.assertEqual(
            count,
            1,
            f"PERFORMANCE REGRESSION (N={n}): ac_store_root.rglob('*.yaml') fired "
            f"{count} time(s). Expected exactly 1 (index built once). "
            f"count==0 means instrumentation filter is broken; "
            f"count=={n} means the per-file walk was not fixed.",
        )

    @_requires_import
    def test_ac_perf_store_walked_exactly_once_batch_of_12(self):
        """PERFORMANCE REGRESSION (N=12): store rglob must fire exactly once.

        Running the same invariant at a larger batch size proves the walk count is
        constant (O(1)) and not just <= 1 for the specific N=4 case.  If the fix
        has a hidden O(N) factor, this test catches it while the N=4 test masks it.

        A count of 0 means the instrumentation filter is broken (false green).
        A count > 1 means the index-once fix is missing or incomplete.
        """
        n = 12
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            child_paths = self._build_fixture(tmp, n)
            count = self._count_store_rglob_calls(tmp, child_paths)

        self.assertEqual(
            count,
            1,
            f"PERFORMANCE REGRESSION (N={n}): ac_store_root.rglob('*.yaml') fired "
            f"{count} time(s). Expected exactly 1 (index built once). "
            f"count==0 means instrumentation filter is broken; "
            f"count=={n} means the per-file walk was not fixed.",
        )


class TestModuleImport(unittest.TestCase):
    """Verify the hook module exists and loads without import errors."""

    def test_hook_script_exists_at_template_path(self):
        """The hook file must exist at templates/scripts/commit_guardian/check_ac_parent_covered_by.py."""
        self.assertTrue(
            _HOOK_PATH.exists(),
            f"Hook script not found at {_HOOK_PATH}. "
            "Ensure templates/scripts/commit_guardian/check_ac_parent_covered_by.py exists.",
        )

    def test_module_imports_successfully(self):
        """Hook module must import without syntax errors or import failures."""
        self.assertTrue(
            _IMPORT_OK,
            f"Hook module failed to import: {_IMPORT_ERROR}",
        )


# ---------------------------------------------------------------------------
# ACS-100i-2-i: Hook fails open on non-UTF-8 staged YAML files
# ---------------------------------------------------------------------------


@_requires_import
class TestBinaryContentFailOpenAcs100i2i(unittest.TestCase):
    """ACS-100i-2-i: hook exits 0 and logs a WARNING for non-UTF-8 YAML files.

    When a staged .yaml file under docs/acceptance-criteria/ contains binary
    (non-UTF-8) content, the hook must:
      1. Log a WARNING naming the file path and the decode error.
      2. Return exit code 0 (do NOT block the commit).
    """

    def _run_main_with_binary_file(
        self, tmp: Path
    ) -> tuple[int, str]:
        """Create a binary .yaml file, run main(), capture exit code and stderr.

        Args:
            tmp: Temporary directory to use as project root.

        Returns:
            Tuple of (returncode, captured_stderr_text).
        """
        ac_store = tmp / _AC_STORE_REL
        ac_store.mkdir(parents=True, exist_ok=True)

        # Write a binary file that is NOT valid UTF-8.
        binary_file = ac_store / "binary_test.yaml"
        binary_file.write_bytes(b"\xff\xfe\x00This is not valid UTF-8\x80\x81")

        import io

        captured_stderr = io.StringIO()
        old_env = os.environ.copy()
        os.environ["HOOK_ROOT"] = str(tmp)
        os.environ["HOOK_TEST_FILES"] = str(binary_file)
        os.environ.pop("HOOK_NO_GIT", None)

        old_stderr = sys.stderr
        sys.stderr = captured_stderr
        try:
            returncode = _main()
        finally:
            sys.stderr = old_stderr
            os.environ.clear()
            os.environ.update(old_env)

        return returncode, captured_stderr.getvalue()

    def test_binary_file_does_not_block_hook(self) -> None:
        """A staged YAML file with binary content must not cause exit code 1 (ACS-100i-2-i)."""
        # covers: ACS-100i-2-i
        with tempfile.TemporaryDirectory() as tmpdir:
            returncode, _ = self._run_main_with_binary_file(Path(tmpdir))

        self.assertEqual(
            returncode,
            0,
            "ACS-100i-2-i: hook must exit 0 when the only staged file has "
            "non-UTF-8 content. Commit must not be blocked by a binary file.",
        )

    def test_binary_file_logs_warning(self) -> None:
        """A staged binary YAML file must produce a WARNING on stderr (ACS-100i-2-i)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _, stderr_text = self._run_main_with_binary_file(Path(tmpdir))

        self.assertIn(
            "WARNING",
            stderr_text,
            "ACS-100i-2-i: hook must log a WARNING when it encounters a "
            "non-UTF-8 staged file. "
            f"Captured stderr: {stderr_text!r}",
        )

    def test_warning_names_file_path(self) -> None:
        """The WARNING message must name the file path of the binary file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _, stderr_text = self._run_main_with_binary_file(Path(tmpdir))

        self.assertIn(
            "binary_test.yaml",
            stderr_text,
            "ACS-100i-2-i: the WARNING message must include the file path. "
            f"Captured stderr: {stderr_text!r}",
        )


if __name__ == "__main__":
    unittest.main()
