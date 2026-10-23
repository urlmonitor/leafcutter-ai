"""
MODULE: unit_tests/ac_store/test_acd_2500b_1_ii.py
COVERS: ACD-2500b-1-ii
GOAL: Pin the behaviour of the test-intent clause reader (scripts/ac_store/_test_intent.py,
    outcome_clauses) across ticket 08, which handles the no-match case before the step-line
    match's groups are read, so the type checker's union-attr finding at lines 64-65 goes away.
DESIGN: a no-behaviour-change fix. The expected clause lists are today's outputs, pinned
    literally; the type checker run itself is the proof of the finding (test_intent needs_test
    false), so no test here runs it.
HONEST LIMIT: these tests guard the reader's results; they cannot observe a static typing
    finding.
RED STATE: green at baseline by design. The criterion, boundary and discrimination tests pin
    behaviour that exists today and must survive the fix; the discrimination test goes red
    under each must_catch wrong version (see its docstring), which the test-writer verified by
    running it against those versions.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for _extra in (HERE, REPO / "scripts" / "ac_store"):
    if str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))

from _rule_check_fixtures import (  # noqa: E402
    FAMILY_TEST_INTENT,
    cli_argv,
    findings_for,
    hierarchy,
    intent_entry,
    make_store,
    run_cli_subprocess,
)
from _test_intent import outcome_clauses  # noqa: E402

THEN_AND = "Given a table,\nWhen the job runs,\nThen one row is written,\nAnd the count is 1.\n"
THEN_AND_CLAUSES = ["one row is written,", "the count is 1."]
# A prose line before any step keyword, a Then header with "-" bullets, a wrapped bullet, and an
# And whose text wraps onto a continuation line.
MIXED = (
    "Background: orders exist in the table.\n"
    "Given a table,\n"
    "When the job runs,\n"
    "Then the report lists:\n"
    "  - one row per order,\n"
    "  - a total line that\n"
    "    wraps onto a second line,\n"
    "And the count is\n"
    "  carried over to the summary.\n"
)
MIXED_CLAUSES = [
    "one row per order,",
    "a total line that wraps onto a second line,",
    "the count is carried over to the summary.",
]


def test_outcome_clauses_unchanged_for_then_and():
    # covers: ACD-2500b-1-ii
    # angle: criterion
    """outcome_clauses on a Then/And criteria returns exactly today's two clauses, in order."""
    assert outcome_clauses(THEN_AND) == THEN_AND_CLAUSES


@pytest.mark.parametrize("criteria", [
    "Given a table,\nWhen the job runs,\n",
    "This record has plain prose only.\nNo step keyword starts any line here.\n",
    None,
    42,
], ids=["given-when-only", "plain-prose", "none", "int"])
def test_no_outcome_clause_returns_empty_without_error(criteria):
    # covers: ACD-2500b-1-ii
    # angle: boundary
    """Criteria with Given/When only, plain prose lines that match no step keyword, and a
    non-string value each return [] and raise nothing."""
    assert outcome_clauses(criteria) == []


def test_no_match_guard_keeps_other_lines():
    # covers: ACD-2500b-1-ii
    # angle: discrimination
    """Criteria mixing non-matching lines with a Then header, '-' bullets and a wrapped
    continuation line return today's clauses unchanged. Wrong versions this catches:
    (a) a guard that returns [] at the first line the step pattern does not match (the prose
    first line); (b) a guard that skips non-matching lines, dropping the bullets and the
    continuation lines; (c) reading match.group(...) without a guard, which raises
    AttributeError on the first non-matching line."""
    assert outcome_clauses(MIXED) == MIXED_CLAUSES


def test_test_intent_reader_reachable_from_rule_check_cli(tmp_path):
    # covers: ACD-2500b-1-ii
    # angle: reachability
    """Entry point: `python scripts/ac_store/requirement_rule_check.py` as a subprocess on a tmp
    store. The record with the Then/And criteria above and one test_intent entry per clause gets
    no 'test intent coverage' finding; the control record with one entry missing gets exactly
    one 'missing' finding, naming the clause it lacks."""
    entries = [intent_entry(clause.rstrip(",.")) for clause in THEN_AND_CLAUSES]
    records = hierarchy("ACD-9990", 2, child={
        1: {"criteria": THEN_AND, "test_intent": entries},
        2: {"criteria": THEN_AND, "test_intent": entries[:1]},
    })
    store = make_store(tmp_path, records)

    run = run_cli_subprocess(cli_argv(store, stage="itpo"), cwd=store.repo_root)

    assert findings_for(run.report, "ACD-9990a-1", FAMILY_TEST_INTENT) == [], run.report["findings"]
    gap = findings_for(run.report, "ACD-9990a-2", FAMILY_TEST_INTENT)
    assert len(gap) == 1, run.report["findings"]
    assert gap[0]["detail"]["kind"] == "missing", gap[0]
    assert "the count is 1" in gap[0]["message"], gap[0]["message"]
