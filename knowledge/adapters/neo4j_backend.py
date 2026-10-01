"""MODULE: neo4j_backend
GOAL: Own one optional Neo4j driver and bounded registered operations.
BUSINESS CONTEXT: Keep database resources outside callers and kernel state.
ARCHITECTURE: Adapter delegates projection and vector lifecycle to small helpers.

DECISION HISTORY
========================================
- 2026-10-01 12:00 [python-coder]: Use metadata-only manifests and explicit database selection. (#TICKET-KM-400b-1)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

import asyncio
import hashlib
import json
from pathlib import Path

from knowledge.contracts import Entity, ProjectionSnapshot, Relation
from knowledge.errors import BackendUnavailable


def scope_key(repository_id: str, generation_id: str) -> str:
    """Return a collision-resistant projector-only compound key."""
    return hashlib.sha256(json.dumps([repository_id, generation_id]).encode()).hexdigest()


def entity_from_row(row: dict) -> Entity:
    """Deserialize plain entity data; never leak driver records."""
    return Entity.model_validate_json(row["payload"])


class Neo4jBackend:
    """Optional Neo4j read/write adapter with one explicitly closed connection pool."""

    def __init__(
        self,
        uri: str,
        username: str,
        password: str,
        database: str = "neo4j",
        query_timeout: float = 3.0,
    ) -> None:
        """Load the optional driver only when this backend is explicitly selected.

        Args:
            uri: Database connection URI with verified TLS for remote hosts.
            username: Database principal name.
            password: Database credential retained only in the driver configuration.
            database: Explicit database name within the Neo4j instance.
            query_timeout: Maximum database transaction duration in seconds.
        """
        from neo4j import GraphDatabase

        self.driver = GraphDatabase.driver(
            uri, auth=(username, password), max_transaction_retry_time=3.0, connection_timeout=3.0
        )
        self.database = database
        self.query_timeout = min(max(query_timeout, 0.1), 30.0)

    async def _run(
        self, statement: str, parameters: dict | None = None, write: bool = False
    ) -> list[dict]:
        """Execute a trusted statement within a bounded managed transaction.

        Args:
            statement: Fixed parameterized Cypher text owned by this adapter.
            parameters: Bound values kept separate from Cypher syntax.
            write: Whether the managed transaction may mutate projection data.

        Returns:
            Database result records converted to plain dictionaries.
        """
        return await self._transaction(
            lambda tx: self._rows(tx, statement, parameters or {}), write
        )

    def _rows(self, tx: object, statement: str, parameters: dict) -> list[dict]:
        """Perform the scoped rows operation.

        Args:
            tx: Driver-owned transaction provided by the managed callback.
            statement: Fixed parameterized Cypher text owned by this adapter.
            parameters: Bound values kept separate from Cypher syntax.

        Returns:
            Transaction result records materialized as plain dictionaries.
        """
        return [record.data() for record in tx.run(statement, parameters)]

    async def _transaction(
        self, callback: Callable[[object], object], write: bool = False
    ) -> object:
        """Run idempotent database work in a worker and normalize infrastructure faults.

        Args:
            callback: Operation executed inside a bounded managed transaction.
            write: Whether the managed transaction may mutate projection data.

        Returns:
            The callback result after successful managed commit, with bounded retry policy.
        """
        from neo4j import unit_of_work
        from neo4j.exceptions import DriverError, Neo4jError
        from knowledge.deadlines import remaining_seconds

        timeout = remaining_seconds(self.query_timeout)

        def execute():
            """Own the synchronous session within its worker-thread lifetime."""
            with self.driver.session(database=self.database) as session:
                runner = session.execute_write if write else session.execute_read
                return runner(unit_of_work(timeout=timeout)(callback))

        try:
            return await asyncio.to_thread(execute)
        except (OSError, TimeoutError, DriverError, Neo4jError) as error:
            raise BackendUnavailable() from error

    async def setup(self) -> None:
        """Apply idempotent, versioned Community-compatible projection constraints."""
        migration = Path(__file__).parents[1] / "migrations" / "001_projection.cypher"
        for statement in migration.read_text(encoding="utf-8").split(";"):
            if statement.strip():
                await self._run(statement, write=True)

    async def capabilities(self) -> dict:
        """Advertise implemented mechanisms; readiness is generation-specific."""
        return {"graph": True, "semantic": True, "hybrid": True, "model": None, "dimensions": None}

    async def active(self, repository_id: str) -> ProjectionSnapshot | None:
        """Read the active manifest once without reading entity nodes.

        Args:
            repository_id: Trusted repository namespace that isolates all reads and writes.

        Returns:
            Metadata for the active published generation, or None when none exists.
        """
        rows = await self._run(
            'MATCH (r:KRRepository {repository_id:$repo}) MATCH (g:KRGeneration {key:r.active}) WHERE g.status="ready" RETURN g',
            {"repo": repository_id},
        )
        return self._manifest(rows[0]["g"]) if rows else None

    async def get_generation(
        self, repository_id: str, generation_id: str
    ) -> ProjectionSnapshot | None:
        """Read only a retained ready generation's manifest metadata.

        Args:
            repository_id: Trusted repository namespace that isolates all reads and writes.
            generation_id: Immutable generation identifier within the repository.

        Returns:
            Published generation metadata in the requested scope, or None if unavailable.
        """
        rows = await self._run(
            'MATCH (g:KRGeneration {key:$key, status:"ready"}) RETURN g',
            {"key": scope_key(repository_id, generation_id)},
        )
        return self._manifest(rows[0]["g"]) if rows else None

    async def get_revision(self, repository_id: str, source_sha: str) -> ProjectionSnapshot | None:
        """Select a retained ready manifest for an exact repository commit.

        Args:
            repository_id: Trusted repository namespace that isolates all reads and writes.
            source_sha: Exact immutable source commit SHA to locate.

        Returns:
            Published generation metadata for that exact SHA, or None if unavailable.
        """
        rows = await self._run(
            'MATCH (g:KRGeneration {repository_id:$repo,source_sha:$sha,status:"ready"}) RETURN g ORDER BY g.ready_at DESC LIMIT 1',
            {"repo": repository_id, "sha": source_sha},
        )
        return self._manifest(rows[0]["g"]) if rows else None

    @staticmethod
    def _manifest(row: dict) -> ProjectionSnapshot:
        """Deserialize generation metadata without loading entity or relationship data.

        Args:
            row: Driver result row containing serialized projection metadata.

        Returns:
            Validated source generation with immutable provenance.
        """
        return ProjectionSnapshot(
            repository_id=row["repository_id"],
            source_sha=row["source_sha"],
            generation_id=row["generation_id"],
            mapper_version=row["mapper_version"],
            node_count=row.get("node_count", 0),
            edge_count=row.get("edge_count", 0),
            diagnostics=json.loads(row.get("diagnostics", "[]")),
            semantic_ready=row.get("semantic_ready", False),
            embedding_model=row.get("embedding_model"),
            embedding_dimensions=row.get("embedding_dimensions"),
            supported_kinds=row.get("supported_kinds", []),
        )

    async def publish(
        self, snapshot: ProjectionSnapshot, expected_generation: str | None = None
    ) -> bool:
        """Build an immutable generation and atomically compare-and-swap its pointer.

        Args:
            snapshot: Validated immutable generation and its canonical source records.
            expected_generation: Previously active generation required for compare-and-swap.

        Returns:
            Whether the guarded operation succeeded.
        """
        from knowledge.adapters.neo4j_projection import publish

        return await publish(self, snapshot, expected_generation)

    async def query(
        self, repository_id: str, generation_id: str, operation: str, arguments: dict, limit: int
    ) -> list[Entity]:
        """Execute only the reviewed catalog over one ready generation.

        Args:
            repository_id: Trusted repository namespace that isolates all reads and writes.
            generation_id: Immutable generation identifier within the repository.
            operation: Registered query operation; never arbitrary caller Cypher.
            arguments: Bound operation parameters passed separately from query text.
            limit: Maximum result count after enforcing the adapter bound.

        Returns:
            Matching canonical entities in the scoped generation, bounded by limit.
        """
        from knowledge.adapters.neo4j_queries import query

        return await query(self, repository_id, generation_id, operation, arguments, limit)

    async def neighbors(
        self,
        repository_id: str,
        generation_id: str,
        entity_ids: list[str],
        edge_types: list[str],
        limit: int,
    ) -> tuple[list[Entity], list[Relation]]:
        """Return a bounded one-hop expansion within the pinned scope.

        Args:
            repository_id: Trusted repository namespace that isolates all reads and writes.
            generation_id: Immutable generation identifier within the repository.
            entity_ids: Canonical seed IDs within the selected generation.
            edge_types: Allowlisted relationship labels requested for expansion.
            limit: Maximum result count after enforcing the adapter bound.

        Returns:
            Bounded neighboring entities and their original directed relationships.
        """
        from knowledge.adapters.neo4j_queries import neighbors

        return await neighbors(self, repository_id, generation_id, entity_ids, edge_types, limit)

    async def put_embeddings(
        self,
        repository_id: str,
        generation_id: str,
        embeddings: dict,
        model: str,
        dimensions: int,
        content_hashes: dict,
    ) -> None:
        """Attach content-validated vectors and publish semantic readiness separately.

        Args:
            repository_id: Trusted repository namespace that isolates all reads and writes.
            generation_id: Immutable generation identifier within the repository.
            embeddings: Canonical entity IDs mapped to their precomputed vectors.
            model: Embedding model identifier bound to this generation.
            dimensions: Expected number of finite values in every embedding.
            content_hashes: Expected source hashes keyed by canonical entity ID.
        """
        from knowledge.adapters.neo4j_vectors import put_embeddings

        await put_embeddings(
            self, repository_id, generation_id, embeddings, model, dimensions, content_hashes
        )

    async def semantic(
        self,
        repository_id: str,
        generation_id: str,
        vector: list[float],
        kinds: list[str],
        limit: int,
        model: str,
    ) -> list[tuple[Entity, float]]:
        """Query a generation-local ANN index with bounded candidate count.

        Args:
            repository_id: Trusted repository namespace that isolates all reads and writes.
            generation_id: Immutable generation identifier within the repository.
            vector: Finite nonzero query vector with the configured dimensions.
            kinds: Allowed entity kinds for the scoped semantic search.
            limit: Maximum result count after enforcing the adapter bound.
            model: Embedding model identifier bound to this generation.

        Returns:
            Canonical entities paired with descending similarity scores from scoped indexes.
        """
        from knowledge.adapters.neo4j_vectors import semantic

        return await semantic(self, repository_id, generation_id, vector, kinds, limit, model)

    async def rollback(
        self, repository_id: str, generation_id: str, expected_generation: str
    ) -> bool:
        """Explicitly select a retained generation using the same atomic pointer guard.

        Args:
            repository_id: Trusted repository namespace that isolates all reads and writes.
            generation_id: Immutable generation identifier within the repository.
            expected_generation: Previously active generation required for compare-and-swap.

        Returns:
            Whether the guarded operation succeeded.
        """
        from knowledge.adapters.neo4j_projection import switch_active

        if await self.get_generation(repository_id, generation_id) is None:
            return False
        return await switch_active(self, repository_id, generation_id, expected_generation)

    async def cleanup(
        self,
        repository_id: str,
        generation_id: str,
        retention_seconds: int = 3600,
        now: float | None = None,
    ) -> bool:
        """Remove only an inactive owned generation after its retention deadline.

        Args:
            repository_id: Trusted repository namespace that isolates all reads and writes.
            generation_id: Immutable generation identifier within the repository.
            retention_seconds: Minimum elapsed retirement time before removal is permitted.
            now: Optional clock value for deterministic retention checks.

        Returns:
            Whether the guarded operation succeeded.
        """
        from knowledge.adapters.neo4j_projection import cleanup

        return await cleanup(self, repository_id, generation_id, retention_seconds, now)

    async def close(self) -> None:
        """Close the configured driver's pool."""
        await asyncio.to_thread(self.driver.close)
