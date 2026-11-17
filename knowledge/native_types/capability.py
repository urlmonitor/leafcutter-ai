"""Read the authored capability registry without invoking runtime descriptors.

BUSINESS CONTEXT: KM-400a-3-i makes every authored capability field queryable.
ARCHITECTURE: Trusted schema checks validate known fields without applying runtime
defaults or discarding extension data. Registry context remains separate.
"""

from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path

from jsonschema import Draft7Validator

from knowledge.native_types.common import NativeRecord, read_json, relative


def _allow_extensions(value):
    """Relax only unknown keys; retain all known-field and admission constraints."""
    if isinstance(value, dict):
        return {
            key: True if key == "additionalProperties" else _allow_extensions(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_allow_extensions(item) for item in value]
    return value


@lru_cache(maxsize=1)
def _validator() -> Draft7Validator:
    """Use the reader's trusted schema, never a schema or code from the snapshot."""
    source = Path(__file__).resolve().parents[2] / "config/capability_registry.schema.json"
    schema = json.loads(source.read_text(encoding="utf-8-sig"))
    return Draft7Validator(_allow_extensions(schema))


def extract(root: Path) -> list[NativeRecord]:
    """Return exact raw capability entries, including disabled and fixed records."""
    source = root / "config/capability_registry.json"
    if not source.exists() and not source.is_symlink():
        return []
    source_path = relative(root, source)
    value = read_json(source)
    error = next(_validator().iter_errors(value), None)
    if error is not None:
        location = "/" + "/".join(str(part) for part in error.absolute_path)
        raise ValueError(f"invalid capability registry at {location}: {error.message}")
    registry_context = {key: item for key, item in value.items() if key != "capabilities"}
    records = []
    identities = set()
    for index, entry in enumerate(value["capabilities"]):
        native_id = entry["id"]
        if native_id in identities:
            raise ValueError(f"duplicate capability registry id: {native_id}")
        identities.add(native_id)
        records.append(
            NativeRecord(
                kind="Capability",
                native_id=native_id,
                source_path=source_path,
                metadata=deepcopy(entry),
                locator=f"/capabilities/{index}",
                title=entry["name"],
                description=entry["description"],
                derived={"registry_context": deepcopy(registry_context)},
            )
        )
    return records
