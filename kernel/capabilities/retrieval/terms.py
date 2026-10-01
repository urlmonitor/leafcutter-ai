"""
MODULE: kernel.capabilities.retrieval.terms
GOAL: Deterministic query-term extraction from an evidence need and the task's technologies.
BUSINESS CONTEXT: What to search for is computable, so code decides it (ADR-053 section 5); Jev
    is only asked afterwards which of the found candidates are relevant.
ARCHITECTURE: Pure functions. Terms are lowercase tokens of three or more characters minus a
    stopword list, first occurrence order, technologies appended. `build_query_terms` orders
    them goal first (the first hint), then other hints, then the need's own template wording.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

MIN_TERM_LENGTH = 3
_TOKEN = re.compile(r"[a-z0-9][a-z0-9_\-]*")
STOPWORDS = frozenset("""
a about above after again all also am an and any are as at be because been before being below
between both but by can could did do does doing down during each few for from further had has
have having he her here hers him his how i if in into is it its just me more most my no nor not
now of off on once only or other our out over own same she should so some such than that the
their them then there these they this those through to too under until up very was we were what
when where which while who whom why will with would you your use using used which whether
should
""".split()) | frozenset("decide decision question need needs".split())
#: Generic decision words: useless as body terms (they match every ADR) but meaningful in a path.
GENERIC_WORDS = frozenset("decide decision decisions question need needs".split())


def extract_terms(text: str, technologies: Sequence[str] = (), max_terms: int = 24) -> list[str]:
    """Return the search terms for `text` plus `technologies`.

    Args:
        text: The need's question.
        technologies: Task metadata naming technologies (kept as extra terms).
        max_terms: Upper bound on the number of terms returned.

    Returns:
        list[str]: Distinct lowercase terms, at most `max_terms`, in first-occurrence order.
    """
    tokens = _TOKEN.findall(text.lower())
    tokens += [t for tech in technologies for t in _TOKEN.findall(tech.lower())]
    kept = [t for t in tokens if len(t) >= MIN_TERM_LENGTH and t not in STOPWORDS]
    return list(dict.fromkeys(kept))[:max_terms]


def extract_path_terms(text: str, max_terms: int = 24) -> list[str]:
    """Return the words of `text` worth matching against file paths.

    Like `extract_terms`, but the generic decision words are kept: `decision` says nothing about
    a document body yet names a module (`kernel/contracts/decision.py`).
    """
    plain = STOPWORDS - GENERIC_WORDS
    kept = [t for t in _TOKEN.findall(text.lower()) if len(t) >= MIN_TERM_LENGTH and t not in plain]
    return list(dict.fromkeys(kept))[:max_terms]


def _terms(text: str) -> list[str]:
    """Return the distinct search terms of one text, in first-occurrence order."""
    kept = [t for t in _TOKEN.findall(text.lower())
            if len(t) >= MIN_TERM_LENGTH and t not in STOPWORDS]
    return list(dict.fromkeys(kept))


def build_query_terms(question: str, hints: Sequence[str] = (),
                      technologies: Sequence[str] = (), max_terms: int = 24) -> list[str]:
    """Return the search terms for a need, led by its hints (the goal first).

    The need's own wording carries a category template ("concrete candidates items facts ...")
    whose filler used to take the first slots, and a long goal lost its end. With hints, the first
    hint (the goal) is taken whole up to a share of `max_terms`, then the technologies, the other
    hints (criteria, option text), and last the need's own words. A quarter of the bound is kept
    for the other hints, so a long goal cannot push the criteria out. Without hints this is
    `extract_terms`.

    Args:
        question: The need's question (template wording included).
        hints: Query texts in priority order; the first is the goal.
        technologies: Task metadata naming technologies.
        max_terms: Upper bound on the number of terms returned.

    Returns:
        list[str]: Distinct lowercase terms, at most `max_terms`.
    """
    if not hints:
        return extract_terms(question, technologies, max_terms)
    goal = _terms(hints[0])
    extra = [t for t in _terms(" ".join(hints[1:])) if t not in set(goal)]
    reserve = min(len(extra), max_terms // 4)
    ordered = [*goal[:max_terms - reserve], *_terms(" ".join(technologies)), *extra,
               *_terms(question), *goal[max_terms - reserve:]]
    return list(dict.fromkeys(ordered))[:max_terms]


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: build_query_terms puts the goal first and the need-template filler
#   last, and keeps room for criteria and option text; the first 24 terms of "template + goal"
#   cut off the end of the goal in a live run. (#KernelV01/D)
# - 2026-10-01 [python-coder]: `extract_path_terms` keeps the generic decision words for path
#   matching only, so "the Decision contract" finds decision.py. (#KernelV01/B)
# - 2026-09-30 23:00 [python-coder]: The stopword list includes generic decision words
#   (decide, question, need) that match every ADR and would drown real terms.
#   (#KernelBootstrapV0/P5)
# ====================================================================
