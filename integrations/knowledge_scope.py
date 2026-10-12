"""
MODULE: knowledge_scope
GOAL: Validate trusted knowledge request and evidence scope.
BUSINESS CONTEXT: Preserve repository, revision and source authorization.
ARCHITECTURE: Shared scope checks for bounded kernel knowledge retrieval.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import TYPE_CHECKING

from kernel.capabilities.retrieval.access import ReadPolicy
from knowledge.errors import KnowledgeError

if TYPE_CHECKING:
    from typing import Any

    from kernel.capabilities.base import ExecutionContext
    from kernel.contracts.payloads import RetrievalRequestPayload
    from knowledge.contracts import KnowledgeEvidence, KnowledgeRetrievalRequest


def _authorized(
    ctx: ExecutionContext, request: KnowledgeRetrievalRequest, item: KnowledgeEvidence,
    *, source_ids: set[str] | None = None,
) -> bool:
    """Check revision/repository and existing path policy before exposing evidence.

    Args:
        ctx: Trusted execution scope, budgets and telemetry owner.
        request: Validated repository-scoped retrieval request.
        item: Disclosed neutral evidence to map or authorize.

    Returns:
        bool: Validated result of the documented operation.
    """
    source = item.entity.source
    if source.repository_id != request.repository_id:
        return False
    if (
        request.revision != "latest"
        and not request.allow_stale
        and source.source_sha != request.revision
    ):
        return False
    path, win = PurePosixPath(source.path), PureWindowsPath(source.path)
    if path.is_absolute() or win.drive or ".." in (*path.parts, *win.parts):
        return False
    policy = ReadPolicy(
        Path(ctx.scope.repository_root).resolve(),
        tuple(ctx.scope.read_roots),
        (*ctx.config.retrieval.deny_globs,
         *(pattern for configured in ctx.config.sources if configured.id in (source_ids or set())
           and configured.kind == "graph_query" for pattern in configured.deny_globs)),
        ctx.config.retrieval.max_file_bytes,
    )
    relative = policy.relative(policy.root / source.path)
    return (relative is not None and not policy.is_denied(source.path)
            and not policy.is_denied(relative))


def _scoped_request(
    ctx: ExecutionContext, payload: RetrievalRequestPayload, capabilities: dict[str, Any]
) -> dict[str, Any]:
    """Validate trusted repository/source bindings before routing.

    Args:
        ctx: Existing trusted task scope and configuration.
        payload: Caller retrieval payload.
        capabilities: Available retrieval mechanisms.

    Returns:
        dict[str, Any]: Explicit request fields after scope validation.
    """
    config = ctx.config.knowledge
    root = config.repository_root
    if capabilities.get("status") != "disabled" and (
        not root or Path(root).resolve() != Path(ctx.scope.repository_root).resolve()
    ):
        raise KnowledgeError(
            "scope_mismatch", "knowledge repository binding does not match task scope"
        )
    raw = dict(payload.knowledge or {})
    if raw.get("repository_id", config.repository_id) != config.repository_id:
        raise KnowledgeError("scope_mismatch", "requested knowledge repository is not authorized")
    if ctx.scope.source_ids and not any(
        s.id in ctx.scope.source_ids and s.kind == "graph_query" for s in ctx.config.sources
    ):
        raise KnowledgeError(
            "scope_mismatch", "task source scope does not allow knowledge retrieval"
        )
    return raw
