"""
MODULE: test_skill_registry_schema
GOAL: Validate that every entry in config/skill_registry.json has the
    required fields with correct types, and that optional fields (description,
    path, internal) are well-typed when present.
BUSINESS CONTEXT: Enforces the schema contract introduced by the
    add-skill-to-package SKILL.md update (EPIC-ArtifactCRUDClarity/09).
    When a developer promotes a skill via add-skill-to-package, the new
    registry entry must have id (non-empty str), description (non-empty str),
    path (non-empty str), and internal (bool). Existing entries that pre-date
    the update are validated for required fields only (id) and for type
    correctness of any optional fields that ARE present.
ARCHITECTURE: Pure unit tests using unittest.TestCase. No network, no DB.
    Reads config/skill_registry.json from the repo root resolved via __file__.
    All tests must complete in < 5 seconds.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_REGISTRY_PATH = _REPO_ROOT / "config" / "skill_registry.json"


class TestSkillRegistryRequiredFields(unittest.TestCase):
    """Every entry in skill_registry.json must have an 'id' field that is a
    non-empty string. This is the minimum required field for all entries."""

    def setUp(self) -> None:
        with _REGISTRY_PATH.open(encoding="utf-8") as fh:
            data = json.load(fh)
        self.skills: list[dict] = data["skills"]

    def test_registry_is_list(self) -> None:
        self.assertIsInstance(
            self.skills,
            list,
            msg="skill_registry.json 'skills' must be a list",
        )
        self.assertGreater(
            len(self.skills),
            0,
            msg="skill_registry.json 'skills' must have at least one entry",
        )

    def test_every_entry_has_id(self) -> None:
        missing: list[int] = []
        for idx, skill in enumerate(self.skills):
            if "id" not in skill:
                missing.append(idx)
        self.assertEqual(
            missing,
            [],
            msg=(
                f"skill_registry.json entries at indices {missing} are missing "
                f"the required 'id' field."
            ),
        )

    def test_id_is_nonempty_string(self) -> None:
        bad: list[str] = []
        for skill in self.skills:
            skill_id = skill.get("id", "")
            if not isinstance(skill_id, str) or not skill_id.strip():
                bad.append(repr(skill_id))
        self.assertEqual(
            bad,
            [],
            msg=(
                f"skill_registry.json entries have 'id' values that are not "
                f"non-empty strings: {bad}"
            ),
        )


class TestSkillRegistryOptionalFieldTypes(unittest.TestCase):
    """When optional schema fields (description, path, internal) are present,
    they must have the correct types.

    - description: non-empty string (str, len > 0)
    - path:        non-empty string (str, len > 0)
    - internal:    boolean (bool, not int)

    Entries that pre-date the add-skill-to-package registry-update step do
    not need to have these fields, but any entry that does have them must
    have the correct type. New entries added via the updated add-skill-to-package
    procedure will have all three fields.
    """

    def setUp(self) -> None:
        with _REGISTRY_PATH.open(encoding="utf-8") as fh:
            data = json.load(fh)
        self.skills: list[dict] = data["skills"]

    def test_description_is_nonempty_string_when_present(self) -> None:
        bad: list[str] = []
        for skill in self.skills:
            if "description" not in skill:
                continue
            val = skill["description"]
            if not isinstance(val, str) or not val.strip():
                bad.append(
                    f"id={skill.get('id', '?')!r}: description={val!r}"
                )
        self.assertEqual(
            bad,
            [],
            msg=(
                "skill_registry.json entries have 'description' values that are "
                f"not non-empty strings: {bad}"
            ),
        )

    def test_path_is_nonempty_string_when_present(self) -> None:
        bad: list[str] = []
        for skill in self.skills:
            if "path" not in skill:
                continue
            val = skill["path"]
            if not isinstance(val, str) or not val.strip():
                bad.append(
                    f"id={skill.get('id', '?')!r}: path={val!r}"
                )
        self.assertEqual(
            bad,
            [],
            msg=(
                "skill_registry.json entries have 'path' values that are "
                f"not non-empty strings: {bad}"
            ),
        )

    def test_internal_is_boolean_when_present(self) -> None:
        bad: list[str] = []
        for skill in self.skills:
            if "internal" not in skill:
                continue
            val = skill["internal"]
            # isinstance(True, int) is True in Python, so check bool explicitly
            if not isinstance(val, bool):
                bad.append(
                    f"id={skill.get('id', '?')!r}: internal={val!r} (type {type(val).__name__})"
                )
        self.assertEqual(
            bad,
            [],
            msg=(
                "skill_registry.json entries have 'internal' values that are "
                f"not booleans: {bad}"
            ),
        )


class TestSkillRegistryNewEntryContract(unittest.TestCase):
    """Entries added by the updated add-skill-to-package procedure should have
    all four schema fields: id, description, path, internal.

    This test validates that any entry with the 'path' field (the new canonical
    marker for entries added via the updated procedure) also has 'description'
    and 'internal', since 'path' is only added by the new Step 4 of
    add-skill-to-package.

    Legacy entries (those without 'path') may have partial fields (e.g.
    'internal' or 'description' alone) from before the schema was formalised.
    """

    def setUp(self) -> None:
        with _REGISTRY_PATH.open(encoding="utf-8") as fh:
            data = json.load(fh)
        self.skills: list[dict] = data["skills"]

    def test_path_entries_are_complete(self) -> None:
        """Any entry with 'path' must also have 'description' and 'internal'."""
        incomplete: list[str] = []
        for skill in self.skills:
            if "path" not in skill:
                continue
            missing = []
            if "description" not in skill:
                missing.append("description")
            if "internal" not in skill:
                missing.append("internal")
            if missing:
                incomplete.append(
                    f"id={skill.get('id', '?')!r}: has 'path' but missing {missing}"
                )
        self.assertEqual(
            incomplete,
            [],
            msg=(
                "skill_registry.json entries with 'path' must also have "
                "'description' and 'internal' (added via updated add-skill-to-package Step 4). "
                f"Incomplete entries: {incomplete}."
            ),
        )


if __name__ == "__main__":
    unittest.main()
