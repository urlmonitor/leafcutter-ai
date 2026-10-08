"""Gather bounded local context before classifying the user's intent.

This deterministic step uses the existing read-only repository search, preserves the
original request, and produces evidence rather than an answer or a user decision.
It requires neither a resolved intent nor a Jev call, so discovery can precede routing.
"""

from __future__ import annotations

import logging
import time

from kernel.capabilities.retrieval.candidates import SearchReport
from kernel.capabilities.retrieval.pool import merge_pool
from kernel.capabilities.retrieval.terms import build_query_terms
from kernel.config import KernelConfig
from kernel.contracts import RegistrySnapshot, TaskInput, content_hash
from kernel.contracts.context import CallerContext, ContextExcerpt, EnrichedContext
from kernel.enrichment_sources import search_source
from kernel.observability.redaction import Redactor

logger = logging.getLogger(__name__)


def _caller_context(task: TaskInput, config: KernelConfig, redact: Redactor
                    ) -> tuple[CallerContext, bool]:
    """Keep supplied claims separate from repository evidence and bound/redact their text."""
    remaining = config.context_enrichment.max_context_chars
    cut = False

    def keep(text: str, field_limit: int = 4000) -> str:
        nonlocal remaining, cut
        masked = redact.mask_text(text)
        retained = masked[:min(remaining, field_limit)]
        cut |= retained != masked
        remaining -= len(retained)
        return retained

    supplied = task.context
    host = keep(supplied.host, 256) if supplied.host is not None else None
    # Recent conversation gets first claim on the budget; retain chronological order.
    conversation = list(reversed([keep(t) for t in reversed(supplied.conversation)]))
    observations = [keep(t) for t in supplied.observations]
    capabilities = [keep(t) for t in supplied.capabilities]
    return CallerContext(host=host, conversation=[t for t in conversation if t],
                         observations=[t for t in observations if t],
                         capabilities=[t for t in capabilities if t]), cut


def _search(task: TaskInput, config: KernelConfig, query: str, terms: list[str],
            deadline: float) -> tuple[list[SearchReport], list[str], bool]:
    """Search only configured and scope-permitted local sources with a shared file budget."""
    cfg = config.context_enrichment
    wanted = cfg.source_ids
    scoped = task.scope.source_ids
    available = {s.id: s for s in config.sources if s.kind == "repo_text"}
    ids = wanted or list(available)
    chosen = [available[i] for i in ids if i in available and (not scoped or i in scoped)]
    notes = [f"context source unavailable: {i}" for i in ids if i not in available]
    truncated = len(chosen) > cfg.max_sources
    if truncated:
        notes.append("context source budget reached")
    chosen = chosen[:cfg.max_sources]
    reports: list[SearchReport] = []
    left = cfg.max_files
    for index, source in enumerate(chosen):
        if left <= 0 or time.monotonic() >= deadline:
            notes.append("context file or time budget reached")
            truncated = True
            break
        allowance = max(1, left // (len(chosen) - index))
        try:
            report, attempted = search_source(task, config, source, query, terms, allowance,
                                              deadline)
        except OSError as exc:
            logger.warning("context retrieval failed for %s: %s", source.id, type(exc).__name__)
            report, attempted = SearchReport(source_id=source.id,
                unavailable_reason=type(exc).__name__), allowance
        left -= attempted
        reports.append(report)
        notes.extend(f"{source.id}: {n}" for n in report.notes)
        if report.unavailable_reason:
            notes.append(f"{source.id}: {report.unavailable_reason}")
        notes.extend(f"{source.id}: {count} skipped ({why})"
                     for why, count in sorted(report.skipped.items()))
        truncated |= any("budget" in n for n in report.notes) or "time_budget" in report.skipped
    return reports, notes, truncated


def _excerpts(reports: list[SearchReport], config: KernelConfig, redact: Redactor
              ) -> tuple[list[ContextExcerpt], bool]:
    """Retain diverse ranked excerpts; hash exactly the redacted text retained locally."""
    cfg = config.context_enrichment
    candidates = merge_pool(reports, config.retrieval)
    evidence: list[ContextExcerpt] = []
    remaining = cfg.max_chars
    truncated = len(candidates) > cfg.max_evidence
    for candidate in candidates[:cfg.max_evidence]:
        if remaining <= 0:
            truncated = True
            break
        masked = redact.mask_text(candidate.excerpt)
        # KernelModel normalises surrounding whitespace; hash that exact retained value.
        excerpt = masked[:min(remaining, cfg.max_excerpt_chars)].strip()
        if not excerpt:
            truncated = True
            continue
        cut = candidate.truncated or len(excerpt) < len(masked)
        truncated |= cut
        evidence.append(ContextExcerpt(
            source_id=candidate.source_id, locator=candidate.locator, excerpt=excerpt,
            content_hash=content_hash(excerpt), truncated=cut))
        remaining -= len(excerpt)
    return evidence, truncated


def gather_context(task_input: TaskInput, config: KernelConfig,
                   registry: RegistrySnapshot | None = None, *, redactor: Redactor | None = None
                   ) -> EnrichedContext:
    """Return the initial context without altering the goal, permissions or user choices.

    Registered capabilities describe configuration, not proven runtime health. Excerpts
    are lexical candidates, not semantically verified answers. Client observations retain
    their caller provenance. Empty or failed searches remain explicit limitations.
    """
    task, cfg = task_input, config.context_enrichment
    redact = redactor or Redactor({}, config.data_policy, config.retrieval.deny_globs)
    caller, cut = _caller_context(task, config, redact)
    result = EnrichedContext(
        original_goal=task.goal, caller_context=caller, workspace_id=task.scope.workspace_id,
        repository_root=task.scope.repository_root, status="no_evidence", truncated=cut,
        registered_capabilities=sorted(c.id for c in registry.descriptors) if registry else [])
    notes = ["caller context truncated to configured budget"] if cut else []
    if not cfg.enabled:
        return result.model_copy(update={"status": "disabled", "limitations": [*notes,
            "context enrichment disabled by configuration"]})
    if "read_repo" not in task.permissions:
        return result.model_copy(update={"status": "unavailable", "limitations": [*notes,
            "context retrieval requires read_repo permission"]})
    hints = [task.goal, *reversed(caller.conversation), *caller.observations, *caller.capabilities]
    query = "\n".join(hints)
    terms = build_query_terms(task.goal, hints, task.scope.technologies,
                              config.retrieval.max_query_terms)
    if not terms:
        return result.model_copy(update={"limitations": [*notes,
            "no searchable terms in request or supplied context"]})
    reports, search_notes, search_cut = _search(task, config, query, terms,
                                               time.monotonic() + cfg.max_seconds)
    evidence, evidence_cut = _excerpts(reports, config, redact)
    notes.extend(search_notes)
    cut |= search_cut or evidence_cut
    if evidence_cut:
        notes.append("context evidence truncated to configured budget")
    if not evidence:
        notes.append("no matching repository context found; missing facts remain unknown")
    unavailable = not reports or all(r.unavailable_reason for r in reports)
    partial = cut or any(r.unavailable_reason or r.skipped for r in reports)
    status = ("unavailable" if unavailable else "partial" if partial else
              "gathered" if evidence else "no_evidence")
    return result.model_copy(update={
        "evidence": evidence, "sources_consulted": [r.source_id for r in reports],
        "files_scanned": sum(r.files_scanned for r in reports), "limitations": notes,
        "truncated": cut, "status": status})
