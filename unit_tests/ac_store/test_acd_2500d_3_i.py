"""
MODULE: unit_tests/ac_store/test_acd_2500d_3_i.py
COVERS: ACD-2500d-3-i
GOAL: Red-first specification of ticket 39, the approval and record half: a reviewed requirement
    whose file finding has no recorded planner decision stays at "reviewed" with the reason "file
    finding undecided"; one whose finding carries a decision (with a reason) is approved; the record
    check accepts a finding carrying file, verdict, line range, reason and decision and rejects a
    finding carrying a key it does not know, naming the key.
BUSINESS CONTEXT: G4 architect note (ticket 29, comment 2026-10-14 14:06), sections 3 to 5. The hold
    is COMPUTED from the record (`_file_findings.undecided_findings`), never carried on `hold_reason`;
    only a non-"consistent" verdict needs a decision. The rule-check family and the workflow
    hand-back are in test_acd_2500d_3_i_family.py and unit_tests/ac_driven_dev/file_findings/.
ARCHITECTURE: Records come from the real serializer. The approval step runs as `approve_acs.py` in a
    subprocess over a tmp store; both record validators (the standalone one and the commit hook)
    run as subprocesses on the same file (_acd_2500_schema_probe); many cheap schema boundary rows
    use the in-process validator.

RED STATE: `file_findings` is not a schema property (the record is refused: assertion red), the
    approval step approves an undecided finding today (assertion red), and `_file_findings` does not
    exist (ModuleNotFoundError: an absence red, the module is new).

INTERPRETATIONS (flagged for the implementer): `undecided_findings(record)` returns the undecided
    finding dicts in their stored order (an empty list when none); a non-list or absent field is [].
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _acd_2500_schema_probe import SCHEMA_FILE, base_record, both_verdicts, in_process_verdict  # noqa: E402
from _acd_2500d_3_i_fixtures import (  # noqa: E402
    EXISTING, FINDINGS, OPENED, STAND, UNDECIDED, decision, finding, leaf,
)
from _acd_2500b_approval_fixtures import (  # noqa: E402
    TWO, build, design_for, goal, holds_module, json_of, read_bytes, reviewed_intent, run_approve,
)

DESCRIBES = "describes, does not implement"
ELSEWHERE = "behaviour found elsewhere"


def _undecided() -> dict:
    return finding(EXISTING, DESCRIBES, line_range="10-20", reason="It only documents the behaviour.")


def _decided(choice: str = STAND) -> dict:
    return finding(EXISTING, DESCRIBES, line_range="10-20", decided=decision(choice))


def _scenario(tmp_path, extra: list[dict] | None = None):
    """The AC's Given: R carries an undecided finding, S one decided "assignment stands"."""
    leaves = [leaf("ZZF-1a-1", [_undecided()]), leaf("ZZF-1a-2", [_decided()]), *(extra or [])]
    return build(tmp_path, [goal("ZZF-1", [r["id"] for r in leaves]), *leaves])


def test_undecided_finding_held_with_reason(tmp_path):
    # covers: ACD-2500d-3-i
    # angle: criterion
    """R stays "reviewed" and the approval report names R with exactly "file finding undecided".

    Wrong versions caught: R is promoted, the reason is another vocabulary value, S (the decided
    control row) is held too, the file path is absolute, or R's file is rewritten. Exact: one held.
    """
    store = _scenario(tmp_path)
    before = read_bytes(store, "ZZF-1a-1")

    report = json_of(run_approve(store, "--goal", "ZZF-1", "--json"))

    assert report["held"] == [{"id": "ZZF-1a-1", "file": store.rel("ZZF-1a-1"), "reason": UNDECIDED}], report
    assert store.read("ZZF-1a-1")["readiness"] == "reviewed"
    assert read_bytes(store, "ZZF-1a-1") == before, "a held record must stay byte-identical"


def test_decided_finding_approved(tmp_path):
    # covers: ACD-2500d-3-i
    # angle: criterion
    """S (decision "assignment stands" with a reason) moves to "approved"; only readiness and amended_by change.

    The same run also holds R, so the test is red today; the extra control rows are approved:
    decisions `reassign` and `split`, and a `consistent` finding whose decision stays null for good
    (it needs none). Exactly four approved, one held.
    """
    extras = [
        leaf("ZZF-1a-3", [_decided("reassign")]),
        leaf("ZZF-1a-4", [_decided("split")]),
        leaf("ZZF-1a-5", [finding(EXISTING, "consistent")]),
    ]
    store = _scenario(tmp_path, extras)
    originals = {rid: store.read(rid) for rid in ("ZZF-1a-2", "ZZF-1a-3", "ZZF-1a-4", "ZZF-1a-5")}

    report = json_of(run_approve(store, "--goal", "ZZF-1", "--json"))

    assert sorted(report["approved"]) == sorted(originals), report
    assert [h["id"] for h in report["held"]] == ["ZZF-1a-1"], report
    for rid, original in originals.items():
        after = store.read(rid)
        assert after["readiness"] == "approved", rid
        untouched = {k: v for k, v in after.items() if k not in ("readiness", "amended_by")}
        assert untouched == {k: v for k, v in original.items() if k not in ("readiness", "amended_by")}, rid


def test_undecided_findings_predicate_rows():
    # covers: ACD-2500d-3-i
    # angle: boundary
    """`undecided_findings` is "decision None and verdict other than consistent", in stored order.

    Rows: field absent, `[]`, a non-list value: []. Consistent with no decision: []. A non-consistent
    verdict with no decision: that finding. A non-consistent verdict with a decision: []. Mixed: only
    the undecided ones, in order, so an exact two-of-four.
    """
    from _file_findings import undecided_findings  # noqa: PLC0415

    first, second = _undecided(), finding("scripts/ac_store/other.py", ELSEWHERE, found_in="x.py")
    rows = {
        "absent": ({}, []),
        "empty": ({FINDINGS: []}, []),
        "not a list": ({FINDINGS: "oops"}, []),
        "consistent, no decision": ({FINDINGS: [finding(EXISTING, "consistent")]}, []),
        "undecided": ({FINDINGS: [first]}, [first]),
        "decided": ({FINDINGS: [_decided()]}, []),
        "mixed": ({FINDINGS: [first, _decided(), finding(EXISTING, "consistent"), second]}, [first, second]),
    }
    wrong = {k: undecided_findings(rec) for k, (rec, want) in rows.items() if list(undecided_findings(rec)) != want}
    assert wrong == {}, f"label -> got: {wrong}"


def test_hold_is_computed_from_the_record_never_carried():
    # covers: ACD-2500d-3-i
    # angle: discrimination
    """approval_hold_reason reads the findings, not `hold_reason`, and keeps the vocabulary order.

    Wrong versions caught: the hold follows a carried `hold_reason: file finding undecided` (a decided
    record carrying it must NOT be held; an undecided one with no marker MUST be), the hold fires for
    any finding, or the order is wrong: undecided plus undesigned intent reads "test design pending",
    undecided plus the pending-reference marker reads "reference file pending".
    """
    holds = holds_module()
    rows = {
        "undecided, nothing carried": (leaf("ZZF-2a-1", [_undecided()]), UNDECIDED),
        "decided, stale marker carried": (leaf("ZZF-2a-2", [_decided()], hold_reason=UNDECIDED), None),
        "one of two undecided": (leaf("ZZF-2a-3", [_decided(), _undecided()]), UNDECIDED),
        "consistent only": (leaf("ZZF-2a-4", [finding(EXISTING, "consistent")]), None),
        "with undesigned intent": (reviewed_intent("ZZF-2a-5", **{FINDINGS: [_undecided()], OPENED: [EXISTING]}), "test design pending"),
        "designed intent": (reviewed_intent("ZZF-2a-6", spec=design_for(TWO), **{FINDINGS: [_undecided()], OPENED: [EXISTING]}), UNDECIDED),
        "pending reference marker": (leaf("ZZF-2a-7", [_undecided()], hold_reason="reference file pending"), "reference file pending"),
    }
    wrong = {k: holds.approval_hold_reason(r) for k, (r, want) in rows.items() if holds.approval_hold_reason(r) != want}
    assert wrong == {}, f"unexpected hold reasons (label -> got): {wrong}"


def _rec(**fields) -> dict:
    return base_record("ZZI-3", **fields)


def test_finding_schema_accepts_known_rejects_unknown_key(tmp_path):
    # covers: ACD-2500d-3-i
    # angle: real_artifact
    """A finding with file, verdict, line range, reason and decision is accepted; a stray key is named.

    Both entry points run as real subprocesses on the same file: validate_ac_schema.py and the commit
    hook. Control (red today): the clean record is accepted by both. Rows: an unknown key on the
    finding and one on its decision are refused by both, each output naming the key and NOT being the
    "file_findings was unexpected" error the undeclared field gives today.
    """
    clean = {FINDINGS: [_decided()], OPENED: [EXISTING]}
    for verdict in both_verdicts(_rec(**clean), tmp_path):
        assert verdict.accepted, verdict.output[:400]

    on_finding = {FINDINGS: [{**_decided(), "confidence": 0.9}], OPENED: [EXISTING]}
    on_decision = {FINDINGS: [{**_decided(), "decision": {**decision(), "note": "x"}}], OPENED: [EXISTING]}
    for fields, key in ((on_finding, "confidence"), (on_decision, "note")):
        for verdict in both_verdicts(_rec(**fields), tmp_path):
            assert not verdict.accepted
            assert f"'{key}' was unexpected" in verdict.output, (key, verdict.output[:400])
            assert "'file_findings' was unexpected" not in verdict.output


_BAD = {
    "unknown verdict": ({**_decided(), "verdict": "mostly consistent"}, "mostly consistent"),
    "unknown choice": ({**_decided(), "decision": decision("ignore")}, "ignore"),
    "decision by someone else": ({**_decided(), "decision": {**decision(), "by": "test-designer"}}, "was expected"),
    "missing reason": ({k: v for k, v in _decided().items() if k != "reason"}, "'reason' is a required property"),
    "missing verdict": ({k: v for k, v in _decided().items() if k != "verdict"}, "'verdict' is a required property"),
    "missing file": ({k: v for k, v in _decided().items() if k != "file"}, "'file' is a required property"),
    "line_range not a string": ({**_decided(), "line_range": 5}, "is not of type"),
    "empty reason": ({**_decided(), "reason": ""}, "''"),  # jsonschema words minLength differently by version
    "decision without reason": ({**_decided(), "decision": {"choice": STAND, "by": "it-po"}}, "'reason' is a required property"),
}


@pytest.mark.parametrize("label", sorted(_BAD))
def test_finding_shape_boundary_rows_are_refused_for_their_own_reason(tmp_path, label):
    # covers: ACD-2500d-3-i
    # angle: boundary
    """Each malformed finding is refused with its own message, never the "undeclared field" error.

    Control (red today, one per row so a refusal cannot be read as the row's): the same record with a
    well-formed finding is accepted by the same validator in the same call.
    """
    assert in_process_verdict(_rec(**{FINDINGS: [_decided()], OPENED: [EXISTING]}), tmp_path).accepted
    bad_finding, token = _BAD[label]
    verdict = in_process_verdict(_rec(**{FINDINGS: [bad_finding], OPENED: [EXISTING]}), tmp_path)
    assert not verdict.accepted
    assert token in verdict.output, verdict.output[:400]
    assert "'file_findings' was unexpected" not in verdict.output


def test_finding_list_edges_are_accepted(tmp_path):
    # covers: ACD-2500d-3-i
    # angle: boundary
    """`[]` findings, an empty opened-files list, a null decision and a null line range are all valid.

    An absent field means the step has not run (never a violation); emptiness of the opened list is a
    rule-check finding, not a schema error. Exact: all five rows accepted (red today: the field is
    undeclared, so even the first row is refused).
    """
    rows = {
        "empty findings": {FINDINGS: [], OPENED: []},
        "empty opened, one finding": {FINDINGS: [finding(EXISTING)], OPENED: []},
        "null decision": {FINDINGS: [_undecided()], OPENED: [EXISTING]},
        "findings without opened field": {FINDINGS: [finding(EXISTING)]},
        "no findings field": {},
    }
    refused = {k: v for k, fields in rows.items() if not (v := in_process_verdict(_rec(**fields), tmp_path)).accepted}
    assert refused == {}, {k: v.output[:200] for k, v in refused.items()}


def test_constants_match_schema_properties():
    # covers: ACD-2500d-3-i
    # angle: real_artifact
    """Each `_file_findings` constant and enum equals the schema's own (the `_test_intent` lockstep).

    Read from the real config/ac_store_schema.json: both record keys are declared, the item shape is
    closed (`additionalProperties: false`) for the finding and for the decision, `file_findings_opened_files`
    has string items with minLength 1 and NO minItems, and `by` is fixed to "it-po".
    """
    import _file_findings as ff  # noqa: PLC0415

    props = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))["properties"]
    items = props[ff.FINDINGS_KEY]["items"]
    decision_schema = items["properties"]["decision"]
    branches = decision_schema.get("oneOf") or decision_schema.get("anyOf") or [decision_schema]
    decision_object = next(b for b in branches if "properties" in b)

    assert (ff.FINDINGS_KEY, ff.FINDINGS_OPENED_KEY) == (FINDINGS, OPENED)
    assert OPENED in props and "minItems" not in props[OPENED]
    assert props[OPENED]["items"].get("minLength") == 1
    assert tuple(items["properties"]["verdict"]["enum"]) == tuple(ff.VERDICTS)
    assert tuple(decision_object["properties"]["choice"]["enum"]) == tuple(ff.CHOICES)
    assert items.get("additionalProperties") is False and decision_object.get("additionalProperties") is False
    assert decision_object["properties"]["by"].get("const") == "it-po"
    assert set(items["required"]) == {"file", "verdict", "reason"}


def test_acd_2500d_3_i_reachable_from_entry_point(tmp_path):
    # covers: ACD-2500d-3-i
    # angle: reachability
    """The AC scenario through the real approval CLI, with a decision written to disk between runs.

    Entry point: `python scripts/ac_store/approve_acs.py --ac <R> --json` (CLI, subprocess). Run 1: R is
    held with the reason and the text mode prints `held ZZF-1a-1: file finding undecided`. The planner's
    decision is then written into R's file with the real serializer; run 2 promotes R, because
    decision presence is judged from the record on disk and nothing is cached or taken from a report.
    """
    store = _scenario(tmp_path)
    first = json_of(run_approve(store, "--ac", "ZZF-1a-1", "--json"))
    assert first["held"] == [{"id": "ZZF-1a-1", "file": store.rel("ZZF-1a-1"), "reason": UNDECIDED}], first
    assert f"held ZZF-1a-1: {UNDECIDED}" in run_approve(store, "--ac", "ZZF-1a-1").stdout

    record = store.read("ZZF-1a-1")
    record[FINDINGS][0]["decision"] = decision()
    store.path("ZZF-1a-1").write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8")

    second = json_of(run_approve(store, "--ac", "ZZF-1a-1", "--json"))
    assert second["held"] == [] and second["approved"] == ["ZZF-1a-1"], second
    assert store.read("ZZF-1a-1")["readiness"] == "approved"
