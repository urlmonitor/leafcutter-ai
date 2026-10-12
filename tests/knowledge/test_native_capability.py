"""Capability records preserve authored fields without runtime admission effects."""

from copy import deepcopy
import importlib
import json
from pathlib import Path

import pytest

from knowledge.native_properties import decode, encode


def _extract(root):
    return importlib.import_module("knowledge.native_types.capability").extract(root)


def _entry():
    return {
        "id": "fixture.capability",
        "name": "Fixture capability",
        "description": "An authored capability",
        "version": "1.2.3",
        "request_kinds": ["evidence", "capability", "evidence"],
        "accepts_schemas": ["leafcutter.goal_request.v1"],
        "produces_schemas": ["leafcutter.evidence_bundle.v1"],
        "execution_mode": "native",
        "binding": "never.execute.this",
        "side_effect_class": "external_write",
        "admission": {
            "kind": "native_registration",
            "decision_ref": "TICKET-do-not-follow",
            "admitted_on": "2026-10-02",
            "admitted_by": "Authored human",
        },
    }


def _registry(root, entries, **context):
    value = {
        "$schema": "untrusted/schema.json",
        "_comment": "Authored commentary",
        "registry_id": "fixture.registry",
        "registry_version": 1,
        "capabilities": entries,
        **context,
    }
    path = root / "config/capability_registry.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8-sig")
    return path, value


def test_capability_all_fields_and_nested_extensions_round_trip(tmp_path):
    # covers: KM-400a-1-xiv
    # covers: KM-400a-3-i
    # test type: unit
    # angle: criterion
    entry = _entry()
    entry.update(
        operations=[],
        scope_tags=["z", "a", "z"],
        components=["finalize"],
        permissions_required=["never-grant-this"],
        enabled=False,
        availability={"status": "unavailable", "reason": None},
        routing="fixed",
        process_maturity=0,
        cost_hints={"jev_calls": 0, "host_operations": None, "latency_ms": 2},
        future={"a~/b": [None, {}, [], ["z", "a"], {"flag": False}]},
    )
    path, value = _registry(tmp_path, [entry], extension={"name": "root", "empty": []})
    before = path.read_bytes()

    (record,) = _extract(tmp_path)

    assert record.kind == "Capability"
    assert record.native_id == entry["id"]
    assert record.title == entry["name"]
    assert record.description == entry["description"]
    assert record.source_path == "config/capability_registry.json"
    assert record.locator == "/capabilities/0"
    assert record.metadata == entry
    assert len(record.metadata) == 21  # All twenty schema fields plus an extension.
    assert decode(encode(record.metadata)) == entry
    assert record.derived == {
        "registry_context": {k: v for k, v in value.items() if k != "capabilities"}
    }
    assert decode(encode(record.derived)) == record.derived
    assert path.read_bytes() == before


def test_capability_real_registry_exact_fields_and_no_defaults():
    # covers: KM-400a-1-xiv
    # covers: KM-400a-3-i
    # test type: integration
    # angle: real_artifact
    root = Path(__file__).resolve().parents[2]
    raw = json.loads((root / "config/capability_registry.json").read_text(encoding="utf-8"))
    records = _extract(root)
    assert len(records) == len(raw["capabilities"]) == 10
    assert any(record.native_id == "host.retrieval_needs" for record in records)
    assert {r.metadata["execution_mode"] for r in records} == {"native", "host_handoff"}
    assert {r.metadata["routing"] for r in records} == {"semantic", "fixed"}
    for index, (record, entry) in enumerate(zip(records, raw["capabilities"], strict=True)):
        assert record.native_id == entry["id"]
        assert record.locator == f"/capabilities/{index}"
        assert record.metadata == decode(encode(record.metadata)) == entry
        assert record.derived["registry_context"] == {
            k: v for k, v in raw.items() if k != "capabilities"
        }
        assert set(record.metadata).isdisjoint(
            {
                "enabled",
                "availability",
                "scope_tags",
                "components",
                "process_maturity",
                "registry_origin",
            }
        )


def test_capability_legacy_admission_does_not_read_references(tmp_path):
    # covers: KM-400a-1-xiv
    # covers: KM-400a-3-i
    # test type: unit
    # angle: boundary
    entry = _entry()
    entry["admission"].update(
        kind="legacy_admission",
        decision_ref="ADR-999",
        legacy_source={"registry": "never/read.json", "id": "legacy.id"},
    )
    _registry(tmp_path, [entry])
    (record,) = _extract(tmp_path)
    assert record.metadata == entry
    assert record.derived.keys() == {"registry_context"}
    assert isinstance(record.metadata["admission"]["admitted_on"], str)


def test_capability_source_order_and_changed_values_are_visible(tmp_path):
    # covers: KM-400a-1-xiv
    # covers: KM-400a-3-i
    # test type: unit
    # angle: criterion
    first, second = _entry(), _entry()
    first["id"], second["id"] = "z.first", "a.second"
    _registry(tmp_path, [first, second])
    before = _extract(tmp_path)
    first["description"] = "Changed source description"
    _registry(tmp_path, [second, first])
    after = _extract(tmp_path)
    assert [r.native_id for r in before] == ["z.first", "a.second"]
    assert [r.native_id for r in after] == ["a.second", "z.first"]
    assert before[0].locator == after[0].locator == "/capabilities/0"
    assert after[1].description == after[1].metadata["description"] == first["description"]
    assert before[0].description != after[1].description


def test_capability_absent_and_empty_registry_do_not_invent_records(tmp_path):
    # covers: KM-400a-1-xiv
    # covers: KM-400a-3-i
    # test type: unit
    # angle: boundary
    config = tmp_path / "config"
    config.mkdir()
    (config / "agent_registry.json").write_text(
        json.dumps({"agents": [{"id": "legacy"}]}), encoding="utf-8"
    )
    assert _extract(tmp_path) == []
    _registry(tmp_path, [])
    assert _extract(tmp_path) == []
    _registry(tmp_path, [_entry()])
    assert len(_extract(tmp_path)) == 1


@pytest.mark.parametrize(
    "contents", ["{", "[]", "{}", '{"registry_id":"x","registry_version":1,"capabilities":{}}']
)
def test_capability_malformed_envelope_fails_explicitly(tmp_path, contents):
    # covers: KM-400a-1-xiv
    # covers: KM-400a-3-i
    # test type: unit
    # angle: failure
    path, _ = _registry(tmp_path, [])
    path.write_text(contents, encoding="utf-8")
    with pytest.raises(ValueError, match="(JSON|capability)"):
        _extract(tmp_path)


@pytest.mark.parametrize(
    "field,value", [("registry_id", ""), ("registry_version", 0), ("registry_version", True)]
)
def test_capability_invalid_registry_identity_fails(tmp_path, field, value):
    # covers: KM-400a-1-xiv
    # covers: KM-400a-3-i
    # test type: unit
    # angle: failure
    _registry(tmp_path, [_entry()], **{field: value})
    with pytest.raises(ValueError, match="capability"):
        _extract(tmp_path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("id", "Bad Id"),
        ("id", None),
        ("name", ""),
        ("version", "1"),
        ("request_kinds", []),
        ("accepts_schemas", ["unknown"]),
        ("execution_mode", "unknown"),
        ("binding", ""),
        ("enabled", 1),
        ("process_maturity", True),
        ("process_maturity", 5),
        ("cost_hints", {"jev_calls": -1}),
        ("availability", {"status": "unknown"}),
        ("admission", {}),
        (
            "admission",
            {
                "kind": "legacy_admission",
                "decision_ref": "ADR-999",
                "admitted_by": "human",
                "admitted_on": "2026-10-02",
            },
        ),
    ],
)
def test_capability_malformed_entry_fails_explicitly(tmp_path, field, value):
    # covers: KM-400a-1-xiv
    # covers: KM-400a-3-i
    # test type: unit
    # angle: failure
    entry = _entry()
    entry[field] = value
    _registry(tmp_path, [entry])
    with pytest.raises(ValueError, match="capability"):
        _extract(tmp_path)


def test_capability_duplicate_ids_fail_without_source_changes(tmp_path):
    # covers: KM-400a-1-xiv
    # covers: KM-400a-3-i
    # test type: unit
    # angle: failure
    path, _ = _registry(tmp_path, [_entry(), _entry()])
    before = path.read_bytes()
    with pytest.raises(ValueError, match="duplicate capability"):
        _extract(tmp_path)
    assert path.read_bytes() == before


def test_capability_resolved_source_cannot_escape_snapshot(tmp_path, monkeypatch):
    # covers: KM-400a-1-xiv
    # covers: KM-400a-3-i
    # test type: unit
    # angle: boundary
    path, _ = _registry(tmp_path, [_entry()])
    original = Path.resolve
    outside = tmp_path.parent / "outside-capabilities.json"
    monkeypatch.setattr(
        Path, "resolve", lambda self, *a, **k: outside if self == path else original(self, *a, **k)
    )
    with pytest.raises(ValueError):
        _extract(tmp_path)


def test_capability_metadata_and_context_are_independent_copies(tmp_path, monkeypatch):
    # covers: KM-400a-1-xiv
    # covers: KM-400a-3-i
    # test type: unit
    # angle: boundary
    _, raw = _registry(tmp_path, [_entry(), {**_entry(), "id": "second"}], extension={"nested": []})
    module = importlib.import_module("knowledge.native_types.capability")
    before = deepcopy(raw)
    monkeypatch.setattr(module, "read_json", lambda path: raw)
    records = _extract(tmp_path)
    records[0].metadata["admission"]["admitted_by"] = "Mutated returned copy"
    records[0].derived["registry_context"]["extension"]["nested"].append("changed")
    assert raw == before
    assert records[1].derived["registry_context"]["extension"]["nested"] == []
