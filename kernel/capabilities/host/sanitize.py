"""
MODULE: kernel.capabilities.host.sanitize
GOAL: The shared rules that turn host-produced content into kernel content: evidence recomputed
    and labelled host-reported, findings re-identified and labelled inference, usage that stays
    unknown when unreported, and the completed CapabilityResult every operation returns.
BUSINESS CONTEXT: Host output is untrusted (Rev 3 section 13.3). It may carry claims, never
    authority: it cannot mark evidence verified, pass its own hash, reuse a kernel id, cite
    evidence that does not exist, or pose as human input. Unknown billing stays unavailable, not
    zero (section 11.7).
ARCHITECTURE: Pure functions over contract models. Every id is derived from the interaction id
    and content, so converting the same submission twice (a replayed graph node) gives identical
    evidence and findings. Nothing here reads state; known ids arrive in the HostConversion.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from kernel.capabilities.host.spec import HOST_NOTE, HostConversion, parse_compiled_by
from kernel.contracts import (
    CapabilityResult,
    Evidence,
    EvidenceSource,
    Finding,
    FindingKind,
    Provenance,
    ResultStatus,
    SemanticType,
    SourceKind,
    Usage,
    Verification,
    content_hash,
    evidence_id,
    sha256_hex,
)
from kernel.contracts.base import KernelModel


def derive_id(prefix: str, *parts: str) -> str:
    """Return a deterministic kernel id `<prefix>-<16 hex>` from the parts."""
    return f"{prefix}-{sha256_hex(chr(10).join(parts))[:16]}"


def elapsed_ms(ctx: HostConversion) -> int:
    """Return whole milliseconds from the packet opening to now (time to answer, never negative)."""
    return max(0, int((ctx.now - ctx.packet.created_at).total_seconds() * 1000))


def host_usage(ctx: HostConversion) -> tuple[list[Usage], bool]:
    """Return the usage to record and whether the host reported any.

    An unreporting host yields one host Usage that knows only the call count and the measured
    time to answer; tokens, model and cost stay None and the cost provenance stays unavailable.
    """
    if ctx.submission.usage:
        return list(ctx.submission.usage), True
    return [Usage(provider="host", duration_ms=elapsed_ms(ctx), calls=1)], False


def _unique(items: Iterable[str]) -> list[str]:
    """Return the items without repeats, in first-seen order."""
    return list(dict.fromkeys(items))


def _semantic_type(value: SemanticType) -> SemanticType:
    """Return the host's semantic type, except that a host cannot claim to be human input."""
    return SemanticType.REPOSITORY_FACT if value is SemanticType.HUMAN_INPUT else value


def convert_evidence(ctx: HostConversion, items: Sequence[Evidence], producer: str
                     ) -> tuple[list[Evidence], dict[str, str], list[str]]:
    """Return host evidence rebuilt by the kernel, the old-to-new id map and the notes.

    The hash is recomputed from the excerpt (or, for an artifact-only item, from the reference),
    the id is content-addressed from it, verification is always host_reported, the source kind is
    always host_research and any claimed source version is dropped.
    """
    out: dict[str, Evidence] = {}
    remap: dict[str, str] = {}
    notes: list[str] = []
    for item in items:
        by_reference = item.excerpt is None
        body = (item.artifact_ref or "") if by_reference else (item.excerpt or "")
        digest = content_hash(body)
        locator = item.source.locator
        if item.content_hash != digest:
            notes.append(f"the content hash the host gave for {locator} was replaced by the "
                         "kernel's own")
        limitations = [*item.limitations, HOST_NOTE]
        if by_reference:
            limitations.append("the hash covers the artifact reference, not its content")
        new = Evidence(
            id=evidence_id(locator, digest), created_at=ctx.now, updated_at=ctx.now,
            category=item.category, semantic_type=_semantic_type(item.semantic_type),
            excerpt=item.excerpt, artifact_ref=item.artifact_ref,
            source=EvidenceSource(id="host", kind=SourceKind.HOST_RESEARCH, locator=locator,
                                  title=item.source.title,
                                  section_locator=item.source.section_locator),
            content_hash=digest,
            provenance=Provenance(producer=producer, invocation_id=ctx.invocation.id,
                                  strategy="host_research", actor=ctx.submission.actor.id,
                                  relayed_by=ctx.submission.relayed_by),
            access=item.access, verification=Verification.HOST_REPORTED,
            limitations=_unique(limitations), truncated=item.truncated)
        out.setdefault(new.id, new)
        remap[item.id] = new.id
    return list(out.values()), remap, notes


def _cited(ids: Sequence[str], remap: dict[str, str], known: frozenset[str] | None,
           notes: list[str]) -> list[str]:
    """Map cited evidence ids to kernel ids; drop (and note) ids that do not exist."""
    mapped = [remap.get(i, i) for i in ids]
    if known is None:
        return _unique(mapped)
    allowed = known | set(remap.values())
    for gone in [i for i in mapped if i not in allowed]:
        notes.append(f"a citation of unknown evidence {gone} was dropped")
    return _unique(i for i in mapped if i in allowed)


def convert_findings(ctx: HostConversion, findings: Sequence[Finding], producer: str,
                     remap: dict[str, str], cap: int | None = None
                     ) -> tuple[list[Finding], list[str]]:
    """Return host findings rebuilt as host-reported inferences and the notes.

    Ids are derived from the interaction and the claim; `source_fact` and `human_input` are
    downgraded to `inference` (only the kernel can verify a fact or relay a human); citations of
    evidence that does not exist are dropped; `cap` bounds how many findings are kept.
    """
    notes: list[str] = []
    kept = list(findings)
    if cap is not None and len(kept) > cap:
        notes.append(f"{len(kept) - cap} findings beyond the requested maximum of {cap} dropped")
        kept = kept[:cap]
    out: list[Finding] = []
    for index, item in enumerate(kept):
        kind = item.kind if item.kind is FindingKind.ASSUMPTION else FindingKind.INFERENCE
        if kind is not item.kind:
            notes.append(f"finding {index} was labelled {item.kind.value}; recorded as inference")
        out.append(Finding(
            id=derive_id("find", ctx.packet.id, str(index), item.claim),
            created_at=ctx.now, updated_at=ctx.now, claim=item.claim, kind=kind,
            supporting_evidence_ids=_cited(item.supporting_evidence_ids, remap,
                                           ctx.known_evidence_ids, notes),
            contradicting_evidence_ids=_cited(item.contradicting_evidence_ids, remap,
                                              ctx.known_evidence_ids, notes),
            limitations=_unique([*item.limitations, HOST_NOTE]), producer=producer,
            producer_version=ctx.invocation.capability_version))
    return out, _unique(notes)


def merge_evidence(first: Sequence[Evidence], second: Sequence[Evidence]) -> list[Evidence]:
    """Return both evidence lists without repeats by id (the first occurrence wins)."""
    return list({e.id: e for e in [*first, *second]}.values())


def completed_result(ctx: HostConversion, schema_id: str, payload: KernelModel, *,
                     evidence: Sequence[Evidence] = (), findings: Sequence[Finding] = (),
                     limitations: Sequence[str] = ()) -> CapabilityResult:
    """Return the completed result of a converted host output, with usage and telemetry facts."""
    usage, reported = host_usage(ctx)
    ref = parse_compiled_by(ctx.packet.output_requirements)
    diagnostics: dict[str, str | int | float | bool] = {
        "host_elapsed_ms": elapsed_ms(ctx), "host_usage": "reported" if reported else "unavailable"}
    if ref is not None:
        diagnostics["host_template"] = f"{ref.template_id}@{ref.template_version}"
        diagnostics["prompt_fingerprint"] = ref.fingerprint
    return CapabilityResult(
        invocation_id=ctx.invocation.id, work_item_id=ctx.packet.work_item_id,
        status=ResultStatus.COMPLETED, output_schema_id=schema_id,
        output_payload=payload.model_dump(mode="json"),
        evidence=merge_evidence(evidence, ctx.extra_evidence), findings=list(findings),
        usage=usage, limitations=_unique([HOST_NOTE, *limitations]), diagnostics=diagnostics)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 11:15 [python-coder]: An unreporting host still yields one Usage (calls=1 and the
#   measured time to answer, everything else None): dropping it would make the run summary show
#   no host operation, while inventing tokens or a zero cost would be wrong (spec 11.7).
#   (#KernelBootstrapV0/P8)
# - 2026-10-01 11:15 [python-coder]: `host_elapsed_ms` is a diagnostic, not ELAPSED_KEY: the time
#   a host takes to answer includes the wait for a person and must not be charged to the run's
#   active-seconds budget. (#KernelBootstrapV0/P8)
# ====================================================================
