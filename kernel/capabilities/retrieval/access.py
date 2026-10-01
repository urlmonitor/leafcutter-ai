"""
MODULE: kernel.capabilities.retrieval.access
GOAL: The read-access policy of the repository retrieval adapter: authorised read roots,
    path-traversal protection, deny globs, size limits and a safe file read.
BUSINESS CONTEXT: Retrieval is read-only and must never leave the repository or surface secrets:
    a source root may not escape the repository root, a scope may narrow the roots further, and
    files matching deny globs (keys, env files, .git) are invisible (Rev 3 sections 10.3 and
    13.3).
ARCHITECTURE: ReadPolicy is an immutable value built from the scope and RetrievalConfig. Every
    path is resolved (symlinks included) and checked for containment before it is read; the read
    itself sits inside try/except OSError and a failed read is reported, never treated as empty.
"""

from __future__ import annotations

import fnmatch
import logging
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

logger = logging.getLogger(__name__)

BINARY_SNIFF_BYTES = 2048


def _fold(posix: str) -> str:
    """Normalise a relative POSIX path for comparison: no leading ./ or trailing /, case-folded
    on case-insensitive platforms (Windows)."""
    cleaned = PurePosixPath(posix).as_posix()
    return cleaned.casefold() if os.name == "nt" else cleaned


@dataclass(frozen=True)
class ReadOutcome:
    """Result of one file read: text, or the reason nothing was read."""

    text: str | None
    reason: str | None = None


@dataclass(frozen=True)
class ResolvedRoots:
    """Allowed, resolved source roots plus a reason for every root that was rejected."""

    roots: tuple[Path, ...]
    rejected: tuple[str, ...]


@dataclass(frozen=True)
class ReadPolicy:
    """What the adapter may read under one repository root."""

    root: Path
    read_roots: tuple[str, ...]
    deny_globs: tuple[str, ...]
    max_file_bytes: int

    def relative(self, path: Path) -> str | None:
        """Return the POSIX path relative to the root, or None if the real path escapes it.

        The real (symlink-resolved) path must also lie inside one of the scope's read roots, so a
        link inside an allowed root cannot reach elsewhere in the repository.
        """
        try:
            rel = path.resolve().relative_to(self.root).as_posix()
        except (ValueError, OSError):
            return None
        return rel if self._in_read_roots(rel) else None

    def _in_read_roots(self, rel_posix: str) -> bool:
        """True if no scope read roots are set or the path lies inside one of them."""
        if not self.read_roots:
            return True
        source = PurePosixPath(_fold(rel_posix))
        for allowed in self.read_roots:
            allowed_path = PurePosixPath(_fold(allowed))
            if source == allowed_path or allowed_path in source.parents:
                return True
        return False

    def is_denied(self, rel_posix: str) -> bool:
        """True if the relative POSIX path matches any deny glob (by path or path component)."""
        rel_posix = rel_posix.casefold()
        parts = rel_posix.split("/")
        for raw in self.deny_globs:
            glob = raw.casefold()
            stripped = glob[3:] if glob.startswith("**/") else glob
            if fnmatch.fnmatchcase(rel_posix, glob) or fnmatch.fnmatchcase(rel_posix, stripped):
                return True
            if "/" not in glob and any(fnmatch.fnmatchcase(p, glob) for p in parts):
                return True
        return False

    def _within_read_roots(self, rel: Path) -> list[str]:
        """Return the effective relative roots after intersecting with the scope read roots."""
        if not self.read_roots:
            return [rel.as_posix()]
        out = []
        for allowed in self.read_roots:
            allowed_path = PurePosixPath(allowed)
            source = PurePosixPath(rel.as_posix())
            if source == allowed_path or allowed_path in source.parents:
                out.append(source.as_posix())
            elif source in allowed_path.parents:
                out.append(allowed_path.as_posix())
        return out

    def resolve_roots(self, configured: list[str]) -> ResolvedRoots:
        """Resolve configured source roots; reject absolute, traversing or escaping roots."""
        roots: list[Path] = []
        rejected: list[str] = []
        for raw in configured:
            posix, win = PurePosixPath(raw), PureWindowsPath(raw)
            if posix.is_absolute() or win.is_absolute() or win.drive or ".." in (
                    *posix.parts, *win.parts):
                rejected.append(f"{raw}: root must be relative and stay inside the repository")
                continue
            effective_roots = self._within_read_roots(posix)
            if not effective_roots:
                rejected.append(f"{raw}: outside the scope's read roots")
            for effective in effective_roots:
                candidate = (self.root / effective).resolve()
                rel = self.relative(candidate)
                if rel is None:
                    rejected.append(f"{raw}: resolves outside the repository root")
                elif candidate.exists():
                    roots.append(candidate)
                else:
                    rejected.append(f"{raw}: root does not exist")
        return ResolvedRoots(tuple(dict.fromkeys(roots)), tuple(rejected))

    def read_text(self, path: Path) -> ReadOutcome:
        """Read one file safely: contained, not denied, not too large, not binary."""
        rel = self.relative(path)
        if rel is None:
            return ReadOutcome(None, "outside_root")
        if self.is_denied(rel):
            return ReadOutcome(None, "denied")
        try:
            if path.stat().st_size > self.max_file_bytes:
                return ReadOutcome(None, "too_large")
            data = path.read_bytes()
        except OSError as exc:
            logger.warning("cannot read %s: %s", rel, exc)
            return ReadOutcome(None, f"unreadable: {exc.__class__.__name__}")
        if b"\x00" in data[:BINARY_SNIFF_BYTES]:
            return ReadOutcome(None, "binary")
        return ReadOutcome(data.decode("utf-8", errors="replace"))


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 02:00 [python-coder]: read_roots are enforced on the resolved real path inside
#   relative() (so read_text and knowledge-map nodes share it) and deny globs match
#   case-insensitively, closing .ENV / server.PEM bypasses on Windows and macOS.
#   (#KernelBootstrapV0/FIXA)
# - 2026-09-30 23:00 [python-coder]: A scope read root narrower than a configured source root
#   replaces that root; a source root outside every scope read root is dropped, so the scope can
#   only restrict, never widen, what config allows. (#KernelBootstrapV0/P5)
# ====================================================================
