"""
MODULE: tests.kernel.retrieval.benchmark_support
GOAL: Run the lexical stage of one retrieval need (source searches, explicit locators, pool) over
    the REAL repository checkout and report what the first Jev rerank batch would contain.
BUSINESS CONTEXT: Round E made research cheap, but a live regression showed the first rerank batch
    filled with registry JSON while the files that answer the question sat unjudged at pool
    positions 24 to 34. A benchmark of named goals and the places that must reach the first batch
    lets a later change trade neither quality for cost nor cost for quality unnoticed.
ARCHITECTURE: Deterministic and offline (no Jev, no knowledge-map bridge, no network): the same
    functions the retrieval executor calls (build_query_terms, extract_entities, search_repo_text,
    fetch_explicit, merge_pool) over the repository this file lives in, with the default config
    sources of the need's category. A case is data (benchmark_cases.json); this module only
    runs it and matches the must-have places against the first batch.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kernel.capabilities.retrieval.access import ReadOutcome, ReadPolicy
from kernel.capabilities.retrieval.candidates import Candidate, SearchReport
from kernel.capabilities.retrieval.entities import extract_entities
from kernel.capabilities.retrieval.locators import fetch_explicit
from kernel.capabilities.retrieval.pool import merge_pool
from kernel.capabilities.retrieval.repository import search_repo_text
from kernel.capabilities.retrieval.terms import build_query_terms
from kernel.config import KernelConfig, SourceConfig, load_kernel_config

REPO_ROOT = Path(__file__).resolve().parents[3]
CASES_FILE = Path(__file__).with_name("benchmark_cases.json")
PROJECT_NAME = "leafcutter"


_TEXTS: dict[tuple[Path, tuple[str, ...], int], ReadOutcome] = {}
_RELATIVE: dict[Path, str | None] = {}


@dataclass(frozen=True)
class _CachedPolicy(ReadPolicy):
    """A ReadPolicy that remembers reads for the life of the process.

    Every case scans the same several thousand files; the cache keeps the whole benchmark to a few
    seconds without changing what a read returns.
    """

    def relative(self, path: Path) -> str | None:
        """Return the cached relative path (the real path resolution is the slow part)."""
        if path not in _RELATIVE:
            _RELATIVE[path] = super().relative(path)
        return _RELATIVE[path]

    def read_text(self, path: Path) -> ReadOutcome:
        """Return the cached read outcome of the file under this policy's limits."""
        key = (path, self.deny_globs, self.max_file_bytes)
        if key not in _TEXTS:
            _TEXTS[key] = super().read_text(path)
        return _TEXTS[key]


@dataclass(frozen=True)
class BatchResult:
    """The pool a need would build and the first batch Jev would judge."""

    pool: list[Candidate]
    batch: list[Candidate]
    reports: list[SearchReport]


def load_cases() -> list[dict[str, Any]]:
    """Return the benchmark cases from the fixture file."""
    return json.loads(CASES_FILE.read_text(encoding="utf-8"))["cases"]


def _sources_for(cfg: KernelConfig, case: dict[str, Any]) -> list[SourceConfig]:
    """Return the repo_text sources serving the case's evidence category (or the named ones)."""
    named = set(case.get("sources", []))
    return [s for s in cfg.sources if s.kind == "repo_text" and (
        s.id in named if named else case["category"] in [c.value for c in s.categories])]


def _search(cfg: KernelConfig, case: dict[str, Any], terms: list[str], root: Path
            ) -> tuple[ReadPolicy, list[SearchReport]]:
    """Search every source of the case in the repository checkout."""
    kind = _CachedPolicy if root.resolve() == REPO_ROOT.resolve() else ReadPolicy
    base = kind(root=root.resolve(), read_roots=(), deny_globs=tuple(cfg.retrieval.deny_globs),
                max_file_bytes=cfg.retrieval.max_file_bytes)
    entities = extract_entities(" ".join(case.get("hints") or [case["goal"]]))
    reports = []
    for source in _sources_for(cfg, case):
        policy = kind(base.root, base.read_roots, (*base.deny_globs, *source.deny_globs),
                      base.max_file_bytes)
        roots = list(policy.resolve_roots(source.roots).roots)
        reports.append(search_repo_text(policy, source.id, roots, terms, cfg.retrieval, entities,
                                        (PROJECT_NAME,)))
    return base, reports


def run_case(case: dict[str, Any], cfg: KernelConfig | None = None, root: Path = REPO_ROOT
             ) -> BatchResult:
    """Build the pool of one case and cut the first rerank batch (explicit candidates are kept
    unjudged, so they are not part of the batch)."""
    config = cfg or load_kernel_config()
    hints = case.get("hints") or [case["goal"]]
    terms = build_query_terms(case.get("question", case["goal"]), hints, (),
                              config.retrieval.max_query_terms)
    policy, reports = _search(config, case, terms, root)
    explicit = fetch_explicit(policy, _sources_for(config, case), case.get("explicit_locators", []),
                              terms, config.retrieval).candidates
    pool = merge_pool(reports, config.retrieval, explicit)
    batch = [c for c in pool if not c.explicit][:config.retrieval.rerank_max_per_need]
    return BatchResult(pool, batch, reports)


def matches(candidate: Candidate, want: dict[str, str]) -> bool:
    """True if the candidate is the wanted file (and, when given, a section naming the label)."""
    return candidate.path == want["path"] and want.get("label", "") in candidate.locator


def reached(result: BatchResult, case: dict[str, Any]) -> dict[str, bool]:
    """Return, per must-have, whether any alternative of it is in the first batch (or kept
    unjudged as an explicit locator)."""
    kept = [c for c in result.pool if c.explicit] + result.batch
    return {m["name"]: any(matches(c, w) for c in kept for w in m["any_of"])
            for m in case["must_include"]}


def positions(result: BatchResult, case: dict[str, Any]) -> dict[str, int | None]:
    """Return the 1-based pool position of each must-have (None when it is not in the pool)."""
    out: dict[str, int | None] = {}
    for m in case["must_include"]:
        found = [i for i, c in enumerate(result.pool, start=1)
                 if any(matches(c, w) for w in m["any_of"])]
        out[m["name"]] = found[0] if found else None
    return out


def crowding(result: BatchResult, case: dict[str, Any]) -> dict[str, int]:
    """Return how many candidates of each must-not-dominate path pattern sit in the first batch."""
    return {f["pattern"]: sum(f["pattern"] in c.path for c in result.batch)
            for f in case.get("must_not_dominate", [])}


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Benchmark harness over the real checkout: the lexical stage only
#   (no Jev, no knowledge-map bridge), the same functions the retrieval executor calls.
#   (#KernelV01/F)
# ====================================================================
