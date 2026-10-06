"""MODULE: kernel.contracts.entity_context
GOAL: Versioned meaning-only interpretation snapshots.
BUSINESS CONTEXT: Names explain references without becoming evidence or authority.
ARCHITECTURE: Frozen contracts preserve all admitted spans separately from wire projection.
"""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, Field

from kernel.contracts.base import KernelModel
from kernel.contracts.context import CallerContext

Family = Literal["glossary", "doc_type", "entry_kind", "native_kind", "symbol", "artifact_id"]
FAMILIES = ("glossary", "doc_type", "entry_kind", "native_kind", "symbol", "artifact_id")


class EntityMatch(KernelModel):
    """Half-open code-point offsets into an original input channel."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=False)
    channel: str
    record_index: int | None = None
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    surface: str


class EntityProvenance(KernelModel):
    """Source bytes and retained projection are independently content-addressed."""

    source_id: str
    locator: str
    snapshot: str
    source_hash: str
    projection_hash: str


class EntityCard(KernelModel):
    """One typed identity and its bounded authored meaning; never task evidence."""

    family: Family
    identity: str
    native_kind: str | None = None
    meaning: str = ""
    signature: str | None = None
    resolution: Literal["resolved", "ambiguous"] = "resolved"
    matches: list[EntityMatch] = Field(default_factory=list)
    provenance: EntityProvenance


class UnresolvedEntity(KernelModel):
    """Caller-provided unresolved text without invented repository provenance."""

    family: Family
    reference: str
    state: Literal["ambiguous", "unknown_id", "invalid_reference", "unsupported_kind"]
    matches: list[EntityMatch] = Field(default_factory=list)
    candidates: list[str] = Field(default_factory=list)


class EntityCounts(KernelModel):
    """Distinct candidate and identity counts, after permission filtering."""

    detected: int = 0
    resolved: int = 0
    returned: int = 0
    omitted: int = 0
    unknown: int = 0
    ambiguous: int = 0


class EntityCoverage(KernelModel):
    """Freshness and scan completeness are separate from bounded output omission."""

    scan_complete: bool = False
    index_status: str = "unavailable"
    index_fingerprint: str | None = None
    families: dict[str, str] = Field(default_factory=dict)
    counts: EntityCounts = Field(default_factory=EntityCounts)
    by_family: dict[str, EntityCounts] = Field(default_factory=dict)


class EntityBudgets(KernelModel):
    """Actual bounded work and exact compact projection length."""

    lookups: int = 0
    serialized_chars: int = 0
    elapsed_ms: float = 0
    jev_calls: Literal[0] = 0


class EntityContext(KernelModel):
    """An initial interpretation snapshot; old EnrichedContext remains a separate type."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=False)
    kind: Literal["entity_context"] = "entity_context"
    original_goal: str
    caller_context: CallerContext = Field(default_factory=CallerContext)
    workspace_id: str
    repository_root: str
    registered_capabilities: list[str] = Field(default_factory=list)
    status: Literal["recognized", "no_matches", "partial", "unavailable", "disabled"]
    entities: list[EntityCard] = Field(default_factory=list)
    unresolved: list[UnresolvedEntity] = Field(default_factory=list)
    coverage: EntityCoverage = Field(default_factory=EntityCoverage)
    budgets: EntityBudgets = Field(default_factory=EntityBudgets)
    limitations: list[str] = Field(default_factory=list)

# DECISION HISTORY
# ================================================================================
# - 2026-10-03 15:05 [python-coder]: Keep pre-intent meanings deterministic, scoped and separate from task evidence. (#TICKETLESS reason=user-approved-ac-first-DK300)
