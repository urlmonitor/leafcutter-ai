"""
MODULE: kernel.split.gate
GOAL: Build the split gate: the human question that offers the parts of a split record, each with
    its quote, the parts it waits for and its capability, before anything runs.
BUSINESS CONTEXT: ADR-053 and ADR-067 section 6: a person approves the split, and the wording is
    template text built from the record, never written by a model. The gate names the split id so
    an answer can be tied to it, and nothing runs until the person answers.
ARCHITECTURE: Pure functions from a Decomposition to a RequestProposal (kind human). The scheduler
    parks the split root on it like any clarification question; DK-400d-1 gives it its dedicated
    answer schema and the keep, reword, leave-out choices.
"""

from __future__ import annotations

from typing import Any

from kernel.contracts import Decomposition, Priority, RequestKind, RequestProposal, schema_ids
from kernel.contracts.interaction import Choice
from kernel.contracts.payloads import HumanQuestionRequestPayload

APPROVE = "approve"
REJECT = "reject"
WHY_PERSON = "Only a person may approve how a request is split; nothing runs until you answer."


def _part_lines(part: dict[str, Any], released: list[str]) -> list[str]:
    """Return the lines that show one offered part."""
    waits = ", ".join(part["depends_on"]) if part["depends_on"] else "no part"
    lines = [f"{part['id']}. {part['text']}", f'   Your words: "{part["covers"]}"',
             f"   Waits for: {waits}"]
    if released:
        lines.append(f"   No longer waits for {', '.join(released)} (set aside)")
    lines.append(f"   Capability: {part['child_capability']}")
    return lines


def gate_text(record: Decomposition, released: dict[str, list[str]]) -> str:
    """Return the question: the parts in proposed order, then what is shown read-only."""
    n = len(record.parts)
    lines = [f"Split {record.id}: I would answer your request as {n} separate parts. "
             "Each part quotes your own words. Nothing runs until you answer.", ""]
    for part in record.parts:
        lines += [*_part_lines(part, released.get(part["id"], [])), ""]
    if record.not_covered:
        lines.append("Not covered (" + str(record.not_covered[0]["reason"]) + "; ask again as a "
                     "request of its own):")
        lines += [f"   {p['id']}. {p['text']}" for p in record.not_covered]
        lines.append("")
    if record.dropped:
        lines.append("Set aside:")
        lines += [f"   {p['text']}\n      Your words, as quoted: \"{p['covers']}\"\n"
                  f"      ({p['reason']})" for p in record.dropped]
        lines.append("")
    lines.append("Approve this split, or reject it.")
    return "\n".join(lines)


def gate_proposal(record: Decomposition, released: dict[str, list[str]]) -> RequestProposal:
    """Return the human request that opens the split gate for the record."""
    question = gate_text(record, released)
    payload = HumanQuestionRequestPayload(
        question=question, why_research_cannot_settle=WHY_PERSON,
        choices=[Choice(id=APPROVE, label="Approve the split"),
                 Choice(id=REJECT, label="Reject the split")])
    return RequestProposal(
        kind=RequestKind.HUMAN, goal=f"Approve the split {record.id}"[:300], question=question,
        payload_schema=schema_ids.HUMAN_QUESTION_REQUEST,
        payload=payload.model_dump(mode="json"),
        requested_output_schema=schema_ids.HUMAN_ANSWER, priority=Priority.REQUIRED)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-09 [python-coder]: The gate shows each offered part's quote but not the subject text
#   verbatim: the parts' quotes are the reviewable content and the subject is on the split record.
#   DK-400d-1 owns the final gate wording. (#TICKET-20261006-DK-400c-1)
# ====================================================================
