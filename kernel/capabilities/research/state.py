"""
MODULE: kernel.capabilities.research.state
GOAL: The research capability's continuation model and the working state shared by its nodes.
BUSINESS CONTEXT: Research pauses while child retrievals and a possible synthesis run; everything
    needed to resume (needs, which sources were dispatched, evidence collected so far) lives in
    the work item's continuation, never on a call stack (Rev 3 section 7.4).
ARCHITECTURE: ResearchContinuation is the JSON-serialisable part (frozen Pydantic model,
    design part 4 fields plus the collected bundle so a resume needs no lookup to rebuild it).
    Plan is the parsed request; Collected accumulates merged child results.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import Field

from kernel.contracts.base import KernelModel
from kernel.contracts.enums import NeedStatus
from kernel.contracts.evidence import (
    Contradiction,
    Evidence,
    EvidenceNeed,
    Finding,
    UnavailableSource,
)

STATUS_RANK = {NeedStatus.UNAVAILABLE: 0, NeedStatus.OPEN: 1, NeedStatus.PARTIAL: 2,
               NeedStatus.SATISFIED: 3}


class ResearchContinuation(KernelModel):
    """Persisted research state (phase: planned, collected or synthesizing)."""

    phase: str = "planned"
    needs: list[EvidenceNeed] = Field(default_factory=list)
    child_map: dict[str, list[str]] = Field(default_factory=dict)
    unavailable: list[UnavailableSource] = Field(default_factory=list)
    attempted: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    coverage: dict[str, NeedStatus] = Field(default_factory=dict)
    contradictions: list[Contradiction] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    truncated: bool = False
    synthesized: bool = False


@dataclass
class Plan:
    """The parsed research request."""

    question: str
    expected_coverage: str
    mandated: list[EvidenceNeed]
    source_restrictions: list[str]


@dataclass
class Collected:
    """Evidence, coverage and findings merged from finished children."""

    evidence: dict[str, Evidence] = field(default_factory=dict)
    coverage: dict[str, NeedStatus] = field(default_factory=dict)
    attempted: list[str] = field(default_factory=list)
    unavailable: list[UnavailableSource] = field(default_factory=list)
    contradictions: list[Contradiction] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    truncated: bool = False

    def merge_coverage(self, need_id: str, status: NeedStatus) -> None:
        """Keep the best status reported for a need across bundles."""
        current = self.coverage.get(need_id)
        if current is None or STATUS_RANK[status] > STATUS_RANK[current]:
            self.coverage[need_id] = status


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:00 [python-coder]: The collected evidence is stored in the continuation
#   (beyond the design's field list) so the synthesis resume can rebuild the bundle even if the
#   kernel's evidence lookup misses an item. (#KernelBootstrapV0/P5)
# ====================================================================
