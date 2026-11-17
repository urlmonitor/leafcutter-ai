"""
MODULE: unit_tests/ac_store/test_acd_2500d_2_i.py
COVERS: ACD-2500d-2-i
GOAL: Red-first specification of ticket 37: a package-surface requirement whose reference file is
    still pending (the technical planner supplied the other four package-surface fields, the
    file-aware step has not run) is accepted at the planner stage, held at "reviewed" with the reason
    "reference file pending" at approval, and, once the reference file is named, is validated by the
    five-field rule exactly as before.
BUSINESS CONTEXT: G4 architect note (ticket 29, comment 2026-10-14 14:06), sections 5 and 8. The
    marker is the record's `hold_reason` field set to "reference file pending": explicit, never
    inferred from the key's absence (ACS-100i-6-i keeps its intent). Three enforcement points move
    together: the schema (`config/ac_store_schema.json`, read by validate_ac_schema.py and the
    commit hook), the authoring-time validator (validate_ac.py) and the approval hold.
ARCHITECTURE: Records come from the real serializer (yaml.safe_dump). All three validators run as
    real subprocesses on the same file: the standalone schema validator, the commit hook, and
    validate_ac.py. The approval step runs as `approve_acs.py` in a subprocess over a tmp store.

RED STATE: `hold_reason` is not a property of the schema, so a pending record is refused by both
    schema validators today (an ASSERTION red); the approval step approves a pending record today
    (assertion red); the lockstep test finds no `hold_reason` property (assertion red).

PASSING-TODAY PARTS: the post-naming half of the seam test and the "no marker is refused" rows
    already hold. Each such test also carries a red-today half (its control row: the marker IS
    accepted), so no test here is green today; the docstrings say which half is which.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _acd_2500_schema_probe import SCHEMA_FILE, cli_verdict, hook_verdict  # noqa: E402
from _acd_2500b_approval_fixtures import (  # noqa: E402
    build,
    goal,
    holds_module,
    json_of,
    read_bytes,
    reviewed_intent,
    run_approve,
    valid_record,
)
from _acs_100i_fixtures import (  # noqa: E402
    PKG_SURFACE_VALIDATOR_CLI,
    base_ac_record,
    complete_impl_spec,
    fields_reported_missing,
    run_cli,
    write_ac_yaml,
)

REFERENCE_PENDING = "reference file pending"
MARKER = {"hold_reason": REFERENCE_PENDING}
NAMED_FILE = "config/ac_store_schema.json"  # exists in this repo, so the existence check passes


def _four_fields() -> dict:
    """The technical planner's output: every package-surface field except the reference file."""
    spec = complete_impl_spec()
    del spec["reference_file_path"]
    return spec


def _surface(record_id: str = "ACS-998", spec: dict | None = None, **extra) -> dict:
    """A package-surface record at `reviewed` (the state the approval step reads)."""
    return base_ac_record(
        id=record_id, package_surface=True, readiness="reviewed",
        it_requirements=_four_fields() if spec is None else spec, **extra,
    )


def _verdicts(record: dict, tmp_path: Path) -> dict[str, tuple[bool, str]]:
    """(accepted, output) from the three real validators run on the same record."""
    path = write_ac_yaml(tmp_path / "pkg", f"{record['id']}.yaml", record)
    pkg = run_cli(PKG_SURFACE_VALIDATOR_CLI, str(path))
    schema = cli_verdict(record, tmp_path)
    hook = hook_verdict(record, tmp_path)
    return {
        "validate_ac_schema.py": (schema.accepted, schema.output),
        "commit hook": (hook.accepted, hook.output),
        "validate_ac.py": (not pkg.refused, pkg.output),
    }


def _refused_everywhere(verdicts: dict[str, tuple[bool, str]]) -> bool:
    return all(not accepted for accepted, _ in verdicts.values())


def _store_with_pending(tmp_path: Path):
    """The AC scenario: R is pending (four fields + marker); S is complete (five fields, no marker)."""
    pending = valid_record(
        "ZZR-1a-1", readiness="reviewed", package_surface=True, test_required=False,
        it_requirements=_four_fields(), **MARKER,
    )
    complete = valid_record(
        "ZZR-1a-2", readiness="reviewed", package_surface=True, test_required=False,
        it_requirements={**complete_impl_spec(), "reference_file_path": NAMED_FILE},
    )
    return build(tmp_path, [goal("ZZR-1", ["ZZR-1a-1", "ZZR-1a-2"]), pending, complete])


def test_pending_reference_file_held_at_reviewed(tmp_path):
    # covers: ACD-2500d-2-i
    # angle: criterion
    """R (four fields + marker) stays "reviewed" and the report names R with "reference file pending".

    Wrong versions caught: R is promoted, the reason is another vocabulary value ("test design
    pending"), `file` is absolute or backslashed, S (a complete five-field record, the control row)
    is held too, or R's file is rewritten. Exact counts: one held, one approved.
    """
    store = _store_with_pending(tmp_path)
    before = read_bytes(store, "ZZR-1a-1")

    report = json_of(run_approve(store, "--goal", "ZZR-1", "--json"))

    assert report["held"] == [
        {"id": "ZZR-1a-1", "file": store.rel("ZZR-1a-1"), "reason": REFERENCE_PENDING}
    ], report
    assert report["approved"] == ["ZZR-1a-2"], report
    assert store.read("ZZR-1a-1")["readiness"] == "reviewed"
    assert read_bytes(store, "ZZR-1a-1") == before, "a held record must stay byte-identical"
    assert store.read("ZZR-1a-2")["readiness"] == "approved"


def test_planner_stage_not_failed_for_pending_reference(tmp_path):
    # covers: ACD-2500d-2-i
    # angle: criterion
    """Four fields plus the marker are accepted at every enforcement point of the planner stage.

    The standalone schema validator, the commit hook and validate_ac.py all accept; the rule check at
    stage end (`itpo`) reports no record-schema finding naming `hold_reason` or `reference_file_path`.
    Red today: the schema does not declare `hold_reason` and requires `reference_file_path`.
    """
    from _rule_check_fixtures import check_store, findings_for, finding_text, make_store  # noqa: PLC0415

    verdicts = _verdicts(_surface(**MARKER), tmp_path)
    refusing = {name: out[:300] for name, (accepted, out) in verdicts.items() if not accepted}
    assert refusing == {}, f"the planner's stage is failed for the pending reference file: {refusing}"

    pending = valid_record(
        "ZZR-9", level="L0", readiness="reviewed", package_surface=True,
        test_required=False, it_requirements=_four_fields(), **MARKER,
    )
    _code, report = check_store(make_store(tmp_path / "rc", [pending]), stage="itpo")
    schema_text = [finding_text(f) for f in findings_for(report, "ZZR-9", "record schema")]
    assert schema_text == [], schema_text


def test_after_naming_five_field_validation_unchanged(tmp_path):
    # covers: ACD-2500d-2-i
    # angle: seam
    """From the real pending state, through the file-aware step's own edit, to five-field validation.

    Step 0 (red today): the pending record is accepted. Step 1: the designer's edit (set
    reference_file_path, delete hold_reason) gives a complete record that all three validators accept.
    Step 2: with n_location_rule and required_skills then removed, validation refuses and names exactly
    those two (never the named reference file), as before the change. Step 3: a named file that does
    not exist is refused with the existing "does not exist" message, so the existence check is back
    on once the marker is gone. Wrong version caught: the existence/five-field checks stay skipped
    because the record once carried the marker, or are skipped for every record that has a path.
    """
    record = _surface(**MARKER)
    refusing = [n for n, (ok, _) in _verdicts(record, tmp_path).items() if not ok]
    assert refusing == [], f"the pending record is refused by: {refusing}"

    named = copy.deepcopy(record)
    named["it_requirements"]["reference_file_path"] = NAMED_FILE
    del named["hold_reason"]
    assert all(a for a, _ in _verdicts(named, tmp_path).values()), _verdicts(named, tmp_path)

    thin = copy.deepcopy(named)
    del thin["it_requirements"]["n_location_rule"], thin["it_requirements"]["required_skills"]
    verdicts = _verdicts(thin, tmp_path)
    assert _refused_everywhere(verdicts), verdicts
    for _name, (_accepted, output) in verdicts.items():
        assert {"n_location_rule", "required_skills"} >= fields_reported_missing(output)
    assert fields_reported_missing(verdicts["validate_ac.py"][1]) == {"n_location_rule", "required_skills"}

    ghost = copy.deepcopy(named)
    ghost["it_requirements"]["reference_file_path"] = "config/no_such_reference_file.json"
    _accepted, output = _verdicts(ghost, tmp_path)["validate_ac.py"]
    assert not _accepted and "does not exist at resolved path" in output, output


def test_four_fields_without_marker_still_refused(tmp_path):
    # covers: ACD-2500d-2-i
    # angle: failure
    """A four-field object is refused unless it carries the explicit marker, naming the missing field.

    Control row (red today): with the marker the record is accepted. Negative rows (refused by the
    schema validator, the commit hook and validate_ac.py, which together name `reference_file_path`
    as the missing field): no marker at all, and a `hold_reason` that is another vocabulary value
    ("test design pending"). Wrong version caught: any `hold_reason` (or any key) relaxes the rule, or
    the absence of the key is read as "pending".
    """
    assert all(a for a, _ in _verdicts(_surface(**MARKER), tmp_path).values()), "control row refused"
    rows = {
        "no marker": _surface(),
        "other hold reason": _surface(hold_reason="test design pending"),
    }
    for label, record in rows.items():
        verdicts = _verdicts(record, tmp_path)
        assert _refused_everywhere(verdicts), (label, verdicts)
        text = " ".join(output for _accepted, output in verdicts.values())
        assert fields_reported_missing(text) == {"reference_file_path"}, (label, text[:400])


def test_hold_reason_schema_lockstep_and_required_lists():
    # covers: ACD-2500d-2-i
    # angle: real_artifact
    """`hold_reason` is declared as a string whose enum IS HOLD_REASONS, and the two five-field lists relax.

    Read from the real schema file. `reference_file_path` is dropped from the object branch's
    `required` list and from the root `then` list (both held the five fields before), while the other
    four stay required in both (control: nothing else was loosened).
    """
    from _impl_readiness_gate import HOLD_REASONS  # noqa: PLC0415

    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    declared = schema["properties"].get("hold_reason")
    assert declared is not None, "hold_reason is not declared in config/ac_store_schema.json"
    assert declared.get("type") == "string"
    assert tuple(declared.get("enum", ())) == tuple(HOLD_REASONS)

    object_branch = next(b for b in schema["properties"]["it_requirements"]["oneOf"] if b.get("type") == "object")
    then_list = schema["then"]["properties"]["it_requirements"]["required"]
    others = {"config_schema_fragment", "n_location_rule", "required_skills", "post_write_commands"}
    for name, required in (("object branch", object_branch["required"]), ("root then", then_list)):
        assert "reference_file_path" not in required, f"{name} still requires reference_file_path"
        assert others <= set(required), f"{name} loosened more than the reference file: {required}"


def test_approval_hold_order_and_marker_boundaries():
    # covers: ACD-2500d-2-i
    # angle: boundary
    """approval_hold_reason reports "reference file pending" from the marker alone, in the vocabulary order.

    Rows: marker on a record with no intent: "reference file pending"; the same record once the marker
    is cleared and the file named: None (a control that the hold follows the marker, not the
    package_surface flag); marker plus intent with no design: "test design pending" (it comes first in
    APPROVAL_HOLD_CHECKS); marker with the intent fully designed: "reference file pending".
    """
    from _acd_2500b_approval_fixtures import TWO, design_for  # noqa: PLC0415

    holds = holds_module()
    spec = {**complete_impl_spec(), "reference_file_path": NAMED_FILE}
    base = {"package_surface": True, "test_required": False}
    rows = {
        "marker alone": (valid_record("ZZR-2a-1", readiness="reviewed", it_requirements=_four_fields(), **base, **MARKER), REFERENCE_PENDING),
        "named, marker cleared": (valid_record("ZZR-2a-2", readiness="reviewed", it_requirements=spec, **base), None),
        "marker and undesigned intent": (reviewed_intent("ZZR-2a-3", package_surface=True, it_requirements=_four_fields(), **MARKER), "test design pending"),
        "marker and designed intent": (reviewed_intent("ZZR-2a-4", spec=design_for(TWO), package_surface=True, it_requirements=_four_fields(), **MARKER), REFERENCE_PENDING),
    }
    wrong = {k: holds.approval_hold_reason(r) for k, (r, want) in rows.items() if holds.approval_hold_reason(r) != want}
    assert wrong == {}, f"unexpected hold reasons (label -> got): {wrong}"
    assert len(holds.APPROVAL_HOLD_CHECKS) >= 2


def test_acd_2500d_2_i_reachable_from_entry_point(tmp_path):
    # covers: ACD-2500d-2-i
    # angle: reachability
    """The AC scenario through the real approval CLI, as a subprocess, with its result consumed.

    Entry point: `python scripts/ac_store/approve_acs.py --ac ZZR-1a-1 --json` (CLI), then the text
    mode of the same CLI. R stays reviewed (the file on disk is the proof, not the report alone), the
    text mode prints `held ZZR-1a-1: reference file pending`, a second run is idempotent, and the
    complete sibling S is promoted by the goal-mode run.
    """
    store = _store_with_pending(tmp_path)
    before = read_bytes(store, "ZZR-1a-1")

    single = json_of(run_approve(store, "--ac", "ZZR-1a-1", "--json"))
    assert single["held"] == [{"id": "ZZR-1a-1", "file": store.rel("ZZR-1a-1"), "reason": REFERENCE_PENDING}], single
    assert read_bytes(store, "ZZR-1a-1") == before

    text = run_approve(store, "--goal", "ZZR-1")
    assert f"held ZZR-1a-1: {REFERENCE_PENDING}" in text.stdout, text.stdout
    assert store.read("ZZR-1a-1")["readiness"] == "reviewed"
    assert store.read("ZZR-1a-2")["readiness"] == "approved"
    again = json_of(run_approve(store, "--goal", "ZZR-1", "--json"))
    assert [h["id"] for h in again["held"]] == ["ZZR-1a-1"] and again["approved"] == [], again


@pytest.mark.parametrize("which", ["schema", "hook"])
def test_marker_value_outside_the_vocabulary_is_refused_naming_the_field(tmp_path, which):
    # covers: ACD-2500d-2-i
    # angle: boundary
    """A made-up hold_reason is refused naming the bad value, not as an "undeclared property".

    Control (red today): the real marker is accepted by the same validator in the same run, so the
    refusal below cannot be the "Additional properties" error the undeclared field gives today.
    """
    probe = cli_verdict if which == "schema" else hook_verdict
    assert probe(_surface(**MARKER), tmp_path).accepted, "control row refused"
    verdict = probe(_surface(hold_reason="made-up reason"), tmp_path)
    assert not verdict.accepted
    assert "made-up reason" in verdict.output and "was unexpected" not in verdict.output, verdict.output[:400]
