"""
MODULE: kernel.persistence.base
GOAL: Storage ports (run, gap, artifact stores), their record models and the shared gap
    aggregation.
BUSINESS CONTEXT: Runs must survive process restarts, duplicate submissions must be idempotent
    and gap telemetry must feed the capability backlog (Rev 3 sections 12.4, 13.1, 14). Ports let
    the scheduler run against memory in tests and against files in production (P2).
ARCHITECTURE: Ports are synchronous Protocols (writes are small atomic file operations). The
    file-backed implementations (P2) and memory doubles (memory.py) share aggregate_gaps so the
    observation-to-gap rules are defined once.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from pydantic import Field

from kernel.contracts.base import KernelModel, utc_now
from kernel.contracts.enums import RunStatus
from kernel.contracts.interaction import HostWorkRequest, HumanQuestion, InteractionSubmission
from kernel.contracts.run import MAX_EXAMPLE_RUNS, CapabilityGap, RunEvent
from kernel.observability.tracer import TraceState


class RunNotFound(LookupError):
    """No run record exists for the run id."""

    def __init__(self, run_id: str) -> None:
        """Build the message from the run id."""
        super().__init__(f"run not found: {run_id}")
        self.run_id = run_id


class RunAlreadyExists(ValueError):
    """A run record with this id already exists."""

    def __init__(self, run_id: str) -> None:
        """Build the message from the run id."""
        super().__init__(f"run already exists: {run_id}")
        self.run_id = run_id


class CancelInfo(KernelModel):
    """Who cancelled a run and when."""

    by: str
    at: datetime


class RunRecord(KernelModel):
    """Contents of run.json: the authoritative small record of a run."""

    run_id: str
    root_task_id: str
    status: RunStatus = RunStatus.RUNNING
    state_revision: int = Field(default=0, ge=0)
    trace: TraceState | None = None
    cancel: CancelInfo | None = None
    registry_hash: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SubmissionRecord(KernelModel):
    """Idempotency ledger entry for an accepted submission."""

    run_id: str
    interaction_id: str
    sha256: str
    submission: InteractionSubmission
    accepted_at: datetime = Field(default_factory=utc_now)


class ArtifactRef(KernelModel):
    """Reference to a stored artifact."""

    ref: str
    sha256: str
    size_bytes: int = Field(ge=0)
    path: str | None = None


@runtime_checkable
class RunStorePort(Protocol):
    """Run records, event log, interaction packets and the submission ledger."""

    def create_run(self, record: RunRecord) -> None:
        """Create a run record (RunAlreadyExists if present)."""

    def get_run(self, run_id: str) -> RunRecord:
        """Return the run record (RunNotFound if absent)."""

    def update_run(self, record: RunRecord) -> None:
        """Atomically replace the run record (RunNotFound if absent)."""

    def list_run_ids(self) -> list[str]:
        """Return all run ids, sorted."""

    def is_cancelled(self, run_id: str) -> bool:
        """Return True if the run record carries a cancellation."""

    def append_event(self, event: RunEvent) -> None:
        """Append an event to the run's log."""

    def read_events(self, run_id: str, after_seq: int = -1) -> list[RunEvent]:
        """Return events with seq greater than after_seq, in seq order."""

    def save_interaction(self, run_id: str, packet: HostWorkRequest | HumanQuestion) -> None:
        """Persist the packet exactly as delivered to the host."""

    def load_interaction(self, run_id: str, interaction_id: str
                         ) -> HostWorkRequest | HumanQuestion | None:
        """Return a saved packet or None."""

    def record_submission(self, record: SubmissionRecord) -> None:
        """Write the ledger entry for an accepted submission."""

    def get_submission(self, run_id: str, interaction_id: str) -> SubmissionRecord | None:
        """Return the ledger entry or None."""


@runtime_checkable
class GapStorePort(Protocol):
    """Append-only gap observations with aggregated reads."""

    def record(self, gap: CapabilityGap) -> None:
        """Append one observation."""

    def load_gaps(self) -> list[CapabilityGap]:
        """Return aggregated gaps (see aggregate_gaps), sorted by gap_key."""

    def write_draft(self, gap: CapabilityGap, markdown: str) -> str:
        """Store a backlog-ready draft for the gap and return its reference."""


@runtime_checkable
class ArtifactStorePort(Protocol):
    """Run-scoped artifact storage; names are validated, host input never names a path."""

    def write_artifact(self, run_id: str, name: str, content: bytes | str) -> ArtifactRef:
        """Store content under a validated name and return its reference."""

    def read_artifact(self, run_id: str, ref: str) -> bytes:
        """Return the stored bytes (KeyError if the ref is unknown)."""

    def absolute_path(self, run_id: str, ref: str) -> str | None:
        """Return an absolute filesystem path for the client, or None for memory stores."""


def aggregate_gaps(observations: list[CapabilityGap]) -> list[CapabilityGap]:
    """Merge observations by gap_key into one gap each.

    occurrence_count sums, first_seen/last_seen take the min/max, example_run_ids keeps at most
    five distinct run ids in first-seen order, and the newest observation supplies the rest.

    Args:
        observations: Raw gap observations.

    Returns:
        list[CapabilityGap]: Aggregated gaps sorted by gap_key.
    """
    grouped: dict[str, list[CapabilityGap]] = {}
    for obs in observations:
        grouped.setdefault(obs.gap_key, []).append(obs)
    merged: list[CapabilityGap] = []
    for key in sorted(grouped):
        group = sorted(grouped[key], key=lambda g: (g.last_seen or g.created_at, g.id))
        newest = group[-1]
        examples: list[str] = []
        for obs in group:
            for run_id in obs.example_run_ids:
                if run_id not in examples and len(examples) < MAX_EXAMPLE_RUNS:
                    examples.append(run_id)
        firsts = [g.first_seen for g in group if g.first_seen]
        lasts = [g.last_seen for g in group if g.last_seen]
        merged.append(newest.model_copy(update={
            "occurrence_count": sum(g.occurrence_count for g in group),
            "example_run_ids": examples,
            "first_seen": min(firsts) if firsts else None,
            "last_seen": max(lasts) if lasts else None,
        }))
    return merged


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:00 [python-coder]: Ports are synchronous; RunNotFound lives here and is
#   re-exported by service.py so persistence never imports the service layer.
#   (#KernelBootstrapV0/P1)
# ====================================================================
