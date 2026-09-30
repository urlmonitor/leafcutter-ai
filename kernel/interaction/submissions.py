"""
MODULE: kernel.interaction.submissions
GOAL: Validate one interaction submission against the pending interaction and classify every
    refusal with a stable rejection code (Rev 3 sections 7.8, 11.6 and 13.3).
BUSINESS CONTEXT: A submission is the only way outside content enters a waiting run, so it must
    name the interaction the kernel issued and the revision it was issued at, come from the right
    kind of actor, and pass schema and reference checks. A generative host result can therefore
    never answer a human question, approve, or grant permissions.
ARCHITECTURE: `check_submission` is a pure function over the graph state values and the raw
    resume value; the scheduler node and the submission service both call it, so they can never
    disagree. The order of the checks fixes which code a bad submission gets.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pydantic import ValidationError

from kernel.contracts import (
    ActorKind,
    HostWorkRequest,
    HumanQuestion,
    InteractionSubmission,
    PayloadValidationError,
    SemanticContext,
    SemanticValidationError,
    WorkItemStatus,
    canonical_json,
    schema_ids,
    sha256_hex,
    validate_payload,
    validate_semantics,
)
from kernel.contracts.payloads import HumanAnswerPayload


class RejectionCode(StrEnum):
    """Stable codes a client may branch on (never renamed)."""

    STALE_REVISION = "stale_revision"
    NOT_PENDING = "not_pending"
    WRONG_KIND = "wrong_kind"
    ACTOR_MISMATCH = "actor_mismatch"
    SCHEMA_INVALID = "schema_invalid"
    SEMANTIC_INVALID = "semantic_invalid"
    FORGED_ID = "forged_id"
    CANCELLED_OR_SUPERSEDED = "cancelled_or_superseded"


_DEAD_STATUSES = frozenset({WorkItemStatus.CANCELLED, WorkItemStatus.FAILED,
                            WorkItemStatus.BLOCKED})
_REQUIRED_KEYS = ("run_id", "interaction_id", "expected_state_revision", "actor",
                  "response_schema_id", "response")


@dataclass(frozen=True)
class Verdict:
    """Outcome of checking one submission: accepted (with the parsed model) or one rejection."""

    code: RejectionCode | None = None
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    submission: InteractionSubmission | None = None
    repairable: bool = False

    @property
    def ok(self) -> bool:
        """True if the submission may be applied."""
        return self.code is None


def reject(code: RejectionCode, message: str, *, repairable: bool = False, **details: Any
           ) -> Verdict:
    """Build a rejecting verdict (repairable: a host may resend corrected content)."""
    return Verdict(code=code, message=message, details=dict(details), repairable=repairable)


def submission_hash(submission: InteractionSubmission) -> str:
    """Return the sha256 of the canonical JSON of a parsed submission (the ledger key)."""
    return sha256_hex(canonical_json(submission.model_dump(mode="json")))


def pending_packet(state: Mapping[str, Any]) -> HostWorkRequest | HumanQuestion | None:
    """Return the packet at the head of the interaction queue, or None if nothing is pending."""
    queue = state.get("interaction_queue") or []
    return state.get("interactions", {}).get(queue[0]) if queue else None


def _shape_problem(raw: object) -> str:
    """Return why the raw value is not even a submission object, or an empty string."""
    if not isinstance(raw, Mapping):
        return "a submission must be a JSON object"
    missing = [k for k in _REQUIRED_KEYS if k not in raw]
    if missing:
        return f"missing fields: {', '.join(missing)}"
    if not (isinstance(raw["run_id"], str) and isinstance(raw["interaction_id"], str)
            and isinstance(raw["response_schema_id"], str)
            and isinstance(raw["actor"], Mapping)):
        return "run_id, interaction_id, response_schema_id and actor have the wrong type"
    revision = raw["expected_state_revision"]
    if not isinstance(revision, int) or isinstance(revision, bool):
        return "expected_state_revision must be an integer"
    return ""


def _unpending(state: Mapping[str, Any], interaction_id: str) -> Verdict:
    """Classify a submission naming an interaction that is not the pending one."""
    packet = state.get("interactions", {}).get(interaction_id)
    if packet is None:
        return reject(RejectionCode.FORGED_ID, "the kernel never issued this interaction id",
                      interaction_id=interaction_id)
    item = state.get("work_items", {}).get(packet.work_item_id)
    if item is not None and item.status in _DEAD_STATUSES:
        return reject(RejectionCode.CANCELLED_OR_SUPERSEDED,
                      "the interaction was cancelled or superseded",
                      interaction_id=interaction_id)
    return reject(RejectionCode.NOT_PENDING, "the interaction is not the pending one",
                  interaction_id=interaction_id,
                  pending_interaction_id=(state.get("interaction_queue") or [None])[0])


def _expectation(packet: HostWorkRequest | HumanQuestion) -> tuple[str, ActorKind]:
    """Return the response schema id and actor kind a packet accepts."""
    if isinstance(packet, HumanQuestion):
        return schema_ids.HUMAN_ANSWER, ActorKind.HUMAN
    return packet.output_schema_id, ActorKind.HOST


def _route_problem(raw: Mapping[str, Any], packet: HostWorkRequest | HumanQuestion,
                   state: Mapping[str, Any]) -> Verdict | None:
    """Check run, interaction, revision, kind and actor; return a rejection or None."""
    if raw["run_id"] != state.get("run_id"):
        return reject(RejectionCode.FORGED_ID, "the run id is not this run's",
                      run_id=raw["run_id"])
    if raw["interaction_id"] != packet.id:
        return _unpending(state, raw["interaction_id"])
    revision = state.get("state_revision", 0)
    if raw["expected_state_revision"] != revision:
        return reject(RejectionCode.STALE_REVISION, "the state revision is stale",
                      expected_state_revision=raw["expected_state_revision"],
                      state_revision=revision)
    schema, actor_kind = _expectation(packet)
    if raw["response_schema_id"] != schema:
        return reject(RejectionCode.WRONG_KIND, "the response schema does not fit this interaction",
                      expected_schema=schema, got_schema=raw["response_schema_id"])
    if raw["actor"].get("kind") != actor_kind.value:
        return reject(RejectionCode.ACTOR_MISMATCH,
                      f"this interaction accepts only a {actor_kind.value} actor",
                      expected_actor_kind=actor_kind.value, got_actor_kind=raw["actor"].get("kind"))
    return None


def _answer_problem(packet: HumanQuestion, payload: HumanAnswerPayload) -> list[str]:
    """Return why a validated answer is not one the question allows (empty list if allowed)."""
    if payload.free_text and not packet.free_text_allowed:
        return ["free text is not allowed for this question"]
    if payload.is_structured and not packet.structured_allowed:
        return ["a structured answer is not allowed for this question"]
    return []


def _semantic_context(packet: HostWorkRequest | HumanQuestion, state: Mapping[str, Any]
                      ) -> SemanticContext:
    """Return the ids this run knows, plus what the human question offered."""
    human = isinstance(packet, HumanQuestion)
    return SemanticContext(
        known_evidence_ids=frozenset(state.get("evidence", {})),
        known_finding_ids=frozenset(state.get("findings", {})),
        offered_choice_ids=frozenset(c.id for c in packet.choices) if human else None,
        subject_ids=frozenset(packet.subject_ids) if human else None)


def _content_problem(submission: InteractionSubmission, packet: HostWorkRequest | HumanQuestion,
                     state: Mapping[str, Any]) -> Verdict | None:
    """Validate the response payload structurally and semantically; return a rejection or None."""
    schema, _ = _expectation(packet)
    try:
        payload = validate_payload(schema, dict(submission.response))
    except PayloadValidationError as exc:
        return reject(RejectionCode.SCHEMA_INVALID, "the response does not match its schema",
                      repairable=True, schema_id=schema, detail=exc.detail[:1500])
    extra = _answer_problem(packet, payload) if isinstance(packet, HumanQuestion) \
        and isinstance(payload, HumanAnswerPayload) else []
    try:
        validate_semantics(schema, payload, _semantic_context(packet, state))
    except SemanticValidationError as exc:
        extra = [*extra, *exc.violations]
    if extra:
        return reject(RejectionCode.SEMANTIC_INVALID, "; ".join(extra), repairable=True,
                      violations=extra)
    return None


def check_submission(raw: object, state: Mapping[str, Any]) -> Verdict:
    """Check a raw submission against the pending interaction of the run state.

    Args:
        raw: The resume value as received (parsed JSON, never trusted).
        state: The graph state values (`interaction_queue`, `interactions`, `state_revision`,
            `evidence`, `work_items`, `run_id`).

    Returns:
        Verdict: Accepted with the parsed submission, or rejected with one stable code. The
            order is: shape, run, interaction, revision, kind, actor, full model, payload
            schema, semantics.
    """
    problem = _shape_problem(raw)
    if problem or not isinstance(raw, Mapping):
        return reject(RejectionCode.SCHEMA_INVALID, problem or "malformed submission")
    packet = pending_packet(state)
    if packet is None:
        return _unpending(state, raw["interaction_id"])
    refused = _route_problem(raw, packet, state)
    if refused is not None:
        return refused
    try:
        submission = InteractionSubmission.model_validate(dict(raw))
    except ValidationError as exc:
        return reject(RejectionCode.SCHEMA_INVALID, "the submission has invalid fields",
                      detail=str(exc)[:1500])
    refused = _content_problem(submission, packet, state)
    return refused if refused is not None else Verdict(submission=submission)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:45 [python-coder]: Schema mismatch is `wrong_kind` and actor-kind mismatch is
#   `actor_mismatch`; the schema is checked first, so a host sending findings to a human question
#   is wrong_kind and a host sending human_answer.v1 is actor_mismatch. The prompt's code list
#   replaces design part 5's stale_submission/kind_mismatch/conflicting_duplicate/run_cancelled.
#   (#KernelBootstrapV0/P6)
# - 2026-09-30 23:45 [python-coder]: The contract validator would turn a human actor on a host
#   schema into one generic schema error, so routing checks read the raw fields first to give the
#   precise code. (#KernelBootstrapV0/P6)
# ====================================================================
