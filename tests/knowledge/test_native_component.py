"""Component extraction preserves authored registry fields and exact identities."""

import importlib
import json
from pathlib import Path

import pytest
import yaml


def _extract(root):
    return importlib.import_module("knowledge.native_types.component").extract(root)


def _registry(root, components):
    path = root / "docs/components.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"components": components}), encoding="utf-8")
    return path


def test_component_preserves_every_field_and_registry_identity(tmp_path) -> None:
    # covers: KM-400a-1-iii
    # covers: KM-400a-3-i
    # test type: unit
    # angle: criterion
    entries: dict[str, dict[str, object]] = {
        "z~component/1": {
            "id": "z~component/1",
            "name": "Exact registry name",
            "description": "An authored component description",
            "type": "orchestration",
            "status": "active",
            "detail_ref": "docs/architecture/components/other-stem.md",
            "primary_code": ["z.py", "a.py", "z.py"],
            "agent_affinity": [],
            "exposed_interfaces": [
                {"name": "first", "type": "event", "shape": {"a": 1}},
                {"name": "second", "type": "data_shape", "shape": {"a": False}},
            ],
            "future": {"a~/b": [None, True, 2, 3.5, "4", {}, [], ["x"]]},
        },
        "a_component": {"id": "a_component", "detail_ref": None},
    }
    path = _registry(tmp_path, entries)
    detail_ref = entries["z~component/1"]["detail_ref"]
    assert isinstance(detail_ref, str)
    document = tmp_path / detail_ref
    document.parent.mkdir(parents=True)
    document.write_text(
        "---\n" + yaml.safe_dump({"type": "reference", "status": "draft"}) + "---\nBody",
        encoding="utf-8",
    )

    records = _extract(tmp_path)

    assert [record.native_id for record in records] == ["a_component", "z~component/1"]
    assert len(records) == len(entries)
    by_id = {record.native_id: record for record in records}
    for key, entry in entries.items():
        record = by_id[key]
        assert record.kind == "Component"
        assert record.source_path == "docs/components.json"
        assert record.metadata == entry
        assert record.derived == {}
    assert by_id["z~component/1"].locator == "/components/z~0component~11"
    assert by_id["z~component/1"].title == "Exact registry name"
    assert by_id["z~component/1"].description == "An authored component description"
    assert by_id["a_component"].metadata == {"id": "a_component", "detail_ref": None}
    assert by_id["a_component"].title == by_id["a_component"].description == ""
    assert json.loads(path.read_text(encoding="utf-8"))["components"] == entries


def test_component_real_registry_fields_match_exact_entries():
    # covers: KM-400a-1-iii
    # covers: KM-400a-3-i
    # test type: integration
    # angle: real_artifact
    root = Path(__file__).resolve().parents[2]
    entries = json.loads((root / "docs/components.json").read_text(encoding="utf-8"))["components"]

    records = _extract(root)

    assert len(records) == len(entries) >= 46
    assert {record.native_id: record.metadata for record in records} == entries
    by_id = {record.native_id: record for record in records}
    assert by_id["finalize"].metadata["type"] == "orchestration"
    assert by_id["finalize"].metadata["exposed_interfaces"] == []
    assert by_id["ac_store"].metadata["detail_ref"] is None
    assert "agent_affinity" not in by_id["ac_store"].metadata
    assert by_id["agent_registry"].metadata["detail_ref"].endswith("agent-registry.md")
    assert (
        by_id["decision_kernel"].metadata["exposed_interfaces"]
        == entries["decision_kernel"]["exposed_interfaces"]
    )


def test_component_absent_registry_ignores_architecture_documents(tmp_path):
    # covers: KM-400a-1-iii
    # covers: KM-400a-3-i
    # test type: unit
    # angle: boundary
    document = tmp_path / "docs/architecture/components/unregistered.md"
    document.parent.mkdir(parents=True)
    document.write_text(
        "---\n" + yaml.safe_dump({"title": "Unregistered"}) + "---\nBody",
        encoding="utf-8",
    )
    assert _extract(tmp_path) == []


@pytest.mark.parametrize(
    "contents", ["{", "[]", "{}", '{"components": []}', '{"components": {"a": []}}']
)
def test_component_malformed_registry_fails_explicitly(tmp_path, contents):
    # covers: KM-400a-1-iii
    # covers: KM-400a-3-i
    # test type: unit
    # angle: failure
    path = tmp_path / "docs/components.json"
    path.parent.mkdir()
    path.write_text(contents, encoding="utf-8")
    with pytest.raises(ValueError, match="(JSON|components|component)"):
        _extract(tmp_path)


def test_component_identity_conflict_fails_without_rewriting(tmp_path):
    # covers: KM-400a-1-iii
    # covers: KM-400a-3-i
    # test type: unit
    # angle: failure
    path = _registry(tmp_path, {"registered": {"id": "other"}})
    before = path.read_bytes()
    with pytest.raises(ValueError, match="id.*registered"):
        _extract(tmp_path)
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "reference",
    [
        "../outside.md",
        "docs/../../outside.md",
        "C:/outside.md",
        "C:\\outside.md",
        "/outside.md",
        "\\\\server\\share\\outside.md",
    ],
)
def test_component_reference_cannot_escape_snapshot(tmp_path, reference):
    # covers: KM-400a-1-iii
    # covers: KM-400a-3-i
    # test type: unit
    # angle: boundary
    _registry(tmp_path, {"component": {"id": "component", "detail_ref": reference}})
    with pytest.raises(ValueError, match="detail_ref.*snapshot"):
        _extract(tmp_path)


def test_component_nonstring_presentation_fields_remain_authored(tmp_path) -> None:
    # covers: KM-400a-1-iii
    # covers: KM-400a-3-i
    # test type: unit
    # angle: boundary
    entry: dict[str, object] = {
        "name": None,
        "description": {"future": "shape"},
        "primary_code": [],
    }
    _registry(tmp_path, {"legacy": entry})
    (record,) = _extract(tmp_path)
    assert record.metadata == entry
    assert record.title == record.description == ""
