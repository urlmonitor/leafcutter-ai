"""
MODULE: test_skill_registry
GOAL: Unit tests for skill_registry.json correctness and schema validity.
BUSINESS CONTEXT: Verifies that the skill registry enforces uniqueness of IDs,
    that the 'internal' flag is correctly set on build-feature-ops-notes and
    build-single-ticket (per TICKET-20260519-disambiguate_build_feature_skills),
    and that the registry validates cleanly against skill_registry.schema.json
    after adding the optional 'internal' boolean field.
ARCHITECTURE: Pure unit tests using unittest.TestCase. No network, no DB.
    Reads leafcutter-ai/config/skill_registry.json and skill_registry.schema.json
    from the package root (resolved via __file__). Requires 'jsonschema' for
    schema validation tests; test is skipped gracefully if jsonschema is absent.
    All tests must complete in < 5 seconds.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_REGISTRY_PATH = _REPO_ROOT / "config" / "skill_registry.json"
_SCHEMA_PATH = _REPO_ROOT / "config" / "skill_registry.schema.json"


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


if __name__ == "__main__":
    unittest.main()
