"""
MODULE: scripts/build_orchestration/_wvp_plan.py
GOAL: For each owed wrong version decide exactly one thing: apply its declared replacement, apply the work's pin, or prepare
    (precedence declared > pinned > prepared, TQ-500g-1-xvii, ADR-080; a failing declaration is refused, never prepared).
BUSINESS CONTEXT: TQ-500g-1-xi (ADR-079). A name is prepared only when the work holds no usable
    pin for it; a pinned name is rebuilt by applying its stored replacements to the code AS IT
    NOW STANDS, never by reusing an earlier altered copy. A pin whose old text no longer occurs
    exactly once is not usable: the name goes back to the preparer. "The fix undone" is never
    owed here, so it is never planned or pinned. TQ-500g-1-xiii: every pin is re-checked against the
    code as written (``_wvp_checks``) before any wrong version runs; a pin that fails a check is
    prepared again (decision source ``re-prepared: <check>``), never used and never dropped.
ARCHITECTURE: Decision over the shared owed reading (``_wvr_scope.OwedName``), the pin
    store and the checks (which may run a child interpreter and one traced pytest run, both leaving
    the code as written); the only file written is the plan record ``<git-dir>/leafcutter/work/<work-key>/plan.json``
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
from _wvp_checks import NOT_IN_SCOPE, Item, Verdict, check_candidates
from _wvp_store import NOT_PINNED, PINNED, RE_PREPARED, RESET_SOURCE, PinError, alteration_id, known_failure, parse, read_bytes, usable
from _wvr_scope import OwedName, ScopedTest, declared_text, norm_name

_LOG = logging.getLogger("wrong_version_writer")
_RECORD = "plan.json"
DECLARED = "declared"


@dataclass
class Decision:
    """The one decision for an owed name.

    ``replacements`` is ``None`` when the name is to be prepared, unless ``refused`` is set: a declared
    name that failed a check is unfinished and is never prepared (TQ-500g-1-xvii).
    """

    name: str
    source: str
    reason: str | None = None
    alteration_id: str | None = None
    replacements: list[dict] | None = None
    declared_by: list[dict] | None = None
    refused: str | None = None

    @property
    def to_prepare(self) -> bool:
        """True when the name is asked of the preparer."""
        return self.replacements is None and self.refused is None

    def shown(self) -> dict:
        """The decision as the ``list`` step prints it (fixed key order; ``declared_by`` only on a declared name)."""
        shown = {"name": self.name, "source": self.source, "reason": self.reason, "alteration_id": self.alteration_id}
        return {**shown, "declared_by": self.declared_by} if self.declared_by else shown

    def record(self) -> dict:
        """The decision as the plan record keeps it."""
        return {**self.shown(), "replacements": self.replacements, "refused": self.refused}


def _pin_decision(item: OwedName, pins: dict[str, dict], verdict: Verdict | None) -> Decision:
    """The decision of a name without a declaration: its checked pin, or the preparer (TQ-500g-1-xi, -xiii)."""
    if verdict is None:
        marked = isinstance(pins.get(norm_name(item.name)), dict) and pins[norm_name(item.name)].get("reset") is True
        return Decision(item.name, RESET_SOURCE if marked else NOT_PINNED)
    if verdict.reason:
        return Decision(item.name, f"{RE_PREPARED}: {verdict.reason}", f"the pinned replacement failed a check: {verdict.detail}")
    repls = [dict(r) for r in pins[norm_name(item.name)]["replacements"]]
    return Decision(item.name, PINNED, verdict.note or None, alteration_id(repls), repls)


def declared_refusal(declared_by: list[dict], verdict: Verdict) -> str:
    """The reason of a declared name that failed a check: ``declared on <ac id>, entry <entry>: <failed check>``.

    A path refusal (a test file, outside the repository, inside the version-control folder, not in
    scope) is worded as the preparer's would be; the other checks use their fixed wording.
    """
    check = verdict.detail if verdict.reason == NOT_IN_SCOPE else verdict.reason
    return f"declared on {declared_text(declared_by)}: {check}"


def _declared_decision(item: OwedName, verdict: Verdict | None) -> Decision:
    """The decision of a declared name (TQ-500g-1-xvii): the declaration, or unfinished; never the pin or the preparer."""
    if item.declared_error or verdict is None or item.declared is None:
        reason = item.declared_error or f"declared on {declared_text(item.declared_by)}: the declaration could not be checked"
        return Decision(item.name, DECLARED, reason, declared_by=item.declared_by, refused=reason)
    if verdict.reason:
        reason = declared_refusal(item.declared_by, verdict)
        return Decision(item.name, DECLARED, reason, declared_by=item.declared_by, refused=reason)
    repls = [dict(r) for r in item.declared]
    return Decision(item.name, DECLARED, verdict.note or None, alteration_id(repls), repls, item.declared_by)


def decide(owed: list[OwedName], pins: dict[str, dict], root: Path, test_root_rel: str | None,
           git_directory: Path, tests: list[ScopedTest]) -> list[Decision]:
    """One decision per owed name, in owed order. Precedence: declared > pinned > prepared (ADR-080).

    Every pinned and every declared replacement is checked (``_wvp_checks``) against the code as now
    written, here, before anything is run. A pin that fails a check is neither used nor dropped: the name
    is prepared again (source ``re-prepared: <check>``) and the pin stays in the store as it was. A name
    with a declaration never reads its pin: a failing declaration is unfinished, never prepared.

    Raises:
        PinError: When a load check could not be made or its files could not be put back.
    """
    pinned = [(o, pins[norm_name(o.name)]) for o in owed if not o.declared_by and usable(pins.get(norm_name(o.name)))]
    declared = [o for o in owed if o.declared_by and not o.declared_error and o.declared is not None]
    items = [Item(o.name, pin["replacements"], o.files, known_failure(pin, root)) for o, pin in pinned]
    items += [Item(o.name, o.declared, o.files) for o in declared]
    verdicts = iter(check_candidates(items, root, git_directory, tests, test_root_rel))
    checked = {o.name: next(verdicts) for o, _pin in pinned}
    checked.update({o.name: next(verdicts) for o in declared})
    return [_declared_decision(o, checked.get(o.name)) if o.declared_by else _pin_decision(o, pins, checked.get(o.name)) for o in owed]


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
              test_root_rel: str | None, tests: list[ScopedTest]) -> tuple[list[Decision], str]:
    """Decide every owed name from the work's pins; return ``(decisions, fingerprint)``.

    Raises:
        PinError: When the pin file cannot be read, or a pin's load check could not be made.
    """
    raw = read_bytes(git_directory, work_key)
    decisions = decide(owed, parse(raw), root, test_root_rel, git_directory, tests)
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
        saved = [Decision(d["name"], d["source"], d["reason"], d["alteration_id"], d["replacements"], d.get("declared_by"),
                          d.get("refused")) for d in data["decisions"]]
        fp = data["fingerprint"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    ok = data.get("work_key") == work_key and isinstance(fp, str) and all(
        d.replacements is None or usable({"replacements": d.replacements}) for d in saved)
    return (saved, fp) if ok else None


def plan_for_write(work_dir: Path, git_directory: Path, work_key: str, owed: list[OwedName], root: Path,
                   test_root_rel: str | None, tests: list[ScopedTest]) -> tuple[list[Decision], set[str] | None]:
    """The decisions the write step acts on, and the names the list step sent to the preparer.

    The saved plan record is used only while its fingerprint matches the current state; otherwise
    the plan is recomputed here. ``None`` for the second item means no record: every name to
    prepare was (or must be treated as) asked of the preparer.

    Raises:
        PinError: When the pin file cannot be read.
    """
    saved = _read_record(work_dir, work_key)
    raw = read_bytes(git_directory, work_key)
    sent = None if saved is None else {d.name for d in saved[0] if d.to_prepare}
    if saved is not None and fingerprint(owed, raw, root, saved[0]) == saved[1]:
        return saved[0], sent
    return decide(owed, parse(raw), root, test_root_rel, git_directory, tests), sent


# DECISION HISTORY
# ================================================================================
# - 2026-10-25 15:50 [python-coder]: Pins keep applied replacements per work key and are replayed on the current code; a pin-write failure fails the gate. (#EPIC-OnceANamedWrongVersionIsPreparedAnd/02) (ADR-079)
# - 2026-10-25 22:00 [python-coder]: decide() runs the five checks on every pin; a failing pin becomes "re-prepared: <check>". (#EPIC-OnceANamedWrongVersionIsPreparedAnd/05) (ADR-079)
# - 2026-10-26 09:00 [python-coder]: A reset marker is decided as "re-prepared: pin reset by the operator", not "prepared: not pinned". (#EPIC-OnceANamedWrongVersionIsPreparedAnd/07) (ADR-079)
# - 2026-10-30 12:00 [python-coder]: Precedence declared > pinned > prepared: a name with a declaration is checked like a pin and is never sent to the preparer, never reads its pin; a failing one is refused (unfinished). (#EPIC-OnceANamedWrongVersionIsPreparedAnd/08) (ADR-080)
