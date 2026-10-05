"""
MODULE: kernel.providers.base
GOAL: The narrow Jev port: question specs, batches, normalised answers, results and errors.
BUSINESS CONTEXT: Jev is a bounded classifier the kernel asks literal questions; everything else
    (graphs, scheduler, tests) must depend on this port so the langchain-typesafe adapter (P3)
    stays replaceable and failures map to explicit, non-fabricated outcomes (Rev 3 section 13.4).
ARCHITECTURE: Only providers/jev.py (P3) imports the vendor SDK. Errors live here so the
    scripted test double and the adapter raise identical types.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Annotated, Literal, Protocol, runtime_checkable

from pydantic import Field, JsonValue

from kernel.contracts.base import CorrelationIds, KernelModel, canonical_json, sha256_hex
from kernel.contracts.capability import Usage
from kernel.contracts.verbatim import VerbatimJson


def json_strings(values: Iterable[str]) -> list[JsonValue]:
    """Return the strings as a JSON list (a plain list[str] is not a list[JsonValue] to mypy)."""
    out: list[JsonValue] = []
    out.extend(values)
    return out


class JevError(Exception):
    """Base for Jev provider errors.

    `completed_usage` is the usage of the provider calls of the same batch that finished before
    the error (a chunked assessment aborted after its first chunk): those calls were made and paid
    for, so the caller records them instead of losing them with the failed result.
    """

    completed_usage: Usage | None = None


class JevUnavailable(JevError):
    """Jev cannot be reached or rejected credentials; never a capability gap."""

    def __init__(self, reason: str = "jev unavailable") -> None:
        """Keep the reason as the message."""
        super().__init__(reason)
        self.reason = reason


class JevInvalidResponse(JevError):
    """Jev returned a malformed answer (missing id, unknown choice, bad probabilities)."""

    def __init__(self, reason: str = "invalid jev response") -> None:
        """Keep the reason as the message."""
        super().__init__(reason)
        self.reason = reason


class JevPayloadTooLarge(JevError):
    """The serialised state exceeds jev.max_state_chars; the caller must truncate."""

    def __init__(self, size: int = 0, limit: int = 0) -> None:
        """Build the message from the size and limit."""
        super().__init__(f"jev state too large: {size} > {limit}")
        self.size = size
        self.limit = limit


class QuestionSpec(KernelModel):
    """One literal question with a template id and version."""

    id: str = Field(min_length=1)
    kind: Literal["noul", "choice", "score"]
    template_id: str
    template_version: str
    instructions: str | dict[str, JsonValue]
    criteria: dict[str, str] | list[str] | None = None


class JevBatch(KernelModel):
    """Questions sharing one state, sent in a single provider call."""

    purpose: str = Field(min_length=1)
    state: dict[str, VerbatimJson]
    questions: list[QuestionSpec] = Field(min_length=1)
    correlation: CorrelationIds = Field(default_factory=CorrelationIds)

    def input_fingerprint(self) -> str:
        """Return a sha256 over the state and questions (for trace records)."""
        body = {"state": self.state, "questions": [q.model_dump(mode="json")
                                                   for q in self.questions]}
        return sha256_hex(canonical_json(body))


class NoulAnswer(KernelModel):
    """Answer to a yes/no style question: probability that the statement holds."""

    kind: Literal["noul"] = "noul"
    question_id: str = ""
    probability: float = Field(ge=0.0, le=1.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class ChoiceAnswer(KernelModel):
    """Answer to a choice question: distribution over the criteria and the chosen one."""

    kind: Literal["choice"] = "choice"
    question_id: str = ""
    choice: str
    probabilities: dict[str, float]
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class ScoreAnswer(KernelModel):
    """Answer to a score question."""

    kind: Literal["score"] = "score"
    question_id: str = ""
    score: float
    probabilities: dict[str, float] = Field(default_factory=dict)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


Answer = Annotated[NoulAnswer | ChoiceAnswer | ScoreAnswer, Field(discriminator="kind")]


class JevResult(KernelModel):
    """Normalised provider result; usage unknowns stay None."""

    model_id: str | None = None
    request_id: str | None = None
    answers: dict[str, Answer]
    usage: Usage
    latency_ms: int | None = Field(default=None, ge=0)
    input_fingerprint: str | None = None
    adapter_version: str | None = None

    def noul(self, question_id: str) -> NoulAnswer:
        """Return the answer to question_id, which must be a NoulAnswer."""
        answer = self.answers[question_id]
        if not isinstance(answer, NoulAnswer):
            reason = f"{question_id} is not a noul answer"
            raise JevInvalidResponse(reason)
        return answer

    def choice(self, question_id: str) -> ChoiceAnswer:
        """Return the answer to question_id, which must be a ChoiceAnswer."""
        answer = self.answers[question_id]
        if not isinstance(answer, ChoiceAnswer):
            reason = f"{question_id} is not a choice answer"
            raise JevInvalidResponse(reason)
        return answer


@runtime_checkable
class JevPort(Protocol):
    """Port every graph uses to ask Jev questions."""

    async def assess(self, batch: JevBatch) -> JevResult:
        """Answer every question in the batch.

        Raises:
            JevUnavailable: The provider cannot be reached or credentials are rejected.
            JevInvalidResponse: The provider answered malformed.
            JevPayloadTooLarge: The state exceeds the configured size.
        """


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: JevError carries `completed_usage` so a chunked assessment that
#   aborts midway still reports the calls it made. (#KernelV01/E)
# - 2026-09-30 22:00 [python-coder]: JevUnavailable, JevInvalidResponse and JevPayloadTooLarge
#   are defined here (not in jev_errors.py) because ScriptedJev must raise them in P1; P3's
#   jev_errors.py may re-export and add adapter-only errors. (#KernelBootstrapV0/P1)
# - 2026-10-03 15:10 [python-coder]: Preserve verbatim goals and separate meaning, caller and clarification channels. (#DK-300/entity-context)
# ====================================================================
