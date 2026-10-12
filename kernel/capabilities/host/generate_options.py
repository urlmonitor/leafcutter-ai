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

import re
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


def _ground_options(options: list[Option], request: OptionsRequestPayload, notes: list[str]
                    ) -> list[Option]:
    """Keep only references to supplied evidence; flag or refuse options citing none of it."""
    allowed = set(request.evidence_ids)
    out: list[Option] = []
    for option in options:
        refs = [r for r in dict.fromkeys(option.source_refs) if r in allowed]
        option = option.model_copy(update={"source_refs": refs})
        if refs:
            out.append(option)
        elif request.require_grounding:
            notes.append(f"option {option.id} was refused: it cites none of the supplied "
                         "evidence (not grounded)")
        else:
            notes.append(f"option {option.id} is not grounded: it cites none of the supplied "
                         "evidence")
            out.append(option)
    return out


def _norm(text: str) -> str:
    """Return text lower-cased with every non-alphanumeric run collapsed to one space."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.casefold()).split())


def _in_goal(title: str, goal: str) -> bool:
    """Deterministic check that a title is the caller's own wording: substring or all tokens."""
    wanted, haystack = _norm(title), _norm(goal)
    if not wanted:
        return False
    if wanted in haystack:
        return True
    tokens = [w for w in wanted.split() if len(w) > 2]
    return bool(tokens) and set(tokens) <= set(haystack.split())


def _split_named(options: list[Option], request: OptionsRequestPayload, notes: list[str]
                 ) -> tuple[list[Option], list[Option]]:
    """Split host-claimed named options: verified ones become supplied, the rest proposals.

    Extracting the options from free text is generative work (ADR-053), so the host only claims
    them; the kernel keeps a claim only when the title appears in the goal text. A verified option
    keeps just the caller's title (no host description or assumptions).
    """
    named: list[Option] = []
    rest: list[Option] = []
    for item in options:
        if not item.named_in_goal:
            rest.append(item)
        elif _in_goal(item.title, request.problem):
            named.append(Option(
                id=item.id, title=item.title.strip(), proposal_status=ProposalStatus.SUPPLIED,
                approval_status=ApprovalStatus.NOT_REQUIRED, proposed_by="caller_goal",
                named_in_goal=True, source_refs=item.source_refs))
        else:
            notes.append(f"option {item.id} was claimed as named in the goal but its title was "
                         "not found in the goal; it stays a proposal")
            rest.append(item.model_copy(update={"named_in_goal": False}))
    return named, rest


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
        lines += self._grounding_requirements(request)
        lines.append("If the goal itself names the options to choose between, return each of them "
                     "as an option with named_in_goal true and the caller's own words as its "
                     "title; the kernel checks the wording against the goal and treats verified "
                     "ones as the caller's options. Other options you generate must be grounded.")
        if request.findings:
            lines.append("The request lists accepted findings from an earlier synthesis: build on "
                         "them instead of re-reading the raw excerpts.")
        if not request.propose_criteria:
            lines.append("Leave proposed_criteria empty: criteria were not requested.")
        lines.append("Do not set weight_rule or decision_basis on a criterion; weights belong "
                     "to the approver.")
        if request.existing_option_ids:
            lines.append("Do not reuse these option ids: " + ", ".join(request.existing_option_ids))
        return lines

    @staticmethod
    def _grounded(options: list[Option], request: Any, notes: list[str]) -> list[Option]:
        """Apply the grounding rules of the request (a request that did not parse is skipped)."""
        return options if request is None else _ground_options(options, request, notes)

    @staticmethod
    def _grounding_requirements(request: Any) -> list[str]:
        """Return the grounding rules: cite supplied evidence, no repository access."""
        if not request.evidence_ids:
            return ["No evidence was supplied and this operation has no repository access: "
                    "leave source_refs empty; the options will be flagged as ungrounded."]
        rule = ("This operation has no repository access: use only the cited evidence in the "
                "input artifact. Cite the evidence ids each option rests on in its source_refs "
                "(only ids from: " + ", ".join(request.evidence_ids) + ").")
        if request.require_grounding:
            rule += " An option that cites none of them is refused."
        return [rule]

    def convert_payload(self, ctx: HostConversion, payload: OptionsPayload) -> CapabilityResult:
        """Return options and criteria as proposals, within what the request asked for."""
        request = self.parse_request(ctx.invocation.input_payload)
        notes: list[str] = []
        taken = set(request.existing_option_ids) if request else set()
        options = [o for o in payload.options if o.id not in taken]
        if len(options) != len(payload.options):
            notes.append("options reusing an existing option id were dropped")
        named: list[Option] = []
        if request is not None:
            named, options = _split_named(options, request, notes)
        options = self._grounded(options, request, notes)
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
            named_options=named,
            proposed_criteria=[_as_proposal(c, self.capability_id) for c in criteria],
            unresolved_feasibility=list(payload.unresolved_feasibility))
        return completed_result(ctx, schema_ids.OPTIONS, body, limitations=[
            "options and criteria are proposals until a human approves them", *notes])


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-02 [python-coder]: Options named in the goal are extracted by the host (generative)
#   and verified by the kernel (substring or token match against the goal) before they are
#   supplied options; the alternative of asking at intake whenever the goal enumerates was not
#   taken: it costs a host call on every goal. (#KernelBootstrapV0/GROUND)
# - 2026-10-01 23:00 [python-coder]: generate_options stays read-only WITHOUT repository access
#   (permissions_required remains empty): a host reading files itself would bypass the kernel's
#   deny globs, size limits and revision stamps and produce unverifiable claims. Grounding comes
#   from kernel-retrieved evidence in the packet; options cite it in source_refs and are flagged
#   or refused otherwise. (#KernelBootstrapV0/GROUND)
# - 2026-10-01 11:20 [python-coder]: A criterion's weight_rule and decision_basis are cleared:
#   weighting is the approver's choice (spec 10.4), and a host that supplied one would be
#   resolving a missing preference on the human's behalf. (#KernelBootstrapV0/P8)
# - 2026-10-01 11:20 [python-coder]: Excess options and unrequested criteria are dropped with a
#   limitation instead of rejected: the answer was already accepted as valid, and a rejection
#   here would fail the work item for a surplus rather than a violation. (#KernelBootstrapV0/P8)
# ====================================================================
