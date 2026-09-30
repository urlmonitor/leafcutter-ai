"""
MODULE: kernel.contracts.interaction
GOAL: Host work requests, human questions and interaction submissions (Rev 3 section 7.8).
BUSINESS CONTEXT: Generative host output must never impersonate a human answer or approve a
    policy; the contract makes that structural by tying actor kind to the response schema.
ARCHITECTURE: Packets are persisted exactly as delivered to the client. Submission validation
    against the pending interaction (state revision, kind) is done by the resume path (P6).
"""

from __future__ import annotations

from pydantic import Field, JsonValue, model_validator

from kernel.contracts import schema_ids
from kernel.contracts.base import (
    KernelModel,
    PersistedModel,
    StableId,
    TraceContext,
    fail,
)
from kernel.contracts.capability import Usage
from kernel.contracts.evidence import EvidenceInput
from kernel.contracts.task import Actor


class Choice(KernelModel):
    """One offered answer to a human question, with its consequences."""

    id: StableId
    label: str = Field(min_length=1)
    consequences: str = ""


class ContextLimits(KernelModel):
    """Bounds on what the host may read or return."""

    max_input_chars: int | None = Field(default=None, ge=1)
    max_output_chars: int | None = Field(default=None, ge=1)


class Rejection(KernelModel):
    """A rejected submission attempt recorded on the pending host request."""

    code: str
    message: str = ""


class HostWorkRequest(PersistedModel):
    """Bounded work handed to the cooperative host (exactly one operation)."""

    work_item_id: str
    invocation_id: str | None = None
    operation: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    input_artifact_refs: list[str] = Field(default_factory=list)
    input_evidence_ids: list[str] = Field(default_factory=list)
    allowed_operations: list[str] = Field(default_factory=list)
    forbidden_operations: list[str] = Field(default_factory=list)
    output_schema_id: str
    output_json_schema: dict[str, JsonValue] = Field(default_factory=dict)
    output_requirements: list[str] = Field(default_factory=list)
    context_limits: ContextLimits = Field(default_factory=ContextLimits)
    trace_context: TraceContext = Field(default_factory=TraceContext)
    state_revision: int = Field(ge=0)
    attempt: int = Field(default=1, ge=1)
    rejections: list[Rejection] = Field(default_factory=list)

    @model_validator(mode="after")
    def _known_output_schema(self) -> HostWorkRequest:
        """The expected output must be a registered schema id."""
        if self.output_schema_id not in schema_ids.KNOWN_SCHEMA_IDS:
            fail(f"unknown output_schema_id {self.output_schema_id}")
        return self


class HumanQuestion(PersistedModel):
    """A question only a human can settle; silence never answers it."""

    work_item_id: str
    decision_id: str | None = None
    subject_ids: list[str] = Field(default_factory=list)
    question: str = Field(min_length=1)
    relevant_evidence_ids: list[str] = Field(default_factory=list)
    choices: list[Choice] = Field(default_factory=list)
    free_text_allowed: bool = False
    structured_allowed: bool = False
    why_research_cannot_settle: str = ""
    required_actor_kind: str = Field(default="human", pattern="^human$")
    state_revision: int = Field(ge=0)

    @model_validator(mode="after")
    def _answerable(self) -> HumanQuestion:
        """A question must offer choices, allow free text or allow a structured answer."""
        if not self.choices and not self.free_text_allowed and not self.structured_allowed:
            fail("a human question needs choices, free_text_allowed or structured_allowed")
        return self


class InteractionSubmission(KernelModel):
    """Client response to a pending interaction (unknown fields rejected)."""

    run_id: str
    interaction_id: str
    expected_state_revision: int = Field(ge=0)
    actor: Actor
    relayed_by: str | None = None
    response_schema_id: str
    response: dict[str, JsonValue]
    new_evidence: list[EvidenceInput] = Field(default_factory=list)
    usage: list[Usage] = Field(default_factory=list)

    @model_validator(mode="after")
    def _actor_matches_schema(self) -> InteractionSubmission:
        """Only a human actor may submit human_answer.v1, and a human submits nothing else."""
        is_answer = self.response_schema_id == schema_ids.HUMAN_ANSWER
        is_human = self.actor.kind.value == "human"
        if is_answer != is_human:
            fail("human_answer.v1 must come from a human actor, and only from one")
        if self.response_schema_id not in schema_ids.KNOWN_SCHEMA_IDS:
            fail(f"unknown response_schema_id {self.response_schema_id}")
        return self


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:40 [python-coder]: HostWorkRequest.output_requirements states rules JSON Schema
#   cannot express (generated options are proposals a human approves). (#KernelBootstrapV0/P6)
# - 2026-09-30 23:30 [python-coder]: HumanQuestion.structured_allowed marks approve-or-edit
#   questions that accept a structured answer. (#KernelBootstrapV0/P6)
# - 2026-09-30 22:00 [python-coder]: Actor kind and response schema are bound in both directions
#   so a generative host result cannot impersonate a human answer (spec section 7.8).
#   (#KernelBootstrapV0/P1)
# ====================================================================
