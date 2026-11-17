"""MODULE: kernel.entity_context
GOAL: Recognize permitted repository references without pre-intent evidence retrieval.
BUSINESS CONTEXT: Meanings explain requests while preserving goals and authorization.
ARCHITECTURE: Read prepared index, scan original channels, resolve bounded identities,
    redact metadata, and budget a compact projection. No model, network or source search.
"""

from __future__ import annotations

import time
from typing import Any

from kernel.config import KernelConfig
from kernel.contracts import RegistrySnapshot, TaskInput
from kernel.contracts.base import canonical_json, content_hash
from kernel.contracts.context import CallerContext
from kernel.contracts.entity_context import (
    EntityBudgets, EntityCard, EntityContext, EntityCounts, EntityCoverage, EntityProvenance,
    UnresolvedEntity,
)
from kernel.entity_index_read import read_index
from kernel.entity_matching import Candidate, scan_candidates
from kernel.entity_projection import entity_context_payload
from kernel.entity_records import IndexEntry, bounded_meaning
from kernel.observability.redaction import Redactor


def _caller(task: TaskInput, config: KernelConfig, redact: Redactor
             ) -> tuple[CallerContext, list[tuple], list[str]]:
    """Budget newest supplied claims while preserving their original record indices."""
    remaining, channels, notes = config.entity_context.max_caller_chars, [], []
    retained = remaining
    kept: dict = {"host": None, "conversation": [], "observations": [], "capabilities": []}
    for key in ("conversation", "observations", "capabilities"):
        values = getattr(task.context, key)
        selected = []
        indices = range(len(values) - 1, -1, -1) if key == "conversation" else range(len(values))
        for index in indices:
            raw = values[index][:remaining]
            masked = redact.mask_text(raw)[:min(retained, 4000)]
            if len(raw) < len(values[index]) or masked != raw:
                notes.append("caller context bounded or redacted")
            if raw:
                channels.append((key, index, raw))
                selected.append((index, masked))
                remaining -= len(raw)
                retained -= len(masked)
        kept[key] = [text for _, text in sorted(selected) if text]
    if task.context.host:
        kept["host"] = redact.mask_text(task.context.host[:remaining])[:min(retained, 256)] or None
    return CallerContext(**kept), channels, list(dict.fromkeys(notes))


def _card(entry: IndexEntry, candidate: Candidate, snapshot: str, redact: Redactor,
          limit: int, ambiguous: bool) -> EntityCard:
    """Redact every metadata string before hashing the exact retained meaning projection."""
    values: dict[str, Any] = {"family": entry.family, "identity": redact.mask_text(entry.identity),
              "native_kind": entry.native_kind, "meaning": bounded_meaning(redact.mask_text(entry.meaning), limit),
              "signature": redact.mask_text(entry.signature)[:limit] if entry.signature else None,
              "resolution": "ambiguous" if ambiguous else "resolved"}
    matches = [m.model_copy(update={"surface": redact.mask_text(m.surface)}) for m in candidate.matches]
    provenance = EntityProvenance(source_id=redact.mask_text(entry.source_id),
        locator=redact.mask_text(entry.locator), snapshot=snapshot,
        source_hash=entry.source_hash, projection_hash=content_hash(canonical_json(values)))
    return EntityCard(**values, matches=matches, provenance=provenance)


def _resolve(candidates: list[Candidate], context: EntityContext, config: KernelConfig,
              redact: Redactor, deadline: float) -> EntityContext:
    """Resolve distinct candidates by explicit-reference priority and fixed work bounds."""
    cfg = config.entity_context
    cards: list[EntityCard] = []
    unresolved: list[UnresolvedEntity] = []
    seen_resolved: set[tuple] = set()
    counts = {name: 0 for name in EntityCounts.model_fields if name != "schema_version"}
    counts["detected"] = len(candidates)
    family_counts: dict[str, dict] = {}
    for candidate in candidates:
        family_counts.setdefault(candidate.family, dict.fromkeys(counts, 0))["detected"] += 1
    lookups = 0
    notes = list(context.limitations)
    for position, candidate in enumerate(candidates):
        if lookups >= cfg.max_lookups or time.monotonic() >= deadline:
            counts["omitted"] += len(candidates) - position
            for missing in candidates[position:]:
                family_counts[missing.family]["omitted"] += 1
            notes.append("candidate lookup budget or deadline exhausted")
            break
        lookups += 1
        own = family_counts[candidate.family]
        entries = sorted(candidate.entries, key=lambda e: (e.identity, e.native_kind or ""))
        ambiguous = len(entries) > 1
        counts["ambiguous"] += int(ambiguous)
        own["ambiguous"] += int(ambiguous)
        new = set(map(_identity_key, entries)) - seen_resolved
        counts["resolved"] += len(new)
        own["resolved"] += len(new)
        seen_resolved.update(new)
        selected = entries[:cfg.max_ambiguity_candidates] if ambiguous else entries
        prior_count = len(cards)
        admitted = _admit(selected, candidate, cards, context, config, redact, ambiguous)
        own["returned"] += len(cards) - prior_count
        omitted = len(entries) - len(admitted)
        counts["omitted"] += omitted
        own["omitted"] += omitted
        if ambiguous or candidate.state:
            if len(unresolved) < cfg.max_unknowns:
                unresolved.append(UnresolvedEntity.model_validate({"family": candidate.family,
                    "reference": redact.mask_text(candidate.reference)[:cfg.max_unknown_chars],
                    "state": "ambiguous" if ambiguous else candidate.state,
                    "matches": [m.model_copy(update={"surface": redact.mask_text(m.surface)}) for m in candidate.matches],
                    "candidates": [redact.mask_text(e.identity) for e in admitted]}))
                counts["unknown"] += int(not ambiguous)
                own["unknown"] += int(not ambiguous)
            else:
                counts["omitted"] += 1
                own["omitted"] += 1
    counts["returned"] = len(cards)
    if counts["omitted"]:
        notes.append("candidate or identity output budget omitted references")
    coverage = context.coverage.model_copy(update={"counts": EntityCounts.model_validate(counts),
        "by_family": {key: EntityCounts.model_validate(value) for key, value in family_counts.items()}})
    return context.model_copy(update={"entities": cards, "unresolved": unresolved, "coverage": coverage,
        "limitations": list(dict.fromkeys(notes)), "budgets": EntityBudgets(lookups=lookups)})


def _admit(entries: list[IndexEntry], candidate: Candidate, cards: list[EntityCard],
           context: EntityContext, config: KernelConfig, redact: Redactor,
           ambiguous: bool) -> list[IndexEntry]:
    """Merge one card per typed identity even when qualified and short mentions overlap."""
    admitted = []
    cfg = config.entity_context
    for entry in entries:
        key = (entry.family, entry.native_kind, entry.identity)
        existing = next((i for i, c in enumerate(cards)
                         if (c.family, c.native_kind, c.identity) == key), None)
        if existing is not None:
            prior = cards[existing]
            merged = list(prior.matches)
            redacted = [m.model_copy(update={"surface": redact.mask_text(m.surface)}) for m in candidate.matches]
            merged.extend(m for m in redacted if m not in merged)
            cards[existing] = prior.model_copy(update={"matches": merged,
                "resolution": "resolved" if not ambiguous or prior.resolution == "resolved" else "ambiguous"})
            admitted.append(entry)
        elif len(cards) < cfg.max_entities:
            cards.append(_card(entry, candidate, context.coverage.index_fingerprint or "", redact,
                               cfg.max_meaning_chars, ambiguous))
            admitted.append(entry)
    return admitted


def _identity_key(entry: IndexEntry) -> tuple:
    """Typed owner identity is the deduplication key across mention forms."""
    return entry.family, entry.native_kind, entry.identity


def _fit(context: EntityContext, maximum: int) -> EntityContext:
    """Bound compact meanings while retaining every checkpoint mention of kept identities."""
    result = context
    while True:
        # serialized_chars itself changes serialization length: converge its decimal width.
        for _ in range(4):
            length = len(canonical_json(entity_context_payload(result)))
            result = result.model_copy(update={"budgets": result.budgets.model_copy(update={"serialized_chars": length})})
        if length <= maximum:
            return result
        cards, unresolved = list(result.entities), list(result.unresolved)
        if cards:
            removed = cards.pop()
            unresolved = [u.model_copy(update={"candidates": [c for c in u.candidates if c != removed.identity]})
                          for u in unresolved]
        elif unresolved:
            unresolved.pop()
        else:
            coverage = result.coverage.model_copy(update={"by_family": {}})
            result = result.model_copy(update={"coverage": coverage,
                "limitations": ["entity projection metadata exceeds configured budget"], "status": "partial"})
            # A valid config always reserves enough for the minimal meaning envelope.
            continue
        counts = result.coverage.counts.model_copy(update={"returned": len(cards),
            "omitted": result.coverage.counts.omitted + 1})
        family_counts = dict(result.coverage.by_family)
        if result.entities:
            prior = family_counts[removed.family]
            family_counts[removed.family] = prior.model_copy(update={
                "returned": max(0, prior.returned - 1), "omitted": prior.omitted + 1})
        result = result.model_copy(update={"entities": cards, "unresolved": unresolved,
            "coverage": result.coverage.model_copy(update={"counts": counts, "by_family": family_counts}), "status": "partial",
            "limitations": list(dict.fromkeys([*result.limitations, "entity serialization budget omitted references"]))})


def recognize_entities(task_input: TaskInput, config: KernelConfig,
                       registry: RegistrySnapshot | None = None, *, redactor: Redactor | None = None
                       ) -> EntityContext:
    """Return one local interpretation snapshot; recognition performs no external work."""
    started = time.monotonic()
    cfg = config.entity_context
    deadline = started + cfg.max_seconds
    redact = redactor or Redactor({}, config.data_policy, config.retrieval.deny_globs)
    caller, channels, notes = _caller(task_input, config, redact)
    context = EntityContext(original_goal=task_input.goal, caller_context=caller,
        workspace_id=task_input.scope.workspace_id, repository_root=task_input.scope.repository_root,
        registered_capabilities=sorted(c.id for c in registry.descriptors) if registry else [],
        status="unavailable", limitations=notes)
    if not cfg.enabled:
        context = context.model_copy(update={"status": "disabled", "limitations": [*notes, "entity recognition disabled"],
            "coverage": EntityCoverage(index_status="disabled")})
    elif "read_repo" not in task_input.permissions:
        context = context.model_copy(update={"limitations": [*notes, "entity recognition requires read_repo permission"]})
    elif time.monotonic() >= deadline:
        context = context.model_copy(update={"status": "partial", "limitations": [*notes, "recognition deadline exhausted"]})
    else:
        view = read_index(task_input.scope, config, deadline)
        coverage = EntityCoverage(index_status=view.status, index_fingerprint=view.fingerprint,
                                  families=view.coverage)
        context = context.model_copy(update={"coverage": coverage, "limitations": [*notes, *view.limitations]})
        if view.status == "current":
            candidates, complete = scan_candidates([("goal", None, task_input.goal), *channels],
                                                    view.entries, view.patterns, deadline)
            context = context.model_copy(update={"coverage": coverage.model_copy(update={"scan_complete": complete})})
            context = _resolve(candidates, context, config, redact, deadline)
            status = "recognized" if context.entities or context.unresolved else "no_matches"
            if not complete:
                context = context.model_copy(update={"limitations": [*context.limitations, "recognition scan deadline exhausted"]})
            if context.limitations:
                status = "partial"
            context = context.model_copy(update={"status": status})
    elapsed = round(max(0, time.monotonic() - started) * 1000, 3)
    context = context.model_copy(update={"budgets": context.budgets.model_copy(update={"elapsed_ms": elapsed})})
    return _fit(context, cfg.max_serialized_chars)

# DECISION HISTORY
# ================================================================================
# - 2026-10-03 15:05 [python-coder]: Keep pre-intent meanings deterministic, scoped and separate from task evidence. (#TICKETLESS reason=user-approved-ac-first-DK300)
# - 2026-10-03 17:00 [python-coder]: Count original caller characters independently of redacted output so masking cannot admit older context. (#DK-300/entity-context)
