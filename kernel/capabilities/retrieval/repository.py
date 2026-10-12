"""
MODULE: kernel.capabilities.retrieval.repository
GOAL: The `repo_text` strategy: walk authorised roots, split files into sections, order them by a
    length-normalised, rarity-weighted score (path and identifier matches counted in), and cut
    bounded excerpts with locators.
BUSINESS CONTEXT: The one real native source of the MVP reads the project's own documents and
    code (ADRs, conventions, patterns) so a decision rests on inspectable evidence rather than an
    LLM-written answer (Rev 3 section 10.3). Live runs showed one window per file missing the
    sections that carry the answer, and a hit-count cut dropping whole packages.
ARCHITECTURE: Synchronous and side-effect free apart from reads through ReadPolicy (which wraps
    every read in try/except OSError); the executor runs it in a worker thread. Each readable file
    yields up to `sections_per_file` section candidates (chunking.py; unstructured formats keep
    the old densest window) and feeds every section it scans into the source's corpus statistics
    (scoring.py), so the score is known once the source has been scanned. Files named by the
    question (entities.py) and registries whose vocabulary it speaks are pinned ahead of body
    ranking. The per-source cap scales with the number of files scanned and is bounded by
    `max_candidates`; every file's best section is offered before any file's second one.
"""

from __future__ import annotations

import math
import os
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
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
from kernel.capabilities.retrieval.scoring import (
    CorpusStats,
    candidate_score,
    count_terms,
    registry_vocabulary,
    reviews_run_of_goal,
    stand_in_score,
)
from kernel.config import RetrievalConfig
from kernel.contracts.enums import SourceKind

STRATEGY = "repo_text"
PINNED_PATH_TERMS = 2
MIN_FILES_FOR_COMMON_TERMS = 4
#: Shortest query term that counts as a word of the project's folder name (a tiny term would
#: match inside it by accident).
MIN_PROJECT_TERM = 4

__all__ = ["STRATEGY", "common_terms", "cut_at_boundary", "search_repo_text", "source_cap"]

_Key = tuple[bool, float, str, int]
_Prioritised = list[tuple[_Key, Candidate]]


@dataclass
class _FileRecord:
    """What one readable file offers: its candidates and how its path matched the question."""

    rel: str
    candidates: list[Candidate]
    exact: bool
    path_hit_terms: frozenset[str]
    head: Candidate | None = None
    vocabulary: frozenset[str] = frozenset()
    """Query words that are names of this structured file's keys (its registry vocabulary)."""


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
               cfg: RetrievalConfig, modified: datetime | None, stats: CorpusStats | None = None
               ) -> Candidate | None:
    """Build a Candidate from the densest line window of one file (None if no term occurs).

    This is the fallback for formats without sections: the file counts as one section.
    """
    full = "\n".join(lines).lower()
    counts = count_terms(full, "", terms)
    if stats is not None:
        stats.add_section(len(full), counts)
    start, end, hits = best_window(lines, terms, cfg.excerpt_context_lines)
    if hits == 0:
        return None
    excerpt = "\n".join(lines[start:end])
    truncated = len(excerpt) > cfg.max_excerpt_chars
    body = cut_at_boundary(excerpt, cfg.max_excerpt_chars)
    return Candidate(
        source_id=source_id, kind=SourceKind.REPOSITORY_FILE, strategy=STRATEGY, path=rel,
        title=rel, locator=_locator(rel, start, end, None), excerpt=body, hits=hits,
        terms=tuple(t for t in terms if t in counts), truncated=truncated, modified_at=modified,
        length=len(full), term_counts=tuple(counts.items()))


def _section_candidate(rel: str, source_id: str, lines: list[str], sec: Section,
                       counts: Mapping[str, int], terms: list[str], cfg: RetrievalConfig,
                       modified: datetime | None) -> Candidate:
    """Build the Candidate for one section: its heading path is part of the locator."""
    start, end, body, truncated = section_excerpt(lines, sec, terms, cfg)
    return Candidate(
        source_id=source_id, kind=SourceKind.REPOSITORY_FILE, strategy=STRATEGY, path=rel,
        title=rel, locator=_locator(rel, start, end, sec.label), excerpt=body,
        hits=sum(counts.values()), terms=tuple(t for t in terms if t in counts),
        truncated=truncated, modified_at=modified,
        length=len("\n".join(lines[sec.start:sec.end])), term_counts=tuple(counts.items()))


def _sectioned(rel: str, source_id: str, text: str, lines: list[str], terms: list[str],
               cfg: RetrievalConfig, modified: datetime | None, stats: CorpusStats
               ) -> list[Candidate] | None:
    """Return the file's best section candidates, or None when the format has no sections.

    Every section is added to the corpus statistics; the best `sections_per_file` (by a stand-in
    score) become candidates.
    """
    sections = split_sections(rel, text, lines, cfg.max_section_lines)
    if sections is None:
        return None
    lowered = [line.lower() for line in lines]
    scored: list[tuple[float, Section, dict[str, int]]] = []
    for sec in sections:
        body = "\n".join(lowered[sec.start:sec.end])
        counts = count_terms(body, (sec.label or "").lower(), terms)
        stats.add_section(len(body), counts)
        if counts:
            scored.append((stand_in_score(counts, len(body), cfg), sec, counts))
    scored.sort(key=lambda item: (-item[0], item[1].start))
    return [_section_candidate(rel, source_id, lines, sec, counts, terms, cfg, modified)
            for _, sec, counts in scored[:cfg.sections_per_file]]


def _head_candidate(rel: str, source_id: str, text: str, lines: list[str], terms: list[str],
                    cfg: RetrievalConfig, modified: datetime | None) -> Candidate | None:
    """Return the opening section of a file whose path matched but whose body has no term."""
    if not lines:
        return None
    sections = split_sections(rel, text, lines)
    window = Section(0, min(len(lines), 2 * cfg.excerpt_context_lines + 1))
    first = sections[0] if sections else window
    return _section_candidate(rel, source_id, lines, first, {}, terms, cfg, modified)


def _file_record(path: Path, rel: str, text: str, source_id: str, terms: list[str],
                 entities: QueryEntities, cfg: RetrievalConfig, stats: CorpusStats,
                 goal: str | None = None) -> _FileRecord:
    """Evaluate one readable file: section candidates plus how its path matched the question."""
    lines, modified = text.splitlines(), file_mtime(path)
    cands = _sectioned(rel, source_id, text, lines, terms, cfg, modified, stats)
    if cands is None:
        single = _candidate(rel, source_id, lines, terms, cfg, modified, stats)
        cands = [single] if single else []
    exact, matched = entity_matches(rel, entities), path_terms(rel, entities.words or terms)
    head = None
    if not cands and (exact or len(matched) >= PINNED_PATH_TERMS):
        head = _head_candidate(rel, source_id, text, lines, terms, cfg, modified)
    if goal and reviews_run_of_goal(rel, text, goal, cfg.review_quote_ratio,
                                    cfg.review_path_markers):
        cands = [replace(c, reviews_goal=True) for c in cands]
        head = replace(head, reviews_goal=True) if head is not None else None
    return _FileRecord(rel, cands, exact, matched, head, registry_vocabulary(rel, text, terms))


def common_terms(files_scanned: int, path_df: Counter[str], project: frozenset[str]
                 ) -> frozenset[str]:
    """Return the terms too generic to say anything about one file's path.

    A term found in the path of most files (the source's own folder name) does not tell files
    apart, and neither does a word of the project's own name (the workspace id): the project name
    is in every path and body of its own documents. They are not counted as path matches.
    """
    if files_scanned < MIN_FILES_FOR_COMMON_TERMS:
        return project
    spread = {t for t, n in path_df.items() if n * 2 > files_scanned}
    return frozenset(spread) | project


def _scored(cand: Candidate, path_hits: frozenset[str], stats: CorpusStats, cfg: RetrievalConfig
            ) -> Candidate:
    """Return the candidate with the query terms its path names and its source-level score.

    The score is the section's BM25-style score plus `path_match_weight` times the rarity of every
    such term: a file named after the topic ranks well, while a path that merely shares a word
    cannot outrank a section that says much more.
    """
    named = replace(cand, path_hits=tuple(sorted(path_hits)))
    return replace(named, score=candidate_score(named, stats, stats.average_length, cfg))


def _prioritised(records: list[_FileRecord], common: frozenset[str], stats: CorpusStats,
                 terms: Sequence[str], cfg: RetrievalConfig) -> _Prioritised:
    """Return (sort key, candidate) pairs: pinned files first, then by BM25-style score.

    A file is pinned when the question names it (an identifier), its path carries two distinctive
    question words, or it is a registry whose vocabulary the question speaks. The rest are ordered
    by one number: the section's length-normalised, document-frequency-weighted score plus the
    path boost (a live run ranked schema files with 1 to 4 hits above files with 20 to 36, and
    later registry JSON with 200 hits above the files that answer).
    """
    out: _Prioritised = []
    for rec in records:
        bonus = rec.path_hit_terms - common
        named = bonus & set(terms)
        pinned = (rec.exact or len(bonus) >= PINNED_PATH_TERMS
                  or len(rec.vocabulary) >= cfg.registry_pin_min_terms)
        cands = rec.candidates or ([rec.head] if rec.head is not None and pinned else [])
        scored = sorted((_scored(c, named, stats, cfg) for c in cands),
                        key=lambda c: (-c.score, c.locator))
        for index, cand in enumerate(scored):
            out.append(((not pinned, -cand.score, rec.rel, index), cand))
    return sorted(out, key=lambda pair: pair[0])


def _select(ordered: _Prioritised, cap: int) -> list[Candidate]:
    """Pick at most `cap` candidates: every file's best section first, then second sections."""
    chosen: dict[str, tuple[_Key, Candidate]] = {}
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
                     cfg: RetrievalConfig, entities: QueryEntities | None = None,
                     project_names: Sequence[str] = (), goal: str | None = None) -> SearchReport:
    """Search the given resolved roots for the terms.

    Args:
        policy: Read policy (containment, deny globs, size limit).
        source_id: Catalog id of the source being searched.
        roots: Resolved, authorised roots (files or directories).
        terms: Query terms (lowercase).
        cfg: Retrieval bounds.
        entities: Identifiers named in the question; files whose path carries one are pinned.
        project_names: Names of the project (the workspace id); their words say nothing about
            which file is meant, so a path match on them is not distinctive. The checkout's
            folder name is not one of them: a worktree named `kernel-v01` would make `kernel/`
            an indistinct path, so the ranking would depend on where the files are checked out.
        goal: The request's goal; a document that reviews a kernel run of it is flagged.

    Returns:
        SearchReport: Ranked candidates (at most `source_cap`), corpus statistics for scoring and
            skip counters.
    """
    report = SearchReport(source_id=source_id)
    wanted = QueryEntities() if entities is None else entities
    records: list[_FileRecord] = []
    path_df: Counter[str] = Counter()
    for root in roots:
        files, linked_dirs = _iter_files(root)
        for link in linked_dirs:
            report.skip("outside_root" if policy.relative(link) is None else "link_not_followed")
        for path in files:
            outcome = policy.read_text(path)
            if outcome.text is None:
                report.skip(outcome.reason or "unreadable")
                if outcome.reason == "too_large":
                    report.note_oversized(policy.relative(path) or path.name,
                                          policy.max_file_bytes)
                continue
            report.files_scanned += 1
            rel = policy.relative(path) or path.name
            rec = _file_record(path, rel, outcome.text, source_id, terms, wanted, cfg,
                               report.stats, goal)
            path_df.update(rec.path_hit_terms)
            if rec.candidates or rec.head is not None:
                records.append(rec)
    common = common_terms(report.files_scanned, path_df, _project_terms(project_names, terms))
    ordered = _prioritised(records, common, report.stats, terms, cfg)
    cap = source_cap(report.files_scanned, cfg)
    report.candidates = _select(ordered, cap)
    cut = len(ordered) - len(report.candidates)
    if cut:
        report.notes.append(_cut_note(ordered, report.candidates, cut, cap, report.files_scanned,
                                      cfg))
    return report


def _project_terms(names: Iterable[str], terms: list[str]) -> frozenset[str]:
    """Return the query terms that are words of the project's own names (the workspace id)."""
    joined = " ".join(names).lower()
    return frozenset(t for t in terms if len(t) >= MIN_PROJECT_TERM and t in joined)


def _cut_note(ordered: _Prioritised, offered: list[Candidate], cut: int, cap: int, scanned: int,
              cfg: RetrievalConfig) -> str:
    """Describe what the source cap cut: sections, files with no section offered and the best cut."""
    kept = {c.locator for c in offered}
    left_out = [c for _, c in ordered if c.locator not in kept]
    whole = {c.path for _, c in ordered} - {c.path for c in offered}
    strongest = max(left_out, key=lambda c: c.score, default=None)
    best = (f"; strongest cut section scored {strongest.score:.1f} ({strongest.hits} hit(s), "
            f"{strongest.locator})") if strongest else ""
    return (f"{cut} lower-ranked section(s) cut at the source cap of {cap} candidates "
            f"({scanned} files scanned, max_candidates={cfg.max_candidates}); "
            f"{len(whole)} matching file(s) had no section offered and "
            f"{len({c.path for c in left_out} - whole)} more lost sections to a sibling{best}")


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: The checkout's folder name no longer counts as a project name;
#   only the caller's (the workspace id) do. In a worktree folder `kernel-v01`, `kernel` stopped
#   being a distinctive path word, so every `kernel/` section lost 3 x idf(kernel) (about 15
#   points) there and the same commit ranked differently in CI (`leafcutter-ai/`).
#   (#KernelV01/CI)
# - 2026-10-01 [python-coder]: Candidates are ordered by a BM25-style score over the scanned
#   sections (document frequency from the whole source, section length normalised, path words as
#   extra occurrences) instead of raw hit counts: registry JSON with 191 to 263 hits filled the
#   rerank batch while short documents with 10 to 30 hits that answer the question sat unjudged.
#   A registry (one JSON object holding one collection) is split by entry and pinned when the
#   goal speaks its vocabulary; a document that reviews a run of the asking goal is flagged.
#   (#KernelV01/F)
# - 2026-10-01 [python-coder]: Ranking is one weighted number (file content hits plus
#   retrieval.path_match_weight per distinctive path word) after pinning; terms in the path of
#   most files and the project's own names (workspace id, folder) are not distinctive. A live
#   regression run offered `leafcutter.*.schema.json` sections with 1 to 4 hits before files with
#   20 to 36 hits. The cut note now counts the files that lost a section to a sibling.
#   (#KernelV01/E)
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
