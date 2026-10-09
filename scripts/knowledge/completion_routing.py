"""
MODULE: completion_routing
GOAL: Give the knowledge-routing step the durability contract INF-700a-5
    (and its L3 children INF-700a-5-i, -ii, -iii) require: a learning
    written while a unit of work's isolated working directory still exists
    counts as written only once that unit of work's OWN commit carries it,
    and the bookkeeping that stops a record being routed twice never claims
    a record whose text is not yet on the base branch.
BUSINESS CONTEXT: The harvester (``harvest_learnings.py``) owns WHAT is
    routable and WHERE each record goes (ADR-034). On its own it writes
    against the invoking process's current directory and marks every record
    routed the moment it has written it -- in an isolated working directory
    that is later removed, both are the defect INF-700a-5 names. This module
    drives the harvester instead of replacing it (BrainCandy, 2026-10-08):
    the harvester's writes are redirected into the caller-supplied
    ``working_dir`` and its state write is held back (``persist_state=False``).
    The confirmation rule is check-the-base-branch: at the start of every
    stage, a record whose text is already on ``base_ref`` (origin/main) is
    claimed as routed; every other unconfirmed record is staged again. A
    record is therefore never marked at routing or commit time, an abandoned
    branch leaves its records eligible, and the accepted failure under two
    concurrent unmerged runs is a duplicate, never a loss.
ARCHITECTURE: Knowledge System component
    (docs/architecture/components/knowledge-system.md), sibling of
    ``harvest_learnings.py`` under ``scripts/knowledge/``. Loads its siblings
    by path (the convention ``harvest_learnings.py`` documents): the state
    primitives (``completion_routing_state.py``), the git reads
    (``completion_routing_git.py``) and the harvester itself. The production
    caller is ``completion_routing_cli.py`` (``stage`` before the path's own
    commit, ``observe`` after it), dispatched by the wired workflows.

Public functions:

    stage_completion(*, sink_path, state_path, working_dir, base_ref, dry_run)
        Claim records already on base_ref, then drive the harvester with its
        writes redirected into working_dir and its state write held back.
        Returns counts, the manifest (absolute paths written), the record
        ids staged, the hashes read, and per-record entries (destination
        relative to working_dir).
    observe_publication(*, working_dir, run, commit_status, sink_path, state_path)
        Read-only. Ask git what HEAD actually carries for each staged entry,
        name every write that did not reach the commit with its reason and
        eligibility, and recount the sink for records emitted after the stage.
    confirm_routed / claim_and_confirm_routed
        Persist ids as routed (the latter flock-arbitrated, with the
        ``arbitration_enabled`` off switch INF-700a-5-iii requires).
    unconfirmed_writes_report(...)
        Read-only. Name staged writes whose text is absent from a merged tree.
    emission_backlog(*, sink_path, read_hashes)
        Read-only. Present versus read, naming the difference as waiting.
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

    Raises
    ------
    ImportError
        If the sibling module cannot be located at all.
    """
    module_path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not build an import spec for {module_path}")  # noqa: TRY003
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_state = _load_required_sibling_module("completion_routing_state", "completion_routing_state.py")
_git = _load_required_sibling_module("completion_routing_git", "completion_routing_git.py")
_harvester = _load_required_sibling_module("harvest_learnings", "harvest_learnings.py")

logger = _state.logger

DEFAULT_BASE_REF = "origin/main"
WAITING_NOTE = (
    "still in the install's sink, waiting for the next completed unit of work "
    "in this install to route it"
)
_REASON_BY_COMMIT_STATUS = {"ok": "left_out_of_commit", "failed": "publication_refused"}


class _NotStaged(OSError):
    """Raised by the redirected capture to make the harvester leave a record
    unwritten and unmarked (its write-failure branch) without a real I/O
    error: a destination outside the working directory, or one whose change
    would conflict with the base branch."""


def _resolve_inside(working_dir: Path, destination: str) -> Path | None:
    """Resolve *destination* under *working_dir*; ``None`` if it escapes it.

    Pure function. An absolute destination or one that climbs out with
    ``..`` would write outside the branch doing the work -- INF-700a-5's
    rejected alternative 2 -- so it is refused rather than followed.
    """
    target = (working_dir / destination).resolve()
    try:
        target.relative_to(working_dir.resolve())
    except ValueError:
        return None
    return target


def stage_completion(
    *,
    sink_path: Path | str,
    state_path: Path | str,
    working_dir: Path | str,
    base_ref: str = DEFAULT_BASE_REF,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Stage every unconfirmed, not-yet-published learning into *working_dir*.

    Never persists a routed mark for a record it writes. The only marks it
    persists are for records whose text is ALREADY on *base_ref* -- their
    publication has happened, so the claim is true (flock-arbitrated, so two
    concurrent stages do not both claim). Fails open: a harvester exit is
    reported as ``could_not_complete``, never raised.
    """
    sink_path, state_path = Path(sink_path), Path(state_path)
    working_dir = Path(working_dir).resolve()

    records = _state.read_eligible_sink_records(sink_path)
    confirmed = _state.load_state_set(state_path)
    _git.refresh_base(working_dir, base_ref)
    has_base = _git.ref_exists(working_dir, base_ref)
    candidates = [r for r in records if r[0] not in confirmed]
    published = [
        h for h, text, dest in candidates
        if has_base and _git.text_on_ref(working_dir, base_ref, dest, text)
    ]
    if published and not dry_run:
        claim_and_confirm_routed(state_path=state_path, record_ids=published)
    ids_by_record = {(text, dest): h for h, text, dest in candidates if h not in published}

    entries: list[dict[str, Any]] = []
    not_staged: list[dict[str, Any]] = []

    def _redirected_capture(text: str, destination: str) -> None:
        target = _resolve_inside(working_dir, destination)
        rel = target.relative_to(working_dir).as_posix() if target is not None else None
        reason = None
        if target is None or rel is None:
            reason = "outside_working_directory"
        elif has_base and _git.would_conflict(working_dir, base_ref, rel):
            reason = "conflicts_with_merged_tree"
        if reason is not None:
            logger.warning("Routing write to %s left out: %s", destination, reason)
            not_staged.append({"destination": destination, "text": text, "reason": reason})
            raise _NotStaged(reason)
        try:
            _harvester._default_capture(text, str(target))
        except OSError:
            not_staged.append({"destination": destination, "text": text, "reason": "write_failed"})
            raise
        entries.append({
            "record_id": ids_by_record.get((text, destination)),
            "destination": rel,
            "text": text,
        })

    base = {"read": len(records), "read_hashes": [r[0] for r in records],
            "already_published": len(published)}
    try:
        result = _harvester.harvest(
            sink_path=sink_path,
            state_path=state_path,
            capture_fn=_redirected_capture,
            dry_run=dry_run,
            persist_state=False,
        )
    except SystemExit as exc:
        logger.warning("Harvester stopped (exit %s); nothing staged.", exc.code)
        return {**base, "harvest_completed": False, "case": "could_not_complete",
                "written": 0, "unwritten": 0,
                "manifest": [], "record_ids": [], "entries": [], "unwritten_records": [],
                "detail": f"harvester exited {exc.code} (sink unreadable or state corrupt)"}

    real_failures = sum(1 for r in not_staged if r["reason"] == "write_failed")
    return {
        **base,
        "harvest_completed": True,
        "case": "could_not_complete" if real_failures else "completed",
        "written": len(entries),
        "unwritten": result.outstanding,
        "manifest": sorted({str(working_dir / e["destination"]) for e in entries}),
        "record_ids": [e["record_id"] for e in entries if e["record_id"]],
        "entries": entries,
        "unwritten_records": not_staged,
        "detail": f"{real_failures} destination write(s) failed" if real_failures else None,
    }


def observe_publication(
    *,
    working_dir: Path | str,
    run: dict[str, Any],
    commit_status: str,
    sink_path: Path | str,
    state_path: Path | str,
) -> dict[str, Any]:
    """Report what the unit of work's own commit actually carried.

    Read-only by construction: reads git, the sink and the state, writes
    none of them. Publication is OBSERVED (INF-700a-5-i): an entry counts as
    written only when *commit_status* is ``ok`` AND HEAD's copy of its
    destination contains its text -- never on the commit agent's word alone.
    """
    working_dir = Path(working_dir).resolve()
    confirmed = _state.load_state_set(Path(state_path))
    reason = _REASON_BY_COMMIT_STATUS.get(commit_status, "stopped_before_publication")
    carried: list[str] = []
    unwritten_records = [
        {**r, "eligible": True} for r in run.get("unwritten_records", [])
    ]
    for entry in run.get("entries", []):
        if commit_status == "ok" and _git.text_on_ref(
            working_dir, "HEAD", entry["destination"], entry["text"]
        ):
            carried.append(entry["destination"])
            continue
        unwritten_records.append({
            "destination": entry["destination"],
            "text": entry["text"],
            "reason": reason,
            "eligible": entry.get("record_id") not in confirmed,
        })
    backlog = emission_backlog(sink_path=sink_path, read_hashes=run.get("read_hashes", []))
    not_carried = len(run.get("entries", [])) - len(carried)
    return {
        "case": run.get("case", "did_not_run"),
        "read": run.get("read", 0),
        "written": len(carried),
        "unwritten": run.get("unwritten", 0) + not_carried,
        "manifest": sorted(set(carried)),
        "unwritten_records": unwritten_records,
        "waiting": {
            "present": backlog["present"],
            "read": backlog["read"],
            "difference": backlog["difference"],
            "records": backlog["waiting"],
            "note": WAITING_NOTE,
        },
        "detail": run.get("detail"),
    }


def confirm_routed(*, state_path: Path | str, record_ids: list[str]) -> None:
    """Persist *record_ids* as durably routed.

    Only for callers that have themselves seen the records' text reach the
    merged tree. Fails open: a persist failure is logged by
    ``persist_state_set`` and the records stay unconfirmed (retried later).
    """
    if not record_ids:
        return
    state_path = Path(state_path)
    try:
        current = _state.load_state_set(state_path)
        _state.persist_state_set(state_path, current | set(record_ids))
    except OSError as exc:
        logger.warning("Routed marks not persisted (records stay eligible): %s", exc)


def unconfirmed_writes_report(
    *,
    working_dir: Path | str,
    install_root: Path | str,
    manifest: list[str],
    record_ids: list[str],
    state_path: Path | str,
) -> list[dict[str, Any]]:
    """Name every staged write whose text is absent from *install_root*.

    Read-only: consults *state_path* but never mutates it (INF-700a-5-i).
    Each entry carries the destination relative to *working_dir*, the
    still-unpublished text, and whether the record is still eligible.
    """
    working_dir = Path(working_dir)
    install_root = Path(install_root)
    confirmed = _state.load_state_set(Path(state_path))

    report: list[dict[str, Any]] = []
    for path_str, record_id in zip(manifest, record_ids):
        abs_path = Path(path_str)
        if not abs_path.is_absolute():
            abs_path = working_dir / abs_path
        try:
            rel_path = abs_path.relative_to(working_dir)
        except ValueError:
            rel_path = Path(abs_path.name)
        working_content = _state.read_text_or_empty(abs_path)
        install_content = _state.read_text_or_empty(install_root / rel_path)
        if working_content == install_content:
            continue
        appended = working_content
        if install_content and working_content.startswith(install_content):
            appended = working_content[len(install_content):]
        report.append({
            "destination": rel_path.as_posix(),
            "text": appended.strip("\n"),
            "eligible": record_id not in confirmed,
        })
    return report


def emission_backlog(
    *, sink_path: Path | str, read_hashes: set[str] | list[str]
) -> dict[str, Any]:
    """Count the eligible sink records a routing step's read set missed.

    Read-only (INF-700a-5-ii: the late look "must count, not drain"). Every
    eligible record whose hash is not in *read_hashes* is named as waiting.
    """
    read_hashes = set(read_hashes)
    records = _state.read_eligible_sink_records(Path(sink_path))
    waiting = [
        {"text": text, "destination": destination}
        for record_hash, text, destination in records
        if record_hash not in read_hashes
    ]
    return {
        "present": len(records),
        "read": len(records) - len(waiting),
        "difference": len(waiting),
        "waiting": waiting,
    }


def waiting_learnings(*, sink_path: Path | str, state_path: Path | str) -> dict[str, Any]:
    """Name every sink record not yet confirmed routed: INF-700a-5-ii's
    findable-by-asking answer, for someone with no completion run in hand.

    Read-only by construction: creates and writes nothing. The count is the
    harvester's own waiting figure (eligible records absent from the state
    set), not a second counter. A sink that exists but cannot be read is
    ``unknown`` (``waiting`` is ``None``), never a fabricated zero.
    """
    sink_path = Path(sink_path)
    if sink_path.exists():
        try:
            with sink_path.open("rb"):
                pass
        except OSError as exc:
            logger.warning("Cannot read knowledge sink %s: %s", sink_path, exc)
            return {"case": "unknown", "waiting": None, "records": [], "note": str(exc)}
    confirmed = _state.load_state_set(Path(state_path))
    records = [
        {"text": text, "destination": destination}
        for record_hash, text, destination in _state.read_eligible_sink_records(sink_path)
        if record_hash not in confirmed
    ]
    return {"case": "ok", "waiting": len(records), "records": records, "note": WAITING_NOTE}


def claim_and_confirm_routed(
    *,
    state_path: Path | str,
    record_ids: list[str],
    lock_path: Path | str | None = None,
    arbitration_enabled: bool = True,
) -> list[str]:
    """Atomically merge *record_ids* into the bookkeeping at *state_path*.

    Returns only the subset THIS call newly claimed. Arbitrates via an
    ``flock``'d lock file held for the state update alone (INF-700a-5-iii:
    nothing held across a dispatch, commit or publication).
    ``arbitration_enabled=False`` is the reachability off switch
    INF-700a-5-iii requires. Fails toward the duplicate: an unopenable lock
    degrades to the unarbitrated path rather than skipping the claim.
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
            "Could not open routing lock %s (%s); proceeding without arbitration.",
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
# - 2026-09-21 [python-coder]: Created for the INF-700a-5 family's durability
#   contract: staging split from confirmation, a read-only unpublished-write
#   report, a read-only late-emission recount, and flock-arbitrated claims
#   with an explicit off switch. (#TICKETLESS reason=ac-scoped-fastlane-build-INF-700a-5)
# - 2026-10-08 [python-coder/INF-700a-5 wiring]: The module had no caller and
#   was a parallel writer rather than a driver of the harvester. Per
#   BrainCandy's answers: stage_completion now DRIVES harvest_learnings.harvest()
#   (entry_kind normalisation, unroutable retention and the outstanding count
#   are the harvester's) with its writes redirected into working_dir and its
#   state write held back; the confirmation rule is check-the-base-branch
#   (claim only records whose text is already on origin/main, stage the rest
#   again); a destination whose change would conflict with the base branch is
#   left out and reported, so a routing write never blocks the work's own
#   publication; observe_publication added -- it asks git what HEAD carries
#   rather than trusting the commit agent. Each staged entry carries its
#   destination relative to working_dir (what the CLI hands the commit phase
#   to stage by name); the library manifest stays absolute. The CLI the
#   workflows call is completion_routing_cli.py.
#   (#INF-700a-5, #INF-700a-5-i)
