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
    digest = content_hash(body if body is not None else locator)
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


def _projected_excerpt(item: KnowledgeEvidence, payload: RetrievalRequestPayload) -> KnowledgeEvidence:
    """Expose requested projected facts with their field locators instead of unrelated source prose.

    Args:
        item: Actual authorized neutral evidence at its current disclosure level.
        payload: Accepted typed needs, if this is the interpreted public path.

    Returns:
        Evidence with attributable projected fields, or the unchanged source excerpt.
    """
    needs = payload.retrieval_needs
    if needs is None or needs.detail_mode != "fields" or item.disclosure_level >= 3:
        return item
    from knowledge.answer_fields import field_value
    fields = {name: field_value(item, name) for name in needs.selections["required_fields"]}
    body = json.dumps({"canonical_id": item.entity.canonical_id, "fields": fields,
        "field_locators": item.field_locators}, ensure_ascii=False, sort_keys=True)
    return item.model_copy(update={"content": body, "limitations": [*item.limitations,
        "Canonical projected fields with source locators; not a verbatim source quote."]})


def _requested_field_contents(item: KnowledgeEvidence, request: KnowledgeRetrievalRequest,
                              result: KnowledgeRetrievalResult) -> KnowledgeEvidence:
    """Reject unrequested or mislocated extra excerpts from the application-owned port.

    Args:
        item: Neutral port response before additional public citations are created.
        request: Authoritative requirements and disclosure permission sent to the port.
        result: Response whose missing requested citations must remain explicit.

    Returns:
        Evidence retaining only requested, supported excerpts at their exact source pointer.
    """
    from knowledge.requested_fields import SOURCE_FIELDS
    required = set(request.answer_requirements.required_fields if request.answer_requirements else [])
    excerpts, availability = {}, dict(item.field_availability)
    properties = dict(item.entity.properties)
    limitations = list(item.limitations)
    for name, text in item.field_contents.items():
        valid = (name in required and name in SOURCE_FIELDS
            and request.disclosure_level == item.disclosure_level == 3
            and item.field_locators.get(name) == SOURCE_FIELDS[name]
            and item.field_availability.get(name) == "present" and bool(text.strip()))
        if valid:
            excerpts[name] = text
            continue
        properties.pop(name, None)
        if name in required:
            availability[name] = "unknown"
            limitations.append(f"requested source field {name} has no valid source citation")
            result.status = "partial"
    return item.model_copy(update={"field_contents": excerpts, "field_availability": availability,
        "entity": item.entity.model_copy(update={"properties": properties}), "limitations": limitations})


def _field_evidence(ctx: ExecutionContext, payload: RetrievalRequestPayload,
                    item: KnowledgeEvidence, result: KnowledgeRetrievalResult,
                    invocation: CapabilityInvocation, remaining: int | None, slots: int
                    ) -> tuple[KnowledgeEvidence, list[Evidence], int | None]:
    """Cite each additional requested field separately under the shared kernel text budget.

    Args:
        ctx: Trusted scope and configured excerpt bound.
        payload: Original question and evidence category.
        item: Authorized source entity with exact additional field excerpts.
        result: Neutral response retaining authoritative truncation state.
        invocation: Current producer for source attribution.
        remaining: Unspent caller character allowance across all source excerpts.
        slots: Remaining public evidence slots after reserving the main source citation.

    Returns:
        Bounded neutral item, separately cited field evidence and remaining characters.
    """
    excerpts = dict(item.field_contents)
    availability = dict(item.field_availability)
    evidence = []
    for name, text in item.field_contents.items():
        cap = min(len(text), ctx.config.retrieval.max_excerpt_chars,
                  remaining if remaining is not None else len(text)) if slots > 0 else 0
        excerpts[name] = text[:cap]
        if cap < len(text):
            result.truncated = True
            availability[name] = "truncated"
        if remaining is not None:
            remaining -= cap
        if not cap:
            continue
        source = item.entity.source.model_copy(update={"locator": item.field_locators[name]})
        field = item.model_copy(update={"entity": item.entity.model_copy(update={"source": source}),
            "content": excerpts[name], "field_contents": {}})
        evidence.append(to_kernel_evidence(field, retrieval_id=result.retrieval_id,
            category=payload.need.category, invocation_id=invocation.id, now=ctx.clock()))
        slots -= 1
    return item.model_copy(update={"field_contents": excerpts, "field_availability": availability}), evidence, remaining


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
        if len(evidence) >= request.budget.max_results:
            break
        item = _requested_field_contents(item, request, result)
        item = _projected_excerpt(item, payload)
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
        item, additional, remaining = _field_evidence(ctx, payload, item, result, invocation, remaining,
            request.budget.max_results - len(evidence) - 1)
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
        evidence.extend(additional)
    result.truncated = result.truncated or len(bounded_items) < len(result.evidence)
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

    def _uses_query_growth(self, invocation, request) -> bool:
        """Resume the existing catalog wait; typed initial reads use the shared selector."""
        growth_resume = (invocation.continuation is not None
            and invocation.continuation.state.get("phase") in {"clarify", "building", "admitting"})
        return (self.query_catalog is not None and self.query_admission is not None
                and request.knowledge is None and (request.retrieval_needs is None or growth_resume))

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
        from integrations.knowledge_budget import preserve_jev_reserve
        with preserve_jev_reserve(ctx, request.jev_reserve) as bounded_ctx:
            if self._uses_query_growth(invocation, request):
                from integrations.query_growth import invoke_query_growth
                return await invoke_query_growth(self.retriever,self.query_catalog,self.query_admission,
                                                 invocation,bounded_ctx,request,eligible)
            return await invoke_knowledge(self.retriever, invocation, bounded_ctx, request, eligible,
                                          fallback=self.fallback, query_catalog=self.query_catalog,
                                          query_admission=self.query_admission)


# DECISION HISTORY
# ================================================================================
# - 2026-10-01 20:00 [python-coder]: Preserve canonical evidence and optional bounded retrieval. (#TICKET-20261001-KM-400e-3)

# - 2026-10-02 04:42 [python-coder]: Carry the requester reserve through graph planning on the real worker budget. (#TICKETLESS reason=kernel-v01-integration)
# - 2026-10-03 20:00 [python-coder]: Consume selected repository fallback through the same bounded capability facade. (#TICKETLESS reason=user-approved-DK300-graph-routing)

# - 2026-10-09 15:40 [python-coder]: Preserve typed question obligations through public research and scoped query selection. (#KM-500/KM-500e-1-i)

# - 2026-10-09 17:00 [python-coder]: Expose additional authored fields as individually cited public evidence under existing character bounds. (#KM-500/KM-500e-1-i)
