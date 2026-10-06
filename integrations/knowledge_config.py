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


def _required_fields():
    """Copy validation metadata, making every setting required in kernel defaults."""
    fields = {}
    for name, info in KnowledgeConfig.model_fields.items():
        required = deepcopy(info)
        required.default = PydanticUndefined
        required.default_factory = None
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
# - 2026-10-01 20:00 [python-coder]: Preserve canonical evidence and optional bounded retrieval. (#TICKET-20261001-KM-400e-3)
