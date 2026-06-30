"""
MODULE: test_check_ac_circular_deps
GOAL: Unit tests for check_ac_circular_deps.py pre-commit hook.
BUSINESS CONTEXT: Verifies that the circular depends_on detection hook correctly
    identifies cycles in the AC depends_on graph, reports them with the full path,
    and passes cleanly when no cycles exist. Also verifies that the hook uses the
    FULL graph scope (including unstaged nodes), so cycles through unstaged ACs
    are detected even when only part of the cycle is staged.
ARCHITECTURE: Tests load the hook module via importlib so no subprocess is needed.
    HOOK_TEST_FILES and HOOK_ROOT env vars are used for isolation. Temporary
    directories provide isolated filesystem state per test.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Repo root and hook path — derived from THIS file's location.
# parents[0] = unit_tests/commit_guardian/
# parents[1] = unit_tests/
# parents[2] = worktree root
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
_HOOK_PATH = (
    _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_ac_circular_deps.py"
)
_VALIDATORS_PATH = (
    _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "_ac_schema_validators.py"
)
_INDEX_PATH = (
    _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "_ac_store_index.py"
)

# Pre-load validators and index so hook's import works.
for _path, _name in [
    (_VALIDATORS_PATH, "_ac_schema_validators"),
    (_INDEX_PATH, "_ac_store_index"),
]:
    if _path.exists() and _name not in sys.modules:
        _s = importlib.util.spec_from_file_location(_name, str(_path))
        _m = importlib.util.module_from_spec(_s)  # type: ignore[arg-type]
        sys.modules[_name] = _m
        _s.loader.exec_module(_m)  # type: ignore[union-attr]

try:
    _MODULE_NAME = "check_ac_circular_deps_test_shim"
    _spec = importlib.util.spec_from_file_location(_MODULE_NAME, str(_HOOK_PATH))
    _mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
    sys.modules[_MODULE_NAME] = _mod
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]

    _build_depends_graph = _mod._build_depends_graph  # type: ignore[attr-defined]
    _detect_all_cycles_for_staged = _mod._detect_all_cycles_for_staged  # type: ignore[attr-defined]
    _find_cycle = _mod._find_cycle  # type: ignore[attr-defined]
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
            f"check_ac_circular_deps not importable: {_IMPORT_ERROR}"
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
        content: YAML content string.

    Returns:
        Absolute Path of the written file.
    """
    target = root / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def _ac_yaml(ac_id: str, depends_on: list[str] | None = None) -> str:
    """Return a minimal AC YAML string with optional depends_on.

    Args:
        ac_id: The AC id field value.
        depends_on: List of AC IDs this AC depends on (may be empty or None).

    Returns:
        YAML string.
    """
    lines = [
        f"id: {ac_id}",
        f'title: "AC {ac_id}"',
        "component: test",
        "status: active",
        "created_by: test",
        "criteria: Given something When something Then something",
    ]
    if depends_on:
        deps_str = "[" + ", ".join(depends_on) + "]"
        lines.append(f"depends_on: {deps_str}")
    else:
        lines.append("depends_on: []")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Tests: _find_cycle (pure unit tests)
# ---------------------------------------------------------------------------

class TestFindCycle(unittest.TestCase):
    """Pure unit tests for _find_cycle — no filesystem needed."""

    @_requires_import
    def test_no_cycle_returns_none(self):
        """DAG with no cycle returns None."""
        graph = {
            "A": ["B", "C"],
            "B": ["D"],
            "C": [],
            "D": [],
        }
        result = _find_cycle(graph, "A")
        self.assertIsNone(result)

    @_requires_import
    def test_direct_cycle_detected(self):
        """A direct A->B->A cycle is detected starting from A."""
        graph = {"A": ["B"], "B": ["A"]}
        result = _find_cycle(graph, "A")
        self.assertIsNotNone(result)
        self.assertIn("A", result)
        self.assertIn("B", result)

    @_requires_import
    def test_longer_cycle_detected(self):
        """A longer A->B->C->A cycle is detected."""
        graph = {"A": ["B"], "B": ["C"], "C": ["A"]}
        result = _find_cycle(graph, "A")
        self.assertIsNotNone(result)
        # The path should form a cycle (start node appears at beginning and end).
        self.assertEqual(result[0], result[-1], "Cycle path must close on start node")

    @_requires_import
    def test_isolated_node_no_cycle(self):
        """A node with no edges returns None."""
        graph = {"A": []}
        result = _find_cycle(graph, "A")
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Tests: full graph scope (cycles through unstaged nodes)
# ---------------------------------------------------------------------------

class TestFullGraphScope(unittest.TestCase):
    """The hook must use the FULL graph scope, not just staged nodes."""

    @_requires_import
    def test_cycle_through_unstaged_node_detected(self):
        """A cycle that routes through an unstaged node is still detected.

        Topology:  staged_A -> unstaged_B -> unstaged_C -> staged_A
        Only staged_A is in staged_overrides; B and C are on-disk only.
        The full graph must include all three nodes for the cycle to be found.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            # B and C exist on disk but are NOT staged.
            _write_yaml(tmp, f"{_AC_STORE_REL}/ACS-B.yaml", _ac_yaml("ACS-B", ["ACS-C"]))
            _write_yaml(tmp, f"{_AC_STORE_REL}/ACS-C.yaml", _ac_yaml("ACS-C", ["ACS-A"]))

            # A is staged and depends on B.
            staged_a_data = {
                "id": "ACS-A",
                "depends_on": ["ACS-B"],
                "title": "Staged A",
                "component": "test",
                "status": "active",
            }
            staged_overrides = {"ACS-A": staged_a_data}

            ac_store_root = tmp / _AC_STORE_REL
            graph = _build_depends_graph(ac_store_root, staged_overrides)

        # All three nodes must be in the graph.
        self.assertIn("ACS-A", graph, "Staged node A must be in graph")
        self.assertIn("ACS-B", graph, "Unstaged node B must be in graph")
        self.assertIn("ACS-C", graph, "Unstaged node C must be in graph")

        # The cycle must be detectable.
        staged_ids = {"ACS-A"}
        errors = _detect_all_cycles_for_staged(graph, staged_ids)
        self.assertTrue(
            len(errors) > 0,
            "Expected a cycle error but got none. "
            f"graph={graph!r}",
        )

    @_requires_import
    def test_no_cycle_passes_cleanly(self):
        """A DAG without any cycle produces no violations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            # B exists on disk.
            _write_yaml(tmp, f"{_AC_STORE_REL}/ACS-B2.yaml", _ac_yaml("ACS-B2", ["ACS-C2"]))
            _write_yaml(tmp, f"{_AC_STORE_REL}/ACS-C2.yaml", _ac_yaml("ACS-C2", []))

            # A is staged and depends on B (no cycle).
            staged_a_data = {
                "id": "ACS-A2",
                "depends_on": ["ACS-B2"],
                "title": "Staged A2",
                "component": "test",
                "status": "active",
            }
            staged_overrides = {"ACS-A2": staged_a_data}

            ac_store_root = tmp / _AC_STORE_REL
            graph = _build_depends_graph(ac_store_root, staged_overrides)
            staged_ids = {"ACS-A2"}
            errors = _detect_all_cycles_for_staged(graph, staged_ids)

        self.assertEqual(errors, [], f"Expected no errors but got: {errors!r}")


# ---------------------------------------------------------------------------
# Tests: main() integration
# ---------------------------------------------------------------------------

class TestMain(unittest.TestCase):
    """Integration tests for main() via env-var seams."""

    @_requires_import
    def test_main_returns_0_when_no_staged_files(self):
        """main() exits 0 when no AC files are staged."""
        old_env = os.environ.copy()
        os.environ["HOOK_NO_GIT"] = "1"
        os.environ.pop("HOOK_TEST_FILES", None)
        try:
            result = _main()
        finally:
            os.environ.clear()
            os.environ.update(old_env)

        self.assertEqual(result, 0)

    @_requires_import
    def test_main_returns_1_on_direct_cycle(self):
        """main() exits 1 when a staged file introduces a direct cycle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            # ACS-X depends on ACS-Y on disk.
            _write_yaml(tmp, f"{_AC_STORE_REL}/ACS-X.yaml", _ac_yaml("ACS-X", ["ACS-Y"]))

            # Staged: ACS-Y depends on ACS-X → cycle.
            staged_path = _write_yaml(
                tmp, f"{_AC_STORE_REL}/ACS-Y.yaml", _ac_yaml("ACS-Y", ["ACS-X"])
            )

            old_env = os.environ.copy()
            os.environ["HOOK_ROOT"] = tmpdir
            os.environ["HOOK_TEST_FILES"] = str(staged_path)
            os.environ.pop("HOOK_NO_GIT", None)
            try:
                result = _main()
            finally:
                os.environ.clear()
                os.environ.update(old_env)

        self.assertEqual(result, 1, "Expected exit code 1 for cycle detection")

    @_requires_import
    def test_main_returns_0_on_acyclic_graph(self):
        """main() exits 0 when the depends_on graph is acyclic."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            # ACS-P1 → ACS-P2 → ACS-P3 (no cycle)
            _write_yaml(tmp, f"{_AC_STORE_REL}/ACS-P2.yaml", _ac_yaml("ACS-P2", ["ACS-P3"]))
            _write_yaml(tmp, f"{_AC_STORE_REL}/ACS-P3.yaml", _ac_yaml("ACS-P3", []))

            staged_path = _write_yaml(
                tmp, f"{_AC_STORE_REL}/ACS-P1.yaml", _ac_yaml("ACS-P1", ["ACS-P2"])
            )

            old_env = os.environ.copy()
            os.environ["HOOK_ROOT"] = tmpdir
            os.environ["HOOK_TEST_FILES"] = str(staged_path)
            os.environ.pop("HOOK_NO_GIT", None)
            try:
                result = _main()
            finally:
                os.environ.clear()
                os.environ.update(old_env)

        self.assertEqual(result, 0)


# ---------------------------------------------------------------------------
# Tests: module import
# ---------------------------------------------------------------------------

class TestModuleImport(unittest.TestCase):
    """Verify the hook module exists and loads without errors."""

    def test_hook_script_exists(self):
        """The hook file must exist at the expected template path."""
        self.assertTrue(
            _HOOK_PATH.exists(),
            f"Hook script not found at {_HOOK_PATH}",
        )

    def test_module_imports_successfully(self):
        """Hook module must import without syntax errors or import failures."""
        self.assertTrue(
            _IMPORT_OK,
            f"Hook module failed to import: {_IMPORT_ERROR}",
        )


if __name__ == "__main__":
    unittest.main()
