"""MODULE: kernel.config_entity
GOAL: Validate deterministic recognition limits.
BUSINESS CONTEXT: A long request cannot expand retrieval or provider work without bounds.
ARCHITECTURE: Values are supplied by the canonical kernel configuration JSON.
"""

from pydantic import BaseModel, ConfigDict, Field


class EntityContextConfig(BaseModel):
    """Independent entity-index and interpretation limits."""

    model_config = ConfigDict(extra="forbid", frozen=True, use_attribute_docstrings=True)
    enabled: bool
    """Whether entity recognition runs on the caller's text before intake."""
    index_path: str
    """Where the entity index is read from, relative to the repository root."""
    source_ids: list[str]
    """Sources whose entities may be recognised."""
    max_caller_chars: int = Field(ge=1, le=12000)
    """Most characters of the caller's text scanned for entities."""
    max_lookups: int = Field(ge=1, le=64)
    """Most index lookups per request, bounding recognition work."""
    max_entities: int = Field(ge=1, le=16)
    """Most recognised entities carried forward."""
    max_ambiguity_candidates: int = Field(ge=1, le=3)
    """Most candidate meanings kept for an ambiguous term."""
    max_meaning_chars: int = Field(ge=1, le=300)
    """Longest meaning text kept per entity."""
    max_serialized_chars: int = Field(ge=1000, le=8000)
    """Largest size of the entity context when carried in run state."""
    max_unknowns: int = Field(ge=1, le=8)
    """Most unresolved terms reported."""
    max_unknown_chars: int = Field(ge=1, le=128)
    """Longest text kept per unresolved term."""
    max_seconds: float = Field(gt=0, le=2)
    """Longest recognition may run, so it cannot delay the run."""

# DECISION HISTORY
# ================================================================================
# - 2026-10-09 [python-coder]: Field purposes added; use_attribute_docstrings on.
#   (#TICKET-20261009-KernelContractFieldDescriptions)
# - 2026-10-03 15:05 [python-coder]: Keep pre-intent meanings deterministic, scoped and separate from task evidence. (#TICKETLESS reason=user-approved-ac-first-DK300)
