"""
MODULE: test_tq_500g_1_ix_in_scope_files
GOAL: TQ-500g-1-ix, the new optional test_spec item field ``in_scope_files``: the AC
    validator accepts a non-empty list of path strings, refuses an empty list, a
    blank item and a non-string item, and still refuses every other unknown key.
BUSINESS CONTEXT: The AC is written with yaml.safe_dump and checked by the real
    validator CLI (scripts/ac_store/validate_ac_schema.py, run as a subprocess).
"""

from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_VALIDATOR = _REPO_ROOT / "scripts" / "ac_store" / "validate_ac_schema.py"

_BASE_AC = {
    "id": "BP-9999f-9", "title": "Fixture AC for the in_scope_files field", "component": "build-pipeline",
    "components": ["build_pipeline"], "status": "active", "readiness": "approved", "priority": "high",
    "level": "L2", "work_status": "todo", "assigned_agent": "python-coder", "estimated_complexity": "S",
    "change_target": "pipeline", "risk_surface": "contract_boundary", "test_required": True,
    "criteria": "Given a fixture,\nWhen it is validated,\nThen the verdict is read.",
    "test_spec": [{"name": "test_a", "target_dir": "unit_tests/x/", "framework": "pytest", "type": "unit",
                   "angle": "criterion", "description": "fixture entry", "must_catch": ["a wrong version"]}],
}


def _validate(tmp_path: Path, label: str, **extra_item_keys) -> int:
    """Write the fixture AC (yaml.safe_dump) with *extra_item_keys* on its test_spec entry; return the exit code."""
    record: dict = copy.deepcopy(_BASE_AC)
    record["test_spec"][0].update(extra_item_keys)
    path = tmp_path / f"{label}.yaml"
    path.write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8")
    proc = subprocess.run([sys.executable, str(_VALIDATOR), str(path)], capture_output=True, text=True,
                          timeout=120, check=False)
    return proc.returncode


def test_test_spec_in_scope_files_field_accepted_and_unknown_keys_still_refused(tmp_path):
    # covers: TQ-500g-1-ix
    # angle: boundary
    # Catches: additionalProperties dropped from the test_spec item to admit the new field
    assert _validate(tmp_path, "control_plain") == 0, "control: the fixture AC without the field is valid"
    assert _validate(tmp_path, "unknown_key", bogus_scope=["a.py"]) == 1, "control: an unknown key is refused"
    assert _validate(tmp_path, "accepted", in_scope_files=["refresh_config.py", "settings.py"]) == 0, (
        "a non-empty list of strings is accepted")
    assert _validate(tmp_path, "empty_list", in_scope_files=[]) == 1, "an empty list is refused"
    assert _validate(tmp_path, "blank_item", in_scope_files=["a.py", "  "]) == 1, "a blank item is refused"
    assert _validate(tmp_path, "non_string", in_scope_files=["a.py", 5]) == 1, "a non-string item is refused"
    assert _validate(tmp_path, "accepted_and_unknown", in_scope_files=["a.py"], bogus_scope=["a.py"]) == 1, (
        "the new field does not open the item to other unknown keys")
