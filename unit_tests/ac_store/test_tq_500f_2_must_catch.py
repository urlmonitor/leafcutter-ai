"""
MODULE: unit_tests/ac_store/test_tq_500f_2_must_catch.py
COVERS: TQ-500f-2

SCOPE NOTE: TQ-500f-2's assigned_agent is python-coder; its Gherkin also
delivers a contract to TQ-500f-2-ii (llm-expert, prompt work) and
TQ-500f-3-i (a sibling AC). This file writes tests ONLY for the
python-coder-scoped behaviours named in the ticket authorization for this
run: must_catch accepted by the validator CLI, carried verbatim (order and
text) onto the generated ticket, the generated ticket's Test Requirements
(including must_catch) validating against config/test_requirements.schema.json,
and an entry with no must_catch getting no must_catch key at all. Nothing
here tests test-writer's own consumption of must_catch (TQ-500f-2-ii,
out of scope for this run).

GOAL (from the AC criteria): given a requirement whose test plan has entry 1
(three must_catch strings) and entry 2 (no must_catch), the validator
accepts the requirement, and the generated work's Test Requirements carry
entry 1's must_catch verbatim (same strings, same order, character for
character) while entry 2 carries no must_catch key at all.

RED BASELINE (2026-09-25, confirmed live at HEAD):
  - config/ac_store_schema.json's test_spec[] item schema has no `must_catch`
    property and additionalProperties: false -> the validator CLI test is red
    (rejects the whole record for the unknown key).
  - scripts/ac_store/_gtfa_tests_section.py's _spec_entry() never reads
    item.get("must_catch") -> the generated entry carries NO must_catch key
    at all today, confirmed by direct probe against the real generator's
    write path (generate_written) before this file was written.
  - config/test_requirements.schema.json's $defs.test_entry has no
    `must_catch` property either -> even once the generator is fixed to
    copy the key through, the entry would fail schema validation until
    that schema is also widened.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import jsonschema
import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_VALIDATOR_CLI = _REPO_ROOT / "scripts" / "ac_store" / "validate_ac_schema.py"
_TEST_REQ_SCHEMA_PATH = _REPO_ROOT / "config" / "test_requirements.schema.json"

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "ac_store"))

from _tkt_500f_support import generate_written, make_ac  # noqa: E402

_TESTS_BLOCK_RE = re.compile(
    r"##\s+Test\s+Requirements\b.*?```(?:yaml)?\s*(.*?)```",
    re.DOTALL | re.IGNORECASE,
)

#: The verbatim strings from the AC's own Given, chosen (per test_rationale)
#: so sorting ('drop' < 'new' < 'revert') or case-folding ('NULL') would
#: change them if the generator normalised anything.
_MUST_CATCH_STRINGS = [
    "revert the fix",
    "drop the second gate condition (retry_due)",
    "new column cvd_delta_30 left NULL",
]

_TWO_ENTRY_TEST_SPEC = [
    {
        "name": "test_retry_gate_runs_when_both_conditions_due",
        "target_dir": "unit_tests/ac_store/",
        "must_catch": list(_MUST_CATCH_STRINGS),
    },
    {
        "name": "test_retry_gate_idle_when_nothing_due",
        "target_dir": "unit_tests/ac_store/",
    },
]


def _parse_tests_from_ticket(ticket_text: str) -> list[dict]:
    match = _TESTS_BLOCK_RE.search(ticket_text)
    assert match is not None, (
        f"no fenced ## Test Requirements YAML block found:\n{ticket_text[:1000]}"
    )
    parsed = yaml.safe_load(match.group(1))
    assert isinstance(parsed, dict) and isinstance(parsed.get("tests"), list)
    return [e for e in parsed["tests"] if isinstance(e, dict)]


def _entry_schema() -> dict:
    schema = json.loads(_TEST_REQ_SCHEMA_PATH.read_text(encoding="utf-8"))
    return schema["$defs"]["test_entry"]


def _validate_entry_against_schema(entry: dict) -> list[str]:
    validator = jsonschema.Draft7Validator(_entry_schema())
    return [err.message for err in validator.iter_errors(entry)]


def _run_validator(ac_yaml_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_VALIDATOR_CLI), str(ac_yaml_path)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(_REPO_ROOT),
        timeout=30,
    )


def _base_ac_yaml(ac_id: str, test_spec_entries: list[dict]) -> dict:
    return {
        "id": ac_id,
        "title": "probe fixture for TQ-500f-2",
        "component": "testing-quality",
        "components": ["testing_quality"],
        "status": "active",
        "readiness": "approved",
        "priority": "high",
        "criteria": "Given x\nWhen y\nThen z\n",
        "test_spec": test_spec_entries,
    }


class TestValidatorCliAcceptsTestSpecWithMustCatch:
    """angle: reachability — production entry point: scripts/ac_store/
    validate_ac_schema.py CLI (the check-ac-schema commit gate)."""

    def test_validator_cli_accepts_test_spec_with_must_catch(self) -> None:
        # covers: TQ-500f-2
        # angle: reachability
        """WRONG VERSION THIS CATCHES: 'only the AC-side schema is widened'
        without the generated-work side — this test alone cannot see that
        half (test_generated_test_requirements_with_must_catch_conform_to_schema
        below does); what THIS test alone catches is a validator that never
        learns the new key at all, e.g. a fix applied only to
        config/test_requirements.schema.json (the ticket-facing schema) and
        never to config/ac_store_schema.json (the AC-facing one this CLI
        actually validates against)."""
        ac = _base_ac_yaml("ZZP-6", _TWO_ENTRY_TEST_SPEC)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "probe.yaml"
            path.write_text(yaml.dump(ac, allow_unicode=True), encoding="utf-8")
            result = _run_validator(path)

        assert result.returncode == 0, (
            "a test_spec with a well-formed must_catch list (and a sibling "
            "entry with none) must be accepted by the real validator CLI.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


class TestGeneratedTicketCopiesMustCatchVerbatimInOrder:
    """angle: criterion — the AC-literal happy path: exact strings, exact
    order, read back through yaml.safe_load from the real generator's
    output."""

    def test_generated_ticket_copies_must_catch_verbatim_in_order(self) -> None:
        # covers: TQ-500f-2
        # angle: criterion
        """WRONG VERSION THIS CATCHES: 'generator sorts or lower-cases the
        list' (AC's own INTENDED must_catch note) — the three strings were
        deliberately chosen ('drop' < 'new' < 'revert' alphabetically; 'NULL'
        would fold under case-normalisation) so any reordering or
        case-folding is caught by the exact list-equality assertion below,
        never a set or case-insensitive comparison."""
        ac = make_ac(assigned_agent="python-coder")
        ac["criteria"] = "Given x\nWhen y\nThen z\n"
        ac["test_spec"] = [dict(entry) for entry in _TWO_ENTRY_TEST_SPEC]

        gen = generate_written(ac, "ZZP-7")
        assert gen.exit_code == 0, f"generator CLI failed: {gen.warnings}"
        entries = _parse_tests_from_ticket(gen.text)

        target = next(
            (
                e
                for e in entries
                if e.get("name") == "test_retry_gate_runs_when_both_conditions_due"
            ),
            None,
        )
        assert target is not None, f"expected entry not found among: {entries}"
        assert target.get("must_catch") == _MUST_CATCH_STRINGS, (
            f"must_catch must be carried through verbatim (same strings, same "
            f"order): expected {_MUST_CATCH_STRINGS!r}, got "
            f"{target.get('must_catch')!r}"
        )


class TestEntryWithoutMustCatchGetsNoMustCatchKey:
    """angle: boundary — the presence/absence contrast in the SAME
    generation: entry 1 must carry must_catch, entry 2 must carry none at
    all (not an empty list)."""

    def test_entry_without_must_catch_gets_no_must_catch_key(self) -> None:
        # covers: TQ-500f-2
        # angle: boundary
        """WRONG VERSION THIS CATCHES: 'generator emits must_catch: [] on
        every entry' (AC's own INTENDED must_catch note) — the
        `"must_catch" not in target` assertion below fails against that
        wrong version (an empty list is still a present key), and is
        exercised in the SAME generation as the entry that must positively
        carry must_catch, so a generator that drops the field everywhere
        cannot pass this test by coincidence."""
        ac = make_ac(assigned_agent="python-coder")
        ac["criteria"] = "Given x\nWhen y\nThen z\n"
        ac["test_spec"] = [dict(entry) for entry in _TWO_ENTRY_TEST_SPEC]

        gen = generate_written(ac, "ZZP-8")
        assert gen.exit_code == 0, f"generator CLI failed: {gen.warnings}"
        entries = _parse_tests_from_ticket(gen.text)

        with_must_catch = next(
            (
                e
                for e in entries
                if e.get("name") == "test_retry_gate_runs_when_both_conditions_due"
            ),
            None,
        )
        without_must_catch = next(
            (
                e
                for e in entries
                if e.get("name") == "test_retry_gate_idle_when_nothing_due"
            ),
            None,
        )
        assert with_must_catch is not None and without_must_catch is not None

        # Positive half — forces this test red today (must_catch absent
        # entirely at HEAD), not vacuously true from the absence check alone.
        assert with_must_catch.get("must_catch") == _MUST_CATCH_STRINGS, (
            f"the entry that named must_catch must carry it: "
            f"{with_must_catch.get('must_catch')!r}"
        )
        # The actual boundary assertion this test exists for.
        assert "must_catch" not in without_must_catch, (
            "an entry whose requirement named no must_catch must carry NO "
            f"must_catch key at all (not even an empty list), got: "
            f"{without_must_catch!r}"
        )


class TestGeneratedTestRequirementsWithMustCatchConformToSchema:
    """angle: seam — real producer (generate_ticket_from_ac.py's write path)
    piped into the real consumer (config/test_requirements.schema.json)."""

    def test_generated_test_requirements_with_must_catch_conform_to_schema(self) -> None:
        # covers: TQ-500f-2
        # angle: seam
        """WRONG VERSION THIS CATCHES: 'only the AC-side schema is widened'
        (AC's own INTENDED must_catch note) — once the generator copies
        must_catch through, an entry carrying it fails jsonschema validation
        against config/test_requirements.schema.json's $defs.test_entry
        until that schema ALSO gains the must_catch property (both schemas
        reject unknown keys by design, per the AC's it_requirements)."""
        ac = make_ac(assigned_agent="python-coder")
        ac["criteria"] = "Given x\nWhen y\nThen z\n"
        ac["test_spec"] = [dict(entry) for entry in _TWO_ENTRY_TEST_SPEC]

        gen = generate_written(ac, "ZZP-9")
        assert gen.exit_code == 0, f"generator CLI failed: {gen.warnings}"
        entries = _parse_tests_from_ticket(gen.text)

        target = next(
            (
                e
                for e in entries
                if e.get("name") == "test_retry_gate_runs_when_both_conditions_due"
            ),
            None,
        )
        assert target is not None
        assert target.get("must_catch") == _MUST_CATCH_STRINGS, (
            "the entry validated below must actually carry must_catch, or "
            "this test would pass on schema conformance for the WRONG "
            f"reason (an entry that simply lacks the key): {target!r}"
        )

        errors = _validate_entry_against_schema(target)
        assert not errors, (
            "generated entry (including must_catch) must validate against "
            f"config/test_requirements.schema.json: {errors}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
