"""
MODULE: kernel.capabilities.host.research
GOAL: The `host.research` operation: compile the bounded-research task and convert the host's
    evidence_bundle.v1 into kernel evidence that is host-reported, unverified, with source
    locators and kernel-computed hashes.
BUSINESS CONTEXT: Host research is a fallback for evidence the native sources cannot provide
    (Rev 3 section 14), and it is reported, not verified (section 11.5). The host must not be able
    to pass its own hash, claim a repository commit, mark evidence verified, reuse a kernel id or
    declare a need satisfied by evidence that is not there.
ARCHITECTURE: Extends HostOperation. The request is retrieval_request.v1; the answer is
    evidence_bundle.v1. Inline evidence is rebuilt by `sanitize.convert_evidence` (new
    content-addressed ids), inline findings by `convert_findings`, and every reference in the
    bundle (evidence ids, contradictions, finding citations) is remapped to those new ids.
"""

from __future__ import annotations

from typing import Any

from kernel.capabilities.host.base import HostOperation
from kernel.capabilities.host.sanitize import (
    completed_result,
    convert_evidence,
    convert_findings,
)
from kernel.capabilities.host.spec import HostConversion
from kernel.contracts import CapabilityResult, NeedStatus, schema_ids
from kernel.contracts.evidence import Contradiction, EvidenceBundlePayload
from kernel.contracts.payloads import RetrievalRequestPayload

NO_NEED_NOTE = "the host reported coverage for a need that was not asked for; it was dropped"


def _coverage(payload: EvidenceBundlePayload, need_id: str | None, found: int, notes: list[str]
              ) -> dict[str, NeedStatus]:
    """Return coverage for the requested need only, never claiming more than the evidence shows."""
    if need_id is None:
        return dict(payload.coverage)
    if set(payload.coverage) - {need_id}:
        notes.append(NO_NEED_NOTE)
    claimed = payload.coverage.get(need_id)
    if not found:
        return {need_id: NeedStatus.UNAVAILABLE}
    if claimed is None or claimed is NeedStatus.OPEN:
        return {need_id: NeedStatus.PARTIAL}
    return {need_id: claimed}


def _contradictions(items: list[Contradiction], remap: dict[str, str], known: set[str] | None,
                    notes: list[str]) -> list[Contradiction]:
    """Return contradictions between evidence that exists (all when `known` is None), remapped."""
    out = []
    for item in items:
        a, b = remap.get(item.a, item.a), remap.get(item.b, item.b)
        if known is None or (a in known and b in known):
            out.append(Contradiction(a=a, b=b, note=item.note))
        else:
            notes.append("a contradiction naming unknown evidence was dropped")
    return out


class Research(HostOperation):
    """host.research: look in supplied artifacts, allowed repository paths and web sources."""

    capability_id = "host.research"
    operation = "bounded_research"
    request_model = RetrievalRequestPayload
    output_model = EvidenceBundlePayload

    def task_text(self, request: Any, goal: str) -> str:
        """Return the research task for the requested evidence need."""
        if request is None:
            return super().task_text(request, goal)
        need = request.need
        return (f"Find evidence for need {need.id} ({need.category.value}, "
                f"{need.priority.value}): {need.question}")

    def requirements(self, request: Any) -> list[str]:
        """Return the evidence rules: locators, no invented hashes or verification, coverage."""
        lines = ["Give every evidence item a source locator (a path with line range, or a URL) "
                 "and the excerpt you read.",
                 "Do not invent content hashes, ids or verification: the kernel computes them and "
                 "records your evidence as host-reported and unverified.",
                 "List sources you could not reach in unavailable_sources; never report a "
                 "failed source as an empty result."]
        if request is None:
            return lines
        lines.append(f"Report coverage under the key {request.need.id} only.")
        if request.source_ids:
            lines.append("Restrict research to these sources: " + ", ".join(request.source_ids))
        if request.limits.top_k:
            lines.append(f"Return at most {request.limits.top_k} evidence items.")
        if request.limits.max_chars:
            lines.append(f"Keep each excerpt under {request.limits.max_chars} characters.")
        return lines

    def convert_payload(self, ctx: HostConversion, payload: EvidenceBundlePayload
                        ) -> CapabilityResult:
        """Return a bundle of host-reported evidence under kernel-computed ids."""
        request = self.parse_request(ctx.invocation.input_payload)
        evidence, remap, notes = convert_evidence(ctx, payload.evidence, self.capability_id)
        findings, finding_notes = convert_findings(ctx, payload.findings, self.capability_id, remap)
        known = None if ctx.known_evidence_ids is None else {
            *ctx.known_evidence_ids, *remap.values(), *(e.id for e in ctx.extra_evidence)}
        cited = [remap.get(i, i) for i in payload.evidence_ids
                 if known is None or remap.get(i, i) in known]
        body = EvidenceBundlePayload(
            evidence_ids=list(dict.fromkeys([*(e.id for e in evidence), *cited])),
            finding_ids=[f.id for f in findings],
            coverage=_coverage(payload, request.need.id if request else None,
                               len(evidence) + len(ctx.extra_evidence), notes),
            attempted_sources=list(payload.attempted_sources),
            unavailable_sources=list(payload.unavailable_sources),
            contradictions=_contradictions(payload.contradictions, remap, known, notes),
            limitations=[*payload.limitations], truncated=payload.truncated,
            evidence=evidence, findings=findings)
        return completed_result(
            ctx, schema_ids.EVIDENCE_BUNDLE, body, evidence=evidence, findings=findings,
            limitations=["evidence is reported by the host and unverified", *notes,
                         *finding_notes])


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 11:30 [python-coder]: Coverage is clamped to the requested need and to what the
#   evidence shows: no evidence means `unavailable` whatever the host claimed, and a claimed
#   `satisfied` is kept only when evidence exists. (#KernelBootstrapV0/P8)
# - 2026-10-01 11:30 [python-coder]: `request_id` of the bundle is dropped (never host-chosen):
#   the kernel already ties the bundle to its request through the invocation.
#   (#KernelBootstrapV0/P8)
# ====================================================================
