"""
MODULE: kernel.capabilities.host.formulate_question
GOAL: The `host.formulate_question` operation: compile the rewording task and convert the host's
    answer into a human_question_request.v1 that keeps exactly the questions, choices and flags
    the kernel asked to have worded.
BUSINESS CONTEXT: Rev 3 section 11.6: Claude may formulate the wording, but the pending
    interaction is created by Leafcutter. The host therefore supplies wording only; it cannot add
    or remove a choice, change what the answer allows, name a different decision, or answer the
    question itself. The kernel later turns the converted payload into a HumanQuestion, which only
    a human actor can answer.
ARCHITECTURE: Extends HostOperation. Request and answer share human_question_request.v1. The
    converted payload starts from the ORIGINAL request and adopts only the host's question text
    and the label and consequences of choices that keep their id; everything else comes from the
    request, and every discarded deviation becomes a limitation.
"""

from __future__ import annotations

from typing import Any

from kernel.capabilities.host.base import HostOperation, invalid_output
from kernel.capabilities.host.sanitize import completed_result
from kernel.capabilities.host.spec import HostConversion
from kernel.contracts import CapabilityResult, schema_ids
from kernel.contracts.interaction import Choice
from kernel.contracts.payloads import HumanQuestionRequestPayload


def _reworded(original: list[Choice], offered: list[Choice], notes: list[str]) -> list[Choice]:
    """Return the original choices with the host's label and consequences where ids match."""
    by_id = {c.id: c for c in offered}
    if set(by_id) != {c.id for c in original}:
        notes.append("the host added, removed or renamed choices; the original choice ids were "
                     "kept")
    return [Choice(id=c.id, label=by_id[c.id].label if c.id in by_id else c.label,
                   consequences=by_id[c.id].consequences if c.id in by_id else c.consequences)
            for c in original]


class FormulateQuestion(HostOperation):
    """host.formulate_question: reword a human question without changing what it asks."""

    capability_id = "host.formulate_question"
    operation = "formulate_question"
    request_model = HumanQuestionRequestPayload
    output_model = HumanQuestionRequestPayload

    def task_text(self, request: Any, goal: str) -> str:
        """Return the rewording task for the request's question."""
        if request is None:
            return super().task_text(request, goal)
        return ("Reword this question so a person can answer it without the surrounding context, "
                f"without changing what is asked: {request.question}")

    def requirements(self, request: Any) -> list[str]:
        """Return the rules that keep the wording from changing the question's meaning."""
        lines = ["Change wording only: keep every choice id, do not add, remove or reorder "
                 "choices, and keep free_text_allowed, structured_allowed, decision_id and "
                 "subject_ids as given.",
                 "Do not answer the question, recommend a choice or approve anything; a person "
                 "answers it later."]
        if request is not None and request.choices:
            lines.append("Choice ids to keep: " + ", ".join(c.id for c in request.choices))
        return lines

    def convert_payload(self, ctx: HostConversion, payload: HumanQuestionRequestPayload
                        ) -> CapabilityResult:
        """Return the original question with only the host's wording applied."""
        original = self.parse_request(ctx.invocation.input_payload)
        if original is None:
            return invalid_output(ctx, "the original question is unavailable, so the wording "
                                       "cannot be applied")
        notes: list[str] = []
        for name in ("free_text_allowed", "structured_allowed", "decision_id", "subject_ids"):
            if getattr(payload, name) != getattr(original, name):
                notes.append(f"the host changed {name}; the original value was kept")
        body = original.model_copy(update={
            "question": payload.question,
            "choices": _reworded(original.choices, payload.choices, notes)})
        return completed_result(ctx, schema_ids.HUMAN_QUESTION_REQUEST, body, limitations=[
            "only the wording was taken from the host; the kernel creates the interaction",
            *notes])


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 11:35 [python-coder]: `why_research_cannot_settle` is kept from the request: it
#   states why a person is needed, which is the kernel's claim, not wording the host may
#   improve. (#KernelBootstrapV0/P8)
# ====================================================================
