"""
MODULE: kernel.capabilities.criterion_evidence
GOAL: Choose, for one criterion (and optionally one option), the evidence ids that are relevant to
    it, instead of citing every evidence id for every criterion.
BUSINESS CONTEXT: A live decision cited all 20 evidence ids on each of its criterion assessments,
    so the citation said nothing about what supports which judgement (round 8 defect e). A
    reader, and a later run reusing the record as precedent, needs the evidence that bears on that
    criterion. Jev judged every criterion against all of the evidence, so relevance here is a
    deterministic, inspectable overlap between the criterion's words and the evidence text, plus
    the evidence the option itself cites; it is a citation aid, never a score.
ARCHITECTURE: Pure functions over evidence items and texts. The content-word tokeniser is the one
    the file memory backend uses for precedent matching. Bounds come from `memory` config
    (`criterion_evidence_max`, `criterion_evidence_min_overlap`).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from kernel.contracts.decision import Criterion, Option
from kernel.contracts.evidence import Evidence
from kernel.memory.file_store import tokens


def _evidence_tokens(item: Evidence) -> frozenset[str]:
    """Return the content words of an evidence item's locator, title and excerpt."""
    return tokens(f"{item.source.locator} {item.source.title} {item.excerpt or ''}")


def relevant_evidence_ids(evidence: Sequence[Evidence], text: str, *, limit: int,
                          min_overlap: int, cited: Iterable[str] = ()) -> list[str]:
    """Return up to `limit` evidence ids that bear on `text`, best first.

    Evidence the option cites comes first (in the option's order). The rest are ranked by the
    number of content words shared with `text` and kept when they share at least `min_overlap`;
    if none does, the single best item with any overlap is kept so a criterion with a weak match
    still cites something rather than nothing. Ties keep the evidence order.
    """
    by_id = {e.id: e for e in evidence}
    chosen = [i for i in dict.fromkeys(cited) if i in by_id][:limit]
    wanted = tokens(text)
    scored = sorted(((len(wanted & _evidence_tokens(e)), n, e.id)
                     for n, e in enumerate(evidence) if e.id not in chosen),
                    key=lambda row: (-row[0], row[1]))
    strong = [i for score, _, i in scored if score >= max(1, min_overlap)]
    weak = [i for score, _, i in scored[:1] if score >= 1]
    return [*chosen, *(strong or weak)][:limit]


def criterion_text(criterion: Criterion) -> str:
    """Return the text a criterion's evidence is matched against."""
    return criterion.question


def option_text(option: Option) -> str:
    """Return the text of an option (its title and description) for option-level matching."""
    return f"{option.title} {option.description}"


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Per-criterion citations come from word overlap plus what the option
#   cites, bounded by memory.criterion_evidence_max; the first live decision cited all 20 ids for
#   every criterion, which made the citation meaningless. (#KernelDecisionStore)
# ====================================================================
