"""
MODULE: unit_tests/ac_store/test_tq_500g_1_xvii.py
GOAL: RED tests for TQ-500g-1-xvii, the new optional test_spec item field ``declared_replacements``: the real
    validator CLI accepts a well-formed declaration, refuses a declaration for a name the entry's must_catch does
    not list (naming the entry and the name), refuses every malformed shape (naming the entry, the field and the
    name) and still refuses every other unknown key.
BUSINESS CONTEXT: The AC files are written with yaml.safe_dump and checked by scripts/ac_store/validate_ac_schema.py
    run as a subprocess (the gate the check-ac-schema hook runs). The generic jsonschema ``oneOf`` message does not
    name the entry; the hand-rolled, entry-naming validator does, so every refusal is asserted on a line shaped
    ``test_spec entry '<name>' ... declared_replacements ...`` carrying the must_catch name, not on the exit code alone.
"""

from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_VALIDATOR = _REPO_ROOT / "scripts" / "ac_store" / "validate_ac_schema.py"
PROP = "propagation that reaches only one level deep"
OTHER = "drop the _lc_obs_installed guard"
UNLISTED = "invert refresh_due"
OLD, NEW = "if _STATE.entered or _STATE.inherited:", "if _STATE.entered:"

_BASE_AC = {
    "id": "BP-9999f-9", "title": "Fixture AC for the declared_replacements field", "component": "build-pipeline",
    "components": ["build_pipeline"], "status": "active", "readiness": "approved", "priority": "high",
    "level": "L2", "work_status": "todo", "assigned_agent": "python-coder", "estimated_complexity": "S",
    "change_target": "pipeline", "risk_surface": "contract_boundary", "test_required": True,
    "criteria": "Given a fixture,\nWhen it is validated,\nThen the verdict is read.",
    "test_spec": [{"name": "test_a", "target_dir": "unit_tests/x/", "framework": "pytest", "type": "unit",
                   "angle": "criterion", "description": "fixture entry", "must_catch": [PROP, OTHER]}],
}


def _repl(**over) -> dict:
    return {"path": "observer.py", "old": OLD, "new": NEW, **over}


def _validate(tmp_path: Path, label: str, **extra_item_keys) -> tuple[int, str]:
    """Write the fixture AC (yaml.safe_dump) with *extra_item_keys* on its test_spec entry; return (exit code, output)."""
    record = copy.deepcopy(_BASE_AC)
    record["test_spec"][0].update(extra_item_keys)
    path = tmp_path / f"{label}.yaml"
    path.write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8")
    proc = subprocess.run([sys.executable, str(_VALIDATOR), str(path)], capture_output=True, text=True,
                          timeout=120, check=False)
    return proc.returncode, proc.stdout + proc.stderr


def _names_entry_and_field(output: str, *must_contain: str) -> bool:
    """Whether one output line reads ``test_spec entry 'test_a' ... declared_replacements ...`` and carries *must_contain*."""
    pattern = re.compile(r"test_spec entry 'test_a'.*declared_replacements")
    return any(pattern.search(line) and all(m in line for m in must_contain) for line in output.splitlines())


def test_schema_refuses_a_declaration_for_an_unlisted_name(tmp_path):
    # covers: TQ-500g-1-xvii
    # angle: failure
    # Catches: a declaration for a name the entry does not owe accepted
    code, _ = _validate(tmp_path, "control_plain")
    assert code == 0, "control: the fixture AC without the field is valid"
    code, out = _validate(tmp_path, "unlisted", declared_replacements={UNLISTED: [_repl()]})
    assert code == 1, out
    assert _names_entry_and_field(out, UNLISTED), f"the message must name the entry, the field and the name {UNLISTED!r}: {out}"
    code, out = _validate(tmp_path, "listed", declared_replacements={PROP: [_repl()]})
    assert code == 0, f"the same declaration under a listed name is valid: {out}"
    code, out = _validate(tmp_path, "respelled", declared_replacements={PROP.upper(): [_repl()]})
    assert code == 1 and _names_entry_and_field(out, PROP.upper()), f"a key must be spelled exactly as must_catch spells it: {out}"
    code, out = _validate(tmp_path, "two_names", declared_replacements={PROP: [_repl()], OTHER: [_repl(new="")]})
    assert code == 0, f"two listed names, and a replacement whose new text is empty, are valid: {out}"


def test_schema_shape_of_declared_replacements_and_unknown_keys(tmp_path):
    # covers: TQ-500g-1-xvii
    # angle: boundary
    # Catches: additionalProperties dropped from the test_spec item to admit the new field
    # Catches: shape checked only in the JSON schema, which the hook does not enforce
    code, out = _validate(tmp_path, "accepted", declared_replacements={PROP: [_repl(), _repl(old="a", new="b")]})
    assert code == 0, f"a well-formed declaration is accepted: {out}"
    refused = {
        "empty_list": {PROP: []},
        "no_old": {PROP: [{"path": "observer.py", "new": NEW}]},
        "no_new": {PROP: [{"path": "observer.py", "old": OLD}]},
        "no_path": {PROP: [{"old": OLD, "new": NEW}]},
        "non_string_new": {PROP: [_repl(new=5)]},
        "blank_path": {PROP: [_repl(path="  ")]},
        "blank_old": {PROP: [_repl(old=" ")]},
        "extra_key": {PROP: [_repl(why="because")]},
        "not_a_list": {PROP: _repl()},
    }
    for label, value in refused.items():
        code, out = _validate(tmp_path, label, declared_replacements=value)
        assert code == 1, f"{label}: a malformed declaration was accepted"
        assert _names_entry_and_field(out, PROP), f"{label}: the message must name the entry, the field and the name: {out}"
    code, out = _validate(tmp_path, "not_an_object", declared_replacements=[_repl()])
    assert code == 1 and _names_entry_and_field(out), f"a non-object value is refused, naming the entry and the field: {out}"
    code, out = _validate(tmp_path, "unknown_key", declared_replacements={PROP: [_repl()]}, bogus_scope=["a.py"])
    assert code == 1 and "test_spec entry 'test_a'" in out and "bogus_scope" in out, f"another unknown key is still refused by name: {out}"
    # The JSON schema itself (read by other tools besides the hook's own Python check) still closes the
    # test_spec item: it admits the new field and refuses any other unknown key.
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((_REPO_ROOT / "config" / "ac_store_schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)

    def schema_errors(**extra_item_keys) -> list[str]:
        record = copy.deepcopy(_BASE_AC)
        record["test_spec"][0].update(extra_item_keys)
        return [e.message for e in validator.iter_errors(record)]

    assert schema_errors(declared_replacements={PROP: [_repl()]}) == [], "control: the schema admits a declaration"
    assert any("bogus_scope" in m for m in schema_errors(bogus_scope=["a.py"])), "the JSON schema no longer refuses an unknown test_spec key"
