"""
MODULE: tests.kernel.contracts.test_schema_descriptions
GOAL: Every property of every committed kernel contract schema carries a description that says
    why the field exists, and a host packet hands that description to the LLM.
BUSINESS CONTEXT: Host packets send `output_json_schema` to a model and Atlas shows the same
    schemas to humans; a bare field name teaches neither reader the field's purpose.
ARCHITECTURE: Walks the committed JSON files (not the models), so a regenerate that drops the
    docstrings fails here. Fields that cannot be described without guessing sit in
    DESCRIPTION_ALLOWLIST with a reason per entry.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path
from typing import Any

from kernel.contracts import schema_ids as sid
from kernel.contracts.schema_catalog import SCHEMA_CATALOG, json_schema_for
from kernel.interaction.packets import tightened_schema
from tests.kernel.interaction.support import host_rig, start

REPO = Path(__file__).resolve().parents[3]
SCHEMA_FILES = [*sorted((REPO / "kernel" / "schemas").glob("*.schema.json")),
                REPO / "config" / "decision_record.schema.json",
                REPO / "config" / "kernel_config.schema.json"]

# "<file name>#<json pointer of the property>" -> reason it cannot be described yet.
DESCRIPTION_ALLOWLIST: dict[str, str] = {}


def _words(text: str) -> str:
    """Return text lowercased with separators and punctuation removed."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def undescribed(node: Any, pointer: str = "") -> list[tuple[str, str]]:
    """Return (pointer, problem) for each property lacking a real description."""
    found: list[tuple[str, str]] = []
    if isinstance(node, dict):
        for name, prop in (node.get("properties") or {}).items():
            where = f"{pointer}/properties/{name}"
            desc = prop.get("description") if isinstance(prop, dict) else None
            if not isinstance(desc, str) or not desc.strip():
                found.append((where, "missing description"))
            elif _words(desc) in {_words(name), _words(name) + "s"}:
                found.append((where, "description only repeats the name"))
        for key, child in node.items():
            found += undescribed(child, f"{pointer}/{key}")
    elif isinstance(node, list):
        for i, child in enumerate(node):
            found += undescribed(child, f"{pointer}/{i}")
    return found


class TestSchemaDescriptions(unittest.TestCase):
    """Committed schemas explain every field."""

    def test_every_property_has_a_purpose(self) -> None:
        problems: list[str] = []
        for path in SCHEMA_FILES:
            data = json.loads(path.read_text(encoding="utf-8"))
            problems += [f"{path.name}#{ptr}: {why}" for ptr, why in undescribed(data)
                         if f"{path.name}#{ptr}" not in DESCRIPTION_ALLOWLIST]
        self.assertEqual(problems, [], f"{len(problems)} undescribed properties; first: "
                                       f"{problems[:15]}")

    def test_allowlist_entries_are_still_needed(self) -> None:
        live = {f"{p.name}#{ptr}" for p in SCHEMA_FILES
                for ptr, _ in undescribed(json.loads(p.read_text(encoding="utf-8")))}
        self.assertEqual(sorted(set(DESCRIPTION_ALLOWLIST) - live), [])
        self.assertTrue(all(DESCRIPTION_ALLOWLIST.values()))

    def test_all_catalog_schemas_are_covered(self) -> None:
        names = {p.name for p in SCHEMA_FILES}
        self.assertTrue({f"{i}.schema.json" for i in SCHEMA_CATALOG} <= names)

    def test_host_packet_schema_carries_descriptions(self) -> None:
        sent = tightened_schema(sid.FINDINGS, json_schema_for(sid.FINDINGS))
        self.assertEqual(undescribed(sent), [])
        self.assertTrue(sent["properties"]["findings"]["description"])


class TestRealHostPacket(unittest.IsolatedAsyncioTestCase):
    """The packet the real graph builds carries the descriptions."""

    async def test_packet_output_schema_describes_every_field(self) -> None:
        run = await start(host_rig())
        schema = run.packet["output_json_schema"]
        self.assertEqual(undescribed(schema), [])
        self.assertTrue(schema["properties"]["coverage"]["description"])


if __name__ == "__main__":
    unittest.main()
