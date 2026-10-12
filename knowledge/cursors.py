"""Authenticated continuations bind scope, operation, generation and cumulative work.
MODULE: knowledge.cursors
GOAL: Preserve bounded, attributable retrieval across optional execution paths.
BUSINESS CONTEXT: Missing facts and disabled infrastructure must remain explicit.
ARCHITECTURE: Neutral contracts and caller-owned ports without kernel dependencies.
"""

from __future__ import annotations

from .contracts import KnowledgeRetrievalRequest

from .errors import invalid, InvalidRequest

import base64
import hashlib
import hmac
import json
import time


def request_hash(request: KnowledgeRetrievalRequest) -> str:
    """Bind continuations to the retrieval semantics rather than transport identity.

    Args:
        request: Validated request including scope, operation and disclosure budgets.

    Returns:
        str: SHA-256 binding of scope, operation, revision and budgets, excluding request identity.
    """
    data = request.model_dump(exclude={"continuation", "request_id", "correlation"})
    if data.get("answer_requirements") is None:
        data.pop("answer_requirements", None)
    if data.get("assessment") is None:
        data.pop("assessment", None)
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def encode(payload: dict, secret: bytes) -> str:
    """Authenticate and encode bounded continuation state.

    Args:
        payload: Continuation state to serialize and authenticate.
        secret: Process-local HMAC key for continuation authentication.

    Returns:
        str: URL-safe state plus its HMAC signature.
    """
    body = (
        base64.urlsafe_b64encode(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        )
        .decode()
        .rstrip("=")
    )
    signature = hmac.new(secret, body.encode(), hashlib.sha256).hexdigest()
    return body + "." + signature


def decode(token: str, secret: bytes, request: KnowledgeRetrievalRequest) -> dict:
    """Verify continuation authentication, request binding and expiration.

    Args:
        token: Opaque signed continuation supplied by the caller.
        secret: Process-local HMAC key for continuation authentication.
        request: Validated request including scope, operation and disclosure budgets.

    Returns:
        dict: Authenticated generation, offset, expiration and cumulative budget state.
    """
    try:
        body, signature = token.split(".")
        expected = hmac.new(secret, body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            invalid("continuation integrity failed")
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        if payload["expires"] < time.time() or payload["request_hash"] != request_hash(request):
            invalid("continuation expired or scope/request changed")
        if payload["round"] >= request.budget.max_rounds:
            invalid("retrieval session round budget exhausted")
    except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidRequest() from exc

    return payload


# DECISION HISTORY
# ================================================================================
# - 2026-10-01 18:55 [python-coder]: Keep requested facts separate from execution success and preserve canonical field meaning. (#KM-500/KM-500e-2)
