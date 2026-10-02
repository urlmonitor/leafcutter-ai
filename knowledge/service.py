"""Budgeted retrieval orchestration over registered backend operations.
MODULE: knowledge.service
GOAL: Provide the scoped knowledge retrieval service responsibility.
BUSINESS CONTEXT: Make attributable research capabilities reusable and explicitly governed.
ARCHITECTURE: Dependencies point inward to neutral contracts; see docs/architecture/components/knowledge-retrieval.md.
"""

from __future__ import annotations

from .retrieval_steps import load_generation, fetch_candidates, disclose_candidates

from collections.abc import Callable
from typing import TYPE_CHECKING

from .ports import SourceResolver, EmbeddingProvider, KnowledgeBackend, RetrievalTelemetry

if TYPE_CHECKING:
    from .query_catalog import QueryCatalog

from .errors import invalid

import asyncio
import logging

logger = logging.getLogger(__name__)
import secrets
import time
from .disclosure import finalize
from uuid import uuid4
from .contracts import Entity, KnowledgeRetrievalRequest, KnowledgeRetrievalResult
from .errors import KnowledgeError
from . import cursors
from .deadlines import deadline
from .semantic import QueryEmbeddings


class KnowledgeService:
    """Coordinate pinned graph retrieval, disclosure and cumulative budgets."""

    def __init__(
        self,
        backend: KnowledgeBackend,
        source_resolver: SourceResolver | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        cursor_secret: bytes | None = None,
        telemetry: RetrievalTelemetry | None = None,
        cancel_probe: Callable[[], bool] | None = None,
        query_catalog: QueryCatalog | None = None,
        observer: object | None = None,
    ) -> None:
        """Store injected dependencies without performing network operations.

        Args:
            backend: Injected backend implementing the registered query and generation operations.
            source_resolver: Optional reader for immutable source excerpts.
            embedding_provider: Optional caller-owned embedding provider.
            cursor_secret: Process-local continuation signing key.
            telemetry: Optional observer exposing record for bounded retrieval metadata.
            cancel_probe: Optional callable reporting caller cancellation.
            query_catalog: Optional trusted persistent operation registry.
            observer: Optional caller-owned final-result observation boundary.
        """
        self.backend = backend
        self.query_catalog = query_catalog
        self.observer = observer
        self.source_resolver = source_resolver
        self.embeddings = QueryEmbeddings(embedding_provider)
        self.cursor_secret = cursor_secret or secrets.token_bytes(32)
        self.telemetry = telemetry
        self.cancel_probe = cancel_probe or (lambda: False)

    async def capabilities(self) -> dict:
        """Capabilities.

        Returns:
            dict: Flags advertising the backend mechanisms available to callers.
        """
        return await self.backend.capabilities()

    async def close(self) -> None:
        """Close."""
        closer = getattr(self.backend, "close", None)
        if closer:
            await closer()

    async def retrieve(self, request: KnowledgeRetrievalRequest) -> KnowledgeRetrievalResult:
        """Execute a registered scoped request and return attributable bounded evidence.

        Args:
            request: Validated request including scope, operation and disclosure budgets.

        Returns:
            KnowledgeRetrievalResult: Scoped disclosed evidence with typed status, provenance and optional continuation.
        """
        request = KnowledgeRetrievalRequest.model_validate(
            request.model_dump(), context={"query_catalog": self.query_catalog}
        )
        out = KnowledgeRetrievalResult(
            request_id=request.request_id,
            retrieval_id=str(uuid4()),
            status="ok",
            requested_mode=request.mode,
            executed_mode=request.mode,
            operation=request.operation,
            operation_version=request.operation_version,
        )
        if request.operation_digest:
            out.stats["operation_digest"] = request.operation_digest
        start = time.monotonic()
        page: dict = {}
        try:
            state = (
                cursors.decode(request.continuation, self.cursor_secret, request)
                if request.continuation
                else None
            )
            page = {"state": state, "used": state.get("used_bytes", 0) if state else 0}
            remaining = request.budget.deadline_ms - (state.get("spent_ms", 0) if state else 0)
            if remaining <= 0:
                invalid("cumulative retrieval deadline exhausted")
            token = deadline.set(time.monotonic() + remaining / 1000)
            try:
                retrieved_page = await asyncio.wait_for(
                    self._retrieve(request, out, state), remaining / 1000
                )
                if retrieved_page is not None:
                    page = retrieved_page
            finally:
                deadline.reset(token)
        except TimeoutError:
            logger.warning("Knowledge retrieval timed out")
            out.status = "partial" if out.evidence else "unavailable"
            out.warnings.append("retrieval deadline reached")
        except KnowledgeError as exc:
            logger.warning("Knowledge retrieval unavailable: %s", exc.code)
            if out.evidence:
                out.status = "partial"
            elif exc.code == "unavailable":
                out.status = "unavailable"
            elif exc.code == "unsupported":
                out.status = "unsupported"
            elif exc.code == "stale":
                out.status = "stale"
            else:
                out.status = "error"
            out.errors.append({"code": exc.code, "message": str(exc), "retryable": exc.retryable})
        except (ValueError, OSError) as exc:
            logger.warning("Knowledge retrieval rejected: %s", type(exc).__name__)
            out.status = "error"
            out.errors.append({"code": "retrieval_failed", "message": str(exc), "retryable": False})
        out.stats["duration_ms"] = round((time.monotonic() - start) * 1000, 3)
        finalize(request, out, page, self.cursor_secret, 128 if self.observer else 0)
        if self.telemetry:
            try:
                self.telemetry.record(
                    {
                        "request_id": request.request_id,
                        "retrieval_id": out.retrieval_id,
                        "repository_id": request.repository_id,
                        "source_sha": out.source_sha,
                        "generation_id": out.generation_id,
                        "operation": out.operation,
                        "requested_mode": request.mode,
                        "executed_mode": out.executed_mode,
                        "status": out.status,
                        "count": len(out.evidence),
                    }
                )
            except (OSError, RuntimeError, ValueError):
                logger.warning("Knowledge telemetry unavailable")
                out.warnings.append("telemetry unavailable")
        from .observation import observe, fit_observation

        observation_limit = len(out.model_dump_json().encode()) + 128 if out.continuation else None
        out.observation = await observe(self.observer, request, out)
        fit_observation(request, out, (page or {}).get("used", 0), observation_limit)
        return out

    async def _retrieve(
        self,
        request: KnowledgeRetrievalRequest,
        out: KnowledgeRetrievalResult,
        state: dict | None = None,
    ) -> dict | None:
        """Populate one result page from a pinned immutable generation.

        Args:
            request: Validated request including scope, operation and disclosure budgets.
            out: Mutable result envelope being assembled for this request.
            state: Verified cumulative continuation accounting, when resuming.

        Returns:
            dict | None: Pagination offsets and cumulative work consumed, or None for an empty/stale result.
        """
        snapshot = await load_generation(self, request, out, state)
        if snapshot is None:
            return None
        offset = state["offset"] if state else 0
        remaining_candidates = request.budget.max_candidates - (
            state.get("used_candidates", 0) if state else 0
        )
        if remaining_candidates <= 0:
            invalid("cumulative candidate budget exhausted")
        used = state["used_bytes"] if state else 0
        if used >= request.budget.max_content_bytes:
            invalid("cumulative retrieval content budget exhausted")
        rows, provenance, semantic_work = await fetch_candidates(
            self, request, out, snapshot, remaining_candidates, offset
        )
        if len(rows) > request.budget.max_candidates:
            rows = rows[: request.budget.max_candidates]
            out.truncated = True
        unique: dict[str, Entity] = {}
        for row in rows:
            if (
                row.source.repository_id != request.repository_id
                or row.source.source_sha != snapshot.source_sha
            ):
                invalid("backend candidate crossed repository or generation scope")
            unique.setdefault(row.canonical_id, row)
        rows = list(unique.values())
        if request.mode not in {"semantic", "hybrid", "precedent"}:
            rows.sort(key=lambda n: n.canonical_id)
        out.stats.update(
            candidates=len(rows),
            estimator_version="utf8-bytes-div4-v1",
            round=(state["round"] + 1 if state else 1),
        )
        selected = rows[offset : offset + request.budget.max_results]
        _mark_population_page(out, offset)
        candidate_work = semantic_work if semantic_work is not None else len(rows)
        candidate_work = await disclose_candidates(
            self,
            request,
            out,
            snapshot,
            selected,
            provenance,
            used,
            remaining_candidates,
            candidate_work,
        )
        more = len(rows) > offset + len(selected)
        if candidate_work >= remaining_candidates:
            out.truncated = True
            out.status = "partial"
            out.warnings.append("candidate budget reached; completeness not established")
        out.truncated = out.truncated or more
        if more:
            out.status = "partial"
        out.stats["candidate_work"] = candidate_work
        return {
            "state": state,
            "offset": offset,
            "more": more,
            "selected": len(selected),
            "used": used,
            "candidates": candidate_work,
            "generation": snapshot.generation_id,
        }


def _mark_population_page(out: KnowledgeRetrievalResult, offset: int) -> None:
    """Prevent a final slice from masquerading as an entire declared population."""
    if offset and "population" in out.stats:
        out.stats["population"]["complete"] = False
        out.stats["population"]["page_offset"] = offset


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 15:46 [python-coder]: Bind verified reusable query versions through scoped retrieval. (#KM-500/TICKET-20261001-KM-500b-3)

# - 2026-10-01 [python-coder]: Preserve question evidence and explicit source support through bounded research. (#KM-500/KM-500e-2)
