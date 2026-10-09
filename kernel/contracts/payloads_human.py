"""
MODULE: kernel.contracts.payloads_human
GOAL: Payload models for the human-facing schema ids: the question the kernel asks a human and
    the answer a human gives (a choice, free text, or a structured approve-or-edit answer).
BUSINESS CONTEXT: A human answer settles what research cannot, so its shape is validated
    strictly (exactly one mode, unique ids) before it can change a decision.
ARCHITECTURE: Split out of `kernel.contracts.payloads`, which re-exports these names, to stay
    under the file-size limit. Reference checks (cited ids exist) live in schema_catalog.
"""

from __future__ import annotations

from pydantic import Field, model_validator

from kernel.contracts.base import KernelModel, StableId, fail
from kernel.contracts.enums import Priority
from kernel.contracts.interaction import Choice


def unique_ids(ids: list[str], what: str) -> None:
    """Fail if ids contains duplicates."""
    if len(ids) != len(set(ids)):
        fail(f"duplicate {what} ids")


class HumanQuestionRequestPayload(KernelModel):
    """leafcutter.human_question_request.v1."""

    question: str = Field(min_length=1)
    """What to ask the human."""
    choices: list[Choice] = Field(default_factory=list)
    """Answers offered to the human, each with its consequences."""
    free_text_allowed: bool = False
    """Whether the human may answer in their own words."""
    structured_allowed: bool = False
    (
        "Whether the human may answer with an approve-or-edit answer about proposed criteria and "
        "options."
    )
    why_research_cannot_settle: str = ""
    """Why evidence cannot settle this, shown so the human understands why they are asked."""
    decision_id: str | None = None
    """The decision the question belongs to, so the answer returns to it."""
    subject_ids: list[str] = Field(default_factory=list)
    (
        "Ids of the options or criteria the question is about; a structured answer may cite only "
        "these."
    )
    evidence_ids: list[str] = Field(default_factory=list)
    """Evidence the question rests on (shown to the human as relevant evidence)."""

    @model_validator(mode="after")
    def _answerable(self) -> HumanQuestionRequestPayload:
        """Offer choices, free text or a structured answer; choice ids must be unique."""
        if not self.choices and not self.free_text_allowed and not self.structured_allowed:
            fail("offer choices or allow free text or a structured answer")
        unique_ids([c.id for c in self.choices], "choice")
        return self


class CriterionEdit(KernelModel):
    """One criterion the human supplies or edits inside a structured approval answer."""

    id: StableId | None = None
    """Id of the pending proposal being edited; omitted for a criterion the human adds."""
    question: str = Field(min_length=1)
    """The criterion's question as the human wants it."""
    priority: Priority = Priority.REQUIRED
    (
        "Whether the human's criterion blocks resolution (required) or only weighs in the "
        "ranking (supporting)."
    )


class AddedOption(KernelModel):
    """One option the human adds inside a structured approval answer."""

    title: str = Field(min_length=1)
    """Short name of the option the human adds."""
    description: str = ""
    """What the human's option means, used to research and compare it."""


class HumanAnswerPayload(KernelModel):
    """leafcutter.human_answer.v1: one of choice_id, free_text or a structured answer.

    The pair {choice_id, free_text} is also one mode: a choice with a condition. The choice is
    authoritative and the text is recorded verbatim as the condition.

    The structured answer answers an approve-or-edit question about proposed criteria and
    options: `approved_*_ids` approve a subset (the listed ids are approved, every other pending
    proposal of that kind is declined) and `edited_criteria` replaces the pending criteria by the
    human's own (an entry with the id of a proposal edits it, an entry without an id is new).
    """

    choice_id: str | None = None
    """Id of the offered choice the human picked."""
    free_text: str | None = None
    (
        "The human's own words; with a choice_id it is recorded verbatim as a condition on that "
        "choice."
    )
    approved_option_ids: list[str] | None = None
    """Pending options the human approves; every other pending option is declined."""
    approved_criterion_ids: list[str] | None = None
    """Pending criteria the human approves; every other pending criterion is declined."""
    edited_criteria: list[CriterionEdit] | None = Field(default=None, min_length=1)
    (
        "The human's own criteria, replacing the pending proposals (an entry with a proposal's "
        "id edits it, one without is new)."
    )
    added_options: list[AddedOption] | None = Field(default=None, min_length=1)
    """Options the human adds (they become human-supplied, approved options)."""

    @property
    def is_structured(self) -> bool:
        """True if any structured approval field is set."""
        return any(v is not None for v in (self.approved_option_ids, self.approved_criterion_ids,
                                           self.edited_criteria, self.added_options))

    @model_validator(mode="after")
    def _exactly_one(self) -> HumanAnswerPayload:
        """One mode must be set: a choice (optionally with free text), free text or structure."""
        has_text = bool(self.free_text and self.free_text.strip())
        modes = [self.choice_id is not None, has_text, self.is_structured]
        is_pair = self.choice_id is not None and has_text and not self.is_structured
        if sum(modes) != 1 and not is_pair:
            fail("set exactly one of choice_id, free_text and a structured approval answer "
                 "(a choice may carry free text as its condition)")
        if self.approved_criterion_ids is not None and self.edited_criteria is not None:
            fail("approved_criterion_ids and edited_criteria are alternatives")
        unique_ids(self.approved_option_ids or [], "approved option")
        unique_ids(self.approved_criterion_ids or [], "approved criterion")
        unique_ids([e.id for e in self.edited_criteria or [] if e.id], "edited criterion")
        return self


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-09 [python-coder]: Split out of payloads.py with their field purposes; the import path
#   kernel.contracts.payloads still works. (#TICKET-20261009-KernelContractFieldDescriptions)
# ====================================================================
