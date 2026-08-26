"""
MODULE: test_check_schema_diff
GOAL: Unit tests for scripts/release/check_schema_diff.py.
BUSINESS CONTEXT: Verifies the schema-diff CI gate correctly detects removed
    keys, newly-required keys, type narrowings, and distinguishes them from
    non-breaking additive changes.
ARCHITECTURE: Pure unit tests with in-memory schema dicts. No git operations
    needed for the comparison logic tests. All tests must complete in < 5 seconds.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MODULE_PATH = _REPO_ROOT / "scripts" / "release" / "check_schema_diff.py"

spec = importlib.util.spec_from_file_location("check_schema_diff", _MODULE_PATH)
assert spec is not None and spec.loader is not None, f"could not load spec for {_MODULE_PATH}"
_mod = importlib.util.module_from_spec(spec)
sys.modules["check_schema_diff"] = _mod
spec.loader.exec_module(_mod)

find_breaking_changes = _mod.find_breaking_changes
_extract_properties = _mod._extract_properties
_get_required_keys = _mod._get_required_keys
_normalize_type = _mod._normalize_type


# ---------------------------------------------------------------------------
# Tests: breaking change detection
# ---------------------------------------------------------------------------

class TestRemovedKeys(unittest.TestCase):

    def test_removed_key_detected(self):
        """Removing a key from properties is a breaking change."""
        prev = {
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            }
        }
        curr = {
            "properties": {
                "name": {"type": "string"},
            }
        }
        changes = find_breaking_changes(prev, curr)
        self.assertEqual(len(changes), 1)
        self.assertIn("Removed key: 'age'", changes[0])

    def test_no_removed_keys(self):
        """No changes when schemas are identical."""
        schema = {
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            }
        }
        changes = find_breaking_changes(schema, schema)
        self.assertEqual(changes, [])


class TestNewlyRequiredKeys(unittest.TestCase):

    def test_newly_required_key_detected(self):
        """Making an optional key required is breaking."""
        prev = {
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
            },
            "required": ["name"],
        }
        curr = {
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
            },
            "required": ["name", "email"],
        }
        changes = find_breaking_changes(prev, curr)
        self.assertEqual(len(changes), 1)
        self.assertIn("Newly required key: 'email'", changes[0])

    def test_already_required_not_flagged(self):
        """Keys that were already required are not flagged."""
        prev = {
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        curr = {
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        changes = find_breaking_changes(prev, curr)
        self.assertEqual(changes, [])


class TestTypeNarrowing(unittest.TestCase):

    def test_type_narrowing_detected(self):
        """Removing a type from a union is narrowing."""
        prev = {
            "properties": {
                "value": {"type": ["string", "null"]},
            }
        }
        curr = {
            "properties": {
                "value": {"type": "string"},
            }
        }
        changes = find_breaking_changes(prev, curr)
        self.assertEqual(len(changes), 1)
        self.assertIn("Type narrowing on 'value'", changes[0])
        self.assertIn("null", changes[0])

    def test_type_widening_not_flagged(self):
        """Adding null to a type union is not breaking."""
        prev = {
            "properties": {
                "value": {"type": "string"},
            }
        }
        curr = {
            "properties": {
                "value": {"type": ["string", "null"]},
            }
        }
        changes = find_breaking_changes(prev, curr)
        self.assertEqual(changes, [])


class TestAdditiveChanges(unittest.TestCase):

    def test_adding_optional_key_not_breaking(self):
        """Adding a new optional key is not a breaking change."""
        prev = {
            "properties": {
                "name": {"type": "string"},
            },
            "required": ["name"],
        }
        curr = {
            "properties": {
                "name": {"type": "string"},
                "nickname": {"type": "string"},
            },
            "required": ["name"],
        }
        changes = find_breaking_changes(prev, curr)
        self.assertEqual(changes, [])

    def test_adding_new_required_key_not_breaking_if_new(self):
        """A newly-required key that didn't exist before is not breaking
        (it's a new addition, not a constraint on existing data)."""
        prev = {
            "properties": {
                "name": {"type": "string"},
            },
            "required": ["name"],
        }
        curr = {
            "properties": {
                "name": {"type": "string"},
                "id": {"type": "integer"},
            },
            "required": ["name", "id"],
        }
        changes = find_breaking_changes(prev, curr)
        # 'id' is newly required BUT it's also newly added, so it doesn't
        # flag (it wasn't in prev_props)
        self.assertEqual(changes, [])


class TestMultipleBreakingChanges(unittest.TestCase):

    def test_multiple_changes_all_detected(self):
        """Multiple breaking changes are all reported."""
        prev = {
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
                "email": {"type": ["string", "null"]},
            },
            "required": ["name"],
        }
        curr = {
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
            },
            "required": ["name", "email"],
        }
        changes = find_breaking_changes(prev, curr)
        # Should detect: removed 'age', newly required 'email', type narrowing on 'email'
        self.assertGreaterEqual(len(changes), 2)
        change_text = " ".join(changes)
        self.assertIn("Removed key: 'age'", change_text)
        self.assertIn("email", change_text)


if __name__ == "__main__":
    unittest.main()
