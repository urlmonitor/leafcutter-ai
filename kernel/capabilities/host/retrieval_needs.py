"""MODULE: retrieval_needs
GOAL: Compile and validate one model-neutral host interpretation of retrieval needs.
BUSINESS CONTEXT: Host generation can interpret needs while classifier quality is evaluated.
ARCHITECTURE: Existing packet, ledger and resume owner; no autonomous LLM or query client.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from kernel.capabilities.host.base import HostOperation, invalid_output
from kernel.capabilities.host.sanitize import completed_result
from kernel.capabilities.host.spec import HostConversion
from kernel.contracts import CapabilityResult, schema_ids
from kernel.contracts.base import KernelModel
from kernel.contracts.retrieval_needs import DIMENSIONS, RetrievalNeedsOutput, RetrievalNeedsRequest


def _membership(request: RetrievalNeedsRequest, output: RetrievalNeedsOutput) -> list[str]:
    """Refuse labels outside supplied offers and contradictory selection membership."""
    violations: list[str] = []
    for dimension in DIMENSIONS:
        selected, uncertain = set(output.selections[dimension]), set(output.uncertain[dimension])
        unknown = (selected | uncertain) - set(request.catalog[dimension])
        if unknown:
            violations.append(f"Unoffered {dimension}: {sorted(unknown)}")
        if selected & uncertain:
            violations.append(f"Selected and uncertain overlap in {dimension}")
    return violations


def _missing(output: RetrievalNeedsOutput) -> list[str]:
    """Add structural unresolved dimensions while leaving semantic judgment to the host."""
    selected = output.selections
    missing = list(output.unresolved)
    missing.extend(name for name in ("entity_types", "document_types") if not selected[name])
    missing.extend(name for name in ("detail_mode", "completeness") if getattr(output, name) == "unknown")
    if output.detail_mode == "fields" and not selected["required_fields"]:
        missing.append("required_fields")
    if output.completeness in {"single_entity", "selected_entities"} and not selected["target_ids"]:
        missing.append("target_ids")
    if output.scope_resolution in {"unknown", "user_choice_missing"}:
        missing.append("scope_resolution")
    return list(dict.fromkeys([*missing, *_hierarchy_gaps(output)]))


def _hierarchy_gaps(output: RetrievalNeedsOutput) -> list[str]:
    """Keep exact sets/counts and identified multi-target requirements explicit."""
    missing = []
    if output.hierarchy_scope == "unknown" and output.completeness in {"exhaustive_count", "exhaustive_set"}:
        missing.append("hierarchy_scope")
    if (output.completeness == "selected_entities" and len(output.selections["target_ids"]) == 1
            and not output.selections["relationships"]):
        missing.append("multiple_target_ids")
    return missing


class RetrievalNeeds(HostOperation):
    """An experimental interpreter, exposed only by explicitly supplied experiment registries."""

    capability_id = "host.retrieval_needs"
    operation = "interpret_retrieval_needs"
    request_model = RetrievalNeedsRequest
    output_model = RetrievalNeedsOutput

    def task_text(self, request: Any, goal: str) -> str:
        """State the original question without selecting a search method or answering it."""
        return "Determine the information needed to answer: " + (request.original_question if request else goal)

    def requirements(self, request: Any) -> list[str]:
        """Compile actionable, bounded host instructions without quality labels or prior outputs."""
        return [
            "Interpret only the original_question and supplied context/catalog in the input artifact. Do not retrieve or answer the question.",
            "Return the original_question and source_scope unchanged. Context and known_ids are unverified candidates, not authority or permissions.",
            "For each of entity_types, target_ids, required_fields, document_types and relationships return selections and uncertain arrays. Choose only exact offered labels; multiple are allowed.",
            "required_fields means facts indispensable to answering, not every related or helpful field. Optional supporting information may be mentioned only in rationale.",
            "User literal targets take precedence over conflicting contextual examples. Do not invent IDs. Missing IDs for thematic discovery do not by themselves require clarification.",
            "detail_mode: fields means requested facts; full_document means whole selected item; bounded_context means selected item plus requested surroundings, never the repository.",
            "completeness: single_entity or selected_entities require complete fields for identified targets; examples permits relevant samples; exhaustive_set/count requires full requested population coverage later.",
            "hierarchy_scope: exclude_root excludes only the chosen root; exclude_parents excludes every parent; include_root includes the root; not_applicable applies to exact-item questions without population inclusion.",
            "scope_resolution: sufficient means retrieval may start; discovery_needed means topic membership needs evidence; user_choice_missing means a genuinely missing preference; unknown retains uncertainty.",
            "Preserve requested all-descendant requirements. Do not substitute bounded direct children. Do not demand population/root clarification for one named criterion.",
            "Use unresolved for unsupported meanings (needs_outside_catalog), unknowns and contradictions. Return needs_resolution rather than a confidently empty interpretation.",
            "This is host-reported interpretation, not classifier approval or a fulfilled answer. No Jev probability, method choice, query, or policy approval may be generated.",
            "engine is host_llm. model_id is null unless known; actual reported submission usage is authoritative for model provenance.",
        ]

    def submission_violations(self, request: Mapping[str, Any], payload: KernelModel) -> list[str]:
        """Check the actual pending request before the interaction ledger accepts output."""
        try:
            expected = RetrievalNeedsRequest.model_validate(dict(request))
        except ValidationError:
            return ["The pending retrieval-needs request is invalid"]
        if not isinstance(payload, RetrievalNeedsOutput):
            return ["The host response is not a retrieval-needs output"]
        violations = _membership(expected, payload)
        if payload.original_question != expected.original_question:
            violations.append("The original question must remain unchanged")
        if payload.source_scope != expected.source_scope:
            violations.append("The source scope must remain unchanged")
        missing = _missing(payload)
        if payload.status == "needs_resolution" and not missing:
            violations.append("An unresolved interpretation needs an explicit missing reason")
        if len(missing) > 32:
            violations.append("Host reasons plus structural missing dimensions exceed the 32-item bound")
        return violations

    def convert_payload(self, ctx: HostConversion, payload: RetrievalNeedsOutput) -> CapabilityResult:
        """Keep the interpretation host-reported and derive status/provenance from the run."""
        violations = self.submission_violations(ctx.invocation.input_payload, payload)
        if violations:
            return invalid_output(ctx, "; ".join(violations))
        missing = _missing(payload)
        model = next((entry.model_id for entry in ctx.submission.usage
                      if entry.provider == "host" and entry.model_id), None)
        body = payload.model_dump(mode="json")
        body.update(status="needs_resolution" if missing else "decided", unresolved=missing, model_id=model)
        try:
            normalized = RetrievalNeedsOutput.model_validate(body)
        except ValidationError:
            return invalid_output(ctx, "Normalized host metadata exceeds the retrieval-needs contract")
        return completed_result(ctx, schema_ids.RETRIEVAL_NEEDS_OUTPUT, normalized,
            limitations=["Interpretation only; no retrieval executed and no answer correctness or classifier approval established."])


# DECISION HISTORY
# ================================================================================
# - 2026-10-03 00:00 [python-coder]: Use real host waits/resumes and reject scope/offer changes before ledger acceptance. (#TICKETLESS reason=user-requested-isolated-host-experiment)
