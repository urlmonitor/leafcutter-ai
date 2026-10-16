"""Explicit operator reconciliation for interrupted, uncertain side effects.

Locks exclude active coordinators. A changed Linux kernel or PID namespace incarnation proves the
recorded processes cannot remain alive; explicit operator confirmation is also required.
"""

import json
import logging
import os
import re
from pathlib import Path
import time
import uuid
from contextlib import ExitStack

from .git_ops import GitOps
from .locks import exclusive


LOGGER = logging.getLogger(__name__)


def linux_runtime_id():
    """Identify the Linux kernel and PID namespace incarnation of this runtime."""
    try:
        boot = str(uuid.UUID(Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()))
        stat = Path("/proc/1/stat").read_text(encoding="ascii")
        start = int(stat.rsplit(") ", 1)[1].split()[19])
        # Root-owned PID 1 namespace links may be ptrace-protected. The
        # coordinator belongs to that same runtime PID namespace; its own link
        # is readable without elevated credentials.
        namespace = os.readlink("/proc/self/ns/pid")
    except (OSError, ValueError, IndexError) as exc:
        LOGGER.info("Linux runtime identity unavailable: %s", type(exc).__name__)
        return None
    identity = {"boot_id": boot, "init_start_ticks": start, "pid_namespace": namespace}
    return identity if _valid_identity(identity) else None


def _valid_identity(identity):
    if not isinstance(identity, dict) or set(identity) != {"boot_id", "init_start_ticks", "pid_namespace"}:
        return False
    try:
        uuid.UUID(identity["boot_id"])
    except (ValueError, TypeError, AttributeError):
        return False
    return (type(identity["init_start_ticks"]) is int and identity["init_start_ticks"] >= 0
            and isinstance(identity["pid_namespace"], str)
            and re.fullmatch(r"pid:\[\d+\]", identity["pid_namespace"]) is not None)


def _restarted(previous, current):
    if not _valid_identity(previous) or not _valid_identity(current):
        return False
    return previous["boot_id"] != current["boot_id"] or (
        previous["init_start_ticks"] != current["init_start_ticks"]
        and previous["pid_namespace"] != current["pid_namespace"])


def reconcile(repo, store, run_id, *, confirm_processes_stopped=False, note="", git=None):
    if confirm_processes_stopped is not True or not isinstance(note, str) or not note.strip():
        raise ValueError("Explicit --confirm-processes-stopped and a non-empty --note are required")
    # Read the identity before constructing paths from caller input.
    run = store.get_run(run_id)
    run_id = run["id"]
    if not run_id.isalnum():
        raise ValueError("Invalid persisted run identity")
    directory = store.path.parent
    with ExitStack() as stack:
        for path in (directory / "startup.lock", directory / "service.lock", directory / (run_id + ".lock"),
                     directory / "locks" / (run_id + ".lock")):
            try:
                acquired = stack.enter_context(exclusive(path))
            except OSError as exc:
                LOGGER.warning("Cannot acquire recovery lock: %s", type(exc).__name__)
                raise ValueError("Worker or run is still active, or its lock is inaccessible") from exc
            if not acquired:
                raise ValueError("Worker or run is still active; stop it and wait for draining before reconciliation")
        with store._transaction():
            if store.get_settings().get("enabled"):
                raise ValueError("Disable the worker before reconciliation")
            run = store.get_run(run_id)
            phase = run["payload"].get("in_flight")
            leases = store.list_leases(run_id)
            uncertain = [ac for ac, budget in run["budgets"].items() if budget["in_progress"]]
            if run["state"] in {"delivered", "completed"}:
                raise ValueError("Delivered or completed runs cannot be reconciled by this command")
            if phase not in {"discover", "implement", "validate", "review"} and not leases and not uncertain:
                raise ValueError("No uncertain discovery, implementation, validation, review or capacity to reconcile")
            previous_boot = run["payload"].get("process_runtime_id")
            current_boot = linux_runtime_id()
            if not _restarted(previous_boot, current_boot):
                raise ValueError("Reconciliation requires a proven Linux runtime restart after the recorded intent; "
                                 "same-runtime or legacy unknown processes retain their capacity")
            if phase in {"prepare", "publish"}:
                raise ValueError("Preparation/publication must use their own idempotent reconciliation")
            # Inspect only; never alter a possibly interrupted commit or worktree.
            operations = git or GitOps(repo, store.get_settings())
            workspace = operations.assert_workspace(run)
            head = operations.head(workspace)
            status = operations.git(workspace, "status", "--porcelain", "--untracked-files=all")
            from .workspace_checkpoint import fingerprint
            checkpoint = fingerprint(operations, run) if git is None else None
            return _reconcile_transaction(store, run, phase, leases, uncertain, head, status, note.strip(), previous_boot, current_boot, checkpoint)


def _reconcile_transaction(store, run, phase, leases, uncertain, head, status, note, previous_boot, current_boot, checkpoint=None):
    now = time.time()
    audit_id = uuid.uuid4().hex
    resumable = phase in {"validate", "review"} and not uncertain and run["review_count"] < 2
    payload = dict(run["payload"])
    for key in ("package", "validated_sha", "reviewed_sha", "review", "input_gate", "discovery_proof"):
        payload.pop(key, None)
    payload["in_flight"] = None
    if checkpoint is not None:
        payload["workspace_checkpoint"] = checkpoint
    payload["next"] = "validate" if resumable else payload.get("next", phase or "implement")
    audit = {
        "id": audit_id, "at": now, "note": note, "processes_stopped_attested": True,
        "previous_runtime_id": previous_boot, "current_runtime_id": current_boot,
        "previous_phase": phase, "previous_state": run["state"],
        "released_lease_ids": [lease["lease_id"] for lease in leases],
        "exhausted_ac_ids": uncertain, "review_count": run["review_count"],
        "head_sha": head, "worktree_status": status,
        "outcome": "fresh_validation" if resumable else "human_required",
    }
    payload["reconciliations"] = [*payload.get("reconciliations", []), audit]
    for ac in uncertain:
        store.connection.execute(
            "UPDATE budgets SET elapsed_seconds=MAX(elapsed_seconds,3600),in_progress=0,last_success=0 "
            "WHERE run_id=? AND ac_id=?", (run["id"], ac),
        )
    store.connection.execute(
        "UPDATE leases SET released_at=? WHERE run_id=? AND released_at IS NULL", (now, run["id"]),
    )
    # Resolve only the engine's exact interrupted-intent notice. Other questions
    # and failures still require their own answer; attestation is not approval.
    store.connection.execute(
        "UPDATE inbox SET status='resolved',answer=?,resolved_at=? WHERE run_id=? AND status='pending' "
        "AND reason='Interrupted side effect requires explicit reconciliation before another agent call'",
        (f"Reconciled by operator: {note} (audit {audit_id})", now, run["id"]),
    )
    if not resumable:
        reason = "Reconciled interruption requires human handling; automatic budgets were not reset"
        details = json.dumps({"audit_id": audit_id, "exhausted_ac_ids": uncertain,
                              "review_count": run["review_count"]})
        store.connection.execute(
            "INSERT INTO inbox(id,run_id,reason,details,fingerprint,created_at) VALUES(?,?,?,?,?,?)",
            (uuid.uuid4().hex, run["id"], reason, details, audit_id, now),
        )
    pending = store.connection.execute(
        "SELECT COUNT(*) FROM inbox WHERE run_id=? AND status='pending'", (run["id"],),
    ).fetchone()[0]
    state = "paused" if resumable and not pending else "blocked"
    store.connection.execute(
        "UPDATE runs SET state=?,payload=?,updated_at=? WHERE id=?",
        (state, json.dumps(payload), now, run["id"]),
    )
    return {"run_id": run["id"], "state": state, "reconciliation": audit}
