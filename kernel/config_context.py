"""Configuration of the bounded initial context pass; values live in the JSON defaults."""

from pydantic import BaseModel, ConfigDict, Field


class ContextEnrichmentConfig(BaseModel):
    """Read, time and payload bounds independent of the later research capability."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    enabled: bool
    source_ids: list[str]
    max_files: int = Field(ge=1, le=1000)
    max_sources: int = Field(ge=1, le=32)
    max_evidence: int = Field(ge=1, le=32)
    max_chars: int = Field(ge=1, le=20000)
    max_context_chars: int = Field(ge=1, le=12000)
    max_excerpt_chars: int = Field(ge=1, le=4000)
    max_seconds: float = Field(gt=0, le=30)
