"""
MODULE: kernel.capabilities.host.generate_options
GOAL: The `host.generate_options` operation: compile the option-generation task and convert the
    host's options.v1 output so every option and criterion is a proposal a human approves later.
BUSINESS CONTEXT: Rev 3 section 10.4: options are proposals and a model must not resolve missing
    user preference by quietly changing the criteria or their weights. The kernel therefore
    forces the proposal and approval status, strips any approver, drops criteria nobody asked
    for and never lets a host weight a criterion.
ARCHITECTURE: Extends HostOperation. The request is options_request.v1; the answer is
    options.v1. The schema pins both status fields in the packet (packets.tightened_schema), the
    semantic check rejects a pre-approved answer for repair, and this conversion enforces the
    same rules again so a path that skipped those checks still cannot produce an approval.
"""

from __future__ import annotations

from typing import Any

from kernel.capabilities.host.base import HostOperation
from kernel.capabilities.host.sanitize import completed_result
from kernel.capabilities.host.spec import HostConversion
from kernel.contracts import (
    ApprovalStatus,
    CapabilityResult,
    ProposalStatus,
    schema_ids,
)
from kernel.contracts.decision import Criterion, Option
from kernel.contracts.payloads import OptionsPayload, OptionsRequestPayload

OPTIONS_REQUIREMENT = ("Every option and every proposed criterion must set proposal_status and "
                       "approval_status to 'proposed'; a human approves them later, so never "
                       "set 'approved' or approved_by.")


def _as_proposal(item: Option | Criterion, producer: str) -> Any:
    """Return the option or criterion as a pure proposal attributed to the producer."""
    return item.model_copy(update={
        "proposal_status": ProposalStatus.PROPOSED, "approval_status": ApprovalStatus.PROPOSED,
        "approved_by": None, "proposed_by": producer})


class GenerateOptions(HostOperation):
    """host.generate_options: propose options (and, when asked, criteria)."""

    capability_id = "host.generate_options"
    operation = "generate_options"
    request_model = OptionsRequestPayload
    output_model = OptionsPayload

    def task_text(self, request: Any, goal: str) -> str:
        """Return the option-generation task for the request's problem."""
        if request is None:
            return super().task_text(request, goal)
        extra = (" Also propose the decision criteria an option must satisfy."
                 if request.propose_criteria else " Do not propose criteria.")
        count = f"up to {request.max_options} candidate options" if request.max_options             else "no options"
        return f"Propose {count} for this problem: {request.problem}.{extra}"

    def requirements(self, request: Any) -> list[str]:
        """Return the proposal rules plus the option count and criteria rules of the request."""
        lines = [OPTIONS_REQUIREMENT]
        if request is None:
            return lines
        lines.append(f"Return at most {request.max_options} options.")
        if not request.propose_criteria:
            lines.append("Leave proposed_criteria empty: criteria were not requested.")
        lines.append("Do not set weight_rule or decision_basis on a criterion; weights belong "
                     "to the approver.")
        if request.existing_option_ids:
            lines.append("Do not reuse these option ids: " + ", ".join(request.existing_option_ids))
        return lines

    def convert_payload(self, ctx: HostConversion, payload: OptionsPayload) -> CapabilityResult:
        """Return options and criteria as proposals, within what the request asked for."""
        request = self.parse_request(ctx.invocation.input_payload)
        notes: list[str] = []
        taken = set(request.existing_option_ids) if request else set()
        options = [o for o in payload.options if o.id not in taken]
        if len(options) != len(payload.options):
            notes.append("options reusing an existing option id were dropped")
        if request is not None and len(options) > request.max_options:
            notes.append(f"{len(options) - request.max_options} options beyond the requested "
                         f"maximum of {request.max_options} were dropped")
            options = options[:request.max_options]
        criteria = list(payload.proposed_criteria)
        if request is not None and not request.propose_criteria and criteria:
            notes.append("proposed criteria were dropped: the request did not ask for criteria")
            criteria = []
        if any(c.weight_rule or c.decision_basis for c in criteria):
            notes.append("weight rules and decision bases set by the host were removed")
        criteria = [c.model_copy(update={"weight_rule": None, "decision_basis": None})
                    for c in criteria]
        body = OptionsPayload(
            options=[_as_proposal(o, self.capability_id) for o in options],
            proposed_criteria=[_as_proposal(c, self.capability_id) for c in criteria],
            unresolved_feasibility=list(payload.unresolved_feasibility))
        return completed_result(ctx, schema_ids.OPTIONS, body, limitations=[
            "options and criteria are proposals until a human approves them", *notes])


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 11:20 [python-coder]: A criterion's weight_rule and decision_basis are cleared:
#   weighting is the approver's choice (spec 10.4), and a host that supplied one would be
#   resolving a missing preference on the human's behalf. (#KernelBootstrapV0/P8)
# - 2026-10-01 11:20 [python-coder]: Excess options and unrequested criteria are dropped with a
#   limitation instead of rejected: the answer was already accepted as valid, and a rejection
#   here would fail the work item for a surplus rather than a violation. (#KernelBootstrapV0/P8)
# ====================================================================
