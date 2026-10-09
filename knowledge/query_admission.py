"""Independent query verification followed by explicitly governed catalog activation.

DECISION HISTORY
- 2026-10-09 09:11 [python-coder]: Emit native queries while preserving versioned catalog admission identities. (#KM-400a-3-i/TICKET-20261009-KM-400a-3-i-native-query-maintenance)
- 2026-10-01 15:46 [python-coder]: Rerun checks; never trust a builder's success receipt. (#KM-500/TICKET-20261001-KM-500b-2)

MODULE: knowledge.query_admission
GOAL: Provide the scoped knowledge retrieval query_admission responsibility.
BUSINESS CONTEXT: Make attributable research capabilities reusable and explicitly governed.
ARCHITECTURE: Dependencies point inward to neutral contracts; see docs/architecture/components/knowledge-retrieval.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from .ports import QueryBackend
from .query_catalog import QueryCatalog

if TYPE_CHECKING:
    from .config import KnowledgeConfig

import time
import asyncio
from .deadlines import deadline
from uuid import uuid4
from .errors import invalid, KnowledgeError
from .query_models import QueryCandidate, QueryDescriptor, validate_arguments
from .query_compile import COMPILER_VERSION, compile_query, digest_data
from .query_execution import execute_query
from .query_store import activate


class QueryAdmission:
    """Trusted admission port; the kernel separately enforces catalog-write permission."""

    def __init__(self, catalog: QueryCatalog, backend: QueryBackend, repository_id: str) -> None:
        """Bind resources selected by application composition.

        Args:
            catalog: Explicit trusted catalog scope.
            backend: Existing serving adapter, never supplied by the coding agent.
            repository_id: Authorized repository binding.
        """
        self.catalog, self.backend, self.repository_id = catalog, backend, repository_id

    async def pin(self, repository_id: str, source_sha: str = "latest") -> dict:
        """Resolve a ready immutable manifest for research before any interruption.

        Args:
            repository_id: Must match the configured trusted repository.
            source_sha: Exact revision or explicit latest policy.

        Returns:
            Serializable repository, SHA and generation identity.
        """
        if repository_id != self.repository_id:
            invalid("admission repository differs from configured scope")
        manifest = (
            await self.backend.active(repository_id)
            if source_sha == "latest"
            else await self.backend.get_revision(repository_id, source_sha)
        )
        if manifest is None or manifest.status != "ready":
            raise KnowledgeError("stale", "admission needs a published requested revision")
        if manifest.repository_id != repository_id or (
            source_sha != "latest" and manifest.source_sha != source_sha
        ):
            invalid("admission manifest crossed requested repository or revision")
        return {
            "repository_id": repository_id,
            "source_sha": manifest.source_sha,
            "generation_id": manifest.generation_id,
            "supported_kinds": list(manifest.supported_kinds),
            "supported_fields": dict(manifest.supported_fields),
            "supported_relationships": list(manifest.supported_relationships),
        }

    async def verify(self, candidate: dict, *, repository_id: str, source_sha: str) -> dict:
        """Run declared judgments and mandatory boundary cases without activating.

        Args:
            candidate: Untrusted recipe, expectations and reviewer attribution.



        Returns:
            Reviewable compiled artifact and freshly measured verification provenance.

        Keyword-only repository_id: Trusted namespace selected before the host build.
        Keyword-only source_sha: Exact pinned source revision, never drifting latest.
        """
        authored = QueryCandidate.model_validate(candidate)
        if source_sha == "latest":
            invalid("admission requires an exact pinned source SHA")
        pinned = await self.pin(repository_id, source_sha)
        compiled = compile_query(authored.descriptor)
        token = deadline.set(time.monotonic() + 30)
        try:
            checks = await asyncio.wait_for(evaluate_candidate(self.backend, authored, pinned), 30)
        except TimeoutError as exc:
            raise KnowledgeError("unavailable", "query verification deadline reached") from exc
        finally:
            deadline.reset(token)
        proof = {
            "status": "verified",
            "digest": compiled["digest"],
            **pinned,
            "candidate_digest": digest_data(authored.model_dump()),
            "reviewer": authored.reviewer,
            "expected_judgments_owner": "candidate author; attribution is not independent approval",
            "verified_at": time.time(),
            "checks": checks,
        }
        return {
            "descriptor": authored.descriptor.model_dump(),
            "compiled": compiled,
            "verification": proof,
            "verification_digest": digest_data(proof),
        }

    async def verify_and_activate(
        self,
        candidate: dict,
        *,
        repository_id: str,
        source_sha: str,
        expected_active_digest: str | None = None,
    ) -> dict:
        """Freshly verify and atomically admit a candidate within the configured root.

        Args:
            candidate: Untrusted reviewable builder artifact.




        Returns:
            Serializable activation receipt bound to query content and measured proof.

        Keyword-only repository_id: Trusted authorized repository binding.
        Keyword-only source_sha: Exact research revision.
        Keyword-only expected_active_digest: Required prior active version when replacing a query.
        """
        entry = await self.verify(candidate, repository_id=repository_id, source_sha=source_sha)
        selected = activate(self.catalog.root, entry, expected_active_digest)
        proof = entry["verification"]
        return {
            **proof,
            "status": "activated",
            "operation": selected["descriptor"]["operation"],
            "version": selected["descriptor"]["version"],
            "verification_digest": entry["verification_digest"],
            "catalog_admission_verification_digest": selected["verification_digest"],
        }


async def evaluate_candidate(
    backend: QueryBackend, candidate: QueryCandidate, pinned: dict
) -> dict:
    """Execute independent fixed checks plus the candidate's declared expectations.

    Args:
        backend: Trusted scoped transaction adapter.
        candidate: Validated authored artifact.
        pinned: Verified exact source generation.

    Returns:
        Measured cases and explicit limits of what the evidence proves.
    """
    descriptor, results = candidate.descriptor, []
    for case in candidate.cases:
        rows = await execute_query(
            backend, descriptor, pinned["repository_id"], pinned["generation_id"], case.arguments
        )
        actual = sorted(entity.canonical_id for entity in rows)
        if actual != sorted(set(case.expected_ids)):
            invalid("query expected-result expectation failed: " + case.name)
        results.append(
            {
                "name": case.name,
                "expected_ids": sorted(case.expected_ids),
                "actual_ids": actual,
                "expansion_truncated": rows.truncated,
            }
        )
    invalid_checked = False
    try:
        validate_arguments(descriptor, {})
    except ValueError:
        invalid_checked = True
    if not invalid_checked:
        invalid("admission invalid-input boundary failed")
    poison = dict(candidate.cases[0].arguments)
    poison[descriptor.recipe.seed_parameter] = [
        "__absent_" + uuid4().hex + "' MATCH (n) RETURN n //"
    ]
    rows = await execute_query(
        backend, descriptor, pinned["repository_id"], pinned["generation_id"], poison
    )
    if rows:
        invalid("admission bound-input isolation failed")
    await verify_foreign_scope(backend, descriptor, pinned, candidate.cases[0].arguments)
    return {
        "declared_cases_passed": len(results),
        "cases": results,
        "invalid_input_rejected": True,
        "bound_injection_empty": True,
        "foreign_scope_rejected": True,
        "semantic_usefulness_proven": False,
        "verification_method": "fresh compiled-query execution and fixed boundary checks",
        "compiler_version": COMPILER_VERSION,
    }


async def verify_foreign_scope(
    backend: QueryBackend, descriptor: QueryDescriptor, pinned: dict, arguments: dict
) -> None:
    """Demand that a foreign repository cannot borrow the pinned generation.

    Args:
        backend: Trusted adapter.
        descriptor: Compiled operation contract.
        pinned: Authorized generation.
        arguments: Otherwise valid values.
    """
    rejected = False
    try:
        rows = await execute_query(
            backend, descriptor, "__foreign_" + uuid4().hex, pinned["generation_id"], arguments
        )
        rejected = not rows
    except KnowledgeError as exc:
        if exc.code != "stale":
            raise
        rejected = True
    if not rejected:
        invalid("admission foreign-scope isolation failed")


def build_query_admission(config: KnowledgeConfig, retriever: object) -> QueryAdmission | None:
    """Compose the trusted port from an existing backend pool and explicit catalog root.

    Args:
        config: Application-owned knowledge configuration.
        retriever: Already composed serving service.

    Returns:
        Admission port, or None when disabled or no persistent root is configured.
    """
    from .query_catalog import QueryCatalog

    root = getattr(config, "query_catalog_root", None)
    if not root or getattr(config, "backend", "none") == "none":
        return None
    backend = getattr(retriever, "backend", None)
    if backend is None:
        invalid("query admission needs the configured serving backend")
    return QueryAdmission(QueryCatalog(root), backend, config.repository_id)


# - 2026-10-01 [python-coder]: Preserve question evidence and explicit source support through bounded research. (#KM-500/KM-500e-2)
