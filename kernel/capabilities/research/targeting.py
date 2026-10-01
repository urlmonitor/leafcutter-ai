"""
MODULE: kernel.capabilities.research.targeting
GOAL: Turn what a decision already knows into targeted queries: the paths its options cite become
    explicit locators, the goal, criteria and option text become query hints, and the gaps a
    synthesis named and the claims of human-added options become evidence needs of their own.
BUSINESS CONTEXT: A live run searched the goal text again every round: an option citing
    `kernel/contracts/decision.py` never had it retrieved, a synthesis said it was missing and
    nothing looked for it, and a human's added option was scored on evidence nobody searched for
    (trace review findings 4 and 5). Domain knowledge stays in the request, not in this code.
ARCHITECTURE: Pure functions over the parsed Plan. Locators are recognised by shape (a repository
    path with a known extension, optionally `#anchor` or `::Symbol`); evidence ids and bare
    symbols stay context. Every output is bounded by configuration.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from kernel.capabilities.decision.option_context import extract_refs
from kernel.capabilities.research.state import Plan
from kernel.config import SourceConfig
from kernel.contracts.enums import EvidenceCategory, Priority
from kernel.contracts.evidence import EvidenceNeed
from kernel.contracts.payloads import OptionContext

GAP_PREFIX = "need.gap."
CLAIM_PREFIX = "need.claim."
_EXTENSIONS = "py|md|json|yaml|yml|toml|sql|ts|js|txt|cfg|ini|sh"
_LOCATOR = re.compile(rf"[\w.\-]+(?:/[\w.\-]+)*\.(?:{_EXTENSIONS})(?:#\S+|::[\w.]+)?")


@dataclass(frozen=True)
class NeedQuery:
    """What one retrieval child is told beyond its need: query hints and exact places to fetch."""

    hints: list[str] = field(default_factory=list)
    locators: list[str] = field(default_factory=list)


def locators_of(refs: Iterable[str]) -> list[str]:
    """Return the refs that look like a repository path, `path#anchor` or `path::Symbol`."""
    return list(dict.fromkeys(r.strip() for r in refs if _LOCATOR.fullmatch(r.strip())))


def _location(locator: str) -> str:
    """Return the file path part of a locator (without `#anchor` or `::Symbol`)."""
    return re.split(r"#|::", locator, maxsplit=1)[0]


def locator_sources(locators: Iterable[str], sources: Iterable[SourceConfig]) -> list[str]:
    """Return the ids of the repo_text sources whose roots hold one of the locators' files.

    A retrieval request's `source_ids` also bound where an explicit locator may be read, and a
    need's own sources rarely hold what an option cites (`kernel/` is not an ADR folder), so the
    request has to name the holders too. They widen the locator lookup only: a search still
    covers just the sources that serve the need's category.
    """
    held = {_location(x) for x in locators}
    found = []
    for source in sources:
        roots = [r.replace("\\", "/").strip("/") for r in source.roots]
        if source.kind == "repo_text" and any(
                path == root or path.startswith(root + "/") for path in held for root in roots):
            found.append(source.id)
    return found


def _option_text(option: OptionContext) -> str:
    """Return one option's title and description as a single query text."""
    return f"{option.title}. {option.description}" if option.description else option.title


def default_query(plan: Plan, max_locators: int) -> NeedQuery:
    """Return the query of an ordinary need: goal, criteria and option text; cited paths."""
    hints = [plan.question, *plan.criteria, *(_option_text(o) for o in plan.options)]
    cited = locators_of(ref for o in plan.options for ref in o.cited_refs)
    return NeedQuery(hints=hints, locators=cited[:max_locators])


def targeted(plan: Plan, limit: int, max_locators: int
             ) -> list[tuple[EvidenceNeed, NeedQuery]]:
    """Return the extra needs (human-added option claims first, then named gaps), at most `limit`.

    Each is supporting and aimed at what the repository says (existing patterns), with its own
    hints and the locators its own text names.
    """
    made: list[tuple[EvidenceNeed, NeedQuery]] = []
    for option in (o for o in plan.options if o.human_added):
        text = _option_text(option)
        need = EvidenceNeed(
            id=f"{CLAIM_PREFIX}{option.option_id}", category=EvidenceCategory.EXISTING_PATTERNS,
            priority=Priority.SUPPORTING,
            question=f"Find evidence for or against this proposed option: {text}")
        made.append((need, NeedQuery([text], locators_of(option.cited_refs)[:max_locators])))
    for number, gap in enumerate(plan.gaps, start=1):
        need = EvidenceNeed(
            id=f"{GAP_PREFIX}{number}", category=EvidenceCategory.EXISTING_PATTERNS,
            priority=Priority.SUPPORTING, question=f"Find evidence for this named gap: {gap}")
        made.append((need, NeedQuery([gap], locators_of(extract_refs(gap))[:max_locators])))
    return made[:limit]


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: locator_sources names the sources holding a cited file, because
#   the live-style end-to-end run showed an option's path refused as "not under any configured
#   source root": the child's source_ids (the need's own sources) also bound locator lookups.
#   (#KernelV01/D)
# - 2026-10-01 [python-coder]: Targeted needs and per-need queries are computed from the Plan on
#   demand (planning and source resolution both call them), so nothing about them has to be
#   persisted in the continuation. (#KernelV01/D)
# ====================================================================
