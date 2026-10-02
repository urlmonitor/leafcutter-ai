"""
MODULE: kernel.memory.staging
GOAL: Stage the record of a decision a human approved, with full provenance (run, trace,
    repository revision, versions), through the ColonyMemory port into the run's own artifacts.
BUSINESS CONTEXT: Approved decisions become reviewable records (ADR-059) but the kernel never
    writes the repository during a run (ADR-060): this is the whole of the kernel's side. A record
    is staged only for a resolved decision a human approved; a decision approved by anything else,
    or not approved, leaves nothing behind. Publishing is a separate, explicit command.
ARCHITECTURE: One function over the execution context and plain decision data (no decision-graph
    internals). The builder is the self-authorization gate; a refusal or a record the model
    rejects is logged and returns None, because filing a record must never fail a decision.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

import kernel
from kernel.contracts.decision import Criterion, Decision, Option, OptionRanking
from kernel.contracts.evidence import Evidence
from kernel.memory.builder import (
    RecordExtras,
    RecordFilters,
    build_decision_record,
    utc_timestamp,
)
from kernel.memory.models import PrecedentNote, RecordProvenance, SourceRevision, TaskContext
from kernel.memory.port import StagedRecord
from kernel.memory.precedent import phases_from_constraints
from kernel.observability.correlation import deterministic_trace_id

if TYPE_CHECKING:
    from kernel.capabilities.base import ExecutionContext

logger = logging.getLogger(__name__)


def record_provenance(ctx: ExecutionContext, decision: Decision) -> RecordProvenance:
    """Return the provenance of a record made now by this run (concept section 12)."""
    revision = ctx.scope.revision
    return RecordProvenance(
        created_at=utc_timestamp(ctx.clock()), run_id=ctx.run_id,
        root_task_id=ctx.corr.root_task_id, langfuse_trace_id=deterministic_trace_id(ctx.run_id),
        repository_revision=SourceRevision(commit=revision.commit, dirty=revision.dirty)
        if revision else SourceRevision(),
        template_version=decision.versions.get("templates"), model_version=ctx.config.jev.model,
        kernel_version=kernel.__version__, decision_versions=dict(decision.versions))


def stage_decision_record(
        ctx: ExecutionContext, decision: Decision, *, options: Sequence[Option],
        criteria: Sequence[Criterion], evidence: Sequence[Evidence],
        ranking: Sequence[OptionRanking] = (), precedents: Sequence[PrecedentNote] = (),
        basis: str = "resolved_gate", criterion_evidence: Mapping[str, Sequence[str]] | None = None,
        supersedes: Sequence[str] = (), related: Sequence[str] = ()) -> StagedRecord | None:
    """Stage the record of a resolved, human-approved decision; None when nothing is staged.

    Args:
        ctx: Execution context (memory port, scope, config, clock, run identity).
        decision: The resolved decision (approver and approval time set by a human answer).
        options: The decision's options; criteria: its criteria; evidence: items it rests on.
        ranking: The kernel ranking the human saw (design decisions).
        precedents: What was decided about each earlier decision that was considered.
        basis: How it was assessed (`kernel_ranking`, `resolved_gate` or `precedent_reuse`).
        criterion_evidence: Evidence ids relevant to each criterion.
        supersedes: Earlier decisions this one replaces; related: ones it cites.

    Returns:
        StagedRecord | None: Where the record was staged, or None when the decision was not
            human-approved, the record was invalid, or the memory backend keeps nothing.
    """
    scope = ctx.scope
    extras = RecordExtras(
        task_context=TaskContext(goal=decision.question, component_ids=list(scope.component_ids),
                                 technologies=list(scope.technologies),
                                 constraints=list(ctx.constraints)),
        filters=RecordFilters(components=list(scope.component_ids),
                              roadmap_phase=phases_from_constraints(ctx.constraints)),
        ranking=ranking, basis=basis, criterion_evidence=criterion_evidence or {},
        precedents=precedents, supersedes=supersedes, related=related)
    try:
        record = build_decision_record(
            decision, options, criteria, evidence, record_provenance(ctx, decision),
            repository_id=ctx.config.memory.repository_id or scope.workspace_id, extras=extras)
    except ValueError as exc:  # NotApproved, or a record the model refuses (ADR-060)
        logger.info("decision %s was not staged as a record: %s", decision.id, exc)
        return None
    return ctx.memory.stage_decision(record)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: A refusal or an invalid record is logged at info/warning and
#   returns None: staging is a by-product of resolving, so it can never fail the decision, and
#   the builder (not this function) decides what counts as human-approved. (#KernelDecisionStore)
# ====================================================================
