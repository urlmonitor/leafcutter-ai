"""
MODULE: unit_tests/ac_store/test_acd_2500c_3.py
COVERS: ACD-2500c-3
GOAL: Red-first specification of ACD-2500c-3 (ticket 22): each test-design entry is tied
    to the outcome clause it proves, and the design carries its author.
    - config/ac_store_schema.json declares four optional per-entry keys on test_spec items
      (proves_clause, code_file, to_be_created, convention_test_file) and two record-level
      properties (test_design_authorship {step, date}, test_design_opened_files);
    - a code-aware design is accepted, a legacy design (no mark, no new keys) is accepted
      AND reported as legacy by the by-author query
      (scripts/ac_store/design_authors_report.py, --json);
    - an entry key the schema does not declare is rejected NAMING the key, at the standalone
      validator and at the commit hook, with identical verdicts (the shared module
      _ac_schema_test_spec_validators.py reads the declared set FROM the schema);
    - the ticket generator drops the new keys and still copies must_catch verbatim, so a
      ticket generated from a code-aware design validates against
      config/test_requirements.schema.json (the two schemas are coupled by hand).
BUSINESS CONTEXT: ADR-071 section 6: legacy designs are kept and told apart from new
    ones only by the missing authorship mark, through one predicate
    (`is_legacy_design`, scripts/ac_store/_test_intent.py). Tickets 23 and 25 read the two
    record keys pinned here.
ARCHITECTURE (architect note, ticket 22, sections 1 and 2): the entry-key rejection cannot
    come from jsonschema alone (test_spec is a oneOf, so a stray key is reported only as
    "is not valid under any of the given schemas"); it is hand-rolled in the shared module.
    Both entry points are driven as REAL subprocesses (unit_tests/ac_store/_acd_2500_schema_probe.py);
    fixtures are written by yaml.safe_dump, never typed as YAML.

RED STATE: the schema declares none of the new properties, so a code-aware record is
    rejected (an ASSERTION red); is_legacy_design, the constants and design_authors_report.py
    do not exist (an ABSENCE red: ModuleNotFoundError / ImportError / the CLI script is
    missing).

PASSING-TODAY PARTS: the generator already drops unknown keys by construction (it builds each
    ticket entry from a fixed key list). Those halves cannot be red; each test that contains
    one also contains a half that is red today, and the note in the test says which.
"""


from __future__ import annotations

import copy
import datetime
import json
import re
from pathlib import Path

import pytest
import yaml

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "ac_store"))

from _acd_2500_schema_probe import (  # noqa: E402
    SCHEMA_FILE,
    base_record,
    both_verdicts,
    cli_verdict,
    hook_verdict,
    in_process_verdict,
)
from _acd_2500c_3_fixtures import (  # noqa: E402
    CRITERIA,
    STEP,
    _accepted_by_all,
    _control_accepted,
    _run_report,
    _test_intent_module,
    code_aware_record,
    legacy_record,
)

# --------------------------------------------------------------------------
# acceptance: code-aware and legacy
# --------------------------------------------------------------------------
def test_code_aware_design_accepted_with_provenance(tmp_path):
    # covers: ACD-2500c-3
    # angle: real_artifact
    """AC clause 1, through the standalone validator AND the commit hook (real subprocesses over a
    yaml.safe_dump record): the authorship mark (step + date), the opened-files list and, on every
    entry, the clause it proves, the code file, the to-be-created flag and the convention test
    file are accepted. The date is also written UNQUOTED (the real serializer emits `2026-10-14`
    for a date object, which loads as a datetime.date): it must be accepted too."""
    _accepted_by_all(code_aware_record("ZZD-1"), tmp_path / "quoted")

    unquoted = code_aware_record(
        "ZZD-3", test_design_authorship={"step": STEP, "date": datetime.date(2026, 10, 14)}
    )
    cli = cli_verdict(unquoted, tmp_path / "unquoted")
    written = (tmp_path / "unquoted" / "cli" / "ZZD-3.yaml").read_text(encoding="utf-8")
    assert re.search(r"^\s+date: 2026-10-14$", written, re.MULTILINE), f"fixture is not the unquoted trap:\n{written}"
    assert cli.accepted, cli.output
    assert hook_verdict(unquoted, tmp_path / "unquoted").accepted


def test_legacy_design_accepted_and_reported_legacy(tmp_path):
    # covers: ACD-2500c-3
    # angle: criterion
    """AC clause 2: a legacy design (no mark, no new key) is accepted by both validators, and the
    by-author query (`design_authors_report.py --json`) lists it under `legacy`, while the
    code-aware design is listed under its step. A record with no design appears in neither."""
    _accepted_by_all(legacy_record("ZZD-2"), tmp_path / "legacy")
    store = tmp_path / "store" / "comp"
    store.mkdir(parents=True)
    for record in (code_aware_record("ZZD-1"), legacy_record("ZZD-2"), base_record("ZZD-6", criteria=CRITERIA)):
        (store / f"{record['id']}.yaml").write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8")

    code, payload, _ = _run_report(["--ac-root", str(tmp_path / "store"), "--json"])

    assert code == 0
    assert payload == {"by_step": {STEP: ["ZZD-1"]}, "legacy": ["ZZD-2"]}


def test_is_legacy_design_is_the_one_predicate():
    # covers: ACD-2500c-3
    # angle: boundary
    """is_legacy_design(record): test_spec non-empty AND no authorship mark. A marked design, a record
    with no design, and an empty test_spec are NOT legacy; nobody re-derives this elsewhere."""
    mod = _test_intent_module()
    spec = [{"name": "test_a", "target_dir": "unit_tests/"}]
    mark = {"step": STEP, "date": "2026-10-14"}

    assert mod.is_legacy_design({"test_spec": spec}) is True
    assert mod.is_legacy_design({"test_spec": spec, mod.AUTHORSHIP_KEY: mark}) is False
    assert mod.is_legacy_design({}) is False
    assert mod.is_legacy_design({"test_spec": []}) is False
    assert mod.is_legacy_design({"test_spec": None}) is False
    assert mod.is_legacy_design({mod.AUTHORSHIP_KEY: mark}) is False


# --------------------------------------------------------------------------
# rejection by name
# --------------------------------------------------------------------------
def test_unknown_entry_key_rejected_naming_key(tmp_path):
    # covers: ACD-2500c-3
    # angle: failure
    """AC clause 3 at BOTH enforcement points, with identical verdicts. Control row: the correctly
    spelled `proves_clause` is accepted. Negative row: the typo `proves_claus` on one entry is
    rejected by the standalone validator and by the commit hook, and each message names the
    entry and states `undeclared key 'proves_claus'` (not the generic oneOf text). A key inside the
    authorship mark and a key at the record root are rejected by name too."""
    _accepted_by_all(code_aware_record("ZZD-1"), tmp_path / "control")

    typo = code_aware_record("ZZD-4")
    typo["test_spec"][1]["proves_claus"] = typo["test_spec"][1].pop("proves_clause")
    cli, hook = both_verdicts(typo, tmp_path / "typo")
    assert (cli.accepted, hook.accepted) == (False, False)
    for output in (cli.output, hook.output):
        assert re.search(r"undeclared key 'proves_claus'", output), output
        assert "test_author_is_reported" in output, output

    mark = code_aware_record(
        "ZZD-5", test_design_authorship={"step": STEP, "date": "2026-10-14", "extra_mark_key": 1}
    )
    cli, hook = both_verdicts(mark, tmp_path / "mark")
    assert (cli.accepted, hook.accepted) == (False, False)
    assert "'extra_mark_key'" in cli.output and "'extra_mark_key'" in hook.output

    root = code_aware_record("ZZD-6", bogus_root_key="x")
    cli, hook = both_verdicts(root, tmp_path / "root")
    assert (cli.accepted, hook.accepted) == (False, False)
    assert "'bogus_root_key'" in cli.output and "'bogus_root_key'" in hook.output


def test_each_undeclared_key_is_one_error_in_sorted_order():
    # covers: ACD-2500c-3
    # angle: boundary
    """The shared validator (test_spec_entry_errors) reports ONE error per undeclared key, sorted, each
    `{path}: test_spec entry {name!r} has undeclared key {key!r}`; an entry with only declared keys
    reports nothing (control row, in the same call); a non-dict entry is skipped, as today."""
    from _ac_schema_test_spec_validators import test_spec_entry_errors

    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    good = {"name": "test_ok", "target_dir": "unit_tests/", "framework": "pytest"}
    bad = {"name": "test_bad", "target_dir": "unit_tests/", "zz_late": 1, "aa_early": 2}
    data = {"test_spec": [good, bad, "not-a-dict"]}

    errors = test_spec_entry_errors(Path("ZZD-9.yaml"), data, schema)

    assert len(errors) == 2, errors
    assert "has undeclared key 'aa_early'" in errors[0]
    assert "has undeclared key 'zz_late'" in errors[1]
    assert all("'test_bad'" in e and e.startswith("ZZD-9.yaml") for e in errors)


def test_declared_entry_keys_are_read_from_the_schema_not_a_second_list():
    # covers: ACD-2500c-3
    # angle: discrimination
    """WRONG VERSION THIS CATCHES: a validator with its own hand-typed list of entry keys. The same
    entry (carrying `future_key`) is rejected under the real schema and accepted once the schema
    declares `future_key`, with no code change; with no schema loaded nothing is judged (the closed
    set is unknowable; the hook already prints its 'schema-level validation was SKIPPED' warning)."""
    from _ac_schema_test_spec_validators import test_spec_entry_errors

    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    widened = copy.deepcopy(schema)
    array_branch = next(b for b in widened["properties"]["test_spec"]["oneOf"] if b.get("type") == "array")
    array_branch["items"]["properties"]["future_key"] = {"type": "string"}
    data = {"test_spec": [{"name": "test_f", "target_dir": "unit_tests/", "future_key": "x"}]}

    rejected = test_spec_entry_errors(Path("ZZD-9.yaml"), data, schema)
    accepted = test_spec_entry_errors(Path("ZZD-9.yaml"), data, widened)

    assert len(rejected) == 1 and "has undeclared key 'future_key'" in rejected[0], rejected
    assert accepted == []
    assert test_spec_entry_errors(Path("ZZD-9.yaml"), data, None) == []


# --------------------------------------------------------------------------
# boundaries of the new properties
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("label", "mark", "expected_in_output"),
    [
        ("missing step", {"date": "2026-10-14"}, "'step'"),
        ("missing date", {"step": STEP}, "'date'"),
        ("empty step", {"step": "", "date": "2026-10-14"}, "test_design_authorship.step"),
        ("date in another format", {"step": STEP, "date": "14.10.2026"}, "test_design_authorship.date"),
        ("date as integer", {"step": STEP, "date": 20261014}, "test_design_authorship.date"),
        ("date as null", {"step": STEP, "date": None}, "test_design_authorship.date"),
        ("mark as null", None, "test_design_authorship"),
        ("mark as string", "test-designer", "test_design_authorship"),
    ],
)
def test_authorship_mark_boundaries_name_the_path(tmp_path, label, mark, expected_in_output):
    # covers: ACD-2500c-3
    # angle: boundary
    """The mark is absent or exactly {step: non-empty string, date: YYYY-MM-DD} (a string or a native
    date): every other shape is rejected and the message names the path. Control row first: a valid
    mark is accepted, so these cannot pass just because the property is undeclared."""
    _control_accepted(tmp_path)

    verdict = in_process_verdict(
        code_aware_record("ZZD-8", test_design_authorship=mark), tmp_path / label.replace(" ", "_")
    )

    assert not verdict.accepted, f"{label} must be rejected"
    assert expected_in_output in verdict.output, verdict.output


@pytest.mark.parametrize(
    ("label", "opened", "accepted"),
    [
        ("empty list is schema-valid on purpose", [], True),
        ("one file", ["scripts/ac_store/_test_intent.py"], True),
        ("not a list", "scripts/ac_store/_test_intent.py", False),
        ("non-string item", ["scripts/ac_store/_test_intent.py", 3], False),
        ("empty-string item", [""], False),
    ],
)
def test_opened_files_list_boundaries(tmp_path, label, opened, accepted):
    # covers: ACD-2500c-3
    # angle: boundary
    """test_design_opened_files: a list of non-empty strings, NO minItems (an empty list is reported
    as 'not grounded' by ACD-2500c-1-i, not rejected by the schema). Control row first."""
    _control_accepted(tmp_path)

    verdict = in_process_verdict(
        code_aware_record("ZZD-8", test_design_opened_files=opened), tmp_path / label.replace(" ", "_")
    )

    assert verdict.accepted is accepted, verdict.output
    if not accepted:
        assert "test_design_opened_files" in verdict.output, verdict.output


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("proves_clause", ""),
        ("code_file", ""),
        ("to_be_created", "yes"),
        ("convention_test_file", ""),
        ("convention_test_file", 5),
    ],
)
def test_per_entry_key_shapes_are_checked(tmp_path, key, value):
    # covers: ACD-2500c-3
    # angle: boundary
    """The four per-entry keys are optional and typed: non-empty strings, and a boolean flag. A
    well-formed entry (control row) is accepted; a malformed value is rejected."""
    _control_accepted(tmp_path)
    record = code_aware_record("ZZD-8")
    record["test_spec"][0][key] = value

    assert not in_process_verdict(record, tmp_path / "bad").accepted, f"{key}={value!r}"


def test_new_per_entry_keys_are_optional_so_legacy_entries_stay_valid(tmp_path):
    # covers: ACD-2500c-3
    # angle: boundary
    """Optional means optional: a code-aware record whose entries omit every per-entry key is
    still schema-valid (presence on code-aware designs is ACD-2500c-1-i's check, not the schema's).
    The record carries the mark, so the declared mark property is what makes it pass."""
    spec = [{"name": "test_plain", "target_dir": "unit_tests/ac_store/"}]

    verdict = in_process_verdict(code_aware_record("ZZD-8", test_spec=spec), tmp_path)

    assert verdict.accepted, verdict.output



# --------------------------------------------------------------------------
# lockstep and the real store
# --------------------------------------------------------------------------
def _item_properties(schema: dict) -> dict:
    array_branch = next(b for b in schema["properties"]["test_spec"]["oneOf"] if b.get("type") == "array")
    return array_branch["items"]["properties"]


def test_constants_match_schema_properties():
    # covers: ACD-2500c-3
    # angle: real_artifact
    """Every name later tickets read is a constant in _test_intent.py, with the pinned value, and
    each is a DECLARED property of the real schema: the four per-entry names among the test_spec
    item properties, the other two among the root properties (so c-1, c-1-i, b-2 and b-3 never
    hand-type one)."""
    mod = _test_intent_module()
    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    per_entry = {
        "ENTRY_CLAUSE_KEY": "proves_clause",
        "ENTRY_CODE_FILE_KEY": "code_file",
        "ENTRY_TO_BE_CREATED_KEY": "to_be_created",
        "ENTRY_CONVENTION_KEY": "convention_test_file",
    }
    record_level = {"AUTHORSHIP_KEY": "test_design_authorship", "OPENED_FILES_KEY": "test_design_opened_files"}

    for constant, value in per_entry.items():
        assert getattr(mod, constant) == value
        assert value in _item_properties(schema), f"{value} not declared on test_spec items"
    for constant, value in record_level.items():
        assert getattr(mod, constant) == value
        assert value in schema["properties"], f"{value} not declared at the record root"

