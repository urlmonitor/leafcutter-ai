"""
MODULE: kernel.capabilities.retrieval.repository
GOAL: The `repo_text` strategy: walk authorised roots, rank files by query-term hits and cut
    bounded excerpts with line locators.
BUSINESS CONTEXT: The one real native source of the MVP reads the project's own documents and
    code (ADRs, conventions, patterns) so a decision rests on inspectable evidence rather than an
    LLM-written answer (Rev 3 section 10.3).
ARCHITECTURE: Synchronous and side-effect free apart from reads through ReadPolicy (which wraps
    every read in try/except OSError); the executor runs it in a worker thread. Ranking is
    deterministic: hits descending, then path ascending.
"""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from pathlib import Path

from kernel.capabilities.retrieval.access import ReadPolicy
from kernel.capabilities.retrieval.candidates import Candidate, SearchReport
from kernel.config import RetrievalConfig
from kernel.contracts.enums import SourceKind

STRATEGY = "repo_text"
_SENTENCE_END = re.compile(r"[.!?](?=\s)")


def _iter_files(root: Path) -> list[Path]:
    """Return every file under root (or root itself if it is a file), sorted by path."""
    if root.is_file():
        return [root]
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        found += [Path(dirpath) / name for name in sorted(filenames)]
    return found


def _best_window(lines: list[str], terms: list[str], context: int) -> tuple[int, int, int]:
    """Return (start, end, hits): the line window with the most hits (end exclusive)."""
    lowered = [line.lower() for line in lines]
    hit_lines = [i for i, line in enumerate(lowered) if any(t in line for t in terms)]
    if not hit_lines:
        return 0, 0, 0
    best = max(hit_lines, key=lambda i: sum(
        lowered[j].count(t) for j in range(max(0, i - context), min(len(lines), i + context + 1))
        for t in terms))
    start, end = max(0, best - context), min(len(lines), best + context + 1)
    hits = sum(lowered[j].count(t) for j in range(len(lines)) for t in terms)
    return start, end, hits


def cut_at_boundary(text: str, cap: int) -> str:
    """Return text cut to at most `cap` chars, at a line end, else a sentence end, else a word.

    The cut never goes below half the cap (a tiny excerpt would say nothing); the caller still
    marks the result as truncated.
    """
    if len(text) <= cap:
        return text
    window, floor = text[:cap], cap // 2
    line = window.rfind("\n")
    if line >= floor:
        return window[:line]
    sentence = max((m.end() for m in _SENTENCE_END.finditer(window)), default=0)
    if sentence >= floor:
        return window[:sentence]
    word = window.rfind(" ")
    return window[:word] if word >= floor else window


def _candidate(rel: str, source_id: str, lines: list[str], terms: list[str],
               cfg: RetrievalConfig, modified: datetime | None) -> Candidate | None:
    """Build a Candidate for one file, or None if no term occurs in it."""
    start, end, hits = _best_window(lines, terms, cfg.excerpt_context_lines)
    if hits == 0:
        return None
    excerpt = "\n".join(lines[start:end])
    truncated = len(excerpt) > cfg.max_excerpt_chars
    body = cut_at_boundary(excerpt, cfg.max_excerpt_chars)
    full = "\n".join(lines).lower()
    matched = tuple(t for t in terms if t in full)
    return Candidate(
        source_id=source_id, kind=SourceKind.REPOSITORY_FILE, strategy=STRATEGY, path=rel,
        title=rel, locator=f"{rel}#L{start + 1}-L{end}", excerpt=body, hits=hits, terms=matched,
        truncated=truncated, modified_at=modified)


def _mtime(path: Path) -> datetime | None:
    """Return the file's modification time (UTC) or None if it cannot be read."""
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    except OSError:
        return None


def search_repo_text(policy: ReadPolicy, source_id: str, roots: list[Path], terms: list[str],
                     cfg: RetrievalConfig) -> SearchReport:
    """Search the given resolved roots for the terms.

    Args:
        policy: Read policy (containment, deny globs, size limit).
        source_id: Catalog id of the source being searched.
        roots: Resolved, authorised roots (files or directories).
        terms: Query terms (lowercase).
        cfg: Retrieval bounds.

    Returns:
        SearchReport: Ranked candidates (at most `max_candidates`) and skip counters.
    """
    report = SearchReport(source_id=source_id)
    found: list[Candidate] = []
    for root in roots:
        for path in _iter_files(root):
            outcome = policy.read_text(path)
            if outcome.text is None:
                report.skip(outcome.reason or "unreadable")
                continue
            report.files_scanned += 1
            rel = policy.relative(path) or path.name
            cand = _candidate(rel, source_id, outcome.text.splitlines(), terms, cfg, _mtime(path))
            if cand is not None:
                found.append(cand)
    found.sort(key=lambda c: (-c.hits, c.path))
    if len(found) > cfg.max_candidates:
        report.notes.append(f"{len(found) - cfg.max_candidates} lower-ranked files cut at "
                            f"max_candidates={cfg.max_candidates}")
    report.candidates = found[:cfg.max_candidates]
    return report


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-02 [python-coder]: Excerpts are cut at a line or sentence end within the cap (still
#   marked truncated) instead of mid-sentence. (#KernelBootstrapV0/GROUND)
# - 2026-09-30 23:00 [python-coder]: One excerpt per file (the densest window) keeps the
#   candidate list small enough for one Jev relevance batch. (#KernelBootstrapV0/P5)
# ====================================================================
