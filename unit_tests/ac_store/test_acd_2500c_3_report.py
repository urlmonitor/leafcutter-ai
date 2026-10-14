"""
MODULE: unit_tests/ac_store/test_acd_2500c_3_report.py
COVERS: ACD-2500c-3
GOAL: Second half of the ACD-2500c-3 (ticket 22) red tests, split by concern from
    test_acd_2500c_3.py: the generator seam (new keys dropped, must_catch carried, generated
    ticket valid against the closed test_requirements schema), the real-store scan for undeclared
    entry keys, and the by-author report CLI (design_authors_report.py) with the reachability test.
    The record builders live in _acd_2500c_3_fixtures.py. See test_acd_2500c_3.py for the full
    background, architecture and red-state notes.
"""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import jsonschema
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "ac_store"))

from _acd_2500_schema_probe import REPO_ROOT, SCHEMA_FILE, hook_verdict  # noqa: E402
from _acd_2500c_3_fixtures import (  # noqa: E402
    MUST_CATCH,
    STEP,
    _accepted_by_all,
    _run_report,
    _write_store,
    base_record,
    code_aware_record,
    legacy_record,
    CRITERIA,
)
from _tkt_500f_support import generate_written, make_ac  # noqa: E402

TEST_REQUIREMENTS_SCHEMA = REPO_ROOT / "config" / "test_requirements.schema.json"
STORE_ROOT = REPO_ROOT / "docs" / "acceptance-criteria"
_TESTS_BLOCK_RE = re.compile(r"##\s+Test\s+Requirements\b.*?```(?:yaml)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


# --------------------------------------------------------------------------
# seams: the generator and the ticket schema
# --------------------------------------------------------------------------
def _ac_for_generation(record: dict) -> dict:
    ac = make_ac(assigned_agent="python-coder")
    ac["criteria"] = record["criteria"]
    ac["test_spec"] = copy.deepcopy(record["test_spec"])
    return ac


def _generated_entries(ac: dict, ac_id: str) -> list[dict]:
    generated = generate_written(ac, ac_id)
    assert generated.exit_code == 0, generated.warnings
    match = _TESTS_BLOCK_RE.search(generated.text)
    assert match is not None, generated.text[:800]
    return [e for e in yaml.safe_load(match.group(1))["tests"] if isinstance(e, dict)]


def test_code_aware_entry_with_must_catch_and_discrimination_accepted(tmp_path):
    # covers: ACD-2500c-3
    # angle: seam
    """The new per-entry keys sit next to the EXISTING must_catch and angle 'discrimination': the
    store accepts the combination (both validators, red today: the new keys are undeclared), and the
    real generator turns that same design into a ticket entry that carries must_catch verbatim
    (same strings, same order), the angle, and NONE of the new keys (they are dropped, never
    copied: the ticket schema is closed). The generator half already holds today; the acceptance
    half is the red one."""
    record = code_aware_record("ZZD-1")
    record["test_spec"][0].update({"must_catch": list(MUST_CATCH), "angle": "discrimination"})

    _accepted_by_all(record, tmp_path)
    entries = _generated_entries(_ac_for_generation(record), "ZZD-1")

    target = next(e for e in entries if e["name"] == "test_design_is_accepted")
    assert target["must_catch"] == MUST_CATCH
    assert target["angle"] == "discrimination"
    for key in ("proves_clause", "code_file", "to_be_created", "convention_test_file"):
        assert key not in target, f"{key} must be dropped from the ticket entry: {target}"


def test_generated_ticket_valid_against_test_requirements_schema(tmp_path):
    # covers: ACD-2500c-3
    # angle: seam
    """Real producer into real consumer: a design the store ACCEPTS (checked first, the red half)
    is given to the real generator, and every generated Test Requirements entry validates against
    config/test_requirements.schema.json ($defs.test_entry, which is closed). A generator that
    copied the new keys through would fail here; the entries must also be the design's own."""
    record = code_aware_record("ZZD-1")
    _accepted_by_all(record, tmp_path)
    entries = _generated_entries(_ac_for_generation(record), "ZZD-1")
    schema = json.loads(TEST_REQUIREMENTS_SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema["$defs"]["test_entry"])

    names = {e["name"] for e in entries}
    assert {"test_design_is_accepted", "test_author_is_reported"} <= names, names
    for generated in entries:
        assert [err.message for err in validator.iter_errors(generated)] == [], generated



def test_real_store_has_no_undeclared_entry_key():
    # covers: ACD-2500c-3
    # angle: real_artifact
    """Closing the entry key set by name reports nothing new on the real store: every test_spec entry
    of every stored record uses only declared keys (no hard-coded counts: the store grows).
    Control row first: the SAME check, given a real stored record with one undeclared key added,
    names that key, so a validator that never judges keys cannot pass this test."""
    from _ac_schema_test_spec_validators import test_spec_entry_errors

    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    records = []
    for path in sorted(STORE_ROOT.rglob("*.yaml")):
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.CSafeLoader)
        if isinstance(data, dict) and isinstance(data.get("test_spec"), list) and data["test_spec"]:
            records.append((path, data))
    assert records, "the real store holds records with a test_spec"

    probe_path, probe = records[0]
    probe = copy.deepcopy(probe)
    probe["test_spec"][0]["zz_not_a_declared_key"] = 1
    control = test_spec_entry_errors(probe_path, probe, schema)
    assert any("'zz_not_a_declared_key'" in message for message in control), control

    offenders = [
        message for path, data in records for message in test_spec_entry_errors(path, data, schema)
        if "undeclared key" in message
    ]
    assert offenders == [], offenders[:5]


# --------------------------------------------------------------------------
# the by-author query and the reachability test
# --------------------------------------------------------------------------
def test_design_authors_report_json_groups_by_step_and_lists_legacy(tmp_path):
    # covers: ACD-2500c-3
    # angle: criterion
    """`design_authors_report.py --ac-root DIR --json` prints exactly {by_step: {step: [ids]}, legacy:
    [ids]}: ids sorted, designs grouped by the mark's step, every unmarked design under legacy,
    records without a design (no test_spec, or an empty one) in neither, files that are not records
    (a YAML list, a record without an id) skipped, nested folders walked. Exit code 0."""
    root = tmp_path / "store"
    other = code_aware_record("ZZD-3", test_design_authorship={"step": "other-designer", "date": "2026-10-15"})
    _write_store(root, [
        ("a", legacy_record("ZZD-5")),
        ("a", code_aware_record("ZZD-2")),
        ("b/nested", code_aware_record("ZZD-1")),
        ("b", other),
        ("b", legacy_record("ZZD-4")),
        ("b", base_record("ZZD-6", criteria=CRITERIA)),
        ("b", base_record("ZZD-7", criteria=CRITERIA, test_spec=[])),
    ])
    (root / "a" / "list.yaml").write_text(yaml.safe_dump(["not", "a", "record"]), encoding="utf-8")
    noid = legacy_record("ZZD-8")
    noid.pop("id")
    (root / "a" / "noid.yaml").write_text(yaml.safe_dump(noid), encoding="utf-8")

    code, payload, _ = _run_report(["--ac-root", str(root), "--json"])

    assert code == 0
    assert payload == {
        "by_step": {"other-designer": ["ZZD-3"], STEP: ["ZZD-1", "ZZD-2"]},
        "legacy": ["ZZD-4", "ZZD-5"],
    }


def test_design_authors_report_over_an_empty_store_and_in_text_mode(tmp_path):
    # covers: ACD-2500c-3
    # angle: boundary
    """An empty store reports {by_step: {}, legacy: []} with exit 0 (it describes, it never gates). Text
    mode prints one line per step and a `legacy: N` line."""
    empty = tmp_path / "empty"
    empty.mkdir()
    code, payload, _ = _run_report(["--ac-root", str(empty), "--json"])
    assert code == 0
    assert payload == {"by_step": {}, "legacy": []}

    root = tmp_path / "store"
    _write_store(root, [("a", code_aware_record("ZZD-1")), ("a", legacy_record("ZZD-2")), ("a", legacy_record("ZZD-3"))])
    code, _, text = _run_report(["--ac-root", str(root)])
    lines = [line.strip() for line in text.splitlines()]
    assert code == 0
    assert sum(1 for line in lines if STEP in line) == 1, text
    assert "legacy: 2" in lines, text


def test_acd_2500c_3_reachable_from_entry_point(tmp_path):
    # covers: ACD-2500c-3
    # angle: reachability
    """Entry points resolved (Step 1.2 and 1.1): the REAL commit hook `scripts/commit_guardian/
    check_ac_schema.py` (registered in .pre-commit-config.yaml) and the CLI script
    `scripts/ac_store/design_authors_report.py`, both as subprocesses. The hook blocks a staged
    record with an undeclared entry key (exit 1, key named) and passes the corrected one (exit 0);
    the report CLI then lists the corrected code-aware design under its step. The rejection is
    consumed in control flow (the hook's exit code), not just printed."""
    bad = code_aware_record("ZZD-1")
    bad["test_spec"][0]["proves_claus"] = bad["test_spec"][0].pop("proves_clause")
    blocked = hook_verdict(bad, tmp_path / "bad")
    assert not blocked.accepted and blocked.exit_code == 1
    assert "undeclared key 'proves_claus'" in blocked.output, blocked.output

    good = code_aware_record("ZZD-1")
    assert hook_verdict(good, tmp_path / "good").accepted

    root = tmp_path / "store"
    _write_store(root, [("c", good)])
    code, payload, _ = _run_report(["--ac-root", str(root), "--json"])
    assert code == 0
    assert payload == {"by_step": {STEP: ["ZZD-1"]}, "legacy": []}
