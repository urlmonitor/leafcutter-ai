"""
MODULE: unit_tests/ac_store/test_outcome_clauses_scenarios.py
COVERS: ACD-2500b-1-i
GOAL: Red-first tests for review finding M-1: `_test_intent.outcome_clauses` mis-splits the store's
    real multi-scenario criteria. Pinned behaviour:
    * a Given or When line after a Then ENDS the current clause (even with no blank line) and opens a
      new scenario whose And / But lines are preconditions, NOT outcomes, until that scenario's own Then;
    * `But` lines inside a Then block are outcome clauses, exactly like And (a `But` in a Given block
      is a precondition);
    * `Then:` followed by bullet lines yields one clause per bullet, the leading `-` and whitespace
      stripped (continuation lines of a bullet join to it);
    * a leading comma after the keyword ("And, as a paired ...") is stripped.
BUSINESS CONTEXT: ADR-071. The rule check, approval and the gate all compare clauses through this one
    parser; a precondition counted as an outcome makes every multi-scenario record (the reviewer counted
    778) report a false "missing" clause.
ARCHITECTURE: synthetic exact-list tests per rule, then tests over REAL criteria read off disk (selected
    by structure at run time, never by a hard-coded count). Existing tests in test_outcome_clauses.py are
    consistent with all of this: none asserts how a second scenario's And lines are treated (checked: the
    single-scenario, blank-line, continuation, "And before the first Then" and keyword-inside-a-line
    tests stay valid).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _rule_check_fixtures import REPO_ROOT, SCRIPTS_DIR  # noqa: E402

STORE = REPO_ROOT / "docs" / "acceptance-criteria"
_KEYWORD = re.compile(r"(Given|When|Then|And|But)\b[,:]?\s*(.*)")


def _split(criteria: str) -> list[str]:
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    import _test_intent  # noqa: PLC0415

    return [_test_intent.normalise_clause(c) for c in _test_intent.outcome_clauses(criteria)]


def test_given_or_when_after_then_opens_a_scenario_whose_and_lines_are_not_outcomes():
    # covers: ACD-2500b-1-i
    # angle: criterion
    """Two scenarios: the second one's `And` (before its own Then) is a precondition.

    Variant A has a blank line between the scenarios, variant B none (the Given directly follows the
    wrapped last clause, which must NOT absorb it as a continuation line), variant C opens the second
    scenario with a When. Exactly four outcome clauses each, in order.
    """
    wanted = ["o1 holds", "o2 holds", "o3 holds", "o4 holds"]
    scenario_a = (
        "Given a,\nWhen b,\nThen o1 holds,\nAnd o2 holds.\n\n"
        "Given c,\nAnd the precondition d,\nWhen e,\nThen o3 holds,\nAnd o4 holds.\n"
    )
    scenario_b = (
        "Given a,\nWhen b,\nThen o1 holds,\nAnd o2\n  holds.\n"
        "Given c,\nAnd the precondition d,\nWhen e,\nThen o3 holds,\nAnd o4 holds.\n"
    )
    scenario_c = (
        "Given a,\nWhen b,\nThen o1 holds,\nAnd o2 holds.\n"
        "When c happens,\nAnd the precondition d,\nThen o3 holds,\nAnd o4 holds.\n"
    )
    assert _split(scenario_a) == wanted
    assert _split(scenario_b) == wanted
    assert _split(scenario_c) == wanted


def test_but_is_an_outcome_inside_a_then_block_and_a_precondition_before_it():
    # covers: ACD-2500b-1-i
    # angle: boundary
    """`But` after a Then is an outcome clause like And; `But` in a Given block is not.

    Control row in the same criteria: the Given-block `But` and the Given-block `And` are both left out.
    """
    criteria = (
        "Given a record,\nBut the folder is empty,\nAnd it was misspelled,\nWhen the check runs,\n"
        "Then the result is failed,\nBut the report is still written,\nAnd it names the location.\n"
    )
    assert _split(criteria) == [
        "the result is failed",
        "the report is still written",
        "it names the location",
    ]


def test_then_colon_with_bullets_yields_one_clause_per_bullet():
    # covers: ACD-2500b-1-i
    # angle: boundary
    """`Then:` followed by bullet lines: one clause per bullet, the `-` and indentation stripped, a
    wrapped bullet joined to itself, and the next And still an ordinary clause. Exactly three."""
    criteria = (
        "Given a record,\nWhen it is reviewed,\nThen:\n"
        "  - the first bullet holds,\n"
        "  - the second bullet\n    wraps over two lines,\n"
        "And the closing outcome holds.\n"
    )
    assert _split(criteria) == [
        "the first bullet holds",
        "the second bullet wraps over two lines",
        "the closing outcome holds",
    ]


def test_leading_comma_after_the_keyword_is_stripped():
    # covers: ACD-2500b-1-i
    # angle: boundary
    """"And, as a paired ..." and "Then, the ..." yield the text after the comma; a comma INSIDE the
    clause is kept."""
    criteria = "Given a,\nWhen b,\nThen, the first holds, in full,\nAnd, as a paired input, the second holds.\n"
    assert _split(criteria) == ["the first holds, in full", "as a paired input, the second holds"]


def _real_criteria() -> list[tuple[str, str]]:
    found = []
    for path in sorted(STORE.rglob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        if "criteria:" not in text:
            continue
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError:
            continue
        if isinstance(data, dict) and isinstance(data.get("criteria"), str):
            found.append((str(data.get("id")), data["criteria"]))
    return found


def _expected_by_phase(criteria: str) -> tuple[int, list[str]]:
    """Independent reading of the same rule: (outcome clause count, precondition first lines)."""
    phase, count, preconditions = "given", 0, []
    for raw in criteria.splitlines():
        match = _KEYWORD.match(raw.strip())
        if not match:
            continue
        word, rest = match.groups()
        if word in ("Given", "When"):
            phase = "given"
        elif word == "Then":
            phase, count = "then", count + 1
        elif phase == "then":
            count += 1
        else:
            preconditions.append(" ".join(rest.split()))
    return count, [p for p in preconditions if p]


def test_real_multi_scenario_criteria_never_count_a_precondition():
    # covers: ACD-2500b-1-i
    # angle: real_artifact
    """Every real record whose criteria hold a Given/When AFTER a Then (found by structure, read off
    disk, never counted by hand) splits into exactly its outcome clauses and none of its later-scenario
    preconditions. The failing ids are listed (first ten) so a miss names its records."""
    multi = []
    for record_id, criteria in _real_criteria():
        lines = [raw.strip() for raw in criteria.splitlines()]
        if any(ln.startswith(("- ", "* ")) for ln in lines):
            continue  # bullet lists are pinned by their own test; a header-plus-bullets count is not
        first_then = next((i for i, ln in enumerate(lines) if re.match(r"Then\b", ln)), None)
        if first_then is not None and any(re.match(r"(Given|When)\b", ln) for ln in lines[first_then:]):
            multi.append((record_id, criteria))
    assert multi, "the shipped store must hold multi-scenario criteria"

    wrong = []
    for record_id, criteria in multi:
        want_count, preconditions = _expected_by_phase(criteria)
        clauses = _split(criteria)
        leaked = [p for p in preconditions if any(c.startswith(p.rstrip(",;. ")) for c in clauses)]
        if len(clauses) != want_count or leaked:
            wrong.append(f"{record_id}: got {len(clauses)} want {want_count} leaked {len(leaked)}")
    assert wrong == [], f"{len(wrong)} of {len(multi)} multi-scenario records mis-split: {wrong[:10]}"


def test_real_bullet_and_comma_records_split_as_pinned():
    # covers: ACD-2500b-1-i
    # angle: real_artifact
    """Two real records read off disk. ACD-1200b-3: each `Then ... covers:` bullet is its own clause (the
    leading `-` gone, no clause holds two bullets). ACD-2500a-1-i: the `And, as a paired acceptable
    input` clause starts with "as a paired acceptable input" (the comma is gone)."""
    by_id = dict(_real_criteria())

    bullets = [
        " ".join(ln.strip()[1:].split()) for ln in by_id["ACD-1200b-3"].splitlines() if ln.strip().startswith("- ")
    ]
    assert len(bullets) == 4, bullets
    clauses = _split(by_id["ACD-1200b-3"])
    for bullet in bullets:
        assert bullet in clauses, f"bullet is not its own clause: {bullet!r}"
    assert not any(c.startswith("-") for c in clauses), clauses
    assert not any(sum(b in c for b in bullets) > 1 for c in clauses), "a clause holds two bullets"

    paired = [c for c in _split(by_id["ACD-2500a-1-i"]) if "paired acceptable input" in c]
    assert len(paired) == 1 and paired[0].startswith("as a paired acceptable input"), paired
