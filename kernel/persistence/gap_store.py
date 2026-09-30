"""
MODULE: kernel.persistence.gap_store
GOAL: Durable, file-backed GapStorePort: append-only gap observations aggregated by gap key, plus
    backlog-ready drafts.
BUSINESS CONTEXT: Gaps are the feedback loop for the capability backlog (Rev 3 section 14); the
    same unmet need seen in many runs must become one gap with an occurrence count and a few
    example runs, never a flood of duplicates and never a live registry entry.
ARCHITECTURE: <run_root>/gaps/observations.jsonl holds raw observations (fsynced lines; a repeated
    observation id from a resumed node is ignored); load_gaps aggregates them with the shared
    aggregate_gaps so memory and file stores agree. Drafts live in gaps/drafts/<gap_key>.md and
    are written atomically; the gap key is validated as a path component.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from pydantic import ValidationError

from kernel.contracts.run import CapabilityGap
from kernel.persistence.base import aggregate_gaps
from kernel.persistence.fsutil import append_line, atomic_write_bytes, read_lines, safe_component

logger = logging.getLogger(__name__)


class FileGapStore:
    """GapStorePort persisting under <run_root>/gaps/."""

    def __init__(self, run_root: Path) -> None:
        """Bind the store to run_root (created lazily)."""
        self.gaps_dir = Path(run_root) / "gaps"
        self._lock = threading.RLock()

    @property
    def observations_file(self) -> Path:
        """Return the path of observations.jsonl."""
        return self.gaps_dir / "observations.jsonl"

    def _observations(self) -> list[CapabilityGap]:
        """Read raw observations, skipping torn or unreadable lines with a warning."""
        found: list[CapabilityGap] = []
        for line in read_lines(self.observations_file):
            try:
                found.append(CapabilityGap.model_validate_json(line))
            except ValidationError:
                logger.warning("skipping unreadable gap observation line")
        return found

    def record(self, gap: CapabilityGap) -> None:
        """Append one observation; an observation id that is already stored is ignored."""
        with self._lock:
            if any(obs.id == gap.id for obs in self._observations()):
                logger.debug("gap observation %s already recorded", gap.id)
                return
            append_line(self.observations_file, gap.model_dump_json())

    def load_gaps(self) -> list[CapabilityGap]:
        """Return gaps aggregated by gap_key (occurrences summed, at most five example runs)."""
        with self._lock:
            return aggregate_gaps(self._observations())

    def write_draft(self, gap: CapabilityGap, markdown: str) -> str:
        """Write gaps/drafts/<gap_key>.md atomically and return its run-root-relative ref."""
        name = f"{safe_component(gap.gap_key)}.md"
        with self._lock:
            atomic_write_bytes(self.gaps_dir / "drafts" / name, markdown.encode("utf-8"))
        return f"drafts/{name}"


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:00 [python-coder]: Observations dedupe by observation id (not only by gap key)
#   so a node that re-executes after resume cannot double-count an occurrence.
#   (#KernelBootstrapV0/P2)
# ====================================================================
