"""
MODULE: unit_tests/ac_store/_reachability_schema_helpers.py
GOAL: Real-schema helpers and the authored-angle fixture record used by
    test_derived_test_reachability_floor.py, relocated verbatim so that test
    file stays under its size ratchet. Not collected by pytest (no ``test_`` prefix).
"""

from __future__ import annotations

import json
from pathlib import Path

_SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "ac_store_schema.json"


def _load_schema() -> dict:
    """Read and parse the REAL on-disk config/ac_store_schema.json."""
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _test_spec_item_schema() -> dict:
    """Return the ``test_spec`` array-item subschema from the real schema file."""
    test_spec = _load_schema()["properties"]["test_spec"]
    array_branches = [
        branch for branch in test_spec["oneOf"] if branch.get("type") == "array"
    ]
    assert len(array_branches) == 1, (
        f"test_spec must keep exactly one array branch in its oneOf: {test_spec}"
    )
    return array_branches[0]["items"]


def _schema_errors(record: dict) -> list[str]:
    """Validate *record* against the real AC store schema; return error strings.

    Uses jsonschema.Draft7Validator against config/ac_store_schema.json — the
    identical mechanism and identical schema file used by BOTH the
    ``check-ac-schema`` pre-commit hook (via
    ``templates/scripts/commit_guardian/check_ac_schema.py``) and
    ``scripts/ac_store/validate_ac_schema.py``. Nested ``oneOf`` context errors
    are flattened in, because the top-level message for a failing array branch
    is only "is not valid under any of the given schemas" and hides the actual
    violation.

    Args:
        record: Parsed AC record.

    Returns:
        Human-readable violation strings; empty list when the record is valid.
    """
    import jsonschema  # noqa: PLC0415 — optional dep, imported at call time

    def _fmt(err) -> str:
        loc = ".".join(str(p) for p in err.absolute_path) or "<root>"
        return f"at {loc} — {err.message}"

    errors: list[str] = []
    for err in sorted(jsonschema.Draft7Validator(_load_schema()).iter_errors(record), key=str):
        errors.append(_fmt(err))
        errors.extend(_fmt(sub) for sub in err.context or [])
    return errors


# A constructed record that is nonetheless a FULL, schema-valid AC — the point
# of the schema assertion is lost if the fixture is a partial dict that
# only happens to satisfy the code path. 'build-pipeline' keeps it out of the
# schema's package-surface if/then branch, which would otherwise demand a
# structured it_requirements object.
_AUTHORED_ANGLE_AC: dict = {
    "id": "ZZ-900a-1",
    "title": "Fixture AC whose it-po authored a reachability-angle test_spec",
    "component": "build-pipeline",
    "components": ["build_pipeline"],
    "status": "active",
    "readiness": "approved",
    "priority": "medium",
    "level": "L2",
    "work_status": "todo",
    "assigned_agent": "python-coder",
    "criteria": "Given a thing\nWhen it happens\nThen the thing is recorded\n",
    "test_spec": [
        {
            "name": "test_zz_900a_1_reachable_from_entry_point",
            "description": "Invoke the CLI and assert the record lands.",
            "target_dir": "unit_tests/zz/",
            "angle": "reachability",
        }
    ],
}
