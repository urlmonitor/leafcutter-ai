"""
MODULE: _rc_file_findings
GOAL: Rule family "file findings consistency": a record's ``file_findings`` must agree with the
    record's declared files and with the tree. A declared file with no finding, a finding for a file
    that is neither declared nor the record's reference file, a verdict that contradicts the tree, a
    verdict missing its companion field, and a verdict on a file that was not opened are each
    reported. Nothing is repaired.
BUSINESS CONTEXT: ACD-2500d-1, -1-i, -3-i (ADR-072; G4 architect note, section 4). The file-aware
    step only reports; it never adds files, so a finding for an undeclared file is a defect. An
    UNDECIDED finding is deliberately NOT reported here: it waits for the planner's next pass and is
    an approval hold (_approval_holds), so failing the stage on it would loop the designer for nothing.
ARCHITECTURE: One family object (NAME, pure `evaluate_record`), registered in
    requirement_rule_check.FAMILIES after _rc_design_grounding and deployed flat
    (scripts/build_phases_ac_store_rc.py). Only a record whose ``file_findings`` is a list is judged
    (an absent field means the step has not run). Paths are judged against `ctx.repo_root`; a path
    with `..` or an absolute form is never in the tree. Declared files are read only through
    `declared_files.get_declared_files`; a declared to_be_created file that is not in the tree yet is
    exempt from "needs a finding". The tree check applies to declared files only (the reference file's
    existence is the record check's business). Every finding is `needs a decision` with
    `detail = {"kind", "path"}`, kind in missing | undeclared | tree-absent | tree-present |
    line_range | found_in | found_in_null | unopened.

DECISION HISTORY:
  - 2026-10-14 [python-coder/ACD-2500d-3-i]: Created per the G4 architect note, section 4.
"""

from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath
from typing import Any

from _file_findings import (
    FINDINGS_OPENED_KEY,
    VERDICT_ABSENT,
    VERDICT_DESCRIBES,
    VERDICT_ELSEWHERE,
    findings_of,
)
from _rc_report import DISPOSITION_DECISION, FAMILY_FILE_FINDINGS, Finding
from declared_files import NoDeclaredFiles, get_declared_files

NAME = FAMILY_FILE_FINDINGS

_MESSAGES = {
    "missing": "{record}: declared file {path} has no entry in file_findings",
    "undeclared": "{record}: file_findings has a finding for {path}, which is neither a declared file nor the reference file",
    "tree-absent": "{record}: {path} is absent from the tree but its verdict is {verdict}, not {absent}",
    "tree-present": "{record}: {path} is in the tree but its verdict is {absent}",
    "line_range": "{record}: the finding for {path} has verdict {verdict} and needs a line_range",
    "found_in": "{record}: the finding for {path} has verdict {verdict} and needs a found_in",
    "found_in_null": "{record}: the finding for {path} has verdict {verdict} and found_in must be null",
    "unopened": "{record}: the finding for {path} is on a file not listed in {opened_key}",
}


def _posix(path: Any) -> str:
    """The path as a forward-slash string ('' for a non-string)."""
    return path.replace("\\", "/") if isinstance(path, str) else ""


def _in_tree(ctx: Any, path: str) -> bool:
    """True when `path` is a repo-relative path (never `..` or absolute) present under the repo root."""
    pure = PurePosixPath(path)
    if PureWindowsPath(path).drive or pure.is_absolute() or ".." in pure.parts:
        return False
    return bool(path) and (ctx.repo_root / path).exists()


def _finding(record: Any, kind: str, path: str, verdict: str = "") -> Finding:
    """One `needs a decision` finding; the subject keeps each kind and path apart."""
    message = _MESSAGES[kind].format(
        record=record["id"], path=path, verdict=verdict, absent=VERDICT_ABSENT, opened_key=FINDINGS_OPENED_KEY
    )
    return Finding.for_record(
        record, NAME, DISPOSITION_DECISION, message, subject=f"{kind}:{path}", detail={"kind": kind, "path": path}
    )


def _reference_path(record: Any) -> str:
    """The record's it_requirements.reference_file_path ('' when none)."""
    spec = record.get("it_requirements")
    return _posix(spec.get("reference_file_path")) if isinstance(spec, dict) else ""


def _declared_states(record: Any) -> dict[str, str]:
    """{path: state} of the declared files ({} for a record with none)."""
    declared = get_declared_files(record)
    if isinstance(declared, NoDeclaredFiles):
        return {}
    return {_posix(item.get("path")): str(item.get("state")) for item in declared if isinstance(item, dict)}


def _companion_kinds(item: dict[str, Any]) -> list[str]:
    """A missing line_range or found_in, or a found_in on a verdict that takes none."""
    verdict = item.get("verdict")
    if verdict == VERDICT_DESCRIBES and not item.get("line_range"):
        return ["line_range"]
    if verdict == VERDICT_ELSEWHERE and not item.get("found_in"):
        return ["found_in"]
    if verdict != VERDICT_ELSEWHERE and item.get("found_in") is not None:
        return ["found_in_null"]
    return []


def _tree_kind(ctx: Any, item: dict[str, Any], path: str, state: str) -> list[str]:
    """`tree-present` / `tree-absent` when the verdict contradicts the tree for a declared file."""
    present = _in_tree(ctx, path)
    if present and item.get("verdict") == VERDICT_ABSENT:
        return ["tree-present"]
    if not present and state != "to_be_created" and item.get("verdict") != VERDICT_ABSENT:
        return ["tree-absent"]
    return []


def _item_kinds(ctx: Any, item: dict[str, Any], path: str, states: dict[str, str], opened: set[str]) -> list[str]:
    """Every defect kind of one finding about a declared file or the reference file."""
    kinds = _companion_kinds(item)
    if path in states:
        kinds += _tree_kind(ctx, item, path, states[path])
    if _in_tree(ctx, path) and path not in opened:
        kinds.append("unopened")
    return kinds


def evaluate_record(ctx: Any, record: Any) -> list[Finding]:
    """Judge a record's file findings against its declared files and the tree; empty when the step has not run."""
    findings = findings_of(record)
    if findings is None:
        return []
    states = _declared_states(record)
    allowed = {*states, _reference_path(record)} - {""}
    opened_value = record.get(FINDINGS_OPENED_KEY)
    opened = {_posix(path) for path in opened_value} if isinstance(opened_value, list) else set()
    named = {_posix(item.get("file")) for item in findings}
    found = [
        _finding(record, "missing", path)
        for path, state in states.items()
        if path not in named and (state != "to_be_created" or _in_tree(ctx, path))
    ]
    for item in findings:
        path = _posix(item.get("file"))
        if path not in allowed:
            found.append(_finding(record, "undeclared", path))
            continue
        found += [_finding(record, kind, path, str(item.get("verdict"))) for kind in _item_kinds(ctx, item, path, states, opened)]
    return found
