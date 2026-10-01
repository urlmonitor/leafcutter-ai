"""
MODULE: kernel.persistence.artifacts
GOAL: Durable, file-backed ArtifactStorePort: run-scoped artifacts addressed by a validated name.
BUSINESS CONTEXT: Large content (evidence bundles, reports, host inputs) travels by reference, not
    inline; clients receive an absolute path but hosts never choose one, so no input can write or
    read outside the run's artifact folder (Rev 3 section 13.1).
ARCHITECTURE: <run_root>/runs/<run_id>/artifacts/<name>. Names must satisfy ARTIFACT_NAME_RE (the
    rule the memory double enforces); the resolved path is additionally proven to lie inside the
    artifact folder. Writes are atomic; refs are the names and carry sha256 and size.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from kernel.persistence.base import ArtifactRef
from kernel.persistence.fsutil import (
    UnsafePathComponent,
    atomic_write_bytes,
    ensure_within,
    safe_component,
)
from kernel.persistence.memory import ARTIFACT_NAME_RE, InvalidArtifactName

logger = logging.getLogger(__name__)


class FileArtifactStore:
    """ArtifactStorePort persisting under <run_root>/runs/<run_id>/artifacts/."""

    def __init__(self, run_root: Path) -> None:
        """Bind the store to run_root (created lazily)."""
        self.run_root = Path(run_root)

    def artifact_dir(self, run_id: str) -> Path:
        """Return the validated artifact folder of a run."""
        return self.run_root / "runs" / safe_component(run_id) / "artifacts"

    def _path(self, run_id: str, name: str) -> Path:
        """Return the validated file path of an artifact."""
        if not ARTIFACT_NAME_RE.fullmatch(name):
            raise InvalidArtifactName(name)
        folder = self.artifact_dir(run_id)
        try:
            return ensure_within(folder, folder / name)
        except UnsafePathComponent as exc:
            raise InvalidArtifactName(name) from exc

    def write_artifact(self, run_id: str, name: str, content: bytes | str) -> ArtifactRef:
        """Store content under a validated name and return its reference."""
        data = content.encode("utf-8") if isinstance(content, str) else content
        path = self._path(run_id, name)
        atomic_write_bytes(path, data)
        return ArtifactRef(ref=name, sha256=hashlib.sha256(data).hexdigest(),
                           size_bytes=len(data), path=str(path))

    def read_artifact(self, run_id: str, ref: str) -> bytes:
        """Return the stored bytes (KeyError if the ref is unknown)."""
        path = self._path(run_id, ref)
        try:
            return path.read_bytes()
        except FileNotFoundError as exc:
            raise KeyError(ref) from exc
        except OSError:
            logger.exception("cannot read artifact %s of run %s", ref, run_id)
            raise

    def absolute_path(self, run_id: str, ref: str) -> str | None:
        """Return the absolute path of an existing artifact, or None if it does not exist."""
        path = self._path(run_id, ref)
        return str(path) if path.is_file() else None


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 20:00 [python-coder]: Names are checked with fullmatch so a trailing newline is
#   rejected. (#KernelBootstrapV0/FIXB)
# - 2026-09-30 23:00 [python-coder]: Invalid names always raise InvalidArtifactName (the memory
#   double's error) so callers handle one exception type for both stores. (#KernelBootstrapV0/P2)
# ====================================================================
