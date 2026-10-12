"""
MODULE: test_ac_schema_components_enum_parity
GOAL: Fail when the component enum in config/ac_store_schema.json
    (properties.components.items.enum) and the component ids declared in
    docs/components.json disagree, in either direction.
BUSINESS CONTEXT: The enum is a hand-maintained copy of the component registry.
    It drifted (decision_kernel and epic_retrospective were registered but
    absent), so every AC naming them failed schema validation. This test keeps
    the two lists in lockstep.
ARCHITECTURE: Pure data comparison of two on-disk JSON files, no I/O beyond
    reading them; ids are taken from the registry keys and cross-checked
    against each entry's own "id" field.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCHEMA = _REPO_ROOT / "config" / "ac_store_schema.json"
_COMPONENTS = _REPO_ROOT / "docs" / "components.json"


def _load(path: Path) -> dict:
    """Return the parsed JSON object at ``path``."""
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


class TestAcSchemaComponentsEnumParity(unittest.TestCase):
    """The schema enum must equal the registry's component ids."""

    def setUp(self) -> None:
        """Load the schema enum and the registry id set."""
        schema = _load(_SCHEMA)
        self.enum = schema["properties"]["components"]["items"]["enum"]
        registry = _load(_COMPONENTS)["components"]
        self.registry_ids = set(registry)
        self.inner_ids = {entry["id"] for entry in registry.values()}

    def test_registry_keys_match_entry_ids(self) -> None:
        """Registry keys and their inner ids are the same set."""
        self.assertEqual(self.registry_ids, self.inner_ids)

    def test_enum_has_no_duplicates(self) -> None:
        """The enum lists each id once."""
        self.assertEqual(len(self.enum), len(set(self.enum)))

    def test_registry_ids_missing_from_enum(self) -> None:
        """Every registered component id is allowed by the schema."""
        missing = sorted(self.registry_ids - set(self.enum))
        self.assertEqual(missing, [], f"in components.json but not in schema enum: {missing}")

    def test_enum_ids_missing_from_registry(self) -> None:
        """Every schema enum id is a registered component."""
        extra = sorted(set(self.enum) - self.registry_ids)
        self.assertEqual(extra, [], f"in schema enum but not in components.json: {extra}")


if __name__ == "__main__":
    unittest.main()
