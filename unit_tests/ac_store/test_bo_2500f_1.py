"""
MODULE: unit_tests/ac_store/test_bo_2500f_1.py
GOAL: RED tests for BO-2500f-1 (PR 1: the validator only) -- a test-free record
    names how it is verified in a typed ``verified_by`` record, refused when
    incomplete. The done rule (BO-2500f-4), the stated-reason rule and the
    misplaced-record report are NOT covered here.

API UNDER TEST (to be created): scripts/ac_store/_verification_record.py

    validate_verification_record(record) -> {
        "valid": bool,
        "method": "check" | "inspection" | None,
        "problems": [{"part": str, "message": str}],
    }
    Takes the WHOLE AC record mapping, never raises, and every problem message
    names the record id and the part.

PART-NAME VOCABULARY (each problem's ``part`` is exactly one of these):
    verified_by            the record is absent / null / empty / not a mapping
    verified_by.method     method absent or not exactly 'check' | 'inspection'
                           (the message names the offending value)
    verified_by.check      check form: source path absent or empty;
                           inspection form: a cross-method part present
    verified_by.wired_as   check form: absent, or not 'pre-commit:<id>' /
                           'build-phase:<name>' with a non-empty id; inspection
                           form: a cross-method part present
    verified_by.gate_run   inspection form: absent or empty; check form: a
                           cross-method part present
    verified_by.statement  inspection form: absent or empty
    verified_by.inspected  inspection form: absent, an empty list, or an entry
                           lacking ``path`` or with a ``blob`` that is not 40 hex
                           characters (message names path/blob)
    change_target          (BO-2500f-1-i) see test_bo_2500f_1_i.py

Red today: ``_verification_record`` does not exist (ModuleNotFoundError), the
store schema refuses ``verified_by`` as an additional property, and the module is
not in AC_STORE_DEPLOY_MAP.
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent))

import copy
import json
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

import pytest

from _bo_2500f_1_support import (  # noqa: E402
    BLOB, RECORD_ID, REPO_ROOT, VALIDATE_SCRIPT, check_form, inspection_form,
    parts, record, validator,
)


def _only_part(verdict: dict, part: str, *, where: str) -> None:
    assert verdict["valid"] is False, f"{where}: must be refused, got {verdict}"
    assert parts(verdict) == [part], f"{where}: expected exactly one problem on {part}, got {verdict['problems']}"
    message = verdict["problems"][0]["message"]
    assert RECORD_ID in message, f"{where}: message must name the record id: {message!r}"
    assert part in message, f"{where}: message must name the part {part!r}: {message!r}"


def test_bo_2500f_1_unknown_method_value_is_refused_naming_the_value():
    # covers: BO-2500f-1
    # angle: boundary
    """AC: any method other than check/inspection is refused, naming the value."""
    validate = validator()
    for bad in ("analysis", "test", "Check", " inspection"):
        verdict = validate(record({"method": bad}))
        assert verdict["valid"] is False and verdict["method"] is None, verdict
        assert "verified_by.method" in parts(verdict), verdict
        problem = next(p for p in verdict["problems"] if p["part"] == "verified_by.method")
        assert bad in problem["message"], problem
        assert RECORD_ID in problem["message"], problem
    for bad in ("", None, ["check"], 7):
        verdict = validate(record({"method": bad}))
        assert verdict["valid"] is False and verdict["method"] is None, (bad, verdict)
        assert "verified_by.method" in parts(verdict), (bad, verdict)
        assert all(RECORD_ID in p["message"] for p in verdict["problems"]), verdict
    # verified_by is not a mapping at all: refused, never raises.
    for bad in ("check", 3, ["check"], True):
        verdict = validate(record(bad))
        assert verdict["valid"] is False and verdict["method"] is None, (bad, verdict)
        assert "verified_by" in parts(verdict), (bad, verdict)
    # control: both closed values in their full valid shapes are valid.
    ok_check = validate(record(check_form()))
    assert ok_check == {"valid": True, "method": "check", "problems": []}, ok_check
    ok_insp = validate(record(inspection_form(), change_target="docs"))
    assert ok_insp == {"valid": True, "method": "inspection", "problems": []}, ok_insp


@pytest.mark.parametrize("mutation,part", [
    (lambda v: v.pop("check"), "verified_by.check"),
    (lambda v: v.update(check=""), "verified_by.check"),
    (lambda v: v.pop("wired_as"), "verified_by.wired_as"),
    (lambda v: v.update(wired_as="cron:x"), "verified_by.wired_as"),
    (lambda v: v.update(wired_as="pre-commit:"), "verified_by.wired_as"),
    (lambda v: v.update(wired_as="build-phase:"), "verified_by.wired_as"),
    (lambda v: v.update(wired_as=""), "verified_by.wired_as"),
    (lambda v: v.update(wired_as="pre-commit:x\n"), "verified_by.wired_as"),
])
def test_bo_2500f_1_check_record_missing_check_or_wiring_is_refused_part_by_part(mutation, part):
    # covers: BO-2500f-1
    # angle: boundary
    """AC: a check record lacking its check or its wiring is refused, naming that part."""
    validate = validator()
    form = check_form()
    mutation(form)
    _only_part(validate(record(form)), part, where=f"{part} / {form}")
    # control row: the complete record is valid, for both wiring kinds.
    assert validate(record(check_form()))["valid"] is True
    phase = check_form()
    phase["wired_as"] = "build-phase:ac_store"
    assert validate(record(phase)) == {"valid": True, "method": "check", "problems": []}


@pytest.mark.parametrize("mutation,part", [
    (lambda v: v.pop("gate_run"), "verified_by.gate_run"),
    (lambda v: v.pop("statement"), "verified_by.statement"),
    (lambda v: v.update(statement=""), "verified_by.statement"),
    (lambda v: v.pop("inspected"), "verified_by.inspected"),
    (lambda v: v.update(inspected=[]), "verified_by.inspected"),
    (lambda v: v.update(inspected=[{"blob": BLOB}]), "verified_by.inspected"),
    (lambda v: v.update(inspected=[{"path": "a.md", "blob": "xyz"}]), "verified_by.inspected"),
    (lambda v: v.update(inspected=[{"path": "a.md", "blob": BLOB[:39]}]), "verified_by.inspected"),
    (lambda v: v.update(inspected=[{"path": "a.md", "blob": BLOB + "0"}]), "verified_by.inspected"),
    (lambda v: v.update(inspected=[{"path": "a.md", "blob": BLOB + "\n"}]), "verified_by.inspected"),
    (lambda v: v.update(inspected=[{"path": "a.md", "blob": BLOB}, {"path": "b.md"}]), "verified_by.inspected"),
])
def test_bo_2500f_1_inspection_record_missing_any_part_or_with_empty_file_list_is_refused(mutation, part):
    # covers: BO-2500f-1
    # angle: boundary
    """AC: an inspection record missing any part, or with an empty file list, is refused."""
    validate = validator()
    form = inspection_form()
    mutation(form)
    # change_target docs so the BO-2500f-1-i restriction cannot be what refuses it.
    _only_part(validate(record(form, change_target="docs")), part, where=f"{part} / {form}")
    # control row: complete record, many files, is valid.
    many = inspection_form()
    many["inspected"] = [{"path": f"f{i}.md", "blob": BLOB} for i in range(3)]
    assert validate(record(many, change_target="docs")) == {
        "valid": True, "method": "inspection", "problems": []}


def test_bo_2500f_1_part_of_the_other_method_is_refused_naming_that_part():
    # covers: BO-2500f-1
    # angle: discrimination
    """AC: a check carrying gate_run, or an inspection carrying check/wired_as, is refused naming it.

    Catches (a) a validator checking only the stated method's required parts and
    ignoring extra keys, (b) one that names the method but not the foreign part.
    """
    validate = validator()
    # check form + a gate run reference: each per-method required part is present.
    form = check_form()
    form["gate_run"] = "pf-20261025-0912"
    verdict = validate(record(form))
    _only_part(verdict, "verified_by.gate_run", where="check + gate_run")
    assert verdict["method"] == "check", "the stated method is still reported"
    # inspection form + a hook (check, wired_as, both).
    for extra, expected in (
        ({"check": "templates/x.py"}, ["verified_by.check"]),
        ({"wired_as": "pre-commit:x"}, ["verified_by.wired_as"]),
        ({"check": "templates/x.py", "wired_as": "pre-commit:x"},
         ["verified_by.check", "verified_by.wired_as"]),
    ):
        form = inspection_form()
        form.update(extra)
        verdict = validate(record(form, change_target="docs"))
        assert verdict["valid"] is False, (extra, verdict)
        assert sorted(parts(verdict)) == sorted(expected), (extra, verdict)
        assert verdict["method"] == "inspection", verdict
        for problem in verdict["problems"]:
            assert RECORD_ID in problem["message"] and problem["part"] in problem["message"], problem
    # control: no foreign part, both methods valid.
    assert validate(record(check_form()))["valid"] is True
    assert validate(record(inspection_form(), change_target="docs"))["valid"] is True


def test_bo_2500f_1_record_with_no_verification_record_is_refused_naming_the_missing_record():
    # covers: BO-2500f-1
    # angle: failure
    """AC: no verified_by (absent, null, empty mapping) is refused, naming verified_by."""
    validate = validator()
    for label, rec in (
        ("absent", record()),
        ("null", record(None)),
        ("empty mapping", record({})),
    ):
        verdict = validate(rec)
        _only_part(verdict, "verified_by", where=label)
        assert verdict["method"] is None, (label, verdict)
    # never raises on a record that is not a mapping at all.
    for junk in (None, "x", 3, [], [1]):
        verdict = validate(junk)
        assert verdict["valid"] is False and verdict["method"] is None, (junk, verdict)
        assert verdict["problems"], junk


def test_bo_2500f_1_verified_by_is_declared_in_the_store_schema_without_a_write_time_rule():
    # covers: BO-2500f-1
    # angle: seam
    """AC: verified_by is declared in config/ac_store_schema.json, permissively (no write-time rule)."""
    schema = json.loads((REPO_ROOT / "config" / "ac_store_schema.json").read_text(encoding="utf-8"))
    declared = schema["properties"]
    assert "verified_by" in declared, "verified_by must be declared (top-level additionalProperties is false)"
    text = json.dumps(declared["verified_by"])
    assert '"if"' not in text and '"then"' not in text and '"required"' not in text, (
        "the declaration must carry no if/then and no required keys: validity is decided at mark time")
    # Seam: the REAL validator CLI accepts a record carrying any verified_by shape.
    from _rule_check_fixtures import make_store, valid_record
    shapes = [check_form(), inspection_form(), {"method": "analysis"}, {}, None, "free text", ["x"], True, 3]
    with tempfile.TemporaryDirectory() as tmp:
        for index, shape in enumerate(shapes):
            rec = valid_record(f"BO-9997f-{index + 1}", verified_by=copy.deepcopy(shape))
            store = make_store(Path(tmp) / f"s{index}", [rec])
            proc = subprocess.run([sys.executable, str(VALIDATE_SCRIPT), str(store.path(rec["id"]))],
                                  capture_output=True, text=True, timeout=60)
            assert proc.returncode == 0, (
                f"verified_by={shape!r} refused by validate_ac_schema.py: {proc.stdout}{proc.stderr}")


def test_bo_2500f_1_verification_module_imports_in_the_deployed_layout():
    # covers: BO-2500f-1
    # angle: deployed
    """AC: the module is in AC_STORE_DEPLOY_MAP and imports from the DEPLOYED copy in a fresh process."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    try:
        import build_phases_ac_store
    finally:
        sys.path.pop(0)
    sources = [src for src, _dest in build_phases_ac_store.AC_STORE_DEPLOY_MAP]
    assert "scripts/ac_store/_verification_record.py" in sources, (
        "scripts/ac_store/_verification_record.py must be in AC_STORE_DEPLOY_MAP")
    dests = [dest for src, dest in build_phases_ac_store.AC_STORE_DEPLOY_MAP
             if src == "scripts/ac_store/_verification_record.py"]
    assert dests == ["_verification_record.py"], dests
    deployed_dir = REPO_ROOT / ".leafcutter" / "scripts" / "ac_store"
    deployed = deployed_dir / "_verification_record.py"
    assert deployed.is_file(), (
        f"deployed copy missing at {deployed}; run `python scripts/build.py --target-dir .` "
        "(a missing deployed module is a failure, never a skip)")
    proc = subprocess.run(
        [sys.executable, "-I", "-c", textwrap.dedent(f"""\
            import sys
            sys.path.insert(0, {str(deployed_dir)!r})
            from _verification_record import validate_verification_record
            v = validate_verification_record({{"id": "X-1", "verified_by": {{"method": "analysis"}}}})
            assert v["valid"] is False
            print("ok")
        """)],
        capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0 and "ok" in proc.stdout, proc.stdout + proc.stderr
