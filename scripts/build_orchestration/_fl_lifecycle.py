"""
MODULE: scripts/build_orchestration/_fl_lifecycle.py
GOAL: AC work_status lifecycle functions for the fast-lane build pipeline.
BUSINESS CONTEXT: BO-2400f-7 through BO-2400f-10 — claim (todo->in_progress),
    release (in_progress->todo on failure), and mark-done (in_progress->done
    on success) status-only mutations of the AC YAML store, plus the
    stale-todo guard that verifies a passing run left every built AC done.
    Extracted verbatim from fast_lane.py (NO behaviour change) as part of the
    2026-09-14 file-size split — see fast_lane.py's own DECISION HISTORY and
    _fl_common.py's ARCHITECTURE note for the full record of the split.
ARCHITECTURE: All file I/O is wrapped per the Error Handling Policy (Rule 1).
    _update_ac_work_status commits its edit via _atomic_write_text
    (BO-2400e-3), a write-to-temp-in-the-same-directory then os.replace so a
    reader always sees either the whole old or whole new content and an
    interrupted/failed write never truncates the on-disk record. Imported
    into fast_lane.py's namespace for CLI dispatch and re-exported so every
    name previously importable from fast_lane (claim_build_set,
    release_claim, filter_already_claimed, mark_done_built_acs,
    check_no_stale_todo, _update_ac_work_status) remains importable from
    fast_lane.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import yaml

from _fl_common import _LOG, _load_ac, _walk_ac_yamls

# ---------------------------------------------------------------------------
# Lifecycle helpers (BO-2400f-7 through BO-2400f-10)
# ---------------------------------------------------------------------------


def _build_ac_id_to_path_index(ac_root: Path) -> dict[str, Path]:
    """Scan *ac_root* once and return a mapping from AC id to YAML file path.

    A single-pass scan so callers that process multiple ACs avoid repeated full
    store walks.  Uses _load_ac for YAML parsing and error reporting; the
    ``_path`` metadata injected by _load_ac is used to resolve the file path
    rather than being forwarded to any re-dump.

    Args:
        ac_root: Root directory of the AC YAML store.

    Returns:
        Dict mapping AC id strings to their on-disk :class:`pathlib.Path`
        objects.  Returns ``{}`` when *ac_root* does not exist.
    """
    if not ac_root.exists():
        return {}
    index: dict[str, Path] = {}
    for yaml_path in _walk_ac_yamls(ac_root):
        record = _load_ac(yaml_path)
        if record is not None:
            ac_id = record.get("id")
            if ac_id:
                index[str(ac_id)] = yaml_path
    return index


def _atomic_write_text(target_path: Path, text: str) -> None:
    """Replace *target_path*'s content with *text* atomically from a reader's
    point of view (BO-2400e-3 / BO-2400e-3-i).

    The previous implementation opened *target_path* with ``"w"``, which
    TRUNCATES the file to zero bytes the instant it is opened — before a
    single byte of the new content has been written. Any failure after that
    point (a write that fails partway, a process interruption) left the
    on-disk record empty or short: real data loss on the build system's
    source of truth.

    This instead writes the new content to a temp file created in the SAME
    directory as *target_path* (so the final swap is a same-filesystem
    rename), then calls :func:`os.replace` to atomically swap it into place.
    ``os.replace`` is a single filesystem rename operation — a concurrent
    reader opening *target_path* at any point sees either the complete OLD
    content or the complete NEW content, never a partial mixture, and the
    ORIGINAL file is never truncated or otherwise touched by a write that
    later fails. This is the single extra filesystem metadata operation
    (the rename) added to the read/write pair the function already performed.

    On any failure — creating the temp file, writing to it, or the final
    rename — the temp file is removed on a best-effort basis (a cleanup
    failure is logged, never allowed to mask or replace the original error)
    and the triggering ``OSError`` is re-raised. The caller MUST NOT treat a
    caught-and-logged failure here as anything but a failed write (per this
    repo's Error Handling Policy Rule 3: "log at WARNING and return" is not
    an acceptable substitute for propagating the failure) — *target_path* is
    guaranteed unchanged whenever this raises.

    Args:
        target_path: Absolute path of the file to replace.
        text: Full new file content.

    Raises:
        OSError: The temp file could not be created, written, or renamed
            into place (e.g. a read-only directory/file, or a write that
            fails partway through, such as under ``RLIMIT_FSIZE``).
    """
    tmp_fd: int | None = None
    tmp_name: str | None = None
    try:
        tmp_fd, tmp_name = tempfile.mkstemp(
            dir=str(target_path.parent),
            prefix=f".{target_path.name}.",
            suffix=".tmp",
        )
        with os.fdopen(tmp_fd, "w", encoding="utf-8", newline="") as fh:
            tmp_fd = None  # ownership transferred to the context manager
            fh.write(text)
        os.replace(tmp_name, target_path)
        tmp_name = None  # swapped into place -- nothing left to clean up
    except OSError as exc:
        _LOG.warning("_atomic_write_text: cannot write %s: %s", target_path, exc)
        raise
    finally:
        if tmp_fd is not None:
            try:
                os.close(tmp_fd)
            except OSError as cleanup_exc:
                _LOG.warning(
                    "_atomic_write_text: failed to close leaked temp fd for %s: %s",
                    target_path,
                    cleanup_exc,
                )
        if tmp_name is not None:
            try:
                os.unlink(tmp_name)
            except OSError as cleanup_exc:
                _LOG.warning(
                    "_atomic_write_text: failed to remove temp file %s for %s: %s",
                    tmp_name,
                    target_path,
                    cleanup_exc,
                )


def _line_ending_suffix(line: str) -> str:
    """Return the exact trailing line-ending bytes of *line*.

    BO-2400e-4 / KI-BO-022: a targeted single-line text edit must reproduce
    the file's own line-ending convention on the rewritten line, not
    Python's default ``"\\n"``. A CRLF-encoded record's ``work_status:``
    line must be rewritten with a trailing ``"\\r\\n"``, not downgraded to a
    bare ``"\\n"`` — otherwise the "only the value changes" criterion is
    violated on the byte level even when the read/write pair otherwise
    preserves every other line untouched.

    Args:
        line: A single line, possibly including its trailing newline
            sequence (as produced by ``str.splitlines(keepends=True)``).

    Returns:
        ``"\\r\\n"``, ``"\\n"``, ``"\\r"``, or ``""`` when *line* has no
        trailing line-ending sequence at all (e.g. the file's last line).
    """
    if line.endswith("\r\n"):
        return "\r\n"
    if line.endswith("\n"):
        return "\n"
    if line.endswith("\r"):
        return "\r"
    return ""


def _update_ac_work_status(yaml_path: Path, new_status: str) -> None:
    """Overwrite only the *work_status* line of an AC YAML file on disk.

    KI-BO-003 fix: this used to round-trip the whole document through
    ``yaml.safe_load`` -> ``yaml.safe_dump``, which is true of VALUES but
    false of FORMATTING — it alphabetises every top-level key, reflows
    hand-authored ``criteria: |`` / ``notes: |`` block scalars into
    folded/quoted strings, and drops comments (a one-field change produced a
    161-line diff on a real AC file). This instead performs a targeted text
    edit of exactly the column-0 ``work_status:`` line, so every other byte
    of the file — formatting, comments, and key order — is preserved
    byte-identically; only the value on that one line changes.

    The match is anchored at column 0 (start of line, no leading
    whitespace) so an indented occurrence of the literal string
    ``work_status`` inside a block-scalar's prose (e.g. an ``amended_by``
    reason narrating "Reset to work_status todo:") is never mistaken for the
    real key.

    BO-2400e-3: the new bytes reach disk via :func:`_atomic_write_text`
    rather than a truncating ``open("w")``, so an interrupted or partially
    failed write can never leave the record zero-length or half-written —
    the targeted single-line text edit above is unchanged; only how the
    resulting bytes are committed to disk changed.

    Args:
        yaml_path: Absolute path to the AC YAML file.
        new_status: Target work_status value — ``"in_progress"``, ``"todo"``,
            or ``"done"``.

    Raises:
        OSError: When the file cannot be read, or the new content cannot be
            written and swapped into place (BO-2400e-3-i: the original file
            is guaranteed unchanged whenever this is raised — the caller
            must treat it as a failed update and MUST NOT proceed as though
            the status had been recorded).
        ValueError: When the file contains more than one column-0
            ``work_status:`` line. Which of them is the real key is genuinely
            ambiguous, so this raises rather than editing the first and
            leaving a contradictory record behind. Zero matches is NOT an
            error: the key is created (see below).

    A file with no ``work_status:`` line gains one, appended as a single new
    line. That is not a guess — satisfying the contract "work_status is now
    *new_status*" has exactly one meaning when the line is missing — and it
    matches what the pre-KI-BO-003 round-trip did. 143 of the 3012 real ACs
    in this repo's store have no such key, so refusing them would crash the
    fast lane on 4.7% of the store.
    """
    try:
        with yaml_path.open(encoding="utf-8", newline="") as fh:
            original = fh.read()
    except OSError as exc:
        _LOG.warning("_update_ac_work_status: cannot read %s: %s", yaml_path, exc)
        raise

    lines = original.splitlines(keepends=True)
    match_indices = [
        i for i, line in enumerate(lines) if line.startswith("work_status:")
    ]
    if len(match_indices) > 1:
        msg = (
            f"_update_ac_work_status: expected at most one column-0 "
            f"'work_status:' line in {yaml_path}, found {len(match_indices)}"
        )
        raise ValueError(msg)

    if match_indices:
        index = match_indices[0]
        newline_suffix = _line_ending_suffix(lines[index])
        lines[index] = f"work_status: {new_status}{newline_suffix}"
    else:
        # Key absent: create it. This is not a guess — the function's whole
        # contract is "work_status is now *new_status*", and appending is the
        # single way to satisfy it when no such line exists. 143 of the 3012
        # real ACs in this repo's store carry no work_status (the /quick-fix
        # authored records, e.g. ACD-1400); the pre-KI-BO-003 round-trip added
        # the key silently, so refusing here would crash the lane on 4.7% of
        # the store. Appending keeps the edit minimal — one added line, every
        # existing byte untouched.
        file_ending = next(
            (_line_ending_suffix(line) for line in lines if _line_ending_suffix(line)),
            "\n",
        )
        if lines and not _line_ending_suffix(lines[-1]):
            lines[-1] = lines[-1] + file_ending
        lines.append(f"work_status: {new_status}{file_ending}")
    updated = "".join(lines)

    _atomic_write_text(yaml_path, updated)


def claim_build_set(
    ac_ids: list[str],
    *,
    ac_root: Path,
) -> dict:
    """Flip every AC in *ac_ids* whose work_status is todo to in_progress.

    Status-only change — only the work_status field is modified in the AC YAML
    store.  ACs already in_progress are reported via ``error`` but are not
    double-counted.  Any I/O failure returns ``success=False`` so the caller
    can halt before dispatching test-writer or coder (BO-2400f-7-i).

    Args:
        ac_ids: Ordered list of AC ids whose work_status to flip todo →
            in_progress.
        ac_root: Root directory of the AC YAML store.

    Returns:
        Dict with keys:

        ``claimed`` (list[str])
            AC ids actually flipped todo → in_progress.

        ``success`` (bool)
            True when every target todo AC was claimed without error.

        ``error`` (str | None)
            Human-readable error when success is False; None on success.

        ``named_acs`` (list[str])
            All AC ids the call attempted to claim (always equals *ac_ids*).
    """
    id_to_path = _build_ac_id_to_path_index(ac_root)
    claimed: list[str] = []
    named_acs: list[str] = list(ac_ids)
    error: str | None = None

    for ac_id in ac_ids:
        yaml_path = id_to_path.get(ac_id)
        if yaml_path is None:
            error = (
                f"AC {ac_id!r} not found in store at {ac_root}; "
                f"named_acs: {named_acs}"
            )
            return {
                "claimed": claimed,
                "success": False,
                "error": error,
                "named_acs": named_acs,
            }

        try:
            with yaml_path.open(encoding="utf-8") as fh:
                record = yaml.safe_load(fh)
        except OSError as exc:
            _LOG.warning("claim_build_set: cannot read %s: %s", yaml_path, exc)
            error = f"Cannot read {ac_id!r} from {yaml_path}: {exc}"
            return {
                "claimed": claimed,
                "success": False,
                "error": error,
                "named_acs": named_acs,
            }

        current_status = record.get("work_status", "")
        if current_status == "in_progress":
            # Already claimed by another run — note but do not double-flip.
            if error is None:
                error = (
                    f"AC {ac_id!r} is already in_progress (claimed by "
                    f"another run); named_acs: {named_acs}"
                )
            continue

        try:
            _update_ac_work_status(yaml_path, "in_progress")
        except OSError as exc:
            error = f"Failed to claim {ac_id!r}: {exc}; named_acs: {named_acs}"
            return {
                "claimed": claimed,
                "success": False,
                "error": error,
                "named_acs": named_acs,
            }

        claimed.append(ac_id)

    success = error is None
    return {
        "claimed": claimed,
        "success": success,
        "error": error,
        "named_acs": named_acs,
    }


def release_claim(
    claimed_ids: list[str],
    done_ids: list[str],
    *,
    ac_root: Path,
) -> dict:
    """Release claimed-but-not-done ACs back to work_status: todo.

    Called on a non-success run exit so no AC is permanently stuck in
    in_progress blocking future runs (BO-2400f-10).  Status-only change —
    only work_status is modified.

    Args:
        claimed_ids: IDs this run flipped to in_progress at start.
        done_ids: IDs that were successfully transitioned to done.
        ac_root: Root directory of the AC YAML store.

    Returns:
        Dict with key:

        ``released`` (list[str])
            AC ids that were released back to todo.
    """
    done_set = set(done_ids)
    id_to_path = _build_ac_id_to_path_index(ac_root)
    released: list[str] = []

    for ac_id in claimed_ids:
        if ac_id in done_set:
            continue  # Already done — do not regress its status.

        yaml_path = id_to_path.get(ac_id)
        if yaml_path is None:
            _LOG.warning("release_claim: AC %r not found in store at %s", ac_id, ac_root)
            continue

        try:
            _update_ac_work_status(yaml_path, "todo")
        except OSError as exc:
            _LOG.warning("release_claim: failed to release %s: %s", ac_id, exc)
            continue

        released.append(ac_id)

    return {"released": released}


def filter_already_claimed(
    build_set: list[str],
    *,
    ac_root: Path,
) -> dict:
    """Partition *build_set* into ACs free to build and those already claimed.

    Reads each AC's current work_status from disk.  ACs with work_status todo
    are free to build.  ACs with work_status in_progress are treated as claimed
    by another in-flight run and must never be rebuilt (BO-2400f-8).

    Args:
        build_set: Resolved connected build set as a list of AC ids.
        ac_root: Root directory of the AC YAML store.

    Returns:
        Dict with keys:

        ``to_build`` (list[str])
            ACs with work_status todo — free to claim and build.

        ``excluded_claimed`` (list[str])
            ACs with work_status in_progress — already claimed by another run.

        ``target_refused`` (bool)
            True when *to_build* is empty and at least one AC was excluded —
            i.e. every member of *build_set* is already claimed so the run
            must refuse to proceed.
    """
    id_to_path = _build_ac_id_to_path_index(ac_root)
    to_build: list[str] = []
    excluded_claimed: list[str] = []

    for ac_id in build_set:
        yaml_path = id_to_path.get(ac_id)
        if yaml_path is None:
            # Unknown AC — treat as buildable (conservative; caller resolves).
            to_build.append(ac_id)
            continue

        try:
            with yaml_path.open(encoding="utf-8") as fh:
                record = yaml.safe_load(fh)
        except OSError as exc:
            _LOG.warning("filter_already_claimed: cannot read %s: %s", yaml_path, exc)
            to_build.append(ac_id)
            continue

        if record.get("work_status") == "in_progress":
            excluded_claimed.append(ac_id)
        else:
            to_build.append(ac_id)

    target_refused = len(to_build) == 0 and len(excluded_claimed) > 0
    return {
        "to_build": to_build,
        "excluded_claimed": excluded_claimed,
        "target_refused": target_refused,
    }


def mark_done_built_acs(
    built_ac_ids: list[str],
    covered_ac_ids: list[str],
    *,
    ac_root: Path,
) -> dict:
    """Flip each built AC whose coverage gate passed to work_status done.

    ACs in *built_ac_ids* but absent from *covered_ac_ids* are NOT flipped —
    their coverage gate did not pass (BO-2400f-9).  Status-only change.

    Args:
        built_ac_ids: All AC ids that were built in this run.
        covered_ac_ids: AC ids whose coverage gate passed (have a covering
            test that is green).
        ac_root: Root directory of the AC YAML store.

    Returns:
        Dict with keys:

        ``marked_done`` (list[str])
            AC ids that were flipped to work_status done.

        ``skipped_uncovered`` (list[str])
            AC ids in *built_ac_ids* that were NOT flipped because they were
            absent from *covered_ac_ids* or could not be written.
    """
    covered_set = set(covered_ac_ids)
    id_to_path = _build_ac_id_to_path_index(ac_root)
    marked_done: list[str] = []
    skipped_uncovered: list[str] = []

    for ac_id in built_ac_ids:
        if ac_id not in covered_set:
            skipped_uncovered.append(ac_id)
            continue

        yaml_path = id_to_path.get(ac_id)
        if yaml_path is None:
            _LOG.warning("mark_done_built_acs: AC %r not found in store at %s", ac_id, ac_root)
            skipped_uncovered.append(ac_id)
            continue

        try:
            _update_ac_work_status(yaml_path, "done")
        except OSError as exc:
            _LOG.warning("mark_done_built_acs: failed to mark %s done: %s", ac_id, exc)
            skipped_uncovered.append(ac_id)
            continue

        marked_done.append(ac_id)

    return {"marked_done": marked_done, "skipped_uncovered": skipped_uncovered}


def check_no_stale_todo(
    built_ac_ids: list[str],
    *,
    ac_root: Path,
) -> dict:
    """Verify that every AC in *built_ac_ids* has work_status done on disk.

    The stale-todo guard (BO-2400f-9-i): a passing run MUST leave every built
    AC as done.  Any AC still todo or in_progress after the finish-time
    transition is a stale-todo error that blocks the success result.

    Args:
        built_ac_ids: All AC ids that were built (and should now be done).
        ac_root: Root directory of the AC YAML store.

    Returns:
        Dict with keys:

        ``all_done`` (bool)
            True iff every AC in *built_ac_ids* has work_status done on disk.

        ``stale`` (list[str])
            AC ids still todo or in_progress after the finish transition.
    """
    id_to_path = _build_ac_id_to_path_index(ac_root)
    stale: list[str] = []

    for ac_id in built_ac_ids:
        yaml_path = id_to_path.get(ac_id)
        if yaml_path is None:
            stale.append(ac_id)
            continue

        try:
            with yaml_path.open(encoding="utf-8") as fh:
                record = yaml.safe_load(fh)
        except OSError as exc:
            _LOG.warning("check_no_stale_todo: cannot read %s: %s", yaml_path, exc)
            stale.append(ac_id)
            continue

        if record.get("work_status") != "done":
            stale.append(ac_id)

    return {"all_done": len(stale) == 0, "stale": stale}


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-18 18:00 [python-coder]: Replaced the yaml.safe_load ->
#   yaml.safe_dump round-trip in _update_ac_work_status with a targeted
#   single-line text edit of the column-0 `work_status:` line (KI-BO-003:
#   the round-trip was true of VALUES but false of FORMATTING -- it
#   alphabetised every top-level key, reflowed hand-authored `criteria: |`
#   / `notes: |` block scalars into folded/quoted strings, and dropped
#   comments, producing a 161-line diff for a one-field change on a real
#   AC file). The new implementation reads the file as text, finds the
#   line that starts with `work_status:` at column 0 (never an indented
#   occurrence of the same literal string inside block-scalar prose, e.g.
#   an `amended_by` reason narrating "Reset to work_status todo:"), and
#   raises ValueError rather than guessing when that line is absent or
#   appears more than once -- silently adding the key or silently editing
#   the first of several matches is exactly the failure class this fix
#   closes. Trailing-newline presence is preserved from the original
#   line. Docstring updated to name the byte/formatting/comment/key-order
#   guarantee actually tested, replacing the prior overclaim ("every
#   other field is preserved unchanged", true of values, false of
#   formatting). (#TICKETLESS reason=known-issue-fix-no-ticket-KI-BO-003)
# - 2026-08-18 19:15 [review correction]: The first cut of the above raised
#   ValueError on ZERO matches as well as on many. A real-artifact
#   spot-check over the whole store found 143 of 3012 AC files carry no
#   column-0 `work_status:` key at all (the /quick-fix authored records,
#   e.g. ACD-1400 — `status: active`, reachable by claim_build_set). The
#   round-trip being replaced added the key silently, so raising would have
#   converted a working path into a crash on 4.7% of the store — a
#   regression invisible to the unit suite, whose fixtures all happened to
#   have the field. Zero matches now APPENDS the key as one new line;
#   only the ambiguous many-matches case still raises. Covered by
#   TestWorkStatusKeyAbsent.
#   (#TICKETLESS reason=known-issue-fix-no-ticket-KI-BO-003)
# - 2026-09-14 [python-coder/refactor-fast-lane-size]: Extracted verbatim
#   from fast_lane.py (NO behaviour change) as part of the file-size split —
#   see fast_lane.py's own DECISION HISTORY for the full record.
#   (#TICKETLESS reason=fast-lane-file-size-split)
# ====================================================================
