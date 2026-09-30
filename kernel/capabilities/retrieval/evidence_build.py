"""
MODULE: kernel.capabilities.retrieval.evidence_build
GOAL: Turn ranked candidates into Evidence items with source identity, locator, revision, content
    hash, provenance and truncation, honouring the request's detail level and size limit.
BUSINESS CONTEXT: Every result must be inspectable: where it came from, which revision, what
    hash, whether it was cut (Rev 3 section 10.3). Source text is stored verbatim as evidence; it
    is never interpreted.
ARCHITECTURE: Pure function over Candidate and Ranked. The evidence id is content-addressed
    (locator plus hash), so the same excerpt from the same place is the same evidence.
"""

from __future__ import annotations

from datetime import datetime

from kernel.capabilities.retrieval.candidates import Candidate
from kernel.capabilities.retrieval.rerank import Ranked
from kernel.contracts.base import content_hash, evidence_id
from kernel.contracts.enums import EvidenceCategory, SemanticType, SourceKind, Verification
from kernel.contracts.evidence import Evidence, EvidenceSource, Provenance, SourceVersion
from kernel.contracts.payloads import RetrievalRequestPayload

PRODUCER = "retrieve.repository"


def _semantic_type(candidate: Candidate) -> SemanticType:
    """Markdown and knowledge nodes are documentation facts; other files repository facts."""
    if candidate.kind is SourceKind.KNOWLEDGE_NODE or candidate.path.endswith(".md"):
        return SemanticType.DOCUMENTATION_FACT
    return SemanticType.REPOSITORY_FACT


def _shape(candidate: Candidate, request: RetrievalRequestPayload, remaining: int | None
           ) -> tuple[str, bool, list[str]]:
    """Return (excerpt, truncated, limitations) after applying detail and the char budget."""
    limits: list[str] = []
    truncated = candidate.truncated
    excerpt = candidate.excerpt
    if request.detail == "locator":
        excerpt, truncated = f"[locator only] {candidate.locator}", True
        limits.append("detail=locator requested: excerpt omitted")
    elif request.detail == "summary":
        limits.append("detail=summary is not supported natively: excerpt returned")
    if remaining is not None and len(excerpt) > remaining:
        excerpt, truncated = excerpt[:max(remaining, 0)], True
        limits.append("excerpt cut to the request's max_chars")
    if candidate.truncated:
        limits.append("excerpt cut at max_excerpt_chars")
    return excerpt, truncated, limits


def build_evidence(ranked: Ranked, request: RetrievalRequestPayload,
                   category: EvidenceCategory, version: SourceVersion | None,
                   invocation_id: str, now: datetime, remaining: int | None, terms: list[str]
                   ) -> Evidence | None:
    """Build one Evidence item, or None when the char budget is already exhausted."""
    candidate = ranked.candidate
    if remaining is not None and remaining <= 0:
        return None
    excerpt, truncated, limits = _shape(candidate, request, remaining)
    if not excerpt:
        return None
    digest = content_hash(excerpt)
    source = EvidenceSource(
        id=candidate.source_id, kind=candidate.kind, locator=candidate.locator,
        title=candidate.title, source_version=version, retrieved_at=now,
        observed_modified_at=candidate.modified_at)
    provenance = Provenance(
        producer=PRODUCER, invocation_id=invocation_id, strategy=candidate.strategy,
        query=request.need.question, terms=list(candidate.terms or terms), rank=ranked.rank,
        relevance=ranked.relevance)
    return Evidence(
        id=evidence_id(candidate.locator, digest), category=category,
        semantic_type=_semantic_type(candidate), excerpt=excerpt, source=source,
        content_hash=digest, provenance=provenance, verification=Verification.SOURCE_VERIFIED,
        limitations=limits, truncated=truncated)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:00 [python-coder]: Excerpts read verbatim from a file are marked
#   source_verified (the text is exactly what the source contains); that says nothing about the
#   claim being true. (#KernelBootstrapV0/P5)
# ====================================================================
