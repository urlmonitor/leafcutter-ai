"""
MODULE: unit_tests/ac_store/test_bo_2500a_8_i_schema_permissive.py
GOAL: BO-2500a-8-i - the JSON store schema alone stays permissive for a reasonless test-free record;
    the refusal is made by the commit-time record check only.
BUSINESS CONTEXT: A conditional rule in config/ac_store_schema.json would also refuse the 99 stored
    records that lack a reason and turn the whole-store baseline red.
ARCHITECTURE: scripts/ac_store/validate_ac_schema.py (the schema-only path) runs as a subprocess on a
    record written with yaml.safe_dump.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from unit_tests.ac_store._acs_100i_fixtures import SCHEMA_VALIDATOR_CLI, base_ac_record, run_cli


def test_json_schema_alone_stays_permissive_for_a_reasonless_test_free_record(tmp_path: Path) -> None:
    # covers: BO-2500a-8-i
    # angle: criterion
    """validate_ac_schema.py exits 0 on a test_required false record with no test_rationale."""
    record = base_ac_record(id="ZZ-810b-1", readiness="draft", assigned_agent="documentation-expert",
                            test_required=False)
    assert "test_rationale" not in record
    path = tmp_path / "ZZ-810b-1.yaml"
    path.write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8")
    run = run_cli(SCHEMA_VALIDATOR_CLI, str(path))
    assert run.returncode == 0, run.output
