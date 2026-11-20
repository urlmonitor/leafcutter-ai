"""
MODULE: scripts/ac_store/_verification_record.py
GOAL: Decide whether a test-free AC record names how it is verified, in a typed
    ``verified_by`` record, and return a typed verdict listing every defect.
BUSINESS CONTEXT: BO-2500f-1 / BO-2500f-1-i (ADR-076, wave 2). A record with
    ``test_required: false`` owes no test, so it must instead name its
    verification method: ``check`` (a named check wired into everyday work) or
    ``inspection`` (a person's gate-approved review of fingerprinted files).
    An inspection may not verify a change that can be tested, so it is only
    allowed for change_target values docs, prompt or config; a missing
    change_target fails closed.
ARCHITECTURE: One pure function, ``validate_verification_record(record)``,
    taking the WHOLE AC record mapping and returning
    ``{"valid": bool, "method": "check"|"inspection"|None,
    "problems": [{"part": str, "message": str}]}``. It never raises on
    malformed input; every refusal is logged at WARNING and resolves to an
    invalid verdict, never a waiver. Parts are ``verified_by``,
    ``verified_by.<field>`` and ``change_target``; every message names the
    record id and the part. It is called only from mark-time paths (the shared
    done rule of BO-2500f-4), never from write-time checks, so unfinished
    records stay editable (user decision 2026-10-25). Stdlib only; deployed
    flat into <root>/scripts/ac_store/ via AC_STORE_DEPLOY_MAP in
    scripts/build_phases_ac_store.py.

DECISION HISTORY:
  - 2026-11-05 [python-coder/BO-2500f-1, BO-2500f-1-i]: Created (PR 1, validator
    only). Clause 6 of BO-2500f-1-i (derived kind via BO-3500c-2's
    derive_proof_kind) is NOT implemented: that function does not exist yet,
    and no second path-to-kind table is kept here.
  - 2026-11-05 [claude_code/BO-2500f-1]: Review fixes: a non-string change_target
    item is refused instead of raising; wired_as and blob must match in full (a
    trailing newline no longer passes).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any

logger = logging.getLogger(__name__)

METHODS: tuple[str, ...] = ("check", "inspection")
INSPECTION_TARGETS: frozenset[str] = frozenset({"docs", "prompt", "config"})
_CHECK_PARTS = ("check", "wired_as")
_INSPECTION_PARTS = ("gate_run", "statement", "inspected")
_WIRED_RE = re.compile(r"(pre-commit|build-phase):\S+")
_BLOB_RE = re.compile(r"[0-9a-f]{40}")
_WIRED_HINT = "use 'pre-commit:<hook-id>' or 'build-phase:<name>'"


def _problem(rid: str, part: str, text: str) -> dict[str, str]:
    """Build one problem whose message names the record id and the part; log it."""
    message = f"{rid}: {part} {text}"
    logger.warning("verification record refused: %s", message)
    return {"part": part, "message": message}


def _blank(value: Any) -> bool:
    """Return True when *value* is not a non-blank string."""
    return not isinstance(value, str) or not value.strip()


def _wired_problems(rid: str, wired: Any) -> list[dict[str, str]]:
    """Problems of the ``wired_as`` part of a check record."""
    part = "verified_by.wired_as"
    if wired is None or wired == "":
        return [_problem(rid, part, f"is missing: {_WIRED_HINT}")]
    if not isinstance(wired, str) or not _WIRED_RE.fullmatch(wired):
        return [_problem(rid, part, f"is invalid ({wired!r}): {_WIRED_HINT}")]
    return []


def _check_problems(rid: str, vb: Mapping[str, Any]) -> list[dict[str, str]]:
    """Problems of a check-form record (own parts plus foreign inspection parts)."""
    out: list[dict[str, str]] = []
    if _blank(vb.get("check")):
        out.append(_problem(rid, "verified_by.check", "is missing: name the check's source path"))
    out.extend(_wired_problems(rid, vb.get("wired_as")))
    for part in _INSPECTION_PARTS:
        if part in vb:
            out.append(_problem(rid, f"verified_by.{part}", "belongs to the inspection method and is not allowed on a check"))
    return out


def _inspected_problems(rid: str, inspected: Any) -> list[dict[str, str]]:
    """Problems of the ``inspected`` file list (absent, empty, bad entry or blob)."""
    part = "verified_by.inspected"
    if inspected is None:
        return [_problem(rid, part, "is missing: list every inspected file")]
    if not isinstance(inspected, list) or not inspected:
        return [_problem(rid, part, "must be a non-empty list of {path, blob}")]
    out: list[dict[str, str]] = []
    for index, entry in enumerate(inspected):
        if not isinstance(entry, Mapping) or _blank(entry.get("path")):
            out.append(_problem(rid, part, f"entry {index} lacks a path"))
            continue
        blob = entry.get("blob")
        if not isinstance(blob, str) or not _BLOB_RE.fullmatch(blob):
            out.append(_problem(rid, part, f"entry {index} ({entry['path']}) blob is not a 40-hex git blob sha: {blob!r}"))
    return out


def _inspection_problems(rid: str, vb: Mapping[str, Any]) -> list[dict[str, str]]:
    """Problems of an inspection-form record (own parts plus foreign check parts)."""
    out: list[dict[str, str]] = []
    if _blank(vb.get("gate_run")):
        out.append(_problem(rid, "verified_by.gate_run", "is missing: name the workflow run whose gate recorded the approval"))
    if _blank(vb.get("statement")):
        out.append(_problem(rid, "verified_by.statement", "is missing: state what the review confirmed"))
    out.extend(_inspected_problems(rid, vb.get("inspected")))
    for part in _CHECK_PARTS:
        if part in vb:
            out.append(_problem(rid, f"verified_by.{part}", "belongs to the check method and is not allowed on an inspection"))
    return out


def _targets(raw: Any) -> list[Any]:
    """Normalise a scalar or list change_target to a list; absent/blank gives []."""
    items = raw if isinstance(raw, (list, tuple)) else [raw]
    return [t for t in items if t is not None and t != ""]


def _change_target_problems(rid: str, record: Mapping[str, Any]) -> list[dict[str, str]]:
    """BO-2500f-1-i: an inspection is only allowed for docs/prompt/config targets."""
    targets = _targets(record.get("change_target"))
    if not targets:
        return [_problem(rid, "change_target", "is missing: an inspection needs a declared change_target of docs, prompt or config")]
    ruling = next((t for t in targets if not isinstance(t, str) or t not in INSPECTION_TARGETS), None)
    if ruling is None:
        return []
    # The derived-kind override (BO-2500f-1-i clause 6) waits for BO-3500c-2.
    return [_problem(rid, "change_target", f"value {ruling!r} rules inspection out: only docs, prompt or config may be inspected")]


def _verdict(valid: bool, method: str | None, problems: list[dict[str, str]]) -> dict[str, Any]:
    """Assemble the typed verdict."""
    return {"valid": valid, "method": method, "problems": problems}


def validate_verification_record(record: Any) -> dict[str, Any]:
    """Validate the ``verified_by`` record of an AC record mapping.

    Never raises: any malformed input resolves to an invalid verdict.

    Args:
        record: The whole AC record mapping (its ``id``, ``verified_by`` and
            ``change_target`` are read).

    Returns:
        ``{"valid": bool, "method": "check"|"inspection"|None,
        "problems": [{"part": str, "message": str}]}``.
    """
    if not isinstance(record, Mapping):
        text = f"is missing: the record is not a mapping ({type(record).__name__})"
        return _verdict(False, None, [_problem("<unknown>", "verified_by", text)])
    rid = str(record.get("id") or "<unknown>")
    vb = record.get("verified_by")
    if vb is None or vb == {}:
        text = "is missing: a test-free record must name how it is verified"
        return _verdict(False, None, [_problem(rid, "verified_by", text)])
    if not isinstance(vb, Mapping):
        return _verdict(False, None, [_problem(rid, "verified_by", f"must be a mapping, got {type(vb).__name__}")])
    method = vb.get("method")
    if not isinstance(method, str) or method not in METHODS:
        return _verdict(False, None, [_problem(rid, "verified_by.method", f"must be 'check' or 'inspection', got {method!r}")])
    if method == "check":
        problems = _check_problems(rid, vb)
    else:
        problems = _inspection_problems(rid, vb) + _change_target_problems(rid, record)
    return _verdict(not problems, method, problems)
