"""
MODULE: test_skill_registry
GOAL: Unit tests for skill_registry.json correctness, schema validity, and
    bidirectional consistency with templates/skills/ on disk.
BUSINESS CONTEXT: Verifies that the skill registry enforces uniqueness of IDs,
    that the 'internal' flag is correctly set on build-feature-ops-notes and
    build-single-ticket (per TICKET-20260519-disambiguate_build_feature_skills),
    that the registry validates cleanly against skill_registry.schema.json
    after adding the optional 'internal' boolean field, and that there are no
    orphaned skill directories (on disk without a registry entry) or orphaned
    registry entries (in the registry without a corresponding directory).
ARCHITECTURE: Pure unit tests using unittest.TestCase. No network, no DB.
    Reads leafcutter-ai/config/skill_registry.json and skill_registry.schema.json
    from the package root (resolved via __file__). The bidirectional tests call
    scripts.registry_validator.validate_skill_registry() rather than
    re-implementing the logic. Requires 'jsonschema' for schema validation tests;
    test is skipped gracefully if jsonschema is absent.
    All tests must complete in < 5 seconds.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_REGISTRY_PATH = _REPO_ROOT / "config" / "skill_registry.json"
_SCHEMA_PATH = _REPO_ROOT / "config" / "skill_registry.schema.json"
_SKILLS_DIR = _REPO_ROOT / "templates" / "skills"

# Make sure scripts/ is importable even when pytest is run from the repo root.
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


class TestSkillRegistryUniqueness(unittest.TestCase):
    """No two entries in skill_registry.json may share the same id."""

    def setUp(self) -> None:
        with _REGISTRY_PATH.open(encoding="utf-8") as fh:
            self.registry = json.load(fh)

    def test_no_duplicate_ids(self) -> None:
        ids = [skill["id"] for skill in self.registry["skills"]]
        seen: set[str] = set()
        duplicates: list[str] = []
        for skill_id in ids:
            if skill_id in seen:
                duplicates.append(skill_id)
            seen.add(skill_id)
        self.assertEqual(
            duplicates,
            [],
            msg=f"Duplicate skill IDs found in skill_registry.json: {duplicates}",
        )


class TestSkillRegistryInternalFlag(unittest.TestCase):
    """build-feature-ops-notes and build-single-ticket must have internal: true."""

    def setUp(self) -> None:
        with _REGISTRY_PATH.open(encoding="utf-8") as fh:
            registry = json.load(fh)
        self.skills_by_id = {skill["id"]: skill for skill in registry["skills"]}

    def test_build_feature_ops_notes_is_internal(self) -> None:
        skill_id = "build-feature-ops-notes"
        self.assertIn(
            skill_id,
            self.skills_by_id,
            msg=f"Expected entry with id '{skill_id}' in skill_registry.json",
        )
        skill = self.skills_by_id[skill_id]
        self.assertTrue(
            skill.get("internal", False),
            msg=f"Expected '{skill_id}' to have internal: true in skill_registry.json",
        )

    def test_build_single_ticket_is_internal(self) -> None:
        skill_id = "build-single-ticket"
        self.assertIn(
            skill_id,
            self.skills_by_id,
            msg=f"Expected entry with id '{skill_id}' in skill_registry.json",
        )
        skill = self.skills_by_id[skill_id]
        self.assertTrue(
            skill.get("internal", False),
            msg=f"Expected '{skill_id}' to have internal: true in skill_registry.json",
        )

    def test_build_feature_id_not_present(self) -> None:
        """The old 'build-feature' id must be gone (renamed to build-feature-ops-notes)."""
        self.assertNotIn(
            "build-feature",
            self.skills_by_id,
            msg=(
                "Found old id 'build-feature' in skill_registry.json — "
                "it must be renamed to 'build-feature-ops-notes'."
            ),
        )


class TestSkillRegistrySchemaValidation(unittest.TestCase):
    """skill_registry.json must validate against skill_registry.schema.json."""

    def test_registry_validates_against_schema(self) -> None:
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema not installed — skipping schema validation test")

        with _SCHEMA_PATH.open(encoding="utf-8") as fh:
            schema = json.load(fh)
        with _REGISTRY_PATH.open(encoding="utf-8") as fh:
            registry = json.load(fh)

        try:
            jsonschema.validate(instance=registry, schema=schema)
        except jsonschema.ValidationError as exc:
            self.fail(
                f"skill_registry.json failed schema validation: {exc.message}"
            )

    def test_schema_allows_internal_field(self) -> None:
        """The schema's skill definition must allow the optional 'internal' boolean."""
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema not installed — skipping schema validation test")

        with _SCHEMA_PATH.open(encoding="utf-8") as fh:
            schema = json.load(fh)

        # Attempt to validate a minimal skill entry that includes internal: true.
        minimal_registry = {
            "skills": [
                {
                    "id": "test-skill",
                    "name": "Test Skill",
                    "portable": True,
                    "domain": None,
                    "dependencies": [],
                    "internal": True,
                }
            ]
        }
        try:
            jsonschema.validate(instance=minimal_registry, schema=schema)
        except jsonschema.ValidationError as exc:
            self.fail(
                f"Schema rejected a skill entry with 'internal: true': {exc.message}"
            )


class TestSkillRegistryBidirectional(unittest.TestCase):
    """Bidirectional consistency: skill directories on disk vs registry entries.

    Delegates all logic to registry_validator.validate_skill_registry() so
    these tests remain thin and the logic stays in one place.
    """

    def setUp(self) -> None:
        from registry_validator import validate_skill_registry

        self._orphaned_dirs, self._orphaned_entries = validate_skill_registry(
            _REPO_ROOT, _SKILLS_DIR, _REGISTRY_PATH
        )

    def test_no_orphaned_directories(self) -> None:
        """Every directory under templates/skills/ must have a registry entry."""
        self.assertEqual(
            self._orphaned_dirs,
            [],
            msg=(
                "Skill directories exist on disk with no matching skill_registry.json "
                f"entry. Add entries for: {self._orphaned_dirs}"
            ),
        )

    def test_no_orphaned_entries(self) -> None:
        """Every registry entry must have a corresponding directory on disk."""
        self.assertEqual(
            self._orphaned_entries,
            [],
            msg=(
                "skill_registry.json has entries with no matching directory under "
                f"templates/skills/. Remove or fix entries for: {self._orphaned_entries}"
            ),
        )

    def test_registry_entry_schema(self) -> None:
        """Every entry in skill_registry.json has required fields with correct types.

        Checks 'id' (str), 'name' (str), 'portable' (bool), 'domain' (str or None),
        and 'dependencies' (list). This is a lightweight structural check that
        catches hand-edited entries that break the consumer contract.
        """
        with _REGISTRY_PATH.open(encoding="utf-8") as fh:
            registry = json.load(fh)

        errors: list[str] = []
        for skill in registry.get("skills", []):
            skill_id = skill.get("id", "<no id>")
            if not isinstance(skill.get("id"), str):
                errors.append(f"[{skill_id}] 'id' must be a string")
            if not isinstance(skill.get("name"), str):
                errors.append(f"[{skill_id}] 'name' must be a string")
            if not isinstance(skill.get("portable"), bool):
                errors.append(f"[{skill_id}] 'portable' must be a boolean")
            if "domain" not in skill:
                errors.append(f"[{skill_id}] 'domain' field is required (may be null)")
            elif skill["domain"] is not None and not isinstance(skill["domain"], str):
                errors.append(f"[{skill_id}] 'domain' must be a string or null")
            if not isinstance(skill.get("dependencies"), list):
                errors.append(f"[{skill_id}] 'dependencies' must be an array")

        self.assertEqual(
            errors,
            [],
            msg=f"Registry entry schema violations found:\n" + "\n".join(errors),
        )


if __name__ == "__main__":
    unittest.main()
