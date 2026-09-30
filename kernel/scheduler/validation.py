"""
MODULE: kernel.scheduler.validation
GOAL: Validate a CapabilityResult before the kernel merges it: identity, output schema, semantic
    references and cited evidence/finding ids (spec section 8.1 step 6).
BUSINESS CONTEXT: A capability proposes; the kernel disposes. A forged work-item id, an output
    that does not match the catalog, or a citation of evidence that does not exist must never
    reach run state, or a false "complete" could be reported.
ARCHITECTURE: Pure function over the result, its invocation and the ids known to the run. The
    verdict carries a machine code that becomes the failed item's error code.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

from kernel.contracts import (
    CapabilityInvocation,
    CapabilityResult,
    PayloadValidationError,
    Request,
    ResultStatus,
    SemanticContext,
    SemanticValidationError,
    UnknownSchemaError,
    validate_payload,
    validate_semantics,
)


@dataclass(frozen=True)
class Verdict:
    """Outcome of result validation."""

    ok: bool
    code: str = ""
    messages: tuple[str, ...] = ()

    def text(self) -> str:
        """Return the messages as one line."""
        return "; ".join(self.messages)


_OK = Verdict(True)


def _rejected(code: str, *messages: str) -> Verdict:
    """Build a failing verdict."""
    return Verdict(False, code, tuple(messages))


def _missing(cited: Collection[str], known: Collection[str]) -> list[str]:
    """Return the cited ids that are not known, sorted."""
    return sorted(set(cited) - set(known))


def _check_citations(result: CapabilityResult, known_evidence: set[str]) -> Verdict:
    """Findings and decisions may only cite evidence that exists or is included."""
    cited = [i for f in result.findings
             for i in (*f.supporting_evidence_ids, *f.contradicting_evidence_ids)]
    cited += [i for d in result.decisions for i in d.evidence_ids]
    gone = _missing(cited, known_evidence)
    if gone:
        return _rejected("unknown_reference", *(f"evidence {i} does not exist" for i in gone))
    return _OK


def _check_output(result: CapabilityResult, request: Request, known_evidence: set[str],
                  known_findings: set[str]) -> Verdict:
    """Validate the typed output: catalog schema, requested schema and references."""
    schema_id = result.output_schema_id
    if schema_id is None or result.output_payload is None:
        return _OK
    try:
        model = validate_payload(schema_id, dict(result.output_payload))
    except (PayloadValidationError, UnknownSchemaError) as exc:
        return _rejected("schema_invalid", str(exc))
    if result.status is ResultStatus.COMPLETED and schema_id != request.requested_output_schema:
        return _rejected("output_schema_mismatch", f"expected {request.requested_output_schema}, "
                         f"got {schema_id}")
    ctx = SemanticContext(known_evidence_ids=frozenset(known_evidence),
                          known_finding_ids=frozenset(known_findings))
    try:
        validate_semantics(schema_id, model, ctx)
    except SemanticValidationError as exc:
        return _rejected("semantic_invalid", *exc.violations)
    return _OK


def validate_result(result: CapabilityResult, invocation: CapabilityInvocation,
                    request: Request, known_evidence_ids: Collection[str],
                    known_finding_ids: Collection[str]) -> Verdict:
    """Validate one result against its invocation and the ids known to the run.

    Args:
        result: The executor's result.
        invocation: The invocation it answers.
        request: The request the work item serves (supplies the requested output schema).
        known_evidence_ids: Evidence ids already in run state.
        known_finding_ids: Finding ids already in run state.

    Returns:
        Verdict: ok, or a rejection with code `identity_mismatch`, `schema_invalid`,
            `output_schema_mismatch`, `semantic_invalid` or `unknown_reference`.
    """
    if (result.work_item_id != invocation.work_item_id
            or result.invocation_id != invocation.id):
        return _rejected("identity_mismatch", f"result claims work item {result.work_item_id}, "
                         f"invocation belongs to {invocation.work_item_id}")
    if result.status is ResultStatus.FAILED:
        return _OK
    known_evidence = set(known_evidence_ids) | {e.id for e in result.evidence}
    known_findings = set(known_finding_ids) | {f.id for f in result.findings}
    verdict = _check_output(result, request, known_evidence, known_findings)
    if not verdict.ok:
        return verdict
    return _check_citations(result, known_evidence)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:30 [python-coder]: Supplied-option checks are left to the decision capability
#   (P5): options may arrive through child outcomes, so the kernel cannot know the full set and
#   a strict check here would reject valid reports. (#KernelBootstrapV0/P4)
# ====================================================================
