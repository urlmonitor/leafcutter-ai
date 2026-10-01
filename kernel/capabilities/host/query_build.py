"""Coding host packet for a missing bounded graph query; no activation authority."""
from typing import Any
from kernel.capabilities.host.base import HostOperation
from kernel.capabilities.host.sanitize import completed_result
from kernel.capabilities.host.spec import HostConversion
from kernel.contracts import CapabilityResult, schema_ids
from kernel.contracts.query import QueryBuildRequest, QueryCandidate

class QueryBuild(HostOperation):
    """Author candidate data and tests for independent native admission."""
    capability_id = "host.query_build"
    operation = "build_query"
    request_model = QueryBuildRequest
    output_model = QueryCandidate

    def task_text(self, request: Any, goal: str) -> str:
        """Describe the parameterized query and measured test deliverables.


        Args:
            request: Validated request being routed or compiled.
            goal: Input to the documented operation.

        Returns:
            str: Coding task using the original evidence need.
        """
        return ("Build a reusable parameterized Neo4j query recipe and positive/negative tests for: "
                + (request.question if request is not None else goal))

    def requirements(self, request: Any) -> list[str]:
        """Return limits that keep candidate data outside the execution boundary.


        Args:
            request: Validated request being routed or compiled.

        Returns:
            list[str]: Explicit authoring and verification requirements.
        """
        return ["Return candidate with descriptor, cases, reviewer. Never claim activation.",
                "Descriptor has operation, version 1, description, questions, parameters and recipe.",
                "Recipe seeds use a required string_list parameter; at most two directed canonical edge steps.",
                "Use only canonical kinds and kind/status/decision_type/canonical_id parameter filters.",
                "Supply positive and negative expected_ids cases; trusted code independently executes them.",
                "Do not return raw Cypher, Python, credentials or filesystem destinations.",
                "If bounded recipe cannot express the need, report inability; do not fabricate success."]

    def convert_payload(self, ctx: HostConversion, payload: QueryCandidate) -> CapabilityResult:
        """Preserve the candidate as untrusted input for the native verifier.


        Args:
            ctx: Trusted runtime scope, budgets and services.
            payload: Validated original evidence request.

        Returns:
            CapabilityResult: Completed candidate construction, not admitted execution.
        """
        return completed_result(ctx, schema_ids.QUERY_CANDIDATE, payload)
