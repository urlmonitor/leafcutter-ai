"""
MODULE: scripts/build_orchestration/_wvp_plan.py
GOAL: For each owed wrong version decide exactly one thing: apply the work's pin, or prepare.
BUSINESS CONTEXT: TQ-500g-1-xi (ADR-079). A name is prepared only when the work holds no usable
    pin for it; a pinned name is rebuilt by applying its stored replacements to the code AS IT
    NOW STANDS, never by reusing an earlier altered copy. A pin whose old text no longer occurs
    exactly once is not usable: the name goes back to the preparer. "The fix undone" is never
    owed here, so it is never planned or pinned. Later ACs add their triggers in ``decide``.
ARCHITECTURE: Pure decision over the shared owed reading (``_wvr_scope.OwedName``) and the pin
    store; the only I/O is the plan record ``<git-dir>/leafcutter/work/<work-key>/plan.json``
    (atomic) written by ``list --work-key``. The record carries a fingerprint over the owed list,
    the pin file bytes and the bytes of every file a planned replacement names; the write step
    trusts it only when the fingerprint still matches the current state, else it recomputes the
    plan here. Nothing is ever taken from the route or the reply.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

import _wvr_gate as gate_mod
from _wvp_store import NOT_PINNED, PINNED, PinError, alteration_id, parse, read_bytes, usable
from _wvr_scope import OwedName, norm_name
from _wvw_prepare import alter

_LOG = logging.getLogger("wrong_version_writer")
_RECORD = "plan.json"


@dataclass
class Decision:
    """The one decision for an owed name; ``replacements`` is ``None`` when the name is to be prepared."""

    name: str
    source: str
    reason: str | None = None
    alteration_id: str | None = None
    replacements: list[dict] | None = None

    def shown(self) -> dict:
        """The decision as the ``list`` step prints it (fixed key order)."""
        return {"name": self.name, "source": self.source, "reason": self.reason, "alteration_id": self.alteration_id}

    def record(self) -> dict:
        """The decision as the plan record keeps it."""
        return {**self.shown(), "replacements": self.replacements}


def decide(owed: list[OwedName], pins: dict[str, dict], root: Path, test_root_rel: str | None) -> list[Decision]:
    """One decision per owed name, in owed order."""
    out: list[Decision] = []
    for item in owed:
        pin = pins.get(norm_name(item.name))
        if not usable(pin):
            out.append(Decision(item.name, NOT_PINNED))
            continue
        _, reason = alter(item.name, pin["replacements"], root, item.files, test_root_rel)
        if reason:
            out.append(Decision(item.name, NOT_PINNED, f"the pinned replacement no longer applies: {reason}"))
        else:
            repls = [dict(r) for r in pin["replacements"]]
            out.append(Decision(item.name, PINNED, None, alteration_id(repls), repls))
    return out


def fingerprint(owed: list[OwedName], pin_raw: bytes, root: Path, decisions: list[Decision]) -> str:
    """SHA-256 over the owed list, the pin file's bytes and the bytes of every file a planned replacement names."""
    digest = hashlib.sha256(json.dumps([asdict(o) for o in owed], sort_keys=True, ensure_ascii=False).encode("utf-8"))
    digest.update(b"\0" + pin_raw)
    paths = sorted({r["path"] for d in decisions for r in d.replacements or []})
    for rel in paths:
        target = root / rel
        data = target.read_bytes() if target.is_file() else b"\0missing"
        digest.update(b"\0" + rel.encode("utf-8") + b"\0" + data)
    return digest.hexdigest()


def make_plan(owed: list[OwedName], git_directory: Path, work_key: str, root: Path,
              test_root_rel: str | None) -> tuple[list[Decision], str]:
    """Decide every owed name from the work's pins; return ``(decisions, fingerprint)``.

    Raises:
        PinError: When the pin file cannot be read.
    """
    raw = read_bytes(git_directory, work_key)
    decisions = decide(owed, parse(raw), root, test_root_rel)
    return decisions, fingerprint(owed, raw, root, decisions)


def write_record(work_dir: Path, work_key: str, decisions: list[Decision], fp: str) -> None:
    """Write the plan record atomically.

    Raises:
        PinError: When it cannot be written.
    """
    body = {"work_key": work_key, "fingerprint": fp, "decisions": [d.record() for d in decisions]}
    try:
        work_dir.mkdir(parents=True, exist_ok=True)
        gate_mod.atomic_write_bytes(work_dir / _RECORD, (json.dumps(body, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    except OSError as exc:
        _LOG.warning("the plan record cannot be saved: %s", exc)
        msg = f"the plan record cannot be saved: {exc}"
        raise PinError(msg) from exc


def _read_record(work_dir: Path, work_key: str) -> tuple[list[Decision], str] | None:
    """The saved decisions and fingerprint, or ``None`` when there is no usable record of this work."""
    try:
        data = json.loads((work_dir / _RECORD).read_text(encoding="utf-8"))
        saved = [Decision(d["name"], d["source"], d["reason"], d["alteration_id"], d["replacements"]) for d in data["decisions"]]
        fp = data["fingerprint"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    ok = data.get("work_key") == work_key and isinstance(fp, str) and all(
        d.replacements is None or usable({"replacements": d.replacements}) for d in saved)
    return (saved, fp) if ok else None


def plan_for_write(work_dir: Path, git_directory: Path, work_key: str, owed: list[OwedName], root: Path,
                   test_root_rel: str | None) -> tuple[list[Decision], set[str] | None]:
    """The decisions the write step acts on, and the names the list step sent to the preparer.

    The saved plan record is used only while its fingerprint matches the current state; otherwise
    the plan is recomputed here. ``None`` for the second item means no record: every name to
    prepare was (or must be treated as) asked of the preparer.

    Raises:
        PinError: When the pin file cannot be read.
    """
    saved = _read_record(work_dir, work_key)
    raw = read_bytes(git_directory, work_key)
    sent = None if saved is None else {d.name for d in saved[0] if d.replacements is None}
    if saved is not None and fingerprint(owed, raw, root, saved[0]) == saved[1]:
        return saved[0], sent
    return decide(owed, parse(raw), root, test_root_rel), sent


# DECISION HISTORY
# ================================================================================
# - 2026-10-25 15:50 [python-coder]: Pins keep applied replacements per work key and are replayed on the current code; a pin-write failure fails the gate. (#EPIC-OnceANamedWrongVersionIsPreparedAnd/02) (ADR-079)
