"""Disabled retriever performs no I/O or optional dependency imports.
MODULE: knowledge.adapters.null_backend
GOAL: Preserve bounded, attributable retrieval across optional execution paths.
BUSINESS CONTEXT: Missing facts and disabled infrastructure must remain explicit.
ARCHITECTURE: Neutral contracts and caller-owned ports without kernel dependencies.
"""

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
        result = KnowledgeRetrievalResult(
            request_id=request.request_id,
            retrieval_id=str(uuid4()),
            status="disabled",
            requested_mode=request.mode,
            executed_mode=request.mode,
            operation=request.operation,
        )
        from knowledge.answers import assess_answer

        result.answer = assess_answer(request, result)
        return result

    async def close(self) -> None:
        """Close the disabled adapter without allocating or releasing external resources."""
        return None


# - 2026-10-01 [python-coder]: Preserve question evidence and explicit source support through bounded research. (#KM-500/KM-500e-2)
