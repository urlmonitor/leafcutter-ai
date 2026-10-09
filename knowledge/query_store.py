"""Atomic local catalog persistence with retained immutable versions.

DECISION HISTORY
- 2026-10-09 09:46 [python-coder]: Remove obsolete compiler compatibility after explicit native saved-catalog re-admission. (#KM-400a-3-i/TICKET-20261009-KM-400a-3-i-native-query-maintenance)
- 2026-10-09 09:11 [python-coder]: Emit native queries while preserving versioned catalog admission identities. (#KM-400a-3-i/TICKET-20261009-KM-400a-3-i-native-query-maintenance)
- 2026-10-01 15:46 [python-coder]: A configured catalog root owns writes; serving only reads. (#KM-500/TICKET-20261001-KM-500b-3)

MODULE: knowledge.query_store
GOAL: Provide the scoped knowledge retrieval query_store responsibility.
BUSINESS CONTEXT: Make attributable research capabilities reusable and explicitly governed.
ARCHITECTURE: Dependencies point inward to neutral contracts; see docs/architecture/components/knowledge-retrieval.md.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4
from .errors import invalid, CatalogIOError
from .query_compile import COMPILER_VERSION, compile_query, digest_data
from .query_models import QueryDescriptor
from .contracts import Model


class CatalogDocument(Model):
    """Typed outer envelope prevents malformed persisted values escaping as runtime errors."""

    entries: dict[str, dict]
    active: dict[str, str]


def read_catalog(root: Path) -> dict:
    """Read and verify an atomic catalog snapshot.

    Args:
        root: Explicit trusted storage directory.

    Returns:
        Catalog entries and active operation pointers.
    """
    try:
        path = root / "catalog.json"
        data = (
            json.loads(path.read_text(encoding="utf-8"))
            if path.exists()
            else {"entries": {}, "active": {}}
        )
    except (OSError, ValueError) as exc:
        raise CatalogIOError("catalog_read") from exc
    if not isinstance(data, dict) or set(data) != {"entries", "active"}:
        invalid("catalog integrity failed")
    if not isinstance(data["entries"], dict) or not isinstance(data["active"], dict):
        invalid("catalog integrity failed")
    data = CatalogDocument.model_validate(data).model_dump()
    for key, entry in data["entries"].items():
        validate_entry(key, entry)
    for operation, key in data["active"].items():
        if (
            key not in data["entries"]
            or data["entries"][key]["descriptor"]["operation"] != operation
        ):
            invalid("catalog active pointer integrity failed")
    return data


def validate_entry(key: str, entry: dict) -> None:
    """Recompute descriptor, Cypher and verification integrity before discovery.

    Args:
        key: Expected immutable entry digest.
        entry: Untrusted persisted JSON object.
    """
    required = {"descriptor", "compiled", "verification", "verification_digest"}
    if not isinstance(entry, dict) or set(entry) != required:
        invalid("catalog entry integrity failed")
    if not isinstance(entry["verification"], dict):
        invalid("catalog verification integrity failed")
    descriptor = QueryDescriptor.model_validate(entry["descriptor"])
    recorded = entry["compiled"]
    if not isinstance(recorded, dict):
        invalid("catalog compiler integrity failed")
    if recorded.get("compiler_version") != COMPILER_VERSION:
        invalid("catalog compiler requires re-admission with the current native compiler")
    compiled = compile_query(descriptor)
    if key != compiled["digest"] or entry["compiled"] != compiled:
        invalid("catalog descriptor/query integrity failed")
    if entry.get("verification_digest") != digest_data(entry["verification"]):
        invalid("catalog verification integrity failed")
    proof = entry["verification"]
    if proof.get("digest") != key or proof.get("status") != "verified":
        invalid("catalog admission integrity failed")
    checks = proof.get("checks")
    if not isinstance(checks, dict) or checks.get("compiler_version") != COMPILER_VERSION:
        invalid("catalog verification requires fresh current-compiler admission")


def activate(root: Path, entry: dict, expected_active_digest: str | None) -> dict:
    """Atomically compare and activate a verified immutable entry under one lock.

    Args:
        root: Explicit configured write scope.
        entry: Locally verified descriptor, query and measured proof.
        expected_active_digest: Expected prior active version, or absent for first admission.

    Returns:
        The activated entry, including repeated identical delivery.
    """
    lock, temporary = root / ".activation.lock", root / (".catalog-" + uuid4().hex)
    owned = False
    try:
        root.mkdir(parents=True, exist_ok=True)
        handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(handle)
        owned = True
        data = read_catalog(root)
        operation, key = entry["descriptor"]["operation"], entry["compiled"]["digest"]
        active = data["active"].get(operation)
        if active == key:
            return data["entries"][key]
        if active != expected_active_digest:
            invalid("catalog activation conflict: active version changed")
        for previous in data["entries"].values():
            old = previous["descriptor"]
            if old["operation"] == operation and old["version"] == entry["descriptor"]["version"]:
                invalid("query version already has different content")
        validate_entry(key, entry)
        data["entries"][key] = entry
        data["active"][operation] = key
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(data, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, root / "catalog.json")
    except OSError as exc:
        raise CatalogIOError("catalog_write") from exc
    finally:
        if owned:
            _cleanup(lock, temporary)
    return entry


def _cleanup(lock: Path, temporary: Path) -> None:
    """Release only paths owned by this activation attempt.

    Args:
        lock: Acquired writer lock.
        temporary: Unique unpublished file.
    """
    try:
        temporary.unlink(missing_ok=True)
        lock.unlink()
    except OSError as exc:
        raise CatalogIOError("catalog_cleanup") from exc
