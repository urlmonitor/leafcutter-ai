"""MODULE: kernel.entity_index_read
GOAL: Read and validate a prepared index without source discovery or body retrieval.
BUSINESS CONTEXT: A broad cache must not reveal denied names, counts or fingerprints.
ARCHITECTURE: Typed deserialization followed by per-run ReadPolicy and bounded stat checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
import time

from pydantic import ValidationError

from kernel.config import KernelConfig
from kernel.contracts.base import canonical_json, content_hash, fail
from kernel.contracts.task import Scope
from kernel.entity_records import EntityIndex, IndexEntry, READER_VERSION
from kernel.entity_owners import PACKAGE_REGISTRY
from kernel.entity_owner_scope import scoped_native_entries
from kernel.entity_sources import SourcePermission, policy_for, selected_sources, stamp

logger = logging.getLogger(__name__)
MAX_INDEX_BYTES = 32_000_000


@dataclass
class IndexView:
    """Only permitted metadata, independent of the broad cache's hidden contents."""

    status: str = "unavailable"
    entries: list[IndexEntry] = field(default_factory=list)
    fingerprint: str | None = None
    coverage: dict[str, str] = field(default_factory=dict)
    patterns: dict[str, str] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)


class PermissionFilter:
    """Cache per-file policy decisions without repeating path resolution per symbol."""

    def __init__(self, root: Path, scope: Scope, config: KernelConfig, deadline: float):
        """Bind the current read policy and deadline, not the builder's prior privileges."""
        self.sources = {s.id: s for s in selected_sources(config, scope.source_ids)}
        self.policies = {key: policy_for(root, config, source, scope.read_roots)
                         for key, source in self.sources.items()}
        resolved_paths: dict[str, str | None] = {}
        self.checks = {key: SourcePermission(source, self.policies[key], resolved_paths)
                       for key, source in self.sources.items()}
        self.deadline = deadline
        self.cache: dict[tuple[str, str], bool] = {}

    def allowed(self, source_id: str, path: str) -> bool:
        """Filter before constructing names, counters or any content-derived fingerprint."""
        key = (source_id, path)
        if key not in self.cache:
            if time.monotonic() >= self.deadline:
                raise TimeoutError
            self.cache[key] = source_id in self.checks and self.checks[source_id].allowed(path)
        return self.cache[key]


def _load(root: Path, config: KernelConfig) -> EntityIndex:
    """Read only the configured derived cache under an explicit size bound."""
    path = root / config.entity_context.index_path
    with path.open("rb") as stream:
        raw = stream.read(MAX_INDEX_BYTES + 1)
    if len(raw) > MAX_INDEX_BYTES:
        fail("entity index exceeds supported size")
    return EntityIndex.model_validate_json(raw)


def read_index(scope: Scope, config: KernelConfig, deadline: float) -> IndexView:
    """Return a permission-filtered current index, otherwise an honest unavailable result."""
    root = Path(scope.repository_root)
    try:
        index = _load(root, config)
    except FileNotFoundError:
        logger.warning("entity index missing")
        return IndexView(status="missing", limitations=["entity index missing; prepare it explicitly"])
    except (OSError, ValueError, ValidationError) as exc:
        logger.warning("entity index unavailable: %s", type(exc).__name__)
        return IndexView(status="invalid", limitations=["entity index invalid or unreadable"])
    if index.repository_root != str(root.resolve()) or index.reader_version != READER_VERSION:
        return IndexView(status="invalid", limitations=["entity index binding or reader version mismatch"])
    policy = PermissionFilter(root, scope, config, deadline)
    for key, source in policy.sources.items():
        if index.source_configuration.get(key) != source.roots:
            return IndexView(status="stale", limitations=["entity source configuration changed"])
    try:
        stamps = [s for s in index.manifest if policy.allowed(s.source_id, s.path)]
        failure = _freshness(root, index, stamps, deadline)
        if failure is not None:
            return failure
        entries = [entry for entry in index.entries if policy.allowed(entry.source_id, entry.path)]
    except TimeoutError:
        logger.warning("entity policy deadline exhausted")
        return IndexView(status="unavailable", limitations=["entity permission validation deadline exhausted"])
    except OSError as exc:
        logger.warning("entity freshness unavailable: %s", type(exc).__name__)
        return IndexView(status="stale", limitations=["entity source snapshot changed or unavailable"])
    return _result(index, entries, stamps)


def _result(index: EntityIndex, entries: list[IndexEntry], stamps: list) -> IndexView:
    """Compute disclosed fingerprints and family coverage from permitted content only."""
    permitted_paths = {item.path for item in stamps}
    entries, native_coverage = scoped_native_entries(entries, index.owner_scopes, permitted_paths)
    hashes = sorted({(s.path, s.content_hash) for s in stamps if not s.directory and s.exists} |
                    {(e.locator, e.source_hash) for e in entries if e.package_source})
    fingerprint = content_hash(canonical_json(hashes)) if hashes else None
    # Only selected families appear in coverage; excluded entities contribute no counters.
    families: set[str] = {entry.family for entry in entries}
    coverage: dict[str, str] = {family: index.coverage.get(family, "unavailable") for family in families
                if family not in {"artifact_id", "glossary"}}
    coverage.update(native_coverage)
    families.update(native_coverage)
    symbol_failed = bool(permitted_paths.intersection(index.symbol_failures))
    if "symbol" in families or symbol_failed:
        coverage["symbol"] = "partial" if symbol_failed else "current"
        families.add("symbol")
    return IndexView(status="current", entries=entries, fingerprint=fingerprint,
                     coverage=coverage, patterns=index.id_patterns,
                     limitations=[f"{family}: incomplete reader coverage" for family in sorted(families)
                                  if coverage[family] != "current"])


def _freshness(root: Path, index: EntityIndex, stamps: list, deadline: float) -> IndexView | None:
    """Validate enumerated filesystem stamps without discovering or reading any source."""
    if stamp(PACKAGE_REGISTRY) != index.package_stamp:
        return IndexView(status="stale", limitations=["trusted entity reader metadata changed"])
    for item in stamps:
        if time.monotonic() >= deadline:
            return IndexView(status="unavailable", limitations=["entity validation deadline exhausted"])
        try:
            current = stamp(root / item.path)
        except FileNotFoundError:
            current = []
        if current != item.stamp:
            return IndexView(status="stale", limitations=["entity source snapshot stale; refresh explicitly"])
    return None

# DECISION HISTORY
# ================================================================================
# - 2026-10-03 15:05 [python-coder]: Keep pre-intent meanings deterministic, scoped and separate from task evidence. (#TICKETLESS reason=user-approved-ac-first-DK300)
# - 2026-10-03 17:00 [python-coder]: Derive symbol coverage from permitted parse failures and validate missing configured roots without source discovery. (#DK-300/entity-context)
# - 2026-10-03 17:00 [python-coder]: Disclose native reader coverage only after whole-store dependency permission filtering. (#DK-300/entity-context)
