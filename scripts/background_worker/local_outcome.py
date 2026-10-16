"""
MODULE: local_outcome
GOAL: Validate local harness events against phase-specific reply contracts.
BUSINESS CONTEXT: Model claims must not substitute for completed coding tool execution.
ARCHITECTURE: The adapter parses final replies and exposes bounded failure diagnostics.
"""

from collections import Counter
import json

from .execution_boundary import safe_output
from .reply_contract import AgentReplyError, validate_reply


def parse_events(stdout):
    """Read JSON events while ignoring unrelated process output."""
    events = []
    for line in stdout.splitlines():
        try:
            value = json.loads(line)
        except (ValueError, TypeError):
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


def event_diagnostics(events):
    """Summarize bounded events without retaining reasoning or source dumps."""
    commands, errors, messages = [], [], []
    types = Counter()
    for event in events:
        kind = safe_output(event.get("type", "unknown"))[:60]
        types[kind] += 1
        item = event.get("item")
        if isinstance(item, dict) and event.get("type") == "item.completed":
            if item.get("type") in {"command_execution", "file_change"}:
                detail = {"type": item["type"]}
                if "exit_code" in item:
                    detail["exit_code"] = item["exit_code"] if type(item["exit_code"]) is int else None
                if "status" in item:
                    detail["status"] = safe_output(item["status"])[:60]
                if item.get("exit_code", 0) != 0 or item.get("status") == "failed":
                    detail["error_output"] = safe_output(item.get("aggregated_output", ""))[-500:]
                commands.append(detail)
            elif item.get("type") == "agent_message":
                messages.append(safe_output(item.get("text", ""))[-800:])
        if event.get("type") in {"error", "turn.failed"}:
            errors.append(safe_output(event.get("message", event.get("error", "")))[-500:])
    return {"kind": "local_harness", "event_count": len(events),
            "event_types": dict(types.most_common(12)), "tools": commands[-8:],
            "errors": errors[-3:], "final_message": messages[-1] if messages else ""}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON outcome key")
        result[key] = value
    return result


def parse_outcome(stdout, *, discovery=False):
    """Enforce phase-specific readiness or actual coding execution evidence."""
    events = parse_events(stdout)

    def reject(message, cause=None):
        error = AgentReplyError("protocol_error", message)
        error.evidence = {**event_diagnostics(events), "reply_kind": error.reply_kind}
        raise error from cause

    if not any(event.get("type") == "turn.completed" for event in events):
        reject("Local harness returned no completed turn; cannot infer success")
    if any(event.get("type") in {"turn.failed", "error"} for event in events):
        reject("Local harness reported an execution failure")
    items = [event["item"] for event in events if event.get("type") == "item.completed"
             and isinstance(event.get("item"), dict)]
    messages = [item.get("text", "") for item in items if item.get("type") == "agent_message"]
    try:
        outcome = json.loads(messages[-1], object_pairs_hook=_unique_object)
    except (IndexError, ValueError, TypeError) as exc:
        reject("Local harness did not provide a structured completion/needs_input outcome", exc)
    try:
        outcome = validate_reply(outcome, discovery=discovery)
    except AgentReplyError as exc:
        exc.evidence = {**event_diagnostics(events), "reply_kind": exc.reply_kind,
                        "reason": exc.evidence["reason"]}
        raise
    if outcome["status"] == "needs_input":
        return outcome
    if discovery:
        return outcome
    if not any((item.get("type") == "command_execution" and type(item.get("exit_code")) is int and item["exit_code"] == 0)
               or (item.get("type") == "file_change" and item.get("status") == "completed")
               for item in items):
        reject("Local harness produced no actual tool execution evidence")
    return {"status": "completed", "questions": [], "event_count": len(events)}

# DECISION HISTORY
# ========================================
# - 2026-09-26 00:00 [python-coder]: Separate readiness assessment from coding evidence and preserve scoped advisory context. (#TICKETLESS reason=approved-ac-driven-discovery-contract)
# - 2026-09-30 00:00 [python-coder]: Remove unused generation-schema file transport while preserving strict post-turn validation. (#TICKETLESS reason=approved-ac-local-schema-transport)
