"""
MODULE: kernel.persistence.memory
GOAL: In-memory run, gap and artifact stores implementing the persistence ports.
BUSINESS CONTEXT: Scheduler, graph and service tests must run fast and offline without touching
    the project tree; these doubles behave like the file stores (P2) for the port contract.
ARCHITECTURE: Plain dicts and lists, no IO. Artifact names are validated exactly as the file
    store must, so tests catch path-injection mistakes early.
"""

from __future__ import annotations

import hashlib
import re

from kernel.contracts.interaction import HostWorkRequest, HumanQuestion
from kernel.contracts.run import CapabilityGap, RunEvent
from kernel.persistence.base import (
    ArtifactRef,
    RunAlreadyExists,
    RunNotFound,
    RunRecord,
    SubmissionRecord,
    aggregate_gaps,
)

ARTIFACT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class InvalidArtifactName(ValueError):
    """The artifact name is not a plain validated file name."""

    def __init__(self, name: str) -> None:
        """Build the message from the rejected name."""
        super().__init__(f"invalid artifact name: {name!r}")
        self.name = name


class MemoryRunStore:
    """RunStorePort backed by dicts."""

    def __init__(self) -> None:
        """Create an empty store."""
        self._runs: dict[str, RunRecord] = {}
        self._events: dict[str, list[RunEvent]] = {}
        self._interactions: dict[tuple[str, str], HostWorkRequest | HumanQuestion] = {}
        self._ledger: dict[tuple[str, str], SubmissionRecord] = {}

    def create_run(self, record: RunRecord) -> None:
        """Create a run record."""
        if record.run_id in self._runs:
            raise RunAlreadyExists(record.run_id)
        self._runs[record.run_id] = record
        self._events.setdefault(record.run_id, [])

    def get_run(self, run_id: str) -> RunRecord:
        """Return the run record."""
        try:
            return self._runs[run_id]
        except KeyError as exc:
            raise RunNotFound(run_id) from exc

    def update_run(self, record: RunRecord) -> None:
        """Replace the run record."""
        self.get_run(record.run_id)
        self._runs[record.run_id] = record

    def compare_and_update(self, record: RunRecord, expected_revision: int) -> bool:
        """Replace the record only if the stored state_revision equals expected_revision."""
        if self.get_run(record.run_id).state_revision != expected_revision:
            return False
        self._runs[record.run_id] = record
        return True

    def list_run_ids(self) -> list[str]:
        """Return sorted run ids."""
        return sorted(self._runs)

    def is_cancelled(self, run_id: str) -> bool:
        """Return True if the record carries a cancellation."""
        return self.get_run(run_id).cancel is not None

    def append_event(self, event: RunEvent) -> None:
        """Append an event."""
        self._events.setdefault(event.run_id, []).append(event)

    def read_events(self, run_id: str, after_seq: int = -1) -> list[RunEvent]:
        """Return events after after_seq ordered by seq."""
        events = [e for e in self._events.get(run_id, []) if e.seq > after_seq]
        return sorted(events, key=lambda e: e.seq)

    def save_interaction(self, run_id: str, packet: HostWorkRequest | HumanQuestion) -> None:
        """Store the packet as delivered."""
        self._interactions[(run_id, packet.id)] = packet

    def load_interaction(self, run_id: str, interaction_id: str
                         ) -> HostWorkRequest | HumanQuestion | None:
        """Return a saved packet or None."""
        return self._interactions.get((run_id, interaction_id))

    def record_submission(self, record: SubmissionRecord) -> None:
        """Write the ledger entry."""
        self._ledger[(record.run_id, record.interaction_id)] = record

    def get_submission(self, run_id: str, interaction_id: str) -> SubmissionRecord | None:
        """Return the ledger entry or None."""
        return self._ledger.get((run_id, interaction_id))


class MemoryGapStore:
    """GapStorePort backed by a list of observations."""

    def __init__(self) -> None:
        """Create an empty store."""
        self.observations: list[CapabilityGap] = []
        self.drafts: dict[str, str] = {}

    def record(self, gap: CapabilityGap) -> None:
        """Append an observation."""
        self.observations.append(gap)

    def load_gaps(self) -> list[CapabilityGap]:
        """Return aggregated gaps."""
        return aggregate_gaps(self.observations)

    def write_draft(self, gap: CapabilityGap, markdown: str) -> str:
        """Store the draft and return its reference."""
        ref = f"drafts/{gap.gap_key}.md"
        self.drafts[ref] = markdown
        return ref


class MemoryArtifactStore:
    """ArtifactStorePort backed by a dict."""

    def __init__(self) -> None:
        """Create an empty store."""
        self._blobs: dict[tuple[str, str], bytes] = {}

    def write_artifact(self, run_id: str, name: str, content: bytes | str) -> ArtifactRef:
        """Store content under a validated name."""
        if not ARTIFACT_NAME_RE.match(name):
            raise InvalidArtifactName(name)
        data = content.encode("utf-8") if isinstance(content, str) else content
        self._blobs[(run_id, name)] = data
        return ArtifactRef(ref=name, sha256=hashlib.sha256(data).hexdigest(),
                           size_bytes=len(data))

    def read_artifact(self, run_id: str, ref: str) -> bytes:
        """Return stored bytes (KeyError if unknown)."""
        return self._blobs[(run_id, ref)]

    def absolute_path(self, run_id: str, ref: str) -> str | None:
        """Memory artifacts have no filesystem path."""
        return None


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:00 [python-coder]: ARTIFACT_NAME_RE and InvalidArtifactName are exported so the
#   file store (P2) enforces the identical rule. (#KernelBootstrapV0/P1)
# ====================================================================
