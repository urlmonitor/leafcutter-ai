"""Observe final standalone results through the application's existing tracer.

MODULE: knowledge_observation
GOAL: Distinguish query execution, question fulfillment and trace delivery.
BUSINESS CONTEXT: An available trace link alone does not establish remote ingestion.
ARCHITECTURE: Application-owned adapter; neutral knowledge only receives a callback.
"""
from __future__ import annotations

from typing import Any

import hashlib
import inspect
import logging
from kernel.contracts.base import CorrelationIds
from kernel.contracts.enums import ObservabilityStatus
from kernel.observability.tracer import NoOpTracer

logger = logging.getLogger(__name__)


def observation_summary(request: Any, result: Any) -> dict:
    """Build bounded metadata without source excerpts or literal research text.

    Args:
        request: Final original requirements and scoped execution request.
        result: Final response after budgets and answer assessment.

    Returns:
        Correlated execution and fulfillment facts for existing redaction.
    """
    need = request.answer_requirements
    return {"request_id": request.request_id, "retrieval_id": result.retrieval_id,
        "repository_id": request.repository_id, "requested_revision": request.revision,
        "source_sha": result.source_sha, "generation_id": result.generation_id,
        "operation": request.operation, "operation_version": request.operation_version,
        "execution_status": result.status, "truncated": result.truncated,
        "answer_status": result.answer.status if result.answer else "unspecified",
        "completeness": result.answer.completeness.model_dump() if result.answer else None,
        "required_fields": need.required_fields if need else [],
        "scope": need.scope.model_dump(mode="json") if need else {},
        "question_sha256": hashlib.sha256(need.original_question.encode()).hexdigest() if need else None,
        "missing_fields": [item.model_dump() for item in result.answer.missing_fields] if result.answer else [],
        "evidence_ids": [item.entity.canonical_id for item in result.evidence]}


class RetrievalObserver:
    """Use one owned trace segment for an already finalized standalone retrieval."""

    def __init__(self, tracer: Any = None, verify_reference: Any = None) -> None:
        """Bind the existing tracer and optional trusted remote-read verification.

        Args:
            tracer: Existing application telemetry owner; absence disables observation.
            verify_reference: Callback verifying matching remote request and retrieval IDs.
        """
        self.tracer = tracer
        self.verify_reference = verify_reference

    async def observe(self, request: Any, result: Any) -> dict:
        """Return honest delivery state without changing evidence or fulfillment.

        Args:
            request: Final original scoped request.
            result: Final bounded answer and execution result.

        Returns:
            Caller-visible observation state, stable IDs and qualified reference.
        """
        base = {"state": "disabled", "trace_id": None, "trace_url": None,
                "reason": "Observation is disabled", "request_id": request.request_id,
                "retrieval_id": result.retrieval_id}
        if self.tracer is None or isinstance(self.tracer, NoOpTracer):
            return base
        try:
            return await self._record(request, result, base)
        except (OSError, RuntimeError, ValueError, TimeoutError):
            logger.warning("Standalone knowledge observation unavailable; diagnostic details withheld")
            return {**base, "state": "unavailable", "reason": "Observation failed; retrieval remains available"}

    async def _record(self, request: Any, result: Any, base: dict) -> dict:
        """Finalize the existing trace segment and verify only through trusted evidence.

        Args:
            request: Final scoped request.
            result: Final bounded response.
            base: Caller-visible correlation and default delivery state.

        Returns:
            Verified, unverified or unavailable observation reference.
        """
        run_id = "knowledge:" + result.retrieval_id
        trace = self.tracer.open_segment(run_id, request.request_id, "start")
        base.update(trace_id=trace.trace_id)
        try:
            corr = CorrelationIds(run_id=run_id, root_task_id=request.request_id)
            with self.tracer.span("knowledge.retrieve", "retriever", corr) as span:
                span.update(metadata=observation_summary(request, result))
        finally:
            delivery = self.tracer.close_segment()
        if delivery != ObservabilityStatus.OK:
            return {**base, "state": "unavailable", "reason": "Trace export degraded"}
        verified = False
        if self.verify_reference is not None:
            verified = self.verify_reference(trace.trace_id, request.request_id, result.retrieval_id)
            if inspect.isawaitable(verified):
                verified = await verified
        return {**base, "trace_url": trace.trace_url if verified is True else None,
                "state": "verified" if verified is True else "unverified",
                "reason": "Matching remote observation verified" if verified is True else
                          "Local emission succeeded; remote ingestion is unverified"}

# DECISION HISTORY
# - 2026-10-01 [python-coder]: Preserve scoped answer obligations and honest observation through existing runtime owners. (#KM-500/KM-500e-1)
