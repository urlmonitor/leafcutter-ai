"""Read registered Skills and retain the independently authored template fields.

BUSINESS CONTEXT: KM-400a-3-i exposes complete Skill metadata in Neo4j.
ARCHITECTURE: The registry defines admission and identity. Template frontmatter
and prose remain separate source data; extraction never invokes their instructions.
"""

from hashlib import sha256
from pathlib import Path, PureWindowsPath

from knowledge.native_types.common import NativeRecord, frontmatter, read_json, relative


def _template_data(root: Path, entry: dict) -> dict:
    """Read a registered template only after confining its path to the snapshot."""
    reference = entry.get("template_path")
    if reference is None:
        return {}
    if not isinstance(reference, str) or not reference:
        raise ValueError("skill template_path must be a nonempty relative string or null")
    windows_path = PureWindowsPath(reference)
    if windows_path.drive or windows_path.root or Path(reference).is_absolute():
        raise ValueError("skill template_path must remain inside the snapshot")
    normalized = reference.replace("\\", "/")
    # Registry paths use the package name; snapshots already start at that root.
    if normalized.startswith("leafcutter/"):
        normalized = normalized[len("leafcutter/") :]
    template = root / normalized / "SKILL.md"
    try:
        source_path = relative(root, template)
    except ValueError as error:
        raise ValueError("skill template_path must remain inside the snapshot") from error
    metadata, body = frontmatter(template)
    return {
        "template_frontmatter": metadata,
        "template_body": body,
        "template_source_path": source_path,
        "template_source_hash": sha256(template.read_bytes()).hexdigest(),
    }


def extract(root: Path) -> list[NativeRecord]:
    """Return one lossless record per registered Skill, including legacy templates."""
    source = root / "config/skill_registry.json"
    if not source.exists() and not source.is_symlink():
        return []
    source_path = relative(root, source)
    value = read_json(source)
    if not isinstance(value, dict) or not isinstance(value.get("skills"), list):
        raise ValueError("skill registry must contain a skills array")
    records = []
    identities = set()
    for index, entry in enumerate(value["skills"]):
        if not isinstance(entry, dict):
            raise ValueError("skill registry entries must be objects")
        native_id = entry.get("id")
        if not isinstance(native_id, str) or not native_id.strip():
            raise ValueError("skill registry entries must have nonempty string ids")
        if native_id in identities:
            raise ValueError(f"duplicate skill registry id: {native_id}")
        identities.add(native_id)
        derived = _template_data(root, entry)
        title = entry.get("name")
        description = entry.get("description")
        if "description" not in entry:
            description = derived.get("template_frontmatter", {}).get("description")
        records.append(
            NativeRecord(
                kind="Skill",
                native_id=native_id,
                source_path=source_path,
                metadata=entry,
                locator=f"/skills/{index}",
                title=title if isinstance(title, str) else "",
                description=description if isinstance(description, str) else "",
                derived=derived,
            )
        )
    return records
