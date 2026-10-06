"""MODULE: kernel.config_entity
GOAL: Validate deterministic recognition limits.
BUSINESS CONTEXT: A long request cannot expand retrieval or provider work without bounds.
ARCHITECTURE: Values are supplied by the canonical kernel configuration JSON.
"""

from pydantic import BaseModel, ConfigDict, Field


class EntityContextConfig(BaseModel):
    """Independent entity-index and interpretation limits."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    enabled: bool
    index_path: str
    source_ids: list[str]
    max_caller_chars: int = Field(ge=1, le=12000)
    max_lookups: int = Field(ge=1, le=64)
    max_entities: int = Field(ge=1, le=16)
    max_ambiguity_candidates: int = Field(ge=1, le=3)
    max_meaning_chars: int = Field(ge=1, le=300)
    max_serialized_chars: int = Field(ge=1000, le=8000)
    max_unknowns: int = Field(ge=1, le=8)
    max_unknown_chars: int = Field(ge=1, le=128)
    max_seconds: float = Field(gt=0, le=2)

# DECISION HISTORY
# ================================================================================
# - 2026-10-03 15:05 [python-coder]: Keep pre-intent meanings deterministic, scoped and separate from task evidence. (#TICKETLESS reason=user-approved-ac-first-DK300)
