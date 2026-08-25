"""
MODULE: _package_surface_registry
GOAL: Pure helpers for the check-package-surface-declaration hook — the watched
    package-registry enumeration, extraction of the entry keys a registry
    document declares, parsing of acceptance-criterion citations out of text,
    and resolution of a cited id to its `package_surface` declaration.
BUSINESS CONTEXT: ACS-100i-6 narrowed the structured-implementation-spec
    obligation so that it fires only on an explicit `package_surface: true`
    declaration. A declaration is under the author's control and can simply be
    omitted, which would turn the narrowing into a switch-off. The signal that is
    NOT under the author's control is the registration itself: a package surface
    exists because an entry appears in a registry the build reads, that entry is
    in the diff, and it cannot be left out without failing to ship the feature.
    ACS-100i-8 reconciles the two — hence this module.
ARCHITECTURE: Deliberately I/O-free apart from reading one AC YAML file, so the
    hook module keeps all git access and all reporting. Split out of
    check_package_surface_declaration.py to stay inside the project's 400-line
    file limit; it is deployed alongside the hook by build_commit_guardian(),
    which copies every file in templates/scripts/commit_guardian/, so the hook
    cannot hit ModuleNotFoundError in a consumer layout.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

#: The package registries this check watches: the files the build reads to
#: decide what a consumer project receives. Each maps to the containers inside
#: that document whose members are ENTRIES (as opposed to an entry's own
#: fields). A dotted path of "" means the document's own top-level mapping.
#:
#: CONCESSION 3 on ACS-100i-8: this is a maintained enumeration and can go
#: stale. A new kind of registry added later is unwatched until someone adds it
#: here, so pair any new registry with an addition to this dict in the same
#: change.
WATCHED_REGISTRIES: dict[str, tuple[tuple[str, str], ...]] = {
    "config/agent_registry.json": (("agents", "list_ids"),),
    "config/skill_registry.json": (("skills", "list_ids"),),
    "config/paths.json": (("surfaces", "mapping_keys"), ("paths", "mapping_keys")),
    "templates/scripts/commit_guardian/commit_guardian.json": (
        ("hooks_manifest.hooks", "list_ids"),
        ("", "mapping_keys"),
    ),
}

#: Acceptance-criterion id as it appears in prose. Mirrors the `id` pattern in
#: config/ac_store_schema.json, loosened at the tail so a citation is still
#: recognised when it names a deeply-suffixed child. Bounded on both sides so
#: `ACS-901,` yields `ACS-901` and a hyphenated word is not split into one.
_AC_ID_RE = re.compile(
    r"(?<![A-Za-z0-9-])"
    r"[A-Z]{2,6}(?:-[A-Z]{2,6})?-\d+"
    r"(?:[a-z]\d*)?(?:-\d+[a-z\d]*)?(?:-[a-z\d]+)?(?:-[a-z\d]+)?"
    r"(?![A-Za-z0-9-])"
)

#: Keys that name a document's own metadata rather than one of its entries.
#: Excluded from `mapping_keys` extraction so a reworded comment or a schema
#: pointer is never reported as a newly registered surface.
_METADATA_KEYS = frozenset({"$schema", "_comment"})


def _resolve_container(document: Any, dotted_path: str) -> Any:  # noqa: ANN401
    """Return the value at ``dotted_path`` inside ``document``.

    Args:
        document: Parsed registry document.
        dotted_path: Dot-separated key path; "" addresses the document itself.

    Returns:
        The addressed value, or None when any segment is absent or the path
        traverses something that is not a mapping.
    """
    if dotted_path == "":
        return document
    current = document
    for segment in dotted_path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return None
        current = current[segment]
    return current


def registry_entry_keys(document: Any, containers: tuple[tuple[str, str], ...]) -> set[str]:  # noqa: ANN401
    """Return the set of entry keys a registry document declares.

    Two container shapes are recognised, matching the two shapes the watched
    registries actually use:

    * ``list_ids`` — a list of objects, each keyed by its own ``id`` field
      (``agent_registry.json``'s ``agents``, ``commit_guardian.json``'s
      ``hooks_manifest.hooks``).
    * ``mapping_keys`` — an object whose keys are the entries themselves
      (``paths.json``'s ``surfaces`` and ``paths``).

    Args:
        document: Parsed registry document, or None when it could not be read.
        containers: ``(dotted_path, kind)`` pairs to extract from.

    Returns:
        Entry keys. An unreadable or unexpectedly-shaped document yields an
        empty set, which makes a NEW entry look new and an existing one look
        removed — the conservative direction for a gate whose job is to notice
        additions.
    """
    keys: set[str] = set()
    for dotted_path, kind in containers:
        container = _resolve_container(document, dotted_path)
        if kind == "list_ids" and isinstance(container, list):
            for item in container:
                if isinstance(item, dict) and isinstance(item.get("id"), str):
                    keys.add(item["id"])
        elif kind == "mapping_keys" and isinstance(container, dict):
            keys.update(k for k in container if k not in _METADATA_KEYS)
    return keys


def parse_registry_document(raw: str | None) -> Any:  # noqa: ANN401
    """Parse registry JSON text, returning None when it is absent or malformed.

    Args:
        raw: File content, or None when the file does not exist at that revision.

    Returns:
        The parsed document, or None.
    """
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def extract_ac_citations(*texts: str) -> list[str]:
    """Return the acceptance-criterion ids cited across ``texts``, in order.

    Args:
        *texts: Commit-message body and any staged ticket bodies.

    Returns:
        De-duplicated ids in first-seen order.
    """
    seen: list[str] = []
    for text in texts:
        for match in _AC_ID_RE.findall(text or ""):
            if match not in seen:
                seen.append(match)
    return seen


def find_ac_record(store_dir: Path, ac_id: str) -> Path | None:
    """Return the on-disk path of a cited acceptance criterion, if it exists.

    Args:
        store_dir: The repository's ``docs/acceptance-criteria`` directory.
        ac_id: The cited id, which is also the record's file stem.

    Returns:
        The record path, or None when the id resolves to nothing in the store.
    """
    if not store_dir.is_dir():
        return None
    for candidate in store_dir.rglob(f"{ac_id}.yaml"):
        return candidate
    return None


def read_declaration(record_path: Path) -> bool | None:
    """Return the ``package_surface`` declaration carried by an AC record.

    Args:
        record_path: Path to the acceptance-criterion YAML file.

    Returns:
        ``True`` when the record declares a package surface, ``False`` when it
        explicitly denies one, and ``None`` when it made no declaration or could
        not be read. Denial and omission are kept distinct because they are
        different acts and ACS-100i-8-i requires the refusal to say which it saw.
    """
    try:
        import yaml  # noqa: PLC0415
    except ImportError:
        return None

    try:
        data = yaml.safe_load(record_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None

    if not isinstance(data, dict) or "package_surface" not in data:
        return None
    value = data["package_surface"]
    if value is None:
        return None
    return bool(value)
