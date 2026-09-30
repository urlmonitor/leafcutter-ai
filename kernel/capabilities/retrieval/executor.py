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
from pathlib import Path

from kernel.capabilities.base import ExecutionContext
from kernel.capabilities.decision.jev_support import (
    StopCapability,
    blocked_result,
    failed_result,
)
from kernel.capabilities.retrieval.access import ReadPolicy
from kernel.capabilities.retrieval.candidates import Candidate, SearchReport
from kernel.capabilities.retrieval.evidence_build import build_evidence
from kernel.capabilities.retrieval.knowledge_map import search_knowledge_map
from kernel.capabilities.retrieval.repository import search_repo_text
from kernel.capabilities.retrieval.rerank import rerank
from kernel.capabilities.retrieval.terms import extract_terms
from kernel.capabilities.retrieval.versioning import resolve_source_version
from kernel.config import SourceConfig
from kernel.contracts import schema_ids
from kernel.contracts.capability import CapabilityResult, Usage
from kernel.contracts.enums import NeedStatus, ResultStatus
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
        source = catalog.get(source_id)
        if source is None:
            unavailable.append(UnavailableSource(source_id=source_id, reason="unknown source"))
        elif source.kind not in NATIVE_KINDS:
            unavailable.append(UnavailableSource(source_id=source_id,
                                                 reason="not a native repository source"))
    return chosen, unavailable


async def _search_one(ctx: ExecutionContext, policy: ReadPolicy, source: SourceConfig,
                      terms: list[str]) -> SearchReport:
    """Search one source inside a `retrieval.<source>` retriever observation."""
    meta = {"source_id": source.id, "strategy": source.kind, "term_count": len(terms)}
    with ctx.tracer.span(f"retrieval.{source.id}", "retriever", ctx.corr, input={"terms": terms},
                         metadata=meta) as span:
        report = await _search_source(ctx, policy, source, terms)
        span.update(output={"files_scanned": report.files_scanned,
                            "candidates": len(report.candidates),
                            "skipped": dict(report.skipped),
                            "unavailable_reason": report.unavailable_reason},
                    level="WARNING" if report.unavailable_reason else None)
    return report


async def _search_source(ctx: ExecutionContext, policy: ReadPolicy, source: SourceConfig,
                         terms: list[str]) -> SearchReport:
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
                                     terms, cfg)
    report.notes += [f"root not searched: {r}" for r in resolved.rejected]
    return report


def _merge(reports: list[SearchReport], limit: int) -> list[Candidate]:
    """Merge candidates across sources, dropping duplicate locators, best hits first."""
    seen: dict[str, Candidate] = {}
    for report in reports:
        for cand in report.candidates:
            seen.setdefault(cand.locator, cand)
    return sorted(seen.values(), key=lambda c: (-c.hits, c.path, c.locator))[:limit]


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


def _coverage(need: EvidenceNeed, evidence: list[Evidence], consulted: int,
              unavailable: list[UnavailableSource]) -> NeedStatus:
    """Return the need status: unavailable, open (searched, nothing), partial or satisfied."""
    if consulted == 0:
        return NeedStatus.UNAVAILABLE
    if not evidence:
        return NeedStatus.OPEN
    return NeedStatus.PARTIAL if unavailable else NeedStatus.SATISFIED


async def _collect(ctx: ExecutionContext, invocation: CapabilityInvocation,
                   request: RetrievalRequestPayload, reports: list[SearchReport],
                   terms: list[str]) -> tuple[list[Evidence], list[str], bool, list[Usage]]:
    """Rerank the merged candidates and build evidence.

    Returns:
        tuple: (evidence, limitations, cut, usage) where `cut` is True if results were truncated.
    """
    cfg = ctx.config.retrieval
    top_k = min(cfg.top_k, request.limits.top_k or cfg.top_k)
    candidates = _merge(reports, cfg.max_candidates)
    outcome = await rerank(ctx, invocation, request.need, candidates, top_k)
    version = await asyncio.to_thread(resolve_source_version, ctx.run_id, ctx.scope)
    limits = list(outcome.limitations)
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
            usage: list[Usage]) -> CapabilityResult:
    """Assemble the evidence bundle result (partial when no source could be consulted)."""
    consulted = [r for r in reports if not r.unavailable_reason]
    unavailable = unavailable + [UnavailableSource(source_id=r.source_id,
                                                   reason=r.unavailable_reason)
                                 for r in reports if r.unavailable_reason]
    status = _coverage(request.need, evidence, len(consulted), unavailable)
    limits = [*limitations, *_limitations(reports, request.need)]
    limits += [f"source {u.source_id} unavailable: {u.reason}" for u in unavailable]
    bundle = EvidenceBundlePayload(
        evidence_ids=[e.id for e in evidence], coverage={request.need.id: status},
        attempted_sources=[r.source_id for r in reports], unavailable_sources=unavailable,
        limitations=limits, truncated=cut, evidence=evidence)
    result_status = ResultStatus.COMPLETED if consulted else ResultStatus.PARTIAL
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
        terms = extract_terms(request.need.question, ctx.scope.technologies)
        sources, unavailable = select_sources(ctx, request)
        if not terms:
            return _result(invocation, request, [], [], unavailable,
                           ["no query terms could be extracted from the need"], False, [])
        reports = list(await asyncio.gather(*(_search_one(ctx, policy, s, terms)
                                              for s in sources)))
        try:
            evidence, limits, cut, usage = await _collect(ctx, invocation, request, reports,
                                                          terms)
        except StopCapability as stop:
            return stop.result
        return _result(invocation, request, evidence, reports, unavailable, limits, cut, usage)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 00:30 [python-coder]: Each source search is a `retrieval.<source>` retriever span
#   under the capability span (design observation map); output carries counts only, never
#   excerpts. (#KernelBootstrapV0/OBS)
# - 2026-09-30 23:00 [python-coder]: A need whose sources are all unreachable yields a partial
#   bundle with coverage `unavailable` (not failed, not empty) so research can report the
#   unavailable sources. (#KernelBootstrapV0/P5)
# ====================================================================
