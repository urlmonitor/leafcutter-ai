"""
MODULE: test_ac_store_index
GOAL: Unit tests for the _ac_store_index shared mtime-cached AC store index module.
BUSINESS CONTEXT: Verifies that get_ac_index() correctly builds, caches, and
    invalidates its mtime-keyed index of AC YAML files under the AC store directory.
    Ensures the cache prevents redundant re-parses when mtimes are unchanged, and
    that stale entries are evicted when any file is added or modified.
ARCHITECTURE: Tests create temporary directories with fixture .yaml files, call
    get_ac_index() directly, and use invalidate_cache() to reset state between test
    cases. The module is loaded via importlib so the test is stable regardless of
    pytest cwd. No subprocess calls are made.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Repo root and module path — derived from THIS file's location.
# parents[0] = unit_tests/commit_guardian/
# parents[1] = unit_tests/
# parents[2] = worktree root
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = (
    _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "_ac_store_index.py"
)
_VALIDATORS_PATH = (
    _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "_ac_schema_validators.py"
)

# Ensure validators module is importable before loading the module under test.
if _VALIDATORS_PATH.exists():
    _validators_spec = importlib.util.spec_from_file_location(
        "_ac_schema_validators_test_shim", str(_VALIDATORS_PATH)
    )
    _validators_mod = importlib.util.module_from_spec(_validators_spec)  # type: ignore[arg-type]
    sys.modules["_ac_schema_validators"] = _validators_mod
    _validators_spec.loader.exec_module(_validators_mod)  # type: ignore[union-attr]

try:
    _MODULE_NAME = "_ac_store_index_test_shim"
    _spec = importlib.util.spec_from_file_location(_MODULE_NAME, str(_MODULE_PATH))
    _mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
    sys.modules["_ac_store_index"] = _mod
    sys.modules[_MODULE_NAME] = _mod
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]

    get_ac_index = _mod.get_ac_index  # type: ignore[attr-defined]
    invalidate_cache = _mod.invalidate_cache  # type: ignore[attr-defined]
    _IMPORT_OK = True
    _IMPORT_ERROR = ""
except (FileNotFoundError, AttributeError, ImportError, SyntaxError, TypeError, ValueError) as _exc:
    _IMPORT_OK = False
    _IMPORT_ERROR = str(_exc)


def _requires_import(func):
    """Skip test if the module failed to import."""
    if not _IMPORT_OK:
        return unittest.skip(
            f"_ac_store_index not importable: {_IMPORT_ERROR}"
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


def _ac_yaml(ac_id: str, **extra_fields: Any) -> str:
    """Return a minimal valid AC YAML string.

    Args:
        ac_id: The id field value.
        **extra_fields: Additional top-level fields to include.

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
    for key, value in extra_fields.items():
        if isinstance(value, list):
            lines.append(f"{key}: [{', '.join(str(v) for v in value)}]")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Tests: index structure and content
# ---------------------------------------------------------------------------

class TestIndexStructure(unittest.TestCase):
    """get_ac_index returns a correctly structured id->dict mapping."""

    @_requires_import
    def test_returns_dict_mapping_id_to_parsed_content(self):
        """Index maps AC id string to a dict containing at least the id field."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            store_root = tmp / _AC_STORE_REL
            _write_yaml(tmp, f"{_AC_STORE_REL}/ACS-001.yaml", _ac_yaml("ACS-001"))
            _write_yaml(tmp, f"{_AC_STORE_REL}/ACS-002.yaml", _ac_yaml("ACS-002"))
            invalidate_cache(str(store_root))

            index = get_ac_index(str(store_root))

        self.assertIn("ACS-001", index, "Index must contain ACS-001")
        self.assertIn("ACS-002", index, "Index must contain ACS-002")
        self.assertEqual(index["ACS-001"]["id"], "ACS-001")
        self.assertEqual(index["ACS-002"]["id"], "ACS-002")

    @_requires_import
    def test_full_parsed_content_preserved(self):
        """Index preserves all fields from the parsed AC dict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            store_root = tmp / _AC_STORE_REL
            _write_yaml(
                tmp,
                f"{_AC_STORE_REL}/ACS-010.yaml",
                _ac_yaml("ACS-010", implements_pattern="PTN-001", depends_on=["ACS-009"]),
            )
            invalidate_cache(str(store_root))

            index = get_ac_index(str(store_root))

        self.assertIn("ACS-010", index)
        entry = index["ACS-010"]
        self.assertEqual(entry.get("implements_pattern"), "PTN-001")

    @_requires_import
    def test_empty_store_returns_empty_dict(self):
        """An AC store directory with no .yaml files returns an empty index."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            store_root = tmp / _AC_STORE_REL
            store_root.mkdir(parents=True, exist_ok=True)
            invalidate_cache(str(store_root))

            index = get_ac_index(str(store_root))

        self.assertEqual(index, {})

    @_requires_import
    def test_absent_store_root_returns_empty_dict(self):
        """A non-existent store_root path returns an empty index without raising."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent = str(Path(tmpdir) / "does" / "not" / "exist")
            invalidate_cache(nonexistent)

            index = get_ac_index(nonexistent)

        self.assertEqual(index, {})

    @_requires_import
    def test_unparseable_file_skipped_fail_open(self):
        """A file that cannot be parsed is skipped; parseable files still appear."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            store_root = tmp / _AC_STORE_REL
            _write_yaml(tmp, f"{_AC_STORE_REL}/ACS-100.yaml", _ac_yaml("ACS-100"))
            # Write a file with no 'id' field — should be skipped.
            _write_yaml(
                tmp,
                f"{_AC_STORE_REL}/no_id.yaml",
                "title: no id here\nstatus: active\n",
            )
            # Write a binary-like file that will fail to parse.
            bad_file = store_root / "bad.yaml"
            bad_file.write_bytes(b"\xff\xfe invalid utf-8 content \x00\x01")
            invalidate_cache(str(store_root))

            index = get_ac_index(str(store_root))

        self.assertIn("ACS-100", index, "Parseable file must appear in index")
        self.assertNotIn("no_id", index, "File without id must not appear in index")


# ---------------------------------------------------------------------------
# Tests: mtime-keyed caching
# ---------------------------------------------------------------------------

class TestMtimeCache(unittest.TestCase):
    """get_ac_index returns the cached index when mtimes are unchanged."""

    @_requires_import
    def test_second_call_returns_same_object(self):
        """Two consecutive calls with no file changes return the identical dict object."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            store_root = tmp / _AC_STORE_REL
            _write_yaml(tmp, f"{_AC_STORE_REL}/ACS-200.yaml", _ac_yaml("ACS-200"))
            invalidate_cache(str(store_root))

            index1 = get_ac_index(str(store_root))
            index2 = get_ac_index(str(store_root))

        self.assertIs(
            index1,
            index2,
            "Second call must return the cached (identical) dict object when no "
            "file changes occurred between calls.",
        )

    @_requires_import
    def test_invalidate_cache_forces_rebuild(self):
        """After invalidate_cache(), a new index object is returned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            store_root = tmp / _AC_STORE_REL
            _write_yaml(tmp, f"{_AC_STORE_REL}/ACS-201.yaml", _ac_yaml("ACS-201"))
            invalidate_cache(str(store_root))

            index1 = get_ac_index(str(store_root))
            invalidate_cache(str(store_root))
            index2 = get_ac_index(str(store_root))

        # After invalidation a new dict is built (different object identity).
        self.assertIsNot(
            index1,
            index2,
            "After invalidate_cache() the returned index must be a fresh dict.",
        )
        # Content must still be correct.
        self.assertIn("ACS-201", index2)

    @_requires_import
    def test_new_file_detected_after_mtime_change(self):
        """Adding a new .yaml file changes the max mtime, causing a cache rebuild."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            store_root = tmp / _AC_STORE_REL
            _write_yaml(tmp, f"{_AC_STORE_REL}/ACS-300.yaml", _ac_yaml("ACS-300"))
            invalidate_cache(str(store_root))

            index1 = get_ac_index(str(store_root))
            self.assertIn("ACS-300", index1)
            self.assertNotIn("ACS-301", index1)

            # Ensure the new file has a strictly later mtime by sleeping 1 s.
            # Filesystem mtime resolution is 1 s on most platforms.
            time.sleep(1.1)
            _write_yaml(tmp, f"{_AC_STORE_REL}/ACS-301.yaml", _ac_yaml("ACS-301"))

            index2 = get_ac_index(str(store_root))

        self.assertIn(
            "ACS-301",
            index2,
            "New file added after mtime advance must appear in the rebuilt index.",
        )

    @_requires_import
    def test_invalidate_cache_none_clears_all(self):
        """invalidate_cache(None) clears the entire cache for all store roots."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            store_root = tmp / _AC_STORE_REL
            _write_yaml(tmp, f"{_AC_STORE_REL}/ACS-400.yaml", _ac_yaml("ACS-400"))
            invalidate_cache(str(store_root))

            index1 = get_ac_index(str(store_root))
            invalidate_cache(None)  # clear everything
            index2 = get_ac_index(str(store_root))

        self.assertIsNot(index1, index2, "Global cache clear must force a rebuild.")


# ---------------------------------------------------------------------------
# Tests: module exists
# ---------------------------------------------------------------------------

class TestModuleExists(unittest.TestCase):
    """Verify _ac_store_index.py exists and exports the expected public API."""

    def test_module_file_exists(self):
        """The _ac_store_index.py file must exist under templates/scripts/commit_guardian/."""
        self.assertTrue(
            _MODULE_PATH.exists(),
            f"Module not found at {_MODULE_PATH}",
        )

    def test_module_imports_successfully(self):
        """Module must import without syntax errors."""
        self.assertTrue(_IMPORT_OK, f"Module failed to import: {_IMPORT_ERROR}")

    @_requires_import
    def test_get_ac_index_is_callable(self):
        """get_ac_index must be a callable exported by the module."""
        self.assertTrue(callable(get_ac_index))

    @_requires_import
    def test_invalidate_cache_is_callable(self):
        """invalidate_cache must be a callable exported by the module."""
        self.assertTrue(callable(invalidate_cache))


if __name__ == "__main__":
    unittest.main()
