"""
MODULE: kernel.contracts.evidence
GOAL: Evidence, findings, evidence needs and bundles (Rev 3 section 7.3).
BUSINESS CONTEXT: Decisions are only as trustworthy as the evidence behind them; every item keeps
    its source, revision, content hash and verification status so provenance survives restarts.
ARCHITECTURE: Depends on contracts.base and contracts.enums only. Evidence ids are
    content-addressed and verified by a validator.
"""

from __future__ import annotations

from kernel.contracts.verbatim import VerbatimJson

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
    """Commit the source was read at, so evidence can be told stale when the repository moves on."""
    dirty: bool = False
    (
        "True when the working tree differed from that commit, so the text may not match any "
        "commit."
    )


class EvidenceSource(KernelModel):
    """Where an Evidence item came from."""

    id: StableId
    """Id of the configured source the evidence came from."""
    kind: SourceKind
    (
        "What kind of source it is (repository file, knowledge node, host research, human, task "
        "input)."
    )
    locator: str = Field(min_length=1)
    (
        "Where to find the text again (file path with anchor, node id, or similar); part of the "
        "evidence id."
    )
    title: str = ""
    """Human-readable name of the source, for display."""
    source_version: SourceVersion | None = None
    """Revision of the source that was read."""
    retrieved_at: datetime | None = None
    """When the kernel read the source (UTC)."""
    observed_modified_at: datetime | None = None
    """When the source itself was last modified (UTC), to judge how fresh the evidence is."""
    section_locator: str | None = None
    """Position of the excerpt inside the source, such as a heading or line range."""


class Provenance(KernelModel):
    """How an Evidence item was produced."""

    producer: str
    """Component that produced the evidence, for audit."""
    invocation_id: str | None = None
    """Capability invocation that produced it, linking evidence to its trace."""
    strategy: str | None = None
    """Retrieval strategy that found it (for example repository text or knowledge map)."""
    query: str | None = None
    """The query text that found it."""
    terms: list[str] = Field(default_factory=list)
    """Search terms that matched, showing why it was retrieved."""
    rank: int | None = Field(default=None, ge=0)
    """Its position among the candidates the strategy found (0 is best)."""
    relevance: float | None = Field(default=None, ge=0.0, le=1.0)
    """Judged relevance to the need (0 to 1)."""
    actor: str | None = None
    """The human or host actor who supplied it, when it did not come from a kernel retrieval."""
    relayed_by: str | None = None
    """The client that relayed a submission from that actor."""


class Evidence(PersistedModel):
    """One excerpt (or artifact reference) with source, hash and verification status.

    The excerpt is the source text verbatim: whitespace is never stripped, so a hash computed over
    the excerpt as read matches the stored one. `id` and `content_hash` may be omitted on input
    (a host must not invent them): they are then computed from the locator and the body.
    """

    model_config = ConfigDict(str_strip_whitespace=False)

    category: EvidenceCategory
    (
        "What kind of evidence it is (guidance, prior decision, existing pattern, ...), which "
        "decides the needs it can satisfy and its role in a decision."
    )
    semantic_type: SemanticType
    (
        "Whether the text is a repository fact, documentation, human input, synthesis or task "
        "context."
    )
    excerpt: str | None = None
    """The source text verbatim (whitespace kept), so its hash matches the stored one."""
    artifact_ref: str | None = None
    """Reference to a stored artifact holding the content when no excerpt is kept."""
    source: EvidenceSource
    """Where the evidence came from."""
    content_hash: str = Field(min_length=8)
    (
        "Hash of the body; with the locator it forms the evidence id, so identical text is one "
        "item."
    )
    provenance: Provenance
    """How the evidence was produced."""
    access: str = Field(default="internal", pattern="^(internal|restricted)$")
    (
        "Visibility label of the item (internal or restricted), so restricted evidence can be "
        "handled with care."
    )
    verification: Verification = Verification.UNVERIFIED
    (
        "How far the text was checked against its source (unverified, host reported, source "
        "verified)."
    )
    limitations: list[str] = Field(default_factory=list)
    """Caveats on this item, such as a cut excerpt, that the reader should weigh."""
    truncated: bool = False
    """True when the excerpt was cut to fit a limit, so more text exists in the source."""

    @model_validator(mode="before")
    @classmethod
    def _complete_hash_and_id(cls, data: Any) -> Any:
        """Compute a missing content hash and id from the body and locator (never overwrite).

        Args:
            data: Incoming evidence fields before model validation.

        Returns:
            Input fields with missing content identity derived.
        """
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
    """The statement being made; its id is derived from this text."""
    kind: FindingKind
    """Whether the claim is a source fact, an inference, an assumption or reported human input."""
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    """Evidence that backs the claim; a source fact must cite some."""
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    """Evidence that argues against the claim, kept so disagreement stays visible."""
    limitations: list[str] = Field(default_factory=list)
    """Caveats on the claim that the reader should weigh."""
    producer: str
    """Who or what produced the finding, for audit."""
    producer_version: str | None = None
    """Version of that producer (template or model), so findings can be compared across versions."""

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


#: Id prefix of a need that checks the claims of one option (`need.claim.<option id>`).
CLAIM_NEED_PREFIX = "need.claim."


class EvidenceNeed(KernelModel):
    """A piece of evidence the run still needs, with its resolution status."""

    id: StableId
    """Stable id of the need; answers and coverage are keyed by it."""
    category: EvidenceCategory
    """Which kind of evidence would satisfy the need."""
    question: str = Field(min_length=1)
    """What the evidence must tell the run."""
    priority: Priority = Priority.REQUIRED
    """Whether the need blocks resolution (required) or only improves it (supporting)."""
    acceptable_source_kinds: list[SourceKind] = Field(default_factory=list)
    (
        "Source kinds the requester would accept for this need; empty means any (not yet used to "
        "filter sources)."
    )
    resolution: list[str] = Field(default_factory=list)
    """Notes on how the need was resolved, such as why no source could serve it."""
    status: NeedStatus = NeedStatus.OPEN
    """Whether the need is open, satisfied, partly met or cannot be met."""


class UnavailableSource(KernelModel):
    """A source that could not be consulted, with the reason."""

    source_id: str
    """Id of the source that could not be consulted."""
    reason: str
    """Why it could not be consulted, so the reader can tell a gap from a miss."""


class Contradiction(KernelModel):
    """Two evidence items that disagree on a point relevant to the question."""

    a: str
    """Id of one of the two evidence items that disagree."""
    b: str
    """Id of the other evidence item."""
    note: str = ""
    """What they disagree about."""


class BundleBody(KernelModel):
    """Fields shared by the persisted EvidenceBundle and the evidence_bundle.v1 payload."""

    request_id: str | None = None
    """Id of the request this bundle answers."""
    evidence_ids: list[str] = Field(default_factory=list)
    """Ids of the evidence items found for the request."""
    finding_ids: list[str] = Field(default_factory=list)
    """Ids of the findings drawn from that evidence."""
    coverage: dict[str, NeedStatus] = Field(default_factory=dict)
    """For each evidence need id, whether it was satisfied, partly met or unavailable."""
    assessments: dict[str, dict[str, VerbatimJson]] = Field(default_factory=dict)
    """Attributed conditional assessments; never independently verified source facts."""
    attempted_sources: list[str] = Field(default_factory=list)
    """Ids of the sources consulted, so an empty result can be told from a search never made."""
    unavailable_sources: list[UnavailableSource] = Field(default_factory=list)
    """Sources that could not be consulted, with the reason."""
    contradictions: list[Contradiction] = Field(default_factory=list)
    """Pairs of evidence that disagree, surfaced for the reader to resolve."""
    limitations: list[str] = Field(default_factory=list)
    """Caveats on the bundle's completeness, such as cut-off retrieval."""
    truncated: bool = False
    """True when limits cut the result, so more matching evidence may exist."""


class EvidenceBundle(PersistedModel, BundleBody):
    """Persisted bundle of evidence answering one request."""


class EvidenceBundlePayload(BundleBody):
    """leafcutter.evidence_bundle.v1: the bundle plus its inline evidence and findings."""

    evidence: list[Evidence] = Field(default_factory=list)
    """The evidence items themselves, carried inline so the receiver needs no lookup."""
    findings: list[Finding] = Field(default_factory=list)
    """The findings themselves, carried inline."""
    unknowns: list[str] = Field(default_factory=list)
    """What a synthesis said it could not find (gaps the next round can aim a query at)."""
    need_evidence: dict[str, list[str]] = Field(default_factory=dict)
    (
        "Per need id, the ids of its evidence that passed relevance (a claim need names its "
        "option)."
    )
    need_limitations: dict[str, list[str]] = Field(default_factory=dict)
    """Per need id, the retrieval cut notes of that need (a decision summarises them per need)."""


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-09 [python-coder]: Field purposes added; the `#:` field comments became attribute
#   docstrings with the same meaning. (#TICKET-20261009-KernelContractFieldDescriptions)
# - 2026-10-01 [python-coder]: EvidenceBundlePayload.need_evidence maps a need to the evidence that
#   passed relevance for it, so a decision can cite a claim need's evidence on its option.
#   (#KernelDecisionStore)
# - 2026-10-01 [python-coder]: The bundle payload carries the unknowns a synthesis named, so the
#   decision can turn them into targeted research. (#KernelV01/D)
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
