"""Pinned file references retain their complete native field shape without I/O."""

from copy import deepcopy
import importlib
from pathlib import Path

import pytest

from knowledge.contracts import Entity, SourceReference
from knowledge.native_properties import decode, encode


def _read(root, entity):
    return importlib.import_module("knowledge.native_types.source_file").from_entity(root, entity)


def _entity(**changes):
    value = {
        "canonical_id": "reference/custom.py",
        "kind": "SourceFile",
        "title": "Authored reference caption",
        "summary": "An existing reference summary",
        "source": SourceReference(
            repository_id="leafcutter",
            source_sha="a" * 40,
            path="src/custom.py",
            locator="",
            content_hash="pinned-original-hash",
        ),
        "properties": {
            "surface": "files",
            "missing": False,
            "canonical": False,
            "registry_identity": False,
        },
    }
    value.update(changes)
    return Entity.model_validate(value)


def test_source_file_complete_contract_and_nested_future_fields(tmp_path):
    # covers: KM-400a-1-xvi
    # covers: KM-400a-3-i
    # test type: unit
    # angle: criterion
    entity = _entity()
    entity.source.locator = "retained locator"
    entity.properties.update(
        {
            "title": "Different property title",
            "source": {"path": None},
            "future": {"a~/b": [None, False, "", [], {}, {"ordered": [2, 1, 2]}]},
        }
    )
    expected = deepcopy(entity.model_dump(mode="python"))

    record = _read(tmp_path, entity)

    assert record.kind == "SourceFile"
    assert record.native_id == entity.canonical_id != entity.source.path
    assert record.source_path == entity.source.path
    assert record.locator == "retained locator"
    assert record.title == entity.title
    assert record.description == entity.summary
    assert record.derived == {}
    assert record.metadata == expected
    assert decode(encode(record.metadata)) == expected
    assert entity.model_dump(mode="python") == expected


@pytest.mark.parametrize(
    "missing,hash_value",
    [
        (True, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
        (False, "older-hash"),
        (True, ""),
    ],
)
def test_source_file_never_refreshes_pinned_existence_or_hash(
    tmp_path, monkeypatch, missing, hash_value
):
    # covers: KM-400a-1-xvi
    # covers: KM-400a-3-i
    # test type: unit
    # angle: boundary
    entity = _entity()
    entity.properties["missing"] = missing
    entity.source.content_hash = hash_value
    if missing:
        (tmp_path / "src").mkdir()
        (tmp_path / entity.source.path).write_text("file appeared later", encoding="utf-8")
    reader = importlib.import_module("knowledge.native_types.source_file")

    def forbidden(*args, **kwargs):
        raise AssertionError("SourceFile enrichment must not inspect the filesystem")

    with monkeypatch.context() as patch:
        for method in (
            "exists",
            "is_file",
            "is_dir",
            "read_bytes",
            "read_text",
            "stat",
            "resolve",
            "rglob",
            "glob",
            "iterdir",
        ):
            patch.setattr(Path, method, forbidden)
        record = reader.from_entity(tmp_path, entity)

    assert record.metadata["properties"]["missing"] is missing
    assert record.metadata["source"]["content_hash"] == hash_value
    assert record.native_id == entity.canonical_id


def test_source_file_absence_empty_and_false_are_distinct(tmp_path):
    # covers: KM-400a-1-xvi
    # covers: KM-400a-3-i
    # test type: unit
    # angle: boundary
    entity = _entity(
        title="",
        summary="",
        properties={"false": False, "null": None, "list": [], "object": {}, "text": ""},
    )
    entity.source.content_hash = ""
    record = _read(tmp_path, entity)
    assert record.metadata == entity.model_dump(mode="python")
    assert "missing" not in record.metadata["properties"]
    assert "canonical" not in record.metadata["properties"]
    assert record.title == record.description == record.locator == ""
    assert decode(encode(record.metadata)) == entity.model_dump(mode="python")


def test_source_file_repeat_enrichment_removes_only_exact_internal_keys(tmp_path):
    # covers: KM-400a-1-xvi
    # covers: KM-400a-3-i
    # test type: unit
    # angle: boundary
    entity = _entity(
        properties={
            "_native_projection": {"old": "large recursive payload"},
            "_native_identity": "old-id",
            "_native_source_path": "old-path",
            "_native_future": {"retained": True},
            "_native_projection_extra": False,
            "nested": {"_native_projection": "authored nested value"},
        }
    )
    original = deepcopy(entity.model_dump(mode="python"))
    record = _read(tmp_path, entity)
    assert record.metadata["properties"] == {
        "_native_future": {"retained": True},
        "_native_projection_extra": False,
        "nested": {"_native_projection": "authored nested value"},
    }
    assert entity.model_dump(mode="python") == original


def test_source_file_nested_values_are_independent_copies(tmp_path):
    # covers: KM-400a-1-xvi
    # covers: KM-400a-3-i
    # test type: unit
    # angle: boundary
    entity = _entity(properties={"nested": [{"values": [1, 2]}]})
    record = _read(tmp_path, entity)
    record.metadata["properties"]["nested"][0]["values"].append(3)
    assert entity.properties["nested"][0]["values"] == [1, 2]
    entity.properties["nested"][0]["values"].append(4)
    assert record.metadata["properties"]["nested"][0]["values"] == [1, 2, 3]


@pytest.mark.parametrize("kind", ["Test", "Component", "Document", "AcceptanceCriterion"])
def test_source_file_rejects_other_entity_kinds(tmp_path, kind):
    # covers: KM-400a-1-xvi
    # covers: KM-400a-3-i
    # test type: unit
    # angle: failure
    with pytest.raises(ValueError, match="SourceFile"):
        _read(tmp_path, _entity(kind=kind))


@pytest.mark.parametrize(
    "path",
    ["../outside.py", "src/../../outside.py", "/outside.py", "C:/outside.py", "src\\file.py"],
)
def test_source_file_revalidates_invalid_source_path(tmp_path, path):
    # covers: KM-400a-1-xvi
    # covers: KM-400a-3-i
    # test type: unit
    # angle: failure
    entity = _entity()
    entity.source.path = path
    with pytest.raises(ValueError, match="repository-relative"):
        _read(tmp_path, entity)


def test_source_file_rejects_non_entity_and_invalid_reference(tmp_path):
    # covers: KM-400a-1-xvi
    # covers: KM-400a-3-i
    # test type: unit
    # angle: failure
    with pytest.raises(TypeError, match="Entity"):
        _read(tmp_path, _entity().model_dump(mode="python"))
    entity = _entity()
    entity.source.source_sha = "uncommitted"
    with pytest.raises(ValueError):
        _read(tmp_path, entity)
