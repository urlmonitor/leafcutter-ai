"""
MODULE: kernel.intent.questions
GOAL: Build the plain-language clarification questions the router asks a human (answer kinds, or
    the capabilities that could serve the request, as choices) and read an answered question
    back as text the classifier and router can use.
BUSINESS CONTEXT: A clarification is only useful if the person can answer it (Rev 3 section
    11.6): the question names no internal ids or jargon, offers concrete choices wherever the
    kernel has candidates, and still allows free text. A follow-up after an answer that did not
    help is a different question, never a repeat.
ARCHITECTURE: Pure builders returning RequestProposal objects (kind human, validated through the
    schema catalog). No scheduler imports. Choice ids are kernel ids (answer kinds, capability
    ids) and never appear in the question text; labels and consequences are user wording.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from kernel.contracts import CapabilityDescriptor, RequestKind, RequestProposal, schema_ids
from kernel.contracts.context import EnrichedContext
from kernel.contracts.entity_context import EntityContext
from kernel.contracts.interaction import Choice
from kernel.contracts.payloads import HumanQuestionRequestPayload
from kernel.intent.classify import (
    CHANGE,
    DECISION,
    EVIDENCE,
    IDEAS,
    ClarificationAnswer,
)

MAX_GOAL_CHARS = 200
MAX_LABEL_CHARS = 120
EXAMPLE_REPHRASINGS = ('"Decide which option to pick for ..."', '"Find where ... is defined in '
                       'this repository"', '"Suggest ideas to improve ..."')
_WHY_INTENT = ("Your request could fit more than one kind of answer, and guessing could send you "
               "down the wrong path.")
_WHY_ROUTING = "I could not tell which of my abilities fits your request."
_CHOICES = (
    (DECISION, "Choose between options or approaches",
     "You get a recommendation with its reasoning and the evidence behind it."),
    (EVIDENCE, "Find facts in this repository",
     "You get the relevant excerpts and where they come from."),
    (IDEAS, "Suggest ideas or options, without choosing",
     "You get proposals to consider; nothing is decided."),
    (CHANGE, "Implement or change something",
     "Not supported yet: this version is read-only and will say so."),
)


def kind_choices() -> list[Choice]:
    """Return the answer kinds a person can pick, in user terms."""
    return [Choice(id=kind, label=label, consequences=consequence)
            for kind, label, consequence in _CHOICES]


def shorten(text: str, limit: int) -> str:
    """Return text cut to `limit` characters with an ellipsis when it was longer."""
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[:limit - 3].rstrip() + "..."


def _proposal(goal: str, question: str, why: str, choices: list[Choice]) -> RequestProposal:
    """Build the human request: choices plus free text, answered by a human_answer.v1."""
    payload = HumanQuestionRequestPayload(question=question, choices=choices,
                                          free_text_allowed=True,
                                          why_research_cannot_settle=why)
    return RequestProposal(
        kind=RequestKind.HUMAN, goal=f"Ask what is meant by: {shorten(goal, MAX_GOAL_CHARS)}",
        question=question, payload_schema=schema_ids.HUMAN_QUESTION_REQUEST,
        payload=payload.model_dump(mode="json"),
        requested_output_schema=schema_ids.HUMAN_ANSWER)


def _follow_up(prior: ClarificationAnswer | None) -> str:
    """Return the lead-in of a follow-up question (empty for the first question)."""
    if prior is None:
        return ""
    return (f'You answered "{shorten(prior.text, MAX_GOAL_CHARS)}", but I still cannot tell what '
            "to do with it. ")


def intent_question(goal: str, prior: ClarificationAnswer | None = None, *,
                    context: EnrichedContext | EntityContext | None = None) -> RequestProposal:
    """Ask what kind of answer the goal needs, offering the answer kinds as choices."""
    question = (f'{_follow_up(prior)}What kind of answer would you like for "'
                f'{shorten(goal, MAX_GOAL_CHARS)}"? Pick the closest one, or say it in your own '
                "words, for example " + " or ".join(EXAMPLE_REPHRASINGS[:2]) + ".")
    why = _WHY_INTENT
    if isinstance(context, EntityContext):
        why = ("The recognized names explain references in the request, but do not establish "
               "which kind of answer you want.")
    elif context is not None:
        why = (f"Initial context gathering finished with status {context.status}: "
               f"{context.files_scanned} file(s) checked and {len(context.evidence)} excerpt(s) "
               "retained. That context still does not establish which kind of answer you want.")
        if context.limitations:
            why += " Limits: " + "; ".join(context.limitations[:3])
    return _proposal(goal, question, why, kind_choices())


def _first_sentence(text: str) -> str:
    """Return the first sentence of a capability description, bounded for a choice label."""
    sentence = text.strip().split(". ")[0].rstrip(".")
    return shorten(sentence, MAX_LABEL_CHARS)


def capability_question(goal: str, candidates: list[CapabilityDescriptor],
                        prior: ClarificationAnswer | None = None) -> RequestProposal:
    """Ask which of the eligible abilities fits the request, described in user terms."""
    choices = [Choice(id=d.id, label=_first_sentence(d.description)) for d in candidates]
    question = (f'{_follow_up(prior)}I am not sure how to handle this request: "'
                f'{shorten(goal, MAX_GOAL_CHARS)}". '
                + ("Which of these fits best? You can also say it in your own words."
                   if choices else "Please say it in your own words."))
    return _proposal(goal, question, _WHY_ROUTING, choices)


def unclear_message() -> str:
    """Return the plain message for a request that stayed unclear after the questions."""
    return ("unclear_request: I could not tell what to do with this request, even after your "
            "answer. Try rephrasing it, for example " + ", ".join(EXAMPLE_REPHRASINGS) + ".")


def repeated_message() -> str:
    """Return the plain message for a question that was already asked and has no new answer."""
    return ("unclear_request: I already asked about this request and have no new information. "
            "Please start again with a more specific request, for example "
            + ", ".join(EXAMPLE_REPHRASINGS) + ".")


def answer_of(request_payload: Mapping[str, Any], output: Mapping[str, Any] | None
              ) -> ClarificationAnswer | None:
    """Read an answered human question as text (a chosen option's label, or the free text).

    Args:
        request_payload: The human_question_request.v1 payload that was asked.
        output: The human_answer.v1 payload that came back (None while unanswered).

    Returns:
        ClarificationAnswer | None: None when nothing was answered.
    """
    if not output:
        return None
    if output.get("free_text"):
        return ClarificationAnswer(text=str(output["free_text"]))
    choice_id = output.get("choice_id")
    if not choice_id:
        return None
    labels = {c.get("id"): c.get("label") for c in request_payload.get("choices", [])
              if isinstance(c, Mapping)}
    return ClarificationAnswer(text=str(labels.get(choice_id) or choice_id),
                               choice_id=str(choice_id))


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 22:00 [python-coder]: Questions keep internal ids out of the text and offer the
#   answer kinds (or the eligible capabilities' first description sentence) as choices with free
#   text still allowed; a follow-up quotes the earlier answer and is a different question, so the
#   dedup guard does not mistake it for a repeat. (#KernelBootstrapV0/INTENT)
# - 2026-10-03 15:10 [python-coder]: Preserve verbatim goals and separate meaning, caller and clarification channels. (#DK-300/entity-context)
# ====================================================================
