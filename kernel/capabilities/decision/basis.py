"""
MODULE: kernel.capabilities.decision.basis
GOAL: The deterministic `validate_basis` node: decide, without Jev, whether options and approved
    criteria exist and whether generated proposals still await human approval.
BUSINESS CONTEXT: Jev decides against known decision knowledge; it never invents options or
    criteria (ADR-053 section 2). Missing options go to a host options request that also proposes
    criteria; options without criteria go to a host criteria proposal (max_options=0); every
    proposal then passes a human approval step before Jev may use it (user decision).
ARCHITECTURE: Pure function over Working returning a Followup or None (basis is complete).
"""

from __future__ import annotations

from kernel.capabilities.decision.requests import (
    DEFAULT_MAX_OPTIONS,
    Followup,
    approval_request,
    grounding_request,
    options_request,
)
from kernel.capabilities.decision.state import Working
from kernel.contracts.enums import DecisionStatus, MissingKnowledge

GROUND_KEY = "ground:options"
OPTIONS_KEY = "options:full"
CRITERIA_KEY = "options:criteria-only"


def _approval_followup(work: Working) -> Followup:
    """Build the human approval step for pending proposals."""
    pending = work.pending_ids
    return Followup(
        status=DecisionStatus.NEEDS_HUMAN, key="approval:" + ",".join(sorted(pending)),
        phase="awaiting_approval", reason="proposal_approval",
        request=approval_request(work),
        open_question="Generated options or criteria await human approval.",
        missing=[MissingKnowledge.HUMAN_PREFERENCE_OR_AUTHORIZATION])


def _grounding_followup(work: Working) -> Followup:
    """Build the research step that gathers evidence about the option space."""
    return Followup(
        status=DecisionStatus.NEEDS_EVIDENCE, key=GROUND_KEY, phase="awaiting_grounding",
        reason="options_need_grounding", request=grounding_request(work),
        open_question="Evidence about the option space is needed before options are proposed.",
        missing=[MissingKnowledge.UNKNOWN_OPTIONS])


def needs_grounding(work: Working) -> bool:
    """True if options are unknown, nothing is known about the option space and no research ran."""
    return (not work.usable_options and not work.evidence
            and GROUND_KEY not in work.cont.requested)


def grounding_gap(work: Working) -> bool:
    """True if grounding research already ran yet no evidence exists to ground options in."""
    return (not work.usable_options and not work.pending_ids and not work.evidence
            and GROUND_KEY in work.cont.requested)


def validate_basis(work: Working) -> Followup | None:
    """Return the follow-up that must happen before assessment, or None when the basis is ready.

    Order: pending approvals first (proposals are never used unapproved), then grounding research
    when options are unknown and nothing is known about the option space, then missing options
    (request options plus proposed criteria, with the evidence attached), then missing criteria
    (request criteria only).
    """
    if work.pending_ids:
        return _approval_followup(work)
    if needs_grounding(work):
        return _grounding_followup(work)
    if not work.usable_options:
        return Followup(
            status=DecisionStatus.NEEDS_OPTIONS, key=OPTIONS_KEY, phase="awaiting_options",
            reason="unknown_options", request=options_request(work, DEFAULT_MAX_OPTIONS),
            open_question="No usable options are known.",
            missing=[MissingKnowledge.UNKNOWN_OPTIONS])
    if not work.has_required_criterion:
        return Followup(
            status=DecisionStatus.NEEDS_OPTIONS, key=CRITERIA_KEY, phase="awaiting_options",
            reason="missing_criteria", request=options_request(work, 0),
            open_question="Options are known but no approved required criterion exists.",
            missing=[MissingKnowledge.UNKNOWN_OPTIONS])
    return None


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 23:00 [python-coder]: Unknown options with no evidence are grounded first: the
#   host that proposes options has no repository access, so without evidence in the packet it
#   could only invent them. (#KernelBootstrapV0/GROUND)
# - 2026-10-01 02:00 [python-coder]: "No usable required criterion" counts as missing criteria:
#   only required criteria gate resolution, so supporting-only sets must not reach the gate.
#   (#KernelBootstrapV0/FIXA)
# - 2026-09-30 23:00 [python-coder]: Options known but criteria missing no longer asks a human
#   for free-text criteria (design part 4); it requests LLM-proposed criteria first and then a
#   human approval, per the user decision. (#KernelBootstrapV0/P5)
# ====================================================================
