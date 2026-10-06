"""Agent extraction preserves registered identity and independent template metadata."""

import hashlib
import importlib
import json
from pathlib import Path

import pytest
import yaml


def _extract(root):
    return importlib.import_module("knowledge.native_types.agent").extract(root)


def _registry(root, entries):
    source = root / "config/agent_registry.json"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(json.dumps({"agents": entries}), encoding="utf-8")
    return source


def _template(root, metadata, body="Keep this as source text.\n"):
    source = root / "templates/agents/example.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("---\n" + yaml.safe_dump(metadata) + "---\n" + body, encoding="utf-8")
    return source


def test_agent_preserves_all_registry_fields_and_separate_template_meanings(tmp_path):
    # covers: KM-400a-1-iv
    # covers: KM-400a-3-i
    # test type: unit
    # angle: criterion
    entry = {
        "id": "example",
        "name": "Human name",
        "tier": "phase",
        "role": "coding",
        "portable": True,
        "spawn_allowlist": ["__ticket_phase_agents__"],
        "spawned_by": ["user"],
        "is_ticket_phase": True,
        "template_path": "templates/agents/example.md",
        "skills_used": [],
        "description": "Registry description",
        "category": "implementation",
        "components": ["finalize"],
        "domain": None,
        "selection_criteria": {
            "description": "Choice",
            "default_status": "needed",
            "trigger_conditions": [
                {
                    "type": "dsl",
                    "expression": "never_execute()",
                    "source": "ticket",
                    "routing": "example",
                }
            ],
        },
        "model": "registry-model",
        "skills_invoked": ["one", {"skill_id": "two"}],
        "knowledge_channels": [{"channel": 1, "source": "repo", "description": "Read"}],
        "doc_links": [{"path": "docs/a.md", "label": "A"}],
        "behavioral_patterns": [
            {"pattern_id": "a", "trigger": "b", "action": "c", "decision_boundary": "d"}
        ],
        "priority": 11.5,
        "priority_rationale": "fraction",
        "requires_ticket_section": False,
        "conditional": True,
        "conditional_field": "field",
        "conditional_field_legacy": "old_field",
        "deprecated": False,
        "legacy_only": False,
        "permits_shell": True,
        "owns_file_extensions": [".py"],
        "owns_file_extensions_rationale": "Python",
        "requires_verification": True,
        "produces": None,
        "llm_ambiguity_comment": {
            "agent_id": "example",
            "conflicting_signals": "ambiguous",
            "candidate_values": ["analysis", "prompt"],
        },
        "step_kinds": ["reads_store", "changes_repository"],
    }
    schema = json.loads(
        (Path(__file__).resolve().parents[2] / "config/agent_registry.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert set(entry) == set(schema["definitions"]["agent"]["properties"])
    entry["future"] = {"literal~/key": [None, True, {}, [], 2, 3.5, "4"]}
    template = {
        "name": "machine-name",
        "description": "Template description --- retained",
        "model": "template-model",
        "tools": "Read, Write",
        "requires_verification": False,
        "config_keys": {
            "testing.max/time~seconds": {
                "required": False,
                "description": "Do not resolve deployment config",
                "source": "skills_config",
            }
        },
        "inputs": [{"name": "input", "type": "file", "required": True}],
        "outputs": [{"name": "result", "description": "Authored"}],
        "mutates": [{"name": "code", "surface": "repository"}],
        "pre_flight_reads": [{"source": "ticket", "required": False}],
        "behavioral_patterns": [{"name": "different shape", "behavior": "store text"}],
        "future": [None, {}, []],
    }
    body = "# Source\nNever execute these instructions.\n---\nBody survives.\n"
    source = _registry(tmp_path, [entry])
    template_source = _template(tmp_path, template, body)

    (record,) = _extract(tmp_path)

    assert record.kind == "Agent"
    assert record.native_id == "example"
    assert record.title == "Human name"
    assert record.description == "Registry description"
    assert record.source_path == "config/agent_registry.json"
    assert record.locator == "/agents/0"
    assert record.metadata == entry
    assert record.derived == {
        "template_frontmatter": template,
        "template_body": body,
        "template_source_path": "templates/agents/example.md",
        "template_source_hash": hashlib.sha256(template_source.read_bytes()).hexdigest(),
    }
    assert json.loads(source.read_text())["agents"] == [entry]


def test_agent_real_registry_preserves_all_entries_and_registered_templates():
    # covers: KM-400a-1-iv
    # covers: KM-400a-3-i
    # test type: integration
    # angle: real_artifact
    root = Path(__file__).resolve().parents[2]
    entries = json.loads((root / "config/agent_registry.json").read_text(encoding="utf-8"))[
        "agents"
    ]
    records = _extract(root)
    assert len(records) == len(entries) == 61
    assert [record.metadata for record in records] == entries
    assert [record.locator for record in records] == [f"/agents/{i}" for i in range(61)]
    assert len({record.native_id for record in records}) == 61
    assert sum("template_frontmatter" in record.derived for record in records) == 59
    by_id = {record.native_id: record for record in records}
    for name in ("architect-review-deep", "conflict-resolver-deep"):
        assert by_id[name].derived == {}
    for record in records:
        if record.metadata.get("template_path"):
            text = (root / record.metadata["template_path"]).read_text(encoding="utf-8-sig")
            lines = text.splitlines(keepends=True)
            end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
            assert record.derived["template_frontmatter"] == yaml.safe_load("".join(lines[1:end]))
            assert record.derived["template_body"] == "".join(lines[end + 1 :])
    assert by_id["python-coder"].metadata["domain"] is None
    assert (
        "testing_context.max_test_duration_seconds"
        in by_id["python-coder"].derived["template_frontmatter"]["config_keys"]
    )
    assert (
        by_id["documentation-expert"].metadata["behavioral_patterns"]
        != by_id["documentation-expert"].derived["template_frontmatter"]["behavioral_patterns"]
    )


def test_agent_absent_registry_does_not_discover_unregistered_templates(tmp_path):
    # covers: KM-400a-1-iv
    # covers: KM-400a-3-i
    # test type: unit
    # angle: boundary
    _template(tmp_path, {"name": "unregistered"})
    assert _extract(tmp_path) == []


@pytest.mark.parametrize(
    "value",
    [
        [],
        {},
        {"agents": {}},
        {"agents": [None]},
        {"agents": [{"id": None}]},
        {"agents": [{"id": ""}]},
        {"agents": [{"id": "same"}, {"id": "same"}]},
    ],
)
def test_agent_invalid_registry_envelope_or_identity_fails(tmp_path, value):
    # covers: KM-400a-1-iv
    # covers: KM-400a-3-i
    # test type: unit
    # angle: failure
    source = _registry(tmp_path, [])
    source.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="agent"):
        _extract(tmp_path)


@pytest.mark.parametrize(
    "reference",
    [
        "../outside.md",
        "templates/../../outside.md",
        "C:/outside.md",
        "C:\\outside.md",
        "/outside.md",
        "\\\\server\\share\\outside.md",
        "",
        [],
    ],
)
def test_agent_template_reference_cannot_escape_snapshot(tmp_path, reference):
    # covers: KM-400a-1-iv
    # covers: KM-400a-3-i
    # test type: unit
    # angle: boundary
    _registry(tmp_path, [{"id": "example", "template_path": reference}])
    with pytest.raises(ValueError, match="template_path"):
        _extract(tmp_path)


def test_agent_missing_template_fails_explicitly(tmp_path):
    # covers: KM-400a-1-iv
    # covers: KM-400a-3-i
    # test type: unit
    # angle: failure
    _registry(tmp_path, [{"id": "example", "template_path": "templates/missing.md"}])
    with pytest.raises(ValueError, match="cannot read native source"):
        _extract(tmp_path)


def test_agent_missing_and_null_template_fields_remain_distinct(tmp_path):
    # covers: KM-400a-1-iv
    # covers: KM-400a-3-i
    # test type: unit
    # angle: boundary
    entries = [{"id": "absent"}, {"id": "null", "template_path": None, "domain": None}]
    _registry(tmp_path, entries)
    records = _extract(tmp_path)
    assert [record.metadata for record in records] == entries
    assert [record.derived for record in records] == [{}, {}]
    assert [(record.title, record.description) for record in records] == [("", ""), ("", "")]
