"""
MODULE: kernel.memory.port
GOAL: The `ColonyMemory` port (find, get and stage decisions), the query and hit value objects and
    the `NullColonyMemory` backend that remembers nothing.
BUSINESS CONTEXT: Decisions live in git-reviewed files today and may live in a graph later (the
    user's Neo4j concept); the kernel must not know which. It talks only to this port, so a graph
    backend replaces the file store without any kernel change (ADR-059), and a kernel without
    memory behaves exactly as before (`memory.backend: null`).
ARCHITECTURE: A runtime-checkable Protocol with three methods, all synchronous and bounded (the
    file backend reads small YAML files). `stage_decision` is the only write and it may touch
    only the run's own artifacts, never the repository. Precedent is evidence, not authority: a
    hit carries a text score and flags (superseded, corrected) so a caller can label it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from kernel.memory.models import DecisionRecord


class DecisionQuery(BaseModel):
    """What a new decision knows when it looks for precedent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str = Field(min_length=1)
    components: list[str] = Field(default_factory=list)
    roadmap_phase: list[str] = Field(default_factory=list)
    change_target: list[str] = Field(default_factory=list)
    risk_surface: list[str] = Field(default_factory=list)
    limit: int = Field(default=3, ge=1)
    #: Records scoring below this text match are not candidates.
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)


@dataclass(frozen=True)
class DecisionHit:
    """One precedent candidate: the record, how well its text matched and where it lives."""

    record: DecisionRecord
    score: float
    path: str
    #: Ids of records that supersede this one (derived from the others' `supersedes`).
    superseded_by: tuple[str, ...] = field(default_factory=tuple)

    @property
    def superseded(self) -> bool:
        """True if a later record replaced this one."""
        return bool(self.superseded_by or self.record.superseded_by)


@dataclass(frozen=True)
class StagedRecord:
    """Where a staged record was written (inside the run's own artifacts)."""

    decision_id: str
    path: Path


@runtime_checkable
class ColonyMemory(Protocol):
    """The kernel's view of approved decisions: read precedent, stage a new record."""

    def find_decisions(self, query: DecisionQuery) -> list[DecisionHit]:
        """Return up to `query.limit` approved records that may bear on the query, best first."""

    def get_decision(self, decision_id: str) -> DecisionRecord | None:
        """Return one approved record by id, or None when it is not (or no longer) known."""

    def stage_decision(self, record: DecisionRecord) -> StagedRecord | None:
        """Stage a record in the run's artifacts for explicit publication; None if not kept."""


class NullColonyMemory:
    """Memory that remembers nothing: no precedent, nothing staged (`memory.backend: null`)."""

    def find_decisions(self, query: DecisionQuery) -> list[DecisionHit]:
        """Return no precedent."""
        return []

    def get_decision(self, decision_id: str) -> DecisionRecord | None:
        """Know no decision."""
        return None

    def stage_decision(self, record: DecisionRecord) -> StagedRecord | None:
        """Stage nothing."""
        return None


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: The port is three synchronous methods; a graph backend that needs
#   IO wraps it in a worker thread at the call site instead of making every caller async.
#   (#KernelDecisionStore)
# ====================================================================
