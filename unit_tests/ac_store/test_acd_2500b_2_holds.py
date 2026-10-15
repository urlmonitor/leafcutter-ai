"""
MODULE: unit_tests/ac_store/test_acd_2500b_2_holds.py
COVERS: ACD-2500b-2
GOAL: Second half of the ACD-2500b-2 (ticket 23) red tests, split by concern from
    test_acd_2500b_2.py: the closed hold-reason vocabulary, the coverage boundaries of the approval
    hold (decided by the per-entry clause key, never by test names), the registry that later
    gates append to, and the text-mode output of the approval step.
ARCHITECTURE: `approval_hold_reason(record) -> str | None` and `APPROVAL_HOLD_CHECKS` (a tuple of
    callables, record -> reason | None) live in scripts/ac_store/_approval_holds.py;
    `uncovered_needs_test_clauses(record)` lives in _test_intent.py (note section 1). Coverage is
    "a needs_test true clause has a test_spec entry whose ENTRY_CLAUSE_KEY normalises to it"
    (ticket 22's note on proves_clause). Records come from _acd_2500b_approval_fixtures.
RED STATE: _approval_holds and uncovered_needs_test_clauses do not exist (absence reds); the
    constant HOLD_REASON_TEST_DESIGN_PENDING is not yet defined; `--json` and the `held <id>: <reason>`
    line do not exist (assertion reds from the real CLI).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _acd_2500b_approval_fixtures import (  # noqa: E402
    PENDING,
    TWO,
    build,
    design_for,
    entry,
    goal,
    holds_module,
    json_of,
    read_bytes,
    reviewed_intent,
    reviewed_no_tests,
    run_approve,
)

_VOCABULARY = (
    "missing file targets",
    "missing test contract",
    "test design pending",
    "reference file pending",
    "file finding undecided",
)


def test_hold_reason_vocabulary_is_one_closed_list():
    # covers: ACD-2500b-2
    # angle: boundary
    """HOLD_REASONS keeps its five values in order, and "test design pending" is the NAMED constant.

    The literal is replaced in place by HOLD_REASON_TEST_DESIGN_PENDING (exported in __all__);
    order and the other four values are unchanged, so no gate keeps a local list.
    """
    import _impl_readiness_gate as gate  # noqa: PLC0415

    assert gate.HOLD_REASONS == _VOCABULARY
    assert gate.HOLD_REASON_TEST_DESIGN_PENDING == PENDING
    assert gate.HOLD_REASONS[2] == gate.HOLD_REASON_TEST_DESIGN_PENDING
    assert "HOLD_REASON_TEST_DESIGN_PENDING" in gate.__all__


def _covers(clause: str, **extra) -> dict:
    return entry(f"test_for_{abs(hash(clause)) % 1000}", clause, **extra)


def test_approval_hold_boundaries_follow_the_clause_key():
    # covers: ACD-2500b-2
    # angle: boundary
    """approval_hold_reason decides on the clause link, and on nothing else.

    Rows (label: expected): both clauses covered: None. One of two covered: held (an exact "both
    needed", not "at least one"). A needs_test false clause with no entry: not needed, None. Names
    that mention the clause but no clause key: held (coverage is never read from names). A link that
    differs only in trailing punctuation and spacing: still covers. A stale link (names a clause
    that is not in criteria) does not cover the real one. Intent with every needs_test false and no
    design: held (note conflict 11). No intent at all: never held here.
    """
    holds = holds_module()
    first, second = TWO
    rows = {
        "both covered": (reviewed_intent("ZZB-4a-1", spec=design_for(TWO)), None),
        "one of two covered": (reviewed_intent("ZZB-4a-2", spec=design_for([first])), PENDING),
        "false clause uncovered": (
            reviewed_intent(
                "ZZB-4a-3",
                entries=[
                    {"clause": first, "needs_test": True, "reason": "r"},
                    {"clause": second, "needs_test": False, "reason": "r"},
                ],
                spec=design_for([first]),
            ),
            None,
        ),
        "names but no key": (
            reviewed_intent(
                "ZZB-4a-4",
                spec=[
                    {"name": f"test_{first.replace(' ', '_')}", "description": first, "target_dir": "unit_tests/x/"},
                    {"name": f"test_{second.replace(' ', '_')}", "description": second, "target_dir": "unit_tests/x/"},
                ],
            ),
            PENDING,
        ),
        "key differs by punctuation and spacing": (
            reviewed_intent(
                "ZZB-4a-5",
                spec=[
                    _covers(f"  {first}.  "),
                    _covers(second.replace(" ", "  ") + ";"),
                ],
            ),
            None,
        ),
        "stale link": (
            reviewed_intent("ZZB-4a-6", spec=[*design_for([first]), _covers("a clause that is not in criteria")]),
            PENDING,
        ),
        "all needs_test false, no design": (
            reviewed_intent(
                "ZZB-4a-7",
                entries=[{"clause": c, "needs_test": False, "reason": "r"} for c in TWO],
            ),
            PENDING,
        ),
        "no intent": (reviewed_no_tests("ZZB-4a-8"), None),
    }
    wrong = {label: holds.approval_hold_reason(rec) for label, (rec, want) in rows.items() if holds.approval_hold_reason(rec) != want}
    assert wrong == {}, f"unexpected hold reasons (label -> got): {wrong}"


def test_uncovered_needs_test_clauses_lists_exactly_the_gap():
    # covers: ACD-2500b-2
    # angle: boundary
    """uncovered_needs_test_clauses returns the needs_test true clauses with no linked entry, in order.

    One clause covered, one not: exactly [second]. Both covered: []. A needs_test false clause is
    never listed. Compared after the one normalisation, so trailing punctuation does not matter.
    """
    from _test_intent import normalise_clause, uncovered_needs_test_clauses  # noqa: PLC0415

    first, second = TWO
    partial = reviewed_intent("ZZB-5a-1", spec=design_for([first]))
    assert [normalise_clause(c) for c in uncovered_needs_test_clauses(partial)] == [second]
    assert uncovered_needs_test_clauses(reviewed_intent("ZZB-5a-2", spec=design_for(TWO))) == []
    only_false = reviewed_intent(
        "ZZB-5a-3", entries=[{"clause": c, "needs_test": False, "reason": "r"} for c in TWO]
    )
    assert uncovered_needs_test_clauses(only_false) == []


def test_hold_checks_registry_is_open_for_later_gates_and_closed_on_reasons(monkeypatch):
    # covers: ACD-2500b-2
    # angle: seam
    """APPROVAL_HOLD_CHECKS is the tuple later gates append to; every emitted reason is a member.

    A check appended by a later ticket (here a stand-in returning "reference file pending") is
    consulted by approval_hold_reason; a check that returns a reason outside HOLD_REASONS is
    rejected (the vocabulary stays closed). Control: with the original tuple the designed record is
    not held.
    """
    import pytest  # noqa: PLC0415

    holds = holds_module()
    designed = reviewed_intent("ZZB-6a-1", spec=design_for(TWO))
    assert isinstance(holds.APPROVAL_HOLD_CHECKS, tuple) and holds.APPROVAL_HOLD_CHECKS
    assert all(callable(check) for check in holds.APPROVAL_HOLD_CHECKS)
    assert holds.approval_hold_reason(designed) is None

    monkeypatch.setattr(holds, "APPROVAL_HOLD_CHECKS", (*holds.APPROVAL_HOLD_CHECKS, lambda _r: "reference file pending"))
    assert holds.approval_hold_reason(designed) == "reference file pending"

    monkeypatch.setattr(holds, "APPROVAL_HOLD_CHECKS", (lambda _r: "an invented reason",))
    with pytest.raises((AssertionError, ValueError)):
        holds.approval_hold_reason(designed)


def test_text_mode_keeps_existing_lines_and_adds_one_held_line(tmp_path):
    # covers: ACD-2500b-2
    # angle: seam
    """Text mode: the existing "promoted" line is byte-identical, plus one `held <id>: <reason>` line.

    Consumer: the existing ACD-1200b-5 tests read the "promoted ... readiness reviewed -> approved"
    line. A held record prints NO "promoted" line, and a record outside the batch is not touched.
    """
    records = [
        goal("ZZB-7", ["ZZB-7a-1", "ZZB-7a-2"]),
        reviewed_intent("ZZB-7a-1"),
        reviewed_no_tests("ZZB-7a-2"),
        reviewed_intent("ZZB-7a-9"),
    ]
    store = build(tmp_path, records)
    outside = read_bytes(store, "ZZB-7a-9")

    run = run_approve(store, "--goal", "ZZB-7")
    lines = run.stdout.splitlines()

    assert "promoted ZZB-7a-2 readiness reviewed -> approved" in lines, run.stdout
    assert f"held ZZB-7a-1: {PENDING}" in lines, run.stdout
    assert not any(line.startswith("promoted ZZB-7a-1") for line in lines), run.stdout
    assert read_bytes(store, "ZZB-7a-9") == outside


def test_json_mode_prints_one_document_and_nothing_else(tmp_path):
    # covers: ACD-2500b-2
    # angle: boundary
    """`--json` is the whole of stdout: no "promoted" or "held" text lines alongside it.

    Empty and many: a goal whose leaves are all held reports approved == [] (exact), and one with
    three promotable leaves reports exactly three approved and held == [].
    """
    all_held = build(tmp_path / "held", [goal("ZZB-8", ["ZZB-8a-1"]), reviewed_intent("ZZB-8a-1")])
    report = json_of(run_approve(all_held, "--goal", "ZZB-8", "--json"))
    assert report["approved"] == [] and len(report["held"]) == 1

    ids = [f"ZZB-9a-{n}" for n in (1, 2, 3)]
    many = build(tmp_path / "many", [goal("ZZB-9", ids), *[reviewed_no_tests(i) for i in ids]])
    report = json_of(run_approve(many, "--goal", "ZZB-9", "--json"))
    assert sorted(report["approved"]) == ids and report["held"] == []
