"""
MODULE: reply_contract
GOAL: Define shared phase-specific prompts, schemas and reply validation.
BUSINESS CONTEXT: Discovery readiness and implementation completion carry distinct obligations.
ARCHITECTURE: Adapters and graph boundaries enforce this same communication contract.
"""
import json

from .execution_boundary import ExecutorError, safe_output


class AgentReplyError(ExecutorError):
    """A refusal, reported error or unusable reply needs operator attention."""

    stop_run = True

    def __init__(self, kind, reason):
        self.reply_kind = kind
        reason = safe_output(reason)[:800]
        self.evidence = {"kind": "agent_reply", "reply_kind": kind, "reason": reason}
        super().__init__(f"Local agent {kind}: {reason}")


def reply_schema(*, discovery=False):
    """Return the authoritative reply shape for the selected agent phase."""
    schema = {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["ready" if discovery else "completed", "needs_input", "refused", "error"]},
            "questions": {"type": "array", "items": {"type": "string"}},
            "reason": {"type": "string"},
        },
        "required": ["status", "questions"],
        "additionalProperties": False,
    }
    if discovery:
        schema["properties"]["assessment"] = {"type": "string"}
        schema["allOf"] = [{"if": {"properties": {"status": {"const": "ready"}}},
                            "then": {"required": ["assessment"],
                                     "properties": {"assessment": {"type": "string", "pattern": r"\S"}}}}]
    return schema


def reply_instructions(*, discovery=False):
    """Describe the phase contract using examples derived from its schema."""
    schema = reply_schema(discovery=discovery)
    success = schema["properties"]["status"]["enum"][0]
    def compact(value):
        return json.dumps(value, separators=(",", ":"))
    success_reply = {"status": success, "questions": []}
    if discovery:
        success_reply["assessment"] = (
            "The AC defines trimming surrounding whitespace and rejecting an empty result; the saved decision "
            "resolves internal whitespace handling. The coding agent can now implement this behavior and add "
            "tests for padded and empty input."
        )
    return (
        ("After assessing readiness, " if discovery else "After tool execution, ")
        + "return ONLY one JSON object without Markdown fences, explanation or trailing characters. "
        + ("For ready, include a nonblank assessment explaining why the supplied evidence is sufficient. "
           "For other discovery outcomes assessment is optional. " if discovery else "")
        + "Fill status and questions; use reason only for refused or error. "
        + ("Illustrative ready example only; assess the actual AC, not this example: " if discovery else "")
        + compact(success_reply)
        + " reports the phase outcome, never approval or proof of implementation. "
        + compact({"status": "needs_input", "questions": ["the exact question"]})
        + " means a human decision is missing; it does not request delegation. "
        + compact({"status": "refused", "questions": [], "reason": "why execution was refused"})
        + " means execution was declined. "
        + compact({"status": "error", "questions": [], "reason": "what prevented execution"})
        + " means work could not be performed. Refused/error require a nonblank reason and no questions. "
        "Success requires empty questions; needs_input requires nonblank questions. "
        "Do not emit handoff, invent human answers, echo context fields or claim verified checks in this report. "
        "The coordinator verifies files, checks and human answers independently. "
        "Final-response JSON Schema: " + compact(schema) + "\n"
    )


def validate_reply(outcome, *, discovery=False, adapter=False):
    """Reject malformed outcomes and preserve only phase-approved fields."""
    schema = reply_schema(discovery=discovery)
    allowed = set(schema["properties"]) | ({"event_count"} if adapter else set())
    def invalid(reason):
        raise AgentReplyError("protocol_error", "Invalid structured local outcome: " + reason)
    if not isinstance(outcome, dict) or not set(schema["required"]).issubset(outcome):
        invalid("required fields are missing")
    if set(outcome) - allowed:
        invalid("undeclared fields are not communication or authorization")
    status = outcome["status"]
    if not isinstance(status, str) or status not in schema["properties"]["status"]["enum"]:
        invalid("Unsupported local reply status: " + str(status))
    if discovery and "assessment" in outcome and not isinstance(outcome["assessment"], str):
        invalid("discovery assessment must be a string")
    if discovery and status == "ready" and not outcome.get("assessment", "").strip():
        invalid("ready requires a nonblank discovery assessment")
    questions = outcome["questions"]
    if not isinstance(questions, list) or any(not isinstance(q, str) or not q.strip() for q in questions):
        invalid("questions must be a list of nonblank strings")
    if "event_count" in outcome and (type(outcome["event_count"]) is not int or outcome["event_count"] < 0):
        invalid("adapter event count must be a nonnegative integer")
    reason = outcome.get("reason", "")
    if not isinstance(reason, str):
        invalid("reason must be a string")
    if status in {"refused", "error"}:
        if questions or not reason.strip():
            invalid("refused/error requires a reason and empty questions")
        raise AgentReplyError(status, reason)
    if reason.strip() or (status == "needs_input") != bool(questions):
        invalid("completion contradicts outstanding questions or a failure reason")
    result = {"status": status, "questions": list(questions)}
    if discovery and "assessment" in outcome:
        result["assessment"] = outcome["assessment"]
    if adapter and "event_count" in outcome:
        result["event_count"] = outcome["event_count"]
    return result

# DECISION HISTORY
# ========================================
# - 2026-09-26 00:00 [python-coder]: Separate readiness assessment from coding evidence and preserve scoped advisory context. (#TICKETLESS reason=approved-ac-driven-discovery-contract)

# - 2026-09-30 00:00 [python-coder]: Illustrate readiness with concrete remaining coding work rather than completion claims. (#TICKETLESS reason=approved-ac-discovery-role-clarity)
