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

from kernel.contracts.verbatim import VerbatimJson

from dataclasses import dataclass, field

from pydantic import Field, JsonValue

from kernel.contracts.base import KernelModel
from kernel.contracts.enums import NeedStatus
from kernel.contracts.evidence import (
    Contradiction,
    Evidence,
    EvidenceNeed,
    Finding,
    UnavailableSource,
)
from kernel.contracts.payloads import OptionContext
from kernel.contracts.work import RequestProposal

#: Prefix of the note of a bundle-level contradiction that names no evidence pair.
UNLOCALISED = "unlocalised: "
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
    assessments: dict[str, dict[str, VerbatimJson]] = Field(default_factory=dict)
    contradictions: list[Contradiction] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    truncated: bool = False
    synthesized: bool = False
    #: Supporting needs only a host can serve, held back until the native evidence proves thin.
    deferred: list[RequestProposal] = Field(default_factory=list)
    deferred_dispatched: bool = False
    #: Needs whose evidence matched the topic but did not answer (kept partial across a resume).
    unanswered: list[str] = Field(default_factory=list)


def contradiction_key(item: Contradiction) -> tuple[frozenset[str], str]:
    """Return the identity of a contradiction: its evidence pair (unordered) and its claim."""
    return frozenset((item.a, item.b)), item.note.strip()


@dataclass
class Plan:
    """The parsed research request."""

    question: str
    expected_coverage: str
    mandated: list[EvidenceNeed]
    source_restrictions: list[str]
    needs_only: bool = False
    answer_requirements: dict[str, JsonValue] | None = None
    assessment: dict[str, JsonValue] | None = None
    #: What the decision already knows: its options, approved criteria and named gaps.
    options: list[OptionContext] = field(default_factory=list)
    criteria: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    #: Jev calls the requester keeps for itself; research never spends into them.
    jev_reserve: int = 0


@dataclass
class Collected:
    """Evidence, coverage and findings merged from finished children."""

    evidence: dict[str, Evidence] = field(default_factory=dict)
    coverage: dict[str, NeedStatus] = field(default_factory=dict)
    assessments: dict[str, dict[str, VerbatimJson]] = field(default_factory=dict)
    attempted: list[str] = field(default_factory=list)
    unavailable: list[UnavailableSource] = field(default_factory=list)
    contradictions: list[Contradiction] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    truncated: bool = False
    #: What a synthesis said it could not find.
    unknowns: list[str] = field(default_factory=list)
    #: Per need, the ids of its kept evidence that passed relevance (what an answer is judged on).
    need_evidence: dict[str, list[str]] = field(default_factory=dict)
    #: Per need, the retrieval cut notes its child reported (summarised by the decision).
    need_notes: dict[str, list[str]] = field(default_factory=dict)
    unanswered: list[str] = field(default_factory=list)

    def add_contradictions(self, items: list[Contradiction]) -> None:
        """Record contradictions once per evidence pair and claim.

        Args:
            items: Actual contradictory evidence to merge.
        """
        seen = {contradiction_key(c) for c in self.contradictions}
        for item in items:
            key = contradiction_key(item)
            if key not in seen:
                seen.add(key)
                self.contradictions.append(item)

    @property
    def has_localised_contradiction(self) -> bool:
        """True if any recorded contradiction names the evidence pair it is about."""
        return any(not c.note.startswith(UNLOCALISED) for c in self.contradictions)

    @property
    def has_unlocalised_contradiction(self) -> bool:
        """True if a bundle-level contradiction without a localised pair was recorded."""
        return any(c.note.startswith(UNLOCALISED) for c in self.contradictions)

    def merge_coverage(self, need_id: str, status: NeedStatus) -> None:
        """Keep the best status reported for a need across bundles."""
        current = self.coverage.get(need_id)
        if current is None or STATUS_RANK[status] > STATUS_RANK[current]:
            self.coverage[need_id] = status


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: The Plan carries the requester's Jev reserve. (#KernelV01/E)
# - 2026-10-01 [python-coder]: The Plan carries option_context, criteria and gaps, and Collected
#   the synthesis unknowns and the per-need evidence ids behind answer-aware coverage; neither is
#   persisted (a resume re-reads the child bundles). (#KernelV01/D)
# - 2026-10-02 [python-coder]: The continuation keeps the host-only supporting needs that were
#   held back and whether they were dispatched. (#KernelBootstrapV0/GROUND)
# - 2026-10-01 23:00 [python-coder]: Contradictions are deduplicated by evidence pair and claim at
#   the single point where they are added: a resumed collect re-reads every child bundle, so the
#   same disagreement used to arrive again and again. (#KernelBootstrapV0/GROUND)
# - 2026-09-30 23:00 [python-coder]: The collected evidence is stored in the continuation
#   (beyond the design's field list) so the synthesis resume can rebuild the bundle even if the
#   kernel's evidence lookup misses an item. (#KernelBootstrapV0/P5)
# ====================================================================
