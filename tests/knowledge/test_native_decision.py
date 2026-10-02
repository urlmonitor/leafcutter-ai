"""Approved decision metadata keeps its exact authored shape and source checks."""

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib
import json
from pathlib import Path

import pytest
import yaml

from knowledge.native_properties import decode, encode


def _module():
    return importlib.import_module("knowledge.native_types.decision")


def _minimal():
    return {
        "id": "dec-0123456789abcdef",
        "repository_id": "leafcutter",
        "title": "  Keep authored spacing  ",
        "decision_type": "storage_format",
        "question": "Which storage?",
        "selected_option_id": "one",
        "task_context": {"goal": "Store decisions"},
        "rationale": {"text": "Human chose this option"},
        "options": [{"id": "one", "title": "YAML"}],
        "approval": {
            "approval_status": "approved",
            "approved_by": "human:user",
            "approved_at": "2026-10-01T14:48:31Z",
        },
        "provenance": {"created_at": "2026-10-01T14:48:31Z", "run_id": "run-1"},
        "repository_wide": True,
    }


def _complete():
    raw = _minimal()
    raw.update(
        {
            "schema_version": "1.0",
            "kind": "decision",
            "description": "Exact description",
            "components": ["finalize"],
            "change_target": ["code"],
            "risk_surface": ["data"],
            "roadmap_phase": ["phase-1"],
            "file_globs": ["**/*.py"],
            "supersedes": [],
            "superseded_by": [],
            "related": [],
            "assumptions": ["first", "second"],
            "unresolved_risks": [],
            "task_context": {
                "goal": "Store decisions",
                "component_ids": ["finalize"],
                "technologies": ["YAML"],
                "constraints": [],
            },
            "rationale": {"text": "Human chose this option", "origin": "host"},
            "options": [
                {
                    "id": "one",
                    "title": "YAML",
                    "description": "Exact",
                    "assumptions": [],
                    "evidence_ids": ["proof"],
                    "proposed_by": None,
                    "approved_by": "human:user",
                }
            ],
            "criteria": [
                {
                    "id": "criterion",
                    "question": "Readable?",
                    "priority": "required",
                    "kind": "evidence_answerable",
                    "evidence_ids": ["proof"],
                }
            ],
            "evidence": [
                {
                    "id": "proof",
                    "locator": "docs/a.md#one",
                    "category": "document",
                    "content_hash": "abcdef01",
                    "source_version": {"commit": None, "dirty": False},
                    "relevance": 0.75,
                    "verification": "verified",
                }
            ],
            "assessment": {
                "basis": "kernel_ranking",
                "confidence": None,
                "design_reason": "Choice",
                "selected_rank": 2,
                "ranking": [
                    {
                        "option_id": "external",
                        "rank": 1,
                        "required_mean": 0.8,
                        "required_passed": 2,
                        "required_total": 3,
                        "scores": {"external~/criterion": 0.5},
                    }
                ],
            },
            "final_outcome": {"status": "corrected", "note": "Observed later", "observed_at": None},
            "precedents_considered": [
                {
                    "id": "dec-fedcba9876543210",
                    "action": "set_aside",
                    "applicability": 0.25,
                    "note": "Does not apply",
                }
            ],
            "corrections": [
                {
                    "reason": "Clarify",
                    "corrected_by": "human",
                    "corrected_at": "2026-10-02T12:00:00Z",
                    "new_selected_option_id": "future-option",
                    "superseded_by": None,
                    "preserved": {
                        "selected_option_id": "one",
                        "evidence_ids": ["proof"],
                        "assumptions": [],
                    },
                }
            ],
        }
    )
    raw["approval"]["note"] = "Approved explicitly"
    raw["provenance"].update(
        {
            "created_by_capability": "decision",
            "decision_versions": {"a~/b": "v1"},
            "kernel_version": None,
            "langfuse_trace_id": None,
            "langfuse_trace_url": None,
            "model_version": None,
            "origin": "learned",
            "policy_version": None,
            "repository_revision": {"commit": "authored-ref", "dirty": False},
            "root_task_id": None,
            "template_version": None,
        }
    )
    return raw


def _put(root, path, text):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def _store(root, raw=None, name=None):
    raw = _minimal() if raw is None else raw
    _put(root, "docs/components.json", json.dumps({"components": {"finalize": {}}}))
    _put(root, "docs/roadmap.json", json.dumps({"phases": [{"id": "phase-1"}]}))
    _put(
        root,
        "config/ac_store_schema.json",
        json.dumps(
            {
                "properties": {
                    "change_target": {"enum": ["code"]},
                    "risk_surface": {"anyOf": [{"enum": ["data"]}]},
                }
            }
        ),
    )
    _put(root, "templates/rules/python.md", "---\nglobs: '**/*.py'\n---\nRules")
    return _put(
        root, f"docs/decisions/{name or raw['id']}.yaml", yaml.safe_dump(raw, sort_keys=False)
    )


def test_decision_complete_source_is_lossless_and_schema_pinned(tmp_path):
    # covers: KM-400a-1-xv
    # covers: KM-400a-3-i
    # type: integration
    # angle: criterion
    module = _module()
    raw = _complete()
    source = _store(tmp_path, raw)
    before = source.read_bytes()
    (record,) = module.extract(tmp_path)
    schema = json.loads(module.SCHEMA_PATH.read_text(encoding="utf-8"))
    assert hashlib.sha256(module.SCHEMA_PATH.read_bytes()).hexdigest() == (
        "84471651010968540a902a3ea8dd83d7c1e5bdc71d3834201393a44c8880e1c3"
    )
    assert set(raw) == set(schema["properties"])
    assert len(raw) == 31
    assert record.kind == "Decision"
    assert record.native_id == raw["id"]
    assert record.source_path == f"docs/decisions/{raw['id']}.yaml"
    assert record.title == raw["title"]
    assert record.description == raw["description"]
    assert record.locator == ""
    assert record.metadata == raw == decode(encode(record.metadata))
    assert record.derived["index_freshness"] == "upstream_source_validation_required"
    assert source.read_bytes() == before


def test_decision_minimal_retains_omission_null_and_empty(tmp_path):
    # covers: KM-400a-1-xv
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    raw = _minimal()
    raw["provenance"]["model_version"] = None
    raw["options"][0]["assumptions"] = []
    _store(tmp_path, raw)
    (record,) = _module().extract(tmp_path)
    assert record.metadata == raw == decode(encode(record.metadata))
    assert "description" not in record.metadata
    assert "kind" not in record.metadata
    assert "schema_version" not in record.metadata
    assert record.description == ""
    # The data schema permits empty maps; canonical YAML's plain subset rejects
    # flow mappings (including {}), so check this shape at the metadata boundary.
    raw["provenance"]["decision_versions"] = {}
    _module().validate_metadata(raw)
    assert raw == decode(encode(raw))


def test_decision_absent_or_empty_store_needs_no_schema_or_kernel(tmp_path):
    # covers: KM-400a-1-xv
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    module = _module()
    assert module.extract(tmp_path) == []
    (tmp_path / "docs/decisions").mkdir(parents=True)
    assert module.extract(tmp_path) == []
    # Both checks deliberately use a repository without schemas or kernel code.
    assert not (tmp_path / "kernel").exists()
    assert not (tmp_path / "schemas").exists()


BAD_FIELDS = [
    ("approval", None),
    ("approval/approval_status", "pending"),
    ("approval/approval_status", "rejected"),
    ("approval/approved_by", "host"),
    ("approval/approved_by", "kernel:user"),
    ("approval/approved_at", "yesterday"),
    ("approval/approved_at", datetime(2026, 10, 1, tzinfo=timezone.utc)),
    ("selected_option_id", "missing"),
    ("title", " \t"),
    ("repository_id", " "),
    ("task_context/goal", " "),
    ("rationale/text", " "),
    ("question", " "),
    ("options/0/title", " "),
    ("criteria/0/question", " "),
    ("evidence/0/locator", " "),
    ("evidence/0/category", " "),
    ("provenance/run_id", " "),
    ("corrections/0/reason", " "),
    ("options/0/evidence_ids", ["missing"]),
    ("criteria/0/evidence_ids", ["missing"]),
    ("related", ["dec-0123456789abcdef"]),
    ("supersedes", ["not-an-id"]),
    ("description", None),
    ("components", None),
    ("final_outcome", None),
    ("assessment/ranking/0/rank", True),
    ("assessment/ranking/0/scores/x", True),
    ("approval/extra", "forbidden"),
    ("provenance/repository_revision/dirty", "false"),
    ("unknown", "forbidden"),
]


def _assign(raw, path, value):
    parts = path.split("/")
    item = raw
    for key in parts[:-1]:
        item = item[int(key)] if isinstance(item, list) else item[key]
    item[int(parts[-1]) if isinstance(item, list) else parts[-1]] = value


@pytest.mark.parametrize(
    "path,value", BAD_FIELDS, ids=[f"invalid-field-{i}" for i in range(len(BAD_FIELDS))]
)
def test_decision_invalid_authored_fields_rejected_without_mutating(path, value):
    # covers: KM-400a-1-xv
    # covers: KM-400a-3-i
    # type: unit
    # angle: failure
    raw = _complete()
    _assign(raw, path, value)
    before = deepcopy(raw)
    with pytest.raises(ValueError, match="Decision"):
        _module().validate_metadata(raw)
    assert raw == before


@pytest.mark.parametrize("field", ["options", "criteria", "evidence"])
def test_decision_duplicate_local_ids_rejected(field):
    # covers: KM-400a-1-xv
    # covers: KM-400a-3-i
    # type: unit
    # angle: failure
    raw = _complete()
    raw[field].append(deepcopy(raw[field][0]))
    with pytest.raises(ValueError, match="duplicate"):
        _module().validate_metadata(raw)


def test_decision_missing_approval_or_classification_rejected():
    # covers: KM-400a-1-xv
    # covers: KM-400a-3-i
    # type: unit
    # angle: failure
    raw = _minimal()
    raw.pop("approval")
    with pytest.raises(ValueError, match="approval"):
        _module().validate_metadata(raw)
    raw = _minimal()
    raw["repository_wide"] = False
    with pytest.raises(ValueError, match="filter"):
        _module().validate_metadata(raw)


@pytest.mark.parametrize("name", ["unexpected", "dec-fedcba9876543210"])
def test_decision_filename_must_match_canonical_identity(tmp_path, name):
    # covers: KM-400a-1-xv
    # covers: KM-400a-3-i
    # type: unit
    # angle: failure
    _store(tmp_path, name=name)
    with pytest.raises(ValueError, match="filename"):
        _module().extract(tmp_path)


@pytest.mark.parametrize(
    "field", ["components", "change_target", "risk_surface", "roadmap_phase", "file_globs"]
)
def test_decision_unknown_filter_value_rejected(tmp_path, field):
    # covers: KM-400a-1-xv
    # covers: KM-400a-3-i
    # type: unit
    # angle: failure
    raw = _minimal()
    raw[field] = ["unknown"]
    _store(tmp_path, raw)
    with pytest.raises(ValueError, match="vocabulary"):
        _module().extract(tmp_path)


@pytest.mark.parametrize("field", ["supersedes", "superseded_by", "related", "corrections"])
def test_decision_unresolved_store_links_rejected(tmp_path, field):
    # covers: KM-400a-1-xv
    # covers: KM-400a-3-i
    # type: unit
    # angle: failure
    raw = _complete()
    if field == "corrections":
        raw[field][0]["superseded_by"] = "dec-fedcba9876543210"
    else:
        raw[field] = ["dec-fedcba9876543210"]
    _store(tmp_path, raw)
    with pytest.raises(ValueError, match="target"):
        _module().extract(tmp_path)


def test_decision_supersession_requires_reciprocal_source_and_preserves_original(tmp_path):
    # covers: KM-400a-1-xv
    # covers: KM-400a-3-i
    # type: integration
    # angle: boundary
    old, new = _complete(), _minimal()
    new["id"] = "dec-fedcba9876543210"
    old["superseded_by"] = [new["id"]]
    old["corrections"][0]["superseded_by"] = new["id"]
    _store(tmp_path, old)
    _store(tmp_path, new)
    with pytest.raises(ValueError, match="reciprocal"):
        _module().extract(tmp_path)
    new["supersedes"] = [old["id"]]
    _store(tmp_path, new)
    records = _module().extract(tmp_path)
    assert {r.native_id: r.metadata for r in records} == {old["id"]: old, new["id"]: new}


@pytest.mark.parametrize(
    "bad",
    [
        "title: &label abc\n",
        "title: *label\n",
        "title: !!str abc\n",
        "title: {nested: bad}\n",
        "---\ntitle: next\n",
        "#" + "x" * 400001,
    ],
    ids=["anchor", "alias", "tag", "flow-map", "multiple-documents", "oversize"],
)
def test_decision_plain_yaml_and_size_bound_enforced(tmp_path, bad):
    # covers: KM-400a-1-xv
    # covers: KM-400a-3-i
    # type: unit
    # angle: failure
    source = _store(tmp_path)
    source.write_text(source.read_text(encoding="utf-8") + bad, encoding="utf-8")
    with pytest.raises(ValueError, match="400000" if len(bad) > 400000 else "YAML"):
        _module().extract(tmp_path)


def test_decision_changed_source_schema_cannot_weaken_trusted_validator(tmp_path):
    # covers: KM-400a-1-xv
    # covers: KM-400a-3-i
    # type: unit
    # angle: failure
    _store(tmp_path)
    _put(tmp_path, "config/decision_record.schema.json", '{"type":"object"}')
    with pytest.raises(ValueError, match="schema"):
        _module().extract(tmp_path)
    schema = _module().SCHEMA_PATH.read_text(encoding="utf-8")
    _put(tmp_path, "config/decision_record.schema.json", schema)
    assert len(_module().extract(tmp_path)) == 1


@pytest.mark.parametrize("bad", [b"\xff", b"- list\n", b"title: first\ntitle: second\n"])
def test_decision_malformed_source_fails_explicitly(tmp_path, bad):
    # covers: KM-400a-1-xv
    # covers: KM-400a-3-i
    # type: unit
    # angle: failure
    source = _store(tmp_path)
    source.write_bytes(source.read_bytes() + bad if bad.startswith(b"title:") else bad)
    with pytest.raises(ValueError, match="(UTF-8|YAML)"):
        _module().extract(tmp_path)


def test_decision_source_resolution_cannot_escape_snapshot(tmp_path, monkeypatch):
    # covers: KM-400a-1-xv
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    source = _store(tmp_path)
    original = Path.resolve

    def redirected(path, *args, **kwargs):
        if path == source:
            return tmp_path.parent / "outside-decision.yaml"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", redirected)
    with pytest.raises(ValueError):
        _module().extract(tmp_path)
