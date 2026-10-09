"""Configuration of the bounded initial context pass; values live in the JSON defaults."""

from pydantic import BaseModel, ConfigDict, Field


class ContextEnrichmentConfig(BaseModel):
    """Read, time and payload bounds independent of the later research capability."""

    model_config = ConfigDict(extra="forbid", frozen=True, use_attribute_docstrings=True)
    enabled: bool
    """Whether the bounded initial context pass runs before intake."""
    source_ids: list[str]
    """Sources the pass may read."""
    max_files: int = Field(ge=1, le=1000)
    """Most files the pass may read."""
    max_sources: int = Field(ge=1, le=32)
    """Most sources the pass may consult."""
    max_evidence: int = Field(ge=1, le=32)
    """Most evidence items the pass may attach."""
    max_chars: int = Field(ge=1, le=20000)
    """Most characters the pass may read in total."""
    max_context_chars: int = Field(ge=1, le=12000)
    """Most characters of context carried forward to later steps."""
    max_excerpt_chars: int = Field(ge=1, le=4000)
    """Longest excerpt the pass keeps."""
    max_seconds: float = Field(gt=0, le=30)
    """Longest the pass may run, so it cannot delay the run."""


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-09 [python-coder]: Field purposes added; use_attribute_docstrings on.
#   (#TICKET-20261009-KernelContractFieldDescriptions)
# ====================================================================
