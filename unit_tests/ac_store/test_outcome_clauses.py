"""
MODULE: unit_tests/ac_store/test_outcome_clauses.py
COVERS: ACD-2500b-1-i
GOAL: Red-first specification of the outcome-clause splitter and normaliser, the
    shared parser behind the "test intent coverage" rule family
    (scripts/ac_store/_test_intent.py: outcome_clauses, normalise_clause,
    intent_entries, design_pending; architect note G3, sections 1 and 6).
BUSINESS CONTEXT: A silently skipped Then/And clause becomes "no test needed" by
    omission. Every consumer (the rule check, approval, the gate) must therefore find
    the SAME clauses in the criteria and compare them the SAME way. Conflict 1 of the
    note: the ticket generator's own Then matcher has no And and no continuation lines,
    so `outcome_clauses` is the single parser for intent. Conflict 2: "exact or
    whitespace-normalised" breaks when a fifth clause is appended (the old last
    clause's trailing "." becomes ","), so `normalise_clause` also drops one trailing
    "," ";" or ".".
ARCHITECTURE: The module does not exist yet: every test here is red with
    ModuleNotFoundError (an ABSENCE red, the correct state for code that is not
    written). The module is imported inside each test through `_mod()`, so one missing
    file fails each test on its own instead of breaking collection. Fixtures come from
    the shared builders (intent_criteria) and from the real AC file ACD-2500b-1.yaml,
    never from a hand-typed record.

    Not asserted on purpose: whether `outcome_clauses` itself keeps or drops the
    trailing punctuation (the note leaves it to the normaliser), the keyword's letter
    case, and the behaviour for a non-string criteria.
"""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _rule_check_fixtures import REPO_ROOT, SCRIPTS_DIR, intent_criteria, intent_record  # noqa: E402

AC_FILE = (
    REPO_ROOT / "docs" / "acceptance-criteria" / "ac-driven-dev"
    / "ACD-2500-right-job-right-agent" / "ACD-2500b-1.yaml"
)


def _mod():
    """Import scripts/ac_store/_test_intent.py (absent until ticket 21 is built)."""
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    return importlib.import_module("_test_intent")


def _normalised(criteria: str) -> list[str]:
    mod = _mod()
    return [mod.normalise_clause(text) for text in mod.outcome_clauses(criteria)]


# --------------------------------------------------------------------------
# normalise_clause
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("the result is failed.", "the result is failed"),
        ("the result is failed,", "the result is failed"),
        ("the result is failed;", "the result is failed"),
        ("the result is failed", "the result is failed"),
        ("  the   result\n   is\tfailed  ", "the result is failed"),
        ("a, b; c.", "a, b; c"),
        ("it reports v1.2 as stale.", "it reports v1.2 as stale"),
    ],
)
def test_normalise_collapses_whitespace_and_drops_one_trailing_punctuation(raw, expected):
    # covers: ACD-2500b-1-i
    # angle: boundary
    """Whitespace runs collapse to one space, the ends are stripped, and one trailing
    ',' ';' or '.' is dropped; punctuation inside the clause stays (a 'v1.2' or a
    'a, b' must not be cut)."""
    mod = _mod()

    assert mod.normalise_clause(raw) == expected


def test_normalise_is_idempotent():
    # covers: ACD-2500b-1-i
    # angle: boundary
    """Normalising a normalised clause changes nothing, so a stored entry that was
    already written in normal form still matches."""
    mod = _mod()
    once = mod.normalise_clause("  each entry names   its clause,  ")

    assert mod.normalise_clause(once) == once == "each entry names its clause"


# --------------------------------------------------------------------------
# outcome_clauses
# --------------------------------------------------------------------------
def test_outcome_clauses_are_the_text_after_each_then_and_keyword():
    # covers: ACD-2500b-1-i
    # angle: criterion
    """One Then and two And lines are three clauses, in order, without the keyword."""
    clauses = ["the first outcome holds", "the second outcome holds", "the third outcome holds"]

    found = _normalised(intent_criteria(clauses))

    assert found == clauses
    assert not any(re.match(r"(?i)(then|and)\b", text) for text in found)


def test_outcome_clauses_join_continuation_lines():
    # covers: ACD-2500b-1-i
    # angle: boundary
    """A clause wrapped over several lines (the store's own criteria are wrapped at 90
    columns) is ONE clause, the continuation joined with single spaces."""
    criteria = (
        "Given a record,\n"
        "When the planner enriches it,\n"
        "Then the record carries one entry per clause,\n"
        "And each entry names its clause, states needs-test yes or no, and gives a one-sentence\n"
        "  reason,\n"
        "And the criteria text is byte-identical.\n"
    )

    found = _normalised(criteria)

    assert found == [
        "the record carries one entry per clause",
        "each entry names its clause, states needs-test yes or no, and gives a one-sentence reason",
        "the criteria text is byte-identical",
    ]


def test_and_before_the_first_then_is_not_an_outcome_clause():
    # covers: ACD-2500b-1-i
    # angle: boundary
    """An `And` that continues the Given or When is a precondition, not an outcome. A
    splitter that counts every And line would demand an entry for it and report a
    stale clause nobody can write."""
    criteria = (
        "Given a record whose criteria carry 4 outcome clauses,\n"
        "  And a second precondition,\n"
        "When the rule check runs,\n"
        "  And a second action,\n"
        "Then one finding names the record,\n"
        "And the verdict is failed.\n"
    )

    found = _normalised(criteria)

    assert found == ["one finding names the record", "the verdict is failed"]


def test_criteria_without_a_then_have_no_outcome_clause():
    # covers: ACD-2500b-1-i
    # angle: boundary
    """No Then, no outcome: the empty case returns an empty list, not a crash and not a
    made-up clause."""
    mod = _mod()

    assert mod.outcome_clauses("Given a thing,\nWhen it runs,\n") == []
    assert mod.outcome_clauses("") == []


def test_keyword_inside_a_line_does_not_split_the_clause():
    # covers: ACD-2500b-1-i
    # angle: boundary
    """Only a line that STARTS with the keyword opens a clause; 'Then' or 'And' later
    in a line is ordinary text."""
    criteria = "Given x,\nWhen y,\nThen the report lists the words Then and And verbatim.\n"

    assert _normalised(criteria) == ["the report lists the words Then and And verbatim"]


def test_fifth_clause_appended_keeps_the_first_four_matching():
    # covers: ACD-2500b-1-i
    # angle: boundary
    """The AC's own scenario: a fifth outcome clause is added. The old last clause's
    trailing '.' becomes ',', and it must still match its stored entry (otherwise the
    next run reports a false stale entry next to the true missing one)."""
    four = ["alpha holds", "beta holds", "gamma holds", "delta holds"]
    five = [*four, "epsilon holds"]

    before = _normalised(intent_criteria(four))
    after = _normalised(intent_criteria(five))

    assert len(before) == 4
    assert len(after) == 5
    assert after[:4] == before
    assert after[4] == "epsilon holds"


def test_real_ac_criteria_split_into_one_clause_per_outcome_line():
    # covers: ACD-2500b-1-i
    # angle: real_artifact
    """The criteria of the real record ACD-2500b-1 (read off disk, as the store holds it):
    the Then and each And is one clause; a wrapped And line is joined, not split; the
    indented '(1) ...' lines under the Given are preconditions, not clauses."""
    mod = _mod()
    criteria = yaml.safe_load(AC_FILE.read_text(encoding="utf-8"))["criteria"]
    lines = criteria.splitlines()
    first_then = next(i for i, line in enumerate(lines) if line.startswith("Then"))
    expected_count = sum(1 for line in lines[first_then:] if re.match(r"(Then|And)\b", line))

    clauses = mod.outcome_clauses(criteria)

    assert expected_count >= 2, "fixture sanity: the real AC has several outcome lines"
    assert len(clauses) == expected_count
    assert all("\n" not in text for text in clauses)
    joined = [mod.normalise_clause(text) for text in clauses]
    assert any(text.endswith("gives a one-sentence reason") for text in joined), joined
    assert not any("the check reports that 4 records were checked" in text for text in joined)


# --------------------------------------------------------------------------
# intent_entries / design_pending
# --------------------------------------------------------------------------
def test_intent_entries_returns_the_list_or_none():
    # covers: ACD-2500b-1-i
    # angle: criterion
    """A record carrying test_intent yields its entries; a record without the field yields
    None (the 'not evaluated' answer for legacy records, never an empty list)."""
    mod = _mod()
    with_intent = intent_record("ACD-9990a-1", ["alpha holds", "beta holds"])
    without = {k: v for k, v in with_intent.items() if k != "test_intent"}

    entries = mod.intent_entries(with_intent)

    assert entries is not None and [e["clause"] for e in entries] == ["alpha holds", "beta holds"]
    assert mod.intent_entries(without) is None


@pytest.mark.parametrize(
    ("record", "expected"),
    [
        ({"test_intent": [{"clause": "a", "needs_test": True, "reason": "r"}]}, True),
        ({"test_intent": [{"clause": "a", "needs_test": True, "reason": "r"}], "test_spec": []}, True),
        ({"test_intent": [{"clause": "a", "needs_test": True, "reason": "r"}], "test_spec": None}, True),
        (
            {
                "test_intent": [{"clause": "a", "needs_test": True, "reason": "r"}],
                "test_spec": [{"name": "test_a", "target_dir": "unit_tests/"}],
            },
            False,
        ),
        ({"test_spec": [{"name": "test_a", "target_dir": "unit_tests/"}]}, False),
        ({}, False),
        ({"test_intent": []}, False),
    ],
)
def test_design_pending_is_intent_without_a_design(record, expected):
    # covers: ACD-2500b-1-i
    # angle: boundary
    """ADR-071 section 3: pending means a NON-EMPTY test_intent and a test_spec that is
    absent, null or empty. Intent plus a design, a design alone (legacy), nothing at
    all and an empty intent list are all not pending."""
    mod = _mod()

    assert mod.design_pending(record) is expected
