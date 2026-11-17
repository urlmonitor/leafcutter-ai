"""Read Agent registry entries and retain the independently authored templates.

BUSINESS CONTEXT: KM-400a-3-i makes every authored Agent field available in Neo4j.
ARCHITECTURE: Registry identity is authoritative; runtime template fields remain
in derived.template_frontmatter to prevent conflicting names overwriting fields.
"""

from hashlib import sha256
from pathlib import Path, PureWindowsPath

from knowledge.native_types.common import NativeRecord, frontmatter, read_json, relative


def _template_data(root: Path, entry: dict) -> dict:
    """Enrich a registered agent without resolving configuration or running source."""
    reference = entry.get("template_path")
    if reference is None:
        return {}
    if not isinstance(reference, str) or not reference:
        raise ValueError("agent template_path must be a nonempty relative string or null")
    windows_path = PureWindowsPath(reference)
    if windows_path.drive or windows_path.root or Path(reference).is_absolute():
        raise ValueError("agent template_path must remain inside the snapshot")
    template = root / reference.replace("\\", "/")
    try:
        source_path = relative(root, template)
    except ValueError as error:
        raise ValueError("agent template_path must remain inside the snapshot") from error
    metadata, body = frontmatter(template)
    return {
        "template_frontmatter": metadata,
        "template_body": body,
        "template_source_path": source_path,
        "template_source_hash": sha256(template.read_bytes()).hexdigest(),
    }


def extract(root: Path) -> list[NativeRecord]:
    """Return one lossless record per registered Agent, including inline agents."""
    source = root / "config/agent_registry.json"
    if not source.exists() and not source.is_symlink():
        return []
    source_path = relative(root, source)
    value = read_json(source)
    if not isinstance(value, dict) or not isinstance(value.get("agents"), list):
        raise ValueError("agent registry must contain an agents array")
    records = []
    identities = set()
    for index, entry in enumerate(value["agents"]):
        if not isinstance(entry, dict):
            raise ValueError("agent registry entries must be objects")
        native_id = entry.get("id")
        if not isinstance(native_id, str) or not native_id.strip():
            raise ValueError("agent registry entries must have nonempty string ids")
        if native_id in identities:
            raise ValueError(f"duplicate agent registry id: {native_id}")
        identities.add(native_id)
        title = entry.get("name")
        description = entry.get("description")
        records.append(
            NativeRecord(
                kind="Agent",
                native_id=native_id,
                source_path=source_path,
                metadata=entry,
                locator=f"/agents/{index}",
                title=title if isinstance(title, str) else "",
                description=description if isinstance(description, str) else "",
                derived=_template_data(root, entry),
            )
        )
    return records
