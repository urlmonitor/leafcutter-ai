"""
MODULE: scripts/build_orchestration/_wvp_store.py
GOAL: The wrong-version pin store: read, write and promote the replacements a named wrong
    version was prepared with, so a later run of the same work can apply them again.
BUSINESS CONTEXT: TQ-500g-1-xi (ADR-079). Once a named wrong version is prepared and passes
    its checks for a piece of work, every later run applies the SAME replacement to the code as
    it then stands, instead of asking the preparer for a different guess. Only the applied
    replacements (path, old text, new text) are kept: never an altered copy, never the
    preparer's raw reply. Pins are private to the workspace (inside the git directory, never
    committed) and are keyed by work key and then by the shared name normaliser.
ARCHITECTURE: One location rule (``pin_path``): ``<git-dir>/leafcutter/pins/<work-key>.json``,
    outside ``leafcutter/work/<work-key>/`` so nothing that clears the work folder reaches
    it. One identity function (``alteration_id``). Writes are atomic (``atomic_write_bytes``)
    and deterministic. ``promote`` is the pin step's rule: a prepared name becomes a pin only
    when every verdict row of that name is caught or survived. Logging goes to stderr only.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path

import _wvr_gate as gate_mod
from _wvr_scope import UNDONE_NAME, norm_name, wrong_version_key

_LOG = logging.getLogger("wrong_version_writer")
PIN_KEYS = ("name", "replacements", "alteration_id", "failed_check", "reset", "cleared_alteration_id")
PINNED = "pinned"
NOT_PINNED = "prepared: not pinned"
_PASSING = frozenset({"caught", "survived"})


class PinError(Exception):
    """The pin store cannot be read or written; ``str(exc)`` is the error a step prints."""


def plain_segment(key: str) -> bool:
    """True when *key* is one plain path segment (no separator, no ``..``)."""
    return bool(key.strip()) and key not in {".", ".."} and not re.search(r"[\\/:\x00]", key)


def git_dir(test_root: Path) -> Path:
    """The absolute git directory of the working tree at *test_root*.

    Raises:
        PinError: When *test_root* is not inside a git working tree.
    """
    try:
        return Path(gate_mod.git_text(test_root, "rev-parse", "--absolute-git-dir"))
    except gate_mod.GateError as exc:
        msg = f"internal error: {exc}"
        raise PinError(msg) from exc


def pin_path(git_directory: Path, work_key: str) -> Path:
    """Where the pins of *work_key* live: the one location rule."""
    return git_directory / "leafcutter" / "pins" / f"{work_key}.json"


def alteration_id(replacements: list[dict]) -> str:
    """The identity of an ordered replacement list: ``sha256:`` plus 16 hex of its canonical JSON."""
    canon = json.dumps([{"path": r["path"], "old": r["old"], "new": r["new"]} for r in replacements],
                       sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(canon).hexdigest()[:16]


def read_bytes(git_directory: Path, work_key: str) -> bytes:
    """The pin file's bytes (empty when there is none).

    Raises:
        PinError: When the file exists but cannot be read.
    """
    path = pin_path(git_directory, work_key)
    if not path.is_file():
        return b""
    try:
        return path.read_bytes()
    except OSError as exc:
        _LOG.warning("the pin file %s cannot be read: %s", path, exc)
        msg = f"the pin file cannot be read: {exc}"
        raise PinError(msg) from exc


def parse(raw: bytes) -> dict[str, dict]:
    """The ``pins`` object of the pin file bytes *raw* (``{}`` for no bytes).

    Raises:
        PinError: When the bytes are not a pin file.
    """
    if not raw:
        return {}
    try:
        data = json.loads(raw.decode("utf-8"))
        pins = data["pins"]
    except (ValueError, KeyError, TypeError) as exc:
        msg = f"the pin file is not readable: {exc!r}"
        raise PinError(msg) from exc
    if not isinstance(pins, dict):
        msg = "the pin file is not readable: pins is not an object"
        raise PinError(msg)
    return pins


def usable(entry: object) -> bool:
    """True when *entry* is a pin that can be applied (not reset, with well-formed replacements)."""
    if not isinstance(entry, dict) or entry.get("reset") or not isinstance(entry.get("replacements"), list):
        return False
    repls = entry["replacements"]
    return bool(repls) and all(isinstance(r, dict) and all(isinstance(r.get(k), str) for k in ("path", "old", "new")) for r in repls)


def _write(git_directory: Path, work_key: str, pins: dict[str, dict]) -> None:
    """Write the whole pin file atomically."""
    path = pin_path(git_directory, work_key)
    data = (json.dumps({"work_key": work_key, "pins": pins}, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        gate_mod.atomic_write_bytes(path, data)
    except OSError as exc:
        _LOG.warning("the pins of %s cannot be saved: %s", work_key, exc)
        msg = f"the pins cannot be saved: {exc}"
        raise PinError(msg) from exc


def _passing_names(verdict: dict) -> set[str]:
    """The normalised names whose every verdict row is caught or survived (and that have a row)."""
    rows = verdict.get("results")
    if not isinstance(rows, list):
        msg = "the runner's JSON has no results list"
        raise PinError(msg)
    seen: dict[str, bool] = {}
    for r in rows:
        key = norm_name(r.get("wrong_version") or "") if isinstance(r, dict) else ""
        if key:
            seen[key] = seen.get(key, True) and r.get("result") in _PASSING
    return {k for k, ok in seen.items() if ok}


def _new_pin(entry: dict) -> dict:
    """The pin of a prepared manifest *entry*, in the fixed key order."""
    repls = [{"path": r["path"], "old": r["old"], "new": r["new"]} for r in entry["replacements"]]
    return dict(zip(PIN_KEYS, (entry["name"], repls, alteration_id(repls), None, False, None), strict=True))


def _candidate(entry: object, passing: set[str], stored: dict[str, dict]) -> bool:
    """True when manifest *entry* is a preparation that passed and has no pin yet.

    "The fix undone" is never a candidate under any alias spelling: it is rebuilt from the base
    ref on every run. The list already keeps it out of the manifest; this is the second line.
    """
    if not isinstance(entry, dict) or not isinstance(entry.get("name"), str) or entry.get("status") != "prepared":
        return False
    source = entry.get("source")
    key = norm_name(entry["name"])
    return (isinstance(source, str) and source.startswith(("prepared", "re-prepared"))
            and wrong_version_key(entry["name"]) != norm_name(UNDONE_NAME) and key in passing and key not in stored
            and usable({"replacements": entry.get("replacements")}))


def promote(git_directory: Path, work_key: str, manifest: dict, verdict: dict) -> dict:
    """The pin step's rule: pin each preparation that passed; leave every other pin as it is.

    Args:
        git_directory: The absolute git directory.
        work_key: The work key.
        manifest: The alterations manifest (``entries`` with name, status, source, replacements).
        verdict: The runner's run JSON.

    Returns:
        ``{pinned: [{name, alteration_id}], kept: [name], error: None}``.

    Raises:
        PinError: When the store or the inputs cannot be read, or the pins cannot be saved.
    """
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        msg = "the manifest has no entries list"
        raise PinError(msg)
    stored = parse(read_bytes(git_directory, work_key))
    passing = _passing_names(verdict)
    fresh = {norm_name(e["name"]): _new_pin(e) for e in entries if _candidate(e, passing, stored)}
    if fresh:
        _write(git_directory, work_key, {**stored, **fresh})
    kept = [e["name"] for e in entries if isinstance(e, dict) and e.get("source") == PINNED and isinstance(e.get("name"), str)]
    return {"pinned": [{"name": p["name"], "alteration_id": p["alteration_id"]} for p in fresh.values()], "kept": kept, "error": None}


def _read_inputs(work_key: str, manifest_path: str, verdict_text: str) -> tuple[dict, dict]:
    """Read the manifest and the runner's JSON; every way of failing is a ``PinError``."""
    if not plain_segment(work_key):
        msg = f"the work key {work_key!r} is not one plain path segment"
        raise PinError(msg)
    try:
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        verdict = json.loads(verdict_text)
    except (OSError, ValueError) as exc:
        msg = f"the manifest or the runner's JSON cannot be read: {exc}"
        raise PinError(msg) from exc
    if not isinstance(manifest, dict) or not isinstance(verdict, dict):
        msg = "the manifest or the runner's JSON is not an object"
        raise PinError(msg)
    return manifest, verdict


def run_pin(work_key: str, manifest_path: str, test_root: Path, verdict_text: str) -> tuple[dict, int]:
    """Run the pin step: read the manifest and the runner's JSON, promote, return ``(payload, exit code)``."""
    try:
        manifest, verdict = _read_inputs(work_key, manifest_path, verdict_text)
        return promote(git_dir(test_root), work_key, manifest, verdict), 0
    except PinError as exc:
        return {"pinned": [], "kept": [], "error": str(exc)}, 1


# DECISION HISTORY
# ================================================================================
# - 2026-10-25 15:50 [python-coder]: Pins keep applied replacements per work key and are replayed on the current code; a pin-write failure fails the gate. (#EPIC-OnceANamedWrongVersionIsPreparedAnd/02) (ADR-079)
# - 2026-10-25 18:40 [coordinator]: _candidate refused only the alias "revert the fix" (key != its
#   canonical key) and let an entry named "the fix undone" through; it now refuses every spelling
#   whose canonical key is the fix undone. Found by the wrong-version gate (a survivor). (#EPIC-OnceANamedWrongVersionIsPreparedAnd/02)
