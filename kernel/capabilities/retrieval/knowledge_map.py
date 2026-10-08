"""
MODULE: kernel.capabilities.retrieval.knowledge_map
GOAL: The `knowledge_map` strategy: bridge to the existing scripts/knowledge_query.py so the
    retrieval adapter reuses the repository's own knowledge-map facility (ADRs, components,
    skills, agents) instead of re-implementing it.
BUSINESS CONTEXT: The knowledge map already indexes the project's decision and component
    surfaces (design part 4). Reusing it keeps one source of truth; a load failure must mark the
    source unavailable and never masquerade as "no results" (Rev 3 section 10.3).
ARCHITECTURE: The module is loaded with importlib.util.spec_from_file_location and cached per
    process; maps are cached per (root, surface) because a full build costs seconds. Node paths
    pass through the same ReadPolicy containment and deny checks as file reads.
"""

from __future__ import annotations

import hashlib
import importlib.util
import logging
import sys
import threading
from pathlib import Path
from types import ModuleType
from typing import Protocol

from kernel.capabilities.retrieval.access import ReadPolicy
from kernel.capabilities.retrieval.candidates import Candidate, SearchReport
from kernel.capabilities.retrieval.repository import source_cap
from kernel.config import RetrievalConfig, SourceConfig, repo_root
from kernel.contracts.enums import SourceKind

logger = logging.getLogger(__name__)

STRATEGY = "knowledge_map"
SCRIPT = Path("scripts") / "knowledge_query.py"
PATHS_JSON = Path("config") / "paths.json"
_LOAD_ERRORS = (ImportError, OSError, SyntaxError, AttributeError, SystemExit, ValueError,
                KeyError, TypeError)
_MODULES: dict[str, ModuleType] = {}
_NODES: dict[tuple[str, str], list[MapNode]] = {}
_LOAD_LOCK = threading.RLock()


STAGE_NO_SPEC = "script cannot be loaded"
STAGE_LOAD = "script failed to load"
STAGE_BUILD = "build failed"


class MapNode(Protocol):
    """The part of a knowledge-map node the bridge reads (the script returns richer objects)."""

    id: str
    title: str
    description: str
    path: Path
    missing: bool


class KnowledgeMapUnavailable(Exception):
    """The knowledge map could not be loaded or built."""

    def __init__(self, stage: str, detail: str = "") -> None:
        """Build the reason from the failing stage and an optional detail."""
        self.reason = f"knowledge map {stage}" + (f": {detail}" if detail else "")
        super().__init__(self.reason)


def trusted_root() -> Path:
    """Return the kernel's own installation root: the only place the bridge script may come from.

    The scope repository is data. Executing a script from it would run whatever Python a scoped
    (possibly untrusted) repository ships (Rev 3 section 13.3).
    """
    return repo_root()


def clear_caches() -> None:
    """Drop the per-process module and map caches (tests)."""
    with _LOAD_LOCK:
        _MODULES.clear()
        _NODES.clear()


def _load_module() -> ModuleType:
    """Load the trusted scripts/knowledge_query.py (cached); raise KnowledgeMapUnavailable.

    Loading is serialised: the script registers its sibling modules in `sys.modules` before they
    finish executing, so a second worker thread must never start a load while one is running.
    """
    key = str(trusted_root())
    with _LOAD_LOCK:
        if key in _MODULES:
            return _MODULES[key]
        module = _exec_script(key)
        _MODULES[key] = module
        return module


def _exec_script(key: str) -> ModuleType:
    """Execute the trusted script as a uniquely named module (caller holds the load lock)."""
    script = trusted_root() / SCRIPT
    if not script.is_file():
        raise KnowledgeMapUnavailable(STAGE_LOAD, f"trusted script not found ({SCRIPT.as_posix()})")
    name = "leafcutter_kernel_kq_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]
    spec = importlib.util.spec_from_file_location(name, script)
    if spec is None or spec.loader is None:
        raise KnowledgeMapUnavailable(STAGE_NO_SPEC, SCRIPT.as_posix())
    try:
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    except _LOAD_ERRORS as exc:
        sys.modules.pop(name, None)
        logger.warning("knowledge map script failed to load: %s", exc)
        raise KnowledgeMapUnavailable(STAGE_LOAD, repr(exc)) from exc
    return module


def _surface_nodes(root: Path, surface: str) -> list[MapNode]:
    """Return the nodes of one surface (cached); raise KnowledgeMapUnavailable on failure."""
    key = (str(root), surface)
    if key not in _NODES:
        module = _load_module()
        try:  # the scope root is passed as data only
            built = module.build_knowledge_map(root, root / PATHS_JSON, surface_filter=surface)
        except _LOAD_ERRORS as exc:
            logger.warning("knowledge map build failed for %s: %s", surface, exc)
            raise KnowledgeMapUnavailable(STAGE_BUILD, repr(exc)) from exc
        _NODES[key] = list(built.nodes)
    return _NODES[key]


def _node_candidate(policy: ReadPolicy, source: SourceConfig, node: MapNode, terms: list[str],
                    report: SearchReport) -> Candidate | None:
    """Build a Candidate for a node whose title or description contains a term."""
    excerpt = f"{node.title}: {node.description}".strip()
    hits = sum(excerpt.lower().count(t) for t in terms)
    if hits == 0 or getattr(node, "missing", False):
        return None
    raw = Path(node.path)
    rel = policy.relative(raw if raw.is_absolute() else policy.root / raw)
    if rel is None:
        report.skip("outside_root")
        return None
    if policy.is_denied(rel):
        report.skip("denied")
        return None
    return Candidate(
        source_id=source.id, kind=SourceKind.KNOWLEDGE_NODE, strategy=STRATEGY, path=rel,
        title=node.title, locator=f"{rel}#node={node.id}", excerpt=excerpt, hits=hits,
        terms=tuple(t for t in terms if t in excerpt.lower()))


def search_knowledge_map(policy: ReadPolicy, source: SourceConfig, terms: list[str],
                         cfg: RetrievalConfig) -> SearchReport:
    """Search the source's knowledge-map surfaces for the terms.

    Args:
        policy: Read policy (containment and deny globs apply to node paths).
        source: The catalog entry (its `surfaces` select the map surfaces).
        terms: Query terms (lowercase).
        cfg: Retrieval bounds.

    Returns:
        SearchReport: Ranked candidates, or `unavailable_reason` if the map could not be built.
    """
    report = SearchReport(source_id=source.id)
    try:
        nodes = [n for surface in source.surfaces for n in _surface_nodes(policy.root, surface)]
    except KnowledgeMapUnavailable as exc:
        report.unavailable_reason = exc.reason
        return report
    report.files_scanned = len(nodes)
    found = [c for c in (_node_candidate(policy, source, n, terms, report) for n in nodes)
             if c is not None]
    found.sort(key=lambda c: (-c.hits, c.locator))
    cap = source_cap(len(nodes), cfg)
    if len(found) > cap:
        report.notes.append(f"{len(found) - cap} nodes cut at the source cap of {cap} "
                            f"(max_candidates={cfg.max_candidates})")
    report.candidates = found[:cap]
    return report


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Node candidates use the same size-scaled source cap as file
#   sources. (#KernelV01/B)
# - 2026-10-02 [python-coder]: the bridge nodes are typed by a Protocol instead of object (#KernelBootstrapV0/GROUND)
# - 2026-10-02 [python-coder]: SECURITY: the bridge script is loaded only from the kernel's own
#   installation (`trusted_root`), never from the scope repository, which is passed to it as data.
#   A scoped untrusted repository could otherwise run its Python in the kernel process (Rev 3
#   section 13.3). A missing trusted script makes the source unavailable with a reason.
#   (#KernelBootstrapV0/GROUND)
# - 2026-10-01 00:30 [python-coder]: Module loading holds an RLock because the shipped script's
#   _load_sibling_module publishes half-loaded modules in sys.modules; parallel retrieval workers
#   otherwise saw them (scripts/ is a package file and is not edited here). (#KernelBootstrapV0/OBS)
# - 2026-09-30 23:00 [python-coder]: SystemExit is caught explicitly because
#   build_knowledge_map exits the process when paths.json is missing; that must become an
#   unavailable source, never end the run. (#KernelBootstrapV0/P5)
# ====================================================================
