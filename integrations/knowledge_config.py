"""
MODULE: knowledge_config
GOAL: Reuse neutral knowledge settings while preserving kernel JSON-owned defaults.
BUSINESS CONTEXT: Keep optional knowledge retrieval bounded and traceable.
ARCHITECTURE: Adapter between neutral knowledge transport and existing kernel contracts.
"""

from copy import deepcopy
from typing import TYPE_CHECKING

from pydantic import create_model
from pydantic_core import PydanticUndefined

from knowledge.config import KnowledgeConfig


_DESCRIPTIONS = {
    "backend": "Knowledge backend: none turns graph retrieval off, neo4j serves it from Neo4j.",
    "repository_id": "Repository whose knowledge graph is queried; part of every graph scope.",
    "repository_root": "Local git checkout that resolves source text for graph hits; null for none.",
    "query_catalog_root": "Folder of admitted query recipes; null means no query catalog.",
    "neo4j_uri_env": "Name of the environment variable holding the Neo4j URI (never the URI).",
    "neo4j_username_env": "Name of the environment variable holding the Neo4j user name.",
    "neo4j_password_env": "Name of the environment variable holding the Neo4j password.",
    "database": "Neo4j database to query; null uses the server default.",
    "embeddings_enabled": "Whether embedding-based search supplements graph queries.",
    "embedding_endpoint_env": "Name of the environment variable holding the embedding service URL.",
    "embedding_token_env": "Name of the environment variable holding the embedding service token.",
    "embedding_model": "Embedding model to ask; required once embeddings are enabled.",
    "embedding_dimensions": "Vector size the embedding model returns, to match the stored index.",
    "query_timeout": "Seconds a graph query may run before it is cut off.",
}


def _required_fields():
    """Copy validation metadata, making every setting required in kernel defaults."""
    fields = {}
    for name, info in KnowledgeConfig.model_fields.items():
        required = deepcopy(info)
        required.default = PydanticUndefined
        required.default_factory = None
        required.description = _DESCRIPTIONS.get(name, required.description)
        fields[name] = (info.annotation, required)
    return fields


if TYPE_CHECKING:

    class KnowledgeBindingConfig(KnowledgeConfig):
        """Kernel view of the shared settings with defaults supplied by JSON."""
else:
    KnowledgeBindingConfig = create_model(
        "KnowledgeBindingConfig", __base__=KnowledgeConfig, **_required_fields()
    )

# DECISION HISTORY
# ================================================================================
# - 2026-10-09 [python-coder]: Field purposes are set on the copied KnowledgeConfig fields,
#   because create_model drops attribute docstrings.
#   (#TICKET-20261009-KernelContractFieldDescriptions)
# - 2026-10-01 20:00 [python-coder]: Preserve canonical evidence and optional bounded retrieval. (#TICKET-20261001-KM-400e-3)
