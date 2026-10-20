"""
MODULE: unit_tests/ac_store/test_acd_2500b_1_i.py
COVERS: ACD-2500b-1-i
GOAL: Red-first specification of ACD-2500b-1-i (ticket 21): the requirement rule check's
    new family "test intent coverage" reports an outcome clause with no test_intent entry,
    an entry for a clause that no longer exists, and a clause with two entries; and
    config/ac_store_schema.json declares test_intent so BOTH record validators accept a
    well-formed one and reject a bad one, naming the offending key.
BUSINESS CONTEXT: A silently skipped Then/And clause becomes "no test needed" by omission,
    the exact untested-Then gap the test contract exists to close (AC notes; ADR-071).
    test_intent is not a test contract: the family judges COVERAGE only, never repairs
    (disposition 'needs a decision'), and evaluates only records that carry test_intent.
ARCHITECTURE (architect note G3, sections 2 and 3):
    - The family is evaluated through the REAL CLI (requirement_rule_check.main in process,
      and the script as a subprocess for the reachability test) over records written with
      yaml.safe_dump (unit_tests/ac_store/_rule_check_fixtures.py).
    - Finding shape: rule_family "test intent coverage"; message
      `outcome clause has no test_intent entry: "<clause>"`; detail {"kind": "missing" |
      "stale" | "duplicate", "clause": <text>}; line null; at most one finding per
      (record, kind, normalised clause).
    - Schema: `test_intent` is a plain closed-items array (no oneOf, no null branch), so
      jsonschema names the bad or missing key; neither validator file is edited, and the
      two give identical verdicts (unit_tests/ac_store/_acd_2500_schema_probe.py runs both).

RED STATE: the family does not exist, so every rule-check test finds no finding under
    "test intent coverage" (an ASSERTION red); the schema does not declare test_intent, so
    both validators reject a well-formed record (an ASSERTION red).

NEGATIVE-ROW CONTROLS: a test that says "no finding" would also pass while the family is
    missing, so every such test sits next to a control record in the SAME store that must
    produce exactly one finding.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _acd_2500_schema_probe import base_record, both_verdicts, in_process_verdict  # noqa: E402
from _rule_check_fixtures import (  # noqa: E402
    FAMILY_TEST_INTENT,
    check_store,
    cli_argv,
    findings_for,
    hierarchy,
    intent_criteria,
    intent_entry,
    intent_record,
    make_store,
    run_cli_subprocess,
    snapshot_tree,
    valid_record,
)

FOUR = ["alpha is reported", "beta is reported", "gamma is reported", "delta is reported"]
THREE_ENTRIES = [intent_entry(clause) for clause in FOUR[:3]]
GAP = "ACD-9990a-1"       # 4 clauses, entries for 3: the negative row
COVERED = "ACD-9990a-2"   # one entry per clause: the control row
NOTE_QUOTE = '"delta is reported'


def _family(report: dict, record_id: str | None = None) -> list[dict]:
    return findings_for(report, record_id=record_id, rule_family=FAMILY_TEST_INTENT)


def _store_with_gap_and_control(tmp_path, *, extra: list[dict] | None = None):
    """A coherent folder: GAP (4 clauses, 3 entries) and COVERED (4 clauses, 4 entries)."""
    records = hierarchy(
        "ACD-9990", 2,
        child={
            1: {"criteria": intent_criteria(FOUR), "test_intent": [dict(e) for e in THREE_ENTRIES]},
            2: {
                "criteria": intent_criteria(FOUR),
                "test_intent": [intent_entry(clause) for clause in FOUR],
            },
        },
    )
    return make_store(tmp_path, [*records, *(extra or [])])


# --------------------------------------------------------------------------
# the family
# --------------------------------------------------------------------------
def test_clause_without_intent_entry_reported_with_quote(tmp_path):
    # covers: ACD-2500b-1-i
    # angle: criterion
    """AC clause 1: 4 outcome clauses and 3 entries yield ONE finding that names the record
    and quotes the clause that has no entry; the fully covered sibling gets none."""
    store = _store_with_gap_and_control(tmp_path)

    _, report = check_store(store, stage="itpo")

    findings = _family(report)
    assert len(findings) == 1, report["findings"]
    finding = findings[0]
    assert finding["record_id"] == GAP
    assert finding["file"] == store.rel(GAP)
    assert finding["disposition"] == "needs a decision"
    assert NOTE_QUOTE in finding["message"], finding["message"]
    assert finding["detail"]["kind"] == "missing"
    assert finding["line"] is None
    assert _family(report, COVERED) == []


def test_stale_intent_entry_reported(tmp_path):
    # covers: ACD-2500b-1-i
    # angle: criterion
    """AC clause 2: an entry that names a clause no longer in the criteria is reported as
    stale, quoting the entry's clause; the three matching entries produce nothing."""
    entries = [intent_entry(clause) for clause in FOUR[:3]]
    entries.append(intent_entry("a clause that was deleted from the criteria"))
    store = make_store(tmp_path, [intent_record("ACD-9990", FOUR[:3], entries, level="L0")])

    _, report = check_store(store, stage="itpo")

    findings = _family(report)
    assert len(findings) == 1, report["findings"]
    assert findings[0]["detail"]["kind"] == "stale"
    assert "stale" in findings[0]["message"]
    assert '"a clause that was deleted from the criteria' in findings[0]["message"]
    assert findings[0]["disposition"] == "needs a decision"
    assert findings[0]["record_id"] == "ACD-9990"


def test_reworded_clause_reports_the_missing_and_the_stale_side_separately(tmp_path):
    # covers: ACD-2500b-1-i
    # angle: boundary
    """A clause reworded after enrichment is two defects: its old entry is stale AND the new
    wording has no entry. Each gets its own finding (they dedupe on different subjects)."""
    reworded = [*FOUR[:3], "delta is now reported differently"]
    store = make_store(
        tmp_path,
        [intent_record("ACD-9990", reworded, [intent_entry(c) for c in FOUR], level="L0")],
    )

    _, report = check_store(store, stage="itpo")

    findings = _family(report)
    assert sorted(f["detail"]["kind"] for f in findings) == ["missing", "stale"], report["findings"]
    missing = next(f for f in findings if f["detail"]["kind"] == "missing")
    stale = next(f for f in findings if f["detail"]["kind"] == "stale")
    assert '"delta is now reported differently' in missing["message"]
    assert '"delta is reported' in stale["message"]


def test_added_fifth_clause_reported_next_run(tmp_path):
    # covers: ACD-2500b-1-i
    # angle: boundary
    """AC clause 3: a fully covered record is clean; after a fifth clause is added to the
    criteria, the NEXT run reports exactly that clause as having no entry. The old last
    clause's trailing '.' became ',' and must not turn into a false stale finding."""
    four_entries = [intent_entry(clause) for clause in FOUR]
    store = make_store(tmp_path, [intent_record("ACD-9990", FOUR, four_entries, level="L0")])
    _, first = check_store(store, stage="itpo")
    assert _family(first) == [], first["findings"]

    five = [*FOUR, "epsilon is reported"]
    store.write(intent_record("ACD-9990", five, four_entries, level="L0"))
    _, second = check_store(store, stage="itpo")

    findings = _family(second)
    assert len(findings) == 1, second["findings"]
    assert findings[0]["detail"]["kind"] == "missing"
    assert '"epsilon is reported' in findings[0]["message"]


def test_full_coverage_no_finding(tmp_path):
    # covers: ACD-2500b-1-i
    # angle: criterion
    """AC clause 4: a record with exactly one entry per clause produces no finding for this
    family. Control row: its gap sibling in the SAME run must still produce one, so the
    test cannot pass while the family is missing."""
    store = _store_with_gap_and_control(tmp_path)

    _, report = check_store(store, stage="itpo")

    assert _family(report, COVERED) == []
    assert len(_family(report, GAP)) == 1, "control row: the gap record must be reported"


def test_clause_matching_ignores_whitespace_and_trailing_punctuation(tmp_path):
    # covers: ACD-2500b-1-i
    # angle: boundary
    """Entries written with different spacing or a different trailing mark still match their
    clause (the one matching rule, stated once: whitespace collapsed, one trailing , ; . dropped).
    The gap sibling is the control row."""
    sloppy = [
        intent_entry("alpha   is reported."),
        intent_entry("beta is  reported;"),
        intent_entry("  gamma is reported"),
        intent_entry("delta is reported,"),
    ]
    records = hierarchy(
        "ACD-9990", 2,
        child={
            1: {"criteria": intent_criteria(FOUR), "test_intent": sloppy},
            2: {"criteria": intent_criteria(FOUR), "test_intent": [dict(e) for e in THREE_ENTRIES]},
        },
    )
    store = make_store(tmp_path, records)

    _, report = check_store(store, stage="itpo")

    assert _family(report, "ACD-9990a-1") == [], report["findings"]
    assert len(_family(report, "ACD-9990a-2")) == 1, "control row: the gap record is reported"


def test_two_entries_for_one_clause_reported_as_duplicate(tmp_path):
    # covers: ACD-2500b-1-i
    # angle: boundary
    """'Exactly one entry per clause': a second entry for the same clause is one duplicate
    finding. The single-entry clauses around it are the control rows (no finding)."""
    entries = [intent_entry(c) for c in FOUR]
    entries.append(intent_entry("beta is reported.", needs_test=False, reason="Same clause again."))
    store = make_store(tmp_path, [intent_record("ACD-9990", FOUR, entries, level="L0")])

    _, report = check_store(store, stage="itpo")

    findings = _family(report)
    assert len(findings) == 1, report["findings"]
    assert findings[0]["detail"]["kind"] == "duplicate"
    assert '"beta is reported' in findings[0]["message"]
    assert findings[0]["disposition"] == "needs a decision"


def test_records_without_test_intent_are_not_evaluated(tmp_path):
    # covers: ACD-2500b-1-i
    # angle: criterion
    """Implementation note: evaluates only records carrying test_intent. A legacy record
    (test_spec, no test_intent) and a record with neither are never judged by this family
    (ACD-2500b-3 owns legacy). The gap record in the same run is the control row."""
    legacy = valid_record(
        "ACD-9990a-3",
        criteria=intent_criteria(FOUR),
        test_spec=[{"name": "test_alpha", "target_dir": "unit_tests/ac_store/"}],
    )
    plain = valid_record("ACD-9990a-4", criteria=intent_criteria(FOUR))
    store = _store_with_gap_and_control(tmp_path, extra=[legacy, plain])

    _, report = check_store(store, stage="itpo")

    assert _family(report, "ACD-9990a-3") == []
    assert _family(report, "ACD-9990a-4") == []
    assert [f["record_id"] for f in _family(report)] == [GAP], "control row: only the gap is reported"


def test_findings_need_a_decision_and_no_record_is_repaired(tmp_path):
    # covers: ACD-2500b-1-i
    # angle: failure
    """Findings are 'needs a decision' and NEVER repaired: the verdict is failed, the exit code
    is 1, no finding of the family is 'fixed', and the record files are byte-identical after
    the run (a repairing family would append the missing entry)."""
    store = _store_with_gap_and_control(tmp_path)
    before = snapshot_tree(store.folder)

    exit_code, report = check_store(store, stage="itpo")

    findings = _family(report)
    assert len(findings) == 1
    assert findings[0]["disposition"] == "needs a decision"
    assert report["verdict"] == "failed"
    assert exit_code == 1
    assert snapshot_tree(store.folder) == before


# --------------------------------------------------------------------------
# reachability: the production entry point
# --------------------------------------------------------------------------
def test_acd_2500b_1_i_reachable_from_entry_point(tmp_path):
    # covers: ACD-2500b-1-i
    # angle: reachability
    """Entry point resolved (Step 1.1, a CLI script with `main()` under scripts/): the
    script `python scripts/ac_store/requirement_rule_check.py --location <folder> --stage
    itpo ...`, run as a subprocess. The gap record is reported under 'test intent coverage'
    and fails the run (exit 1, verdict failed). After the missing entry is added (the
    IT PO's rework) the same entry point passes the same family: the finding is consumed
    in control flow, not just printed."""
    store = _store_with_gap_and_control(tmp_path)

    failed = run_cli_subprocess(cli_argv(store, stage="itpo"), cwd=store.repo_root)

    assert failed.exit_code == 1, failed.stdout
    assert failed.report["verdict"] == "failed"
    gap = _family(failed.report, GAP)
    assert len(gap) == 1, failed.report["findings"]
    assert gap[0]["disposition"] == "needs a decision"
    assert NOTE_QUOTE in gap[0]["message"]

    fixed = store.read(GAP)
    fixed["test_intent"].append(intent_entry(FOUR[3]))
    store.write(fixed)
    passed = run_cli_subprocess(cli_argv(store, stage="itpo"), cwd=store.repo_root)

    assert _family(passed.report) == [], passed.report["findings"]
    assert passed.report["verdict"] == "passed", passed.report["findings"]
    assert passed.exit_code == 0


# --------------------------------------------------------------------------
# schema: both validators, one file
# --------------------------------------------------------------------------
GOOD_INTENT = [
    {"clause": "alpha is reported", "needs_test": True, "reason": "It is the visible outcome."},
    {"clause": "beta is reported", "needs_test": False, "reason": "A prompt wording change only."},
]


def test_schema_accepts_intent_and_rejects_unknown_key(tmp_path):
    # covers: ACD-2500b-1-i
    # angle: real_artifact
    """config/ac_store_schema.json, read by BOTH real validators (the standalone CLI and the
    commit hook, run as subprocesses over a yaml.safe_dump record): a well-formed
    test_intent is accepted, an item with an undeclared key is rejected, and both
    rejections name that key. The two verdicts are identical in each case."""
    good = base_record("ZZI-1", test_intent=[dict(e) for e in GOOD_INTENT])
    cli_ok, hook_ok = both_verdicts(good, tmp_path / "good")
    assert cli_ok.accepted, cli_ok.output
    assert hook_ok.accepted, hook_ok.output

    bad_entry = {**GOOD_INTENT[0], "test_name": "test_alpha"}
    bad = base_record("ZZI-2", test_intent=[bad_entry, dict(GOOD_INTENT[1])])
    cli_bad, hook_bad = both_verdicts(bad, tmp_path / "bad")

    assert (cli_bad.accepted, hook_bad.accepted) == (False, False)
    assert "'test_name'" in cli_bad.output, cli_bad.output
    assert "'test_name'" in hook_bad.output, hook_bad.output


@pytest.mark.parametrize("missing", ["clause", "needs_test", "reason"])
def test_schema_requires_all_three_keys_naming_the_missing_one(tmp_path, missing):
    # covers: ACD-2500b-1-i
    # angle: failure
    """All three keys are required. A well-formed record is accepted (control), the same
    record minus one key is rejected by both validators and the message names that key."""
    control = in_process_verdict(base_record("ZZI-3", test_intent=[dict(GOOD_INTENT[0])]), tmp_path / "control")
    assert control.accepted, f"control row (a well-formed test_intent) was rejected: {control.output}"
    entry = {k: v for k, v in GOOD_INTENT[0].items() if k != missing}

    cli, hook = both_verdicts(base_record("ZZI-4", test_intent=[entry]), tmp_path / "bad")

    assert (cli.accepted, hook.accepted) == (False, False)
    assert f"'{missing}'" in cli.output, cli.output
    assert f"'{missing}'" in hook.output, hook.output


@pytest.mark.parametrize(
    ("label", "value"),
    [
        ("null", None),
        ("empty list", []),
        ("not a list", {"clause": "alpha is reported", "needs_test": True, "reason": "r"}),
        ("entry not an object", ["alpha is reported"]),
        ("needs_test not boolean", [{"clause": "a", "needs_test": "yes", "reason": "r"}]),
        ("empty clause", [{"clause": "", "needs_test": True, "reason": "r"}]),
        ("empty reason", [{"clause": "a", "needs_test": True, "reason": ""}]),
    ],
)
def test_schema_rejects_malformed_test_intent_shapes(tmp_path, label, value):
    # covers: ACD-2500b-1-i
    # angle: boundary
    """Plain closed array, minItems 1, no null branch: each malformed shape is rejected.
    The control row (a well-formed intent accepted by the same validator) stops this from
    passing while test_intent is simply an undeclared property."""
    control = in_process_verdict(base_record("ZZI-5", test_intent=[dict(GOOD_INTENT[0])]), tmp_path / "c")
    assert control.accepted, control.output

    verdict = in_process_verdict(base_record("ZZI-6", test_intent=value), tmp_path / label.replace(" ", "_"))

    assert not verdict.accepted, f"{label} must be rejected: {verdict.output}"
