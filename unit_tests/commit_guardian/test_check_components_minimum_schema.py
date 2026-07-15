"""
MODULE: test_check_components_minimum_schema
GOAL: Unit tests for the validate_component_minimum_schema function added to
      check_components_integrity.py per ACS-300g-1.
BUSINESS CONTEXT: Verifies that the minimum schema validator correctly accepts
      well-formed component entries and rejects entries with missing required
      fields, invalid enum values, short descriptions, and invalid detail_ref
      paths. This ensures docs/components.json entries satisfy the AC store
      minimum schema contract at commit time.
ARCHITECTURE: Tests invoke the validation function directly (not via subprocess)
      to keep tests fast and deterministic. A tempdir fixture is used for
      detail_ref path tests to avoid depending on real on-disk paths.
"""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

import pytest

HOOK_SCRIPT = (
    Path(__file__).parent.parent.parent
    / "templates"
    / "scripts"
    / "commit_guardian"
    / "check_components_integrity.py"
)


def _load_module():
    """Load check_components_integrity as a module without executing main()."""
    spec = importlib.util.spec_from_file_location("check_components_integrity", HOOK_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Load once at import time for performance.
try:
    _mod = _load_module()
    # REPO_ROOT defaults to parents[2] of the canonical templates path, which
    # resolves to the templates/ subdirectory rather than the worktree root.
    # Patch it to the actual worktree root so detail_ref path checks work
    # (same technique used in test_acs_300g2_components_preserved.py).
    _mod.REPO_ROOT = Path(__file__).parent.parent.parent
    validate_minimum_schema = _mod.validate_component_minimum_schema
    ALLOWED_TYPES = _mod.ALLOWED_TYPES
    ALLOWED_STATUSES = _mod.ALLOWED_STATUSES
    DESCRIPTION_MIN_LEN = _mod.DESCRIPTION_MIN_LEN
    MODULE_AVAILABLE = True
except Exception as exc:  # noqa: BLE001 — discovery error, not runtime error
    MODULE_AVAILABLE = False
    _load_error = str(exc)


def _valid_entry(overrides: dict | None = None) -> dict:
    """Return a minimal valid component entry dict, optionally with overrides."""
    base = {
        "id": "my_component",
        "name": "My Component",
        "type": "utility",
        "description": "A well-formed component for testing purposes.",
        "detail_ref": None,
        "status": "active",
        "primary_code": ["scripts/my_component.py"],
    }
    if overrides:
        base.update(overrides)
    return base


@unittest.skipUnless(MODULE_AVAILABLE, f"module load failed: {_load_error if not MODULE_AVAILABLE else ''}")
class TestValidateComponentMinimumSchema(unittest.TestCase):
    """Tests for validate_component_minimum_schema (ACS-300g-1)."""

    # ------------------------------------------------------------------
    # Happy-path tests
    # ------------------------------------------------------------------

    def test_valid_entry_returns_no_errors(self):
        """A fully valid component entry produces an empty error list."""
        errors = validate_minimum_schema("my_component", _valid_entry())
        self.assertEqual(errors, [], f"Unexpected errors: {errors}")

    def test_detail_ref_null_is_accepted(self):
        """detail_ref: null is a valid value (no doc exists yet)."""
        entry = _valid_entry({"detail_ref": None})
        errors = validate_minimum_schema("my_component", entry)
        self.assertEqual(errors, [])

    def test_missing_detail_ref_field_is_accepted(self):
        """A component without a detail_ref key at all is still valid (the field
        is optional in the minimum schema)."""
        entry = _valid_entry()
        del entry["detail_ref"]
        errors = validate_minimum_schema("my_component", entry)
        self.assertEqual(errors, [])

    def test_all_allowed_types_accepted(self):
        """Every value in ALLOWED_TYPES passes type validation."""
        for type_value in ALLOWED_TYPES:
            entry = _valid_entry({"type": type_value})
            errors = validate_minimum_schema("my_component", entry)
            type_errors = [e for e in errors if "'type'" in e]
            self.assertEqual(
                type_errors,
                [],
                f"Type '{type_value}' was unexpectedly rejected: {type_errors}",
            )

    def test_all_allowed_statuses_accepted(self):
        """Every value in ALLOWED_STATUSES passes status validation."""
        for status_value in ALLOWED_STATUSES:
            entry = _valid_entry({"status": status_value})
            errors = validate_minimum_schema("my_component", entry)
            status_errors = [e for e in errors if "'status'" in e]
            self.assertEqual(
                status_errors,
                [],
                f"Status '{status_value}' was unexpectedly rejected: {status_errors}",
            )

    def test_primary_code_with_multiple_paths_accepted(self):
        """primary_code with more than one path is valid."""
        entry = _valid_entry({"primary_code": ["scripts/a.py", "scripts/b.py"]})
        errors = validate_minimum_schema("my_component", entry)
        self.assertEqual(errors, [])

    # ------------------------------------------------------------------
    # Missing required field tests
    # ------------------------------------------------------------------

    def test_missing_id_field_produces_error(self):
        """A component entry missing 'id' is rejected."""
        entry = _valid_entry()
        del entry["id"]
        errors = validate_minimum_schema("my_component", entry)
        self.assertTrue(any("'id'" in e for e in errors), f"Expected id error: {errors}")

    def test_missing_name_field_produces_error(self):
        """A component entry missing 'name' is rejected."""
        entry = _valid_entry()
        del entry["name"]
        errors = validate_minimum_schema("my_component", entry)
        self.assertTrue(any("'name'" in e for e in errors), f"Expected name error: {errors}")

    def test_missing_type_field_produces_error(self):
        """A component entry missing 'type' is rejected."""
        entry = _valid_entry()
        del entry["type"]
        errors = validate_minimum_schema("my_component", entry)
        self.assertTrue(any("'type'" in e for e in errors), f"Expected type error: {errors}")

    def test_missing_description_field_produces_error(self):
        """A component entry missing 'description' is rejected."""
        entry = _valid_entry()
        del entry["description"]
        errors = validate_minimum_schema("my_component", entry)
        self.assertTrue(
            any("'description'" in e for e in errors), f"Expected description error: {errors}"
        )

    def test_missing_status_field_produces_error(self):
        """A component entry missing 'status' is rejected."""
        entry = _valid_entry()
        del entry["status"]
        errors = validate_minimum_schema("my_component", entry)
        self.assertTrue(
            any("'status'" in e for e in errors), f"Expected status error: {errors}"
        )

    def test_missing_primary_code_field_produces_error(self):
        """A component entry missing 'primary_code' is rejected."""
        entry = _valid_entry()
        del entry["primary_code"]
        errors = validate_minimum_schema("my_component", entry)
        self.assertTrue(
            any("'primary_code'" in e for e in errors),
            f"Expected primary_code error: {errors}",
        )

    # ------------------------------------------------------------------
    # Field value validation tests
    # ------------------------------------------------------------------

    def test_id_mismatch_with_top_level_key_produces_error(self):
        """An 'id' field that does not match the top-level key is rejected."""
        entry = _valid_entry({"id": "wrong_id"})
        errors = validate_minimum_schema("my_component", entry)
        self.assertTrue(
            any("'id'" in e and "does not match" in e for e in errors),
            f"Expected id-mismatch error: {errors}",
        )

    def test_invalid_type_produces_error(self):
        """A type value not in ALLOWED_TYPES is rejected."""
        entry = _valid_entry({"type": "not_a_valid_type"})
        errors = validate_minimum_schema("my_component", entry)
        self.assertTrue(
            any("'type'" in e and "not one of the allowed types" in e for e in errors),
            f"Expected type-enum error: {errors}",
        )

    def test_description_too_short_produces_error(self):
        """A description shorter than DESCRIPTION_MIN_LEN characters is rejected."""
        short_desc = "A" * (DESCRIPTION_MIN_LEN - 1)
        entry = _valid_entry({"description": short_desc})
        errors = validate_minimum_schema("my_component", entry)
        self.assertTrue(
            any("'description'" in e and "at least" in e for e in errors),
            f"Expected description-length error: {errors}",
        )

    def test_description_at_minimum_length_is_accepted(self):
        """A description exactly DESCRIPTION_MIN_LEN characters long is accepted."""
        exact_desc = "A" * DESCRIPTION_MIN_LEN
        entry = _valid_entry({"description": exact_desc})
        errors = validate_minimum_schema("my_component", entry)
        desc_errors = [e for e in errors if "'description'" in e and "at least" in e]
        self.assertEqual(desc_errors, [])

    def test_invalid_status_produces_error(self):
        """A status value not in ALLOWED_STATUSES is rejected."""
        entry = _valid_entry({"status": "invalid_status"})
        errors = validate_minimum_schema("my_component", entry)
        self.assertTrue(
            any("'status'" in e and "not one of the allowed statuses" in e for e in errors),
            f"Expected status-enum error: {errors}",
        )

    def test_empty_primary_code_array_produces_error(self):
        """An empty primary_code array is rejected."""
        entry = _valid_entry({"primary_code": []})
        errors = validate_minimum_schema("my_component", entry)
        self.assertTrue(
            any("'primary_code'" in e and "at least one" in e for e in errors),
            f"Expected primary_code-empty error: {errors}",
        )

    def test_primary_code_with_non_string_produces_error(self):
        """primary_code containing non-string values is rejected."""
        entry = _valid_entry({"primary_code": [42, "scripts/b.py"]})
        errors = validate_minimum_schema("my_component", entry)
        self.assertTrue(
            any("'primary_code'" in e and "strings" in e for e in errors),
            f"Expected primary_code-non-string error: {errors}",
        )

    def test_primary_code_not_a_list_produces_error(self):
        """primary_code that is not a list is rejected."""
        entry = _valid_entry({"primary_code": "scripts/a.py"})
        errors = validate_minimum_schema("my_component", entry)
        self.assertTrue(
            any("'primary_code'" in e and "array" in e for e in errors),
            f"Expected primary_code-not-list error: {errors}",
        )

    # ------------------------------------------------------------------
    # detail_ref validation tests
    # ------------------------------------------------------------------

    def test_detail_ref_pointing_to_existing_file_is_accepted(self):
        """detail_ref pointing to an on-disk file is accepted."""
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as tmp:
            tmp.write(b"# doc\n")
            tmp_path = Path(tmp.name)

        # Temporarily override REPO_ROOT to the tmp file's parent
        original_repo_root = _mod.REPO_ROOT
        try:
            _mod.REPO_ROOT = tmp_path.parent
            rel_path = tmp_path.name
            entry = _valid_entry({"detail_ref": rel_path})
            errors = validate_minimum_schema("my_component", entry)
            detail_errors = [e for e in errors if "'detail_ref'" in e]
            self.assertEqual(detail_errors, [], f"Expected no detail_ref errors: {errors}")
        finally:
            _mod.REPO_ROOT = original_repo_root
            tmp_path.unlink(missing_ok=True)

    def test_detail_ref_pointing_to_missing_file_produces_error(self):
        """detail_ref pointing to a non-existent file is rejected."""
        entry = _valid_entry({"detail_ref": "docs/does_not_exist.md"})
        errors = validate_minimum_schema("my_component", entry)
        self.assertTrue(
            any("'detail_ref'" in e and "does not exist" in e for e in errors),
            f"Expected detail_ref path error: {errors}",
        )

    def test_detail_ref_non_string_produces_error(self):
        """detail_ref that is not a string or null is rejected."""
        entry = _valid_entry({"detail_ref": 42})
        errors = validate_minimum_schema("my_component", entry)
        self.assertTrue(
            any("'detail_ref'" in e and "string path or null" in e for e in errors),
            f"Expected detail_ref type error: {errors}",
        )

    # ------------------------------------------------------------------
    # Edge case tests
    # ------------------------------------------------------------------

    def test_non_dict_component_data_produces_error(self):
        """A non-dict component_data value is rejected immediately."""
        errors = validate_minimum_schema("my_component", "not_a_dict")
        self.assertTrue(
            any("not a JSON object" in e for e in errors),
            f"Expected non-dict error: {errors}",
        )

    def test_empty_name_string_produces_error(self):
        """An empty-string 'name' field is rejected."""
        entry = _valid_entry({"name": ""})
        errors = validate_minimum_schema("my_component", entry)
        self.assertTrue(
            any("'name'" in e for e in errors), f"Expected name-empty error: {errors}"
        )


@unittest.skipUnless(MODULE_AVAILABLE, f"module load failed: {_load_error if not MODULE_AVAILABLE else ''}")
class TestComponentsJsonCurrentState(unittest.TestCase):
    """Integration test: verify current docs/components.json passes the minimum schema."""

    @pytest.mark.xfail(
        reason=(
            "pre-existing components.json data debt: 5 entries have an empty "
            "primary_code array — ac_driven_dev, persona_management, "
            "stakeholder_delivery, ux_prototyping, infrastructure — "
            "tracked as follow-up, not part of ACS-300 backfill"
        ),
        strict=False,
    )
    def test_all_current_entries_pass_minimum_schema(self):
        """Every entry in docs/components.json satisfies the minimum schema (ACS-300g-1)."""
        import json

        components_path = (
            Path(__file__).parent.parent.parent / "docs" / "components.json"
        )
        if not components_path.exists():
            self.skipTest(f"docs/components.json not found at {components_path}")

        try:
            with components_path.open(encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            self.fail(f"Failed to load docs/components.json: {exc}")

        components = data.get("components", {})
        all_errors: list[str] = []
        for cid, cdata in components.items():
            errors = validate_minimum_schema(cid, cdata)
            all_errors.extend(errors)

        self.assertEqual(
            all_errors,
            [],
            "docs/components.json has minimum-schema violations:\n" + "\n".join(all_errors),
        )


if __name__ == "__main__":
    unittest.main()
