"""
MODULE: completion_routing
GOAL: Give the knowledge-routing step the durability contract INF-700a-5
    (and its L3 children INF-700a-5-i, -ii, -iii) require: a learning
    written while a unit of work's isolated working directory still exists
    is written only once it is published by that unit of work's OWN
    commit, never by an unattended commit of the routing step's own, and
    the bookkeeping that stops a record being routed twice does not
    outlive the publication it rode.
BUSINESS CONTEXT: `harvest_learnings.py` already knows HOW to drain the
    knowledge sink and WHERE each record's destination file lives; what it
    does not know is that four of the five completion paths run inside a
    working directory that is later removed, and that "the destination
    file contains the text" is worthless once that directory is gone
    unless the write also reached the merged tree. This module is the
    thin layer a driver's completion step calls INSTEAD of writing
    directly against the current-working-directory-relative defaults:
    every destination is resolved explicitly under a caller-supplied
    `working_dir` (INF-700a-5's it_requirements: "an explicit
    working-directory parameter"), nothing is marked routed until the
    driver calls `confirm_routed` AFTER its own publication has actually
    reached the merged tree, and a write that is staged but never
    published is reported back as still-eligible rather than as done.
ARCHITECTURE: New module for the Knowledge System component
    (docs/architecture/components/knowledge-system.md), a sibling of
    `harvest_learnings.py` under `scripts/knowledge/`. Deliberately
    self-contained (stdlib only) rather than importing
    `harvest_learnings.py`'s routing/eligibility machinery: this module's
    concern is DURABILITY across a publication boundary, which is
    orthogonal to that module's entry_kind classification and does not
    need it. Loaded by path via `importlib.util.spec_from_file_location`
    by its test fixture (`unit_tests/workflows/_inf700a5_fixtures.py`),
    the same convention `harvest_learnings.py` itself documents for why
    its own siblings are loaded this way -- and, for the same reason,
    this file loads its own sink/state helper sibling
    (`completion_routing_state.py`, extracted for the GE-127b-1-style
    file-size ratchet) via the identical by-path mechanism rather than a
    bare top-level import.

Public functions (the contract test-writer's fixture module establishes):

    stage_completion(*, sink_path, state_path, working_dir, dry_run=False)
        Write every eligible, not-yet-confirmed sink record's learning
        text into its destination file resolved under `working_dir`.
        Does NOT touch `state_path` -- confirmation is a separate, later
        call. Returns a dict of counts plus the manifest of paths written
        and the record hashes to pass to `confirm_routed`.

    confirm_routed(*, state_path, record_ids)
        Persist `record_ids` as durably routed. Callers must invoke this
        only after their own commit carrying the manifest paths has
        reached the merged tree.

    unconfirmed_writes_report(*, working_dir, install_root, manifest,
                               record_ids, state_path)
        Read-only. Names every manifest path whose learning text is
        absent from `install_root` (the merged tree), together with the
        text and whether the record is still eligible for a later run.

    emission_backlog(*, sink_path, read_hashes)
        Read-only. Re-reads `sink_path` and reports how many eligible
        records are present versus how many `read_hashes` already
        accounts for, naming the difference rather than routing it.

    claim_and_confirm_routed(*, state_path, record_ids, lock_path=None,
                              arbitration_enabled=True)
        Atomically merge `record_ids` into the bookkeeping at
        `state_path`, returning only the subset this call newly claimed.
        Arbitrates via an flock'd lock file so two concurrent completions
        racing over one shared `state_path` do not both claim the same
        record. `arbitration_enabled=False` is the reachability negative
        control INF-700a-5-iii's it_requirements demand: with it, no
        arbitration is performed at all.
"""

from __future__ import annotations

import fcntl
import importlib.util
import os
import sys
from pathlib import Path
from typing import Any


def _load_required_sibling_module(module_name: str, filename: str) -> Any:
    """Load a required sibling module from this file's own directory.

    Mirrors ``harvest_learnings.py``'s own helper of the same name and for
    the same reason: this file is loaded via
    ``importlib.util.spec_from_file_location`` by its test fixture, which
    does not add ``scripts/knowledge/`` to ``sys.path`` first, so a bare
    top-level ``import`` would not resolve.

    Raises
    ------
    ImportError
        If the sibling module cannot be located at all.
    """
    module_path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not build an import spec for {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_state = _load_required_sibling_module("completion_routing_state", "completion_routing_state.py")

logger = _state.logger


def stage_completion(
    *,
    sink_path: Path | str,
    state_path: Path | str,
    working_dir: Path | str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Stage every eligible, not-yet-confirmed learning into *working_dir*.

    Resolves each record's ``destination`` explicitly under *working_dir*
    (never against the invoking process's own current directory) and
    appends its learning text there. Does NOT persist anything to
    *state_path* -- confirmation only happens once the caller's own
    publication has reached the merged tree (see ``confirm_routed``).

    A per-record staging failure is logged and counted in ``unwritten``;
    it never raises, per the project's fail-open error-handling policy
    for this family (a routing failure must never fail the unit of work).
    """
    sink_path = Path(sink_path)
    state_path = Path(state_path)
    working_dir = Path(working_dir)

    if not sink_path.exists():
        return {
            "read": 0,
            "written": 0,
            "unwritten": 0,
            "case": "did_not_run",
            "manifest": [],
            "record_ids": [],
        }

    confirmed = _state.load_state_set(state_path)
    unconfirmed_records = [
        record
        for record in _state.read_eligible_sink_records(sink_path)
        if record[0] not in confirmed
    ]

    manifest: list[str] = []
    record_ids: list[str] = []
    unwritten = 0

    for record_hash, text, destination in unconfirmed_records:
        if dry_run:
            continue
        abs_dest = working_dir / destination
        try:
            abs_dest.parent.mkdir(parents=True, exist_ok=True)
            with open(abs_dest, "a", encoding="utf-8") as fh:
                fh.write(text + "\n")
        except OSError as exc:
            logger.warning(
                "Could not stage routing write to %s: %s -- record stays "
                "unwritten and will be retried on a later run.",
                abs_dest,
                exc,
            )
            unwritten += 1
            continue
        manifest.append(str(abs_dest))
        record_ids.append(record_hash)

    case = "could_not_complete" if unwritten else "completed"

    return {
        "read": len(unconfirmed_records),
        "written": len(manifest),
        "unwritten": unwritten,
        "case": case,
        "manifest": manifest,
        "record_ids": record_ids,
    }


def confirm_routed(*, state_path: Path | str, record_ids: list[str]) -> None:
    """Persist *record_ids* as durably routed.

    Callers must invoke this only after their own commit carrying the
    manifest paths ``stage_completion`` returned has actually reached the
    merged tree -- never at staging time (a mark written earlier would be
    true before publication has happened, which is the bookkeeping this
    AC family forbids).

    Fails open: a persist failure is already logged by
    ``persist_state_set``; it is swallowed here rather than raised, so a
    bookkeeping failure never fails the unit of work. The affected
    records simply remain unconfirmed and are retried by a later run.
    """
    if not record_ids:
        return
    state_path = Path(state_path)
    try:
        current = _state.load_state_set(state_path)
        _state.persist_state_set(state_path, current | set(record_ids))
    except OSError:
        pass


def unconfirmed_writes_report(
    *,
    working_dir: Path | str,
    install_root: Path | str,
    manifest: list[str],
    record_ids: list[str],
    state_path: Path | str,
) -> list[dict[str, Any]]:
    """Name every manifest write absent from the merged tree.

    Read-only: consults *state_path* but never mutates it (INF-700a-5-i's
    it_requirements: "that read must not mutate it"). For each
    ``(manifest_path, record_id)`` pair, compares the working-directory
    content against *install_root*'s real content at the same relative
    path; a manifest path whose learning text has already reached
    *install_root* is omitted. Each remaining entry carries the
    destination (relative to *working_dir*), the still-unpublished
    learning text, and whether the underlying record is still eligible
    for a later run (i.e. not yet confirmed at *state_path*).
    """
    working_dir = Path(working_dir)
    install_root = Path(install_root)
    confirmed = _state.load_state_set(Path(state_path))

    report: list[dict[str, Any]] = []
    for path_str, record_id in zip(manifest, record_ids):
        abs_path = Path(path_str)
        try:
            rel_path = abs_path.relative_to(working_dir)
        except ValueError:
            rel_path = Path(abs_path.name)

        working_content = _state.read_text_or_empty(abs_path)
        install_content = _state.read_text_or_empty(install_root / rel_path)
        if working_content == install_content:
            continue

        appended_text = working_content
        if install_content and working_content.startswith(install_content):
            appended_text = working_content[len(install_content) :]
        appended_text = appended_text.strip("\n")

        report.append(
            {
                "destination": str(rel_path),
                "text": appended_text,
                "eligible": record_id not in confirmed,
            }
        )
    return report


def emission_backlog(
    *, sink_path: Path | str, read_hashes: set[str] | list[str]
) -> dict[str, Any]:
    """Report how many eligible sink records a routing step's read set missed.

    Read-only, no side effects: re-reads *sink_path* but never touches
    *state_path* or writes anything (this AC's it_requirements: "must not
    route"). Every eligible record whose hash is not in *read_hashes* is
    reported as still waiting for the next completed unit of work, never
    as routed, written, or nothing-to-do.
    """
    read_hashes = set(read_hashes)
    records = _state.read_eligible_sink_records(Path(sink_path))

    waiting = [
        {"text": text, "destination": destination}
        for record_hash, text, destination in records
        if record_hash not in read_hashes
    ]
    present = len(records)
    difference = len(waiting)
    return {
        "present": present,
        "read": present - difference,
        "difference": difference,
        "waiting": waiting,
    }


def claim_and_confirm_routed(
    *,
    state_path: Path | str,
    record_ids: list[str],
    lock_path: Path | str | None = None,
    arbitration_enabled: bool = True,
) -> list[str]:
    """Atomically merge *record_ids* into the bookkeeping at *state_path*.

    Returns only the subset THIS call newly claimed -- ids a concurrent
    caller racing over the same *state_path* had already claimed are
    excluded. Arbitrates via an ``flock``'d *lock_path* (defaulting to
    ``state_path`` with a ``.lock`` suffix appended) so the read-then-write
    of the bookkeeping is atomic across overlapping callers, bounding the
    critical section to the state update alone (per this AC's
    it_requirements: nothing else may be held across it).

    With ``arbitration_enabled=False`` no locking is performed at all --
    the reachability negative control INF-700a-5-iii's it_requirements
    demand ("WHATEVER ARBITRATES MUST HAVE AN OFF SWITCH REACHABLE FROM
    THE TEST HARNESS") -- so two overlapping callers can both claim the
    same id. The race window is also deliberately widened in that case
    (see ``completion_routing_state.claim_without_arbitration``'s
    docstring) so the overlap is reliably observable rather than merely
    possible.

    Fails toward the duplicate: if the lock file itself cannot be opened,
    this degrades to the unarbitrated path rather than skipping the claim
    (per this AC's it_requirements: a mechanism that skips on failure
    produces the loss mode the criteria forbid, not the survivable one).
    """
    state_path = Path(state_path)
    ids = list(record_ids)
    if not ids:
        return []

    if not arbitration_enabled:
        return _state.claim_without_arbitration(state_path, ids, widen_race_window=True)

    resolved_lock_path = (
        Path(lock_path) if lock_path is not None else state_path.with_suffix(".lock")
    )
    try:
        resolved_lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_fd = os.open(str(resolved_lock_path), os.O_CREAT | os.O_RDWR)
    except OSError as exc:
        logger.warning(
            "Could not open routing lock %s (%s); proceeding without "
            "arbitration for this call rather than skipping the claim.",
            resolved_lock_path,
            exc,
        )
        return _state.claim_without_arbitration(state_path, ids, widen_race_window=True)

    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        try:
            return _state.claim_without_arbitration(state_path, ids)
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
    finally:
        os.close(lock_fd)


# DECISION HISTORY
# ================================================================================
# - 2026-09-21 [python-coder]: Created this module to satisfy the INF-700a-5
#   family's durability contract (INF-700a-5, INF-700a-5-i, INF-700a-5-ii,
#   INF-700a-5-iii): `stage_completion`/`confirm_routed` split staging from
#   confirmation so a record is never marked routed before its write has
#   actually been published; `unconfirmed_writes_report` gives the teardown
#   announcement a read-only, non-mutating way to name what a refused or
#   dropped publication left behind; `emission_backlog` counts (never
#   routes) the residual a publishing-phase emission creates after the
#   routing step has already read the sink; `claim_and_confirm_routed`
#   arbitrates the bookkeeping race two concurrent completions can now
#   produce over one shared, install-wide sink, with an explicit
#   `arbitration_enabled=False` off switch so the write-once behaviour is
#   provably exercised rather than merely present. Scoped strictly to what
#   the fast-lane test baseline for this AC set requires; the fuller
#   test_spec descriptors these ACs declare (re-eligibility after an
#   abandoned branch, the full failure-count/exit-status equality pair) are
#   not yet covered by a test in this run and are therefore not claimed
#   done here. Extracted sink/state helpers to completion_routing_state.py
#   in the same change to stay under the check-file-size 400-line limit for
#   new .py files. (#TICKETLESS reason=ac-scoped-fastlane-build-INF-700a-5)
