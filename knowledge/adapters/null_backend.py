"""Disabled retriever performs no I/O or optional dependency imports."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from knowledge.contracts import KnowledgeRetrievalRequest

from uuid import uuid4
from knowledge.contracts import KnowledgeRetrievalResult


class NullKnowledgeRetriever:
    """Disabled retriever that returns explicit status without external I/O."""

    async def capabilities(self) -> dict:
        """Report that retrieval is explicitly disabled without checking external services.

        Returns:
            Explicit disabled status and false flags for every retrieval capability.
        """
        return {"status": "disabled", "graph": False, "semantic": False, "hybrid": False}

    async def retrieve(self, request: KnowledgeRetrievalRequest) -> KnowledgeRetrievalResult:
        """Return an explicit disabled result without performing retrieval I/O.

        Args:
            request: Validated neutral retrieval request.

        Returns:
            A disabled response tied to the caller request, without external I/O.
        """
        return KnowledgeRetrievalResult(
            request_id=request.request_id,
            retrieval_id=str(uuid4()),
            status="disabled",
            requested_mode=request.mode,
            executed_mode=request.mode,
            operation=request.operation,
        )

    async def close(self) -> None:
        """Close the disabled adapter without allocating or releasing external resources."""
        return None
