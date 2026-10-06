"""Roadmap phase metadata remains complete and distinct from roadmap context."""

import importlib
import json
from pathlib import Path

import pytest


def _extract(root):
    return importlib.import_module("knowledge.native_types.roadmap_phase").extract(root)


def _phase(**changes):
    value = {
        "id": "phase_1",
        "title": "A phase",
        "exit_criteria": [],
        "tickets_advancing_outcome": [],
    }
    value.update(changes)
    return value


def _write(root, phases=None, *, path="docs/roadmap.json", **context):
    value = {
        "current_phase": "phase_1",
        "current_outcome": "Deliver it",
        "phases": phases or [_phase()],
    }
    value.update(context)
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value), encoding="utf-8")
    return value


def _config(root, path):
    target = root / "config/paths.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"surfaces": {"roadmap": {"path": path}}}), encoding="utf-8")


def test_phase_fields_context_order_and_future_fields_are_lossless(tmp_path):
    # covers: KM-400a-1-viii
    # covers: KM-400a-3-i
    # test type: unit
    # angle: criterion
    phases = [
        _phase(
            description="",
            status="active",
            components=["finalize", "ac", "finalize"],
            exit_criteria=["Second", "First"],
            tickets_advancing_outcome=["", "T2", "T2"],
            future={"nested": [None, {}, [True, 4]]},
        ),
        _phase(id="phase_2", status="active"),
    ]
    source = _write(
        tmp_path,
        phases,
        last_updated="authored update text",
        _comment="Keep as data",
        future_root={"x": []},
    )
    records = _extract(tmp_path)
    assert len(records) == 2
    assert [record.metadata for record in records] == phases
    assert [record.native_id for record in records] == ["phase_1", "phase_2"]
    assert [record.locator for record in records] == ["/phases/0", "/phases/1"]
    context = {key: value for key, value in source.items() if key != "phases"}
    for index, record in enumerate(records):
        assert record.kind == "RoadmapPhase"
        assert record.source_path == "docs/roadmap.json"
        assert record.title == "A phase"
        assert record.description == ""
        assert record.derived == {"roadmap_context": context, "phase_index": index}
    assert "description" not in records[1].metadata
    assert "components" not in records[1].metadata
    _write(tmp_path, list(reversed(phases)))
    assert [(r.native_id, r.locator) for r in _extract(tmp_path)] == [
        ("phase_2", "/phases/0"),
        ("phase_1", "/phases/1"),
    ]


def test_optional_fields_remain_absent_and_empty_lists_remain_present(tmp_path):
    # covers: KM-400a-1-viii
    # covers: KM-400a-3-i
    # test type: unit
    # angle: boundary
    source = _write(tmp_path)
    (record,) = _extract(tmp_path)
    assert record.metadata == source["phases"][0]
    assert set(record.metadata) == {"id", "title", "exit_criteria", "tickets_advancing_outcome"}
    assert record.metadata["exit_criteria"] == []
    assert record.metadata["tickets_advancing_outcome"] == []


def test_configured_source_and_nonempty_description(tmp_path):
    # covers: KM-400a-1-viii
    # covers: KM-400a-3-i
    # test type: unit
    # angle: seam
    _config(tmp_path, "plans/custom.json")
    source = _write(tmp_path, [_phase(description="Exact description")], path="plans/custom.json")
    (record,) = _extract(tmp_path)
    assert record.source_path == "plans/custom.json"
    assert record.description == "Exact description"
    assert record.metadata == source["phases"][0]


def test_absent_optional_source_returns_no_records(tmp_path):
    # covers: KM-400a-1-viii
    # covers: KM-400a-3-i
    # test type: unit
    # angle: boundary
    assert _extract(tmp_path) == []
    _config(tmp_path, "plans/absent.json")
    assert _extract(tmp_path) == []


@pytest.mark.parametrize("contents", ["{", "[]", "{}", '{"phases": []}', '{"phases": [42]}'])
def test_malformed_source_fails(tmp_path, contents):
    # covers: KM-400a-1-viii
    # covers: KM-400a-3-i
    # test type: unit
    # angle: failure
    _write(tmp_path)
    (tmp_path / "docs/roadmap.json").write_text(contents, encoding="utf-8")
    with pytest.raises(ValueError):
        _extract(tmp_path)


@pytest.mark.parametrize(
    "changes",
    [
        {"id": ""},
        {"id": 1},
        {"id": "Phase-1"},
        {"title": ""},
        {"exit_criteria": [""]},
        {"tickets_advancing_outcome": [1]},
        {"components": None},
        {"description": None},
        {"status": "unknown"},
    ],
)
def test_invalid_phase_shape_fails(tmp_path, changes):
    # covers: KM-400a-1-viii
    # covers: KM-400a-3-i
    # test type: unit
    # angle: failure
    _write(tmp_path, [_phase(**changes)])
    with pytest.raises(ValueError):
        _extract(tmp_path)


def test_duplicate_ids_fail(tmp_path):
    # covers: KM-400a-1-viii
    # covers: KM-400a-3-i
    # test type: unit
    # angle: failure
    _write(tmp_path, [_phase(), _phase(title="A second title")])
    with pytest.raises(ValueError, match="duplicate"):
        _extract(tmp_path)


@pytest.mark.parametrize(
    "context",
    [
        {"current_phase": "missing"},
        {"current_phase": None},
        {"current_outcome": ""},
        {"last_updated": 42},
        {"_comment": []},
    ],
)
def test_invalid_root_context_fails(tmp_path, context):
    # covers: KM-400a-1-viii
    # covers: KM-400a-3-i
    # test type: unit
    # angle: failure
    _write(tmp_path, **context)
    with pytest.raises(ValueError):
        _extract(tmp_path)


@pytest.mark.parametrize(
    "path",
    [
        "../outside.json",
        "C:/outside.json",
        "C:outside.json",
        "/outside.json",
        "\\\\server\\outside.json",
    ],
)
def test_configured_path_escape_fails_even_when_target_absent(tmp_path, path):
    # covers: KM-400a-1-viii
    # covers: KM-400a-3-i
    # test type: unit
    # angle: boundary
    _config(tmp_path, path)
    with pytest.raises(ValueError):
        _extract(tmp_path)


def test_real_roadmap_all_fields_and_context_match_source():
    # covers: KM-400a-1-viii
    # covers: KM-400a-3-i
    # test type: integration
    # angle: real_artifact
    root = Path(__file__).resolve().parents[2]
    source = json.loads((root / "docs/roadmap.json").read_text(encoding="utf-8"))
    records = _extract(root)
    assert len(records) == len(source["phases"]) >= 13
    assert [r.metadata for r in records] == source["phases"]
    assert [r.native_id for r in records] == [p["id"] for p in source["phases"]]
    assert sum(r.metadata.get("status") == "active" for r in records) == 2
    for index, record in enumerate(records):
        assert record.locator == f"/phases/{index}"
        assert record.derived["roadmap_context"] == {
            k: v for k, v in source.items() if k != "phases"
        }
