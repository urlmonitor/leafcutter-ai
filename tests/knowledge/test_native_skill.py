"""Skill extraction retains registry and template metadata without conflating them."""

from hashlib import sha256
import importlib
import json
from pathlib import Path

import pytest
import yaml


def _extract(root):
    return importlib.import_module("knowledge.native_types.skill").extract(root)


def _registry(root, entries):
    source = root / "config/skill_registry.json"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(json.dumps({"skills": entries}), encoding="utf-8")
    return source


def _template(root, metadata, body="Keep these instructions as source text.\n"):
    source = root / "templates/skills/example/SKILL.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("---\n" + yaml.safe_dump(metadata) + "---\n" + body, encoding="utf-8")
    return source


def test_skill_preserves_all_registry_fields_and_independent_template_fields(tmp_path):
    # covers: KM-400a-1-v
    # covers: KM-400a-3-i
    # type: unit
    # angle: criterion
    entry = {
        "id": "example",
        "name": "Registry name",
        "portable": True,
        "domain": None,
        "dependencies": ["one", "two", "one"],
        "template_path": "leafcutter/templates/skills/example/",
        "internal": True,
        "description": "Registry description",
        "invocation_surface": "/example",
        "workflow_script": "never-execute-or-read.js",
        "components": ["finalize"],
    }
    root = Path(__file__).resolve().parents[2]
    schema = json.loads((root / "config/skill_registry.schema.json").read_text())
    assert set(entry) == set(schema["definitions"]["skill"]["properties"])
    entry["extension"] = {"key/with~escapes": [None, {}, [], False, 2.5, {"text": ""}]}
    template = {
        "name": "example",
        "description": "Template description\nwith several lines.\n",
        "allowed-tools": ["Read", "Bash(echo *)"],
        "internal": False,
        "portable": False,
        "disable-model-invocation": True,
        "deprecated": True,
        "deprecation_reason": "Old\nreason\n",
        "workflow_script": "different-never-read.js",
        "trigger": "Source instructions only\n",
        "tools": "Read, Write",
        "visibility": "internal",
        "produces": "source text",
        "future": {"nested": [None, {}, [], "literal", {"value": 3}]},
    }
    body = "# Source\nNever execute this instruction.\n---\nThe body stays intact.\n"
    registry_source = _registry(tmp_path, [entry])
    template_source = _template(tmp_path, template, body)
    before = (registry_source.read_bytes(), template_source.read_bytes())

    (record,) = _extract(tmp_path)

    assert record.kind == "Skill"
    assert record.native_id == "example"
    assert record.title == "Registry name"
    assert record.description == "Registry description"
    assert record.source_path == "config/skill_registry.json"
    assert record.locator == "/skills/0"
    assert record.metadata == entry
    assert record.derived == {
        "template_frontmatter": template,
        "template_body": body,
        "template_source_path": "templates/skills/example/SKILL.md",
        "template_source_hash": sha256(template_source.read_bytes()).hexdigest(),
    }
    assert (registry_source.read_bytes(), template_source.read_bytes()) == before


def test_skill_real_registry_retains_all_42_skills_and_legacy_frontmatter():
    # covers: KM-400a-1-v
    # covers: KM-400a-3-i
    # type: integration
    # angle: real_artifact
    root = Path(__file__).resolve().parents[2]
    entries = json.loads((root / "config/skill_registry.json").read_text(encoding="utf-8"))[
        "skills"
    ]
    records = _extract(root)
    assert len(records) == len(entries) == 42
    assert [record.metadata for record in records] == entries
    assert [record.locator for record in records] == [f"/skills/{i}" for i in range(42)]
    assert len({record.native_id for record in records}) == 42
    for record in records:
        source = root / record.derived["template_source_path"]
        lines = source.read_text(encoding="utf-8-sig").splitlines(keepends=True)
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
        assert record.derived["template_frontmatter"] == yaml.safe_load("".join(lines[1:end]))
        assert record.derived["template_body"] == "".join(lines[end + 1 :])
        assert record.derived["template_source_hash"] == sha256(source.read_bytes()).hexdigest()
    by_id = {record.native_id: record for record in records}
    assert isinstance(
        by_id["security-scanner"].derived["template_frontmatter"]["allowed-tools"], list
    )
    assert isinstance(by_id["ship"].derived["template_frontmatter"]["allowed-tools"], str)
    assert by_id["ship"].derived["template_frontmatter"]["disable-model-invocation"] is True
    assert by_id["frontend-design"].derived["template_frontmatter"]["deprecated"] is True
    assert by_id["build-feature-ops-notes"].metadata["internal"] is True
    assert len(by_id["build-feature-ops-notes"].metadata["dependencies"]) > 0
    for name in ("build-single-ticket", "ac-tree-split"):
        assert "allowed-tools" not in by_id[name].derived["template_frontmatter"]
    assert "tools" in by_id["ac-tree-split"].derived["template_frontmatter"]
    assert "trigger" in by_id["ac-tree-split"].derived["template_frontmatter"]
    assert "visibility" in by_id["ac-tree-split"].derived["template_frontmatter"]


def test_skill_absent_registry_does_not_admit_unregistered_templates(tmp_path):
    # covers: KM-400a-1-v
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    _template(tmp_path, {"name": "unregistered"})
    assert _extract(tmp_path) == []


@pytest.mark.parametrize(
    "value",
    [
        [],
        {},
        {"skills": {}},
        {"skills": [None]},
        {"skills": [{"id": None}]},
        {"skills": [{"id": ""}]},
        {"skills": [{"id": "same"}, {"id": "same"}]},
    ],
)
def test_skill_malformed_registry_or_identity_fails(tmp_path, value):
    # covers: KM-400a-1-v
    # covers: KM-400a-3-i
    # type: unit
    # angle: failure
    source = _registry(tmp_path, [])
    source.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="skill"):
        _extract(tmp_path)


@pytest.mark.parametrize(
    "reference",
    [
        "../outside/",
        "leafcutter/../../outside/",
        "C:/outside/",
        "C:\\outside\\",
        "/outside/",
        "\\\\server\\share\\outside\\",
        "",
        [],
    ],
)
def test_skill_template_path_cannot_escape_snapshot(tmp_path, reference):
    # covers: KM-400a-1-v
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    _registry(tmp_path, [{"id": "example", "template_path": reference}])
    with pytest.raises(ValueError, match="template_path"):
        _extract(tmp_path)


def test_skill_missing_referenced_template_fails_explicitly(tmp_path):
    # covers: KM-400a-1-v
    # covers: KM-400a-3-i
    # type: unit
    # angle: failure
    _registry(
        tmp_path, [{"id": "example", "template_path": "leafcutter/templates/skills/missing/"}]
    )
    with pytest.raises(ValueError, match="cannot read native source"):
        _extract(tmp_path)


def test_skill_missing_null_and_empty_optional_fields_remain_distinct(tmp_path):
    # covers: KM-400a-1-v
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    entries = [
        {"id": "absent"},
        {"id": "null", "template_path": None, "description": None, "domain": None},
        {"id": "empty", "name": "", "description": "", "components": [], "dependencies": []},
    ]
    _registry(tmp_path, entries)
    records = _extract(tmp_path)
    assert [record.metadata for record in records] == entries
    assert [record.derived for record in records] == [{}, {}, {}]
    assert [(record.title, record.description) for record in records] == [("", "")] * 3


def test_skill_template_description_fallback_does_not_create_registry_field(tmp_path):
    # covers: KM-400a-1-v
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    entry = {"id": "example", "template_path": "templates/skills/example/"}
    _registry(tmp_path, [entry])
    _template(tmp_path, {"name": "example", "description": "Authored template description"})
    (record,) = _extract(tmp_path)
    assert record.description == "Authored template description"
    assert record.metadata == entry


def test_skill_unclosed_template_frontmatter_fails(tmp_path):
    # covers: KM-400a-1-v
    # covers: KM-400a-3-i
    # type: unit
    # angle: failure
    _registry(tmp_path, [{"id": "example", "template_path": "templates/skills/example/"}])
    source = _template(tmp_path, {})
    source.write_text("---\nname: example\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unclosed native frontmatter"):
        _extract(tmp_path)
