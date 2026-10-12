"""Source fidelity and validation boundaries for native AC metadata (KM-400a-3-i)."""

from copy import deepcopy
from datetime import date
import json
from pathlib import Path

import pytest
import yaml


SCHEMA = Path(__file__).resolve().parents[2] / "config/ac_store_schema.json"


def _minimal():
    return {
        "id": "FIN-100a",
        "title": "Preserve authored acceptance fields",
        "component": "finalize-store",
        "components": ["finalize", "knowledge_management", "finalize"],
        "status": "deprecated",
        "criteria": "Given authored data\nWhen it is projected\nThen preserve it exactly\n",
        "readiness": "reviewed",
        "priority": "high",
    }


def _complete():
    """Populate every schema key, including fields absent in the current corpus."""
    return {
        **_minimal(),
        "created_by": "tickets/original.md",
        "created": date(2026, 10, 2),
        "created_by_ticket": None,
        "superseded_by": ["FIN-200", "FIN-300"],
        "amended_by": ["tickets/amendment.md", {"reason": " Keep spacing ", "count": 0}],
        "covered_by": ["tests/test_final.py#test_one", "tests/test_final.py#test_one"],
        "implemented_by": ["src/final.py#run"],
        "origin_agent": "historical-agent",
        "documentation_triggers": ["reference-doc"],
        "documentation_rationale": "Authored rationale",
        "work_status": "in_progress",
        "level": "L1",
        "depends_on": [],
        "implements_pattern": "PTN-100",
        "pattern_bindings": {"a/b~c": {"0": [None, False, 0, "", {}, []]}},
        "pattern_slots": ["{slot}"],
        "assigned_agent": "python-coder",
        "estimated_complexity": "M",
        "delivers_to": [{"agent": "reader", "contract": {"value": False}}, "legacy"],
        "expects_from": {"agent": "author", "contract": []},
        "package_surface": False,
        "it_requirements": {
            "config_schema_fragment": {"properties": {"a/b~c": {"type": "string"}}},
            "reference_file_path": "config/paths.json",
            "n_location_rule": "all",
            "required_skills": ["python-coder"],
            "post_write_commands": [],
            "current": "source value; not graph bookkeeping",
        },
        "test_spec": [
            {
                "name": "test_first",
                "target_dir": "tests/knowledge/",
                "framework": "pytest",
                "type": "unit",
                "angle": "discrimination",
                "must_catch": [" Drop fields ", " Drop fields "],
                "surface_invoked": "knowledge.native_types.acceptance_criterion.extract",
                "description": "Preserve fields",
                "covers": ["FIN-100a"],
                "requires_db": False,
            },
            {"name": "test_second", "target_dir": "tests/knowledge/"},
        ],
        "test_required": True,
        "test_rationale": "",
        "doc_links": [
            "docs/reference/ac-schema.md",
            {
                "path": "docs/new.md",
                "status": "planned",
                "relationship": "describes",
                "relevance": "details",
                "extra": None,
            },
        ],
        "declared_files": [{"path": "src/new_final.py", "state": "to_be_created"}],
        "req_status": "approved",
        "roadmap_phase": "phase_1",
        "target_epic": "EPIC-NativeMetadata",
        "notes": "Retain full notes\nwith newlines",
        "parent": "FIN-100",
        "scope": "repository",
        "example_product": "example-product",
        "child_limit_override": 7,
        "change_target": ["code", "schema"],
        "risk_surface": "contract_boundary",
        "declares_side_effect": False,
        "product_truth": [
            {
                "flow": "flow-1",
                "node": "step-1",
                "node_kind": "step",
                "flow_kind": "journey",
                "screen": None,
                "mock_data": None,
                "entities": ["AC"],
                "source": "docs/product/example.yaml",
                "asof": "2026-10-02",
            }
        ],
    }


def _write(root, record, surface="docs/acceptance-criteria", filename="FIN-100a.yaml"):
    (root / "config").mkdir(exist_ok=True)
    (root / "docs").mkdir(exist_ok=True)
    (root / "config/paths.json").write_text(
        json.dumps({"surfaces": {"acs": {"path": surface}}}), encoding="utf-8"
    )
    (root / "docs/components.json").write_text(
        json.dumps({"components": {"finalize": {}, "knowledge_management": {}}}), encoding="utf-8"
    )
    target = root / surface / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(record, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return target


def test_all_schema_fields_survive_validated_source_extraction(tmp_path):
    # covers: KM-400a-1-i
    # covers: KM-400a-3-i
    # angle: real_artifact
    from knowledge.native_types.acceptance_criterion import extract

    source = _complete()
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert len(schema["properties"]) == 47
    assert set(source) == set(schema["properties"])
    path = _write(tmp_path, source)
    (record,) = extract(tmp_path)
    assert record.kind == "AcceptanceCriterion"
    assert record.native_id == source["id"]
    assert record.title == source["title"]
    assert record.source_path == path.relative_to(tmp_path).as_posix()
    assert record.locator == "/criteria"
    assert record.description == ""
    assert record.metadata == source
    assert record.derived == {}
    assert type(record.metadata["created"]) is date
    assert type(record.metadata["product_truth"][0]["asof"]) is str


def test_absent_defaults_and_yaml_date_strings_remain_authored(tmp_path):
    # covers: KM-400a-1-i
    # covers: KM-400a-3-i
    # angle: boundary
    from knowledge.native_types.acceptance_criterion import extract

    source = {**_minimal(), "created": "2026-10-02", "superseded_by": None}
    _write(tmp_path, source)
    (record,) = extract(tmp_path)
    assert record.metadata == source
    assert "covered_by" not in record.metadata
    assert "parent" not in record.metadata
    assert type(record.metadata["created"]) is str
    assert record.metadata["superseded_by"] is None


def test_configured_surface_is_used_and_non_records_are_excluded(tmp_path):
    # covers: KM-400a-1-i
    # covers: KM-400a-3-i
    # angle: boundary
    from knowledge.native_types.acceptance_criterion import extract

    source = _minimal()
    path = _write(tmp_path, source, surface="custom/criteria")
    (path.parent / "index.yaml").write_text("components: {}\n", encoding="utf-8")
    ignored = tmp_path / "docs/acceptance-criteria/invalid.yaml"
    ignored.parent.mkdir(parents=True)
    ignored.write_text("id: INVALID\n", encoding="utf-8")
    (record,) = extract(tmp_path)
    assert record.source_path == "custom/criteria/FIN-100a.yaml"
    assert record.metadata == source


@pytest.mark.parametrize(
    "invalid",
    [
        {"criteria": ""},
        {"unknown_field": True},
        {"components": ["unknown_component"]},
        {"depends_on": ["FIN-999"]},
    ],
)
def test_invalid_source_is_rejected_by_existing_validator(tmp_path, invalid):
    # covers: KM-400a-1-i
    # covers: KM-400a-3-i
    # angle: failure
    from knowledge.native_types.acceptance_criterion import extract
    from knowledge.projection.validation import SourceValidationError

    _write(tmp_path, {**_minimal(), **invalid})
    with pytest.raises(SourceValidationError):
        extract(tmp_path)


def test_duplicate_ids_are_not_collapsed(tmp_path):
    # covers: KM-400a-1-i
    # covers: KM-400a-3-i
    # angle: failure
    from knowledge.native_types.acceptance_criterion import extract
    from knowledge.projection.validation import SourceValidationError

    first = _write(tmp_path, _minimal())
    (first.parent / "duplicate.yaml").write_bytes(first.read_bytes())
    with pytest.raises(SourceValidationError, match="duplicate canonical ID"):
        extract(tmp_path)


def test_source_cannot_escape_supplied_snapshot(tmp_path):
    # covers: KM-400a-1-i
    # covers: KM-400a-3-i
    # angle: boundary
    from knowledge.native_types.acceptance_criterion import extract

    _write(tmp_path, _minimal())
    (tmp_path / "config/paths.json").write_text(
        json.dumps({"surfaces": {"acs": {"path": "../outside"}}}), encoding="utf-8"
    )
    with pytest.raises(ValueError):
        extract(tmp_path)


def test_metadata_does_not_alias_another_extraction(tmp_path):
    # covers: KM-400a-1-i
    # covers: KM-400a-3-i
    # angle: boundary
    from knowledge.native_types.acceptance_criterion import extract

    source = _complete()
    _write(tmp_path, source)
    (first,) = extract(tmp_path)
    expected = deepcopy(first.metadata)
    first.metadata["test_spec"][0]["name"] = "changed"
    (second,) = extract(tmp_path)
    assert second.metadata == expected
