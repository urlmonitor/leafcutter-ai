"""Strict authored query recipes; these data models cannot carry executable code.

DECISION HISTORY
- 2026-10-09 09:11 [python-coder]: Preserve admitted descriptor identity without exposing compiler provenance in authored data. (#KM-400a-3-i/TICKET-20261009-KM-400a-3-i-native-query-maintenance)
- 2026-10-01 15:46 [python-coder]: Restrict live admission to bounded declared graph paths. (#KM-500/TICKET-20261001-KM-500b-2)

MODULE: knowledge.query_models
GOAL: Provide the scoped knowledge retrieval query_models responsibility.
BUSINESS CONTEXT: Make attributable research capabilities reusable and explicitly governed.
ARCHITECTURE: Dependencies point inward to neutral contracts; see docs/architecture/components/knowledge-retrieval.md.
"""

from __future__ import annotations

from typing import Literal
from pydantic import Field, PrivateAttr, model_validator
from .contracts import Model, OPERATIONS
from .errors import invalid

KINDS = {"Component", "AcceptanceCriterion", "ADR", "Test", "SourceFile", "Decision", "Lesson"}
EDGES = {
    "component_membership",
    "covered_by",
    "implemented_by",
    "depends_on",
    "related_docs",
    "ABOUT",
    "CORRECTED_BY",
    "TAUGHT",
    "USED_EVIDENCE",
}
Property = Literal["canonical_id", "kind", "status", "decision_type"]


class QueryParameter(Model):
    """Bounded input declaration exposed to the research planner."""

    type: Literal["string", "string_list"]
    required: bool = True


class QueryStep(Model):
    """One directed and fanout-bounded relationship expansion."""

    edge_type: str
    direction: Literal["incoming", "outgoing"]
    kind: str | None = None
    filters: dict[Property, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def vocabulary(self):
        """Reject undeclared relationships and projected kinds."""
        if self.edge_type not in EDGES or (self.kind is not None and self.kind not in KINDS):
            invalid("recipe uses an unsupported edge or kind; requires a code-build gap")
        return self


class QueryRecipe(Model):
    """At most two bounded expansions from an explicitly supplied seed list."""

    seed_parameter: str
    seed_kind: str | None = None
    filters: dict[Property, str] = Field(default_factory=dict)
    steps: list[QueryStep] = Field(default_factory=list, max_length=2)


class QueryDescriptor(Model):
    """Versioned reusable operation with purpose, input contract and restricted recipe."""

    operation: str = Field(pattern=r"^[a-z][a-z0-9_]{2,79}$")
    version: str = Field(pattern=r"^[1-9][0-9]{0,4}$")
    description: str = Field(min_length=10, max_length=2000)
    questions: list[str] = Field(min_length=1, max_length=10)
    result_meaning: str = "Canonical entities reached by the declared scoped relationship path"
    parameters: dict[str, QueryParameter] = Field(min_length=1, max_length=8)
    recipe: QueryRecipe
    _admitted_compiler_version: str | None = PrivateAttr(default=None)

    @model_validator(mode="after")
    def declared_inputs(self):
        """Bind all recipe references to typed, non-reserved input names."""
        if self.operation in OPERATIONS:
            invalid("built-in operation cannot be replaced by a catalog entry")
        validate_parameter_names(self.parameters)
        seed = self.parameters.get(self.recipe.seed_parameter)
        if seed is None or seed.type != "string_list" or not seed.required:
            invalid("recipe requires a declared required string_list seed parameter")
        if self.recipe.seed_kind is not None and self.recipe.seed_kind not in KINDS:
            invalid("unsupported seed kind")
        validate_filter_references(self)
        return self

    @property
    def digest(self) -> str:
        """Recompute identity using the admitted compiler, or the current authoring compiler.

        Only trusted catalog reads bind an admitted version. Private provenance is
        excluded from authored JSON; copying or editing still recomputes the digest.
        """
        from .query_compile import COMPILER_VERSION, compile_query

        if self._admitted_compiler_version == "1":
            from .query_legacy import compile_legacy_query

            return compile_legacy_query(self)["digest"]
        if self._admitted_compiler_version not in {None, COMPILER_VERSION}:
            invalid("query identity requires an unsupported compiler version")
        return compile_query(self)["digest"]


class EvaluationCase(Model):
    """An authored expected-result judgment to be independently executed."""

    name: str = Field(min_length=1, max_length=200)
    arguments: dict
    expected_ids: list[str] = Field(max_length=200)


class QueryCandidate(Model):
    """Reviewable authored artifact; no success flags or executable text are accepted."""

    descriptor: QueryDescriptor
    reviewer: str = Field(min_length=1, max_length=200)
    cases: list[EvaluationCase] = Field(min_length=2, max_length=20)

    @model_validator(mode="after")
    def positive_and_empty(self):
        """Require positive and no-match expected outcomes, not empty proof."""
        outcomes = [bool(case.expected_ids) for case in self.cases]
        if not any(outcomes) or all(outcomes):
            invalid("admission requires both positive and empty expected-result cases")
        for case in self.cases:
            validate_arguments(self.descriptor, case.arguments)
        return self


def validate_arguments(descriptor: QueryDescriptor, arguments: dict) -> None:
    """Reject unknown, missing or excessive inputs before any backend operation.

    Args:
        descriptor: Trusted input contract.
        arguments: Untrusted data values bound separately from query syntax.
    """
    if set(arguments) - set(descriptor.parameters):
        invalid("unknown query arguments")
    for name, spec in descriptor.parameters.items():
        if name not in arguments and not spec.required:
            continue
        value = arguments.get(name)
        values = value if spec.type == "string_list" and isinstance(value, list) else [value]
        if spec.type == "string_list" and (
            not isinstance(value, list) or not 1 <= len(value) <= 20
        ):
            invalid("seed list requires 1..20 values")
        if any(not isinstance(v, str) or not v.strip() or len(v) > 300 for v in values):
            invalid("query values require bounded nonempty strings")


def validate_parameter_names(parameters: dict) -> None:
    """Reject syntax-bearing and reserved input names.

    Args:
        parameters: Authored input declarations.
    """
    import re

    reserved = {"repo", "repository_id", "generation_id", "scope_key", "limit"}
    if any(
        not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", name) or name in reserved for name in parameters
    ):
        invalid("invalid or reserved query parameter")


def validate_filter_references(descriptor: QueryDescriptor) -> None:
    """Resolve recipe filter references and forbid inert contract fields.

    Args:
        descriptor: Authored descriptor under validation.
    """
    filters = [descriptor.recipe.filters, *(step.filters for step in descriptor.recipe.steps)]
    used = {descriptor.recipe.seed_parameter}
    for group in filters:
        for name in group.values():
            if name not in descriptor.parameters or descriptor.parameters[name].type != "string":
                invalid("filter must reference a declared string parameter")
            used.add(name)
    if used != set(descriptor.parameters):
        invalid("unused query parameter")
    if any(not q.strip() or len(q) > 1000 for q in descriptor.questions):
        invalid("invalid supported question")
