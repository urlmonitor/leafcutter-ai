"""
MODULE: kernel.persistence.run_store
GOAL: Durable, file-backed RunStorePort: run.json, the append-only event log, interaction packets
    and the submission idempotency ledger.
BUSINESS CONTEXT: The local run record is authoritative for diagnosis, cancellation and duplicate
    detection; it must survive a crash at any point and never depend on Langfuse or the graph
    checkpoint (Rev 3 sections 12.4 and 13.1).
ARCHITECTURE: Layout <run_root>/runs/<run_id>/{run.json,events.jsonl,interactions/<id>.json,
    submissions/<id>.json}. Every path segment passes safe_component. run.json is written
    atomically; events are fsynced JSONL where a repeated seq is a no-op (first write wins);
    submissions are first-write-wins so a replay cannot change the ledger. One process lock
    serialises writers; cross-process writers are not supported in V0.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from pydantic import BaseModel, ValidationError

from kernel.contracts.interaction import HostWorkRequest, HumanQuestion
from kernel.contracts.run import RunEvent
from kernel.persistence.base import RunAlreadyExists, RunNotFound, RunRecord, SubmissionRecord
from kernel.persistence.fsutil import (
    append_line,
    atomic_write_bytes,
    create_exclusive,
    read_lines,
    read_text_or_none,
    safe_component,
)

logger = logging.getLogger(__name__)

_PACKET_TYPES = {"host_work": HostWorkRequest, "human_question": HumanQuestion}


class RunStoreCorrupt(ValueError):
    """A persisted run file cannot be parsed into its record model."""

    def __init__(self, path: Path, detail: str) -> None:
        """Build the message from the file path and parse detail."""
        super().__init__(f"corrupt run store file {path}: {detail}")
        self.path = str(path)


def _dump(model: BaseModel) -> bytes:
    """Serialise a pydantic model to indented UTF-8 JSON bytes."""
    return (model.model_dump_json(indent=2) + "\n").encode("utf-8")


class FileRunStore:
    """RunStorePort persisting under <run_root>/runs/<run_id>/."""

    def __init__(self, run_root: Path) -> None:
        """Bind the store to run_root (created lazily)."""
        self.run_root = Path(run_root)
        self._lock = threading.RLock()

    # ---- paths -------------------------------------------------------
    def run_dir(self, run_id: str) -> Path:
        """Return the validated directory of a run."""
        return self.run_root / "runs" / safe_component(run_id)

    def _run_file(self, run_id: str) -> Path:
        """Return the path of run.json."""
        return self.run_dir(run_id) / "run.json"

    def _events_file(self, run_id: str) -> Path:
        """Return the path of events.jsonl."""
        return self.run_dir(run_id) / "events.jsonl"

    def _child(self, run_id: str, folder: str, name: str) -> Path:
        """Return <run>/<folder>/<name>.json with both segments validated."""
        return self.run_dir(run_id) / folder / f"{safe_component(name)}.json"

    # ---- run record --------------------------------------------------
    def create_run(self, record: RunRecord) -> None:
        """Create run.json exclusively (RunAlreadyExists if present)."""
        with self._lock:
            if not create_exclusive(self._run_file(record.run_id), _dump(record)):
                raise RunAlreadyExists(record.run_id)

    def get_run(self, run_id: str) -> RunRecord:
        """Return the run record (RunNotFound if absent, RunStoreCorrupt if unparseable)."""
        path = self._run_file(run_id)
        text = read_text_or_none(path)
        if text is None:
            raise RunNotFound(run_id)
        try:
            return RunRecord.model_validate_json(text)
        except ValidationError as exc:
            raise RunStoreCorrupt(path, str(exc)) from exc

    def update_run(self, record: RunRecord) -> None:
        """Atomically replace run.json (RunNotFound if absent); identical content is a no-op."""
        with self._lock:
            current = self.get_run(record.run_id)
            if current == record:
                return
            atomic_write_bytes(self._run_file(record.run_id), _dump(record))

    def compare_and_update(self, record: RunRecord, expected_revision: int) -> bool:
        """Replace the record only if the stored state_revision equals expected_revision.

        Returns:
            bool: True if written, False if the stored revision differs (caller is stale).
        """
        with self._lock:
            if self.get_run(record.run_id).state_revision != expected_revision:
                return False
            atomic_write_bytes(self._run_file(record.run_id), _dump(record))
            return True

    def list_run_ids(self) -> list[str]:
        """Return the ids of all runs that have a run.json, sorted."""
        runs = self.run_root / "runs"
        try:
            children = list(runs.iterdir()) if runs.is_dir() else []
        except OSError:
            logger.exception("cannot list %s", runs)
            raise
        return sorted(p.name for p in children if (p / "run.json").is_file())

    def is_cancelled(self, run_id: str) -> bool:
        """Return True if run.json carries a cancellation."""
        return self.get_run(run_id).cancel is not None

    # ---- events ------------------------------------------------------
    def append_event(self, event: RunEvent) -> None:
        """Append the event; a seq that is already logged is ignored (first write wins)."""
        with self._lock:
            if any(e.seq == event.seq for e in self.read_events(event.run_id)):
                logger.debug("event seq %s already logged for %s", event.seq, event.run_id)
                return
            append_line(self._events_file(event.run_id), event.model_dump_json())

    def read_events(self, run_id: str, after_seq: int = -1) -> list[RunEvent]:
        """Return events with seq > after_seq ordered by seq; torn or bad lines are skipped."""
        events: list[RunEvent] = []
        for line in read_lines(self._events_file(run_id)):
            try:
                event = RunEvent.model_validate_json(line)
            except ValidationError:
                logger.warning("skipping unreadable event line in run %s", run_id)
                continue
            if event.seq > after_seq:
                events.append(event)
        return sorted(events, key=lambda e: e.seq)

    # ---- interactions ------------------------------------------------
    def save_interaction(self, run_id: str, packet: HostWorkRequest | HumanQuestion) -> None:
        """Persist the packet exactly as delivered, tagged with its type."""
        kind = "host_work" if isinstance(packet, HostWorkRequest) else "human_question"
        body = {"packet_type": kind, "packet": json.loads(packet.model_dump_json())}
        data = (json.dumps(body, indent=2) + "\n").encode("utf-8")
        with self._lock:
            atomic_write_bytes(self._child(run_id, "interactions", packet.id), data)

    def load_interaction(self, run_id: str, interaction_id: str
                         ) -> HostWorkRequest | HumanQuestion | None:
        """Return a saved packet or None."""
        path = self._child(run_id, "interactions", interaction_id)
        text = read_text_or_none(path)
        if text is None:
            return None
        try:
            body = json.loads(text)
            return _PACKET_TYPES[body["packet_type"]].model_validate(body["packet"])
        except (ValueError, KeyError, TypeError) as exc:
            raise RunStoreCorrupt(path, str(exc)) from exc

    # ---- submission ledger -------------------------------------------
    def record_submission(self, record: SubmissionRecord) -> None:
        """Write the ledger entry; an existing entry is never overwritten (first write wins)."""
        path = self._child(record.run_id, "submissions", record.interaction_id)
        with self._lock:
            if not create_exclusive(path, _dump(record)):
                logger.debug("submission ledger entry for %s already exists",
                             record.interaction_id)

    def get_submission(self, run_id: str, interaction_id: str) -> SubmissionRecord | None:
        """Return the ledger entry or None."""
        path = self._child(run_id, "submissions", interaction_id)
        text = read_text_or_none(path)
        if text is None:
            return None
        try:
            return SubmissionRecord.model_validate_json(text)
        except ValidationError as exc:
            raise RunStoreCorrupt(path, str(exc)) from exc


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:00 [python-coder]: update_run stays a plain atomic replace (the memory double
#   and P4 rely on that); optimistic concurrency is an opt-in compare_and_update so a stale
#   cancel write is never silently dropped. (#KernelBootstrapV0/P2)
# - 2026-09-30 23:00 [python-coder]: Duplicate event seq and duplicate submission are
#   first-write-wins because nodes re-execute on resume (design part 6 risk 6).
#   (#KernelBootstrapV0/P2)
# ====================================================================
