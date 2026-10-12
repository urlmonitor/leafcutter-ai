"""
MODULE: kernel.capabilities.research.targeting
GOAL: Turn what a decision already knows into targeted queries: the paths its options cite become
    explicit locators, the goal, criteria and option text become query hints, and the gaps a
    synthesis named and the claims of human-added options become evidence needs of their own
    (claims and gaps under separate caps; options the claim cap drops are named).
BUSINESS CONTEXT: A live run searched the goal text again every round: an option citing
    `kernel/contracts/decision.py` never had it retrieved, a synthesis said it was missing and
    nothing looked for it, and a human's added option was scored on evidence nobody searched for
    (trace review findings 4 and 5). Domain knowledge stays in the request, not in this code.
ARCHITECTURE: Functions over the parsed Plan, pure apart from one existence check. Locators are
    recognised by shape (a repository path with a known extension, optionally `#anchor` or
    `::Symbol`) and requested only when that file exists; evidence ids and bare symbols stay
    context. Every output is bounded by configuration.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath

from kernel.capabilities.decision.option_context import extract_refs
from kernel.capabilities.research.state import Plan
from kernel.config import SourceConfig
from kernel.contracts.enums import EvidenceCategory, Priority
from kernel.contracts.evidence import CLAIM_NEED_PREFIX, EvidenceNeed
from kernel.contracts.payloads import OptionContext

logger = logging.getLogger(__name__)

GAP_PREFIX = "need.gap."
CLAIM_PREFIX = CLAIM_NEED_PREFIX
_EXTENSIONS = "py|md|json|yaml|yml|toml|sql|ts|js|txt|cfg|ini|sh"
#: A repository path: it starts with a letter, digit or underscore (so `-NNN.yaml`, a fragment of
#: a placeholder name, is not one), has a known extension, then an optional anchor or symbol.
_LOCATOR = re.compile(rf"\.?\w[\w.\-]*(?:/[\w.\-]+)*\.(?:{_EXTENSIONS})(?:#\S+|::[\w.]+)?")
#: A class or contract named in prose: "Decision contract", "the Decision class", a `Decision` span.
_NAMED_SYMBOL = re.compile(
    r"\b([A-Z][A-Za-z0-9_]*)\s+(?:contract|class|model|dataclass|schema|type)\b|`([A-Z][A-Za-z0-9_]*)`")
MAX_SYMBOLS = 4


@dataclass(frozen=True)
class NeedQuery:
    """What one retrieval child is told beyond its need: query hints and exact places to fetch."""

    hints: list[str] = field(default_factory=list)
    locators: list[str] = field(default_factory=list)


def locators_of(refs: Iterable[str]) -> list[str]:
    """Return the refs that look like a repository path, `path#anchor` or `path::Symbol`."""
    return list(dict.fromkeys(r.strip() for r in refs if _LOCATOR.fullmatch(r.strip())))


def existing_locators(root: Path, locators: Iterable[str]) -> list[str]:
    """Return the locators whose file exists under `root` (a refused one is logged at debug).

    A locator is requested only if it looks like a repository path (see `locators_of`), stays
    inside the repository and names an existing file; anything else is a fragment of prose.
    """
    kept: list[str] = []
    for raw in locators:
        path = _location(raw)
        posix, win = PurePosixPath(path), PureWindowsPath(path)
        inside = not (posix.is_absolute() or win.is_absolute() or win.drive
                      or ".." in (*posix.parts, *win.parts))
        try:
            found = inside and (root / path).is_file()
        except OSError:
            logger.debug("explicit locator %r dropped: cannot be checked", raw, exc_info=True)
            continue
        if found:
            kept.append(raw)
        else:
            logger.debug("explicit locator %r dropped: no such file in the repository", raw)
    return kept


def symbols_named(texts: Iterable[str]) -> list[str]:
    """Return the class or contract names the texts mention (`Decision contract`, `Decision`)."""
    found: list[str] = []
    for text in texts:
        found += [a or b for a, b in _NAMED_SYMBOL.findall(text)]
    return list(dict.fromkeys(found))[:MAX_SYMBOLS]


def _defines(text: str, symbol: str) -> bool:
    """True if the Python source defines a top-level class or function with this name."""
    return re.search(rf"^(?:class|def|async def)\s+{re.escape(symbol)}\b", text, re.MULTILINE) is not None


def with_symbol_locators(root: Path, locators: list[str], texts: Iterable[str]) -> list[str]:
    """Return the locators with `path::Symbol` added after each Python file that defines a named one.

    When an option or gap names a contract or class ("Decision contract") and cites the file that
    holds it, fetching only the file returned the module header, not the class body (round 8
    defect f). A symbol is added only for a file that really defines it.
    """
    symbols = symbols_named(texts)
    out: list[str] = []
    for locator in locators:
        out.append(locator)
        path = _location(locator)
        if "::" in locator or "#" in locator or not path.endswith(".py") or not symbols:
            continue
        try:
            source = (root / path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            logger.debug("symbol locators for %r skipped: cannot read it", locator, exc_info=True)
            continue
        out += [f"{path}::{s}" for s in symbols if _defines(source, s)]
    return list(dict.fromkeys(out))


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


def claims_left_out(plan: Plan, claim_limit: int) -> list[str]:
    """Return one limitation per human-added option the claim cap leaves without a claim need."""
    added = [o for o in plan.options if o.human_added]
    return [f"option {o.option_id} was not researched: claim cap {claim_limit} reached"
            for o in added[claim_limit:]]


def targeted(plan: Plan, claim_limit: int, gap_limit: int, max_locators: int
             ) -> list[tuple[EvidenceNeed, NeedQuery]]:
    """Return the extra needs: human-added option claims (at most `claim_limit`), then gaps.

    Gaps are capped separately at `gap_limit`. Each need is supporting and aimed at what the
    repository says (existing patterns), with its own hints and the locators its own text names.
    """
    made: list[tuple[EvidenceNeed, NeedQuery]] = []
    for option in [o for o in plan.options if o.human_added][:claim_limit]:
        text = _option_text(option)
        need = EvidenceNeed(
            id=f"{CLAIM_PREFIX}{option.option_id}", category=EvidenceCategory.EXISTING_PATTERNS,
            priority=Priority.SUPPORTING,
            question=f"Find evidence for or against this proposed option: {text}")
        made.append((need, NeedQuery([text], locators_of(option.cited_refs)[:max_locators])))
    for number, gap in enumerate(plan.gaps[:gap_limit], start=1):
        need = EvidenceNeed(
            id=f"{GAP_PREFIX}{number}", category=EvidenceCategory.EXISTING_PATTERNS,
            priority=Priority.SUPPORTING, question=f"Find evidence for this named gap: {gap}")
        made.append((need, NeedQuery([gap], locators_of(extract_refs(gap))[:max_locators])))
    return made


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-02 [python-coder]: Claims and gaps no longer share one cap: `targeted` takes a claim
#   limit and a gap limit, and `claims_left_out` names each added option the claim cap drops
#   (live run: 19 of 21 added options were never searched). (#KernelResearchEveryAddedOption)
# - 2026-10-01 [python-coder]: A class or contract named in an option or gap text ("Decision
#   contract", `Decision`) also becomes a `path::Symbol` locator for each cited Python file that
#   defines it; a file locator alone returned header slices, not the class body. (#KernelDecisionStore)
# - 2026-10-01 [python-coder]: A locator must start with a word character and name an existing
#   file inside the repository before it is requested (live: option text produced `-NNN.yaml`).
#   (#KernelV01/E)
# - 2026-10-01 [python-coder]: locator_sources names the sources holding a cited file, because
#   the live-style end-to-end run showed an option's path refused as "not under any configured
#   source root": the child's source_ids (the need's own sources) also bound locator lookups.
#   (#KernelV01/D)
# - 2026-10-01 [python-coder]: Targeted needs and per-need queries are computed from the Plan on
#   demand (planning and source resolution both call them), so nothing about them has to be
#   persisted in the continuation. (#KernelV01/D)
# ====================================================================
