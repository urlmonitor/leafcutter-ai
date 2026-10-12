"""
MODULE: kernel.memory.file_store
GOAL: `FileColonyMemory`: the file backend of the `ColonyMemory` port. It finds precedent through
    the generated index of `docs/decisions/`, reads a record by id, and stages a new record into
    the run root (never into the repository).
BUSINESS CONTEXT: Decisions are filed as reviewable YAML files now and may move to a graph later
    (ADR-059). The kernel stays read-only during a run (ADR-060): this backend reads
    `docs/decisions/` and writes only under `<run_root>/runs/<run_id>/staged/decisions/`; the
    explicit `decisions publish` command moves a staged record into the repository.
ARCHITECTURE: Reads go through `index.json` (filters and the text score pick candidates, then
    each candidate file is loaded and checked against the sha256 the index holds, so a stale
    index never serves a record the index does not describe). The text score is the overlap
    coefficient of the content words of the query and of the record's question and title. A
    missing or invalid index yields no precedent and a warning; `decisions validate` is what
    fails on it.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from pathlib import Path

from kernel.memory.codec import RecordReadError, load_record_file, read_text, write_record_file
from kernel.memory.index import INDEX_NAME, IndexEntry, file_sha256, read_index
from kernel.memory.models import DECISION_ID_PATTERN, DecisionRecord
from kernel.memory.port import DecisionHit, DecisionQuery, StagedRecord
from kernel.persistence.fsutil import UnsafePathComponent, safe_component

logger = logging.getLogger(__name__)

STAGED_SUBPATH = ("staged", "decisions")
_WORD = re.compile(r"[a-z][a-z0-9_]{2,}")
#: Words that carry no topic; short enough to read, long enough to matter for an English question.
_STOP = frozenset({
    "the", "and", "for", "with", "that", "this", "from", "into", "which", "should", "would",
    "could", "can", "how", "what", "when", "where", "who", "why", "are", "was", "were", "has",
    "have", "had", "not", "but", "all", "any", "its", "their", "our", "use", "using", "used",
    "decide", "decision", "decisions", "does", "did", "you", "your", "then", "than", "also"})
_FACETS = ("components", "roadmap_phase", "change_target", "risk_surface")


def tokens(text: str) -> frozenset[str]:
    """Return the content words of a text (lower case, stop words and short words removed)."""
    return frozenset(w for w in _WORD.findall(text.lower()) if w not in _STOP)


def text_score(query: str, record: str) -> float:
    """Return the overlap coefficient (0..1) of the content words of two texts."""
    a, b = tokens(query), tokens(record)
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def filters_match(entry: IndexEntry, query: DecisionQuery) -> bool:
    """True unless a facet the query names is set on a record that is not repository-wide
    and shares none of the query's values (a record without a facet is not filtered by it)."""
    if entry.repository_wide:
        return True
    for facet in _FACETS:
        wanted, have = getattr(query, facet), getattr(entry, facet)
        if wanted and have and not set(wanted) & set(have):
            return False
    return True


def staged_dir(run_root: Path, run_id: str) -> Path:
    """Return the folder staging a run's records (`run_id` must be a safe path segment)."""
    return run_root / "runs" / safe_component(run_id) / Path(*STAGED_SUBPATH)


def staged_files(run_root: Path, run_id: str) -> list[Path]:
    """Return the staged record files of a run, sorted (empty when nothing was staged)."""
    folder = staged_dir(run_root, run_id)
    try:
        return sorted(folder.glob("dec-*.yaml")) if folder.is_dir() else []
    except OSError:
        logger.warning("cannot list staged records in %s", folder, exc_info=True)
        return []


class FileColonyMemory:
    """ColonyMemory over `<repo_root>/<decisions_dir>/` (read) and the run root (stage)."""

    def __init__(self, repo_root: Path, run_root: Path, decisions_dir: str = "docs/decisions"
                 ) -> None:
        """Bind to a repository root, the run root and the store folder (relative to the root)."""
        self.repo_root = Path(repo_root)
        self.run_root = Path(run_root)
        self.folder = self.repo_root / decisions_dir

    def _candidates(self, query: DecisionQuery, entries: Iterable[IndexEntry]
                    ) -> list[tuple[float, IndexEntry]]:
        """Return (score, entry) pairs that pass the filters and the minimum text score."""
        scored = [(text_score(query.text, f"{e.question} {e.title} {e.decision_type}"), e)
                  for e in entries if filters_match(e, query)]
        kept = [(s, e) for s, e in scored if s > 0.0 and s >= query.min_score]
        return sorted(kept, key=lambda pair: (-pair[0], pair[1].id))

    def _load_checked(self, entry: IndexEntry) -> DecisionRecord | None:
        """Load an indexed record whose file still matches the index (else None, with a warning)."""
        path = self.folder / entry.file
        try:
            text = read_text(path)
            if file_sha256(text) != entry.sha256:
                logger.warning("decision record %s changed since the index was built; skipped",
                               entry.file)
                return None
            return load_record_file(path)
        except RecordReadError:
            logger.warning("decision record %s is unreadable; skipped", entry.file)
            return None

    def find_decisions(self, query: DecisionQuery) -> list[DecisionHit]:
        """Return up to `query.limit` records for the query, best text match first."""
        entries = read_index(self.folder / INDEX_NAME)
        if not entries:
            return []
        replaced = {e.id: tuple(e.superseded_by) for e in entries}
        hits: list[DecisionHit] = []
        for score, entry in self._candidates(query, entries):
            record = self._load_checked(entry)
            if record is not None:
                hits.append(DecisionHit(record=record, score=round(score, 4),
                                        path=f"{self.folder.relative_to(self.repo_root).as_posix()}"
                                             f"/{entry.file}", superseded_by=replaced[entry.id]))
            if len(hits) >= query.limit:
                break
        return hits

    def get_decision(self, decision_id: str) -> DecisionRecord | None:
        """Return the record with this id, or None when there is none (or it cannot be read)."""
        if not re.fullmatch(DECISION_ID_PATTERN, decision_id):
            return None
        path = self.folder / f"{decision_id}.yaml"
        try:
            return load_record_file(path) if path.is_file() else None
        except (RecordReadError, OSError):
            logger.warning("decision record %s is unreadable", path, exc_info=True)
            return None

    def stage_decision(self, record: DecisionRecord) -> StagedRecord | None:
        """Write the record under the run root's staged folder; None if it could not be kept."""
        try:
            path = staged_dir(self.run_root, record.provenance.run_id) / f"{record.id}.yaml"
        except UnsafePathComponent:
            logger.warning("record %s has an unsafe run id and was not staged", record.id)
            return None
        try:
            write_record_file(record, path)
        except OSError:
            return None  # write_record_file logged it; staging never fails a decision
        return StagedRecord(decision_id=record.id, path=path)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Candidates are chosen by the index (filters and a content-word
#   overlap coefficient) and a file is trusted only while its sha256 still matches the index; the
#   text score is deliberately simple because Jev, not this score, judges applicability.
#   (#KernelDecisionStore)
# - 2026-10-01 [python-coder]: A staging failure returns None instead of raising: filing a record
#   is a by-product of a decision and must never fail it. (#KernelDecisionStore)
# ====================================================================
