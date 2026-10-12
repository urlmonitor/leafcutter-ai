"""
MODULE: kernel.memory.index
GOAL: Build, render, read and check the generated filter index `docs/decisions/index.json`: one
    small entry per record (id, filters, selected option, approval, links) so a later run selects
    precedent by filter without opening every record.
BUSINESS CONTEXT: The format decision requires a generated, never hand-edited index
    (dec-ef8ddcb79d668a67). It makes records findable by component, roadmap phase, repository-wide
    flag or file type, and `decisions validate` fails when the committed index does not match the
    records, so it cannot rot.
ARCHITECTURE: Pure functions plus two small IO helpers. The index carries no timestamps, so the
    rendering of the same records is byte-identical and "up to date" is an exact text comparison.
    `superseded_by` is the union of the record's own list and the reverse of every record's
    `supersedes`, which lets a correction be found without editing the corrected file.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from kernel.memory.models import DecisionRecord

logger = logging.getLogger(__name__)

INDEX_NAME = "index.json"
INDEX_VERSION = "1.0"
GENERATED_BY = "python -m kernel decisions index"


class IndexEntry(BaseModel):
    """What the index says about one record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    file: str
    sha256: str
    title: str
    question: str
    decision_type: str
    selected_option_id: str
    selected_option_title: str
    approved_by: str
    approved_at: str
    components: list[str] = Field(default_factory=list)
    change_target: list[str] = Field(default_factory=list)
    risk_surface: list[str] = Field(default_factory=list)
    roadmap_phase: list[str] = Field(default_factory=list)
    file_globs: list[str] = Field(default_factory=list)
    repository_wide: bool = False
    supersedes: list[str] = Field(default_factory=list)
    superseded_by: list[str] = Field(default_factory=list)
    related: list[str] = Field(default_factory=list)
    corrections: int = 0


def _lf(text: str) -> str:
    """Return the text with CRLF line endings turned into LF."""
    return text.replace("\r\n", "\n")


def file_sha256(text: str) -> str:
    """Return the sha256 hex digest of a record file's text (UTF-8, line endings as LF).

    A Windows checkout with `core.autocrlf` turns LF into CRLF; the digest must not depend on it.
    """
    return hashlib.sha256(_lf(text).encode("utf-8")).hexdigest()


def _reverse_supersedes(records: Iterable[DecisionRecord]) -> dict[str, set[str]]:
    """Map each record id to the ids of the records that supersede it."""
    out: dict[str, set[str]] = {}
    for record in records:
        for old in record.supersedes:
            out.setdefault(old, set()).add(record.id)
    return out


def build_entries(items: Iterable[tuple[DecisionRecord, str]]) -> list[IndexEntry]:
    """Build the sorted entries from (record, file text) pairs; the file name is `<id>.yaml`."""
    pairs = sorted(items, key=lambda pair: pair[0].id)
    reverse = _reverse_supersedes(r for r, _ in pairs)
    entries = []
    for record, text in pairs:
        replaced_by = sorted({*record.superseded_by, *reverse.get(record.id, set())})
        entries.append(IndexEntry(
            id=record.id, file=f"{record.id}.yaml", sha256=file_sha256(text), title=record.title,
            question=record.question, decision_type=record.decision_type,
            selected_option_id=record.selected_option_id,
            selected_option_title=record.selected_option.title,
            approved_by=record.approval.approved_by, approved_at=record.approval.approved_at,
            components=record.components, change_target=record.change_target,
            risk_surface=record.risk_surface, roadmap_phase=record.roadmap_phase,
            file_globs=record.file_globs, repository_wide=record.repository_wide,
            supersedes=record.supersedes, superseded_by=replaced_by, related=record.related,
            corrections=len(record.corrections)))
    return entries


def render_index(entries: list[IndexEntry]) -> str:
    """Return the index file text (deterministic: sorted entries, 2-space JSON, LF)."""
    body: dict[str, Any] = {
        "schema_version": INDEX_VERSION, "generated_by": GENERATED_BY,
        "_comment": "Generated; never edit by hand. Regenerate with the command in generated_by.",
        "count": len(entries), "records": [e.model_dump(mode="json") for e in entries]}
    return json.dumps(body, indent=2, ensure_ascii=False) + "\n"


class IndexFormatError(ValueError):
    """The index text is not a valid decision index document."""

    def __init__(self, detail: object) -> None:
        """Build the message from the underlying problem."""
        super().__init__(f"not a valid decision index: {detail}")


def parse_index(text: str) -> list[IndexEntry]:
    """Parse index text into entries.

    Raises:
        IndexFormatError: The text is not a valid index document (a ValueError).
    """
    try:
        data = json.loads(text)
        rows = data["records"]
        return [IndexEntry.model_validate(row) for row in rows]
    except (json.JSONDecodeError, KeyError, TypeError, ValidationError) as exc:
        raise IndexFormatError(exc) from exc


def read_index(path: Path) -> list[IndexEntry] | None:
    """Read the index file; None (with a warning) when it is missing or invalid."""
    try:
        return parse_index(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        logger.warning("decision index %s unusable: %s", path, exc)
        return None


def index_problems(expected: str, actual: str | None) -> list[str]:
    """Return why the committed index text differs from the one the records produce."""
    if actual is None:
        return [f"{INDEX_NAME} is missing: run `{GENERATED_BY}`"]
    if _lf(actual) != expected:
        return [f"{INDEX_NAME} is out of date: run `{GENERATED_BY}`"]
    return []


def superseded_map(entries: Iterable[IndexEntry]) -> Mapping[str, tuple[str, ...]]:
    """Map record id to the ids that replaced it."""
    return {e.id: tuple(e.superseded_by) for e in entries if e.superseded_by}


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: The index has no generation timestamp: a clock value would make
#   every regeneration a diff and "is the index up to date" an approximate question.
#   (#KernelDecisionStore)
# ====================================================================
