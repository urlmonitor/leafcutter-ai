"""
MODULE: scripts/build_orchestration/_wvw_write.py
GOAL: The writer's ``write`` step: the preparer's reply becomes the alterations manifest
    (and the altered copies) under ``<git-dir>/leafcutter/work/<work-key>/``.
BUSINESS CONTEXT: TQ-500g-1-ix. The first filesystem action removes whatever an earlier
    preparation of the same work left, so an unreadable reply can never leave an old
    manifest to be read in its place. The manifest is written last, atomically, and holds
    exactly the owed names (derived from the test entries, never from the reply) built only
    from the writer's own values: name, status, reason, files and the computed diff.
ARCHITECTURE: Uses ``_wvw_list`` (owed names), ``_wvp_plan`` (pinned or prepared, TQ-500g-1-xi:
    a pinned name is rebuilt from its pinned replacements on the code as it now stands and the
    reply is never used for it), ``_wvw_reply`` (reply reading) and ``_wvw_prepare`` (replacements).
    Manifest entries also carry ``replacements``, ``alteration_id`` and ``source``. Nothing is written in the working tree and no git
    stash or commit is used. Deterministic: same reply, owed names and code give a
    byte-identical manifest and copies. Progress logging goes to stderr only.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import sys
from pathlib import Path

import _wvr_gate as gate_mod
import _wvw_reply as reply_mod
from _wvp_checks import Item, static_check
from _wvp_plan import Decision, plan_for_write
from _wvp_store import RE_PREPARED, PinError, alteration_id
from _wvp_store import plain_segment as _plain_segment
from _wvw_list import Derived, derive_owed
from _wvw_prepare import Altered, unified_diff

_LOG = logging.getLogger("wrong_version_writer")
_MANIFEST = "alterations.json"


def _fail(error: str) -> tuple[dict, int]:
    """The payload and exit code of a step that stopped."""
    return {"written": False, "manifest_path": None, "error": error, "entries": [],
            "ignored_reply_names": [], "preparer_anomalies": []}, 1


def _read_reply(source: str) -> str:
    """Read the raw reply from the file *source*, or from stdin when it is ``-``."""
    raw = sys.stdin.buffer.read() if source == "-" else Path(source).read_bytes()
    return raw.decode("utf-8-sig")


def _clean(work_dir: Path) -> None:
    """Remove the manifest and copies an earlier preparation of the same work left."""
    for stale in (work_dir / _MANIFEST, work_dir / f"{_MANIFEST}.tmp"):
        stale.unlink(missing_ok=True)
    if (work_dir / "copies").exists():
        shutil.rmtree(work_dir / "copies")


def _slug(index: int, name: str) -> str:
    """A deterministic, filesystem-safe folder name for the copies of one owed name."""
    return f"{index + 1:02d}-{re.sub(r'[^A-Za-z0-9]+', '-', name).strip('-').lower()[:40] or 'name'}"


def _write_copies(folder: Path, altered: list[Altered]) -> list[dict]:
    """Write the altered copies under *folder*; return the manifest ``files`` list."""
    files = []
    for item in altered:
        target = folder.joinpath(*item.rel.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(item.data)
        files.append({"path": item.rel, "altered_copy": str(target)})
    return files


def _entry(index: int, name: str, files: list[str], decision: Decision, answer: reply_mod.Answer, derived: Derived,
           copies: Path) -> dict:
    """Build the manifest entry of one owed name (copies are written only when it is prepared).

    A pinned name applies its pinned replacements to the code as it now stands; every other name
    takes the preparer's answer. Whatever is applied is held to checks (e), (a) and (c) first
    (``_wvp_checks.static_check``); (b) and (d) are the run's. A name sent back to the preparer
    (source ``re-prepared: <check>``) keeps that check at the start of its reason, then gives the
    second failure. The entry also carries the replacements actually applied, their identity and
    the source of the row.
    """
    pinned = decision.replacements is not None
    repls = decision.replacements if pinned else answer.replacements
    reason, altered = ("" if pinned else answer.reason), []
    if not reason:
        checked = static_check(Item(name, repls, files), derived.root, derived.test_root_rel)
        altered, reason = checked.altered, checked.detail
    if reason and decision.source.startswith(RE_PREPARED):
        reason = f"{decision.source}; {reason}"
    if reason:
        return {"name": name, "status": "could_not_prepare", "reason": reason, "files": [], "diff": "",
                "replacements": [], "alteration_id": None, "source": decision.source}
    applied = [{"path": r["path"], "old": r["old"], "new": r["new"]} for r in repls]
    return {"name": name, "status": "prepared", "reason": None,
            "files": _write_copies(copies / _slug(index, name), altered), "diff": unified_diff(altered),
            "replacements": applied, "alteration_id": alteration_id(applied), "source": decision.source}


def _write_manifest(work_dir: Path, manifest: dict) -> Path:
    """Write *manifest* to a temporary file, then rename it over ``alterations.json`` in one step."""
    final, temp = work_dir / _MANIFEST, work_dir / f"{_MANIFEST}.tmp"
    temp.write_bytes((json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    os.replace(temp, final)
    return final


def _load_reply(source: str, work_key: str) -> reply_mod.Reply:
    """Read and parse the reply; every way of failing to read it is a ``ReplyError``."""
    try:
        text = _read_reply(source)
    except (OSError, UnicodeDecodeError) as exc:
        msg = f"{reply_mod.UNREADABLE}: {exc}"
        raise reply_mod.ReplyError(msg) from exc
    return reply_mod.parse_reply(text, work_key)


def _prepare_reply(source: str, work_key: str, has_owed: bool) -> reply_mod.Reply:
    """Load the reply; with nothing owed an unreadable reply is no error."""
    try:
        return _load_reply(source, work_key)
    except reply_mod.ReplyError as exc:
        if has_owed:
            raise
        _LOG.info("nothing is owed; the reply is not needed (%s)", exc)
        return reply_mod.Reply()


def _build(work_key: str, work_dir: Path, derived: Derived, reply: reply_mod.Reply,
           decisions: list[Decision]) -> tuple[dict, int]:
    """Build every entry, write the copies and then the manifest; return the payload."""
    owed = derived.owed
    asked = [o.name for o, d in zip(owed, decisions, strict=True) if d.replacements is None]
    groups, ignored = reply_mod.group_by_name(reply.entries, asked)
    copies = work_dir / "copies"
    entries = [_entry(i, o.name, o.files, d, reply_mod.answer_for(groups[o.name]) if o.name in groups else reply_mod.Answer(),
                      derived, copies)
               for i, (o, d) in enumerate(zip(owed, decisions, strict=True))]
    path = _write_manifest(work_dir, {"work_key": work_key, "entries": entries})
    shown = [{"name": e["name"], "status": e["status"], "reason": e["reason"]} for e in entries]
    return {"written": True, "manifest_path": str(path), "error": None, "entries": shown,
            "ignored_reply_names": ignored, "preparer_anomalies": reply.anomalies}, 0


def _run(work_key: str, source: str, ac_ids: list[str], test_root: Path, ac_root: Path, git_dir: Path,
         base_ref: str) -> tuple[dict, int]:
    """Clean the work folder, derive the owed names, plan them, read the reply and build the manifest.

    The reply is required only for a name to prepare that the list step sent to the preparer
    (or, with no plan record of the work, for any name to prepare).
    """
    work_dir = git_dir / "leafcutter" / "work" / work_key
    _clean(work_dir)
    derived = derive_owed(ac_ids, test_root, ac_root, base_ref)
    if derived.error:
        return _fail(derived.error)
    decisions, sent = plan_for_write(work_dir, git_dir, work_key, derived.owed, derived.root, derived.test_root_rel,
                                    derived.tests)
    needs_reply = any(d.replacements is None and (sent is None or d.name in sent) for d in decisions)
    work_dir.mkdir(parents=True, exist_ok=True)
    return _build(work_key, work_dir, derived, _prepare_reply(source, work_key, needs_reply), decisions)


def run_write(work_key: str, source: str, ac_ids: list[str], test_root: Path, ac_root: Path,
              base_ref: str = "HEAD") -> tuple[dict, int]:
    """Run the ``write`` step; return ``(stdout payload, exit code)``.

    Args:
        work_key: The work key (one plain path segment).
        source: Path of the file holding the raw reply, or ``-`` for stdin.
        ac_ids: The requirement ids whose owed names are derived.
        test_root: The working-tree root.
        ac_root: Root of the AC store.
        base_ref: The ref the work began from (empty means HEAD); scope of an undeclared name derives from it.

    Returns:
        The one JSON object to print and the exit code (0 when the manifest was written).
    """
    if not _plain_segment(work_key):
        return _fail(f"the work key {work_key!r} is not one plain path segment")
    try:
        git_dir = Path(gate_mod.git_text(test_root, "rev-parse", "--absolute-git-dir"))
    except gate_mod.GateError as exc:
        return _fail(f"internal error: {exc}")
    work_dir = git_dir / "leafcutter" / "work" / work_key
    try:
        return _run(work_key, source, ac_ids, test_root, ac_root, git_dir, base_ref)
    except (reply_mod.ReplyError, PinError) as exc:
        return _fail(str(exc))
    except Exception as exc:  # noqa: BLE001 -- the JSON shape must print whatever went wrong
        _LOG.warning("the write step failed: %r", exc)
        try:
            _clean(work_dir)
        except OSError:
            _LOG.warning("partial copies of %s could not be removed", work_dir)
        return _fail(f"internal error: {exc!r}")


# DECISION HISTORY
# ================================================================================
# - 2026-10-25 15:50 [python-coder]: Pins keep applied replacements per work key and are replayed on the current code; a pin-write failure fails the gate. (#EPIC-OnceANamedWrongVersionIsPreparedAnd/02) (ADR-079)
# - 2026-10-25 22:00 [python-coder]: Every applied replacement goes through _wvp_checks.static_check; a re-prepared name keeps its failed pin check at the start of its reason. (#EPIC-OnceANamedWrongVersionIsPreparedAnd/05) (ADR-079)
