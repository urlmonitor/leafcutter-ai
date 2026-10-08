"""
MODULE: kernel.capabilities.retrieval.entities
GOAL: Extract exact identifiers from a question (ADR-NNN, AC ids, file names, dotted symbols,
    paths) and match them, and the query terms, against a file's path.
BUSINESS CONTEXT: A lexical pre-filter that ranks by body hits alone dropped the files the
    question named outright (`kernel/contracts/decision.py` for "the Decision contract"). A file
    whose path or name carries the question's identifiers is a candidate before any body
    ranking (Rev 3 section 10.3: sources bounded, and what was cut is reported).
ARCHITECTURE: Pure functions; the output is lowercase so matching is case-insensitive on every
    platform. Identifier matching is by path fragment with alphanumeric boundaries, so `ACD-100`
    does not match `ACD-1000.yaml`.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from kernel.capabilities.retrieval.terms import extract_path_terms

_FILE_EXT = r"(?:py|md|json|ya?ml|sql|toml|txt|js|ts|sh)"
_ID = re.compile(r"(?<![\w-])([A-Za-z]{2,6}-\d+[A-Za-z0-9]*(?:-\d+)*)(?![\w])")
_ADR_SPACED = re.compile(r"\bADR\s+(\d{1,4})\b", re.IGNORECASE)
_PATH = re.compile(r"(?<![\w/.\\])((?:[\w.\-]+[/\\])+[\w.\-]+)")
_FILE = re.compile(rf"(?<![\w/\\])([\w\-]+\.{_FILE_EXT})(?![\w])", re.IGNORECASE)
_DOTTED = re.compile(r"(?<![\w/.])([A-Za-z_]\w+(?:\.[A-Za-z_]\w+)+)(?![\w(/])")
_PATH_TOKEN = re.compile(r"[a-z0-9]+")
MIN_SUBSTRING_TERM = 4


@dataclass(frozen=True)
class QueryEntities:
    """Exact identifiers named in a question (all lowercase)."""

    ids: tuple[str, ...] = ()
    paths: tuple[str, ...] = ()
    names: tuple[str, ...] = ()
    #: Question words to look for in paths (includes generic words like "decision").
    words: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        """True if the question named at least one identifier (path words do not count)."""
        return bool(self.ids or self.paths or self.names)


def _normalise_id(raw: str) -> str:
    """Lowercase an id; ADR numbers are zero-padded to three digits like the ADR file names."""
    low = raw.lower()
    adr = re.fullmatch(r"adr-(\d{1,3})", low)
    return f"adr-{int(adr.group(1)):03d}" if adr else low


def extract_entities(question: str) -> QueryEntities:
    """Return the identifiers `question` names: ids, path fragments and file names.

    Dotted symbols (`kernel.contracts.decision`) become path fragments (`kernel/contracts/
    decision`); `.py` and other file names become names; anything with a slash is a path.
    """
    ids = [_normalise_id(m) for m in _ID.findall(question)]
    ids += [f"adr-{int(n):03d}" for n in _ADR_SPACED.findall(question)]
    paths = [m.replace("\\", "/").lower().strip("./") for m in _PATH.findall(question)]
    names = [m.lower() for m in _FILE.findall(question)]
    for dotted in _DOTTED.findall(question):
        if re.search(rf"\.{_FILE_EXT}$", dotted, re.IGNORECASE):
            continue
        parts = dotted.lower().split(".")
        if all(len(p) >= 2 for p in parts):
            paths.append("/".join(parts))
    return QueryEntities(tuple(dict.fromkeys(ids)), tuple(dict.fromkeys(p for p in paths if p)),
                         tuple(dict.fromkeys(names)), tuple(extract_path_terms(question)))


def entity_matches(rel: str, entities: QueryEntities) -> bool:
    """True if the relative path carries one of the question's identifiers."""
    low = rel.lower()
    if any(re.search(rf"(?<![a-z0-9]){re.escape(i)}(?![a-z0-9])", low) for i in entities.ids):
        return True
    if any(p in low for p in entities.paths):
        return True
    return any(low == n or low.endswith("/" + n) for n in entities.names)


def path_terms(rel: str, terms: Sequence[str]) -> frozenset[str]:
    """Return the query terms that occur in the path (a short term must equal a path token)."""
    low = rel.lower()
    tokens = set(_PATH_TOKEN.findall(low))
    return frozenset(t for t in terms
                     if (t in low if len(t) >= MIN_SUBSTRING_TERM else t in tokens))


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Identifiers are matched on the path only, with alphanumeric
#   boundaries, so a file is pinned by what it is called, not by a word in its body (body hits
#   keep ranking the rest). (#KernelV01/B)
# ====================================================================
