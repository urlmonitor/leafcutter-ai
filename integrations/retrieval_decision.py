"""
MODULE: retrieval_decision
GOAL: Kernel-owned retrieval choice; backend capabilities constrain every option.
BUSINESS CONTEXT: Keep optional knowledge retrieval bounded and traceable.
ARCHITECTURE: Adapter between neutral knowledge transport and existing kernel contracts.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Any
    from kernel.capabilities.base import ExecutionContext
    from kernel.contracts.capability import Usage
    from kernel.contracts.work import CapabilityInvocation


from dataclasses import dataclass, field

from kernel.capabilities.decision.jev_support import ask_jev, choice_question, make_batch
from kernel.providers.base import JevInvalidResponse


@dataclass(frozen=True)
class RetrievalChoice:
    """Serializable decision summary, not a new persisted domain Decision."""

    retrieve: bool
    mode: str
    operation: str
    reason: str
    arguments: dict = field(default_factory=dict)
    allowed_fallback: str | None = None
    disclosure_level: int = 0
    ambiguous: bool = False


def choose_retrieval_mode(
    *,
    known_ids: Sequence[str],
    intent: str,
    capabilities: dict[str, Any],
    evidence_sufficient: bool = False,
    component_ids: Sequence[str] = (),
) -> RetrievalChoice:
    """Choose an obvious recipe without a model call, or mark semantic ambiguity.

    Returns:
        RetrievalChoice: Validated result of the documented operation.
    """
    if evidence_sufficient:
        return RetrievalChoice(False, "exact", "get_entities", "existing evidence is sufficient")
    if not capabilities.get("graph"):
        return RetrievalChoice(False, "exact", "get_entities", "knowledge capability unavailable")
    words = intent.casefold()
    if known_ids:
        if any(word in words for word in ("test", "verify", "coverage")):
            return RetrievalChoice(
                True,
                "graph",
                "get_related_tests",
                "known entity test relationship",
                {"entity_ids": list(known_ids)},
            )
        return RetrievalChoice(
            True,
            "exact",
            "get_entities",
            "canonical IDs are known",
            {"entity_ids": list(known_ids)},
        )
    if component_ids:
        operation = "get_component_context"
        for marker, candidate in (
            ("criteria", "get_acceptance_criteria"),
            ("requirement", "get_acceptance_criteria"),
            ("adr", "get_relevant_adrs"),
        ):
            if marker in words:
                operation = candidate
                break
        return RetrievalChoice(
            True,
            "graph",
            operation,
            "known component relationship",
            {"component_id": component_ids[0]},
        )
    if capabilities.get("semantic") or capabilities.get("hybrid"):
        precedent = any(
            word in words for word in ("precedent", "previous", "mistake", "correction")
        )
        mode = "hybrid" if precedent and capabilities.get("hybrid") else "semantic"
        return RetrievalChoice(
            True,
            mode,
            "find_similar_decisions",
            "semantic intent needs assessment",
            {"query_text": intent},
            ambiguous=True,
        )
    return RetrievalChoice(False, "graph", "get_entities", "no supported operation for unknown IDs")


async def assess_retrieval_mode(
    ctx: ExecutionContext,
    invocation: CapabilityInvocation,
    *,
    known_ids: Sequence[str],
    intent: str,
    capabilities: dict[str, Any],
    evidence_sufficient: bool = False,
) -> tuple[RetrievalChoice, list[Usage]]:
    """Ask Jev only when multiple supported semantic modes need judgment.

    Args:
        ctx: Trusted execution scope, budgets and telemetry owner.
        invocation: Existing registered capability invocation.

    Returns:
        tuple[RetrievalChoice, list[Usage]]: Validated result of the documented operation.
    """
    selected = choose_retrieval_mode(
        known_ids=known_ids,
        intent=intent,
        capabilities=capabilities,
        evidence_sufficient=evidence_sufficient,
        component_ids=ctx.scope.component_ids,
    )
    if not selected.ambiguous:
        return selected, []
    options = {"skip": "Existing evidence is sufficient; do not retrieve."}
    if capabilities.get("semantic"):
        options["semantic"] = "Find similar reviewed decisions; candidate summaries suffice."
    if capabilities.get("hybrid"):
        options["hybrid"] = (
            "Find similar decisions and inspect their correction, lesson and evidence links."
        )
    batch = make_batch(
        ctx,
        "knowledge.retrieval_mode",
        {"intent": intent[:4000]},
        [
            choice_question(
                "knowledge.mode",
                "knowledge.retrieval_mode.v1",
                "Select the supported evidence retrieval mode; similarity is not truth.",
                options,
            )
        ],
    )
    reply = await ask_jev(ctx, invocation, batch)
    answer = reply.choice("knowledge.mode")
    if answer.choice not in options:
        raise JevInvalidResponse("retrieval mode was not an offered choice")
    threshold = ctx.config.routing.min_selected_probability
    confidence = ctx.config.routing.min_confidence
    if (
        answer.probabilities.get(answer.choice, 0) < threshold
        or answer.confidence is None
        or answer.confidence < confidence
    ):
        return RetrievalChoice(
            False, selected.mode, selected.operation, "retrieval mode assessment is uncertain"
        ), [reply.usage]
    if answer.choice == "skip":
        return RetrievalChoice(
            False, selected.mode, selected.operation, "Jev judged existing evidence sufficient"
        ), [reply.usage]
    return RetrievalChoice(
        True,
        answer.choice,
        selected.operation,
        "Jev selected a supported retrieval mode",
        selected.arguments,
    ), [reply.usage]


# DECISION HISTORY
# ================================================================================
# - 2026-10-01 20:00 [python-coder]: Preserve canonical evidence and optional bounded retrieval. (#TICKET-20261001-KM-400e-3)
