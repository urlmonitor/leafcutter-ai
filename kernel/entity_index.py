"""MODULE: kernel.entity_index
GOAL: Explicitly prepare a disposable local index of compact repository meanings.
BUSINESS CONTEXT: Initial recognition must never crawl or rebuild repository knowledge.
ARCHITECTURE: Trusted native readers and AST produce metadata; a stat manifest detects
    ordinary edits/additions/deletions without rereading source bodies during intake.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
import tempfile

from kernel.config import KernelConfig
from kernel.contracts.base import canonical_json, content_hash, fail
from kernel.contracts.entity_context import FAMILIES
from kernel.entity_owners import PACKAGE_REGISTRY, native_projections, symbol_projections, vocabulary_projections
from kernel.entity_owner_scope import prepare_owner_scopes
from kernel.entity_records import EntityIndex, IndexEntry, SourceStamp
from kernel.entity_sources import permitted, policy_for, selected_sources, stamp

logger = logging.getLogger(__name__)
_IGNORED = {".git", ".leafcutter", "__pycache__", ".venv", "node_modules"}


def _ignored(path: Path, output: Path, run_root: Path) -> bool:
    """Exclude derived runtime/cache directories from the canonical input snapshot."""
    return (bool(_IGNORED.intersection(path.parts)) or path == output or
            path == run_root or run_root in path.parents)


def _inventory(root: Path, config: KernelConfig, output: Path
                ) -> tuple[list[SourceStamp], dict[str, tuple[str, str]]]:
    """Enumerate source files once, exclusively during an explicit maintenance build."""
    manifest: dict[tuple[str, str], SourceStamp] = {}
    files: dict[str, tuple[str, str]] = {}
    run_root = (root / config.paths.run_root).resolve()
    for source in selected_sources(config):
        policy = policy_for(root, config, source)
        for raw in source.roots:
            relative = raw.replace("\\", "/")
            candidate = root / relative
            if (permitted(relative, source, policy) and not candidate.exists()
                    and not _ignored(candidate, output, run_root)):
                manifest[(source.id, relative)] = SourceStamp(path=relative, source_id=source.id,
                    directory=False, exists=False, stamp=[])
        for base in policy.resolve_roots(source.roots).roots:
            try:
                paths = [base, *sorted(base.rglob("*"))] if base.is_dir() else [base]
                for path in paths:
                    if _ignored(path, output, run_root):
                        continue
                    relative = path.relative_to(root).as_posix()
                    if not permitted(relative, source, policy):
                        continue
                    directory = path.is_dir()
                    digest = ""
                    if not directory:
                        if path.stat().st_size > policy.max_file_bytes:
                            continue
                        data = path.read_bytes()
                        digest = hashlib.sha256(data).hexdigest()
                        files.setdefault(relative, (source.id, digest))
                    manifest[(source.id, relative)] = SourceStamp(path=relative,
                        source_id=source.id, directory=directory, stamp=stamp(path), content_hash=digest)
            except OSError as exc:
                logger.warning("entity inventory unavailable: %s", type(exc).__name__)
                raise
    return list(manifest.values()), files


def _symbols(root: Path, files: dict[str, tuple[str, str]], limit: int
             ) -> tuple[list[dict], list[str]]:
    """Parse supported declarations and explicitly mark incomplete language coverage."""
    result, failures = [], []
    for relative in sorted(files):
        if not relative.endswith(".py"):
            continue
        try:
            text = (root / relative).read_text(encoding="utf-8-sig")
            result.extend(symbol_projections(relative, text, limit))
        except (OSError, UnicodeError, SyntaxError, ValueError) as exc:
            logger.warning("entity Python declarations unavailable: %s", type(exc).__name__)
            failures.append(relative)
    return result, failures


def _entries(projections: list[dict], files: dict[str, tuple[str, str]]) -> list[IndexEntry]:
    """Retain only owner metadata whose physical source passed the source read policy."""
    entries = {}
    for row in projections:
        source = files.get(row["path"])
        if source is None:
            continue
        values = {"source_id": source[0], "source_hash": source[1], **row}
        entry = IndexEntry(**values)
        entries[(entry.family, entry.native_kind or "", entry.identity)] = entry
    return [entries[key] for key in sorted(entries)]


def build_entity_index(repository_root: Path | str, config: KernelConfig, *,
                       output_path: Path | str | None = None) -> EntityIndex:
    """Build and atomically save metadata without modifying any canonical source.

    Freshness is conservative metadata validation, not tamper-proof filesystem attestation.
    Hashes capture actual dirty bytes; a second ordinary edit invalidates the prior stamp.
    """
    root = Path(repository_root).resolve()
    output = Path(output_path) if output_path is not None else Path(config.entity_context.index_path)
    output = (root / output).resolve() if not output.is_absolute() else output.resolve()
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        logger.exception("cannot prepare entity index directory")
        raise
    limit = config.entity_context.max_meaning_chars
    manifest, files = _inventory(root, config, output)
    native, native_coverage, vocabulary, vocab_coverage, patterns, owner_scopes = _owners(root, files, limit)
    symbols, symbol_failures = _symbols(root, files, limit)
    entries = _entries([*native, *vocabulary, *symbols], files)
    coverage = {family: "current" for family in FAMILIES}
    coverage.update(native_coverage)
    coverage.update(vocab_coverage)
    coverage["symbol"] = "partial" if symbol_failures else "current"
    fingerprint = content_hash(canonical_json(sorted((p, h) for p, (_, h) in files.items())))
    index = EntityIndex(repository_root=str(root), fingerprint=fingerprint,
        source_configuration={s.id: s.roots for s in selected_sources(config)}, entries=entries,
        manifest=[item.model_copy(update={"stamp": stamp(root / item.path)}) if item.exists else item
                  for item in manifest],
        coverage=coverage, id_patterns=patterns, package_stamp=stamp(PACKAGE_REGISTRY),
        symbol_failures=symbol_failures,
        owner_scopes=owner_scopes,
        limitations=[f"{family}: incomplete reader coverage" for family, status in coverage.items()
                     if status != "current"])
    temporary = output.with_name(output.name + ".tmp")
    try:
        temporary.write_text(canonical_json(index.model_dump(mode="json")), encoding="utf-8")
        os.replace(temporary, output)
    except OSError:
        logger.exception("cannot save entity index")
        raise
    return index


def _owners(root: Path, files: dict[str, tuple[str, str]], limit: int) -> tuple:
    """Run canonical readers over a temporary data-only snapshot of permitted files.

    Native readers own whole-store validation and have no per-record filter seam.
    The isolated snapshot prevents those readers from opening excluded source bodies.
    """
    try:
        with tempfile.TemporaryDirectory(prefix="leafcutter-entity-owners-") as directory:
            snapshot = Path(directory)
            for relative, (_, digest) in files.items():
                data = (root / relative).read_bytes()
                if hashlib.sha256(data).hexdigest() != digest:
                    fail("canonical source changed during entity preparation")
                target = snapshot / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            native, coverage, statuses, dependencies = native_projections(snapshot, limit)
            vocabulary, vocab_coverage, patterns = vocabulary_projections(snapshot, limit)
            scopes = prepare_owner_scopes(snapshot, files, statuses, dependencies)
            return native, coverage, vocabulary, vocab_coverage, patterns, scopes
    except OSError:
        logger.exception("cannot prepare permitted native-reader snapshot")
        raise

# DECISION HISTORY
# ================================================================================
# - 2026-10-03 15:05 [python-coder]: Keep pre-intent meanings deterministic, scoped and separate from task evidence. (#TICKETLESS reason=user-approved-ac-first-DK300)
# - 2026-10-03 17:00 [python-coder]: Preserve absent-root freshness and complete permitted native dependencies, including configured owner locations. (#DK-300/entity-context)
