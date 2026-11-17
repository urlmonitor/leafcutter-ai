"""Bounded caller context and the evidence gathered before intent classification.

Caller context is a claim supplied by the client. Retrieved excerpts are source data,
never instructions or proof of runtime availability or user approval.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from kernel.contracts.base import KernelModel

ContextText = Annotated[str, StringConstraints(max_length=4000)]


class CallerContext(KernelModel):
    """Optional host observations and conversation supplied explicitly by the client."""

    host: str | None = Field(default=None, max_length=256)
    capabilities: list[ContextText] = Field(default_factory=list, max_length=32)
    conversation: list[ContextText] = Field(default_factory=list, max_length=12)
    observations: list[ContextText] = Field(default_factory=list, max_length=12)


class ContextExcerpt(KernelModel):
    """A locally retrieved, redacted excerpt with a hash of the retained text."""

    source_id: str
    locator: str
    excerpt: str
    content_hash: str
    truncated: bool = False


class EnrichedContext(KernelModel):
    """Checkpointed result of one initial context pass; it never selects an intent."""

    original_goal: str
    caller_context: CallerContext = Field(default_factory=CallerContext)
    workspace_id: str
    repository_root: str
    registered_capabilities: list[str] = Field(default_factory=list)
    evidence: list[ContextExcerpt] = Field(default_factory=list)
    sources_consulted: list[str] = Field(default_factory=list)
    files_scanned: int = Field(default=0, ge=0)
    limitations: list[str] = Field(default_factory=list)
    truncated: bool = False
    status: Literal["gathered", "no_evidence", "partial", "unavailable", "disabled"]
