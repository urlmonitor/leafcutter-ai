"""
MODULE: tests.kernel.registry.test_registry_load
GOAL: Test loading, validation, admission rules, hashing and snapshot pinning of the capability
    registry, including the committed config/capability_registry.json.
BUSINESS CONTEXT: The registry starts empty and legacy assets may enter only with a recorded
    admission decision; a run must be pinned to one snapshot (user override of Rev 3 2.1/6).
ARCHITECTURE: Real files in a temp directory, produced with json.dumps exactly as a writer would.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from kernel.registry import (
    RegistryCompatibilityError,
    RegistryError,
    load_component_ids,
    load_registry,
    verify_pinned,
)
from tests.kernel.helpers import load_json

REPO = Path(__file__).resolve().parents[3]
CONFIG = REPO / "config"


class RegistryCase(unittest.TestCase):
    """Base with a temp dir holding a registry next to the committed schema."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        shutil.copy(CONFIG / "capability_registry.schema.json", self.dir)

    def write(self, capabilities: list[dict], **top: object) -> Path:
        body = {"registry_id": "t.caps", "registry_version": 1, "capabilities": capabilities}
        body.update(top)
        path = self.dir / "capability_registry.json"
        path.write_text(json.dumps(body, indent=2), encoding="utf-8")
        return path


class TestCommittedRegistry(unittest.TestCase):
    """The committed registry holds exactly the seven V0 native and host-handoff entries."""

    def test_committed_registry_is_valid_and_lists_the_v0_capabilities(self) -> None:
        snapshot = load_registry(CONFIG / "capability_registry.json")
        self.assertEqual([d.id for d in snapshot.descriptors], [
            "decision", "host.formulate_question", "host.generate_options", "host.research",
            "host.synthesize", "research", "retrieve.repository"])
        self.assertEqual(snapshot.registry_id, "leafcutter.capabilities")

    def test_component_ids_load_from_components_json(self) -> None:
        ids = load_component_ids(REPO / "docs" / "components.json")
        self.assertIn("decision_kernel", ids)


class TestLoading(RegistryCase):
    """Loading and validation."""

    def test_native_entry_loads_with_origin(self) -> None:
        path = self.write([load_json("registry/descriptor_native.json")])
        snapshot = load_registry(path)
        self.assertEqual([d.id for d in snapshot.descriptors], ["retrieve.repository"])
        origin = snapshot.descriptors[0].registry_origin
        self.assertEqual((origin.registry_id, origin.registry_version), ("t.caps", 1))
        self.assertEqual(len(origin.entry_hash), 64)

    def test_entries_sorted_by_id(self) -> None:
        a, b = load_json("registry/descriptor_native.json"), load_json(
            "registry/descriptor_native.json")
        a["id"], b["id"] = "zeta", "alpha"
        snapshot = load_registry(self.write([a, b]))
        self.assertEqual([d.id for d in snapshot.descriptors], ["alpha", "zeta"])

    def test_duplicate_ids_rejected(self) -> None:
        entry = load_json("registry/descriptor_native.json")
        with self.assertRaises(RegistryError) as raised:
            load_registry(self.write([entry, dict(entry)]))
        self.assertIn("duplicate", str(raised.exception))

    def test_unknown_field_rejected_by_schema(self) -> None:
        entry = {**load_json("registry/descriptor_native.json"), "import_path": "os.system"}
        with self.assertRaises(RegistryError):
            load_registry(self.write([entry]))

    def test_unregistered_schema_id_rejected(self) -> None:
        entry = {**load_json("registry/descriptor_native.json"),
                 "accepts_schemas": ["leafcutter.made_up.v1"]}
        with self.assertRaises(RegistryError):
            load_registry(self.write([entry]))

    def test_unknown_component_rejected_when_components_given(self) -> None:
        entry = {**load_json("registry/descriptor_native.json"), "components": ["nope"]}
        path = self.write([entry])
        load_registry(path)
        with self.assertRaises(RegistryError):
            load_registry(path, known_components=frozenset({"decision_kernel"}))

    def test_missing_and_malformed_files(self) -> None:
        with self.assertRaises(RegistryError):
            load_registry(self.dir / "absent.json")
        bad = self.dir / "capability_registry.json"
        bad.write_text("{not json", encoding="utf-8")
        with self.assertRaises(RegistryError):
            load_registry(bad)

    def test_description_length_limit(self) -> None:
        entry = {**load_json("registry/descriptor_native.json"), "description": "x" * 401}
        with self.assertRaises(RegistryError):
            load_registry(self.write([entry]))


class TestAdmission(RegistryCase):
    """Legacy assets enter only by recorded decision."""

    def test_entry_without_admission_rejected(self) -> None:
        entry = load_json("registry/descriptor_native.json")
        del entry["admission"]
        with self.assertRaises(RegistryError):
            load_registry(self.write([entry]))

    def test_legacy_admission_with_adr_reference_loads(self) -> None:
        snapshot = load_registry(self.write([load_json("registry/descriptor_legacy.json")]))
        admission = snapshot.descriptors[0].admission
        self.assertEqual((admission.kind, admission.decision_ref), ("legacy_admission", "ADR-999"))
        self.assertEqual(admission.legacy_source.id, "test-writer")

    def test_legacy_admission_needs_source_and_adr_ref(self) -> None:
        for mutate in (lambda a: a.pop("legacy_source"),
                       lambda a: a.update(decision_ref="TICKET-20260930-KernelBootstrapV0"),
                       lambda a: a.update(decision_ref="because I said so")):
            entry = load_json("registry/descriptor_legacy.json")
            mutate(entry["admission"])
            with self.subTest(admission=entry["admission"]), self.assertRaises(RegistryError):
                load_registry(self.write([entry]))

    def test_native_entry_must_not_claim_legacy_source(self) -> None:
        entry = load_json("registry/descriptor_native.json")
        entry["admission"]["legacy_source"] = {"registry": "agent_registry", "id": "x"}
        with self.assertRaises(RegistryError):
            load_registry(self.write([entry]))

    def test_process_maturity_is_bounded(self) -> None:
        entry = {**load_json("registry/descriptor_native.json"), "process_maturity": 3}
        self.assertEqual(load_registry(self.write([entry])).descriptors[0].process_maturity, 3)
        entry["process_maturity"] = 5
        with self.assertRaises(RegistryError):
            load_registry(self.write([entry]))


class TestPinning(RegistryCase):
    """Snapshot hashing and pinning."""

    def test_hash_ignores_comment_but_changes_with_content(self) -> None:
        entry = load_json("registry/descriptor_native.json")
        first = load_registry(self.write([entry], _comment="one"))
        same = load_registry(self.write([entry], _comment="two"))
        changed = load_registry(self.write([{**entry, "version": "1.0.1"}]))
        self.assertEqual(first.content_hash, same.content_hash)
        self.assertNotEqual(first.content_hash, changed.content_hash)

    def test_verify_pinned_detects_silent_change(self) -> None:
        entry = load_json("registry/descriptor_native.json")
        pinned = load_registry(self.write([entry]))
        verify_pinned(pinned, load_registry(self.write([entry])))
        with self.assertRaises(RegistryCompatibilityError):
            verify_pinned(pinned, load_registry(self.write([{**entry, "enabled": False}])))

    def test_snapshot_get(self) -> None:
        snapshot = load_registry(self.write([load_json("registry/descriptor_native.json")]))
        self.assertEqual(snapshot.get("retrieve.repository").version, "1.0.0")
        self.assertIsNone(snapshot.get("missing"))


if __name__ == "__main__":
    unittest.main()

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:00 [python-coder]: The admission rules are tested through the JSON file path
#   (schema plus Pydantic) because that is the only way an entry can enter the registry.
#   (#KernelBootstrapV0/P1)
# ====================================================================
