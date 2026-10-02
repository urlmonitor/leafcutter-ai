"""Lossless native metadata to queryable Neo4j properties.

BUSINESS CONTEXT: KM-400a-3-i exposes authored leaves without JSON value blobs.
ARCHITECTURE: Simple values keep their names; nested or reserved names use JSON
Pointers. A value-free shape manifest preserves containers, nulls and types.
"""

from __future__ import annotations

from datetime import date, datetime
import json
import math

RESERVED = frozenset(
    {
        "id",
        "name",
        "title",
        "kind",
        "summary",
        "key",
        "payload",
        "canonical_id",
        "generation_key",
        "current",
        "repository_id",
        "source_path",
        "source_revision",
        "content_hash",
        "source_locator",
        "native_kind",
        "native_id",
        "native_source_path",
        "components",
        "parent_id",
        "decision_type",
    }
)
MANIFEST = "_native_shape"


def _pointer(parts: tuple[str, ...]) -> str:
    return "/" + "/".join(part.replace("~", "~0").replace("/", "~1") for part in parts)


def _property(parts: tuple[str, ...]) -> str:
    if len(parts) == 1 and parts[0] not in RESERVED and not parts[0].startswith(("/", "_native_")):
        return parts[0]
    return _pointer(parts)


def _scalar_type(value: object) -> str:
    if isinstance(value, datetime):
        return "datetime"
    if isinstance(value, date):
        return "date"
    if type(value) is bool:
        return "boolean"
    if type(value) is int:
        return "integer" if -(2**63) <= value < 2**63 else "big_integer"
    if type(value) is float and math.isfinite(value):
        return "float"
    if isinstance(value, str):
        return "string"
    raise ValueError(f"unsupported native property type: {type(value).__name__}")


def encode(metadata: dict) -> dict:
    """Expose every authored leaf, retaining structure without adding defaults."""
    if not isinstance(metadata, dict):
        raise ValueError("native metadata must be an object")
    props, shape = {}, {}

    def visit(value: object, parts: tuple[str, ...]) -> None:
        pointer = _pointer(parts) if parts else ""
        if value is None:
            shape[pointer] = {"type": "null"}
        elif isinstance(value, dict):
            keys, typed_keys = [], {}
            children = []
            for key, child in value.items():
                if isinstance(key, str):
                    token = key
                else:
                    kind = "null" if key is None else _scalar_type(key)
                    stored = (
                        key.isoformat()
                        if isinstance(key, (date, datetime))
                        else str(key)
                        if kind == "big_integer"
                        else key
                    )
                    token = "@" + kind + ":" + str(stored)
                    while token in value or token in keys:
                        token = "@" + token
                    typed_keys[token] = {"type": kind, "value": stored}
                keys.append(token)
                children.append((token, child))
            shape[pointer] = {"type": "object", "keys": keys}
            if typed_keys:
                shape[pointer]["typed_keys"] = typed_keys
            for token, child in children:
                visit(child, (*parts, token))
        elif isinstance(value, list):
            scalar = bool(value) and all(
                item is not None and not isinstance(item, (dict, list, tuple)) for item in value
            )
            kinds = [_scalar_type(item) for item in value] if scalar else []
            homogeneous = bool(kinds) and len(set(kinds)) == 1 and kinds[0] != "big_integer"
            if homogeneous:
                key = _property(parts)
                props[key] = list(value)
                shape[pointer] = {
                    "type": "scalar_list",
                    "item_type": kinds[0],
                    "property": key,
                    "length": len(value),
                }
            else:
                shape[pointer] = {"type": "array", "length": len(value)}
                for index, child in enumerate(value):
                    visit(child, (*parts, str(index)))
        else:
            kind = _scalar_type(value)
            key = _property(parts)
            props[key] = str(value) if kind == "big_integer" else value
            shape[pointer] = {"type": kind, "property": key}

    visit(metadata, ())
    props[MANIFEST] = json.dumps(shape, ensure_ascii=False, separators=(",", ":"))
    props["_native_null_paths"] = [path for path, entry in shape.items() if entry["type"] == "null"]
    props["_native_empty_paths"] = [
        path
        for path, entry in shape.items()
        if (entry["type"] == "object" and not entry["keys"])
        or (entry["type"] == "array" and not entry["length"])
    ]
    return props


def _restore(value: object, kind: str) -> object:
    if hasattr(value, "to_native"):
        value = value.to_native()
    if kind == "date" and isinstance(value, str):
        return date.fromisoformat(value)
    if kind == "datetime" and isinstance(value, str):
        return datetime.fromisoformat(value)
    if kind == "big_integer":
        return int(value)
    return value


def restore_types(properties: dict) -> dict:
    """Recover driver-supported temporal types after the canonical JSON round trip."""
    result = dict(properties)
    for entry in json.loads(result.get(MANIFEST, "{}")).values():
        key = entry.get("property")
        if key is None:
            continue
        kind = entry.get("item_type") if entry["type"] == "scalar_list" else entry["type"]
        if kind not in {"date", "datetime"}:
            continue
        value = result[key]
        result[key] = (
            [_restore(item, entry["item_type"]) for item in value]
            if entry["type"] == "scalar_list"
            else _restore(value, entry["type"])
        )
    return result


def decode(properties: dict) -> dict:
    """Reconstruct exact authored metadata for independent coverage verification."""
    shape = json.loads(properties[MANIFEST])

    def visit(parts: tuple[str, ...]) -> object:
        pointer = _pointer(parts) if parts else ""
        entry = shape[pointer]
        kind = entry["type"]
        if kind == "null":
            return None
        if kind == "object":
            keys = entry.get("typed_keys", {})
            return {
                _restore(keys[key]["value"], keys[key]["type"]) if key in keys else key: visit(
                    (*parts, key)
                )
                for key in entry["keys"]
            }
        if kind == "array":
            return [visit((*parts, str(index))) for index in range(entry["length"])]
        value = properties[entry["property"]]
        if kind == "scalar_list":
            return [_restore(item, entry["item_type"]) for item in value]
        if kind == "big_integer":
            return int(value)
        return _restore(value, kind)

    return visit(())
