"""MODULE: kernel.entity_sources
GOAL: Share source policy between explicit entity preparation and read-only recognition.
BUSINESS CONTEXT: Cached names must obey the same permissions as source file reads.
ARCHITECTURE: Reuses retrieval.ReadPolicy for resolved paths, deny globs and read roots.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from kernel.capabilities.retrieval.access import ReadPolicy
from kernel.config import KernelConfig, SourceConfig


def selected_sources(config: KernelConfig, scope_ids: list[str] | None = None) -> list[SourceConfig]:
    """Intersect configured entity sources with the current scope source restriction."""
    wanted = config.entity_context.source_ids
    return [s for s in config.sources if s.kind == "repo_text"
            and (not wanted or s.id in wanted) and (not scope_ids or s.id in scope_ids)]


def policy_for(root: Path, config: KernelConfig, source: SourceConfig,
               read_roots: list[str] | None = None) -> ReadPolicy:
    """Use the exact ordinary retrieval policy, including source-specific restrictions."""
    return ReadPolicy(root=root, read_roots=tuple(read_roots or []),
                      deny_globs=tuple([*config.retrieval.deny_globs, *source.deny_globs]),
                      max_file_bytes=source.max_file_bytes or config.retrieval.max_file_bytes)


def inside_source(relative: str, source: SourceConfig) -> bool:
    """Check lexical configured ownership without reading a directory."""
    path = PurePosixPath(relative)
    for configured in source.roots:
        base = PurePosixPath(configured.replace("\\", "/"))
        if base.is_absolute() or ".." in base.parts or ":" in configured:
            continue
        if base == path or base in path.parents:
            return True
    return False


class SourcePermission:
    """Compile lexical ownership once while retaining the canonical resolved-path policy."""

    def __init__(self, source: SourceConfig, policy: ReadPolicy,
                 resolved_paths: dict[str, str | None] | None = None):
        """Prepare immutable source roots for this invocation's permission decisions."""
        self.policy = policy
        self.resolved = resolved_paths if resolved_paths is not None else {}
        self.roots = tuple(PurePosixPath(raw.replace("\\", "/")).as_posix() for raw in source.roots
                           if not PurePosixPath(raw.replace("\\", "/")).is_absolute()
                           and ".." not in PurePosixPath(raw.replace("\\", "/")).parts and ":" not in raw)

    def _inside(self, relative: str) -> bool:
        """Compare normalized path components without repeatedly allocating parent paths."""
        return not relative.startswith("/") and ".." not in relative.split("/") and any(
            base == "." or relative == base or relative.startswith(base + "/") for base in self.roots)

    def allowed(self, relative: str) -> bool:
        """Use the existing OS resolution and scope checks for every distinct physical path."""
        if not self._inside(relative) or self.policy.is_denied(relative):
            return False
        if relative not in self.resolved:
            self.resolved[relative] = self.policy.relative(self.policy.root / relative)
        resolved = self.resolved[relative]
        if resolved is None:
            return False
        return resolved == relative or (self._inside(resolved) and not self.policy.is_denied(resolved))


def permitted(relative: str, source: SourceConfig, policy: ReadPolicy) -> bool:
    """Require lexical and resolved paths to satisfy source, scope and deny rules."""
    if not inside_source(relative, source) or policy.is_denied(relative):
        return False
    resolved = policy.relative(policy.root / relative)
    return resolved is not None and inside_source(resolved, source) and not policy.is_denied(resolved)


def stamp(path: Path) -> list[int]:
    """Read conservative high-resolution filesystem freshness metadata."""
    value = path.stat()
    return [value.st_mtime_ns, value.st_ctime_ns, value.st_size, value.st_ino]

# DECISION HISTORY
# ================================================================================
# - 2026-10-03 15:05 [python-coder]: Keep pre-intent meanings deterministic, scoped and separate from task evidence. (#TICKETLESS reason=user-approved-ac-first-DK300)
# - 2026-10-03 17:00 [python-coder]: Reuse per-run path decisions while retaining canonical resolved-path permissions within the cold lookup deadline. (#DK-300/entity-context)
