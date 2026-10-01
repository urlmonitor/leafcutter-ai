"""
MODULE: kernel.contracts.evidence
GOAL: Evidence, findings, evidence needs and bundles (Rev 3 section 7.3).
BUSINESS CONTEXT: Decisions are only as trustworthy as the evidence behind them; every item keeps
    its source, revision, content hash and verification status so provenance survives restarts.
ARCHITECTURE: Depends on contracts.base and contracts.enums only. Evidence ids are
    content-addressed and verified by a validator.
"""

from __future__ import annotations

from datetime import datetime

from typing import Any

from pydantic import ConfigDict, Field, field_validator, model_validator

from kernel.contracts.base import (
    KernelModel,
    PersistedModel,
    StableId,
    content_hash,
    evidence_id,
    fail,
    sha256_hex,
)
from kernel.contracts.enums import (
    EvidenceCategory,
    FindingKind,
    NeedStatus,
    Priority,
    SemanticType,
    SourceKind,
    Verification,
)


class EvidenceInput(KernelModel):
    """Caller-supplied initial evidence; the kernel converts it to Evidence at intake.

    The excerpt is kept verbatim (indentation included); only title and locator are stripped.
    """

    model_config = ConfigDict(str_strip_whitespace=False)

    title: str = Field(min_length=1, max_length=300)
    excerpt: str = Field(min_length=1)
    locator: str | None = None
    category: EvidenceCategory = EvidenceCategory.TASK_CONTEXT

    @field_validator("title", "locator")
    @classmethod
    def _strip_labels(cls, value: str | None) -> str | None:
        """Strip the label fields (the excerpt is the only verbatim field)."""
        return value.strip() if value is not None else None

    @field_validator("excerpt")
    @classmethod
    def _excerpt_not_blank(cls, value: str) -> str:
        """Keep the excerpt verbatim but refuse one that is only whitespace."""
        if not value.strip():
            fail("an evidence excerpt must contain text")
        return value


class SourceVersion(KernelModel):
    """Revision identity of a source (commit plus dirty flag)."""

    commit: str | None = None
    dirty: bool = False


class EvidenceSource(KernelModel):
    """Where an Evidence item came from."""

    id: StableId
    kind: SourceKind
    locator: str = Field(min_length=1)
    title: str = ""
    source_version: SourceVersion | None = None
    retrieved_at: datetime | None = None
    observed_modified_at: datetime | None = None
    section_locator: str | None = None


class Provenance(KernelModel):
    """How an Evidence item was produced."""

    producer: str
    invocation_id: str | None = None
    strategy: str | None = None
    query: str | None = None
    terms: list[str] = Field(default_factory=list)
    rank: int | None = Field(default=None, ge=0)
    relevance: float | None = Field(default=None, ge=0.0, le=1.0)
    actor: str | None = None
    relayed_by: str | None = None


class Evidence(PersistedModel):
    """One excerpt (or artifact reference) with source, hash and verification status.

    The excerpt is the source text verbatim: whitespace is never stripped, so a hash computed over
    the excerpt as read matches the stored one. `id` and `content_hash` may be omitted on input
    (a host must not invent them): they are then computed from the locator and the body.
    """

    model_config = ConfigDict(str_strip_whitespace=False)

    category: EvidenceCategory
    semantic_type: SemanticType
    excerpt: str | None = None
    artifact_ref: str | None = None
    source: EvidenceSource
    content_hash: str = Field(min_length=8)
    provenance: Provenance
    access: str = Field(default="internal", pattern="^(internal|restricted)$")
    verification: Verification = Verification.UNVERIFIED
    limitations: list[str] = Field(default_factory=list)
    truncated: bool = False

    @model_validator(mode="before")
    @classmethod
    def _complete_hash_and_id(cls, data: Any) -> Any:
        """Compute a missing content hash and id from the body and locator (never overwrite)."""
        if not isinstance(data, dict):
            return data
        body = data.get("excerpt")
        if body is None:
            body = data.get("artifact_ref")
        source = data.get("source")
        locator = source.get("locator") if isinstance(source, dict) else None
        if not isinstance(body, str) or not isinstance(locator, str):
            return data
        filled = dict(data)
        filled.setdefault("content_hash", content_hash(body))
        filled.setdefault("id", evidence_id(locator.strip(), str(filled["content_hash"])))
        return filled

    @model_validator(mode="after")
    def _check_body_and_id(self) -> Evidence:
        """Require an excerpt or artifact ref and a content-addressed id."""
        if self.excerpt is None and self.artifact_ref is None:
            fail("evidence needs an excerpt or an artifact_ref")
        expected = evidence_id(self.source.locator, self.content_hash)
        if self.id != expected:
            fail(f"evidence id must be content-addressed ({expected})")
        return self


def stronger_category(known: Evidence | None, new: Evidence) -> Evidence:
    """Return the evidence to keep when `new` arrives and `known` may hold the same content.

    Evidence ids are content-addressed (locator and hash), so one excerpt fetched for two needs
    is one item. It must not stay an `existing_patterns` item because that need happened to
    finish first when another need found the same text to be a decision basis, an internal
    principle or task context: a pattern shows how something is done, not that it is required.
    """
    if known is None:
        return new
    if known.category is EvidenceCategory.EXISTING_PATTERNS             and new.category is not EvidenceCategory.EXISTING_PATTERNS:
        return known.model_copy(update={"category": new.category})
    return known


class Finding(PersistedModel):
    """A source-linked claim: fact, inference, assumption or reported human input."""

    claim: str = Field(min_length=1)
    kind: FindingKind
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    producer: str
    producer_version: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _complete_id(cls, data: Any) -> Any:
        """Derive a missing id from the claim (a host must not invent ids)."""
        if isinstance(data, dict) and "id" not in data and isinstance(data.get("claim"), str):
            return {**data, "id": "find-" + sha256_hex(data["claim"].strip())[:16]}
        return data

    @model_validator(mode="after")
    def _facts_need_support(self) -> Finding:
        """A source fact must cite evidence; it cannot stand on its own."""
        if self.kind is FindingKind.SOURCE_FACT and not self.supporting_evidence_ids:
            fail("a source_fact finding needs supporting_evidence_ids")
        return self


class EvidenceNeed(KernelModel):
    """A piece of evidence the run still needs, with its resolution status."""

    id: StableId
    category: EvidenceCategory
    question: str = Field(min_length=1)
    priority: Priority = Priority.REQUIRED
    acceptable_source_kinds: list[SourceKind] = Field(default_factory=list)
    resolution: list[str] = Field(default_factory=list)
    status: NeedStatus = NeedStatus.OPEN


class UnavailableSource(KernelModel):
    """A source that could not be consulted, with the reason."""

    source_id: str
    reason: str


class Contradiction(KernelModel):
    """Two evidence items that disagree on a point relevant to the question."""

    a: str
    b: str
    note: str = ""


class BundleBody(KernelModel):
    """Fields shared by the persisted EvidenceBundle and the evidence_bundle.v1 payload."""

    request_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    finding_ids: list[str] = Field(default_factory=list)
    coverage: dict[str, NeedStatus] = Field(default_factory=dict)
    attempted_sources: list[str] = Field(default_factory=list)
    unavailable_sources: list[UnavailableSource] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    truncated: bool = False


class EvidenceBundle(PersistedModel, BundleBody):
    """Persisted bundle of evidence answering one request."""


class EvidenceBundlePayload(BundleBody):
    """leafcutter.evidence_bundle.v1: the bundle plus its inline evidence and findings."""

    evidence: list[Evidence] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 23:00 [python-coder]: One excerpt fetched for several needs keeps the non-pattern
#   category (stronger_category): first-wins merging let an existing_patterns need that finished
#   first hide the decision basis the same ADR provided for prior_decisions.
#   (#KernelBootstrapV0/GROUND)
# - 2026-10-01 23:00 [python-coder]: Evidence excerpts are verbatim (no whitespace stripping):
#   stripping changed the text after its hash was computed and broke a host's own hash. A missing
#   id or content_hash is computed, so the host schema may leave them out. (#KernelBootstrapV0/GROUND)
# - 2026-09-30 22:00 [python-coder]: Evidence id integrity is enforced in the model so a forged
#   id cannot enter state; bundle fields are shared through BundleBody. (#KernelBootstrapV0/P1)
# ====================================================================
