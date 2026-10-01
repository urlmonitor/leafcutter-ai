"""
MODULE: kernel.capabilities.retrieval.repository
GOAL: The `repo_text` strategy: walk authorised roots, split files into sections, rank them by
    query-term hits and path or identifier matches, and cut bounded excerpts with locators.
BUSINESS CONTEXT: The one real native source of the MVP reads the project's own documents and
    code (ADRs, conventions, patterns) so a decision rests on inspectable evidence rather than an
    LLM-written answer (Rev 3 section 10.3). Live runs showed one window per file missing the
    sections that carry the answer, and a hit-count cut dropping whole packages.
ARCHITECTURE: Synchronous and side-effect free apart from reads through ReadPolicy (which wraps
    every read in try/except OSError); the executor runs it in a worker thread. Each readable file
    yields up to `sections_per_file` section candidates (chunking.py; unstructured formats keep
    the old densest window). Files named by the question (entities.py) are pinned ahead of body
    ranking. The per-source cap scales with the number of files scanned and is bounded by
    `max_candidates`; every file's best section is offered before any file's second one.
"""

from __future__ import annotations

import math
import os
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from kernel.capabilities.retrieval.access import ReadPolicy, file_mtime
from kernel.capabilities.retrieval.candidates import Candidate, SearchReport
from kernel.capabilities.retrieval.chunking import (
    Section,
    best_window,
    cut_at_boundary,
    section_excerpt,
    split_sections,
)
from kernel.capabilities.retrieval.entities import QueryEntities, entity_matches, path_terms
from kernel.config import RetrievalConfig
from kernel.contracts.enums import SourceKind

STRATEGY = "repo_text"
PINNED_PATH_TERMS = 2
MIN_FILES_FOR_COMMON_TERMS = 4

__all__ = ["STRATEGY", "cut_at_boundary", "search_repo_text", "source_cap"]

_Prioritised = list[tuple[tuple[bool, int, int, str, int], Candidate]]


@dataclass
class _FileRecord:
    """What one readable file offers: its candidates and how its path matched the question."""

    rel: str
    candidates: list[Candidate]
    file_hits: int
    exact: bool
    path_hit_terms: frozenset[str]
    head: Candidate | None = None


def _iter_files(root: Path) -> tuple[list[Path], list[Path]]:
    """Return (files, linked_dirs) under root, both sorted; a file root yields just itself.

    os.walk lists a symlinked directory in `dirnames` but never descends into it, so such links
    are returned separately for the caller to report instead of vanishing silently.
    """
    if root.is_file():
        return [root], []
    found: list[Path] = []
    linked: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        linked += [Path(dirpath) / d for d in dirnames if (Path(dirpath) / d).is_symlink()]
        found += [Path(dirpath) / name for name in sorted(filenames)]
    return found, sorted(linked)


def source_cap(files_scanned: int, cfg: RetrievalConfig) -> int:
    """Return how many candidates a source of `files_scanned` files may offer.

    The cap grows with the source (`source_candidate_ratio` per file, at least
    `source_candidate_floor`) and never exceeds `max_candidates`, the overall rerank batch bound.
    """
    wanted = max(cfg.source_candidate_floor, math.ceil(files_scanned * cfg.source_candidate_ratio))
    return min(cfg.max_candidates, wanted)


def _locator(rel: str, start: int, end: int, label: str | None) -> str:
    """Return `path#Lx-Ly`, followed by the heading path or symbol in parentheses when known."""
    base = f"{rel}#L{start + 1}-L{end}"
    return f"{base} ({label})" if label else base


def _candidate(rel: str, source_id: str, lines: list[str], terms: list[str],
               cfg: RetrievalConfig, modified: datetime | None) -> Candidate | None:
    """Build a Candidate from the densest line window of one file (None if no term occurs).

    This is the fallback for formats without sections.
    """
    start, end, hits = best_window(lines, terms, cfg.excerpt_context_lines)
    if hits == 0:
        return None
    excerpt = "\n".join(lines[start:end])
    truncated = len(excerpt) > cfg.max_excerpt_chars
    body = cut_at_boundary(excerpt, cfg.max_excerpt_chars)
    full = "\n".join(lines).lower()
    matched = tuple(t for t in terms if t in full)
    return Candidate(
        source_id=source_id, kind=SourceKind.REPOSITORY_FILE, strategy=STRATEGY, path=rel,
        title=rel, locator=_locator(rel, start, end, None), excerpt=body, hits=hits,
        terms=matched, truncated=truncated, modified_at=modified)


def _section_candidate(rel: str, source_id: str, lines: list[str], sec: Section, hits: int,
                       terms: list[str], cfg: RetrievalConfig, modified: datetime | None
                       ) -> Candidate:
    """Build the Candidate for one section: its heading path is part of the locator."""
    start, end, body, truncated = section_excerpt(lines, sec, terms, cfg)
    low = f"{sec.label or ''}\n{body}".lower()
    return Candidate(
        source_id=source_id, kind=SourceKind.REPOSITORY_FILE, strategy=STRATEGY, path=rel,
        title=rel, locator=_locator(rel, start, end, sec.label), excerpt=body, hits=hits,
        terms=tuple(t for t in terms if t in low), truncated=truncated, modified_at=modified)


def _sectioned(rel: str, source_id: str, text: str, lines: list[str], terms: list[str],
               cfg: RetrievalConfig, modified: datetime | None
               ) -> tuple[list[Candidate], int] | None:
    """Return (best section candidates, file hits), or None when the format has no sections."""
    sections = split_sections(rel, text, lines)
    if sections is None:
        return None
    lowered = [line.lower() for line in lines]
    scored: list[tuple[int, Section]] = []
    file_hits = 0
    for sec in sections:
        body = "\n".join(lowered[sec.start:sec.end])
        in_body = sum(body.count(t) for t in terms)
        file_hits += in_body
        total = in_body + 3 * sum((sec.label or "").lower().count(t) for t in terms)
        if total:
            scored.append((total, sec))
    scored.sort(key=lambda item: (-item[0], item[1].start))
    best = scored[:cfg.sections_per_file]
    return [_section_candidate(rel, source_id, lines, sec, hits, terms, cfg, modified)
            for hits, sec in best], file_hits


def _head_candidate(rel: str, source_id: str, text: str, lines: list[str], terms: list[str],
                    cfg: RetrievalConfig, modified: datetime | None) -> Candidate | None:
    """Return the opening section of a file whose path matched but whose body has no term."""
    if not lines:
        return None
    sections = split_sections(rel, text, lines)
    window = Section(0, min(len(lines), 2 * cfg.excerpt_context_lines + 1))
    first = sections[0] if sections else window
    return _section_candidate(rel, source_id, lines, first, 0, terms, cfg, modified)


def _file_record(path: Path, rel: str, text: str, source_id: str, terms: list[str],
                 entities: QueryEntities, cfg: RetrievalConfig) -> _FileRecord:
    """Evaluate one readable file: section candidates plus how its path matched the question."""
    lines, modified = text.splitlines(), file_mtime(path)
    built = _sectioned(rel, source_id, text, lines, terms, cfg, modified)
    if built is None:
        single = _candidate(rel, source_id, lines, terms, cfg, modified)
        built = ([single] if single else []), (single.hits if single else 0)
    cands, file_hits = built
    exact, matched = entity_matches(rel, entities), path_terms(rel, entities.words or terms)
    head = None
    if not cands and (exact or len(matched) >= PINNED_PATH_TERMS):
        head = _head_candidate(rel, source_id, text, lines, terms, cfg, modified)
    return _FileRecord(rel, cands, file_hits, exact, matched, head)


def _prioritised(records: list[_FileRecord], files_scanned: int, df: Counter[str]
                 ) -> _Prioritised:
    """Return (sort key, candidate) pairs, pinned files first, then path matches, then hits.

    A term found in the path of most files (the source's own folder name) says nothing about one
    file, so it is not counted as a path match.
    """
    common = {t for t, n in df.items() if files_scanned >= MIN_FILES_FOR_COMMON_TERMS
              and n * 2 > files_scanned}
    out: _Prioritised = []
    for rec in records:
        score = len(rec.path_hit_terms - common)
        pinned = rec.exact or score >= PINNED_PATH_TERMS
        cands = rec.candidates or ([rec.head] if rec.head is not None and pinned else [])
        for index, cand in enumerate(cands):
            out.append(((not pinned, -score, -rec.file_hits, rec.rel, index), cand))
    return sorted(out, key=lambda pair: pair[0])


def _select(ordered: _Prioritised, cap: int) -> list[Candidate]:
    """Pick at most `cap` candidates: every file's best section first, then second sections."""
    chosen: dict[str, tuple[tuple[bool, int, int, str, int], Candidate]] = {}
    firsts: set[str] = set()
    for key, cand in ordered:
        if len(chosen) < cap and cand.path not in firsts:
            firsts.add(cand.path)
            chosen[cand.locator] = (key, cand)
    for key, cand in ordered:
        if len(chosen) < cap:
            chosen.setdefault(cand.locator, (key, cand))
    return [cand for _, cand in sorted(chosen.values(), key=lambda pair: pair[0])]


def search_repo_text(policy: ReadPolicy, source_id: str, roots: list[Path], terms: list[str],
                     cfg: RetrievalConfig, entities: QueryEntities | None = None
                     ) -> SearchReport:
    """Search the given resolved roots for the terms.

    Args:
        policy: Read policy (containment, deny globs, size limit).
        source_id: Catalog id of the source being searched.
        roots: Resolved, authorised roots (files or directories).
        terms: Query terms (lowercase).
        cfg: Retrieval bounds.
        entities: Identifiers named in the question; files whose path carries one are pinned.

    Returns:
        SearchReport: Ranked candidates (at most `source_cap`) and skip counters.
    """
    report = SearchReport(source_id=source_id)
    wanted = QueryEntities() if entities is None else entities
    records: list[_FileRecord] = []
    df: Counter[str] = Counter()
    for root in roots:
        files, linked_dirs = _iter_files(root)
        for link in linked_dirs:
            report.skip("outside_root" if policy.relative(link) is None else "link_not_followed")
        for path in files:
            outcome = policy.read_text(path)
            if outcome.text is None:
                report.skip(outcome.reason or "unreadable")
                continue
            report.files_scanned += 1
            rel = policy.relative(path) or path.name
            rec = _file_record(path, rel, outcome.text, source_id, terms, wanted, cfg)
            df.update(rec.path_hit_terms)
            if rec.candidates or rec.head is not None:
                records.append(rec)
    ordered = _prioritised(records, report.files_scanned, df)
    cap = source_cap(report.files_scanned, cfg)
    report.candidates = _select(ordered, cap)
    cut = len(ordered) - len(report.candidates)
    if cut:
        unoffered = len({c.path for _, c in ordered}) - len({c.path for c in report.candidates})
        report.notes.append(
            f"{cut} lower-ranked section(s) cut at the source cap of {cap} candidates "
            f"({report.files_scanned} files scanned, max_candidates={cfg.max_candidates}); "
            f"{unoffered} matching file(s) not offered")
    return report


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Files are read as sections (several per file, best first), the
#   per-source cap scales with source size under max_candidates, and files whose path or name
#   carries the question's identifiers are pinned ahead of body-hit ranking, so
#   `kernel/contracts/decision.py` is offered for "the Decision contract". (#KernelV01/B)
# - 2026-10-02 [python-coder]: A symlinked directory is reported as a skip (outside_root when it
#   resolves outside the allowed area, else link_not_followed); os.walk never descends into it, so
#   on Linux an escaping link was silently dropped with no limitation. (#KernelBootstrapV0/CI)
# - 2026-10-02 [python-coder]: Excerpts are cut at a line or sentence end within the cap (still
#   marked truncated) instead of mid-sentence. (#KernelBootstrapV0/GROUND)
# - 2026-09-30 23:00 [python-coder]: One excerpt per file (the densest window) keeps the
#   candidate list small enough for one Jev relevance batch. (#KernelBootstrapV0/P5)
# ====================================================================
