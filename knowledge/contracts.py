"""Versioned transport and projection records, independent of kernel domain models."""

from __future__ import annotations

from .errors import invalid

from typing import Literal
from pathlib import PurePosixPath
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Model(BaseModel):
    """Strict transport model rejecting undeclared fields."""

    model_config = ConfigDict(extra="forbid")


class SourceReference(Model):
    """Immutable repository source locator and content identity."""

    repository_id: str = Field(min_length=1)
    source_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    path: str = Field(min_length=1)
    locator: str = ""
    content_hash: str = ""

    @field_validator("path")
    @classmethod
    def safe_path(cls, value):
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or "\\" in value or ":" in value:
            invalid("source path must remain repository-relative")
        return value


class Entity(Model):
    """Canonical source entity carried by a projection generation."""

    canonical_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    title: str
    summary: str = ""
    source: SourceReference
    properties: dict = Field(default_factory=dict)


class Relation(Model):
    """Typed canonical relation with source provenance."""

    source: SourceReference | None = None
    source_id: str
    target_id: str
    edge_type: str
    locator: str = ""


class ProjectionSnapshot(Model):
    """Immutable projection contents or lightweight published manifest."""

    repository_id: str
    source_sha: str
    generation_id: str
    nodes: list[Entity] = Field(default_factory=list)
    edges: list[Relation] = Field(default_factory=list)
    mapper_version: str = "1"
    diagnostics: list = Field(default_factory=list)
    status: str = "ready"
    node_count: int = 0
    edge_count: int = 0
    supported_kinds: list[str] = Field(default_factory=list)
    semantic_ready: bool = False
    embedding_model: str | None = None
    embedding_dimensions: int | None = None


class RetrievalBudget(Model):
    """Validated upper bounds for cumulative retrieval work and disclosure."""

    max_results: int = Field(default=20, ge=1, le=100)
    max_candidates: int = Field(default=50, ge=1, le=200)
    max_neighbors_per_seed: int = Field(default=10, ge=1, le=50)
    max_hops: int = Field(default=2, ge=0, le=2)
    max_rounds: int = Field(default=3, ge=1, le=10)
    max_content_bytes: int = Field(default=32768, ge=1024, le=131072)
    max_estimated_tokens: int = Field(default=4000, ge=256, le=16000)
    deadline_ms: int = Field(default=10000, ge=1, le=30000)


OPERATIONS = {
    "get_entities": ("exact", "entity_ids"),
    "get_component_context": ("graph", "component_id"),
    "get_acceptance_criteria": ("graph", "component_id"),
    "get_related_tests": ("graph", "entity_ids"),
    "get_relevant_adrs": ("graph", "component_id"),
    "get_related_policies": ("graph", "component_id"),
    "get_previous_decisions": ("graph", "component_id"),
    "get_corrected_decisions": ("graph", "entity_ids"),
    "get_related_lessons": ("graph", "entity_ids"),
    "get_decision_evidence": ("graph", "entity_ids"),
    "find_similar_decisions": ("semantic", "query_text"),
    "find_similar_lessons": ("semantic", "query_text"),
}


class KnowledgeRetrievalRequest(Model):
    """Versioned registered retrieval request and authorized repository scope."""

    contract_version: Literal["1"] = "1"
    request_id: str = Field(min_length=1, max_length=200)
    repository_id: str = Field(min_length=1, max_length=200)
    operation: str = "get_entities"
    operation_version: Literal["1"] = "1"
    mode: Literal["exact", "graph", "semantic", "hybrid", "precedent"] = "exact"
    arguments: dict = Field(default_factory=dict)
    revision: str = "latest"
    disclosure_level: int = Field(default=0, ge=0, le=3)
    budget: RetrievalBudget = Field(default_factory=RetrievalBudget)
    continuation: str | None = None
    allow_stale: bool = False
    correlation: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def registered_arguments(self):
        if self.operation not in OPERATIONS:
            invalid("unknown registered operation")
        expected, required = OPERATIONS[self.operation]
        modes = {expected}
        if expected == "semantic":
            modes |= {"hybrid", "precedent"}
        if expected == "graph":
            modes.add("precedent")
        if self.mode not in modes:
            invalid("mode conflicts with registered operation")
        validate_operation_arguments(self.arguments, required, self.operation)
        if self.revision != "latest" and (
            len(self.revision) != 40 or any(x not in "0123456789abcdef" for x in self.revision)
        ):
            invalid("revision must be exact SHA or latest")
        return self


class KnowledgeEvidence(Model):
    """Disclosed canonical evidence with provenance and limitations."""

    entity: Entity
    evidence_id: str = ""
    content: str | None = None
    disclosure_level: int = 0
    signals: dict[str, float] = Field(default_factory=dict)
    seed_id: str | None = None
    path: list[Relation] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    relationships: list[Relation] = Field(default_factory=list)
    related: list[dict[str, str]] = Field(default_factory=list)


class KnowledgeRetrievalResult(Model):
    """Bounded retrieval envelope with typed status and continuation."""

    contract_version: Literal["1"] = "1"
    request_id: str
    retrieval_id: str
    status: Literal["ok", "partial", "disabled", "unavailable", "unsupported", "stale", "error"]
    requested_mode: str
    executed_mode: str
    operation: str = ""
    operation_version: str = "1"
    source_sha: str | None = None
    generation_id: str | None = None
    evidence: list[KnowledgeEvidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[dict] = Field(default_factory=list)
    continuation: str | None = None
    truncated: bool = False
    stats: dict = Field(default_factory=dict)


def validate_operation_arguments(arguments: dict, required: str, operation: str) -> None:
    """Reject unknown fields and malformed registered arguments before backend access.

    Args:
        arguments: Request-supplied operation argument mapping.
        required: Required argument name declared by the operation catalog.
        operation: Registered operation determining which filters are permitted.
    """
    allowed = {required}
    if operation in {
        "get_previous_decisions",
        "find_similar_decisions",
        "find_similar_lessons",
    }:
        allowed |= {"status", "decision_type"}
    if any(
        not isinstance(arguments[name], str) or len(arguments[name]) > 200
        for name in ("status", "decision_type")
        if name in arguments
    ):
        invalid("filter values must be bounded strings")
    if set(arguments) - allowed:
        invalid("unknown operation arguments")
    value = arguments.get(required)
    validate_required_value(value, required)


def validate_required_value(value: object, required: str) -> None:
    """Validate the catalog-required scalar or bounded canonical-ID list.

    Args:
        value: Required argument supplied by the request.
        required: Catalog argument name distinguishing entity lists from text.
    """
    if required == "entity_ids":
        if (
            not isinstance(value, list)
            or not value
            or len(value) > 200
            or any(not isinstance(x, str) or not x or len(x) > 300 for x in value)
        ):
            invalid("entity_ids requires 1..200 canonical IDs")
    elif not isinstance(value, str) or not value.strip() or len(value) > 4000:
        invalid("missing or invalid required argument")
