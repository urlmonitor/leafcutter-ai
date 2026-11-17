"""Composition configuration. Enabled configuration errors fail before network access.
MODULE: knowledge.config
GOAL: Provide the scoped knowledge retrieval config responsibility.
BUSINESS CONTEXT: Make attributable research capabilities reusable and explicitly governed.
ARCHITECTURE: Dependencies point inward to neutral contracts; see docs/architecture/components/knowledge-retrieval.md.
"""

from __future__ import annotations

from .ports import EmbeddingProvider, ManagedKnowledgeRetriever

from .errors import invalid

import os
from urllib.parse import urlsplit
from pydantic import Field
from .contracts import Model
from .adapters.null_backend import NullKnowledgeRetriever


class KnowledgeConfig(Model):
    """Optional infrastructure settings with external credential variable names."""

    backend: str = "none"
    repository_id: str = "leafcutter"
    repository_root: str | None = None
    query_catalog_root: str | None = None
    neo4j_uri_env: str = "LEAFCUTTER_NEO4J_URI"
    neo4j_username_env: str = "LEAFCUTTER_NEO4J_USERNAME"
    neo4j_password_env: str = "LEAFCUTTER_NEO4J_PASSWORD"
    database: str | None = None
    embeddings_enabled: bool = False
    embedding_endpoint_env: str = "LEAFCUTTER_EMBEDDING_ENDPOINT"
    embedding_token_env: str = "LEAFCUTTER_EMBEDDING_TOKEN"
    embedding_model: str | None = None
    embedding_dimensions: int | None = None
    query_timeout: float = Field(default=3.0, gt=0, le=30)
    # KM-400f-1: the retention bound is DECLARED, never defaulted. Both parts
    # are required together and neither has a fallback value, so an unset
    # bound is refused rather than silently resolved.
    retention_max_generations: int | None = None
    retention_min_age_seconds: int | None = None


class RetentionBound(Model):
    """Declared generation retention bound: a count limit AND a minimum retirement age."""

    generation_limit: int
    minimum_age_seconds: int
    source: str


def _unset_bound(name: str, source: str) -> ValueError:
    """Build the refusal naming one undeclared retention setting.

    Args:
        name: Configuration setting that is not declared.
        source: Inspectable name of the configuration that was read.

    Returns:
        ValueError: Refusal that states no built-in value is used.
    """
    return ValueError(
        f"retention bound is unset: {name} is not declared in configuration "
        f"(source: {source}); no built-in value is used"
    )


_COUNT_RANGE = "retention_max_generations must be at least 1"
_AGE_RANGE = "retention_min_age_seconds must be nonnegative"


def _out_of_range(message: str) -> ValueError:
    """Wrap a range refusal for a declared retention setting.

    Args:
        message: Refusal text naming the setting.

    Returns:
        ValueError: Refusal carrying the message.
    """
    return ValueError(message)


def resolve_retention_bound(config: KnowledgeConfig, *, source: str) -> RetentionBound:
    """Resolve the declared retention bound, refusing an incomplete declaration.

    Args:
        config: Knowledge configuration carrying the declared bound, if any.
        source: Inspectable name of where the bound was read from.

    Returns:
        RetentionBound: Count limit, minimum retirement age and configuration source.

    Raises:
        ValueError: When either setting is undeclared (zero counts as declared) or out of range.
    """
    # `is None`, never falsiness: a zero minimum age is a declared value.
    if config.retention_max_generations is None:
        raise _unset_bound("retention_max_generations", source)
    if config.retention_min_age_seconds is None:
        raise _unset_bound("retention_min_age_seconds", source)
    if config.retention_max_generations < 1:
        raise _out_of_range(_COUNT_RANGE)
    if config.retention_min_age_seconds < 0:
        raise _out_of_range(_AGE_RANGE)
    return RetentionBound(
        generation_limit=config.retention_max_generations,
        minimum_age_seconds=config.retention_min_age_seconds,
        source=source,
    )


def build_retriever(
    config: KnowledgeConfig | dict,
    *,
    embedding_provider: EmbeddingProvider | None = None,
    observer: object | None = None,
) -> ManagedKnowledgeRetriever:
    """Compose an optional serving backend without starting the kernel.

    Args:
        config: Explicit optional backend configuration.


    Returns:
        ManagedKnowledgeRetriever: Disabled retriever or configured service owning its selected database adapter.

    Keyword-only embedding_provider: Optional caller-owned embedding provider.
    """
    config = KnowledgeConfig.model_validate(config) if isinstance(config, dict) else config
    if config.backend == "none":
        return NullKnowledgeRetriever()
    if config.backend != "neo4j":
        invalid("knowledge backend must be none or neo4j")
    from .environment import resolve_neo4j, resolve_database

    values = resolve_neo4j(config)
    uri = urlsplit(values[0])
    if uri.scheme not in {"neo4j+s", "bolt+s"} and uri.hostname not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        invalid("remote Neo4j requires verified TLS via neo4j+s or bolt+s")
    from .adapters.neo4j_backend import Neo4jBackend
    from .adapters.git_source import GitSourceResolver
    from .service import KnowledgeService

    backend = Neo4jBackend(
        *values, database=resolve_database(config), query_timeout=config.query_timeout
    )
    resolver = (
        GitSourceResolver(config.repository_root, config.repository_id)
        if config.repository_root
        else None
    )
    provider = embedding_provider or build_embedding_provider(config)
    from .query_catalog import QueryCatalog

    catalog = QueryCatalog(config.query_catalog_root) if config.query_catalog_root else None
    return KnowledgeService(
        backend,
        source_resolver=resolver,
        embedding_provider=provider,
        query_catalog=catalog,
        observer=observer,
    )


def build_embedding_provider(config: KnowledgeConfig) -> EmbeddingProvider | None:
    """Select an explicit gateway only when enabled; credentials remain environment-owned.

    Args:
        config: Explicit optional backend configuration.

    Returns:
        EmbeddingProvider | None: Configured embedding gateway, or None while embeddings are disabled.
    """
    if not config.embeddings_enabled:
        return None
    endpoint = os.environ.get(config.embedding_endpoint_env)
    if not endpoint or not config.embedding_model or not config.embedding_dimensions:
        invalid("enabled embeddings require endpoint environment, model and dimensions")
    from .adapters.http_embeddings import HttpEmbeddingProvider

    return HttpEmbeddingProvider(
        endpoint,
        config.embedding_model,
        config.embedding_dimensions,
        token=os.environ.get(config.embedding_token_env),
    )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 15:46 [python-coder]: Bind verified reusable query versions through scoped retrieval. (#KM-500/TICKET-20261001-KM-500b-3)

# - 2026-10-01 [python-coder]: Preserve question evidence and explicit source support through bounded research. (#KM-500/KM-500e-2)
