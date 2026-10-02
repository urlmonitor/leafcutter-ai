"""Final-result observation without owning a telemetry provider.
MODULE: knowledge.observation
GOAL: Deliver one bounded final retrieval observation through an injected port.
BUSINESS CONTEXT: A local event must not masquerade as verified remote visibility.
ARCHITECTURE: Neutral caller-owned callback; no kernel or provider dependency.
"""

from __future__ import annotations

from .contracts import KnowledgeRetrievalRequest, KnowledgeRetrievalResult

import inspect
import logging

logger = logging.getLogger(__name__)


async def observe(
    observer: object | None, request: KnowledgeRetrievalRequest, result: KnowledgeRetrievalResult
) -> dict:
    """Call an optional sink once; isolate delivery failure from retrieval evidence.

    Args:
        observer: Callable or object exposing observe, optionally asynchronous.
        request: The validated original retrieval request.
        result: The final bounded retrieval result.

    Returns:
        dict: Bounded delivery metadata with an explicit verification state.
    """
    if observer is None:
        return {"state": "disabled"}
    try:
        callback = getattr(observer, "observe", observer)
        if not callable(callback):
            raise ValueError("invalid observer callback")
        observed = callback(request, result.model_copy(deep=True))
        if inspect.isawaitable(observed):
            observed = await observed
        if not isinstance(observed, dict):
            raise ValueError("invalid observer result")
        state = observed.get("state")
        if state not in {"disabled", "unavailable", "unverified", "verified"}:
            raise ValueError("invalid observation state")
        value = {"state": state}
        for key in ("trace_id", "trace_url", "reason", "request_id", "retrieval_id"):
            if isinstance(observed.get(key), str):
                value[key] = observed[key][:512]
        if state != "verified":
            value["trace_url"] = None
        return value
    except Exception:
        logger.warning("Observation delivery failed")
        return {"state": "unavailable", "trace_url": None, "reason": "Observation delivery failed"}


# DECISION HISTORY
# - 2026-10-01 [python-coder]: Observe finalized neutral results once through an injected port. (#EPIC-RepositoryResearchAnswers/TICKET-20261001-KM-500g-1-i)


def fit_observation(
    request: KnowledgeRetrievalRequest,
    result: KnowledgeRetrievalResult,
    used_bytes: int = 0,
    page_limit: int | None = None,
) -> None:
    """Keep optional delivery metadata inside the same whole-response allowance.

    Args:
        request: Original response budgets.
        result: Final evidence with newly returned observation metadata.
        used_bytes: Actual cumulative response bytes already consumed on prior pages.
        page_limit: Finalized page size plus the observation allowance charged to its cursor.
    """
    maximum = min(
        request.budget.max_content_bytes - used_bytes,
        request.budget.max_estimated_tokens * 4 - used_bytes,
    )
    if page_limit is not None:
        maximum = min(maximum, page_limit)
    for key in ("reason", "request_id", "retrieval_id", "trace_url", "trace_id"):
        if len(result.model_dump_json().encode()) <= maximum:
            return
        result.observation.pop(key, None)
        if key == "trace_url" and result.observation.get("state") == "verified":
            result.observation["state"] = "unverified"
    if len(result.model_dump_json().encode()) > maximum:
        result.observation = {"state": "unavailable"}
    if len(result.model_dump_json().encode()) > maximum:
        from .errors import invalid

        invalid("reserved observation metadata exceeds remaining response budget")
