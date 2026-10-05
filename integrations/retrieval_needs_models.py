"""MODULE: retrieval_needs_models
GOAL: Bound the input and output of the standalone retrieval-needs experiment.
BUSINESS CONTEXT: Preserve what an agent needs without choosing or executing retrieval.
ARCHITECTURE: Frozen experiment contracts; no registry or production-flow integration.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import ConfigDict, Field, JsonValue, model_validator

from kernel.contracts.base import KernelModel, fail
from kernel.providers.base import JevResult

MULTI_DIMENSIONS = ("entity_types", "target_ids", "required_fields", "document_types", "relationships")
ID_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]*(?:-[A-Z]+)*-\d+[a-z]?(?:-\d+)?(?:-[ivx]+)?\b")


class NeedsCatalog(KernelModel):
    """Finite semantic offers, independent of current database capabilities."""

    entity_types: dict[str, str] = Field(default_factory=dict)
    target_ids: dict[str, str] = Field(default_factory=dict)
    required_fields: dict[str, str] = Field(default_factory=dict)
    document_types: dict[str, str] = Field(default_factory=dict)
    relationships: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def bounded_options(self) -> NeedsCatalog:
        """Reject unbounded labels/descriptions rather than silently clipping offers."""
        for dimension in MULTI_DIMENSIONS:
            options = getattr(self, dimension)
            if len(options) > 64:
                fail(f"Too many offers for {dimension}; maximum is 64")
            for label, description in options.items():
                if not label or len(label) > 128 or not description or len(description) > 1200:
                    fail(f"Invalid bounded offer in {dimension}")
        return self


class NeedsRequest(KernelModel):
    """Question and supplied context, never augmented with hidden answer labels."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=False)
    original_question: str = Field(min_length=1, max_length=8000)
    context: list[str] = Field(default_factory=list, max_length=32)
    known_ids: list[str] = Field(default_factory=list, max_length=64)
    source_scope: dict[str, JsonValue] = Field(default_factory=dict)
    catalog: NeedsCatalog

    @model_validator(mode="after")
    def grounded_ids(self) -> NeedsRequest:
        """Allow only literal targets or explicitly supplied observed candidates."""
        if not self.original_question.strip():
            fail("The original question must contain text")
        if any(len(item) > 8000 for item in self.context):
            fail("Each supplied context item is limited to 8000 characters")
        for identifier in (*self.known_ids, *self.catalog.target_ids):
            if not identifier or len(identifier) > 128:
                fail("Target IDs must contain 1 to 128 characters")
        for identifier in self.catalog.target_ids:
            if identifier not in self.known_ids and not literal_in_question(identifier, self.original_question):
                fail(f"Ungrounded target candidate: {identifier}")
        return self


def literal_in_question(identifier: str, question: str) -> bool:
    """Recognize an offered exact target without accepting an ID substring."""
    return re.search(r"(?<![\w-])" + re.escape(identifier) + r"(?![\w-])", question) is not None


def target_candidates(request: NeedsRequest) -> dict[str, str]:
    """Combine literal canonical IDs and supplied candidates without semantic guessing."""
    targets = dict(request.catalog.target_ids)
    for identifier in request.known_ids:
        targets.setdefault(identifier, "Caller-supplied observed candidate; not necessarily the target.")
    for identifier in ID_PATTERN.findall(request.original_question):
        targets.setdefault(identifier, "Literal identifier in the original question; assess its role.")
    return targets


class ProbeLimits(KernelModel):
    """Experiment-only bounds; they do not alter global kernel defaults."""

    max_questions_per_call: int = Field(default=128, ge=1, le=128)
    max_state_chars: int = Field(default=50000, ge=1)
    timeout_seconds: float = Field(default=120, gt=0)
    selected_probability: float = Field(default=0.7, gt=0.5, le=1)
    rejected_probability: float = Field(default=0.3, ge=0, lt=0.5)
    max_relation_depth: int = Field(default=3, ge=1, le=10)


class NeedsProbeResult(KernelModel):
    """A proposed information need, never a fulfilled answer or executable query."""

    original_question: str
    source_scope: dict[str, JsonValue]
    selections: dict[str, list[str]]
    uncertain: dict[str, list[str]]
    rejected: dict[str, list[str]]
    detail_mode: str
    completeness: str
    hierarchy_scope: str
    scope_resolution: str
    unresolved: list[str]
    status: Literal["decided", "needs_resolution"]
    response: JevResult
    provider_calls: int = Field(ge=0, le=1)
    max_relation_depth: int
    limitations: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=False)


# DECISION HISTORY
# ================================================================================
# - 2026-10-03 00:00 [python-coder]: Isolate user-authorized semantic experiment before integration. (#TICKETLESS reason=user-requested-standalone-experiment)
