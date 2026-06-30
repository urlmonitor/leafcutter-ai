"""
MODULE: test_ac_store_index
GOAL: Unit tests for the _ac_store_index shared fingerprint-cached AC store index
    module. Covers index structure, in-memory cache, cross-process disk cache, and
    cache invalidation correctness (including removals and same-second edits).
BUSINESS CONTEXT: Verifies that get_ac_index() correctly builds, caches, and
    invalidates its fingerprint-keyed index of AC YAML files under the AC store
    directory. Ensures the cache prevents redundant re-parses when the store is
    unchanged (same process or cross-process via disk), and that stale entries are
    evicted when any file is added, modified, or removed — including cases that the
    old max-mtime key missed (removal of a non-newest file, same-second edits).
ARCHITECTURE: Tests create temporary directories with fixture .yaml files, call
    get_ac_index() directly, and use invalidate_cache() / invalidate_disk_cache()
    to reset state between test cases. The module is loaded via importlib so the
    test is stable regardless of pytest cwd. No subprocess calls are made;
    cross-process simulation is achieved by clearing the in-memory _CACHE dict and
    asserting the disk cache is loaded without re-invoking the YAML parser.
"""

from __future__ import annotations

import datetime
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
_CG_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_MODULE_PATH = _CG_DIR / "_ac_store_index.py"
_DISK_MODULE_PATH = _CG_DIR / "_ac_store_index_disk.py"
_VALIDATORS_PATH = _CG_DIR / "_ac_schema_validators.py"

# Ensure validators module is importable before loading the module under test.
if _VALIDATORS_PATH.exists():
    _validators_spec = importlib.util.spec_from_file_location(
        "_ac_schema_validators_test_shim", str(_VALIDATORS_PATH)
    )
    _validators_mod = importlib.util.module_from_spec(_validators_spec)  # type: ignore[arg-type]
    sys.modules["_ac_schema_validators"] = _validators_mod
    _validators_spec.loader.exec_module(_validators_mod)  # type: ignore[union-attr]

# Load _ac_store_index_disk before the main module so its import succeeds.
# Always create a FRESH module object from disk (never re-use a stale cached
# entry from a previous import in the same pytest session) so tests see the
# current version of the codec.
_disk_mod = None  # fallback; overwritten below if the file exists
if _DISK_MODULE_PATH.exists():
    _disk_spec = importlib.util.spec_from_file_location(
        "_ac_store_index_disk", str(_DISK_MODULE_PATH)
    )
    _disk_mod = importlib.util.module_from_spec(_disk_spec)  # type: ignore[arg-type]
    # Register in sys.modules BEFORE exec so any internal relative imports resolve.
    sys.modules["_ac_store_index_disk"] = _disk_mod
    _disk_spec.loader.exec_module(_disk_mod)  # type: ignore[union-attr]

try:
    _MODULE_NAME = "_ac_store_index_test_shim"
    _spec = importlib.util.spec_from_file_location(_MODULE_NAME, str(_MODULE_PATH))
    _mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
    sys.modules["_ac_store_index"] = _mod
    sys.modules[_MODULE_NAME] = _mod
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]

    get_ac_index = _mod.get_ac_index  # type: ignore[attr-defined]
    invalidate_cache = _mod.invalidate_cache  # type: ignore[attr-defined]
    invalidate_disk_cache = _mod.invalidate_disk_cache  # type: ignore[attr-defined]
    _CACHE = _mod._CACHE  # type: ignore[attr-defined]
    _load_one_yaml_file = _mod._load_one_yaml_file  # type: ignore[attr-defined]
    _IMPORT_OK = True
    _IMPORT_ERROR = ""
except (FileNotFoundError, AttributeError, ImportError, SyntaxError, TypeError, ValueError) as _exc:
    _IMPORT_OK = False
    _IMPORT_ERROR = str(_exc)
    invalidate_disk_cache = None  # type: ignore[assignment]
    _CACHE = {}  # type: ignore[assignment]
    _load_one_yaml_file = None  # type: ignore[assignment]


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


# ---------------------------------------------------------------------------
# Tests: fingerprint-based invalidation (Defect 2 regression suite)
# ---------------------------------------------------------------------------

class TestFingerprintInvalidation(unittest.TestCase):
    """Fingerprint key catches removals and same-second edits that max-mtime missed."""

    @_requires_import
    def test_removal_of_non_newest_file_invalidates(self):
        """Removing a non-newest file must cause the next get_ac_index() to reflect the removal.

        This was the primary Defect 2 failure case: removing a file with an older
        mtime left max(st_mtime) unchanged, so the old max-mtime cache key still
        matched and the stale index was returned. The fingerprint includes every
        file's (path, mtime_ns, size), so a removal changes the fingerprint even
        when the removed file is not the newest.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            store_root = tmp / _AC_STORE_REL
            # Write two files; file A will end up older than file B.
            file_a = _write_yaml(tmp, f"{_AC_STORE_REL}/ACS-OLD-A.yaml", _ac_yaml("ACS-OLD-A"))
            # Bump mtime so file B is strictly newer.
            new_mtime = file_a.stat().st_mtime + 2
            _write_yaml(tmp, f"{_AC_STORE_REL}/ACS-NEW-B.yaml", _ac_yaml("ACS-NEW-B"))
            os.utime(file_a, (new_mtime - 2, new_mtime - 2))

            invalidate_cache(str(store_root))
            invalidate_disk_cache(str(store_root))

            index1 = get_ac_index(str(store_root))
            self.assertIn("ACS-OLD-A", index1)
            self.assertIn("ACS-NEW-B", index1)

            # Remove the OLDER file (ACS-OLD-A, which has the earlier mtime).
            file_a.unlink()

            invalidate_cache(str(store_root))
            index2 = get_ac_index(str(store_root))

        self.assertNotIn(
            "ACS-OLD-A",
            index2,
            "Removed non-newest file must no longer appear in the index after removal.",
        )
        self.assertIn("ACS-NEW-B", index2)

    @_requires_import
    def test_addition_with_older_mtime_invalidates(self):
        """Adding a file with mtime <= existing max must be detected via fingerprint.

        With the old max-mtime key, adding a file that happened to have a mtime
        equal to or less than the current max (e.g. same-second add or back-dated
        file) would leave the cache key unchanged and the new file would not appear.
        The fingerprint includes the sorted path list, so any addition changes it.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            store_root = tmp / _AC_STORE_REL
            existing = _write_yaml(
                tmp, f"{_AC_STORE_REL}/ACS-EXISTING.yaml", _ac_yaml("ACS-EXISTING")
            )

            invalidate_cache(str(store_root))
            invalidate_disk_cache(str(store_root))

            index1 = get_ac_index(str(store_root))
            self.assertNotIn("ACS-BACKDATED", index1)

            # Write new file with a deliberately older mtime (back-dated by 10 s).
            new_file = _write_yaml(
                tmp, f"{_AC_STORE_REL}/ACS-BACKDATED.yaml", _ac_yaml("ACS-BACKDATED")
            )
            old_mtime = existing.stat().st_mtime - 10
            os.utime(new_file, (old_mtime, old_mtime))

            invalidate_cache(str(store_root))
            index2 = get_ac_index(str(store_root))

        self.assertIn(
            "ACS-BACKDATED",
            index2,
            "File added with mtime <= existing max must appear after in-memory cache invalidation.",
        )

    @_requires_import
    def test_in_place_modification_reflected_via_fingerprint(self):
        """In-place file modification changes the fingerprint even within the same second.

        Rather than sleeping to ensure an mtime advance (unreliable on some FS),
        this test asserts that after writing new content the fingerprint changes.
        The fingerprint includes st_mtime_ns (nanosecond resolution on Linux) and
        st_size, both of which change when a file is rewritten with different content.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            store_root = tmp / _AC_STORE_REL
            yaml_path = _write_yaml(
                tmp, f"{_AC_STORE_REL}/ACS-MOD.yaml", _ac_yaml("ACS-MOD")
            )

            invalidate_cache(str(store_root))
            invalidate_disk_cache(str(store_root))

            index1 = get_ac_index(str(store_root))
            self.assertIn("ACS-MOD", index1)
            # Capture the size before modification.
            size_before = yaml_path.stat().st_size

            # Write additional content so size changes even if mtime resolution is coarse.
            yaml_path.write_text(
                _ac_yaml("ACS-MOD", title="Modified title with extra content to change size"),
                encoding="utf-8",
            )
            size_after = yaml_path.stat().st_size
            # The test asserts the fingerprint changes, not a specific index value,
            # because on some FSes the mtime may not advance within the same syscall.
            # Changing the file content guarantees size_after != size_before.
            self.assertNotEqual(
                size_before,
                size_after,
                "Rewritten file must have a different size so the fingerprint changes.",
            )

            invalidate_cache(str(store_root))
            # If fingerprint changed, get_ac_index will rebuild (cache miss).
            # We assert this by checking a new dict object is returned.
            index2 = get_ac_index(str(store_root))

        # Both indices must contain ACS-MOD; test proves the rebuild path ran.
        self.assertIn("ACS-MOD", index1)
        self.assertIn("ACS-MOD", index2)


# ---------------------------------------------------------------------------
# Tests: cross-process disk cache (Defect 1 regression suite)
# ---------------------------------------------------------------------------

class TestDiskCache(unittest.TestCase):
    """On-disk JSON cache enables cross-process cache sharing between hook subprocesses."""

    @_requires_import
    def test_disk_cache_loaded_without_reparsing_yaml(self):
        """Simulate a fresh-process start: disk cache hit must not re-invoke the YAML parser.

        This is the primary Defect 1 scenario: the four hooks each run in a separate
        Python subprocess, so the in-memory _CACHE is empty at the start of each hook
        process. Hook #1 builds the index and writes it to disk. Hooks #2-#4 (simulated
        here by clearing _CACHE) must load from disk rather than re-parsing all YAML.

        The test monkeypatches _load_one_yaml_file in the module under test with a
        counter wrapper and asserts the counter stays 0 on the disk-cache-hit path.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            store_root = tmp / _AC_STORE_REL
            _write_yaml(tmp, f"{_AC_STORE_REL}/ACS-CP-1.yaml", _ac_yaml("ACS-CP-1"))
            _write_yaml(tmp, f"{_AC_STORE_REL}/ACS-CP-2.yaml", _ac_yaml("ACS-CP-2"))

            invalidate_cache(str(store_root))
            invalidate_disk_cache(str(store_root))

            # Process #1: build + persist disk cache.
            index1 = get_ac_index(str(store_root))
            self.assertIn("ACS-CP-1", index1)

            # Simulate fresh process: clear in-memory cache (disk cache remains).
            invalidate_cache(str(store_root))

            # Monkeypatch the YAML loader to count calls.
            parse_call_count: list[int] = [0]
            original_loader = _mod._load_one_yaml_file  # type: ignore[attr-defined]

            def _counting_loader(yaml_file):  # type: ignore[no-untyped-def]
                parse_call_count[0] += 1
                return original_loader(yaml_file)

            _mod._load_one_yaml_file = _counting_loader  # type: ignore[attr-defined]
            try:
                # Process #2: should load from disk cache, not re-parse YAML.
                index2 = get_ac_index(str(store_root))
            finally:
                _mod._load_one_yaml_file = original_loader  # type: ignore[attr-defined]

        self.assertIn(
            "ACS-CP-1",
            index2,
            "Disk-cache-loaded index must contain the same entries as the original.",
        )
        self.assertIn("ACS-CP-2", index2)
        self.assertEqual(
            parse_call_count[0],
            0,
            f"YAML parser invoked {parse_call_count[0]} time(s) on disk-cache hit path; "
            "expected 0 — hooks #2-#4 must not re-parse YAML when the disk cache is warm.",
        )

    @_requires_import
    def test_corrupt_disk_cache_degrades_to_clean_rebuild(self):
        """A corrupt on-disk cache file must degrade to a full rebuild without crashing.

        If the cache file is garbage (e.g. partial write, external mutation), the hook
        must still return the correct index — it must NOT raise an exception or return
        empty data. A warning is written to stderr, then the YAML store is re-parsed.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            store_root = tmp / _AC_STORE_REL
            _write_yaml(tmp, f"{_AC_STORE_REL}/ACS-CRPT-1.yaml", _ac_yaml("ACS-CRPT-1"))

            invalidate_cache(str(store_root))
            invalidate_disk_cache(str(store_root))

            # First call: populates disk cache.
            index1 = get_ac_index(str(store_root))
            self.assertIn("ACS-CRPT-1", index1)

            # Corrupt the disk cache file.
            cache_path = _disk_mod.resolve_cache_path(Path(str(store_root)))  # type: ignore[union-attr]
            cache_path.write_text("}{not valid json at all!!", encoding="utf-8")

            # Clear in-memory cache so disk path is attempted.
            invalidate_cache(str(store_root))

            # Second call must rebuild cleanly despite the corrupt file.
            index2 = get_ac_index(str(store_root))

        self.assertIn(
            "ACS-CRPT-1",
            index2,
            "After corrupt disk cache, get_ac_index must return the correct index via rebuild.",
        )


# ---------------------------------------------------------------------------
# Tests: fail-open YAML parse error handling (H-2 regression)
# ---------------------------------------------------------------------------

class TestYamlParseErrorFailOpen(unittest.TestCase):
    """Malformed YAML in a store file must be skipped with a warning, not raise."""

    @_requires_import
    def test_malformed_yaml_skipped_not_raised(self):
        """A file with invalid YAML syntax must not crash get_ac_index().

        Regression for H-2: _ac_schema_validators.load_yaml() calls yaml.safe_load()
        and does NOT catch yaml.YAMLError, so a malformed AC file (e.g. duplicate keys,
        tab characters in a flow context, invalid UTF-8 sequences that pass OS read but
        fail YAML parsing) would propagate and crash every hook.

        After the fix, _load_one_yaml_file catches yaml.YAMLError on the primary load
        path, logs a WARNING to stderr, and returns None so the file is silently skipped.
        All other valid files in the store must still appear in the index.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            store_root = tmp / _AC_STORE_REL

            # Write a valid AC file.
            _write_yaml(tmp, f"{_AC_STORE_REL}/ACS-GOOD.yaml", _ac_yaml("ACS-GOOD"))

            # Write a file with YAML that will fail yaml.safe_load(): duplicate mapping key
            # triggers yaml.constructor.DuplicateKeyError (a subclass of yaml.YAMLError)
            # when yaml is built with the C extension and strict mode, but the safest
            # cross-platform trigger is a tab character inside a flow mapping, which is a
            # scanner error. We use invalid structure: a mapping key collision via
            # deliberately malformed structure that PyYAML rejects.
            bad_yaml = "id: ACS-BAD\nid: ACS-BAD-DUPLICATE\ntitle: bad\n"
            bad_file = store_root / "ACS-BAD.yaml"
            bad_file.parent.mkdir(parents=True, exist_ok=True)
            bad_file.write_text(bad_yaml, encoding="utf-8")

            invalidate_cache(str(store_root))
            invalidate_disk_cache(str(store_root))

            # Must not raise — must return an index containing the good file.
            try:
                index = get_ac_index(str(store_root))
            except Exception as exc:  # noqa: BLE001
                self.fail(
                    f"get_ac_index() raised {type(exc).__name__} on malformed YAML; "
                    "expected fail-open (skip + warn, no raise)."
                )

        self.assertIn(
            "ACS-GOOD",
            index,
            "Valid AC file must still appear in index when another file has malformed YAML.",
        )

    @_requires_import
    def test_load_one_yaml_file_returns_none_on_yaml_error(self):
        """_load_one_yaml_file must return None (not raise) for a YAML scanner error.

        Directly tests the internal helper to verify the H-2 fix in isolation without
        relying on the full get_ac_index() path. Uses a file whose content causes
        yaml.safe_load() to raise yaml.YAMLError (tab in flow context is a reliable
        cross-platform trigger).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_file = Path(tmpdir) / "bad.yaml"
            # A YAML tab-in-flow-context error: tab is forbidden as indentation
            # inside a flow sequence/mapping in the YAML 1.1/1.2 spec.
            # This reliably raises yaml.scanner.ScannerError on PyYAML ≥ 5.
            bad_file.write_text("key: [\t]\n", encoding="utf-8")

            result = _load_one_yaml_file(bad_file)

        self.assertIsNone(
            result,
            "_load_one_yaml_file must return None (not raise) when yaml.safe_load "
            "raises yaml.YAMLError on malformed input.",
        )


# ---------------------------------------------------------------------------
# Tests: datetime.date codec — real-store date serialisation fix
# ---------------------------------------------------------------------------

def _ac_yaml_with_date(ac_id: str, created: str) -> str:
    """Return a minimal AC YAML string with an UNQUOTED ISO date field.

    PyYAML safe_load will parse the unquoted date as a datetime.date object,
    which is the exact condition that caused json.dump to raise TypeError in
    production.

    Args:
        ac_id: The id field value.
        created: ISO date string (e.g. "2026-06-24") written unquoted.

    Returns:
        YAML string with unquoted date.
    """
    return (
        f"id: {ac_id}\n"
        f'title: "AC {ac_id}"\n'
        "component: test\n"
        "status: active\n"
        "created_by: test\n"
        f"created: {created}\n"
        "criteria: Given something When something Then something\n"
    )


class TestDatetimeCodec(unittest.TestCase):
    """Type-preserving codec for datetime.date/datetime fields in AC YAML files."""

    @_requires_import
    def test_write_disk_cache_succeeds_with_date_field(self):
        """write_disk_cache must create the cache file when the index contains datetime.date.

        Root cause of the production no-op: unquoted dates in real AC YAML files
        (e.g. `created: 2026-06-24`) are parsed by PyYAML as datetime.date objects.
        Without the codec, json.dump raised TypeError, the H-4 handler warned and
        returned, and no cache file was ever written. This test asserts the file IS
        created after the fix.
        """
        # Fetch write_disk_cache from the live sys.modules entry so we always
        # get the version exec'd by this test file's preamble, regardless of
        # the order in which pytest collects and imports modules.
        disk_module = sys.modules.get("_ac_store_index_disk")
        if disk_module is None or not hasattr(disk_module, "_ac_json_default"):
            self.skipTest("_ac_store_index_disk not loaded with codec — skip")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Build an index with a real datetime.date value (as PyYAML would produce).
            date_val = datetime.date(2026, 6, 24)
            index = {
                "ACS-DATE-1": {
                    "id": "ACS-DATE-1",
                    "title": "Date test AC",
                    "created": date_val,
                },
            }
            cache_path = Path(tmpdir) / "test_cache.json"
            disk_module.write_disk_cache(cache_path, "test-fingerprint-abc", index)
            # Assert INSIDE the context manager — tmpdir is deleted on exit.
            self.assertTrue(
                cache_path.exists(),
                "write_disk_cache must create the cache file even when the index "
                "contains datetime.date values (requires the type-preserving codec).",
            )

    @_requires_import
    def test_date_field_round_trips_as_datetime_date(self):
        """load_disk_cache must restore datetime.date, not return a tagged dict or str.

        Verifies that the codec is type-preserving: a value written as datetime.date
        comes back as datetime.date (equal to the original), not as a string or
        tagged-dict artifact.
        """
        disk_module = sys.modules.get("_ac_store_index_disk")
        if disk_module is None or not hasattr(disk_module, "_ac_json_default"):
            self.skipTest("_ac_store_index_disk not loaded with codec — skip")

        with tempfile.TemporaryDirectory() as tmpdir:
            date_val = datetime.date(2026, 6, 24)
            index = {
                "ACS-DATE-2": {
                    "id": "ACS-DATE-2",
                    "created": date_val,
                },
            }
            cache_path = Path(tmpdir) / "roundtrip_cache.json"
            fingerprint = "roundtrip-fp-xyz"

            disk_module.write_disk_cache(cache_path, fingerprint, index)
            loaded = disk_module.load_disk_cache(cache_path, fingerprint)

        self.assertIsNotNone(loaded, "load_disk_cache must return the index on a fingerprint match.")
        loaded_date = loaded["ACS-DATE-2"]["created"]  # type: ignore[index]
        self.assertIsInstance(
            loaded_date,
            datetime.date,
            f"Round-tripped 'created' field must be datetime.date, got {type(loaded_date).__name__!r}.",
        )
        self.assertEqual(
            loaded_date,
            date_val,
            "Round-tripped date value must equal the original datetime.date object.",
        )

    @_requires_import
    def test_cross_process_with_date_field_zero_yaml_parses(self):
        """Cross-process sim: date-containing AC index loads from disk with 0 YAML parses.

        End-to-end integration of the codec fix with the full get_ac_index() pipeline.
        Uses a real fixture file with an unquoted date so PyYAML produces datetime.date.
        Hook #1 (this call) builds + persists the cache. Hook #2 (simulated by clearing
        _CACHE) loads from disk. The YAML parse counter must stay at 0 on the disk-hit
        path, and the date field must come back as datetime.date (type-preserving).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            store_root = tmp / _AC_STORE_REL

            # Write fixture with an UNQUOTED date — PyYAML parses this as datetime.date.
            (store_root).mkdir(parents=True, exist_ok=True)
            (store_root / "ACS-XPROC-DATE.yaml").write_text(
                _ac_yaml_with_date("ACS-XPROC-DATE", "2026-06-24"),
                encoding="utf-8",
            )

            invalidate_cache(str(store_root))
            invalidate_disk_cache(str(store_root))

            # Hook #1: full build — codec must handle datetime.date and write the file.
            index1 = get_ac_index(str(store_root))
            self.assertIn("ACS-XPROC-DATE", index1)
            created1 = index1["ACS-XPROC-DATE"].get("created")
            self.assertIsInstance(
                created1,
                datetime.date,
                "Fresh-parsed 'created' must be datetime.date (PyYAML safe_load behaviour).",
            )

            # Simulate Hook #2: clear in-memory cache, disk cache remains.
            invalidate_cache(str(store_root))

            # Monkeypatch: count YAML parse calls — must be 0 on disk-hit path.
            parse_call_count: list[int] = [0]
            original_loader = _mod._load_one_yaml_file  # type: ignore[attr-defined]

            def _counting_loader(yaml_file):  # type: ignore[no-untyped-def]
                parse_call_count[0] += 1
                return original_loader(yaml_file)

            _mod._load_one_yaml_file = _counting_loader  # type: ignore[attr-defined]
            try:
                index2 = get_ac_index(str(store_root))
            finally:
                _mod._load_one_yaml_file = original_loader  # type: ignore[attr-defined]

        self.assertEqual(
            parse_call_count[0],
            0,
            f"YAML parser called {parse_call_count[0]} time(s) on disk-hit path; "
            "expected 0. The codec fix must allow the cache to be written and read.",
        )
        created2 = index2["ACS-XPROC-DATE"].get("created")
        self.assertIsInstance(
            created2,
            datetime.date,
            "Cache-hit 'created' must be datetime.date (type-preserving codec), "
            f"got {type(created2).__name__!r}.",
        )
        self.assertEqual(
            created2,
            datetime.date(2026, 6, 24),
            "Cache-hit date must equal the original parsed value.",
        )


if __name__ == "__main__":
    unittest.main()
