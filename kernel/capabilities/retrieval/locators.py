"""
MODULE: kernel.capabilities.retrieval.locators
GOAL: Fetch exact explicit locators (`path`, `path#Lx-Ly`, `path#heading`, `path#/pointer`, `path::Symbol`) as
    candidates, under the same read policy as every other read.
BUSINESS CONTEXT: When an option or finding cites a file or symbol, the next retrieval must be
    able to look that exact place up instead of hoping a lexical search surfaces it (live runs
    could not fetch `kernel/contracts/decision.py` directly). Source text stays evidence: a
    locator can only read what a search could, never more (Rev 3 sections 10.3 and 13.3).
ARCHITECTURE: Synchronous and read-only; the executor runs it in a worker thread. Every locator
    passes the path-traversal check, the scope read roots (ReadPolicy.relative), the global and
    per-source deny globs and the size and binary checks, and must lie under a configured
    repo_text source root. A refused or missing locator becomes a note, never an exception and
    never an empty result that looks like a hit. Hits carry strategy `explicit_locator`.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field, replace
from pathlib import Path, PurePosixPath, PureWindowsPath

import yaml

from knowledge.adapters.source_excerpt import excerpt as source_excerpt

from kernel.capabilities.retrieval.access import ReadPolicy, file_mtime
from kernel.capabilities.retrieval.candidates import Candidate
from kernel.capabilities.retrieval.chunking import (
    Section,
    find_heading,
    find_symbol,
    section_excerpt,
)
from kernel.config import RetrievalConfig, SourceConfig
from kernel.contracts.enums import SourceKind

STRATEGY = "explicit_locator"
_LINES = re.compile(r"L?(\d+)(?:\s*-\s*L?(\d+))?")
logger = logging.getLogger(__name__)


@dataclass
class ExplicitResult:
    """Candidates fetched by locator plus a note for each locator that could not be served."""

    candidates: list[Candidate] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def parse_locator(raw: str) -> tuple[str, str, str]:
    """Split a locator into path, selector kind and argument, preserving structured pointers."""
    text = raw.strip()
    if "::" in text:
        path, _, symbol = text.partition("::")
        return path.strip(), "symbol", symbol.strip()
    if "#" in text:
        path, _, fragment = text.partition("#")
        fragment = fragment.strip()
        kind = "pointer" if fragment.startswith("/") else "lines" if _LINES.fullmatch(fragment) else "heading"
        return path.strip(), kind, fragment
    return text, "file", ""


def _safe_relative(path: str) -> bool:
    """True if the path is relative and cannot climb out of the repository."""
    posix, win = PurePosixPath(path), PureWindowsPath(path)
    return bool(path) and not (posix.is_absolute() or win.is_absolute() or win.drive
                               or ".." in (*posix.parts, *win.parts))


def _owning_policy(policy: ReadPolicy, sources: list[SourceConfig], target: Path
                   ) -> tuple[ReadPolicy, str] | None:
    """Return (policy with the source's deny globs, source id) for the first source holding it."""
    for source in sources:
        narrowed = replace(policy, deny_globs=(*policy.deny_globs, *source.deny_globs),
                           max_file_bytes=source.max_file_bytes or policy.max_file_bytes)
        for root in narrowed.resolve_roots(source.roots).roots:
            if target == root or root in target.parents:
                return narrowed, source.id
    return None


def _section_for(kind: str, arg: str, text: str, lines: list[str]) -> tuple[Section | None, str]:
    """Return (section, reason): the part of the file the locator names, or why it is missing."""
    if kind == "lines":
        match = _LINES.fullmatch(arg)
        first = int(match.group(1)) if match else 1
        last = int(match.group(2) or first) if match else first
        low, high = sorted((first, last))
        first, last = max(1, low), max(1, high)
        if first > len(lines):
            return None, f"line {first} is beyond the end of the file ({len(lines)} lines)"
        return Section(first - 1, min(last, len(lines))), ""
    if kind == "heading":
        found = find_heading(lines, arg)
        return found, "" if found else f"no heading matches {arg!r}"
    if kind == "symbol":
        found = find_symbol(text, arg)
        return found, "" if found else f"no top-level class or function {arg!r} (or not Python)"
    return Section(0, len(lines)), ""


def _fetch_one(policy: ReadPolicy, sources: list[SourceConfig], raw: str, terms: list[str],
               cfg: RetrievalConfig) -> Candidate | str:
    """Return the Candidate for one locator, or the reason it was refused or not found."""
    path, kind, arg = parse_locator(raw)
    if not _safe_relative(path):
        return "refused: the path must be relative and stay inside the repository"
    target = (policy.root / path).resolve()
    rel = policy.relative(target)
    if rel is None:
        return "refused: outside the repository or the scope's read roots"
    owner = _owning_policy(policy, sources, target)
    if owner is None:
        return "refused: not under any configured source root"
    narrowed, source_id = owner
    outcome = narrowed.read_text(target)
    if outcome.text is None:
        return f"refused: {outcome.reason or 'unreadable'}"
    selected = _selected_excerpt(rel, kind, arg, outcome.text, terms, cfg)
    if isinstance(selected, str):
        return selected
    locator, body, truncated = selected
    low = body.lower()
    return Candidate(
        source_id=source_id, kind=SourceKind.REPOSITORY_FILE, strategy=STRATEGY, path=rel,
        title=rel, locator=locator, excerpt=body,
        hits=sum(low.count(t) for t in terms), terms=tuple(t for t in terms if t in low),
        truncated=truncated, modified_at=file_mtime(target), explicit=True)


def _selected_excerpt(path: str, kind: str, arg: str, text: str, terms: list[str],
                       cfg: RetrievalConfig) -> tuple[str, str, bool] | str:
    """Bound only the selected source value and retain an independently reusable locator."""
    if kind == "pointer":
        return _pointer_excerpt(path, arg, text, terms, cfg)
    lines = text.splitlines()
    section, why = _section_for(kind, arg, text, lines)
    if section is None:
        return f"not found: {why}"
    start, end, body, truncated = section_excerpt(lines, section, terms, cfg)
    label = f" ({section.label})" if section.label else ""
    return f"{path}#L{start + 1}-L{end}{label}", body, truncated


def _pointer_excerpt(path: str, pointer: str, text: str, terms: list[str],
                      cfg: RetrievalConfig) -> tuple[str, str, bool] | str:
    """Resolve native JSON/YAML pointers after the ordinary source-read policy has admitted bytes."""
    suffix = Path(path).suffix.lower()
    if suffix not in {".json", ".yaml", ".yml"}:
        return "refused: structured pointers require a JSON or YAML source"
    try:
        if suffix == ".json":
            json.loads(text)
        selected = source_excerpt(text.encode("utf-8"), pointer).decode("utf-8")
    except (ValueError, yaml.YAMLError, RecursionError) as exc:
        logger.warning("structured source locator unavailable: %s", type(exc).__name__)
        return "not found: invalid, absent or ambiguous structured source locator"
    if not selected.strip():
        return "not found: structured source locator selects no content"
    lines = selected.splitlines()
    _, _, body, truncated = section_excerpt(lines, Section(0, len(lines)), terms, cfg)
    return f"{path}#{pointer}", body, truncated


def fetch_explicit(policy: ReadPolicy, sources: list[SourceConfig], locators: list[str],
                   terms: list[str], cfg: RetrievalConfig) -> ExplicitResult:
    """Fetch each explicit locator exactly (at most `max_explicit_locators`), in the given order.

    Args:
        policy: Read policy (read roots, global deny globs, size limit).
        sources: The repo_text sources a locator may fall under.
        locators: Requested locators; duplicates are fetched once.
        terms: Query terms, used to pick the densest window of a long place.
        cfg: Retrieval bounds.

    Returns:
        ExplicitResult: The candidates (explicit=True) and one note per locator not served.
    """
    result = ExplicitResult()
    unique = list(dict.fromkeys(x.strip() for x in locators if x.strip()))
    for raw in unique[:cfg.max_explicit_locators]:
        fetched = _fetch_one(policy, sources, raw, terms, cfg)
        if isinstance(fetched, Candidate):
            result.candidates.append(fetched)
        else:
            result.notes.append(f"explicit locator {raw!r} {fetched}")
    skipped = len(unique) - cfg.max_explicit_locators
    if skipped > 0:
        result.notes.append(f"{skipped} explicit locator(s) not fetched "
                            f"(max_explicit_locators={cfg.max_explicit_locators})")
    return result


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: A locator is served only from inside a configured repo_text source
#   root (not only the category-selected sources), so a citation can be followed even when the
#   need's category does not list that source, while the config allowlist, read roots and deny
#   globs still bound what can be read. (#KernelV01/B)
# - 2026-10-03 18:35 [python-coder]: Resolve canonical structured references through the shared native selector before applying excerpt bounds; preserve pointer provenance and refuse invalid selectors. (#DK-300/entity-context)
# ====================================================================
