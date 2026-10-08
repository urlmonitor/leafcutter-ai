"""MODULE: retrieval_needs
GOAL: Define model-neutral contracts for host interpretation of retrieval needs.
BUSINESS CONTEXT: Interpret the same bounded offers as the isolated Jev experiment.
ARCHITECTURE: Registered host payloads; no query execution or classifier promotion.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import ConfigDict, Field, JsonValue, field_validator, model_validator

from kernel.contracts.base import KernelModel, fail

DIMENSIONS = ("entity_types", "target_ids", "required_fields", "document_types", "relationships")
LITERAL_ID = re.compile(r"\b[A-Z][A-Z0-9]*(?:-[A-Z]+)*-\d+[a-z]?(?:-\d+)?(?:-[ivx]+)?\b")


def _dimensions(value: dict) -> dict:
    """Require all five known dimensions without permitting hidden extra fields."""
    if set(value) != set(DIMENSIONS):
        fail("Exactly the five retrieval-needs dimensions are required")
    return value


class RetrievalNeedsRequest(KernelModel):
    """Original question and bounded candidate meanings, independent of backend support."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=False)
    original_question: str = Field(min_length=1, max_length=8000)
    context: list[str] = Field(default_factory=list, max_length=32)
    known_ids: list[str] = Field(default_factory=list, max_length=64)
    source_scope: dict[str, JsonValue] = Field(default_factory=dict)
    catalog: dict[str, dict[str, str]]

    @field_validator("catalog")
    @classmethod
    def finite_catalog(cls, value: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
        """Refuse oversize offers rather than changing the interpreted vocabulary."""
        _dimensions(value)
        for options in value.values():
            if len(options) > 64:
                fail("A needs dimension may offer at most 64 values")
            for key, meaning in options.items():
                if not key or len(key) > 128 or not meaning or len(meaning) > 1200:
                    fail("Offer labels/descriptions must be nonempty and bounded")
        return value

    @model_validator(mode="after")
    def grounded_candidates(self) -> RetrievalNeedsRequest:
        """Validate identities/context before the system augments literal candidates."""
        if not self.original_question.strip() or any(len(text) > 8000 for text in self.context):
            fail("Question/context must contain bounded text")
        for identifier in (*self.known_ids, *self.catalog["target_ids"]):
            if not identifier or len(identifier) > 128:
                fail("Candidate identifiers must contain 1 to 128 characters")
        for identifier in self.catalog["target_ids"]:
            literal = re.search(r"(?<![\w-])" + re.escape(identifier) + r"(?![\w-])", self.original_question)
            if not literal and identifier not in self.known_ids:
                fail(f"Ungrounded target candidate: {identifier}")
        return self


class RetrievalNeedsOutput(KernelModel):
    """Host interpretation, never a retrieved answer or approval of a classifier."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=False)
    original_question: str = Field(min_length=1, max_length=8000)
    source_scope: dict[str, JsonValue]
    selections: dict[str, list[str]]
    uncertain: dict[str, list[str]]
    detail_mode: Literal["fields", "full_document", "bounded_context", "unknown"]
    completeness: Literal["single_entity", "selected_entities", "exhaustive_set", "exhaustive_count", "examples", "unknown"]
    hierarchy_scope: Literal["not_applicable", "exclude_root", "exclude_parents", "include_root", "unknown"]
    scope_resolution: Literal["sufficient", "discovery_needed", "user_choice_missing", "unknown"]
    unresolved: list[str] = Field(default_factory=list, max_length=32)
    rationale: str = Field(default="", max_length=4000)
    engine: Literal["host_llm"] = "host_llm"
    status: Literal["decided", "needs_resolution"] = "decided"
    model_id: str | None = Field(default=None, max_length=200)

    @field_validator("selections", "uncertain")
    @classmethod
    def finite_selections(cls, value: dict[str, list[str]]) -> dict[str, list[str]]:
        """Validate bounded dimension arrays before offer membership checks."""
        _dimensions(value)
        for items in value.values():
            if len(items) > 64 or len(set(items)) != len(items):
                fail("Selections must be unique and contain at most 64 values")
        return value

    @field_validator("unresolved")
    @classmethod
    def bounded_unresolved(cls, value: list[str]) -> list[str]:
        """Keep explanatory unresolved needs finite without inventing semantic certainty."""
        if any(not item or len(item) > 500 for item in value):
            fail("Unresolved descriptions must contain 1 to 500 characters")
        return value


def prepare_request(request: RetrievalNeedsRequest) -> RetrievalNeedsRequest:
    """Add only literal/supplied target candidates before compiling the host request."""
    body = request.model_dump(mode="json")
    targets = body["catalog"]["target_ids"]
    for identifier in request.known_ids:
        targets.setdefault(identifier, "Caller-observed candidate, not necessarily the requested target.")
    for identifier in LITERAL_ID.findall(request.original_question):
        targets.setdefault(identifier, "Literal identifier in the original question; assess its requested role.")
    return RetrievalNeedsRequest.model_validate(body)


# DECISION HISTORY
# ================================================================================
# - 2026-10-03 00:00 [python-coder]: Preserve the frozen needs experiment semantics through typed host work. (#TICKETLESS reason=user-requested-isolated-host-experiment)
