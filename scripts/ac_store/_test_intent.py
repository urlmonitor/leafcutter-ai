"""
MODULE: _test_intent
GOAL: The one parser and the shared predicates for test intent and test-design provenance:
    split a record's criteria into outcome clauses, compare clauses under one normalisation,
    read the test_intent entries, and answer "is the design pending" and "is the design legacy".
BUSINESS CONTEXT: ACD-2500b-1-i and ACD-2500c-3 (ADR-071). A silently skipped Then/And clause
    becomes "no test needed" by omission, so every consumer (the requirement rule check,
    approval, the readiness gate, the by-author report) must find the SAME clauses and compare
    them the SAME way. test_intent is not a test contract; legacy designs are kept and told
    apart from code-aware ones only by the missing authorship mark, through `is_legacy_design`.
ARCHITECTURE: Pure functions and name constants, no I/O. `outcome_clauses` is the single clause
    parser for intent (the ticket generator's own Then matcher has no And and no continuation
    lines and is left alone). `normalise_clause` is the only matching rule: whitespace runs
    collapse to one space, the ends are stripped, and ONE trailing "," ";" or "." is dropped
    (a fifth clause appended later turns the old last clause's "." into ","). The constants name
    the schema properties added by ACD-2500c-3 so no reader hand-types one; a lockstep test
    asserts each is a declared property of config/ac_store_schema.json. Deployed flat into
    <root>/scripts/ac_store/ (see scripts/build_phases_ac_store_rc.py).
"""

from __future__ import annotations

import re
from typing import Any

ENTRY_CLAUSE_KEY = "proves_clause"
ENTRY_CODE_FILE_KEY = "code_file"
ENTRY_TO_BE_CREATED_KEY = "to_be_created"
ENTRY_CONVENTION_KEY = "convention_test_file"
AUTHORSHIP_KEY = "test_design_authorship"
OPENED_FILES_KEY = "test_design_opened_files"

_OUTCOME_LINE = re.compile(r"(Then|And)\b\s*(.*)")
_TRAILING_MARKS = ",;."


def outcome_clauses(criteria: Any) -> list[str]:
    """Return the outcome clauses of *criteria*: the text after each ``Then`` and each ``And``
    that follows the first ``Then``, continuation lines joined with single spaces.

    An ``And`` before the first ``Then`` continues the Given or When and is not an outcome.
    A blank line ends the clause being collected. A non-string *criteria* has no clauses.
    """
    if not isinstance(criteria, str):
        return []
    clauses: list[list[str]] = []
    seen_then = False
    collecting = False
    for line in criteria.splitlines():
        text = line.strip()
        match = _OUTCOME_LINE.match(text)
        if match and (seen_then or match.group(1) == "Then"):
            seen_then = True
            collecting = True
            clauses.append([match.group(2)])
        elif collecting and text:
            clauses[-1].append(text)
        else:
            collecting = False
    return [" ".join(" ".join(parts).split()) for parts in clauses]


def normalise_clause(text: str) -> str:
    """Return *text* in matching form: whitespace collapsed, ends stripped, one trailing
    ``,`` ``;`` or ``.`` dropped. Punctuation inside the clause is kept."""
    collapsed = " ".join(str(text).split())
    if collapsed and collapsed[-1] in _TRAILING_MARKS:
        collapsed = collapsed[:-1].rstrip()
    return collapsed


def intent_entries(record: Any) -> list[dict] | None:
    """Return the record's ``test_intent`` entries, or ``None`` when it carries none.

    ``None`` is the "not evaluated" answer: the field is absent, not a list, or holds no
    object entry. It is never an empty list.
    """
    intent = record.get("test_intent")
    if not isinstance(intent, list):
        return None
    entries = [entry for entry in intent if isinstance(entry, dict)]
    return entries or None


def design_pending(record: Any) -> bool:
    """True when the record has a non-empty ``test_intent`` and no ``test_spec`` (absent, null
    or empty): the intent is waiting for its test design (ADR-071)."""
    return intent_entries(record) is not None and not record.get("test_spec")


def is_legacy_design(record: Any) -> bool:
    """True when the record has a non-empty ``test_spec`` and no authorship mark.

    A record with no design is neither legacy nor code-aware. Every consumer calls this
    predicate; none re-derives it.
    """
    test_spec = record.get("test_spec")
    return isinstance(test_spec, list) and bool(test_spec) and not record.get(AUTHORSHIP_KEY)
