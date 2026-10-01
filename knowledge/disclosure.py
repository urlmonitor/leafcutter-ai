"""Progressive source disclosure and whole-envelope continuation budgeting.
MODULE: knowledge.disclosure
GOAL: Preserve bounded, attributable retrieval across optional execution paths.
BUSINESS CONTEXT: Missing facts and disabled infrastructure must remain explicit.
ARCHITECTURE: Neutral contracts and caller-owned ports without kernel dependencies.
"""

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
SAFE_PROPERTIES = {
    "status",
    "req_status",
    "work_status",
    "readiness",
    "priority",
    "level",
    "parent",
    "structural_parent",
    "structural_parent_locator",
    "has_children",
    "covered_by",
    "implemented_by",
    "depends_on",
    "test_required",
    "corrected_by",
    "superseded_by",
    "synthetic",
    "decision_type",
}


def finalize(
    request: KnowledgeRetrievalRequest,
    out: KnowledgeRetrievalResult,
    page: dict | None,
    cursor_secret: bytes | None,
    observer_bytes: int = 0,
) -> None:
    """Fit evidence and authenticated continuation into cumulative response budgets.

    Args:
        request: Validated request including scope, operation and disclosure budgets.
        out: Mutable result envelope being assembled for this request.
        page: Candidate-work and continuation accounting for the current page.
        cursor_secret: Process-local continuation signing key.
        observer_bytes: Bounded space reserved for post-finalization observation metadata.
    """
    page = page or {}
    state = page.get("state") or {}
    used = page.get("used", 0)
    maximum = (
        min(request.budget.max_content_bytes - used, request.budget.max_estimated_tokens * 4 - used)
        - observer_bytes
    )
    original = len(out.evidence)
    for attempt in range(original + 12):
        from .answers import assess_answer

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
        out.answer = assess_answer(request, out)
        out.assessment = _assess_supplied(request, out)
        out.stats["estimated_tokens"] = (len(out.model_dump_json().encode()) + 3) // 4
        _account_continuation(request, out, used, cursor_secret, observer_bytes)
        if len(out.model_dump_json().encode()) <= maximum:
            break
        if out.evidence:
            out.evidence.pop()
            out.status = "partial"
            out.truncated = True
        else:
            _compact_unresolved(out, maximum)
            break


def _account_continuation(
    request: KnowledgeRetrievalRequest,
    out: KnowledgeRetrievalResult,
    used: int,
    secret: bytes | None,
    observer_bytes: int,
) -> None:
    """Charge the complete assessed envelope before its observation is delivered.

    Args:
        request: Original request bound to the signed continuation.
        out: Final assessed envelope whose evidence will no longer grow.
        used: Response allowance charged by prior pages.
        secret: Process-local continuation authentication key.
        observer_bytes: Maximum optional observation growth reserved on this page.
    """
    if out.continuation is None:
        return
    payload = cursors.decode(out.continuation, secret, request)
    # The small margin covers the changed integer length inside the signed token.
    payload["used_bytes"] = used + len(out.model_dump_json().encode()) + observer_bytes + 32
    out.continuation = cursors.encode(payload, secret)


def _assess_supplied(
    request: KnowledgeRetrievalRequest, out: KnowledgeRetrievalResult
) -> dict | None:
    """Assess only an explicitly supplied packet against the actual final evidence."""
    if request.assessment is None:
        return None
    from .assessments import assess

    return assess(request.assessment, retrieval=out)


def _compact_unresolved(out: KnowledgeRetrievalResult, maximum: int) -> None:
    """Retain question identity and a bounded explicit unresolved result.

    Args:
        out: Result already stripped of oversized evidence.
        maximum: Remaining whole-envelope byte allowance.
    """
    out.continuation = None
    out.warnings = []
    out.errors = [{"code": "budget_exhausted"}]
    out.stats = {}
    if out.assessment is not None:
        out.assessment = {
            "kind": out.assessment.get("kind"),
            "status": "unresolved",
            "limitations": ["response_budget_exhausted"],
        }
    if out.answer is not None:
        out.answer.status = "unresolved"
        out.answer.limitations = ["response_budget_exhausted"]
        out.answer.completeness.limitations = []
        out.answer.completeness.complete = False
        out.answer.completeness.exact_total = None
        out.answer.work_status_counts = None
    if len(out.model_dump_json().encode()) > maximum:
        from .errors import invalid

        invalid(
            "response budget cannot retain the original question contract; increase content/token budget"
        )


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
    from .answer_fields import availability

    fields = request.answer_requirements.required_fields if request.answer_requirements else []
    return KnowledgeEvidence(
        entity=visible,
        field_availability=availability(node, visible, fields, level, limitations),
        field_locators=_field_locators(node, fields),
        field_derivations=_field_derivations(fields),
        evidence_id="knowledge-" + hashlib.sha256(identity.encode()).hexdigest(),
        content=content,
        disclosure_level=level,
        limitations=limitations,
        **provenance,
    )


def _field_locators(node: Entity, fields: list[str]) -> dict[str, str]:
    """Locate actual YAML fields separately from the default criteria excerpt.

    Args:
        node: Actual projected entity with optional derivation provenance.
        fields: Required canonical or explicitly derived fields.

    Returns:
        Field-specific pointers within the same immutable source file.
    """
    locators = {
        name: "/" + name
        for name in fields
        if name not in {"canonical_id", "kind", "title", "source_sha", "source_locator"}
    }
    if "structural_parent" in locators:
        locators["structural_parent"] = node.properties.get("structural_parent_locator", "/id")
    if "has_children" in locators:
        locators["has_children"] = "/id"
    return locators


def _field_derivations(fields: list[str]) -> dict[str, str]:
    """Label derived hierarchy facts rather than presenting them as literal YAML fields."""
    rules = {
        "structural_parent": "explicit parent override or scripts/ac_store/ac_parent_id.py:derive_parent_id",
        "has_children": "membership in canonical structural-parent identities at the pinned source revision",
    }
    return {name: rule for name, rule in rules.items() if name in fields}


# DECISION HISTORY
# ================================================================================
# - 2026-10-01 18:55 [python-coder]: Keep requested facts separate from execution success and preserve canonical field meaning. (#KM-500/KM-500e-2)
