"""
MODULE: test_acd_2500a_1
GOAL: Red-first specification of the requirement rule check CLI
    (scripts/ac_store/requirement_rule_check.py, ACD-2500a-1): it checks a feature
    folder, reports findings naming file, record id and rule family, fails closed,
    and counts the records it checked.
BUSINESS CONTEXT: An authoring stage must not be reported complete on the stage
    agent's word; a deterministic script decides. The check reports one finding per
    rule violation (never one per check that knows the rule).
ARCHITECTURE: Every test drives the check through `main(argv)` (via the shared
    helpers in _rule_check_fixtures.py), never through an `_rc_*` internal. Fixture
    folders are real YAML written by yaml.safe_dump into a tmp consumer-style repo.
    Exit codes: 0 passed, 1 failed, 2 usage (architect note, section 1).

    The workflow half of this ticket lives in
    unit_tests/ac_driven_dev/rule_check/test_acd_2500a_1.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _rule_check_fixtures import (  # noqa: E402
    FAMILY_CONTRACTS,
    check_store,
    findings_for,
    hierarchy,
    make_store,
)

_PRODUCER = "ACD-9990a-1"
_CONSUMER = "ACD-9990a-2"
_CONTRACT = {"ac_id": _PRODUCER, "contract": "A report with a verdict."}


def _one_sided_store(tmp_path):
    """4 records; ACD-9990a-2 expects a contract from ACD-9990a-1 that delivers none."""
    return make_store(tmp_path, hierarchy("ACD-9990", 2, child={2: {"expects_from": _CONTRACT}}))


def test_one_sided_expects_from_yields_single_symmetry_finding(tmp_path):
    # covers: ACD-2500a-1
    """4 records, one expects from a producer that declares no delivery: exactly one
    finding, naming the record's file, the record id and the rule family."""
    store = _one_sided_store(tmp_path)

    exit_code, report = check_store(store)

    assert len(report["findings"]) == 1, report["findings"]
    finding = report["findings"][0]
    assert finding["file"] == store.rel(_CONSUMER)
    assert finding["record_id"] == _CONSUMER
    assert finding["rule_family"] == FAMILY_CONTRACTS == "producer/consumer contract symmetry"
    assert finding["disposition"] == "needs a decision"
    assert exit_code == 1


def test_any_finding_makes_verdict_failed(tmp_path):
    # covers: ACD-2500a-1
    """A report with one finding has verdict failed and a non-zero exit; the same
    folder without the violation passes with exit 0 (control: not a blanket failure)."""
    failing = _one_sided_store(tmp_path / "failing")
    clean = make_store(tmp_path / "clean", hierarchy("ACD-9990", 2))

    failing_exit, failing_report = check_store(failing)
    clean_exit, clean_report = check_store(clean)

    assert failing_report["verdict"] == "failed"
    assert failing_exit != 0
    assert clean_report["verdict"] == "passed", clean_report["findings"]
    assert clean_exit == 0
    assert clean_report["findings"] == []


def test_clean_records_produce_no_findings(tmp_path):
    # covers: ACD-2500a-1
    """The 3 records without a violation produce no finding: the only finding in the
    folder belongs to the one violating record."""
    store = _one_sided_store(tmp_path)

    _, report = check_store(store)

    clean_ids = ["ACD-9990", "ACD-9990a", _PRODUCER]
    assert report["records_checked"] == 4
    for record_id in clean_ids:
        assert findings_for(report, record_id=record_id) == [], record_id
    assert {finding["file"] for finding in report["findings"]} == {store.rel(_CONSUMER)}


def test_records_checked_count_tracks_folder_size(tmp_path):
    # covers: ACD-2500a-1
    # angle: boundary
    """records_checked is 4, then 5 after a fifth record is added and the check re-runs."""
    store = make_store(tmp_path, hierarchy("ACD-9990", 2))

    _, first = check_store(store)
    for record in hierarchy("ACD-9990", 3):
        store.write(record)  # rewrites the parent's covered_by AND adds the fifth record
    _, second = check_store(store)

    assert first["records_checked"] == 4
    assert second["records_checked"] == 5
    assert first["verdict"] == second["verdict"] == "passed", (first, second)


@pytest.mark.parametrize(
    "components",
    [[], ["no_such_component"]],
    ids=["empty-components-list", "component-not-in-registry"],
)
def test_rule_shared_with_record_check_reported_once(tmp_path, components):
    # covers: ACD-2500a-1
    # angle: seam
    """A record violating a rule the store's existing record check already enforces
    (the graph component list) produces exactly ONE finding, not one per check that
    knows the rule (the schema's minItems/enum AND the components rule both fire in
    the existing check). Three other records stay clean (control)."""
    records = hierarchy("ACD-9990", 2, child={1: {"components": components}})
    store = make_store(tmp_path, records)

    _, report = check_store(store)

    violating = findings_for(report, record_id=_PRODUCER)
    assert len(violating) == 1, violating
    assert violating[0]["file"] == store.rel(_PRODUCER)
    assert "components" in violating[0]["message"].lower()
    assert len(report["findings"]) == 1, report["findings"]
    assert report["records_checked"] == 4
