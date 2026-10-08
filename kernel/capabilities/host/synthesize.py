"""
MODULE: kernel.capabilities.host.synthesize
GOAL: The `host.synthesize` operation: compile the evidence-synthesis task and convert the host's
    findings.v1 output into findings that are labelled inference and host-reported.
BUSINESS CONTEXT: Rev 3 section 10.4: synthesis may do real analysis, but the separation is about
    authority. A synthesised claim is the host's reading of the evidence, so it is recorded as an
    inference with a limitation, it may cite only evidence that exists, and agreements and
    disagreements are reported without being resolved.
ARCHITECTURE: Extends HostOperation. The request is synthesis_request.v1 (whose evidence ids the
    submission check already verified); the answer is findings.v1. Findings are re-identified
    from the interaction id and claim so a replayed graph node produces the same ids.
"""

from __future__ import annotations

from typing import Any

from kernel.capabilities.host.base import HostOperation
from kernel.capabilities.host.sanitize import completed_result, convert_findings
from kernel.capabilities.host.spec import HostConversion
from kernel.contracts import CapabilityResult, schema_ids
from kernel.contracts.payloads import FindingsPayload, SynthesisRequestPayload


class Synthesize(HostOperation):
    """host.synthesize: read the supplied evidence and report findings."""

    capability_id = "host.synthesize"
    operation = "synthesize_evidence"
    request_model = SynthesisRequestPayload
    output_model = FindingsPayload

    def task_text(self, request: Any, goal: str) -> str:
        """Return the synthesis task for the request's question."""
        if request is None:
            return super().task_text(request, goal)
        return f"Synthesize the cited evidence to answer: {request.question} (operation: " \
               f"{request.operation})."

    def requirements(self, request: Any) -> list[str]:
        """Return the synthesis rules plus the requester's own output requirements."""
        lines = ["Cite the evidence ids each finding rests on; cite only evidence you were given.",
                 "Report agreements and disagreements between sources; do not resolve a "
                 "disagreement and do not choose an option.",
                 "Your findings are recorded as host-reported inferences, not verified facts."]
        if request is None:
            return lines
        if request.limits.max_findings:
            lines.append(f"Return at most {request.limits.max_findings} findings.")
        if request.limits.max_chars:
            lines.append(f"Keep the whole answer under {request.limits.max_chars} characters.")
        lines += [f"Requester: {text}" for text in request.output_requirements]
        return lines

    def convert_payload(self, ctx: HostConversion, payload: FindingsPayload) -> CapabilityResult:
        """Return the findings as host-reported inferences within the requested maximum."""
        request = self.parse_request(ctx.invocation.input_payload)
        cap = request.limits.max_findings if request else None
        findings, notes = convert_findings(ctx, payload.findings, self.capability_id, {}, cap)
        body = FindingsPayload(
            findings=findings, agreements=list(payload.agreements),
            disagreements=list(payload.disagreements), constraints=list(payload.constraints),
            assumptions=list(payload.assumptions), unknowns=list(payload.unknowns))
        return completed_result(ctx, schema_ids.FINDINGS, body, findings=findings,
                                limitations=["findings are inferences by the host, not "
                                             "verified facts", *notes])


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 11:25 [python-coder]: The requester's own output_requirements are rendered as
#   `Requester: ...` lines, so they read as a quoted request and cannot be mistaken for the
#   kernel's rules. (#KernelBootstrapV0/P8)
# ====================================================================
