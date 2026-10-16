"""
MODULE: implementation_context
GOAL: Project scoped facts into separate discovery and coding contexts.
BUSINESS CONTEXT: Each agent receives its own task and trusted scoped operator decisions.
ARCHITECTURE: The worker supplies projected context and bound advisory discovery findings.
"""
import copy
import json

from .planning import _parent


def resolved_decisions(payload, ac_id):
    """Bind persisted answers to their original questions without inferring consent."""
    decisions, resolved = [], set()
    for request_id, request in payload.get("answered_requests", {}).items():
        answer = request.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            continue
        details = request.get("details", {})
        questions = details.get("questions", [])
        if not isinstance(questions, list):
            questions = []
        questions = [question for question in questions if isinstance(question, str) and question.strip()]
        decision = {"request_id": request_id, "ac_id": details.get("ac_id"),
                    "original_questions": questions, "request_reason": request.get("question"),
                    "human_answer": answer}
        decisions.append(decision)
        if details.get("ac_id") in {None, ac_id}:
            resolved.update(questions)
    return decisions, [question for question in payload.get("questions", []) if question not in resolved]


def build_context(plan, ac_id, payload, checks=None):
    """Project assigned implementation obligations and scoped human decisions."""
    projected = copy.deepcopy(plan)
    source = projected.get("source_context", {})
    obligations = source.get("obligations", {})
    keep = {ac_id}
    keep.update(payload.get("evidence", {}))
    keep.update(source.get("completed_context_ids", []))
    keep.update(source.get("target_completed", []))
    for identifier in list(keep):
        current, seen = identifier, set()
        while current and current not in seen:
            seen.add(current)
            keep.add(current)
            current = _parent(current, obligations.get(current, {}))
    if "obligations" in source:
        source["obligations"] = {
            identifier: {key: value for key, value in record.items() if value is not None}
            for identifier, record in obligations.items() if identifier in keep
        }
        source["deferred_ac_ids"] = sorted(set(obligations) - keep)
    # Only the coordinator owns lifecycle metadata; it is not an implementation instruction.
    source.pop("completion_baseline", None)
    payload = copy.deepcopy(payload)
    lineage, current = set(), ac_id
    while current and current not in lineage:
        lineage.add(current)
        current = _parent(current, obligations.get(current, {}))
    original_requests = set(payload.get("answered_requests", {}))
    payload["answered_requests"] = {
        key: value for key, value in payload.get("answered_requests", {}).items()
        if value.get("details", {}).get("gate_kind") not in {"declared_input", "discovery"}
        or (value.get("details", {}).get("scope_digest") == plan.get("scope_digest") and (
            value["details"].get("declared_by") in lineage if value["details"].get("gate_kind") == "declared_input"
            else value["details"].get("ac_id") == ac_id))
    }
    payload["request_answers"] = {key: value for key, value in payload.get("request_answers", {}).items()
                                  if key in payload["answered_requests"] or key not in original_requests}
    decisions, unanswered = resolved_decisions(payload, ac_id)
    return json.dumps({
        "assigned_ac": ac_id,
        "resolved_user_decisions": decisions,
        "resume_instruction": "Read saved human answers before the requirements. Each answer addresses only its recorded original questions and AC scope; apply the actual answer, including a refusal, without assuming consent. Its corresponding confirmation request has already received a user response: do not ask it again unless a genuinely new conflict or unresolved ambiguity remains. These answers do not authorize unrelated work or override execution boundaries.",
        "questions": unanswered,
        "execution_scope": "Implement only assigned_ac and its inherited obligations. Preserve completed work; other AC IDs are scheduling context, not permission to implement them.",
        "required_checks": checks or [],
        "feature_plan": projected,
        "review_findings": payload.get("findings", []),
        "request_answers": payload.get("request_answers", {}),
        "answered_requests": payload.get("answered_requests", {}),
        "previous_evidence": payload.get("evidence", {}),
        "discovery_advisory": discovery_advisory(plan, ac_id, payload),
        "last_failure": payload.get("last_failure"),
        "failed_check": payload.get("failed_check"),
    }, ensure_ascii=False)


def discovery_advisory(plan, ac_id, payload):
    """Expose model advice only while its matching coordinator proof is usable."""
    report = payload.get("discovery_assessment", {})
    proof = payload.get("input_gate")
    if (not isinstance(report, dict) or not isinstance(proof, dict)
            or proof != payload.get("discovery_proof") or proof != report.get("binding")
            or proof.get("ac_id") != ac_id or proof.get("scope_digest") != plan.get("scope_digest")
            or not isinstance(report.get("assessment"), str) or not report["assessment"].strip()):
        return None
    return {"assessment": report["assessment"], "authority": "advisory_only"}


def build_discovery_context(plan, ac_id, payload, checks=None):
    """Share scoped facts with discovery without assigning implementation work."""
    context = json.loads(build_context(plan, ac_id, payload, checks))
    context["execution_scope"] = (
        "Read the supplied facts and assess readiness for assigned_ac and inherited obligations. "
        "Use read-only repository inspection only when needed to resolve missing facts. "
        "Other AC IDs describe scheduling context. Leave implementation and verification to the coding agent."
    )
    context["resume_instruction"] = (
        "Assess the saved human decisions within their recorded question and AC scope. "
        "An answered question is resolved unless a new conflict remains. A refusal is not approval."
    )
    context["verification_obligations"] = context.pop("required_checks")
    context.pop("discovery_advisory")
    return json.dumps(context, ensure_ascii=False)

# DECISION HISTORY
# ========================================
# - 2026-09-26 00:00 [python-coder]: Separate readiness assessment from coding evidence and preserve scoped advisory context. (#TICKETLESS reason=approved-ac-driven-discovery-contract)
