"""
MODULE: kernel.contracts.schema_catalog
GOAL: Map schema ids to payload models, validate payloads, run semantic (reference) checks and
    export the committed JSON Schemas.
BUSINESS CONTEXT: Schema validation proves structure, not truth (Rev 3 section 7.11); semantic
    checks add the cheap, deterministic truths: cited evidence exists, a selected option was
    supplied, a human answer picked an offered choice.
ARCHITECTURE: SCHEMA_CATALOG is the single registry; errors build their own messages. JSON
    Schema files are written deterministically and a test asserts they match the models.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from kernel.contracts import schema_ids as sid
from kernel.contracts.base import KernelModel
from kernel.contracts.payloads import (
    DecisionReportPayload,
    DecisionRequestPayload,
    EvidenceBundlePayload,
    FindingsPayload,
    GoalRequestPayload,
    HumanAnswerPayload,
    HumanQuestionRequestPayload,
    OptionsPayload,
    OptionsRequestPayload,
    ResearchRequestPayload,
    RetrievalRequestPayload,
    SynthesisRequestPayload,
)

from kernel.contracts.query import (QueryBuildRequest, QueryCandidate,
                                    QueryActivationRequest, QueryActivationReceipt)

logger = logging.getLogger(__name__)

JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"

SCHEMA_CATALOG: dict[str, type[KernelModel]] = {
    sid.QUERY_BUILD_REQUEST: QueryBuildRequest,
    sid.QUERY_CANDIDATE: QueryCandidate,
    sid.QUERY_ACTIVATION_REQUEST: QueryActivationRequest,
    sid.QUERY_ACTIVATION_RECEIPT: QueryActivationReceipt,
    sid.GOAL_REQUEST: GoalRequestPayload,
    sid.DECISION_REQUEST: DecisionRequestPayload,
    sid.DECISION_REPORT: DecisionReportPayload,
    sid.RESEARCH_REQUEST: ResearchRequestPayload,
    sid.RETRIEVAL_REQUEST: RetrievalRequestPayload,
    sid.EVIDENCE_BUNDLE: EvidenceBundlePayload,
    sid.OPTIONS_REQUEST: OptionsRequestPayload,
    sid.OPTIONS: OptionsPayload,
    sid.SYNTHESIS_REQUEST: SynthesisRequestPayload,
    sid.FINDINGS: FindingsPayload,
    sid.HUMAN_QUESTION_REQUEST: HumanQuestionRequestPayload,
    sid.HUMAN_ANSWER: HumanAnswerPayload,
}


class UnknownSchemaError(ValueError):
    """The schema id is not registered in SCHEMA_CATALOG."""

    def __init__(self, schema_id: str) -> None:
        """Build the message from the offending id.

        Args:
            schema_id: Registered payload schema identity.
        """
        super().__init__(f"unknown schema id: {schema_id}")
        self.schema_id = schema_id


class PayloadValidationError(ValueError):
    """A payload failed structural validation against its registered schema."""

    def __init__(self, schema_id: str, detail: str) -> None:
        """Build the message from the schema id and Pydantic detail.

        Args:
            schema_id: Registered payload schema identity.
            detail: Validation failure details.
        """
        super().__init__(f"payload invalid for {schema_id}: {detail}")
        self.schema_id = schema_id
        self.detail = detail


class SemanticValidationError(ValueError):
    """A structurally valid payload violated a reference rule."""

    def __init__(self, schema_id: str, violations: list[str]) -> None:
        """Build the message from the violations (kept on .violations).

        Args:
            schema_id: Registered payload schema identity.
            violations: Detected semantic contract violations.
        """
        super().__init__(f"semantic check failed for {schema_id}: {'; '.join(violations)}")
        self.schema_id = schema_id
        self.violations = violations


def validate_payload(schema_id: str, data: dict) -> KernelModel:
    """Validate data against the registered model for schema_id.

    Args:
        schema_id: A registered schema id.
        data: The payload dict.

    Returns:
        KernelModel: The validated payload model.

    Raises:
        UnknownSchemaError: The id is not registered.
        PayloadValidationError: The payload does not match the schema.
    """
    model = SCHEMA_CATALOG.get(schema_id)
    if model is None:
        raise UnknownSchemaError(schema_id)
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise PayloadValidationError(schema_id, str(exc)) from exc


@dataclass(frozen=True)
class SemanticContext:
    """Ids known to the run, used to check references inside a payload."""

    known_evidence_ids: frozenset[str] = field(default_factory=frozenset)
    known_finding_ids: frozenset[str] = field(default_factory=frozenset)
    supplied_option_ids: frozenset[str] | None = None
    offered_choice_ids: frozenset[str] | None = None
    subject_ids: frozenset[str] | None = None
    kernel_built: bool = False  # True when the kernel itself built the payload (not a submission)


def _missing(cited: Iterable[str], known: Iterable[str], what: str) -> list[str]:
    """Return one violation per cited id that is not known.

    Args:
        cited: Input to the documented operation.
        known: Input to the documented operation.
        what: Input to the documented operation.

    Returns:
        list[str]: Result of the documented contract operation.
    """
    known_set = set(known)
    return [f"{what} {c} does not exist" for c in sorted(set(cited) - known_set)]


def _report_violations(p: DecisionReportPayload, ctx: SemanticContext) -> list[str]:
    """Semantic checks for decision_report.v1.

    Args:
        p: Validated payload whose references are checked.
        ctx: Trusted runtime scope, budgets and services.

    Returns:
        list[str]: Result of the documented contract operation.
    """
    cited = [*p.supporting_evidence_ids, *p.contradicting_evidence_ids,
             *(e for a in p.criterion_assessments for e in a.evidence_ids)]
    out = _missing(cited, ctx.known_evidence_ids, "evidence")
    if p.selected_option_id and ctx.supplied_option_ids is not None:
        out += _missing([p.selected_option_id], ctx.supplied_option_ids, "selected option")
    return out


def _bundle_violations(p: EvidenceBundlePayload, ctx: SemanticContext) -> list[str]:
    """Semantic checks for evidence_bundle.v1 (inline items count as known).

    Args:
        p: Validated payload whose references are checked.
        ctx: Trusted runtime scope, budgets and services.

    Returns:
        list[str]: Result of the documented contract operation.
    """
    inline_ev = {e.id for e in p.evidence}
    inline_fi = {f.id for f in p.findings}
    out = _missing(p.evidence_ids, ctx.known_evidence_ids | inline_ev, "evidence")
    out += _missing(p.finding_ids, ctx.known_finding_ids | inline_fi, "finding")
    for f in p.findings:
        cited = [*f.supporting_evidence_ids, *f.contradicting_evidence_ids]
        out += _missing(cited, ctx.known_evidence_ids | inline_ev, "evidence")
    return out


def _answer_violations(p: HumanAnswerPayload, ctx: SemanticContext) -> list[str]:
    """Semantic checks for a structured human answer: cited ids must be the question's subjects.

    Args:
        p: Validated payload whose references are checked.
        ctx: Trusted runtime scope, budgets and services.

    Returns:
        list[str]: Result of the documented contract operation.
    """
    if ctx.subject_ids is None:
        return []
    cited = [*(p.approved_option_ids or []), *(p.approved_criterion_ids or []),
             *(e.id for e in p.edited_criteria or [] if e.id)]
    return _missing(cited, ctx.subject_ids, "subject")


def _options_violations(p: OptionsPayload, ctx: SemanticContext) -> list[str]:
    """Generated options and criteria must stay proposals: a generator cannot approve itself.

    `named_options` is refused only on a host submission: the kernel creates it after verifying
    the host's claims against the goal, so a kernel-built payload may carry it.
    """
    if p.named_options and not ctx.kernel_built:
        return ["named_options is set by the kernel only: return named options in `options` "
                "with named_in_goal true"]
    items = [("option", i.id, i.approval_status, i.approved_by) for i in p.options]
    items += [("criterion", i.id, i.approval_status, i.approved_by) for i in p.proposed_criteria]
    return [f"generated {kind} {item_id} must have approval_status proposed and no approved_by"
            for kind, item_id, status, by in items if status.value != "proposed" or by]


def semantic_violations(schema_id: str, payload: KernelModel, ctx: SemanticContext) -> list[str]:
    """Return the reference violations of a validated payload (empty list means OK).

    Args:
        schema_id: The payload's schema id.
        payload: The validated payload model.
        ctx: Ids known to the run.

    Returns:
        list[str]: Human-readable violations.
    """
    if isinstance(payload, DecisionReportPayload):
        return _report_violations(payload, ctx)
    if isinstance(payload, EvidenceBundlePayload):
        return _bundle_violations(payload, ctx)
    if isinstance(payload, HumanAnswerPayload):
        if payload.choice_id and ctx.offered_choice_ids is not None:
            return _missing([payload.choice_id], ctx.offered_choice_ids, "choice")
        return _answer_violations(payload, ctx)
    if isinstance(payload, OptionsPayload):
        return _options_violations(payload, ctx)
    if isinstance(payload, DecisionRequestPayload):
        return _missing(payload.evidence_ids, ctx.known_evidence_ids, "evidence")
    if isinstance(payload, (OptionsRequestPayload, SynthesisRequestPayload)):
        return _missing(payload.evidence_ids, ctx.known_evidence_ids, "evidence")
    return []


def validate_semantics(schema_id: str, payload: KernelModel, ctx: SemanticContext) -> None:
    """Raise SemanticValidationError if the payload has reference violations.

    Args:
        schema_id: The payload's schema id.
        payload: The validated payload model.
        ctx: Ids known to the run.
    """
    violations = semantic_violations(schema_id, payload, ctx)
    if violations:
        raise SemanticValidationError(schema_id, violations)


def json_schema_for(schema_id: str) -> dict:
    """Return the JSON Schema (draft 2020-12) of a registered payload, with $id and $schema.

    Args:
        schema_id: Registered payload schema identity.

    Returns:
        dict: Result of the documented contract operation.
    """
    model = SCHEMA_CATALOG.get(schema_id)
    if model is None:
        raise UnknownSchemaError(schema_id)
    schema = model.model_json_schema(mode="validation")
    return {"$schema": JSON_SCHEMA_DIALECT, "$id": schema_id, **schema}


def render_json_schema(schema_id: str) -> str:
    """Return the deterministic text committed for a schema id.

    Args:
        schema_id: Registered payload schema identity.

    Returns:
        str: Result of the documented contract operation.
    """
    return json.dumps(json_schema_for(schema_id), indent=2, sort_keys=True) + "\n"


def export_json_schemas(directory: Path) -> list[Path]:
    """Write <schema_id>.schema.json for every catalog entry into directory.

    Args:
        directory: Target directory (created if missing).

    Returns:
        list[Path]: The written files in schema-id order.
    """
    written: list[Path] = []
    try:
        directory.mkdir(parents=True, exist_ok=True)
        for schema_id in sorted(SCHEMA_CATALOG):
            target = directory / f"{schema_id}.schema.json"
            target.write_text(render_json_schema(schema_id), encoding="utf-8", newline="\n")
            written.append(target)
    except OSError:
        logger.exception("could not export JSON schemas to %s", directory)
        raise
    return written


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: The named_options refusal applies to host submissions only;
#   SemanticContext.kernel_built lets result validation accept the kernel's own converted payload
#   (it had refused it, blocking every goal that names its options). (#KernelNamedOptionsBlocked)
# - 2026-10-02 [python-coder]: A host cannot return named_options itself; only the kernel creates
#   them after verifying the wording against the goal. (#KernelBootstrapV0/GROUND)
# - 2026-09-30 23:40 [python-coder]: A generated options payload that arrives pre-approved is a
#   semantic violation, closing a self-approval path for host output. (#KernelBootstrapV0/P6)
# - 2026-09-30 23:30 [python-coder]: SemanticContext.subject_ids bounds structured approval
#   answers to the ids the question asked about. (#KernelBootstrapV0/P6)
# - 2026-09-30 22:00 [python-coder]: Semantic checks return violation lists (pure) so the
#   resume path can map them to semantic_invalid without catching exceptions.
#   (#KernelBootstrapV0/P1)
# ====================================================================
