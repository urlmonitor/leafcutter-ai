"""
MODULE: kernel.capabilities.retrieval.executor
GOAL: The native `retrieve.repository` capability: a read-only evidence search over allowlisted
    repository files and the knowledge map, returning an evidence bundle.
BUSINESS CONTEXT: The one real local source of the MVP. Results are inspectable evidence (source,
    locator, revision, hash, truncation), a failed or unreachable source is reported as
    unavailable rather than as an empty search, and source text is data, never instructions
    (Rev 3 sections 10.3 and 13.3).
ARCHITECTURE: Plain native function (no graph): select sources from config.sources, search each
    in a worker thread (repo_text or knowledge_map), merge, rerank with one Jev batch, build
    Evidence, and assemble the bundle. Coverage is keyed by need id so the research capability
    can map a bundle back to its need.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
from pathlib import Path

from kernel.capabilities.base import ExecutionContext
from kernel.capabilities.decision.jev_support import (
    StopCapability,
    blocked_result,
    failed_result,
)
from kernel.capabilities.retrieval.access import ReadPolicy
from kernel.capabilities.retrieval.candidates import Candidate, SearchReport
from kernel.capabilities.retrieval.entities import QueryEntities, extract_entities
from kernel.capabilities.retrieval.evidence_build import build_evidence
from kernel.capabilities.retrieval.knowledge_map import search_knowledge_map
from kernel.capabilities.retrieval.locators import fetch_explicit
from kernel.capabilities.retrieval.pool import (
    coverage,
    coverage_note,
    merge_pool,
    pool_note,
)
from kernel.capabilities.retrieval.repository import search_repo_text
from kernel.capabilities.retrieval.rerank import rerank
from kernel.capabilities.retrieval.terms import build_query_terms
from kernel.capabilities.retrieval.versioning import resolve_source_version
from kernel.config import RetrievalConfig, SourceConfig
from kernel.contracts import schema_ids
from kernel.contracts.capability import CapabilityResult, Usage
from kernel.contracts.enums import ResultStatus
from kernel.contracts.evidence import (
    Evidence,
    EvidenceBundlePayload,
    EvidenceNeed,
    UnavailableSource,
)
from kernel.contracts.payloads import RetrievalRequestPayload
from kernel.contracts.schema_catalog import PayloadValidationError, validate_payload
from kernel.contracts.work import CapabilityInvocation

logger = logging.getLogger(__name__)

CAPABILITY_ID = "retrieve.repository"
CAPABILITY_VERSION = "1.0.0"
NATIVE_KINDS = ("repo_text", "knowledge_map")


def select_sources(ctx: ExecutionContext, request: RetrievalRequestPayload
                   ) -> tuple[list[SourceConfig], list[UnavailableSource]]:
    """Pick the native sources serving the need; report requested ids that cannot serve it."""
    scope_ids = set(ctx.scope.source_ids)
    asked = set(request.source_ids)
    chosen, unavailable = [], []
    catalog = {s.id: s for s in ctx.config.sources}
    for source in ctx.config.sources:
        eligible = (source.kind in NATIVE_KINDS and request.need.category in source.categories
                    and (not asked or source.id in asked)
                    and (not scope_ids or source.id in scope_ids))
        if eligible:
            chosen.append(source)
    for source_id in sorted(asked):
        declared = catalog.get(source_id)
        if declared is None:
            unavailable.append(UnavailableSource(source_id=source_id, reason="unknown source"))
        elif declared.kind not in NATIVE_KINDS:
            unavailable.append(UnavailableSource(source_id=source_id,
                                                 reason="not a native repository source"))
    return chosen, unavailable


async def _search_one(ctx: ExecutionContext, policy: ReadPolicy, source: SourceConfig,
                      terms: list[str], entities: QueryEntities) -> SearchReport:
    """Search one source inside a `retrieval.<source>` retriever observation."""
    meta = {"source_id": source.id, "strategy": source.kind, "term_count": len(terms)}
    if source.deny_globs:
        policy = replace(policy, deny_globs=(*policy.deny_globs, *source.deny_globs))
    with ctx.tracer.span(f"retrieval.{source.id}", "retriever", ctx.corr, input={"terms": terms},
                         metadata=meta) as span:
        report = await _search_source(ctx, policy, source, terms, entities)
        span.update(output={"files_scanned": report.files_scanned,
                            "candidates": len(report.candidates),
                            "skipped": dict(report.skipped),
                            "unavailable_reason": report.unavailable_reason},
                    level="WARNING" if report.unavailable_reason else None)
    return report


async def _search_source(ctx: ExecutionContext, policy: ReadPolicy, source: SourceConfig,
                         terms: list[str], entities: QueryEntities) -> SearchReport:
    """Search one source in a worker thread; unreachable sources become unavailable reports."""
    cfg = ctx.config.retrieval
    if source.kind == "knowledge_map":
        timeout = ctx.config.limits.capability_timeout_seconds
        try:
            return await asyncio.wait_for(asyncio.to_thread(
                search_knowledge_map, policy, source, terms, cfg), timeout)
        except TimeoutError:
            report = SearchReport(source_id=source.id)
            report.unavailable_reason = f"knowledge map timed out after {timeout}s"
            return report
    resolved = policy.resolve_roots(source.roots)
    if not resolved.roots:
        report = SearchReport(source_id=source.id)
        report.unavailable_reason = "; ".join(resolved.rejected) or "no readable roots"
        return report
    report = await asyncio.to_thread(search_repo_text, policy, source.id, list(resolved.roots),
                                     terms, cfg, entities, (ctx.scope.workspace_id,))
    report.notes += [f"root not searched: {r}" for r in resolved.rejected]
    return report


def _locator_sources(ctx: ExecutionContext, request: RetrievalRequestPayload
                     ) -> list[SourceConfig]:
    """Return the repo_text sources an explicit locator may fall under (any category).

    The request's `source_ids` and the scope's `source_ids` narrow the set, as for a search.
    """
    scope_ids, asked = set(ctx.scope.source_ids), set(request.source_ids)
    return [s for s in ctx.config.sources
            if s.kind == "repo_text" and (not asked or s.id in asked)
            and (not scope_ids or s.id in scope_ids)]


def _limitations(reports: list[SearchReport], need: EvidenceNeed) -> list[str]:
    """Describe what each consulted source did, including skips and empty searches."""
    out: list[str] = []
    for r in reports:
        if r.unavailable_reason:
            continue
        out += [f"{r.source_id}: {n}" for n in r.notes]
        out += [f"{r.source_id}: {count} item(s) skipped ({why})"
                for why, count in sorted(r.skipped.items())]
        if not r.candidates:
            out.append(f"{r.source_id}: searched {r.files_scanned} item(s) for "
                       f"{need.category.value}, no term match")
    return out


async def _collect(ctx: ExecutionContext, invocation: CapabilityInvocation,
                   request: RetrievalRequestPayload, reports: list[SearchReport],
                   terms: list[str], explicit: list[Candidate]
                   ) -> tuple[list[Evidence], list[str], bool, list[Usage]]:
    """Rerank the merged candidates and build evidence.

    Returns:
        tuple: (evidence, limitations, cut, usage) where `cut` is True if results were truncated.
    """
    cfg = ctx.config.retrieval
    top_k = min(cfg.top_k, request.limits.top_k or cfg.top_k)
    candidates = merge_pool(reports, cfg, explicit)
    cited = {x.split("#")[0].split("::")[0] for x in request.explicit_locators}
    goal = request.query_hints[0] if request.query_hints else None
    outcome = await rerank(ctx, invocation, request.need, candidates, top_k, goal=goal,
                           cited=cited)
    version = await asyncio.to_thread(resolve_source_version, ctx.run_id, ctx.scope)
    limits = [*pool_note(reports, explicit, candidates, cfg), *outcome.limitations]
    if version is None:
        limits.append("source revision unavailable (git not usable)")
    remaining = request.limits.max_chars
    evidence: dict[str, Evidence] = {}
    cut = len(candidates) > len(outcome.kept) + outcome.dropped_irrelevant
    for ranked in outcome.kept:
        item = build_evidence(ranked, request, request.need.category, version, invocation.id,
                              ctx.clock(), remaining, terms)
        if item is None:
            cut = True
            continue
        evidence.setdefault(item.id, item)
        if remaining is not None:
            remaining -= len(item.excerpt or "")
    ordered = list(evidence.values())
    return ordered, limits, cut or any(e.truncated for e in ordered), outcome.usage


def _result(invocation: CapabilityInvocation, request: RetrievalRequestPayload,
            evidence: list[Evidence], reports: list[SearchReport],
            unavailable: list[UnavailableSource], limitations: list[str], cut: bool,
            usage: list[Usage], cfg: RetrievalConfig, explicit_served: bool = False
            ) -> CapabilityResult:
    """Assemble the evidence bundle result (partial when no source could be consulted)."""
    consulted = [r for r in reports if not r.unavailable_reason]
    unavailable = unavailable + [UnavailableSource(source_id=r.source_id,
                                                   reason=r.unavailable_reason)
                                 for r in reports if r.unavailable_reason]
    served = len(consulted) + (1 if explicit_served else 0)
    status = coverage(evidence, served, unavailable, cfg)
    limits = [*limitations, *_limitations(reports, request.need)]
    if note := coverage_note(evidence, status, cfg):
        limits.append(note)
    limits += [f"source {u.source_id} unavailable: {u.reason}" for u in unavailable]
    bundle = EvidenceBundlePayload(
        evidence_ids=[e.id for e in evidence], coverage={request.need.id: status},
        attempted_sources=[r.source_id for r in reports], unavailable_sources=unavailable,
        limitations=limits, truncated=cut, evidence=evidence)
    result_status = ResultStatus.COMPLETED if served else ResultStatus.PARTIAL
    return CapabilityResult(
        invocation_id=invocation.id, work_item_id=invocation.work_item_id,
        status=result_status, output_schema_id=schema_ids.EVIDENCE_BUNDLE,
        output_payload=bundle.model_dump(mode="json"), evidence=evidence, usage=usage,
        limitations=limits if result_status is ResultStatus.PARTIAL else [],
        diagnostics={"sources_consulted": len(consulted), "sources_unavailable": len(unavailable),
                     "evidence_count": len(evidence)})


class RepositoryRetrievalExecutor:
    """CapabilityExecutor for `retrieve.repository` (read-only)."""

    async def ainvoke(self, invocation: CapabilityInvocation, ctx: ExecutionContext
                      ) -> CapabilityResult:
        """Search the selected sources and return an evidence bundle (never mutates anything)."""
        try:
            request = validate_payload(invocation.input_payload_schema, invocation.input_payload)
        except PayloadValidationError as exc:
            return failed_result(invocation, "invalid_request", str(exc))
        if not isinstance(request, RetrievalRequestPayload):
            return failed_result(invocation, "invalid_request",
                                 "retrieval needs retrieval_request.v1")
        if ctx.cancelled():
            return blocked_result(invocation, "cancelled", "run cancelled")
        return await self._retrieve(invocation, ctx, request)

    async def _retrieve(self, invocation: CapabilityInvocation, ctx: ExecutionContext,
                        request: RetrievalRequestPayload) -> CapabilityResult:
        """Run the strategies, rerank and assemble the bundle."""
        policy = ReadPolicy(
            root=Path(ctx.scope.repository_root), read_roots=tuple(ctx.scope.read_roots),
            deny_globs=tuple(ctx.config.retrieval.deny_globs),
            max_file_bytes=ctx.config.retrieval.max_file_bytes)
        terms = build_query_terms(request.need.question, request.query_hints,
                                  ctx.scope.technologies, ctx.config.retrieval.max_query_terms)
        entities = extract_entities(" ".join(request.query_hints or [request.need.question]))
        sources, unavailable = select_sources(ctx, request)
        cfg = ctx.config.retrieval
        if not terms and not request.explicit_locators:
            return _result(invocation, request, [], [], unavailable,
                           ["no query terms could be extracted from the need"], False, [], cfg)
        explicit = await asyncio.to_thread(
            fetch_explicit, policy, _locator_sources(ctx, request), request.explicit_locators,
            terms, ctx.config.retrieval)
        searched = sources if terms else []
        reports = list(await asyncio.gather(*(_search_one(ctx, policy, s, terms, entities)
                                              for s in searched)))
        try:
            evidence, limits, cut, usage = await _collect(
                ctx, invocation, request, reports, terms, explicit.candidates)
        except StopCapability as stop:
            return stop.result
        return _result(invocation, request, evidence, reports, unavailable,
                       [*explicit.notes, *limits], cut, usage, cfg, bool(explicit.candidates))


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Pooling, rerank batching and coverage moved to pool.py/rerank.py:
#   one rerank batch per need, explicit locators unjudged, a need satisfied only by enough
#   evidence above the bar, and every cut reported (the pool cap and the batch cap).
#   (#KernelV01/E)
# - 2026-10-01 [python-coder]: Query terms come from build_query_terms (request.query_hints
#   first, then the need's wording, bounded by retrieval.max_query_terms) and the named
#   identifiers are read from the hints too. (#KernelV01/D)
# - 2026-10-01 [python-coder]: Explicit locators are fetched first and merged ahead of the search
#   candidates; the search also gets the question's identifiers so named files are pinned, and
#   `max_candidates` is the overall rerank batch bound (default raised 20 to 60) while each
#   source's own cap scales with its size. (#KernelV01/B)
# - 2026-10-02 [python-coder]: mypy: the requested-source loop variable no longer reuses the catalog loop's name (#KernelBootstrapV0/GROUND)
# - 2026-10-01 23:00 [python-coder]: Candidates are merged round-robin across sources instead of
#   by raw hit count: with the project-metadata sources the 4468-file acceptance-criteria store
#   crowded tests/README.md out of the bounded list in a live run. (#KernelBootstrapV0/GROUND)
# - 2026-10-01 23:00 [python-coder]: A need is `satisfied` only by evidence whose judged relevance
#   reaches retrieval.coverage_relevance_threshold; a weaker or unjudged hit stays in the bundle
#   as context but leaves the need `partial`, so one irrelevant excerpt cannot close a need.
#   Per-source deny globs extend the global ones. (#KernelBootstrapV0/GROUND)
# - 2026-10-01 00:30 [python-coder]: Each source search is a `retrieval.<source>` retriever span
#   under the capability span (design observation map); output carries counts only, never
#   excerpts. (#KernelBootstrapV0/OBS)
# - 2026-09-30 23:00 [python-coder]: A need whose sources are all unreachable yields a partial
#   bundle with coverage `unavailable` (not failed, not empty) so research can report the
#   unavailable sources. (#KernelBootstrapV0/P5)
# ====================================================================
