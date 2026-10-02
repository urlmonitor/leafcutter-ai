"""MockData authored field fidelity and discovery boundaries (KM-400a-3-i)."""

import importlib
import json
from pathlib import Path

import pytest

from knowledge.native_properties import decode, encode


def _extract(root):
    return importlib.import_module("knowledge.native_types.mock_data").extract(root)


def _metadata():
    return {
        "id": "product/sample",
        "component": "product-truth-component",
        "status": "active",
        "readiness": "approved",
        "superseded_by": None,
        "version": 2,
        "shape_version": 3,
        "reusable": False,
        "example_product": "product",
        "realization": "mock",
        "tags": [],
        "invariants": ["Sample content only"],
        "entities": {
            "Ac": {
                "fields": {"a/b~c": "arbitrary JSON"},
                "records": [
                    {"a/b~c": [None, True, 42, 1.5, {"nested": [[], {}]}], "id": "sample"},
                    {"id": "second", "status": "done"},
                ],
            },
            "Empty": {"fields": {}, "records": []},
        },
        "used_by": {"tests": [], "mockups": ["product/screen"], "flows": []},
        "provenance": [
            {"action": "authored", "by": "A", "date": "arbitrary", "note": "first"},
            {"action": "approved", "by": "B", "note": "second"},
        ],
    }


def _source(root, metadata=None, name="product/sample", text=None):
    path = root / "docs/product-truth/mock-data" / (name + ".mock.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        text if text is not None else json.dumps(metadata or _metadata()), encoding="utf-8-sig"
    )
    return path


def _manifest(root, entries):
    path = root / "docs/product-truth/index.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"artifacts": entries}), encoding="utf-8")


def _entry(**changes):
    return {
        "id": "product/sample",
        "type": "mock_data",
        "path": "mock-data/product/sample.mock.json",
        **changes,
    }


def test_mock_data_all_native_fields_and_nested_sample_values_are_preserved(tmp_path):
    # covers: KM-400a-1-xii
    # covers: KM-400a-3-i
    # type: integration
    # angle: criterion
    metadata = _metadata()
    metadata["future"] = {"unknown": [False, None, {}]}
    _source(tmp_path, metadata)
    (record,) = _extract(tmp_path)
    assert record.kind == "MockData" and record.native_id == "product/sample"
    assert record.source_path == "docs/product-truth/mock-data/product/sample.mock.json"
    assert record.locator == "" and record.title == "" and record.description == ""
    assert record.metadata == metadata
    assert decode(encode(record.metadata)) == metadata
    assert record.derived == {"manifest_registered": False}


def test_mock_data_manifest_is_separate_and_unregistered_files_are_discovered(tmp_path):
    # covers: KM-400a-1-xii
    # covers: KM-400a-3-i
    # type: integration
    # angle: seam
    metadata = _metadata()
    _source(tmp_path, metadata)
    other = {**metadata, "id": "product/unregistered"}
    _source(tmp_path, other, name="product/unregistered")
    prompt = tmp_path / "docs/product-truth/mock-data/adjacent.prompt.json"
    prompt.write_text("not dataset JSON", encoding="utf-8")
    entry = _entry(
        title="Manifest title",
        summary="Manifest summary",
        component="different",
        status="deprecated",
        version=999,
    )
    _manifest(tmp_path, [{"type": "flow", "id": "product/flow"}, entry])
    records = _extract(tmp_path)
    assert len(records) == 2 and {record.kind for record in records} == {"MockData"}
    record = next(record for record in records if record.native_id == metadata["id"])
    assert record.metadata == metadata
    assert record.title == entry["title"] and record.description == entry["summary"]
    assert record.derived["manifest_entry"] == entry
    assert record.derived["manifest_locator"] == "/artifacts/1"
    assert record.derived["manifest_source_path"] == "docs/product-truth/index.json"
    assert record.derived["manifest_registered"] is True
    assert decode(encode(record.derived)) == record.derived
    assert next(record for record in records if record.native_id == other["id"]).derived == {
        "manifest_registered": False
    }


def test_mock_data_real_corpus_preserves_all_records_and_unregistered_dataset():
    # covers: KM-400a-1-xii
    # covers: KM-400a-3-i
    # type: integration
    # angle: real_artifact
    root = Path(__file__).resolve().parents[2]
    records = _extract(root)
    paths = list((root / "docs/product-truth/mock-data").rglob("*.mock.json"))
    assert len(records) == len(paths) == 2
    assert sum(record.derived["manifest_registered"] for record in records) == 1
    assert sum(len(record.metadata["entities"]) for record in records) == 8
    assert (
        sum(
            len(spec["records"])
            for record in records
            for spec in record.metadata["entities"].values()
        )
        == 48
    )
    for record in records:
        source = json.loads((root / record.source_path).read_text(encoding="utf-8-sig"))
        assert record.metadata == source
        assert decode(encode(record.metadata)) == source
        assert "shape_version" not in record.metadata
    unregistered = next(
        record for record in records if record.native_id == "guardrails/frontend-ac-declarations"
    )
    assert unregistered.derived == {"manifest_registered": False}


def test_mock_data_missing_store_and_absent_values_are_not_defaulted(tmp_path):
    # covers: KM-400a-1-xii
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    assert _extract(tmp_path) == []
    metadata = {
        "id": "Not-constrained-to/a-slug/extra",
        "component": "example",
        "status": "active",
        "readiness": "draft",
        "entities": {},
    }
    _source(tmp_path, metadata)
    (record,) = _extract(tmp_path)
    assert record.native_id == metadata["id"]
    assert record.metadata == metadata and decode(encode(record.metadata)) == metadata
    assert "realization" not in record.metadata and "superseded_by" not in record.metadata


@pytest.mark.parametrize("text", ["{", "[]", "{}", '{"id":null}', '{"id":3}', '{"id":"  "}'])
def test_mock_data_bad_source_fails_with_path(tmp_path, text):
    # covers: KM-400a-1-xii
    # covers: KM-400a-3-i
    # type: unit
    # angle: failure
    _source(tmp_path, text=text)
    with pytest.raises(ValueError, match="sample.mock.json"):
        _extract(tmp_path)


def test_mock_data_duplicate_native_ids_are_rejected(tmp_path):
    # covers: KM-400a-1-xii
    # covers: KM-400a-3-i
    # type: unit
    # angle: failure
    _source(tmp_path)
    _source(tmp_path, name="product/other")
    with pytest.raises(ValueError, match="duplicate MockData identity"):
        _extract(tmp_path)


@pytest.mark.parametrize(
    "unsafe",
    [
        "../../../../outside.mock.json",
        "/outside.mock.json",
        "C:/outside.mock.json",
        "https://example.com/data.mock.json",
    ],
)
def test_mock_data_manifest_escape_is_rejected(tmp_path, unsafe):
    # covers: KM-400a-1-xii
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    _source(tmp_path)
    _manifest(tmp_path, [_entry(path=unsafe)])
    with pytest.raises(ValueError):
        _extract(tmp_path)


def test_mock_data_manifest_duplicate_and_mismatched_source_fail(tmp_path):
    # covers: KM-400a-1-xii
    # covers: KM-400a-3-i
    # type: unit
    # angle: failure
    _source(tmp_path)
    _manifest(tmp_path, [_entry(), _entry()])
    with pytest.raises(ValueError, match="duplicate"):
        _extract(tmp_path)
    _manifest(tmp_path, [_entry(path="mock-data/product/elsewhere.mock.json")])
    with pytest.raises(ValueError, match="mismatch"):
        _extract(tmp_path)


def test_mock_data_resolved_symlink_escape_fails_before_read(tmp_path, monkeypatch):
    # covers: KM-400a-1-xii
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    source = _source(tmp_path)
    original = Path.resolve

    def resolve(path, *args, **kwargs):
        return (
            tmp_path.parent / "outside.mock.json"
            if path == source
            else original(path, *args, **kwargs)
        )

    monkeypatch.setattr(Path, "resolve", resolve)
    with pytest.raises(ValueError):
        _extract(tmp_path)


def test_mock_data_unreadable_source_is_explicit(tmp_path, monkeypatch):
    # covers: KM-400a-1-xii
    # covers: KM-400a-3-i
    # type: unit
    # angle: failure
    source = _source(tmp_path)
    original = Path.read_text

    def read(path, *args, **kwargs):
        if path == source:
            raise PermissionError("denied")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    with pytest.raises(ValueError, match="cannot read native source"):
        _extract(tmp_path)
