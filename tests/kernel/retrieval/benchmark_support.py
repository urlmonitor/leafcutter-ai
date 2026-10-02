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
    runs it and matches the must-have places against the first batch. In a git checkout only the
    files git does not ignore are read, so a local build's outputs never enter the corpus.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from kernel.capabilities.retrieval.access import ReadOutcome, ReadPolicy
from kernel.capabilities.retrieval.candidates import Candidate, SearchReport
from kernel.capabilities.retrieval.entities import extract_entities
from kernel.capabilities.retrieval.locators import fetch_explicit
from kernel.capabilities.retrieval.pool import merge_pool
from kernel.capabilities.retrieval.repository import search_repo_text
from kernel.capabilities.retrieval.terms import build_query_terms
from kernel.capabilities.retrieval.rerank import rerank
from kernel.config import KernelConfig, SourceConfig, load_kernel_config
from kernel.contracts import schema_ids
from kernel.contracts.enums import EvidenceCategory
from kernel.contracts.evidence import EvidenceNeed
from kernel.providers.fakes import ScriptedJev, noul_answer
from tests.kernel.capabilities.support import invocation
from tests.kernel.helpers import as_json, make_context

REPO_ROOT = Path(__file__).resolve().parents[3]
#: Record its `current` values from CI's checkout path or with this harness, never a dev folder.
CASES_FILE = Path(__file__).with_name("benchmark_cases.json")
PROJECT_NAME = "leafcutter"
#: Skip reason of a file in the checkout that git ignores (a build output, a local file).
GIT_IGNORED = "git_ignored"


_TEXTS: dict[tuple[Path, tuple[str, ...], int], ReadOutcome] = {}
_RELATIVE: dict[tuple[Path, Path], str | None] = {}


def is_git_checkout(root: Path) -> bool:
    """True if the root is the top of a git work tree (`.git` is a folder, or a file in a worktree)."""
    return (root / ".git").exists()


def _fold(rel: str) -> str:
    """Case-fold a path on Windows, whose file system may spell a name unlike git's index."""
    return rel.casefold() if os.name == "nt" else rel


@cache
def git_visible_files(root: Path) -> frozenset[str]:
    """Return the paths in the checkout that git does not ignore: tracked, or new and not ignored.

    This is what CI scores once the work is committed. Ignored build outputs are not: build.py
    installs `scripts/commit_guardian/` and its siblings as symlinks on Linux (never walked) but
    as copies on Windows without symlink rights (walked: 152 more files in one source's corpus).
    Read once per process.

    Raises:
        subprocess.CalledProcessError: git refused to list the files (the benchmark must not fall
            back to scanning everything, which is what made it disagree with CI).
    """
    listed = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                            cwd=root, capture_output=True, check=True).stdout
    return frozenset(_fold(p) for p in listed.decode("utf-8").split("\0") if p)


@dataclass(frozen=True)
class _CheckoutPolicy(ReadPolicy):
    """A ReadPolicy over a git checkout: reads only what git does not ignore, and remembers reads.

    Every case scans the same several thousand files; the cache keeps the whole benchmark to a few
    seconds without changing what a read returns.
    """

    def relative(self, path: Path) -> str | None:
        """Return the cached relative path (the real path resolution is the slow part)."""
        key = (self.root, path)
        if key not in _RELATIVE:
            _RELATIVE[key] = super().relative(path)
        return _RELATIVE[key]

    def read_text(self, path: Path) -> ReadOutcome:
        """Return the cached read outcome of the file; a file git ignores is skipped as such."""
        key = (path, self.deny_globs, self.max_file_bytes)
        if key not in _TEXTS:
            rel = self.relative(path)
            ignored = rel is not None and _fold(rel) not in git_visible_files(self.root)
            _TEXTS[key] = ReadOutcome(None, GIT_IGNORED) if ignored else super().read_text(path)
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
    kind = _CheckoutPolicy if is_git_checkout(root) else ReadPolicy
    base = kind(root=root.resolve(), read_roots=(), deny_globs=tuple(cfg.retrieval.deny_globs),
                max_file_bytes=cfg.retrieval.max_file_bytes)
    entities = extract_entities(" ".join(case.get("hints") or [case["goal"]]))
    reports = []
    for source in _sources_for(cfg, case):
        policy = kind(base.root, base.read_roots, (*base.deny_globs, *source.deny_globs),
                      source.max_file_bytes or base.max_file_bytes)
        roots = list(policy.resolve_roots(source.roots).roots)
        reports.append(search_repo_text(policy, source.id, roots, terms, cfg.retrieval, entities,
                                        (PROJECT_NAME,), case["goal"]))
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


@dataclass(frozen=True)
class JudgedResult:
    """What the real rerank loop judged under the oracle, and what it cost."""

    locators: set[str]
    calls: int


def judged_with_oracle(case: dict[str, Any], result: BatchResult) -> JudgedResult:
    """Run the real rerank loop over the pool with a scripted oracle (no real Jev).

    The oracle rates a candidate 0.9 when it is one of the case's must-have places and 0.1
    otherwise, so the loop stops exactly when it has found enough of them or the pool gives up:
    this shows how many Jev calls the need would cost and which must-haves it would have judged.
    """
    wanted = [w for m in case["must_include"] for w in m["any_of"]]
    jev = ScriptedJev()

    def rate(question, batch):  # noqa: ANN001, ANN202 - ScriptedJev callback signature
        found = as_json(batch.state)["candidates"][question.id.split(".")[1]]["locator"]
        hit = any(w["path"] == found.split("#")[0] and w.get("label", "") in found for w in wanted)
        return noul_answer(0.9 if hit else 0.1)

    jev.script("retrieval.rerank", "relevant.*", rate)
    config = load_kernel_config()
    ctx = make_context(REPO_ROOT, jev=jev, config=config)
    need = EvidenceNeed(id="need.bench", category=EvidenceCategory(case["category"]),
                        question=case["goal"])
    inv = invocation("retrieve.repository", schema_ids.RETRIEVAL_REQUEST, {})
    asyncio.run(rerank(ctx, inv, need, result.pool, config.retrieval.top_k, goal=case["goal"]))
    sent = {as_json(c)["locator"] for b in jev.batches
            for c in as_json(b.state)["candidates"].values()}
    return JudgedResult(sent, jev.call_count)


def judged_names(case: dict[str, Any], judged: JudgedResult, result: BatchResult) -> list[str]:
    """Return the must-have places the loop judged (named places are kept, not judged)."""
    kept = [c for c in result.pool if c.explicit]
    return [m["name"] for m in case["must_include"]
            if any(matches(c, w) for c in kept for w in m["any_of"])
            or any(w["path"] == loc.split("#")[0] and w.get("label", "") in loc
                   for loc in judged.locators for w in m["any_of"])]


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: A git checkout is scored as git sees it: files git ignores are
#   skipped (`git_ignored`). On Windows the build's `scripts/` shims are copies, on Linux symlinks
#   that are never walked, so the same commit had 731 files in `repo.patterns` on one and 579 on
#   the other. The read cache is keyed by root as well. (#KernelV01/CI)
# - 2026-10-01 [python-coder]: judged_with_oracle runs the real rerank loop with a scripted oracle
#   (must-have places 0.9, the rest 0.1) so the benchmark also shows what a need judges and what
#   it costs in Jev calls, not only the first batch. (#KernelV01/F)
# - 2026-10-01 [python-coder]: Benchmark harness over the real checkout: the lexical stage only
#   (no Jev, no knowledge-map bridge), the same functions the retrieval executor calls.
#   (#KernelV01/F)
# ====================================================================
