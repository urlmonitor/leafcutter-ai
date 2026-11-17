"""Read authored Ticket frontmatter without applying current generator defaults.

BUSINESS CONTEXT: KM-400a-3-i exposes historical and current ticket fields in Neo4j.
ARCHITECTURE: Paths are identities; epic/display derivations never modify metadata.
"""

from pathlib import Path
import re

from knowledge.native_types.common import NativeRecord, frontmatter, read_text, relative


def _conventional_epic(path: Path) -> bool:
    return path.name.lower() == "master_plan.md" and any(
        part.startswith("EPIC-") for part in path.parts[:-1]
    )


def _admitted(path: Path, metadata: dict, has_frontmatter: bool) -> bool:
    """Admit explicit source roles while excluding generic reference documents."""
    if path.name.lower() == "readme.md" or not has_frontmatter:
        return False
    return bool(
        metadata.get("type") == "epic"
        or _conventional_epic(path)
        or re.match(r"(?:TICKET[-_]|\d+[_-])", path.name, re.IGNORECASE)
        or any(key in metadata for key in ("source_ac", "source_acs", "ac_traceability"))
        or (
            metadata.get("status")
            in {"todo", "in_progress", "blocked", "done", "deferred", "open", "invalid"}
            and any(key in metadata for key in ("depends_on", "components", "agents"))
        )
    )


def _derived(path: Path, metadata: dict, body: str) -> tuple[str, dict]:
    if metadata.get("type") == "epic":
        subtype, subtype_source = "epic", "frontmatter.type"
    elif _conventional_epic(path):
        subtype, subtype_source = "epic", "path_convention"
    else:
        subtype, subtype_source = "ticket", "default"
    derived = {"body": body, "subtype": subtype, "subtype_source": subtype_source}
    title = metadata.get("title")
    if isinstance(title, str):
        return title, derived
    epic_name = metadata.get("epic_name")
    if isinstance(epic_name, str) and epic_name:
        derived["title_source"] = "frontmatter.epic_name"
        return epic_name, derived
    heading = re.search(r"^#{1,6}[ \t]+(.+?)\s*$", body, re.MULTILINE)
    if heading:
        derived["title_source"] = "body.heading"
        return heading.group(1), derived
    derived["title_source"] = "source_path.stem"
    return path.stem, derived


def extract(root: Path) -> list[NativeRecord]:
    """Return native Ticket records, keeping full paths and exact authored values."""
    store = root / "tickets"
    if not store.exists() and not store.is_symlink():
        return []
    relative(root, store)
    if not store.is_dir():
        raise ValueError("native Ticket store must be a directory")
    records = []
    for path in sorted(store.rglob("*.md")):
        source_path = relative(root, path)
        if path.name.lower() == "readme.md":
            continue
        text = read_text(path)
        has_frontmatter = bool(text.splitlines() and text.splitlines()[0].strip() == "---")
        metadata, body = frontmatter(path)
        if not _admitted(Path(source_path), metadata, has_frontmatter):
            continue
        title, derived = _derived(Path(source_path), metadata, body)
        records.append(
            NativeRecord(
                kind="Ticket",
                native_id=source_path,
                source_path=source_path,
                metadata=metadata,
                title=title,
                derived=derived,
            )
        )
    return records
