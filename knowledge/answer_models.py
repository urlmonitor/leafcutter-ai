"""MODULE: answer_models
GOAL: Define additive, bounded question-fulfillment contracts.
BUSINESS CONTEXT: Query execution cannot substitute for the requested facts.
ARCHITECTURE: Neutral transport types; no kernel or provider dependencies.
"""

from __future__ import annotations

from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Name = Annotated[str, Field(min_length=1, max_length=200)]
Level = Literal["L0", "L1", "L2", "L3"]


class AnswerScope(BaseModel):
    """Declared population, independent of whichever operation happens to run."""

    model_config = ConfigDict(extra="forbid")
    population: Literal["returned_entities", "ac_descendants", "declared_dependents"] = (
        "returned_entities"
    )
    root_id: Name | None = None
    levels: list[Level] | None = Field(default=None, max_length=4)
    inclusion: Literal["root_excluded", "terminal_leaves", "include_root"] | None = None


class AnswerRequirements(BaseModel):
    """Original question and the facts required to fulfill it, retained on resume."""

    model_config = ConfigDict(extra="forbid")
    original_question: str = Field(min_length=1, max_length=4000)
    required_fields: list[Name] = Field(default_factory=list, max_length=32)
    scope: AnswerScope = Field(default_factory=AnswerScope)
    require_complete: bool = True

    @model_validator(mode="after")
    def distinct_fields(self) -> AnswerRequirements:
        """Reject repeated requirements rather than silently changing the contract."""
        if len(set(self.required_fields)) != len(self.required_fields):
            raise ValueError("required fields must be distinct")
        return self


class MissingField(BaseModel):
    """A missing requested fact and only its attributable availability reason."""

    model_config = ConfigDict(extra="forbid")
    canonical_id: str
    field: str
    reason: Literal[
        "canonical_absent", "projection_missing", "disclosure_omitted", "truncated", "unknown"
    ]


class PopulationCompleteness(BaseModel):
    """Known unique records are distinct from a proven complete population."""

    model_config = ConfigDict(extra="forbid")
    complete: bool = False
    known_count: int = 0
    exact_total: int | None = None
    limitations: list[str] = Field(default_factory=list)


class AnswerAssessment(BaseModel):
    """Deterministic evidence sufficiency, without inferred or fabricated facts."""

    model_config = ConfigDict(extra="forbid")
    status: Literal["fulfilled", "partial", "unresolved"]
    original_question: str
    required_fields: list[str]
    scope: AnswerScope
    missing_fields: list[MissingField] = Field(default_factory=list)
    completeness: PopulationCompleteness
    work_status_counts: dict[str, int] | None = None
    known_work_status_counts: dict[str, int] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)


# DECISION HISTORY
# ================================================================================
# - 2026-10-01 18:55 [python-coder]: Keep requested facts separate from execution success and preserve canonical field meaning. (#KM-500/KM-500e-2)
