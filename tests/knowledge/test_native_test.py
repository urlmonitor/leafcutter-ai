"""Test-reference metadata preserves historical file evidence without discovery."""

from copy import deepcopy
from datetime import date
import importlib
from pathlib import Path

import pytest

from knowledge.contracts import Entity, SourceReference
from knowledge.native_properties import decode, encode


def _reader():
    return importlib.import_module("knowledge.native_types.test")


def _entity(**changes):
    values = {
        "canonical_id": "test-reference:stable-id",
        "kind": "Test",
        "title": "Historical test file",
        "summary": "An original reference summary",
        "source": SourceReference(
            repository_id="leafcutter",
            source_sha="b" * 40,
            path="tests/feature/test_case.py",
            locator="source-level locator",
            content_hash="original-content-digest",
        ),
        "properties": {
            "surface": "files",
            "missing": False,
            "canonical": False,
            "registry_identity": False,
        },
    }
    values.update(changes)
    return Entity(**values)


def test_test_reference_exposes_complete_contract_and_future_fields(tmp_path):
    # covers: KM-400a-1-xvii
    # covers: KM-400a-3-i
    # type: unit
    # angle: criterion
    entity = _entity()
    entity.properties.update(
        {
            "source": {"path": "separate authored path"},
            "title": "separate authored title",
            "future": {"a~/b": [None, False, "", [], {}, {"values": [2, 1, 2]}]},
            "observed_on": date(2025, 10, 2),
        }
    )
    expected = deepcopy(entity.model_dump(mode="python"))

    record = _reader().from_entity(tmp_path, entity)

    assert record.kind == "Test"
    assert record.native_id == "test-reference:stable-id" != entity.source.path
    assert record.source_path == "tests/feature/test_case.py"
    assert record.title == "Historical test file"
    assert record.description == "An original reference summary"
    assert record.locator == "source-level locator"
    assert record.metadata == expected
    assert set(record.metadata) == {
        "canonical_id",
        "kind",
        "title",
        "summary",
        "source",
        "properties",
    }
    assert set(record.metadata["source"]) == {
        "repository_id",
        "source_sha",
        "path",
        "locator",
        "content_hash",
    }
    assert record.derived == {}
    assert decode(encode(record.metadata)) == expected
    assert entity.model_dump(mode="python") == expected


@pytest.mark.parametrize(
    "missing,content_hash,present_now",
    [
        (True, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", True),
        (False, "historical-present-hash", False),
        (True, "", True),
        (False, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", False),
    ],
)
def test_test_reference_never_observes_current_filesystem(
    tmp_path, monkeypatch, missing, content_hash, present_now
):
    # covers: KM-400a-1-xvii
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    entity = _entity()
    entity.properties["missing"] = missing
    entity.source.content_hash = content_hash
    if present_now:
        current = tmp_path / entity.source.path
        current.parent.mkdir(parents=True)
        current.write_text("def test_later(): pass", encoding="utf-8")
    reader = _reader()

    def forbidden(*args, **kwargs):
        raise AssertionError("Test enrichment must not observe current files")

    with monkeypatch.context() as patch:
        for method in (
            "exists",
            "is_file",
            "is_dir",
            "read_bytes",
            "read_text",
            "open",
            "stat",
            "resolve",
            "rglob",
            "glob",
            "iterdir",
        ):
            patch.setattr(Path, method, forbidden)
        record = reader.from_entity(tmp_path, entity)

    assert record.metadata["properties"]["missing"] is missing
    assert record.metadata["source"]["content_hash"] == content_hash
    assert record.metadata["source"]["source_sha"] == "b" * 40
    assert record.derived == {}


@pytest.mark.parametrize("properties", [{}, {"missing": False}, {"missing": None}])
def test_test_reference_absent_empty_null_and_false_remain_distinct(tmp_path, properties):
    # covers: KM-400a-1-xvii
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    entity = _entity(title="", summary="", properties=properties)
    entity.source.locator = ""
    entity.source.content_hash = ""
    expected = entity.model_dump(mode="python")
    record = _reader().from_entity(tmp_path, entity)
    assert record.title == record.description == record.locator == ""
    assert record.metadata == expected
    assert record.metadata["properties"] == properties
    assert decode(encode(record.metadata)) == expected


def test_test_reference_removes_only_exact_adapter_keys(tmp_path):
    # covers: KM-400a-1-xvii
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    entity = _entity(
        properties={
            "_native_projection": {"old": "projection"},
            "_native_identity": "old-id",
            "_native_source_path": "old-source",
            "_native_future": {"field": True},
            "_native_projection_extra": False,
            "nested": {"_native_projection": "original nested value"},
            "outcome": "an original property, never manufactured",
        }
    )
    original = deepcopy(entity.model_dump(mode="python"))
    record = _reader().from_entity(tmp_path, entity)
    assert record.metadata["properties"] == {
        "_native_future": {"field": True},
        "_native_projection_extra": False,
        "nested": {"_native_projection": "original nested value"},
        "outcome": "an original property, never manufactured",
    }
    assert entity.model_dump(mode="python") == original


def test_test_reference_copies_nested_data_in_both_directions(tmp_path):
    # covers: KM-400a-1-xvii
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    entity = _entity(properties={"nested": [{"items": [1, 2]}]})
    record = _reader().from_entity(tmp_path, entity)
    record.metadata["properties"]["nested"][0]["items"].append(3)
    record.metadata["source"]["locator"] = "record-only edit"
    assert entity.properties["nested"][0]["items"] == [1, 2]
    assert entity.source.locator == "source-level locator"
    entity.properties["nested"][0]["items"].append(4)
    entity.source.path = "unit_tests/renamed.py"
    assert record.metadata["properties"]["nested"][0]["items"] == [1, 2, 3]
    assert record.metadata["source"]["path"] == "tests/feature/test_case.py"


@pytest.mark.parametrize("kind", ["SourceFile", "AcceptanceCriterion", "Component", "test"])
def test_test_reference_rejects_other_kinds_without_path_reclassification(tmp_path, kind):
    # covers: KM-400a-1-xvii
    # covers: KM-400a-3-i
    # type: unit
    # angle: failure
    with pytest.raises(ValueError, match="Test"):
        _reader().from_entity(tmp_path, _entity(kind=kind))


@pytest.mark.parametrize(
    "path",
    ["../outside.py", "tests/../../outside.py", "/outside.py", "C:/outside.py", "tests\\case.py"],
)
def test_test_reference_revalidates_source_paths_without_repair(tmp_path, path):
    # covers: KM-400a-1-xvii
    # covers: KM-400a-3-i
    # type: unit
    # angle: failure
    entity = _entity()
    entity.source.path = path
    with pytest.raises(ValueError, match="repository-relative"):
        _reader().from_entity(tmp_path, entity)


def test_test_reference_rejects_non_entity_and_invalid_pinned_source(tmp_path):
    # covers: KM-400a-1-xvii
    # covers: KM-400a-3-i
    # type: unit
    # angle: failure
    with pytest.raises(TypeError, match="Entity"):
        _reader().from_entity(tmp_path, _entity().model_dump(mode="python"))
    entity = _entity()
    entity.source.source_sha = "latest"
    with pytest.raises(ValueError):
        _reader().from_entity(tmp_path, entity)


@pytest.mark.parametrize(
    "path", ["tests/support.json", "unit_tests/shared", "historic/custom/location"]
)
def test_test_reference_preserves_existing_classification_without_invention(tmp_path, path):
    # covers: KM-400a-1-xvii
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    entity = _entity()
    entity.source.path = path
    original = entity.model_dump(mode="python")
    record = _reader().from_entity(tmp_path, entity)
    assert record.kind == "Test"
    assert record.native_id == entity.canonical_id
    assert record.source_path == path
    assert record.metadata == original
    assert record.derived == {}
