"""
MODULE: kernel.config_memory
GOAL: The `memory` section of the kernel configuration: which ColonyMemory backend serves a run
    and the bounds and thresholds of precedent lookup.
BUSINESS CONTEXT: Precedent is evidence, not authority (ADR-060): how many past decisions are
    pulled in, how well their text must match, and how sure Jev must be before the human is asked
    to reuse one are reviewed configuration, never hard-coded, and a null backend switches the
    whole mechanism off without a code change.
ARCHITECTURE: A frozen, extra-forbidding Pydantic section with no field defaults (the default JSON
    is the single source of values, like every other section). It lives beside `kernel.config`
    rather than in it because that file is at the size limit; `KernelConfig.memory` holds it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kernel.contracts.base import fail

Probability = Annotated[float, Field(ge=0.0, le=1.0)]


class MemoryConfig(BaseModel):
    """Decision store backend and precedent lookup settings."""

    model_config = ConfigDict(extra="forbid", frozen=True, use_attribute_docstrings=True)

    backend: Literal["file", "null"]
    """`file` reads docs/decisions through the generated index; `null` remembers nothing."""
    repository_id: str | None
    (
        "The repository part of a record's identity key (ADR-061); null uses the scope's workspace "
        "id."
    )
    decisions_dir: str
    """The store folder, relative to the repository root."""
    max_precedents: int = Field(ge=0)
    """Most past decisions pulled into one decision (0 switches precedent lookup off)."""
    min_candidate_score: Probability
    """Content-word overlap a record's question must reach to be a candidate at all."""
    applies_threshold: Probability
    """Jev's probability that a precedent applies at which it becomes evidence for the decision."""
    reuse_threshold: Probability
    """Jev's probability at which the human is asked to reuse the precedent or decide anew."""
    criterion_evidence_max: int = Field(ge=1)
    """Most evidence ids cited per criterion assessment and record criterion (not all of them)."""
    criterion_evidence_min_overlap: int = Field(ge=1)
    """Content words an evidence item must share with a criterion to be cited for it."""

    @model_validator(mode="after")
    def _ordered(self) -> MemoryConfig:
        """A precedent offered for reuse must also count as applicable."""
        if self.reuse_threshold < self.applies_threshold:
            fail("reuse_threshold must not be below applies_threshold")
        return self

    def decisions_folder(self, base: Path) -> Path:
        """Return the store folder under `base`: the one place `decisions_dir` is resolved.

        Both `decisions publish` and the notice that names where it writes use this, so the
        two cannot drift apart.
        """
        return base / self.decisions_dir


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-09 [python-coder]: use_attribute_docstrings on; the `#:` comments became attribute
#   docstrings. (#TICKET-20261009-KernelContractFieldDescriptions)
# - 2026-10-01 [python-coder]: Two thresholds, not one: applicable precedent is shown as evidence
#   from applies_threshold, but only a stronger judgement (reuse_threshold) interrupts the human
#   with a reuse question, and neither lets a precedent resolve anything. (#KernelDecisionStore)
# ====================================================================
