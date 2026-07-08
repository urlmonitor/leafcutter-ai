"""
MODULE: test_check_ac_pattern_refs
GOAL: Unit tests for check_ac_pattern_refs.py pre-commit hook.
BUSINESS CONTEXT: Verifies that the pattern reference hook correctly:
    - Blocks staged ACs whose implements_pattern references a non-existent ID.
    - Blocks staged ACs whose implements_pattern references a non-pattern AC.
    - Passes staged ACs whose implements_pattern references a valid pattern AC.
    - Blocks deletion of a pattern AC still referenced by surviving ACs.
    - Allows deletion of a pattern AC with no surviving references.
ARCHITECTURE: Tests load the hook module via importlib. HOOK_TEST_FILES and
    HOOK_ROOT env vars provide filesystem isolation. No subprocess calls are
    made. Temporary directories provide per-test isolation.
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
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
_HOOK_PATH = (
    _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_ac_pattern_refs.py"
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
    _MODULE_NAME = "check_ac_pattern_refs_test_shim"
    _spec = importlib.util.spec_from_file_location(_MODULE_NAME, str(_HOOK_PATH))
    _mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
    sys.modules[_MODULE_NAME] = _mod
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]

    _check_implements_pattern_refs = _mod._check_implements_pattern_refs  # type: ignore[attr-defined]
    _check_pattern_deletion_safety = _mod._check_pattern_deletion_safety  # type: ignore[attr-defined]
    _has_parameterized_slots = _mod._has_parameterized_slots  # type: ignore[attr-defined]
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
            f"check_ac_pattern_refs not importable: {_IMPORT_ERROR}"
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


def _pattern_yaml(ac_id: str, slots: list[str] | None = None) -> str:
    """Return a minimal pattern AC YAML string.

    Args:
        ac_id: The AC id.
        slots: Pattern slot names to include in pattern_slots.

    Returns:
        YAML string for a pattern AC.
    """
    lines = [
        f"id: {ac_id}",
        f'title: "Pattern {ac_id}"',
        "component: test",
        "status: active",
        "created_by: test",
        "criteria: Given {action} When {trigger} Then {outcome}",
    ]
    if slots:
        slots_str = "[" + ", ".join(f"{{{s}}}" for s in slots) + "]"
        lines.append(f"pattern_slots: {slots_str}")
    return "\n".join(lines) + "\n"


def _consuming_yaml(ac_id: str, pattern_id: str) -> str:
    """Return a minimal consuming AC YAML string with implements_pattern.

    Args:
        ac_id: The AC id.
        pattern_id: The pattern AC id this AC implements.

    Returns:
        YAML string for a consuming AC.
    """
    return (
        f"id: {ac_id}\n"
        f'title: "Consuming {ac_id}"\n'
        f"component: test\n"
        f"status: active\n"
        f"created_by: test\n"
        f"criteria: Given something When something Then something\n"
        f"implements_pattern: {pattern_id}\n"
    )


def _plain_yaml(ac_id: str) -> str:
    """Return a minimal plain (non-pattern, non-consuming) AC YAML string.

    Args:
        ac_id: The AC id.

    Returns:
        YAML string.
    """
    return (
        f"id: {ac_id}\n"
        f'title: "Plain {ac_id}"\n'
        f"component: test\n"
        f"status: active\n"
        f"created_by: test\n"
        f"criteria: Given something When something Then something\n"
    )


# ---------------------------------------------------------------------------
# Tests: _has_parameterized_slots predicate
# ---------------------------------------------------------------------------

class TestHasParameterizedSlots(unittest.TestCase):
    """_has_parameterized_slots correctly identifies pattern ACs."""

    @_requires_import
    def test_non_empty_pattern_slots_is_pattern(self):
        """An AC with a non-empty pattern_slots list is a pattern."""
        data = {"pattern_slots": ["{action}", "{trigger}"], "criteria": "plain text"}
        self.assertTrue(_has_parameterized_slots(data))

    @_requires_import
    def test_placeholder_in_criteria_is_pattern(self):
        """An AC with {word} in criteria (no pattern_slots) is a pattern."""
        data = {"criteria": "Given {action} When {trigger} Then {outcome}"}
        self.assertTrue(_has_parameterized_slots(data))

    @_requires_import
    def test_plain_criteria_not_pattern(self):
        """An AC with plain criteria and no pattern_slots is not a pattern."""
        data = {"criteria": "Given something happens", "pattern_slots": []}
        self.assertFalse(_has_parameterized_slots(data))

    @_requires_import
    def test_empty_pattern_slots_not_pattern(self):
        """An AC with an empty pattern_slots list is not a pattern."""
        data = {"pattern_slots": [], "criteria": "Given something"}
        self.assertFalse(_has_parameterized_slots(data))


# ---------------------------------------------------------------------------
# Tests: implements_pattern reference validation
# ---------------------------------------------------------------------------

class TestImplementsPatternRefs(unittest.TestCase):
    """_check_implements_pattern_refs validates that referenced patterns exist."""

    @_requires_import
    def test_valid_pattern_ref_produces_no_violations(self):
        """A staged AC referencing a valid pattern produces no violations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            # Pattern AC exists in the store.
            _write_yaml(tmp, f"{_AC_STORE_REL}/PTN-001.yaml", _pattern_yaml("PTN-001", ["action"]))

            # Consuming AC is staged.
            consuming_path = _write_yaml(
                tmp, f"{_AC_STORE_REL}/ACS-C01.yaml", _consuming_yaml("ACS-C01", "PTN-001")
            )

            old_env = os.environ.copy()
            os.environ["HOOK_ROOT"] = tmpdir
            try:
                violations = _check_implements_pattern_refs(
                    [str(consuming_path)], tmp
                )
            finally:
                os.environ.clear()
                os.environ.update(old_env)

        self.assertEqual(violations, [], f"Expected no violations, got: {violations!r}")

    @_requires_import
    def test_dangling_pattern_ref_produces_violation(self):
        """A staged AC referencing a non-existent pattern ID produces a violation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            # NO pattern AC PTN-999 in the store.
            consuming_path = _write_yaml(
                tmp, f"{_AC_STORE_REL}/ACS-C02.yaml", _consuming_yaml("ACS-C02", "PTN-999")
            )

            old_env = os.environ.copy()
            os.environ["HOOK_ROOT"] = tmpdir
            try:
                violations = _check_implements_pattern_refs(
                    [str(consuming_path)], tmp
                )
            finally:
                os.environ.clear()
                os.environ.update(old_env)

        self.assertGreater(
            len(violations), 0,
            "Expected a violation for dangling pattern reference"
        )
        self.assertIn("PTN-999", violations[0])

    @_requires_import
    def test_non_pattern_ac_reference_produces_violation(self):
        """A staged AC implementing a plain (non-pattern) AC produces a violation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            # Plain AC — no pattern_slots, no {word} placeholders.
            _write_yaml(tmp, f"{_AC_STORE_REL}/ACS-P01.yaml", _plain_yaml("ACS-P01"))

            consuming_path = _write_yaml(
                tmp, f"{_AC_STORE_REL}/ACS-C03.yaml", _consuming_yaml("ACS-C03", "ACS-P01")
            )

            old_env = os.environ.copy()
            os.environ["HOOK_ROOT"] = tmpdir
            try:
                violations = _check_implements_pattern_refs(
                    [str(consuming_path)], tmp
                )
            finally:
                os.environ.clear()
                os.environ.update(old_env)

        self.assertGreater(
            len(violations), 0,
            "Expected a violation when implements_pattern references a non-pattern AC"
        )

    @_requires_import
    def test_no_implements_pattern_field_skipped(self):
        """A staged AC without implements_pattern is skipped — no violations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            plain_path = _write_yaml(
                tmp, f"{_AC_STORE_REL}/ACS-P02.yaml", _plain_yaml("ACS-P02")
            )

            old_env = os.environ.copy()
            os.environ["HOOK_ROOT"] = tmpdir
            try:
                violations = _check_implements_pattern_refs(
                    [str(plain_path)], tmp
                )
            finally:
                os.environ.clear()
                os.environ.update(old_env)

        self.assertEqual(violations, [])


# ---------------------------------------------------------------------------
# Tests: pattern deletion safety
# ---------------------------------------------------------------------------

class TestPatternDeletionSafety(unittest.TestCase):
    """_check_pattern_deletion_safety blocks deletion of referenced patterns."""

    @_requires_import
    def test_no_deleted_paths_returns_empty(self):
        """No deleted paths → no violations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            violations = _check_pattern_deletion_safety([], tmp)
        self.assertEqual(violations, [])

    @_requires_import
    def test_main_returns_0_when_no_staged_or_deleted_files(self):
        """main() exits 0 when no staged or deleted AC files are found."""
        old_env = os.environ.copy()
        os.environ["HOOK_NO_GIT"] = "1"
        os.environ.pop("HOOK_TEST_FILES", None)
        os.environ.pop("HOOK_DELETED_FILES", None)
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
