"""
MODULE: scripts/build_orchestration/_fl_heavy_lane_gate.py
GOAL: heavy_lane_gate -- a thin wrapper around fast_lane.verify_red_baseline
    for TQ-500f-3-ii's heavy-lane (/build-feature, /build-ticket) red-baseline
    gate, which also records its own pass on the ticket and reuses it.
BUSINESS CONTEXT: The first cut of TQ-500f-3-ii put the gate's decision logic
    (parsing gate_passed/reason, building halt payloads) inline in
    templates/workflows-js/build-feature.js and build-ticket.js's own
    driveTicketPhases. Both files were already over the JS file-size ratchet
    limit, and that inline logic grew them further. This module moves the
    decision logic OUT of both JS drivers and INTO one fast_lane.py CLI
    subcommand (heavy_lane_gate) instead, so each JS driver keeps only a thin
    dispatch + fail-closed parse of the single JSON object this subcommand
    prints -- see unit_tests/build_orchestration/
    test_tq500f3ii_heavy_lane_gate_subcommand.py for the pinned contract.
    A resumed ticket whose coder already ran would see its new tests green and
    be halted as "green at baseline"; the recorded pass prevents that.
ARCHITECTURE: heavy_lane_gate itself lives in this SIBLING module rather than
    in fast_lane.py: fast_lane.py measured 404 counted content lines (over
    the 400-line check-file-size limit) with this function defined inline,
    so it moved here to keep fast_lane.py under the limit. It imports
    verify_red_baseline via a LOCAL (function-body) import of the fast_lane
    module itself -- never a top-level one -- because fast_lane.py imports
    THIS module's public name (heavy_lane_gate) at ITS OWN top level (for the
    CLI dispatch in main()); a top-level `from fast_lane import
    verify_red_baseline` here would create an import cycle. This is the same
    local-import pattern done_proof.py's own docstring documents for its
    sibling _done_proof_phase_helpers.py relocation, applied for the same
    reason. "No second reader" (TQ-500f-3-ii's own constraint): this module
    calls verify_red_baseline directly and returns its verdict dict
    unchanged plus the HEAVY_WRAPPER_KEYS wrapper keys -- it never
    re-implements the absence/assertion classification itself.
    RECORD AND REUSE (F2): on a pass the wrapper writes one
    ``red_baseline_gate`` frontmatter line into the ticket; a later run
    reuses it (no pytest) when the source_ac matches and every recorded red
    (file, function) is still among the newly added covers-tagged tests.
    The shared reader is untouched, so both lanes judge identically.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

from _fl_common import _LOG, _scan_test_root_for_covers_tags
from _fl_red_baseline_support import (
    _partition_newly_added,
    _resolve_git_baseline_context,
    _run_git_in,
    _RedBaselineGitError,
)

# Every key the wrapper may ADD to the shared reader's verdict. Both lane-parity
# seam tests strip exactly this set before comparing a heavy verdict with the
# fast-lane verdict. ``interpreter`` is NOT here: the reader emits it.
HEAVY_WRAPPER_KEYS: frozenset[str] = frozenset(
    {
        "applicable", "verified", "outcome", "reused", "recorded",
        "record_error", "recorded_at", "head", "halt_classification", "remedy",
    }
)

_RECORD_KEY = "red_baseline_gate"
_RECORD_PREFIX = f"{_RECORD_KEY}:"
_FENCE = "---"
_REUSE_ERRORS = (_RedBaselineGitError, OSError, ValueError, KeyError, TypeError)
_WRITE_ERRORS = (_RedBaselineGitError, OSError, ValueError, KeyError, yaml.YAMLError)


def _bare(line: str) -> str:
    """Return *line* without its line ending."""
    return line.rstrip("\r\n")


def _frontmatter_close(lines: list[str]) -> int:
    """Index of the closing ``---`` line of the frontmatter block.

    Raises:
        ValueError: The text has no frontmatter or no closing fence.
    """
    if not lines or _bare(lines[0]) != _FENCE:
        raise ValueError("ticket has no frontmatter block")
    for index in range(1, len(lines)):
        if _bare(lines[index]) == _FENCE:
            return index
    raise ValueError("ticket frontmatter has no closing ---")


def _record_indexes(lines: list[str], close: int) -> list[int]:
    """Indexes of column-0 ``red_baseline_gate:`` lines inside the frontmatter."""
    return [i for i in range(1, close) if lines[i].startswith(_RECORD_PREFIX)]


def _read_ticket_lines(ticket: Path) -> list[str]:
    """Read *ticket* keeping each line's own ending (``newline=""``)."""
    with ticket.open(encoding="utf-8", newline="") as handle:
        return handle.read().splitlines(keepends=True)


def _read_record(ticket: Path | None) -> tuple[bool, dict | None]:
    """Return ``(record_line_exists, parsed_record_or_None)`` for *ticket*.

    An unreadable ticket, malformed frontmatter, duplicate line or non-mapping
    value yields ``None`` as the record: nothing is guessed.
    """
    if ticket is None or not ticket.is_file():
        return False, None
    try:
        lines = _read_ticket_lines(ticket)
        indexes = _record_indexes(lines, _frontmatter_close(lines))
        if not indexes:
            return False, None
        value = yaml.safe_load(_bare(lines[indexes[0]])[len(_RECORD_PREFIX):])
    except (OSError, ValueError, yaml.YAMLError) as exc:
        _LOG.warning("heavy_lane_gate: unreadable %s record on %s: %s", _RECORD_KEY, ticket, exc)
        return True, None
    if len(indexes) != 1 or not isinstance(value, dict):
        return True, None
    return True, value


def _atomic_write(target: Path, text: str) -> None:
    """Replace *target* with *text* via a same-directory temp file and os.replace.

    Same pattern as ``mark_ac_done._atomic_write``: ``newline=""`` so no line
    ending is translated; *target* is never truncated and is unchanged on error.
    """
    fd, tmp_name = tempfile.mkstemp(
        dir=str(target.parent), prefix=f".{target.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.replace(tmp_name, target)
    except OSError:
        try:
            os.unlink(tmp_name)
        except OSError as cleanup_exc:
            print(f"WARNING: could not remove temp file {tmp_name}: {cleanup_exc}", file=sys.stderr)
        raise


def _write_record_line(ticket: Path, record: dict) -> None:
    """Write the one-line record into *ticket*'s frontmatter and verify it.

    Replaces the single column-0 ``red_baseline_gate:`` line or inserts one
    before the closing ``---``; no other byte changes.

    Raises:
        ValueError: No frontmatter / closing fence, several record lines, or
            the re-parse does not read the record back.
        OSError: The write failed.
    """
    lines = _read_ticket_lines(ticket)
    close = _frontmatter_close(lines)
    indexes = _record_indexes(lines, close)
    if len(indexes) > 1:
        raise ValueError(f"ticket has {len(indexes)} {_RECORD_KEY} lines; refusing to guess")
    slot = indexes[0] if indexes else close
    eol = lines[slot][len(_bare(lines[slot])):] or "\n"
    new_line = f"{_RECORD_PREFIX} {json.dumps(record)}{eol}"
    if indexes:
        lines[slot] = new_line
    else:
        lines.insert(close, new_line)
    _atomic_write(ticket, "".join(lines))
    lines = _read_ticket_lines(ticket)
    front = yaml.safe_load("".join(lines[1:_frontmatter_close(lines)]))
    if not isinstance(front, dict) or front.get(_RECORD_KEY) != record:
        raise ValueError(f"{_RECORD_KEY} did not read back after writing")


def _newly_added_tags(test_root: Path, ids: list[str]) -> tuple[Path, list[dict]]:
    """Covers-tagged, newly added tests for *ids*: ``(repo_root, tags)``.

    Raises:
        _RedBaselineGitError: The git partition could not be resolved.
    """
    wanted = set(ids)
    linked = [t for t in _scan_test_root_for_covers_tags(test_root) if t["ac_id"] in wanted]
    repo_root, base_ref = _resolve_git_baseline_context(test_root, None)
    added, _preexisting = _partition_newly_added(linked, repo_root, base_ref)
    return repo_root, added


def _identity(tag: dict, repo_root: Path) -> tuple[str, str]:
    """``(repo-relative POSIX file, function)`` identity of a covers tag."""
    return Path(tag["file"]).resolve().relative_to(repo_root).as_posix(), tag["function"]


def _record_reusable(record: dict, ids: list[str], test_root: Path) -> bool:
    """True iff *record* may stand in for the reader (all conditions hold).

    The record must say passed, carry the same source_ac ids, list at least
    one red, and every recorded red (file, function) must still be among the
    newly added covers-tagged tests. A git or partition failure is "no reuse".
    """
    red = record.get("red")
    if record.get("passed") is not True or not isinstance(red, list) or not red:
        return False
    if sorted(map(str, record.get("source_ac") or [])) != sorted(ids):
        return False
    try:
        repo_root, added = _newly_added_tags(test_root, ids)
        present = {_identity(tag, repo_root) for tag in added}
        return all((r["file"], r["function"]) in present for r in red)
    except _REUSE_ERRORS as exc:
        _LOG.warning("heavy_lane_gate: record not reusable, running the reader: %s", exc)
        return False


def _reused_verdict(record: dict) -> dict:
    """Pass verdict for a reused record; names ``recorded_at`` and ``head``."""
    stamp, head = record.get("recorded_at"), record.get("head")
    return {
        "gate_passed": True,
        "reason": None,
        "interpreter": sys.executable,
        "applicable": True,
        "verified": True,
        "reused": True,
        "recorded_at": stamp,
        "head": head,
        "outcome": (
            f"red-baseline gate reused the record from {stamp} (head {head}): "
            "no pytest run; every recorded red test is still newly added"
        ),
    }


def _red_identities(verdict: dict, test_root: Path, ids: list[str]) -> list[dict]:
    """Map the reader's red nodeids to ``{file, function}`` from the covers tags."""
    repo_root, added = _newly_added_tags(test_root, ids)
    out: list[dict] = []
    for entry in verdict.get("red") or []:
        path, _, func = str(entry["nodeid"]).replace("\\", "/").rpartition("::")
        func = func.split("[")[0]
        base = Path(path.split("::")[0]).name
        for tag in added:
            file_rel, name = _identity(tag, repo_root)
            item = {"file": file_rel, "function": name}
            if name == func and Path(file_rel).name == base and item not in out:
                out.append(item)
    return out


def _unrecorded(error: str) -> dict:
    """Keys for a pass that could not be recorded; the pass itself stands."""
    return {
        "recorded": False,
        "record_error": error,
        "outcome": (
            f"verify_red_baseline gate passed but NOT recorded ({error}); "
            "a resumed run re-runs the reader and may then see green tests"
        ),
    }


def _record_pass(verdict: dict, ids: list[str], test_root: Path, ticket: Path | None) -> dict:
    """Write the pass record; return ``{recorded: True}`` or the error keys."""
    if ticket is None or not ticket.is_file():
        return _unrecorded("no ticket given" if ticket is None else f"ticket not found: {ticket}")
    try:
        red = _red_identities(verdict, test_root, ids)
        if not red:
            raise ValueError("could not map the red tests to covers-tagged functions")
        record = {
            "passed": True,
            "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "head": _run_git_in(test_root, ["rev-parse", "HEAD"]).strip(),
            "source_ac": ids,
            "red": red,
        }
        _write_record_line(ticket, record)
    except _WRITE_ERRORS as exc:
        return _unrecorded(str(exc))
    return {"recorded": True}


def _green_remedy(verdict: dict, had_record: bool) -> str:
    """The operator remedy for an all-green (green_at_baseline) refusal."""
    greens = verdict.get("green_at_baseline") or []
    names = ", ".join(str(e.get("nodeid", "")).rpartition("::")[2] for e in greens)
    text = (
        f"All newly added tests are already green: {names}. If the behaviour already "
        "exists, set the coder phase to not_needed in the ticket frontmatter and add a "
        "comment naming the commit that delivered it, then resume. Nothing was changed."
    )
    if had_record:
        text += (
            " The ticket has a red_baseline_gate record that was not reused (a recorded "
            "test was renamed or removed, or the source_ac changed); fix the tests rather "
            "than skipping the coder."
        )
    return text


def heavy_lane_gate(
    *,
    source_ac_ids: list[str],
    test_root: Path,
    ac_root: Path,
    ticket: Path | None = None,
) -> dict:
    """Wrap verify_red_baseline for the heavy lane, recording and reusing a pass.

    A ticket with no source requirement has nothing to gate against and
    always passes (``applicable`` False; the verdict carries ``interpreter``).
    Otherwise a valid ``red_baseline_gate`` record on *ticket* is reused
    without running pytest (``reused`` True); else ``fast_lane.verify_red_baseline``
    runs and its verdict is returned plus wrapper keys (HEAVY_WRAPPER_KEYS).
    A pass is recorded on the ticket (``recorded``; on failure ``recorded``
    False with ``record_error``, and the pass stands). An all-green refusal gets
    ``halt_classification`` ``green_at_baseline`` and a ``remedy``. Reuse and
    failed runs never rewrite the ticket.

    Args:
        source_ac_ids: The ticket's source_ac id(s); empty means "not applicable".
        test_root: Root directory to scan for covering tests.
        ac_root: Root directory of the AC YAML store.
        ticket: Ticket file for the record; a relative path resolves against
            *test_root*. ``None`` means nothing can be recorded.

    Returns:
        ``{"gate_passed": bool, "applicable": bool, "verified": bool, ...}``.
    """
    if not source_ac_ids:
        return {
            "gate_passed": True,
            "applicable": False,
            "verified": False,
            "outcome": "red-baseline reader not applicable: no source requirement",
            "interpreter": sys.executable,
        }
    from fast_lane import verify_red_baseline

    if ticket is not None and not ticket.is_absolute():
        ticket = test_root / ticket
    had_record, record = _read_record(ticket)
    if record is not None and _record_reusable(record, source_ac_ids, test_root):
        return _reused_verdict(record)
    verdict = verify_red_baseline(
        ac_ids=source_ac_ids, test_root=test_root, ac_root=ac_root
    )
    result = dict(verdict)
    result["applicable"] = True
    result["verified"] = bool(verdict.get("gate_passed"))
    if result["verified"]:
        result.update(_record_pass(verdict, source_ac_ids, test_root, ticket))
    elif verdict.get("reason") == "all_new_tests_green_at_baseline":
        result["halt_classification"] = "green_at_baseline"
        result["remedy"] = _green_remedy(verdict, had_record)
    return result


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-27 [python-coder/TQ-500f-3-ii]: New sibling module. Moved out of
#   fast_lane.py (which measured 404 counted content lines with this function
#   defined inline, over the 400-line check-file-size limit) to keep that
#   module under its size cap. See the module ARCHITECTURE note above for the
#   local-import rationale.
# - 2026-10-06 [python-coder/review M-1]: The not-applicable verdict now carries
#   ``interpreter`` (sys.executable) so every heavy_lane_gate verdict names the
#   interpreter that ran it. Applicable verdicts already get it from the shared
#   reader; it is deliberately not a wrapper-only key.
# - 2026-10-06 [python-coder/TQ-500f-3-ii F2+F3]: Record and reuse. A pass writes
#   one anchored, atomically replaced ``red_baseline_gate`` ticket line; a later
#   run reuses it with no pytest when source_ac matches and every recorded red
#   (file, function) is still newly added (subset check; a git or partition
#   failure means "run the reader"). All-green refusals gain
#   ``halt_classification`` and ``remedy`` (F3 option A; the name avoids the
#   reader's own list key ``green_at_baseline``). HEAVY_WRAPPER_KEYS is the one
#   wrapper-only key set for both lane-parity seam tests. The reader is unchanged.
# ====================================================================
