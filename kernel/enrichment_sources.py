"""Bound the existing repository retriever for the initial context pass.

File enumeration never follows directory links and honours read roots and deny rules.
The existing section extraction and lexical ranking produce inspectable excerpts.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

from kernel.capabilities.retrieval.access import ReadOutcome, ReadPolicy
from kernel.capabilities.retrieval.candidates import SearchReport
from kernel.capabilities.retrieval.entities import extract_entities
from kernel.capabilities.retrieval.repository import search_repo_text
from kernel.config import KernelConfig, SourceConfig
from kernel.contracts import TaskInput

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TimedReadPolicy(ReadPolicy):
    """Stop subsequent reads at the enrichment deadline, including during ranking."""

    deadline: float

    def read_text(self, path: Path) -> ReadOutcome:
        """Refuse another read once the pass's time allowance has elapsed."""
        if time.monotonic() >= self.deadline:
            return ReadOutcome(None, "time_budget")
        return super().read_text(path)


def _file_order(name: str, terms: list[str]) -> tuple[int, str]:
    """Prefer paths named in the query before filling the bounded file allowance."""
    return -sum(t in name.lower() for t in terms), name


def _files(policy: TimedReadPolicy, roots: tuple[Path, ...], terms: list[str], limit: int,
           notes: list[str]) -> list[Path]:
    """Enumerate at most limit files, pruning forbidden subtrees before descent."""
    selected: dict[Path, None] = {}

    def add(path: Path) -> None:
        rel = policy.relative(path)
        if rel is not None and not policy.is_denied(rel):
            selected.setdefault(path.resolve(), None)

    def walk_error(error: OSError) -> None:
        logger.warning("context source could not be enumerated: %s", type(error).__name__)
        notes.append("source enumeration failed: " + type(error).__name__)

    for root in sorted(roots, key=lambda p: _file_order(p.as_posix(), terms)):
        if time.monotonic() >= policy.deadline:
            notes.append("context time budget reached")
            break
        if root.is_file():
            add(root)
        else:
            for directory, dirs, files in os.walk(root, onerror=walk_error, followlinks=False):
                if time.monotonic() >= policy.deadline or len(selected) >= limit:
                    break
                dirs[:] = sorted((name for name in dirs if
                    not (Path(directory) / name).is_symlink()
                    and (rel := policy.relative(Path(directory) / name)) is not None
                    and not policy.is_denied(rel)), key=lambda s: _file_order(s, terms))
                for name in sorted(files, key=lambda s: _file_order(s, terms)):
                    if len(selected) >= limit or time.monotonic() >= policy.deadline:
                        break
                    add(Path(directory) / name)
        if len(selected) >= limit:
            notes.append("context file budget reached")
            break
    if time.monotonic() >= policy.deadline and "context time budget reached" not in notes:
        notes.append("context time budget reached")
    return list(selected)


def search_source(task: TaskInput, config: KernelConfig, source: SourceConfig,
                  query: str, terms: list[str], allowance: int, deadline: float
                  ) -> tuple[SearchReport, int]:
    """Use the same read policy and repository ranking as research, with a file cap."""
    cfg = config.context_enrichment
    policy = TimedReadPolicy(
        root=Path(task.scope.repository_root), read_roots=tuple(task.scope.read_roots),
        deny_globs=tuple([*config.retrieval.deny_globs, *source.deny_globs]),
        max_file_bytes=min(config.retrieval.max_file_bytes,
                           source.max_file_bytes or config.retrieval.max_file_bytes),
        deadline=deadline)
    resolved = policy.resolve_roots(source.roots)
    notes = ["root not searched: " + reason for reason in resolved.rejected]
    if not resolved.roots:
        return SearchReport(source_id=source.id, unavailable_reason="no readable roots",
                            notes=notes), 0
    paths = _files(policy, resolved.roots, terms, allowance, notes)
    retrieval = config.retrieval.model_copy(update={
        "max_excerpt_chars": min(config.retrieval.max_excerpt_chars, cfg.max_excerpt_chars)})
    report = search_repo_text(policy, source.id, paths, terms, retrieval,
                              extract_entities(query), (task.scope.workspace_id,), task.goal)
    report.notes.extend(notes)
    return report, len(paths)
