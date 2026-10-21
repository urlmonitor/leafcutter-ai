"""
MODULE: test_acd_2500a_2
GOAL: Red-first specification of ACD-2500a-2: five one-right-answer rule families
    are checked; the safe ones are repaired, the rest reported
    (scripts/ac_store/requirement_rule_check.py, architect note sections 1-3).
BUSINESS CONTEXT: The deterministic check replaces judgement-by-prose in the
    technical planner's self-check. Three families have exactly one correct repair
    (parent back-links, an unambiguous graph component list, readiness restored to
    its before-state); two only report (contract symmetry, documentation mapping).
    After repairs the check evaluates again and passes only if nothing is left.
ARCHITECTURE: All tests run through `main(argv)` / the real script in a subprocess
    over real yaml.safe_dump records in a tmp consumer-style repo
    (_rule_check_fixtures.py). Readiness before-state comes from a
    `--before-snapshot` file; rule-source tests edit the TMP copies of the schema /
    components registry and pass them via --schema / --components-registry.

DEPENDENCY NOTE (for the coordinator): this ticket owns the orchestration
    (two-pass evaluation, the field-targeted writer `_rc_edit`, `family_counts`,
    rule-source plumbing). The five families themselves are tickets 10-14, so the
    family-level tests below (all-five count, repairs, report-only) are integration
    tests that go green only once those families exist. The rule-source test needs
    only the record-schema adapter (ticket 06) plus this ticket's flags.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _rule_check_fixtures import (  # noqa: E402
    FAMILY_BACKLINKS,
    FAMILY_COMPONENTS,
    FAMILY_CONTRACTS,
    FAMILY_DOC_TRIGGERS,
    FAMILY_READINESS,
    FIVE_FAMILIES,
    SCRIPTS_DIR,
    # The protected-fields family's 'not evaluated' entries (ACD-2500a-2-vi / -vii)
    # are not this file's subject; every other finding is kept.
    check_store_other_families as check_store,
    cli_argv,
    finding_text,
    findings_for,
    hierarchy,
    make_store,
    run_cli_subprocess_other_families as run_cli_subprocess,
    snapshot_tree,
    valid_record,
    write_snapshot,
)

_L1 = "ACD-9990a"
_CHILD_1 = "ACD-9990a-1"
_CHILD_2 = "ACD-9990a-2"
_NO_COMPONENTS = "ACD-9991"
_RAISED = "ACD-9992"


def _repair_store(tmp_path):
    """6 records, three of them needing exactly one safe repair each:

    - ACD-9990a (L1) lacks child ACD-9990a-2 in covered_by          -> back-link
    - ACD-9991 has `components: []` (namespace ac-driven-dev maps to
      exactly one graph id, ac_driven_dev)                           -> component list
    - ACD-9992 is `approved` now but `draft` in the before-state    -> readiness
    Returns (store, before_snapshot_path_arg_pair).
    """
    records = [
        *hierarchy("ACD-9990", 2, l1={"covered_by": [_CHILD_1]}),
        valid_record(_NO_COMPONENTS, level="L0", components=[]),
        valid_record(_RAISED, level="L0", readiness="approved"),
    ]
    store = make_store(tmp_path, records)
    snapshot = write_snapshot(store, {_RAISED: "draft"})
    return store, ("--before-snapshot", str(snapshot))


def _parsed_tree(store) -> dict[str, dict]:
    return {
        path.name: yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in sorted(store.folder.glob("*.yaml"))
    }


def test_every_record_evaluated_against_all_five_families(tmp_path):
    # covers: ACD-2500a-2
    """Each record in the batch is evaluated by all five families, visible in the
    report's per-family evaluation count (family_counts: {family: {evaluated, ...}})."""
    store = make_store(tmp_path, hierarchy("ACD-9990", 2))

    _, report = check_store(store)

    assert report["records_checked"] == 4
    counts = report["family_counts"]
    for family in FIVE_FAMILIES:
        assert counts[family]["evaluated"] == 4, (family, counts)
        assert counts[family]["not_evaluated"] == 0, (family, counts)
    assert report["verdict"] == "passed", report["findings"]


def test_repair_families_fix_and_report_file_and_value(tmp_path):
    # covers: ACD-2500a-2
    """Back-link, unambiguous component list and approved-by-agent readiness are each
    repaired on disk (only the one field changes) and reported 'fixed' naming the file
    and the value changed; a second run changes nothing and reports no 'fixed' entry."""
    store, before = _repair_store(tmp_path)
    original = _parsed_tree(store)

    exit_code, report = check_store(store, *before)

    fixed = [f for f in report["findings"] if f["disposition"] == "fixed"]
    assert len(report["findings"]) == 3 == len(fixed), report["findings"]
    by_family = {f["rule_family"]: f for f in fixed}
    assert set(by_family) == {FAMILY_BACKLINKS, FAMILY_COMPONENTS, FAMILY_READINESS}
    assert by_family[FAMILY_BACKLINKS]["file"] == store.rel(_L1)
    assert _CHILD_2 in finding_text(by_family[FAMILY_BACKLINKS])
    assert by_family[FAMILY_COMPONENTS]["file"] == store.rel(_NO_COMPONENTS)
    assert "ac_driven_dev" in finding_text(by_family[FAMILY_COMPONENTS])
    assert by_family[FAMILY_READINESS]["file"] == store.rel(_RAISED)
    assert "draft" in finding_text(by_family[FAMILY_READINESS])

    after = _parsed_tree(store)
    expected = {name: dict(record) for name, record in original.items()}
    # existing order kept, missing child appended last
    expected[f"{_L1}.yaml"]["covered_by"] = [_CHILD_1, _CHILD_2]
    expected[f"{_NO_COMPONENTS}.yaml"]["components"] = ["ac_driven_dev"]
    expected[f"{_RAISED}.yaml"]["readiness"] = "draft"
    assert after == expected  # nothing outside the three target fields moved
    assert report["verdict"] == "passed"
    assert exit_code == 0

    frozen = snapshot_tree(store.folder)
    rerun_exit, rerun = check_store(store, *before)
    assert snapshot_tree(store.folder) == frozen  # idempotent: second run writes no byte
    assert [f for f in rerun["findings"] if f["disposition"] == "fixed"] == []
    assert rerun["verdict"] == "passed" and rerun_exit == 0


def test_report_only_families_never_modify_records(tmp_path):
    # covers: ACD-2500a-2
    """Contract symmetry and documentation mapping findings leave every file
    byte-identical and are 'needs a decision'."""
    records = hierarchy(
        "ACD-9990", 2,
        l1={"documentation_triggers": ["how-to"]},  # no documentation-expert record in the folder
        child={2: {"expects_from": {"ac_id": _CHILD_1, "contract": "A report."}}},  # no delivery
    )
    store = make_store(tmp_path, records)
    before_bytes = snapshot_tree(store.folder)

    exit_code, report = check_store(store)

    assert snapshot_tree(store.folder) == before_bytes
    assert len(report["findings"]) == 2, report["findings"]
    assert {f["rule_family"] for f in report["findings"]} == {FAMILY_CONTRACTS, FAMILY_DOC_TRIGGERS}
    assert {f["disposition"] for f in report["findings"]} == {"needs a decision"}
    assert findings_for(report, record_id=_CHILD_2, rule_family=FAMILY_CONTRACTS)
    assert findings_for(report, record_id=_L1, rule_family=FAMILY_DOC_TRIGGERS)
    assert report["verdict"] == "failed" and exit_code == 1


def test_repaired_records_reevaluated_before_passed(tmp_path, monkeypatch):
    # covers: ACD-2500a-2
    """passed is reported only when the evaluation AFTER repairs yields no finding:
    (a) a probe family sees the parent record unrepaired first and repaired later;
    (b) repairs plus a leftover 'needs a decision' finding still end failed, with
    the repair persisted and listed as fixed."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import requirement_rule_check as entry

    observed: list[list[str]] = []

    def evaluate_record(_ctx, record):
        if record["id"] == _L1:
            observed.append(list(record["covered_by"]))
        return []

    probe = SimpleNamespace(NAME="re-evaluation probe family", evaluate_record=evaluate_record)
    monkeypatch.setattr(entry, "FAMILIES", [*entry.FAMILIES, probe])
    store, before = _repair_store(tmp_path / "repair_only")

    exit_code, report = check_store(store, *before)

    assert observed[0] == [_CHILD_1], observed  # evaluated before the repair
    assert observed[-1] == [_CHILD_1, _CHILD_2], observed  # evaluated again after it
    assert report["verdict"] == "passed" and exit_code == 0

    mixed_records = [
        *hierarchy(
            "ACD-9990", 2, l1={"covered_by": [_CHILD_1]},
            child={2: {"expects_from": {"ac_id": _CHILD_1, "contract": "A report."}}},
        ),
    ]
    mixed = make_store(tmp_path / "mixed", mixed_records)

    mixed_exit, mixed_report = check_store(mixed)

    dispositions = sorted(f["disposition"] for f in mixed_report["findings"])
    assert dispositions == ["fixed", "needs a decision"], mixed_report["findings"]
    assert mixed.read(_L1)["covered_by"] == [_CHILD_1, _CHILD_2]  # the repair was still applied
    assert mixed_report["verdict"] == "failed" and mixed_exit == 1


def test_rule_source_change_changes_verdict_without_second_edit(tmp_path):
    # covers: ACD-2500a-2
    # angle: seam
    """Editing a rule in the shared rule source (the components registry; the record
    schema) changes the check's verdict with no edit to the check itself: the same
    record passes against the shipped copies, fails against each edited copy, and
    passes again when pointed back at the originals."""
    store = make_store(
        tmp_path, [valid_record("ACD-990", level="L0", components=["ac_store"])]
    )
    registry_doc = json.loads(store.registry.read_text(encoding="utf-8"))
    registry_doc["components"].pop("ac_store")
    edited_registry = tmp_path / "components.edited.json"
    edited_registry.write_text(json.dumps(registry_doc, indent=2), encoding="utf-8")
    schema_doc = json.loads(store.schema.read_text(encoding="utf-8"))
    schema_doc["properties"]["readiness"]["enum"] = ["reviewed", "approved"]
    edited_schema = tmp_path / "schema.edited.json"
    edited_schema.write_text(json.dumps(schema_doc, indent=2), encoding="utf-8")

    _, baseline = check_store(store)
    _, registry_run = check_store(store, "--components-registry", str(edited_registry))
    _, schema_run = check_store(store, "--schema", str(edited_schema))
    _, restored = check_store(
        store, "--components-registry", str(store.registry), "--schema", str(store.schema)
    )

    assert baseline["verdict"] == "passed", baseline["findings"]
    assert registry_run["verdict"] == "failed"
    assert len(registry_run["findings"]) == 1, registry_run["findings"]
    assert "ac_store" in registry_run["findings"][0]["message"]
    assert schema_run["verdict"] == "failed"
    assert len(schema_run["findings"]) == 1, schema_run["findings"]
    assert "readiness" in schema_run["findings"][0]["message"].lower()
    assert restored["verdict"] == "passed", restored["findings"]


def test_acd_2500a_2_reachable_from_entry_point(tmp_path):
    # covers: ACD-2500a-2
    # angle: reachability
    """Real CLI subprocess: the repair scenario exits 0, lists three 'fixed' entries on
    stdout, and the repairs are on disk -- the effect plan-feature relies on."""
    store, before = _repair_store(tmp_path)

    run = run_cli_subprocess(cli_argv(store, *before), cwd=store.repo_root)

    assert run.exit_code == 0, run.stderr
    assert run.report["verdict"] == "passed"
    assert sorted(f["disposition"] for f in run.report["findings"]) == ["fixed"] * 3
    assert store.read(_L1)["covered_by"] == [_CHILD_1, _CHILD_2]
    assert store.read(_NO_COMPONENTS)["components"] == ["ac_driven_dev"]
    assert store.read(_RAISED)["readiness"] == "draft"
