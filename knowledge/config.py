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
