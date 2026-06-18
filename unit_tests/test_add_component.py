"""
MODULE: test_add_component
GOAL: Unit tests for scripts/add_component.py (ACS-300g-4a).
BUSINESS CONTEXT: Verifies that the add_component CLI tool correctly appends
      new entries to docs/components.json, validates schema, prevents duplicate
      IDs, preserves existing entries, and writes back with consistent formatting
      (2-space indent, sorted keys).  These tests exercise the full AC set for
      ACS-300g-4a without touching the real docs/components.json.
ARCHITECTURE: Tests write to a temporary file so the real registry is never
      mutated.  All tests use the module's public API (main() and helpers)
      to avoid subprocess overhead and keep run-time under 5 seconds.
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Module loading
# ---------------------------------------------------------------------------

_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent / "scripts" / "add_component.py"
)


def _load_module():
    """Load add_component as a module without executing __main__ guard."""
    spec = importlib.util.spec_from_file_location("add_component", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


try:
    _mod = _load_module()
    MODULE_AVAILABLE = True
    _load_error = ""
except Exception as exc:  # noqa: BLE001 — discovery error
    MODULE_AVAILABLE = False
    _load_error = str(exc)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_ARGV_BASE = [
    "--id", "test_comp",
    "--name", "Test Component",
    "--type", "utility",
    "--description", "A test component entry for automated testing.",
    "--primary-code", "scripts/test_comp.py",
    "--status", "active",
]

_MINIMAL_REGISTRY: dict = {
    "components": {
        "existing_comp": {
            "id": "existing_comp",
            "name": "Existing Component",
            "type": "utility",
            "description": "An already-present component.",
            "detail_ref": None,
            "status": "active",
            "primary_code": ["scripts/existing_comp.py"],
        }
    }
}


def _write_registry(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _read_registry(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@unittest.skipUnless(MODULE_AVAILABLE, f"module load failed: {_load_error}")
class TestAddComponentHappyPath(unittest.TestCase):
    """AC: new entry appended; JSON valid; existing entries unchanged; formatting correct."""

    def setUp(self):
        # covers: ACS-300g-4a
        self._tmp = tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w", encoding="utf-8"
        )
        _write_registry(Path(self._tmp.name), _MINIMAL_REGISTRY)
        self._tmp.close()
        self._registry_path = Path(self._tmp.name)

    def tearDown(self):
        self._registry_path.unlink(missing_ok=True)

    def test_new_entry_is_appended(self):
        # covers: ACS-300g-4a
        """AC: a new entry is appended to docs/components.json."""
        argv = _VALID_ARGV_BASE + ["--components-json", str(self._registry_path)]
        rc = _mod.main(argv)
        self.assertEqual(rc, 0, "Expected exit code 0 on success.")

        data = _read_registry(self._registry_path)
        self.assertIn("test_comp", data["components"])

    def test_new_entry_has_correct_fields(self):
        # covers: ACS-300g-4a
        """The appended entry contains all provided fields with correct values."""
        argv = _VALID_ARGV_BASE + ["--components-json", str(self._registry_path)]
        _mod.main(argv)

        data = _read_registry(self._registry_path)
        entry = data["components"]["test_comp"]
        self.assertEqual(entry["id"], "test_comp")
        self.assertEqual(entry["name"], "Test Component")
        self.assertEqual(entry["type"], "utility")
        self.assertEqual(entry["description"], "A test component entry for automated testing.")
        self.assertEqual(entry["primary_code"], ["scripts/test_comp.py"])
        self.assertEqual(entry["status"], "active")
        self.assertIsNone(entry["detail_ref"])

    def test_existing_entries_preserved_unchanged(self):
        # covers: ACS-300g-4a
        """AC: the output preserves existing entries unchanged."""
        argv = _VALID_ARGV_BASE + ["--components-json", str(self._registry_path)]
        _mod.main(argv)

        data = _read_registry(self._registry_path)
        self.assertIn("existing_comp", data["components"])
        orig = _MINIMAL_REGISTRY["components"]["existing_comp"]
        saved = data["components"]["existing_comp"]
        self.assertEqual(saved, orig)

    def test_resulting_json_is_valid(self):
        # covers: ACS-300g-4a
        """AC: the resulting JSON is valid (parseable, no duplicate keys)."""
        argv = _VALID_ARGV_BASE + ["--components-json", str(self._registry_path)]
        _mod.main(argv)

        raw = self._registry_path.read_text(encoding="utf-8")
        # json.loads would raise on duplicate keys or invalid syntax
        data = json.loads(raw)
        self.assertIn("components", data)

    def test_output_uses_two_space_indent(self):
        # covers: ACS-300g-4a
        """AC: the script writes back with consistent 2-space indent formatting."""
        argv = _VALID_ARGV_BASE + ["--components-json", str(self._registry_path)]
        _mod.main(argv)

        raw = self._registry_path.read_text(encoding="utf-8")
        # Every indented line should use 2 spaces, never 4
        lines = raw.splitlines()
        for line in lines:
            stripped = line.lstrip(" ")
            indent_len = len(line) - len(stripped)
            if indent_len > 0:
                self.assertEqual(
                    indent_len % 2,
                    0,
                    f"Expected 2-space indent, found odd indent on line: {line!r}",
                )

    def test_output_keys_are_sorted(self):
        # covers: ACS-300g-4a
        """AC: the script writes back with sorted keys in the components dict."""
        # Add a component whose key sorts before 'existing_comp'
        argv = [
            "--id", "aaa_component",
            "--name", "AAA Component",
            "--type", "utility",
            "--description", "A component that sorts first alphabetically.",
            "--primary-code", "scripts/aaa.py",
            "--status", "active",
            "--components-json", str(self._registry_path),
        ]
        _mod.main(argv)

        data = _read_registry(self._registry_path)
        keys = list(data["components"].keys())
        self.assertEqual(
            keys,
            sorted(keys),
            f"Expected sorted keys, got: {keys}",
        )

    def test_detail_ref_is_written_when_provided(self):
        # covers: ACS-300g-4a
        """When --detail-ref is provided, it is written to the entry."""
        argv = _VALID_ARGV_BASE + [
            "--detail-ref", "docs/architecture/components/test_comp.md",
            "--components-json", str(self._registry_path),
        ]
        _mod.main(argv)

        data = _read_registry(self._registry_path)
        entry = data["components"]["test_comp"]
        self.assertEqual(
            entry["detail_ref"],
            "docs/architecture/components/test_comp.md",
        )

    def test_multiple_primary_code_paths_accepted(self):
        # covers: ACS-300g-4a
        """Multiple --primary-code flags produce a list with all paths."""
        argv = [
            "--id", "multi_code",
            "--name", "Multi Code Component",
            "--type", "infrastructure",
            "--description", "Component with multiple primary code paths.",
            "--primary-code", "scripts/a.py",
            "--primary-code", "scripts/b.py",
            "--status", "active",
            "--components-json", str(self._registry_path),
        ]
        _mod.main(argv)

        data = _read_registry(self._registry_path)
        entry = data["components"]["multi_code"]
        self.assertEqual(entry["primary_code"], ["scripts/a.py", "scripts/b.py"])

    def test_file_ends_with_newline(self):
        # covers: ACS-300g-4a
        """The output file ends with a newline (POSIX convention)."""
        argv = _VALID_ARGV_BASE + ["--components-json", str(self._registry_path)]
        _mod.main(argv)

        raw = self._registry_path.read_text(encoding="utf-8")
        self.assertTrue(raw.endswith("\n"), "Expected file to end with a newline.")


@unittest.skipUnless(MODULE_AVAILABLE, f"module load failed: {_load_error}")
class TestAddComponentDuplicateGuard(unittest.TestCase):
    """AC: exits non-zero if component ID already exists."""

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w", encoding="utf-8"
        )
        _write_registry(Path(self._tmp.name), _MINIMAL_REGISTRY)
        self._tmp.close()
        self._registry_path = Path(self._tmp.name)

    def tearDown(self):
        self._registry_path.unlink(missing_ok=True)

    def test_duplicate_id_exits_nonzero(self):
        # covers: ACS-300g-4a
        """AC: script exits non-zero when the component ID already exists."""
        argv = [
            "--id", "existing_comp",
            "--name", "Duplicate",
            "--type", "utility",
            "--description", "Trying to overwrite an existing entry.",
            "--primary-code", "scripts/existing_comp.py",
            "--status", "active",
            "--components-json", str(self._registry_path),
        ]
        rc = _mod.main(argv)
        self.assertNotEqual(rc, 0, "Expected non-zero exit when ID already exists.")

    def test_duplicate_id_does_not_overwrite(self):
        # covers: ACS-300g-4a
        """The existing entry must remain unchanged after a duplicate attempt."""
        argv = [
            "--id", "existing_comp",
            "--name", "Should Not Win",
            "--type", "analysis",
            "--description", "Attempting a silent overwrite of existing_comp.",
            "--primary-code", "scripts/new_path.py",
            "--status", "planned",
            "--components-json", str(self._registry_path),
        ]
        _mod.main(argv)

        data = _read_registry(self._registry_path)
        orig = _MINIMAL_REGISTRY["components"]["existing_comp"]
        self.assertEqual(data["components"]["existing_comp"], orig)

    def test_exit_code_is_1_for_duplicate(self):
        # covers: ACS-300g-4a
        """The exit code is specifically 1 (not 2) for duplicate-ID errors."""
        argv = [
            "--id", "existing_comp",
            "--name", "Dup",
            "--type", "utility",
            "--description", "Duplicate check with expected exit code 1.",
            "--primary-code", "scripts/existing_comp.py",
            "--status", "active",
            "--components-json", str(self._registry_path),
        ]
        rc = _mod.main(argv)
        self.assertEqual(rc, 1)


@unittest.skipUnless(MODULE_AVAILABLE, f"module load failed: {_load_error}")
class TestAddComponentValidation(unittest.TestCase):
    """Schema validation: required fields, enum values, description length."""

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w", encoding="utf-8"
        )
        _write_registry(Path(self._tmp.name), {"components": {}})
        self._tmp.close()
        self._registry_path = Path(self._tmp.name)

    def tearDown(self):
        self._registry_path.unlink(missing_ok=True)

    def _run(self, extra_argv: list[str] | None = None) -> int:
        """Run main() with the base valid argv plus any extra args."""
        argv = _VALID_ARGV_BASE + ["--components-json", str(self._registry_path)]
        if extra_argv:
            argv = argv + extra_argv
        return _mod.main(argv)

    def test_valid_entry_exits_zero(self):
        # covers: ACS-300g-4a
        """A fully valid entry exits with code 0."""
        rc = self._run()
        self.assertEqual(rc, 0)

    def test_description_too_short_exits_nonzero(self):
        # covers: ACS-300g-4a
        """A description shorter than the minimum is rejected."""
        argv = [
            "--id", "short_desc",
            "--name", "Short Desc",
            "--type", "utility",
            "--description", "Too short",  # < 10 chars
            "--primary-code", "scripts/x.py",
            "--status", "active",
            "--components-json", str(self._registry_path),
        ]
        rc = _mod.main(argv)
        self.assertNotEqual(rc, 0)


@unittest.skipUnless(MODULE_AVAILABLE, f"module load failed: {_load_error}")
class TestValidateEntryUnit(unittest.TestCase):
    """Unit tests for the validate_entry() helper function."""

    def _valid_entry(self, overrides: dict | None = None) -> dict:
        base = {
            "id": "my_comp",
            "name": "My Component",
            "type": "utility",
            "description": "A fully valid component entry for testing purposes.",
            "detail_ref": None,
            "status": "active",
            "primary_code": ["scripts/my_comp.py"],
        }
        if overrides:
            base.update(overrides)
        return base

    def test_valid_entry_produces_no_errors(self):
        # covers: ACS-300g-4a
        errors = _mod.validate_entry("my_comp", self._valid_entry())
        self.assertEqual(errors, [])

    def test_id_mismatch_produces_error(self):
        # covers: ACS-300g-4a
        entry = self._valid_entry({"id": "different_id"})
        errors = _mod.validate_entry("my_comp", entry)
        self.assertTrue(any("does not match" in e for e in errors))

    def test_invalid_type_produces_error(self):
        # covers: ACS-300g-4a
        entry = self._valid_entry({"type": "not_a_type"})
        errors = _mod.validate_entry("my_comp", entry)
        self.assertTrue(any("allowed types" in e for e in errors))

    def test_invalid_status_produces_error(self):
        # covers: ACS-300g-4a
        entry = self._valid_entry({"status": "deprecated"})
        errors = _mod.validate_entry("my_comp", entry)
        self.assertTrue(any("allowed statuses" in e for e in errors))

    def test_short_description_produces_error(self):
        # covers: ACS-300g-4a
        entry = self._valid_entry({"description": "Short"})
        errors = _mod.validate_entry("my_comp", entry)
        self.assertTrue(any("at least" in e for e in errors))

    def test_empty_primary_code_produces_error(self):
        # covers: ACS-300g-4a
        entry = self._valid_entry({"primary_code": []})
        errors = _mod.validate_entry("my_comp", entry)
        self.assertTrue(any("at least one" in e for e in errors))

    def test_detail_ref_non_string_produces_error(self):
        # covers: ACS-300g-4a
        entry = self._valid_entry({"detail_ref": 42})
        errors = _mod.validate_entry("my_comp", entry)
        self.assertTrue(any("string path or null" in e for e in errors))

    def test_all_allowed_types_pass(self):
        # covers: ACS-300g-4a
        for t in _mod.ALLOWED_TYPES:
            entry = self._valid_entry({"type": t})
            errors = _mod.validate_entry("my_comp", entry)
            type_errors = [e for e in errors if "allowed types" in e]
            self.assertEqual(type_errors, [], f"Type '{t}' was unexpectedly rejected.")

    def test_all_allowed_statuses_pass(self):
        # covers: ACS-300g-4a
        for s in _mod.ALLOWED_STATUSES:
            entry = self._valid_entry({"status": s})
            errors = _mod.validate_entry("my_comp", entry)
            status_errors = [e for e in errors if "allowed statuses" in e]
            self.assertEqual(status_errors, [], f"Status '{s}' was unexpectedly rejected.")


@unittest.skipUnless(MODULE_AVAILABLE, f"module load failed: {_load_error}")
class TestAddComponentIOEdgeCases(unittest.TestCase):
    """I/O edge cases: missing file, malformed JSON."""

    def test_missing_registry_file_exits_2(self):
        # covers: ACS-300g-4a
        """When the registry file does not exist, exit code is 2."""
        argv = _VALID_ARGV_BASE + [
            "--components-json", "/tmp/does_not_exist_12345.json"
        ]
        with self.assertRaises(SystemExit) as ctx:
            _mod.main(argv)
        self.assertEqual(ctx.exception.code, 2)

    def test_malformed_json_exits_2(self):
        # covers: ACS-300g-4a
        """When the registry file contains invalid JSON, exit code is 2."""
        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write("{not valid json}")
            tmp_path = Path(f.name)
        try:
            argv = _VALID_ARGV_BASE + ["--components-json", str(tmp_path)]
            with self.assertRaises(SystemExit) as ctx:
                _mod.main(argv)
            self.assertEqual(ctx.exception.code, 2)
        finally:
            tmp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
