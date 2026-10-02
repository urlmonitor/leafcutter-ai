"""Flow metadata fidelity, source reconciliation, and safe identity boundaries."""

import importlib
import json
from pathlib import Path

import pytest


def _extract(root):
    return importlib.import_module("knowledge.native_types.flow").extract(root)


def _flow(native_id="leafcutter/example"):
    return {
        "id": native_id,
        "component": "finalize",
        "name": "Full name",
        "summary": "The full authored summary.",
        "kind": "architecture",
        "source": "real",
        "status": "active",
        "readiness": "approved",
        "version": 1,
        "entities": ["Ticket"],
        "steps": [{"id": "start", "label": "Start", "human": "A person starts", "order": 7}],
    }


def _source(root, value, name="example"):
    path = root / f"docs/product-truth/flows/leafcutter/{name}.flow.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _manifest(root, entries):
    path = root / "docs/product-truth/index.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"artifacts": entries, "by_flow": {"ignored": []}}), encoding="utf-8"
    )
    return path


def _entry(native_id="leafcutter/example", path="flows/leafcutter/example.flow.json"):
    return {"id": native_id, "type": "flow", "path": path, "summary": "Short summary"}


def test_flow_all_nested_fields_preserved_and_manifest_separate(tmp_path):
    # covers: KM-400a-1-x
    # covers: KM-400a-3-i
    # type: unit
    # angle: criterion
    raw = _flow()
    raw.update(
        {
            "product": "Leafcutter",
            "example_product": "demo",
            "level": "journey",
            "realization": "spec",
            "superseded_by": None,
            "shape_version": 2,
            "tags": [],
            "mock_data_ref": "leafcutter/example",
            "impl_summary": {
                "done": 1,
                "in_progress": 0,
                "not_started": 1,
                "total": 2,
                "asof": "2026-10-02",
            },
            "acceptance_scenarios": [{"for": "start", "given": "G", "when": "W", "then": "T"}],
            "provenance": [
                {"action": "authored", "by": "person", "date": "2026-10-01", "note": "note"}
            ],
            "behind": {"confirmed_against": "commit", "changed": ["a.py"], "since": "2026-10-02"},
            "confirmed": {"against": "commit", "state": {"path/a~b": "sig"}},
            "future": {"nested": [None, {}, [], True, 4, "4"]},
        }
    )
    raw["steps"][0].update(
        {
            "screen": "screen",
            "agent": "agent",
            "produces": ["Ticket"],
            "consumes": [],
            "reads": ["source"],
            "writes": [],
            "implements": ["AC-1"],
            "expands_to": "leafcutter/child",
            "impl_status": "done",
            "impl_asof": "2026-10-02",
        }
    )
    raw["steps"].append(
        {
            "id": "next",
            "label": "Next",
            "human": "Continues",
            "order": 2,
            "expands_to": ["leafcutter/child"],
        }
    )
    raw["branches"] = [
        {
            "id": "stop",
            "from": "start",
            "condition": "cancel",
            "label": "Stop",
            "human": "Cancel",
            "screen": "screen",
            "agent": "agent",
            "produces": [],
            "consumes": ["Ticket"],
            "reads": [],
            "writes": [],
            "implements": [],
            "impl_status": "not_started",
            "impl_asof": "2026-10-02",
            "outcome_kind": "exit",
        }
    ]
    source = _source(tmp_path, raw)
    entry = _entry()
    entry.update({"title": "Manifest title", "tags": ["different"], "custom": {"value": 1}})
    manifest = _manifest(tmp_path, [entry])
    before = {p: p.read_bytes() for p in (source, manifest)}
    (record,) = _extract(tmp_path)
    assert record.metadata == raw
    assert record.kind == "Flow" and record.native_id == raw["id"]
    assert record.title == raw["name"] and record.description == raw["summary"]
    assert record.source_path == "docs/product-truth/flows/leafcutter/example.flow.json"
    assert record.locator == ""
    assert record.derived["registered"] is True
    assert record.derived["manifest_entry"] == entry
    assert record.derived["manifest_source_path"] == "docs/product-truth/index.json"
    assert record.derived["manifest_locator"] == "/artifacts/0"
    assert record.metadata["steps"][0]["expands_to"] == "leafcutter/child"
    assert record.metadata["steps"][1]["expands_to"] == ["leafcutter/child"]
    assert record.metadata["steps"][0]["order"] == 7
    assert all(p.read_bytes() == data for p, data in before.items())


def test_flow_unregistered_sources_and_empty_shapes_stay_visible(tmp_path):
    # covers: KM-400a-1-x
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    raw = _flow()
    raw.update({"superseded_by": None, "branches": [], "provenance": [], "tags": []})
    _source(tmp_path, raw)
    _manifest(tmp_path, [{"type": "mockup", "id": "other", "path": "missing.html"}])
    mirror = tmp_path / "docs/product-truth/generated/flows/mirror.flow.json"
    mirror.parent.mkdir(parents=True)
    mirror.write_text("not JSON", encoding="utf-8")
    (record,) = _extract(tmp_path)
    assert record.metadata == raw
    assert record.derived["registered"] is False
    assert "manifest_entry" not in record.derived
    assert "realization" not in record.metadata and "shape_version" not in record.metadata


def test_flow_real_corpus_deep_equality_and_no_rewrites():
    # covers: KM-400a-1-x
    # covers: KM-400a-3-i
    # type: integration
    # angle: real_artifact
    root = Path(__file__).resolve().parents[2]
    paths = sorted((root / "docs/product-truth/flows").rglob("*.flow.json"))
    before = {p: p.read_bytes() for p in paths}
    source = {json.loads(data)["id"]: json.loads(data) for data in before.values()}
    records = _extract(root)
    assert len(records) == len(paths) == 25
    assert {record.native_id: record.metadata for record in records} == source
    assert all(record.derived["registered"] for record in records)
    manifest = json.loads((root / "docs/product-truth/index.json").read_text(encoding="utf-8"))
    registered = {row["id"]: row for row in manifest["artifacts"] if row["type"] == "flow"}
    assert {record.native_id: record.derived["manifest_entry"] for record in records} == registered
    assert all(record.description == source[record.native_id]["summary"] for record in records)
    assert sum(
        record.description != record.derived["manifest_entry"]["summary"] for record in records
    ) == 14
    assert all(p.read_bytes() == data for p, data in before.items())


def test_flow_missing_store_is_empty(tmp_path):
    # covers: KM-400a-1-x
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    assert _extract(tmp_path) == []


@pytest.mark.parametrize(
    "contents", ["{", "[]", "{}", '{"artifacts": {}}', '{"artifacts": [null]}']
)
def test_flow_malformed_manifest_fails(tmp_path, contents):
    # covers: KM-400a-1-x
    # covers: KM-400a-3-i
    # type: unit
    # angle: failure
    path = _manifest(tmp_path, [])
    path.write_text(contents, encoding="utf-8")
    with pytest.raises(ValueError):
        _extract(tmp_path)


@pytest.mark.parametrize(
    "path",
    [
        "",
        "../escape.flow.json",
        "flows/../escape.flow.json",
        "C:/escape.flow.json",
        "C:\\escape.flow.json",
        "/escape.flow.json",
        "\\\\server\\share\\escape.flow.json",
        "flows/example.json",
        "other/example.flow.json",
    ],
)
def test_flow_unsafe_or_noncanonical_declared_path_fails(tmp_path, path):
    # covers: KM-400a-1-x
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    _source(tmp_path, _flow())
    _manifest(tmp_path, [_entry(path=path)])
    with pytest.raises(ValueError):
        _extract(tmp_path)


@pytest.mark.parametrize(
    "case", ["missing", "mismatch", "duplicate_id", "duplicate_path", "duplicate_unregistered"]
)
def test_flow_invalid_registration_or_identity_fails(tmp_path, case):
    # covers: KM-400a-1-x
    # covers: KM-400a-3-i
    # type: unit
    # angle: failure
    entry = _entry()
    entries = [entry]
    if case != "missing":
        _source(tmp_path, _flow("leafcutter/other" if case == "mismatch" else "leafcutter/example"))
    if case == "duplicate_id":
        _source(tmp_path, _flow(), "second")
        entries.append(_entry(path="flows/leafcutter/second.flow.json"))
    if case == "duplicate_path":
        entries.append(_entry("leafcutter/other"))
    if case == "duplicate_unregistered":
        _source(tmp_path, _flow(), "second")
    _manifest(tmp_path, entries)
    expected = {
        "missing": "missing declared",
        "mismatch": "identity mismatch",
        "duplicate_id": "duplicate Flow registration",
        "duplicate_path": "duplicate Flow registration",
        "duplicate_unregistered": "duplicate Flow source",
    }[case]
    with pytest.raises(ValueError, match=expected):
        _extract(tmp_path)


@pytest.mark.parametrize("contents", ["{", "[]", "{}", '{"id": "invalid"}'])
def test_flow_invalid_source_fails(tmp_path, contents):
    # covers: KM-400a-1-x
    # covers: KM-400a-3-i
    # type: unit
    # angle: failure
    source = _source(tmp_path, _flow())
    source.write_text(contents, encoding="utf-8")
    with pytest.raises(ValueError):
        _extract(tmp_path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("summary", None),
        ("version", True),
        ("entities", [1]),
        ("steps", []),
        ("steps", [{"id": "start", "label": "Start", "human": "Start", "order": True}]),
        ("branches", None),
        ("branches", [{"id": "branch"}]),
    ],
)
def test_flow_required_source_shapes_fail_explicitly(tmp_path, field, value):
    # covers: KM-400a-1-x
    # covers: KM-400a-3-i
    # type: unit
    # angle: failure
    raw = _flow()
    raw[field] = value
    _source(tmp_path, raw)
    with pytest.raises(ValueError, match="Flow"):
        _extract(tmp_path)


def test_flow_no_manifest_and_normalized_registration_spelling(tmp_path):
    # covers: KM-400a-1-x
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    raw = _flow()
    _source(tmp_path, raw)
    (record,) = _extract(tmp_path)
    assert record.metadata == raw and record.derived["registered"] is False
    entry = _entry(path="flows\\leafcutter\\example.flow.json")
    _manifest(tmp_path, [entry])
    (record,) = _extract(tmp_path)
    assert record.metadata == raw and record.derived["registered"] is True
    assert record.derived["manifest_entry"]["path"] == entry["path"]
