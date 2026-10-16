"""
MODULE: _rc_test_intent
GOAL: Rule family "test intent coverage": every outcome clause of a record that carries
    test_intent has exactly one intent entry, and every entry names a clause that is still
    in the criteria. A clause with no entry, an entry for a vanished clause and a clause with
    two entries are each reported; nothing is repaired.
BUSINESS CONTEXT: ACD-2500b-1-i (ADR-071). A silently skipped Then/And clause becomes "no test
    needed" by omission. The IT PO records one intent entry per clause, including the clauses
    that need no test; this family judges COVERAGE only (the shape of an entry is the record
    schema's job). A failing itpo stage goes back to the IT PO through the existing verdict.
ARCHITECTURE: One family object (NAME, pure `evaluate_record`), registered in
    requirement_rule_check.FAMILIES and deployed flat (scripts/build_phases_ac_store_rc.py).
    Clauses come from `_test_intent.outcome_clauses`, entry texts from
    `_test_intent.normalise_clause`; comparison is on the normalised text. Every finding is
    `needs a decision` with `detail = {"kind": "missing" | "stale" | "duplicate", "clause": text}`
    and no line; the subject is `<kind>:<normalised clause>`, so each clause has its own
    finding. Only a record whose test_intent is a non-empty list is evaluated (legacy records
    with a test_spec and records with neither are never judged here).

DECISION HISTORY:
  - 2026-10-14 [python-coder/ACD-2500b-1-i]: Created per the G3 architect note, section 3.
    "Exactly one entry per clause" is enforced with a `duplicate` kind (the note's default).
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from _rc_report import DISPOSITION_DECISION, FAMILY_TEST_INTENT, Finding
from _test_intent import intent_entries, normalise_clause, outcome_clauses

NAME = FAMILY_TEST_INTENT

_MESSAGES = {
    "missing": 'outcome clause has no test_intent entry: "{}"',
    "stale": 'test_intent entry names a clause that no longer appears in criteria (stale): "{}"',
    "duplicate": 'more than one test_intent entry for the clause: "{}"',
}


def _finding(record: Any, kind: str, text: str) -> Finding:
    """One `needs a decision` finding of *kind* for the clause *text*."""
    return Finding.for_record(
        record, NAME, DISPOSITION_DECISION, _MESSAGES[kind].format(text),
        subject=f"{kind}:{normalise_clause(text)}", detail={"kind": kind, "clause": text},
    )


def evaluate_record(ctx: Any, record: Any) -> list[Finding]:
    """Report missing, stale and duplicate intent entries; empty for a record without intent."""
    entries = intent_entries(record)
    if entries is None:
        return []
    clauses = {normalise_clause(text): text for text in outcome_clauses(record.get("criteria"))}
    per_clause = Counter(normalise_clause(str(entry.get("clause", ""))) for entry in entries)
    found = [_finding(record, "missing", text) for key, text in clauses.items() if key not in per_clause]
    found += [
        _finding(record, "duplicate", clauses[key]) for key, count in per_clause.items() if count > 1 and key in clauses
    ]
    seen: set[str] = set()
    for entry in entries:
        text = str(entry.get("clause", ""))
        key = normalise_clause(text)
        if key not in clauses and key not in seen:
            seen.add(key)
            found.append(_finding(record, "stale", text))
    return found
