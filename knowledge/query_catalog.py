"""Discover registered query contracts and construct digest-pinned requests.

DECISION HISTORY
- 2026-10-01 15:46 [python-coder]: Catalog context authorizes only admitted operations. (#KM-500/TICKET-20261001-KM-500b-3)

MODULE: knowledge.query_catalog
GOAL: Provide the scoped knowledge retrieval query_catalog responsibility.
BUSINESS CONTEXT: Make attributable research capabilities reusable and explicitly governed.
ARCHITECTURE: Dependencies point inward to neutral contracts; see docs/architecture/components/knowledge-retrieval.md.
"""

from __future__ import annotations

from pathlib import Path
from .contracts import OPERATIONS, KnowledgeRetrievalRequest
from .errors import invalid
from .query_models import QueryDescriptor
from .query_store import read_catalog


class QueryCatalog:
    """A read-only view of builtins and verified persistent operation versions."""

    def __init__(self, root: Path | str) -> None:
        """Bind one explicit filesystem scope without creating it.

        Args:
            root: Trusted configured directory, never a model-supplied path.
        """
        if not str(root).strip():
            invalid("query catalog root must be explicit")
        self.root = Path(root).resolve()

    def get(
        self, operation: str, version: str | None = None, digest: str | None = None
    ) -> QueryDescriptor:
        """Resolve an active or retained immutable custom query version.

        Args:
            operation: Registered custom identity.
            version: Optional exact descriptor version.
            digest: Previously pinned content digest, including inactive retained entries.

        Returns:
            Validated descriptor whose persisted verification remains intact.
        """
        data = read_catalog(self.root)
        key = digest or data["active"].get(operation)
        entry = data["entries"].get(key)
        if entry is None:
            invalid("unknown registered catalog operation or digest")
        descriptor = QueryDescriptor.model_validate(entry["descriptor"])
        if descriptor.operation != operation or (
            version is not None and descriptor.version != version
        ):
            invalid("query identity/version conflicts with pinned digest")
        return descriptor

    def descriptors(self) -> list[dict]:
        """Expose bounded planner metadata without secrets or executable templates.

        Returns:
            Builtin descriptions followed by verified active custom descriptors.
        """
        rows = builtin_descriptors()
        data = read_catalog(self.root)
        for operation, key in sorted(data["active"].items()):
            descriptor = self.get(operation, digest=key)
            rows.append(
                {
                    **descriptor.model_dump(exclude={"recipe"}),
                    "digest": key,
                    "modes": ["graph", "precedent"],
                    "bounds": {
                        "max_hops": len(descriptor.recipe.steps),
                        "max_seeds": 20,
                        "max_neighbors_per_seed": 10,
                        "max_results": 200,
                    },
                }
            )
        return rows

    def request(self, payload: dict) -> KnowledgeRetrievalRequest:
        """Validate a request against this trusted catalog and pin custom content.

        Args:
            payload: Untrusted serializable request data.

        Returns:
            Strict request whose custom operation cannot float across updates.
        """
        data = dict(payload)
        if data.get("operation", "get_entities") not in OPERATIONS:
            descriptor = self.get(
                data["operation"], data.get("operation_version"), data.get("operation_digest")
            )
            data.update(operation_version=descriptor.version, operation_digest=descriptor.digest)
        return KnowledgeRetrievalRequest.model_validate(data, context={"query_catalog": self})


BUILTIN_PURPOSES = {
    "get_entities": "Look up exactly the supplied canonical entity IDs; no relationship expansion.",
    "get_ac_descendants": "Enumerate acceptance criteria under the supplied root_id using declared or canonically derived structural parents. Requires answer_requirements.scope with matching root_id, explicit levels (empty means all levels), and inclusion policy; completeness is bounded and may be partial.",
    "get_declared_dependents": "Return acceptance criteria whose canonical depends_on directly references the supplied entity_ids; this is declared incoming dependency impact only, not transitive or code impact.",
    "get_component_context": "Return a component and its directly linked neighbors; does not traverse from its acceptance criteria to their tests.",
    "get_acceptance_criteria": "Return acceptance criteria directly declaring membership in the supplied component; does not return their tests.",
    "get_related_tests": "Return tests directly referenced by covered_by on the supplied acceptance-criterion entity IDs; component IDs are not acceptance-criterion seeds and no component-to-AC traversal occurs.",
    "get_relevant_adrs": "Return ADRs directly declaring membership in the supplied component.",
    "get_related_policies": "Request policies governing a component; unsupported unless approved Policy source mapping exists.",
    "get_previous_decisions": "Return reviewed decisions directly ABOUT the supplied component, optionally filtered by status or decision type; requires approved Decision mapping.",
    "get_corrected_decisions": "Follow outgoing CORRECTED_BY links from the supplied decision IDs to corrective decisions.",
    "get_related_lessons": "Follow outgoing TAUGHT links from the supplied decision IDs to their lessons.",
    "get_decision_evidence": "Follow outgoing USED_EVIDENCE links from the supplied decision IDs to supporting evidence entities.",
    "find_similar_decisions": "Find semantic Decision candidates from question text; hybrid mode additionally expands approved context links, not an exact component-to-test path.",
    "find_similar_lessons": "Find semantic Lesson candidates from question text; requires approved Lesson mapping and ready embeddings.",
}


def builtin_descriptors() -> list[dict]:
    """Describe the existing operation vocabulary without changing its contracts.

    Returns:
        Purpose, supported questions, modes and typed input metadata for each builtin.
    """
    rows = []
    for operation, (mode, required) in OPERATIONS.items():
        purpose = BUILTIN_PURPOSES[operation]
        params = {
            required: {
                "type": "string_list" if required == "entity_ids" else "string",
                "required": True,
            }
        }
        if operation in {
            "get_previous_decisions",
            "find_similar_decisions",
            "find_similar_lessons",
        }:
            params.update(
                {
                    name: {"type": "string", "required": False}
                    for name in ("status", "decision_type")
                }
            )
        modes = [mode] + (
            ["hybrid", "precedent"]
            if mode == "semantic"
            else (["precedent"] if mode == "graph" else [])
        )
        rows.append(
            {
                "operation": operation,
                "version": "1",
                "digest": "builtin:1",
                "description": purpose,
                "questions": [purpose],
                "parameters": params,
                "modes": modes,
                "result_meaning": "Attributable canonical entities for " + purpose,
            }
        )
    return rows
