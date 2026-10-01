"""
MODULE: knowledge_capability
GOAL: Canonical kernel Evidence conversion and registered capability facade.
BUSINESS CONTEXT: Keep optional knowledge retrieval bounded and traceable.
ARCHITECTURE: Adapter between neutral knowledge transport and existing kernel contracts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from kernel.capabilities.base import ExecutionContext
    from kernel.contracts import CapabilityInvocation, CapabilityResult
    from kernel.contracts.payloads import RetrievalRequestPayload
    from knowledge.ports import KnowledgeRetriever
    from knowledge.query_catalog import QueryCatalog
    from knowledge.query_admission import QueryAdmission

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime
    from knowledge.contracts import (
        KnowledgeEvidence,
        KnowledgeRetrievalRequest,
        KnowledgeRetrievalResult,
    )
    from kernel.contracts.payloads import RetrievalRequestPayload
    from knowledge.ports import KnowledgeRetriever
    from kernel.capabilities.base import CapabilityExecutor, ExecutionContext
    from kernel.contracts.capability import CapabilityResult
    from kernel.contracts.work import CapabilityInvocation


import json
from urllib.parse import quote

from kernel.contracts.base import content_hash, evidence_id, utc_now
from kernel.contracts.enums import EvidenceCategory, SemanticType, SourceKind, Verification
from kernel.contracts.evidence import Evidence, EvidenceSource, Provenance, SourceVersion


def to_kernel_evidence(
    item: KnowledgeEvidence,
    *,
    retrieval_id: str,
    category: EvidenceCategory = EvidenceCategory.TASK_CONTEXT,
    invocation_id: str | None = None,
    now: datetime | None = None,
) -> Evidence:
    """Preserve source revision and exact whitespace using canonical evidence identity.

    Args:
        item: Disclosed neutral evidence to map or authorize.

    Returns:
        Evidence: Validated result of the documented operation.
    """
    source = item.entity.source
    locator = (
        f"knowledge://{quote(source.repository_id, safe='')}@{source.source_sha}/"
        f"{quote(item.entity.canonical_id, safe='')}?path={quote(source.path, safe='/')}"
        f"&locator={quote(source.locator, safe='')}"
    )
    body = item.content
    artifact = None if body is not None else locator
    digest = content_hash(body if body is not None else artifact)
    stamp = now or utc_now()
    limitations = list(item.limitations)
    graph = {
        "seed_id": item.seed_id,
        "signals": item.signals,
        "path": [edge.model_dump(mode="json") for edge in item.path],
        "relationships": [edge.model_dump(mode="json") for edge in item.relationships],
        "related": item.related,
    }
    if any(graph.values()):
        limitations.append(
            "Derived graph context (not a source quote; scores are ranking signals): "
            + json.dumps(graph, ensure_ascii=False, separators=(",", ":"))
        )
    if item.disclosure_level < 3:
        limitations.append(
            "Discovery or summary evidence; request source disclosure before quoting."
        )
    if item.entity.properties.get("synthetic"):
        limitations.append("Synthetic demonstration; not production historical knowledge.")
    return Evidence(
        id=evidence_id(locator, digest),
        created_at=stamp,
        updated_at=stamp,
        category=category,
        semantic_type=SemanticType.DOCUMENTATION_FACT,
        excerpt=body,
        artifact_ref=artifact,
        content_hash=digest,
        source=EvidenceSource(
            id="knowledge.retrieval",
            kind=SourceKind.KNOWLEDGE_NODE,
            locator=locator,
            title=item.entity.title,
            retrieved_at=stamp,
            source_version=SourceVersion(commit=source.source_sha, dirty=False),
            section_locator=source.locator or None,
        ),
        provenance=Provenance(
            producer="knowledge.retrieval",
            invocation_id=invocation_id,
            strategy=f"knowledge:{retrieval_id}",
        ),
        verification=Verification.UNVERIFIED,
        limitations=limitations,
    )


def map_bounded_evidence(
    ctx: ExecutionContext,
    payload: RetrievalRequestPayload,
    request: KnowledgeRetrievalRequest,
    result: KnowledgeRetrievalResult,
    invocation: CapabilityInvocation,
) -> list[Evidence]:
    """Apply kernel excerpt limits before constructing canonical evidence.

    Args:
        ctx: Trusted execution context and excerpt limits.
        payload: Caller content limits and evidence category.
        request: Validated neutral request budget.
        result: Neutral response, updated with honest truncation state.
        invocation: Existing capability invocation for provenance.

    Returns:
        list[Evidence]: Canonical evidence within the caller's excerpt budget.
    """
    evidence = []
    bounded_items = []
    remaining = payload.limits.max_chars
    for item in result.evidence[: request.budget.max_results]:
        text = item.content
        if text is not None:
            cap = min(
                len(text),
                ctx.config.retrieval.max_excerpt_chars,
                remaining if remaining is not None else len(text),
            )
            if cap < len(text):
                item = item.model_copy(
                    update={
                        "content": text[:cap],
                        "limitations": [*item.limitations, "kernel excerpt content budget reached"],
                    }
                )
                result.truncated = True
            if remaining is not None:
                remaining -= cap
        bounded_items.append(item)
        evidence.append(
            to_kernel_evidence(
                item,
                retrieval_id=result.retrieval_id,
                category=payload.need.category,
                invocation_id=invocation.id,
                now=ctx.clock(),
            )
        )
    result.truncated = result.truncated or len(evidence) < len(result.evidence)
    result.evidence = bounded_items
    return evidence


class KnowledgeRetrievalExecutor:
    """Registered retrieve.repository facade; ordinary file retrieval stays available."""

    def __init__(
        self, retriever: KnowledgeRetriever, fallback: CapabilityExecutor | None = None,
        *, query_catalog: QueryCatalog | None=None, query_admission: QueryAdmission | None=None
    ) -> None:
        """Inject an application-owned port, never a database session.

        Args:
            retriever: Application-owned retrieval port.
            fallback: Existing repository executor for ordinary requests.
        """
        self.retriever = retriever
        self.fallback = fallback
        self.query_catalog = query_catalog
        self.query_admission = query_admission

    async def ainvoke(
        self, invocation: CapabilityInvocation, ctx: ExecutionContext
    ) -> CapabilityResult:
        """Use the knowledge seam only for explicit or configured graph requests.

        Args:
            invocation: Existing registered capability invocation.
            ctx: Trusted execution scope, budgets and telemetry owner.

        Returns:
            CapabilityResult: Validated result of the documented operation.
        """
        from integrations.knowledge_execution import invoke_knowledge
        from kernel.capabilities.retrieval import RepositoryRetrievalExecutor
        from kernel.contracts.payloads import RetrievalRequestPayload
        from kernel.contracts.schema_catalog import validate_payload

        request = validate_payload(invocation.input_payload_schema, invocation.input_payload)
        if not isinstance(request, RetrievalRequestPayload):
            return await (self.fallback or RepositoryRetrievalExecutor()).ainvoke(invocation, ctx)
        graph_ids = {
            s.id
            for s in ctx.config.sources
            if s.kind == "graph_query" and request.need.category in s.categories
        }
        eligible = graph_ids.intersection(request.source_ids) if request.source_ids else graph_ids
        if ctx.scope.source_ids:
            eligible.intersection_update(ctx.scope.source_ids)
        if request.knowledge is None and not eligible:
            return await (self.fallback or RepositoryRetrievalExecutor()).ainvoke(invocation, ctx)
        if self.query_catalog is not None and self.query_admission is not None and request.knowledge is None:
            from integrations.query_growth import invoke_query_growth
            return await invoke_query_growth(self.retriever,self.query_catalog,self.query_admission,
                                             invocation,ctx,request,eligible)
        return await invoke_knowledge(self.retriever, invocation, ctx, request, eligible)


# DECISION HISTORY
# ================================================================================
# - 2026-10-01 20:00 [python-coder]: Preserve canonical evidence and optional bounded retrieval. (#TICKET-20261001-KM-400e-3)
