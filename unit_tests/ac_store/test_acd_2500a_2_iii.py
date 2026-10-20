"""
MODULE: test_acd_2500a_2_iii
GOAL: Red-first specification of ACD-2500a-2-iii: one-sided producer/consumer
    contracts are reported with both ends named and are never completed
    (scripts/ac_store/requirement_rule_check.py, family
    "producer/consumer contract symmetry", ticket 12).
BUSINESS CONTEXT: A delivery nobody expects, or an expectation nobody delivers, is
    a planning defect. Whether two contract descriptions MEAN the same thing is
    judgement that stays with the planner (TKT-300a-3): the check is presence-only
    (architect note D3) and never adds, removes or compares contract text.
ARCHITECTURE: Real CLI via main(argv) / subprocess over yaml.safe_dump records.
    Rules (note section 3): a consumer's expects_from target must exist STORE-WIDE
    and declare a non-empty delivers_to; a delivers_to entry naming an agent needs
    a record in the checked folder assigned that agent whose expects_from names the
    producer. All four shapes (null, string, object, list) are normalised: a string
    expects_from is an AC id, a string delivers_to is an agent name.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _rule_check_fixtures import (  # noqa: E402
    BLOCKERS,
    FAMILY_CONTRACTS,
    check_store,
    cli_argv,
    finding_text,
    findings_for,
    hierarchy,
    make_store,
    run_cli_subprocess,
    snapshot_tree,
)

_PRODUCER = "ACD-9990a-1"      # python-coder, delivers to llm-expert, nobody consumes
_NO_DELIVERY = "ACD-9990a-2"   # declares no delivery
_EXPECTS_NO_DELIVERY = "ACD-9990a-4"
_EXPECTS_UNKNOWN = "ACD-9990a-5"
_UNKNOWN_ID = "ACD-9990a-7"


def _llm_surface(name: str) -> dict:
    """Override: a declared file whose surface (templates/agents/*.md) maps to llm-expert,
    so the specialist-versus-surface family has nothing to say about an llm-expert record."""
    return {
        "assigned_agent": "llm-expert",
        "declared_files": [
            {"path": f"templates/agents/_fixture_{name}.md", "state": "to_be_created"}
        ],
    }


def _three_defect_records() -> list[dict]:
    return hierarchy(
        "ACD-9990", 5,
        child={
            1: {
                "assigned_agent": "python-coder",
                "delivers_to": {"agent": "llm-expert", "contract": "A rendered template."},
            },
            4: {"expects_from": {"ac_id": _NO_DELIVERY, "contract": "A report."}},
            5: {"expects_from": {"ac_id": _UNKNOWN_ID, "contract": "A result."}},
        },
    )


def test_delivery_without_consumer_reported(tmp_path):
    # covers: ACD-2500a-2-iii
    # angle: criterion
    """ACD-9990a-1 delivers to llm-expert and no llm-expert record expects from it:
    one 'needs a decision' finding on that record that names llm-expert."""
    store = make_store(tmp_path, _three_defect_records())

    _, report = check_store(store)

    findings = findings_for(report, record_id=_PRODUCER, rule_family=FAMILY_CONTRACTS)
    assert len(findings) == 1, report["findings"]
    assert findings[0]["disposition"] == "needs a decision"
    assert findings[0]["file"] == store.rel(_PRODUCER)
    assert "llm-expert" in finding_text(findings[0])


def test_expects_without_delivery_names_both_ends(tmp_path):
    # covers: ACD-2500a-2-iii
    # angle: criterion
    """ACD-9990a-4 expects a contract from ACD-9990a-2, which declares no delivery:
    the finding is on ACD-9990a-4, names both ids and states the delivery is absent."""
    store = make_store(tmp_path, _three_defect_records())

    _, report = check_store(store)

    findings = findings_for(report, record_id=_EXPECTS_NO_DELIVERY, rule_family=FAMILY_CONTRACTS)
    assert len(findings) == 1, report["findings"]
    assert findings[0]["disposition"] == "needs a decision"
    assert findings[0]["file"] == store.rel(_EXPECTS_NO_DELIVERY)
    text = finding_text(findings[0])
    assert _EXPECTS_NO_DELIVERY in text and _NO_DELIVERY in text
    assert "deliver" in text.lower()


def test_expects_from_unknown_id_reported(tmp_path):
    # covers: ACD-2500a-2-iii
    # angle: failure
    """ACD-9990a-5 expects from ACD-9990a-7, which exists nowhere in the store: a
    'needs a decision' finding on ACD-9990a-5 names the unknown id."""
    store = make_store(tmp_path, _three_defect_records())

    exit_code, report = check_store(store)

    findings = findings_for(report, record_id=_EXPECTS_UNKNOWN, rule_family=FAMILY_CONTRACTS)
    assert len(findings) == 1, report["findings"]
    assert findings[0]["disposition"] == "needs a decision"
    text = finding_text(findings[0])
    assert _EXPECTS_UNKNOWN in text and _UNKNOWN_ID in text
    assert report["verdict"] == "failed" and exit_code == 1


def test_exactly_three_findings_and_no_text_changed(tmp_path):
    # covers: ACD-2500a-2-iii
    # angle: criterion
    """The scenario yields exactly three findings (one per defect, all 'needs a
    decision', all this family) and every record is byte-identical afterwards."""
    store = make_store(tmp_path, _three_defect_records())
    before = snapshot_tree(store.folder)

    _, report = check_store(store)

    assert len(report["findings"]) == 3, report["findings"]
    assert {f["rule_family"] for f in report["findings"]} == {FAMILY_CONTRACTS}
    assert {f["disposition"] for f in report["findings"]} == {"needs a decision"}
    assert {f["record_id"] for f in report["findings"]} == {
        _PRODUCER, _EXPECTS_NO_DELIVERY, _EXPECTS_UNKNOWN,
    }
    assert snapshot_tree(store.folder) == before  # no contract text added or removed


def test_mutual_pair_with_different_wording_passes(tmp_path):
    # covers: ACD-2500a-2-iii
    # angle: boundary
    """A producer and an llm-expert consumer that point at each other produce no
    finding although their contract descriptions share no wording. The control row
    (an expects_from an unknown id, in the same folder) is the only finding, so the
    family demonstrably ran and a text-comparing implementation would add one."""
    records = hierarchy(
        "ACD-9990", 3,
        child={
            1: {"delivers_to": {"agent": "llm-expert", "contract": "A rendered prompt template."}},
            2: {
                **_llm_surface("mutual_consumer"),
                "expects_from": {"ac_id": _PRODUCER, "contract": "Words with nothing in common."},
            },
            3: {"expects_from": {"ac_id": _UNKNOWN_ID, "contract": "A result."}},  # control
        },
    )
    store = make_store(tmp_path, records)

    _, report = check_store(store)

    assert [f["record_id"] for f in report["findings"]] == ["ACD-9990a-3"], report["findings"]
    assert findings_for(report, record_id=_PRODUCER) == []
    assert findings_for(report, record_id=_NO_DELIVERY) == []


def test_all_four_shapes_of_contract_fields_are_handled(tmp_path):
    # covers: ACD-2500a-2-iii
    # angle: boundary
    """delivers_to / expects_from may be null, a string, an object or a list. A string
    expects_from is an AC id; a string delivers_to is an agent name. Satisfied pairs
    in list/string shapes give no finding; an unmatched string delivery and a string
    expects_from naming an unknown id each give one."""
    records = hierarchy(
        "ACD-9990", 6,
        child={
            # list delivery to llm-expert, consumed through a STRING expects_from
            1: {"delivers_to": [{"agent": "llm-expert", "contract": "x"}]},
            2: {**_llm_surface("shape_consumer"), "expects_from": _PRODUCER},
            # STRING delivery (agent name), consumed through a LIST expects_from
            3: {"delivers_to": "python-coder"},
            4: {"expects_from": [{"ac_id": "ACD-9990a-3", "contract": "y"}]},
            # unmatched string delivery; string expects_from with an unknown id
            5: {"delivers_to": "sql-coder"},
            6: {"expects_from": "ACD-9990a-99"},
        },
    )
    store = make_store(tmp_path, records)

    _, report = check_store(store)

    assert sorted(f["record_id"] for f in report["findings"]) == ["ACD-9990a-5", "ACD-9990a-6"], (
        report["findings"]
    )
    assert {f["disposition"] for f in report["findings"]} <= set(BLOCKERS)
    assert "ACD-9990a-99" in finding_text(findings_for(report, record_id="ACD-9990a-6")[0])


def test_expects_from_id_in_another_folder_is_known(tmp_path):
    # covers: ACD-2500a-2-iii
    # angle: boundary
    """'Unknown' means absent from the whole store, not only the checked folder: an
    expects_from naming a delivering record that lives in a sibling feature folder
    produces no finding, while the same expectation naming an absent id does."""
    store = make_store(
        tmp_path,
        hierarchy(
            "ACD-9990", 2,
            child={
                1: {"expects_from": {"ac_id": "ACD-8880", "contract": "From elsewhere."}},
                2: {"expects_from": {"ac_id": "ACD-8881", "contract": "From nowhere."}},
            },
        ),
    )
    other = store.folder.parent / "other-feature"
    other.mkdir()
    elsewhere = {
        "id": "ACD-8880", "title": "Record in another folder", "component": "ac-driven-dev",
        "components": ["ac_driven_dev"], "level": "L0", "status": "active",
        "criteria": "Given x,\nWhen y,\nThen z.\n", "readiness": "draft",
        "delivers_to": {"agent": "python-coder", "contract": "Something."},
    }
    (other / "ACD-8880.yaml").write_text(yaml.safe_dump(elsewhere, sort_keys=False), encoding="utf-8")

    _, report = check_store(store)

    assert [f["record_id"] for f in report["findings"]] == ["ACD-9990a-2"], report["findings"]
    assert "ACD-8881" in finding_text(report["findings"][0])


def test_acd_2500a_2_iii_reachable_from_entry_point(tmp_path):
    # covers: ACD-2500a-2-iii
    # angle: reachability
    """Real CLI subprocess over the three-defect folder: exit 1, three 'needs a
    decision' contract findings on stdout, and no record changed on disk."""
    store = make_store(tmp_path, _three_defect_records())
    before = snapshot_tree(store.folder)

    run = run_cli_subprocess(cli_argv(store), cwd=store.repo_root)

    assert run.exit_code == 1, run.stderr
    assert run.report["verdict"] == "failed"
    assert len(findings_for(run.report, rule_family=FAMILY_CONTRACTS)) == 3
    assert len(run.report["findings"]) == 3
    assert snapshot_tree(store.folder) == before
