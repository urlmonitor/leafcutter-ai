"""
MODULE: _rc_design_grounding
GOAL: Rule family "test design grounding": a code-aware test design (a test_spec carrying the
    authorship mark) must be grounded in the tree. An entry naming a code file that is neither in
    the tree nor declared to-be-created, a design whose opened-files list is empty or missing, an
    entry without a proves_clause or with one that matches no test_intent clause, an entry whose
    target_dir or cited convention test file is not in the tree: each is reported. Nothing is
    repaired.
BUSINESS CONTEXT: ACD-2500c-1-i (ADR-071, ADR-072; G4 architect note section 4, conflict 15). A
    design that names a file nobody opened is how a test-writer ends up asserting against code
    that does not exist. A markless test_spec with no test_intent (a true legacy design) is not judged;
    one WITH test_intent is `unmarked-design` (invalid, ADR-071); a record with no test_spec has nothing to ground.
ARCHITECTURE: One family object (NAME, pure `evaluate_record`), registered in
    requirement_rule_check.FAMILIES after _rc_test_intent and deployed flat
    (scripts/build_phases_ac_store_rc.py). Paths are judged against `ctx.repo_root`; a path with
    `..` or an absolute form is never in the tree. Declared files are read only through
    `declared_files.get_declared_files`: an entry's `to_be_created` flag alone never grounds a path,
    only the record's declared to_be_created list does. Findings are `needs a decision` with
    `detail = {"kind", "entry", "path"}` (kind in absent | no-clause | dangling-clause |
    missing-dir | missing-convention; `entry` is the test_spec entry name; directories have no
    trailing slash), and `detail = {"kind": "not-grounded"}` for the opened-files check. An entry
    flagged to_be_created on a record in the "no declared files" state is `not evaluated`
    (declared_files.NOT_EVALUATED_LABEL): never passed, never rejected. Key names come from
    _test_intent; only `name` and `target_dir` are the test_spec entry's own legacy keys.

DECISION HISTORY:
  - 2026-10-14 [python-coder/ACD-2500c-1-i]: Created per the G4 architect note, section 4.
    "Every named file is in the opened list" is NOT adopted (it would reject files the pre-pass
    legitimately supplied); the empty-list check plus existence is the scope.
"""

from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath
from typing import Any

from _rc_report import DISPOSITION_DECISION, DISPOSITION_NOT_EVALUATED, FAMILY_TEST_DESIGN_GROUNDING, Finding
from _test_intent import (
    AUTHORSHIP_KEY,
    ENTRY_CLAUSE_KEY,
    ENTRY_CODE_FILE_KEY,
    ENTRY_CONVENTION_KEY,
    ENTRY_TO_BE_CREATED_KEY,
    OPENED_FILES_KEY,
    intent_entries,
    is_legacy_design,
    normalise_clause,
)
from declared_files import NOT_EVALUATED_LABEL, NoDeclaredFiles, get_declared_files

NAME = FAMILY_TEST_DESIGN_GROUNDING

_RECORD_KINDS = ("not-grounded", "unmarked-design", "no-reachability")

_MESSAGES = {
    "absent": "{record}: test_spec entry {entry} names {path}, which is neither in the tree nor declared to be created",
    "unmarked-design": "{record}: has test_intent and a test_spec with no {mark_key} mark; a legacy design never carries test_intent",
    "no-reachability": "{record}: the test design has no entry with angle reachability",
    "not-grounded": "{record}: the test design is not grounded: {opened_key} is empty or missing",
    "no-clause": "{record}: test_spec entry {entry} has no {clause_key}",
    "dangling-clause": "{record}: test_spec entry {entry} proves a clause that matches no test_intent clause: {path}",
    "missing-dir": "{record}: test_spec entry {entry} has target_dir {path}, which is not in the tree",
    "missing-convention": "{record}: test_spec entry {entry} cites convention test file {path}, which is not in the tree",
}


def _in_tree(ctx: Any, path: str) -> bool:
    """True when `path` is a repo-relative path (never `..` or absolute) present under the repo root."""
    posix = path.replace("\\", "/")
    if PureWindowsPath(path).drive or PurePosixPath(posix).is_absolute() or ".." in PurePosixPath(posix).parts:
        return False
    return bool(posix) and (ctx.repo_root / posix).exists()


def _finding(record: Any, kind: str, entry: str = "", path: str = "") -> Finding:
    """One `needs a decision` finding of *kind*; the subject keeps each entry and path apart."""
    message = _MESSAGES[kind].format(
        record=record["id"], entry=entry, path=path, clause_key=ENTRY_CLAUSE_KEY, opened_key=OPENED_FILES_KEY,
        mark_key=AUTHORSHIP_KEY,
    )
    detail = {"kind": kind} if kind in _RECORD_KINDS else {"kind": kind, "entry": entry, "path": path}
    return Finding.for_record(
        record, NAME, DISPOSITION_DECISION, message, subject=f"{kind}:{entry}:{path}", detail=detail
    )


def _code_file_findings(ctx: Any, record: Any, entry: dict, name: str, declared: Any) -> list[Finding]:
    """`absent` for a code file in neither the tree nor the declared to_be_created list; `not evaluated`
    for a to_be_created entry on a record with no declared files."""
    path = entry.get(ENTRY_CODE_FILE_KEY)
    if not isinstance(path, str) or not path or _in_tree(ctx, path):
        return []
    if isinstance(declared, NoDeclaredFiles):
        if entry.get(ENTRY_TO_BE_CREATED_KEY) is not True:
            return [_finding(record, "absent", name, path)]
        return [Finding.for_record(
            record, NAME, DISPOSITION_NOT_EVALUATED, f"{record['id']}: {NOT_EVALUATED_LABEL}",
            subject=f"not-evaluated:{name}:{path}",
        )]
    created = {e.get("path") for e in declared if isinstance(e, dict) and e.get("state") == "to_be_created"}
    return [] if path in created else [_finding(record, "absent", name, path)]


def _clause_findings(record: Any, entry: dict, name: str, intent_clauses: set[str] | None) -> list[Finding]:
    """`no-clause` for an entry without proves_clause; `dangling-clause` when the record has intent
    and the clause matches none of it."""
    clause = entry.get(ENTRY_CLAUSE_KEY)
    if not isinstance(clause, str) or not clause.strip():
        return [_finding(record, "no-clause", name)]
    if intent_clauses is not None and normalise_clause(clause) not in intent_clauses:
        return [_finding(record, "dangling-clause", name, clause)]
    return []


def _location_findings(ctx: Any, record: Any, entry: dict, name: str) -> list[Finding]:
    """`missing-dir` for an absent target_dir; `missing-convention` for an absent cited convention file."""
    found: list[Finding] = []
    target = entry.get("target_dir")
    if isinstance(target, str) and target and not _in_tree(ctx, target.rstrip("/")):
        found.append(_finding(record, "missing-dir", name, target.replace("\\", "/").rstrip("/")))
    convention = entry.get(ENTRY_CONVENTION_KEY)
    if isinstance(convention, str) and convention and not _in_tree(ctx, convention):
        found.append(_finding(record, "missing-convention", name, convention))
    return found


def _needs_reachability(record: Any) -> bool:
    """True unless test_required is false or a change_target is present and names no `code`."""
    if record.get("test_required") is False:
        return False
    target = record.get("change_target")
    if target is None:
        return True
    return "code" in ([target] if isinstance(target, str) else target)


def _record_findings(record: Any, spec: list) -> list[Finding]:
    """Record-level findings: not-grounded, and no-reachability for a judged code record."""
    opened = record.get(OPENED_FILES_KEY)
    found = [] if isinstance(opened, list) and opened else [_finding(record, "not-grounded")]
    angles = {item.get("angle") for item in spec if isinstance(item, dict)}
    if "reachability" not in angles and _needs_reachability(record):
        found.append(_finding(record, "no-reachability"))
    return found


def evaluate_record(ctx: Any, record: Any) -> list[Finding]:
    """Judge a code-aware design against the tree; empty for a legacy design or a record with no test_spec."""
    spec = record.get("test_spec")
    if not isinstance(spec, list) or not spec:
        return []
    if is_legacy_design(record):
        return [_finding(record, "unmarked-design")] if intent_entries(record) is not None else []
    found = _record_findings(record, spec)
    declared = get_declared_files(record)
    intent = intent_entries(record)
    clauses = None if intent is None else {normalise_clause(str(item.get("clause", ""))) for item in intent}
    for entry in (item for item in spec if isinstance(item, dict)):
        name = str(entry.get("name", ""))
        found += _code_file_findings(ctx, record, entry, name, declared)
        found += _clause_findings(record, entry, name, clauses)
        found += _location_findings(ctx, record, entry, name)
    return found
