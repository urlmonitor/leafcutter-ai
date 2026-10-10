"""
MODULE: kernel.contracts.base
GOAL: Base Pydantic models, id helpers and correlation/trace value objects shared by every
    kernel contract.
BUSINESS CONTEXT: Every persisted entity needs a stable id, a schema version and UTC timestamps
    (Rev 3 section 7.1). One base class keeps those rules identical across all contracts.
ARCHITECTURE: Leaf module of kernel.contracts (imports only pydantic and stdlib). KernelModel is
    frozen and rejects unknown fields; state changes use model_copy(update=...).
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal, NoReturn

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

ID_PATTERN = r"^[a-z]+-[0-9a-f]{16}$"
STABLE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
ID_PREFIXES = ("run", "task", "req", "work", "inv", "ev", "find", "dec", "opt", "crit",
               "int", "gap", "evt", "ra")

KernelId = Annotated[str, StringConstraints(pattern=ID_PATTERN)]
StableId = Annotated[str, StringConstraints(pattern=STABLE_ID_PATTERN)]
_ID_RE = re.compile(ID_PATTERN)


class ContractViolation(ValueError):
    """A contract invariant was violated (a ValueError so Pydantic reports it per field)."""


def fail(message: str) -> NoReturn:
    """Raise ContractViolation with the given message (single raise site for TRY003).

    Args:
        message: Human-readable description of the violated invariant.
    """
    raise ContractViolation(message)


def utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


def new_id(prefix: str) -> str:
    """Return a kernel-assigned id `<prefix>-<16 hex>` using uuid4.

    Args:
        prefix: One of ID_PREFIXES.

    Returns:
        str: The new id.
    """
    if prefix not in ID_PREFIXES:
        fail(f"unknown id prefix {prefix!r}")
    return f"{prefix}-{uuid.uuid4().hex[:16]}"


def sha256_hex(text: str) -> str:
    """Return the sha256 hex digest of a UTF-8 string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_json(data: Any) -> str:
    """Serialize JSON-compatible data deterministically (sorted keys, compact)."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_hash(text: str) -> str:
    """Return the content hash used for evidence excerpts (sha256 hex)."""
    return sha256_hex(text)


def evidence_id(locator: str, excerpt_hash: str) -> str:
    """Return the content-addressed evidence id: `ev-` + sha256(locator, newline, hash)[:16]."""
    return "ev-" + sha256_hex(locator + "\n" + excerpt_hash)[:16]


def is_kernel_id(value: str, prefix: str | None = None) -> bool:
    """Return True if value is a well-formed kernel id, optionally of the given prefix."""
    if not _ID_RE.match(value):
        return False
    return prefix is None or value.startswith(prefix + "-")


class KernelModel(BaseModel):
    """Frozen, extra-forbidding base for every kernel contract."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True,
                              use_attribute_docstrings=True)

    schema_version: Literal["1.0"] = "1.0"
    (
        "Version of this contract's shape, so a reader can reject a payload written for another "
        "shape."
    )


class PersistedModel(KernelModel):
    """Base for persisted entities: id, UTC timestamps and a kernel-assigned sequence."""

    id: KernelId
    (
        "Identifier other records cite this one by; the kernel assigns it, or derives it from "
        "the content for evidence and findings."
    )
    created_at: datetime = Field(default_factory=utc_now)
    """When the record was first created (UTC), so history can be ordered and audited."""
    updated_at: datetime = Field(default_factory=utc_now)
    (
        "When the record last changed (UTC), so a reader can tell a stale copy from the current "
        "one."
    )
    created_seq: int = Field(default=0, ge=0)
    """Kernel-wide creation counter that orders records exactly where clock times tie."""

    @field_validator("created_at", "updated_at")
    @classmethod
    def _require_aware_utc(cls, value: datetime) -> datetime:
        """Reject naive datetimes and normalise to UTC."""
        if value.tzinfo is None or value.utcoffset() is None:
            fail("datetime must be timezone-aware (UTC)")
        return value.astimezone(UTC)


class CorrelationIds(KernelModel):
    """Correlation ids attached to every observation; None fields are omitted in metadata."""

    run_id: str | None = None
    root_task_id: str | None = None
    task_id: str | None = None
    work_item_id: str | None = None
    request_id: str | None = None
    invocation_id: str | None = None
    decision_id: str | None = None
    capability_id: str | None = None
    interaction_id: str | None = None
    parent_work_item_id: str | None = None
    causation_seq: int | None = None

    def as_metadata(self) -> dict[str, str | int]:
        """Return only the non-null ids as a flat metadata dict."""
        data = self.model_dump(exclude={"schema_version"})
        return {k: v for k, v in data.items() if v is not None}

    def with_updates(self, **updates: str | int | None) -> CorrelationIds:
        """Return a copy with the given ids replaced."""
        return self.model_copy(update=updates)


class TraceContext(KernelModel):
    """Trace handle carried on invocations so capabilities can parent their observations."""

    trace_id: str | None = None
    parent_observation_id: str | None = None
    correlation: CorrelationIds = Field(default_factory=CorrelationIds)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-09 [python-coder]: KernelModel sets use_attribute_docstrings so a docstring under a
#   field becomes its schema description, which host packets send to the LLM and Atlas shows;
#   every contract field now says why it exists.
#   (#TICKET-20261009-KernelContractFieldDescriptions)
# - 2026-09-30 22:00 [python-coder]: Correlation/trace value objects live here (not in
#   observability) so contracts never import the observability package. (#KernelBootstrapV0/P1)
# ====================================================================
