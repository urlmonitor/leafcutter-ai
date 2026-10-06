"""Read approved canonical Decision sources without executing snapshot code.

BUSINESS CONTEXT: KM-400a-3-i exposes every authored decision field in Neo4j.
ARCHITECTURE: A pinned data-only schema and portable source checks protect the
projection boundary. Metadata remains unchanged; generated index freshness is
an upstream source-validation requirement, not a claim made by this reader.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import json
import math
from pathlib import Path
import re
from typing import Any, NoReturn, NotRequired, TypedDict, cast

from jsonschema import Draft202012Validator
import yaml

from .common import NativeRecord, relative

SCHEMA_PATH = Path(__file__).with_name("decision_schema.json")
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
Draft202012Validator.check_schema(SCHEMA)
_VALIDATOR = Draft202012Validator(SCHEMA)
_ID = re.compile(r"dec-[0-9a-f]{16}")
_FILTERS = ("components", "change_target", "risk_surface", "roadmap_phase", "file_globs")
_LINKS = ("supersedes", "superseded_by", "related")
_GLOBS_LINE = re.compile(r"^globs:[ \t]*(.*)$((?:\n[ \t]+-[ \t]+.*)*)", re.MULTILINE)
MAX_RECORD_BYTES = 400_000


class _ReferencedRecord(TypedDict):
    """Fields shared by schema-validated options, criteria and evidence."""

    id: str
    evidence_ids: NotRequired[list[str]]


def _fail(message: str) -> NoReturn:
    raise ValueError(f"Decision: {message}")


def _authored_values(value: Any, schema: dict, path: str = "") -> None:
    """Enforce nonblank required strings and JSON primitive integrity, without coercion."""
    if "$ref" in schema:
        schema = SCHEMA["$defs"][schema["$ref"].split("/")[-1]]
    if isinstance(value, str) and schema.get("minLength", 0) and not value.strip():
        _fail(f"{path} must not be whitespace-only")
    if isinstance(value, float) and not math.isfinite(value):
        _fail(f"{path} must be finite")
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                _fail(f"{path} mapping keys must be strings")
            item_schema = schema.get("properties", {}).get(
                key, schema.get("additionalProperties", {})
            )
            _authored_values(
                item, item_schema if isinstance(item_schema, dict) else {}, f"{path}/{key}"
            )
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _authored_values(item, schema.get("items", {}), f"{path}/{index}")


def validate_metadata(raw: Mapping[str, object]) -> None:
    """Validate recorded approval and internal consistency; never mutate or default raw."""
    if not isinstance(raw, Mapping):
        _fail("record must be a mapping")
    data = dict(raw)
    error = next(_VALIDATOR.iter_errors(data), None)
    if error is not None:
        _fail(f"{'/'.join(map(str, error.path)) or '<record>'}: {error.message}")
    _authored_values(data, SCHEMA)
    # JSON Schema above establishes these collection shapes without coercion.
    groups = {
        name: cast(list[_ReferencedRecord], data.get(name, []))
        for name in ("options", "criteria", "evidence")
    }
    ids = {}
    for name, items in groups.items():
        values = [item["id"] for item in items]
        if len(values) != len(set(values)):
            _fail(f"duplicate {name} id")
        ids[name] = set(values)
    if data["selected_option_id"] not in ids["options"]:
        _fail("selected_option_id does not name an option")
    for name in ("options", "criteria"):
        for item in groups[name]:
            if any(value not in ids["evidence"] for value in item.get("evidence_ids", [])):
                _fail(f"{name}/{item['id']} cites unknown evidence")
    for name in _LINKS:
        for target in cast(list[str], data.get(name, [])):
            if not _ID.fullmatch(target) or target == data["id"]:
                _fail(f"{name} has malformed or self-link target {target!r}")
    if data.get("repository_wide") is not True and not any(data.get(name) for name in _FILTERS):
        _fail("record has no classification filter")


def _read(root: Path, path: Path) -> str:
    relative(root, path)
    try:
        with path.open("rb") as stream:
            contents = stream.read(MAX_RECORD_BYTES + 1)
        if len(contents) > MAX_RECORD_BYTES:
            _fail(f"{path} exceeds {MAX_RECORD_BYTES} bytes")
        return contents.decode("utf-8")
    except (OSError, UnicodeError) as error:
        raise ValueError(f"Decision: cannot read UTF-8 source {path}") from error


class _UniqueKeysLoader(yaml.SafeLoader):
    """Reject duplicate authored fields instead of silently discarding their values."""


def _unique_mapping(loader: _UniqueKeysLoader, node: yaml.MappingNode, deep: bool = False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str) or key in result:
            _fail("YAML has a non-string or duplicate mapping key")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueKeysLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)


def _yaml_record(text: str) -> dict:
    try:
        documents = 0
        for event in yaml.parse(text):
            documents += isinstance(event, yaml.DocumentStartEvent)
            if (
                isinstance(event, yaml.AliasEvent)
                or getattr(event, "anchor", None)
                or getattr(event, "tag", None)
                or isinstance(event, yaml.MappingStartEvent)
                and event.flow_style
                or documents > 1
            ):
                _fail("YAML must use the single-document plain subset")
        value = yaml.load(text, Loader=_UniqueKeysLoader)
    except yaml.YAMLError as error:
        raise ValueError("Decision: invalid YAML") from error
    if not isinstance(value, dict):
        _fail("YAML record must be a mapping")
    return value


def _json(root: Path, relative_path: str) -> dict:
    try:
        value = json.loads(_read(root, root / relative_path))
    except json.JSONDecodeError as error:
        raise ValueError(f"Decision: invalid JSON vocabulary/schema {relative_path}") from error
    if not isinstance(value, dict):
        _fail(f"vocabulary/schema {relative_path} must be a mapping")
    return value


def _vocabulary(root: Path) -> dict[str, set[str]]:
    components = _json(root, "docs/components.json").get("components")
    phases = _json(root, "docs/roadmap.json").get("phases")
    schema = _json(root, "config/ac_store_schema.json")
    if not isinstance(components, dict) or not components:
        _fail("components vocabulary is absent or malformed")
    if not isinstance(phases, list) or not phases:
        _fail("roadmap vocabulary is absent or malformed")
    values = {
        "components": set(components),
        "roadmap_phase": {
            p["id"] for p in phases if isinstance(p, dict) and isinstance(p.get("id"), str)
        },
        "file_globs": set(),
    }
    for name in ("change_target", "risk_surface"):
        prop = schema.get("properties", {}).get(name, {})
        enums = [prop.get("enum", [])] + [p.get("enum", []) for p in prop.get("anyOf", [])]
        found = {item for items in enums for item in items if isinstance(item, str)}
        if not found:
            _fail(f"{name} vocabulary has no enum")
        values[name] = found
    folder = root / "templates/rules"
    relative(root, folder)
    for path in sorted(folder.glob("*.md")):
        match = _GLOBS_LINE.search(_read(root, path).split("\n---", 1)[0])
        if match:
            inline = match.group(1).split(",") if match.group(1) else []
            listed = [line.strip()[1:] for line in match.group(2).splitlines() if line.strip()]
            values["file_globs"].update(
                g.strip().strip("\"'") for g in [*inline, *listed] if g.strip()
            )
    values["file_globs"].discard("")
    return values


def _store_links(records: list[NativeRecord]) -> None:
    by_id = {record.native_id: record.metadata for record in records}
    for record in records:
        raw = record.metadata
        for name in _LINKS:
            for target in raw.get(name, []):
                if target not in by_id:
                    _fail(f"{record.native_id}/{name} target {target} does not exist")
                if name == "superseded_by" and record.native_id not in by_id[target].get(
                    "supersedes", []
                ):
                    _fail(f"{record.native_id} lacks reciprocal supersedes from {target}")
        for correction in raw.get("corrections", []):
            target = correction.get("superseded_by")
            if target is not None and target not in by_id:
                _fail(f"{record.native_id}/corrections target {target} does not exist")


def extract(root: Path) -> list[NativeRecord]:
    """Read direct canonical files; an absent store remains an honest empty list."""
    folder = root / "docs/decisions"
    relative(root, folder)
    if not folder.exists():
        return []
    if not folder.is_dir():
        _fail("docs/decisions must be a directory")
    files = sorted(folder.glob("*.yaml"))
    if not files:
        return []
    schema_path = root / "config/decision_record.schema.json"
    if schema_path.exists() and _json(root, "config/decision_record.schema.json") != SCHEMA:
        _fail("source schema is not the supported reviewed Decision schema")
    vocabulary = _vocabulary(root)
    records = []
    seen = set()
    for path in files:
        if not _ID.fullmatch(path.stem):
            _fail(f"unexpected canonical filename {path.name}")
        raw = _yaml_record(_read(root, path))
        validate_metadata(raw)
        if path.stem != raw["id"]:
            _fail(f"filename {path.name} does not match authored id {raw['id']}")
        if raw["id"] in seen:
            _fail(f"duplicate record id {raw['id']}")
        seen.add(raw["id"])
        for name in _FILTERS:
            for value in raw.get(name, []):
                if value not in vocabulary[name]:
                    _fail(f"{name} value {value!r} is not in the source vocabulary")
        records.append(
            NativeRecord(
                kind="Decision",
                native_id=raw["id"],
                source_path=relative(root, path),
                metadata=deepcopy(raw),
                title=raw["title"],
                description=raw.get("description", ""),
                derived={
                    "schema_id": SCHEMA["$id"],
                    "index_freshness": "upstream_source_validation_required",
                },
            )
        )
    _store_links(records)
    return records
