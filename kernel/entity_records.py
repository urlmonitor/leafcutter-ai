"""MODULE: kernel.entity_records
GOAL: Typed disposable index records and shared compact text helpers.
BUSINESS CONTEXT: Cached meanings retain provenance without retaining artifact bodies.
ARCHITECTURE: Pure Pydantic data and deterministic projections; no source execution.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import Field

from kernel.contracts.base import KernelModel
from kernel.contracts.entity_context import Family

READER_VERSION = "entity-readers-4"


def bounded_meaning(text: str, limit: int) -> str:
    """Prefer a complete first sentence, otherwise cap the retained authored text."""
    clean = " ".join(text.split())
    first = re.split(r"(?<=[.!?])\s+", clean, maxsplit=1)[0]
    return first[:limit]


class IndexEntry(KernelModel):
    """A body-free owner projection with exact aliases and repository source path."""

    family: Family
    identity: str
    native_kind: str | None = None
    meaning: str = ""
    signature: str | None = None
    names: list[str]
    aliases: list[str] = Field(default_factory=list)
    source_id: str
    path: str
    locator: str
    source_hash: str
    package_source: bool = False


class SourceStamp(KernelModel):
    """An enumerated source or directory; intake only stats these known paths."""

    path: str
    source_id: str
    directory: bool
    exists: bool = True
    stamp: list[int]
    content_hash: str = ""


class NativeOwnerScope(KernelModel):
    """Whole-store validation dependencies, retained only inside the local derived cache."""

    native_kind: str
    family: Family
    paths: list[str]
    dependencies: list[str]
    status: str


class EntityIndex(KernelModel):
    """Derived index bound to the canonical physical checkout, never a caller label."""

    kind: Literal["entity_index"] = "entity_index"
    repository_root: str
    reader_version: str = READER_VERSION
    fingerprint: str
    source_configuration: dict[str, list[str]]
    entries: list[IndexEntry]
    manifest: list[SourceStamp]
    coverage: dict[str, str]
    limitations: list[str] = Field(default_factory=list)
    id_patterns: dict[str, str]
    package_stamp: list[int]
    symbol_failures: list[str] = Field(default_factory=list)
    owner_scopes: list[NativeOwnerScope] = Field(default_factory=list)

# DECISION HISTORY
# ================================================================================
# - 2026-10-03 15:05 [python-coder]: Keep pre-intent meanings deterministic, scoped and separate from task evidence. (#TICKETLESS reason=user-approved-ac-first-DK300)
# - 2026-10-03 17:00 [python-coder]: Version absent-root stamps and per-source parse failures so broad cache status cannot reveal denied source errors. (#DK-300/entity-context)
