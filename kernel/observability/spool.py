"""
MODULE: kernel.observability.spool
GOAL: Local JSONL spool that keeps observations when Langfuse export is unavailable.
BUSINESS CONTEXT: Telemetry failure must never erase state or fail a run (Rev 3 section 12.4); the
    spool preserves what would have been exported so a degraded run can still be diagnosed.
    V0 does not re-export the spool (documented limitation).
ARCHITECTURE: TelemetrySpool appends one redacted JSON line per observation to
    <run_root>/telemetry_spool.jsonl under a lock. A write failure is logged at WARNING and
    swallowed: the spool is the last resort and must not raise into the kernel.
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from kernel.contracts.base import utc_now
from kernel.persistence.fsutil import append_line

logger = logging.getLogger(__name__)

SPOOL_FILE_NAME = "telemetry_spool.jsonl"


class TelemetrySpool:
    """Append-only local spool of observations that could not be exported."""

    def __init__(self, path: Path, mask: Callable[..., Any] | None = None) -> None:
        """Bind the spool to path; mask (a Redactor) is applied to every record."""
        self.path = Path(path)
        self._mask = mask
        self._lock = threading.Lock()
        self.written = 0

    def write(self, kind: str, name: str, payload: dict[str, Any], reason: str = "") -> bool:
        """Append one observation record.

        Args:
            kind: span, generation, event or segment.
            name: Observation name.
            payload: JSON-compatible observation data (correlation ids, input, output, ...).
            reason: Why the observation was spooled (for example observability_degraded).

        Returns:
            bool: True if the record reached disk, False if the spool write itself failed.
        """
        record = {"at": utc_now().isoformat(), "kind": kind, "name": name,
                  "reason": reason, "data": payload}
        try:
            safe = self._mask(data=record) if self._mask is not None else record
            line = json.dumps(safe, default=str, ensure_ascii=False)
            with self._lock:
                append_line(self.path, line)
        except (OSError, TypeError, ValueError):
            logger.warning("telemetry spool write to %s failed", self.path, exc_info=True)
            return False
        self.written += 1
        return True

    def read(self) -> list[dict[str, Any]]:
        """Return the spooled records (for diagnosis and tests)."""
        try:
            text = self.path.read_text(encoding="utf-8") if self.path.is_file() else ""
        except OSError:
            logger.warning("cannot read telemetry spool %s", self.path, exc_info=True)
            return []
        records: list[dict[str, Any]] = []
        for line in text.splitlines():
            try:
                records.append(json.loads(line))
            except ValueError:
                logger.warning("skipping unreadable spool line")
        return records


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:00 [python-coder]: The spool masks with the same Redactor as the export path so
#   a degraded run cannot leak what a healthy run would have hidden. (#KernelBootstrapV0/P2)
# ====================================================================
