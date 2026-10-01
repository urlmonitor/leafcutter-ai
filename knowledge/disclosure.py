"""Progressive source disclosure and whole-envelope continuation budgeting."""

from __future__ import annotations

from .contracts import Entity, KnowledgeRetrievalRequest, KnowledgeRetrievalResult
from .ports import SourceResolver

import hashlib
import logging
import time
from .contracts import KnowledgeEvidence
from .errors import KnowledgeError
from . import cursors

logger = logging.getLogger(__name__)
SAFE_PROPERTIES = {"status", "corrected_by", "superseded_by", "synthetic", "decision_type"}


def finalize(
    request: KnowledgeRetrievalRequest,
    out: KnowledgeRetrievalResult,
    page: dict | None,
    cursor_secret: bytes | None,
) -> None:
    """Fit evidence and authenticated continuation into cumulative response budgets.

    Args:
        request: Validated request including scope, operation and disclosure budgets.
        out: Mutable result envelope being assembled for this request.
        page: Candidate-work and continuation accounting for the current page.
        cursor_secret: Process-local continuation signing key.
    """
    page = page or {}
    state = page.get("state") or {}
    used = page.get("used", 0)
    maximum = min(
        request.budget.max_content_bytes - used, request.budget.max_estimated_tokens * 4 - used
    )
    original = len(out.evidence)
    for attempt in range(original + 12):
        count = len(out.evidence)
        more = page.get("more", False) or count < original
        out.truncated = out.truncated or more
        rounds = state.get("round", 0) + 1
        candidates = state.get("used_candidates", 0) + page.get("candidates", 0)
        spent = state.get("spent_ms", 0) + out.stats.get("duration_ms", 0)
        allow = (
            more
            and count
            and rounds < request.budget.max_rounds
            and candidates < request.budget.max_candidates
            and spent < request.budget.deadline_ms
        )
        if allow:
            # Conservative reservation covers cursor/envelope changes and prevents the next
            # page from receiving a budget smaller than its minimal response envelope.
            projected = used + len(out.model_dump_json().encode()) + 768
            if maximum - len(out.model_dump_json().encode()) < 1024:
                allow = False
            else:
                out.continuation = cursors.encode(
                    {
                        "generation_id": page["generation"],
                        "request_hash": cursors.request_hash(request),
                        "offset": page.get("offset", 0) + count,
                        "round": rounds,
                        "used_bytes": projected,
                        "used_candidates": candidates,
                        "spent_ms": spent,
                        "expires": state.get("expires", time.time() + 3600),
                    },
                    cursor_secret,
                )
        if not allow:
            out.continuation = None
        out.stats["estimated_tokens"] = (len(out.model_dump_json().encode()) + 3) // 4
        if len(out.model_dump_json().encode()) <= maximum:
            break
        if out.evidence:
            out.evidence.pop()
            out.status = "partial"
            out.truncated = True
        else:
            out.continuation = None
            out.warnings = []
            out.errors = [{"code": "budget_exhausted"}]
            out.stats = {}
            break


async def evidence(
    node: Entity,
    request: KnowledgeRetrievalRequest,
    provenance: dict,
    content_limit: int | None = None,
    *,
    source_resolver: SourceResolver | None = None,
) -> KnowledgeEvidence:
    """Disclose one canonical entity at the requested bounded source level.

    Args:
        node: Canonical entity selected for disclosure.
        request: Validated request including scope, operation and disclosure budgets.
        provenance: Bounded source and graph explanation fields.
        content_limit: Maximum UTF-8 source bytes available to this evidence item.


    Returns:
        KnowledgeEvidence: Sanitized evidence containing only the requested disclosure level.

    Keyword-only source_resolver: Optional reader for immutable source excerpts.
    """
    level = request.disclosure_level
    properties = {k: v for k, v in node.properties.items() if k in SAFE_PROPERTIES}
    visible = node.model_copy(
        update={"summary": node.summary if level >= 2 else "", "properties": properties}
    )
    content = node.summary if level == 2 else None
    limitations = []
    if level == 3:
        if source_resolver is None:
            limitations.append("source content unavailable")
        else:
            try:
                content = await source_resolver.read(
                    node.source, (content_limit or request.budget.max_content_bytes) + 4
                )
                if content_limit and len(content.encode()) > content_limit:
                    content = content.encode()[:content_limit].decode("utf-8", "ignore")
                    limitations.append("source excerpt truncated to allocated content budget")
            except (OSError, ValueError, KnowledgeError):
                logger.warning("Knowledge source content unavailable")
                limitations.append("source content unavailable")
    identity = "|".join(
        [
            node.source.repository_id,
            node.canonical_id,
            node.source.source_sha,
            node.source.path,
            node.source.locator,
            str(level),
            hashlib.sha256((content or "").encode()).hexdigest(),
        ]
    )
    return KnowledgeEvidence(
        entity=visible,
        evidence_id="knowledge-" + hashlib.sha256(identity.encode()).hexdigest(),
        content=content,
        disclosure_level=level,
        limitations=limitations,
        **provenance,
    )
