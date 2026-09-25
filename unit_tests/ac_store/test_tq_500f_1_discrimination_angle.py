"""
MODULE: unit_tests/ac_store/test_tq_500f_1_discrimination_angle.py
COVERS: TQ-500f-1

GOAL (from the AC criteria): "discrimination" becomes an eighth permitted
test-angle kind — accepted by the validator CLI that gates commits, copied
verbatim onto a generated ticket's Test Requirements where it must conform to
config/test_requirements.schema.json, and accepted without warning by both
the ticket generator and done_proof's permitted-angle reader.

RED BASELINE (2026-09-25, confirmed live at HEAD):
  - config/ac_store_schema.json test_spec[].angle enum has 7 members, no
    "discrimination" -> Test 1's accept-half and Test 3 are red.
  - config/test_requirements.schema.json $defs.test_entry.properties.angle
    enum also has 7 members -> Test 3 is doubly red (entry carries the value
    but fails schema validation).
  - scripts/ac_store/_gtfa_constants.py's _TEST_ANGLES mirror also has 7
    members -> Test 4a (generator warning) is red.
  - done_proof._load_permitted_angle_kinds() reads the same 7-member R schema
    -> Test 4b (done_proof unrecognised-tag reader) is red.
All four confirmed by direct subprocess/function probes against real files
before this test file was written (not asserted from memory).

Every test drives the REAL production surface: the validator CLI as a
subprocess (the actual check-ac-schema commit gate), the real generator's
write path via generate_ticket_from_ac.main(), and done_proof's real tag
scanner — never a hand-typed literal standing in for any of them.
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

# Same fenced-block regex test_bo_2900g_4.py uses to extract the '## Test
# Requirements' YAML from a full ticket's text.
_TESTS_BLOCK_RE = re.compile(
    r"##\s+Test\s+Requirements\b.*?```(?:yaml)?\s*(.*?)```",
    re.DOTALL | re.IGNORECASE,
)


def _parse_tests_from_ticket(ticket_text: str) -> list[dict]:
    match = _TESTS_BLOCK_RE.search(ticket_text)
    assert match is not None, (
        f"no fenced ## Test Requirements YAML block found:\n{ticket_text[:1000]}"
    )
    parsed = yaml.safe_load(match.group(1))
    assert isinstance(parsed, dict) and isinstance(parsed.get("tests"), list)
    return [e for e in parsed["tests"] if isinstance(e, dict)]

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "ac_store"))

from _tkt_500f_support import (  # noqa: E402
    generate_written,
    make_ac,
)

import done_proof  # noqa: E402


def _base_ac_yaml(ac_id: str, test_spec_entries: list[dict]) -> dict:
    """A minimal but fully schema-conformant AC record (all required fields).

    Component/registry ids are real ('testing_quality' — confirmed present in
    docs/components.json). The id matches the real store's id pattern.
    """
    return {
        "id": ac_id,
        "title": "probe fixture for TQ-500f-1",
        "component": "testing-quality",
        "components": ["testing_quality"],
        "status": "active",
        "readiness": "approved",
        "priority": "high",
        "criteria": "Given x\nWhen y\nThen z\n",
        "test_spec": test_spec_entries,
    }


def _run_validator(ac_yaml_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_VALIDATOR_CLI), str(ac_yaml_path)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(_REPO_ROOT),
        timeout=30,
    )


def _entry_schema() -> dict:
    schema = json.loads(_TEST_REQ_SCHEMA_PATH.read_text(encoding="utf-8"))
    return schema["$defs"]["test_entry"]


def _validate_entry_against_schema(entry: dict) -> list[str]:
    validator = jsonschema.Draft7Validator(_entry_schema())
    return [err.message for err in validator.iter_errors(entry)]


class TestValidatorCliAcceptsDiscriminationAndRejectsMisspelling:
    """angle: reachability — production entry point: scripts/ac_store/
    validate_ac_schema.py CLI (the check-ac-schema commit gate)."""

    def test_validator_cli_accepts_discrimination_and_rejects_misspelled_angle(
        self,
    ) -> None:
        # covers: TQ-500f-1
        # angle: reachability
        """WRONG VERSION THIS CATCHES: 'validator accepts any string for
        angle' (named in the AC's own INTENDED must_catch notes) — that wrong
        version would make the second (misspelled) file exit 0, which the
        non-zero assertion below catches. It also catches a validator that
        widens the schema but never improves its error reporting: the
        message must name the specific entry and field, not just say
        'invalid under any of the given schemas'."""
        accept_ac = _base_ac_yaml(
            "ZZP-1",
            [
                {
                    "name": "test_retry_gate_runs_when_both_conditions_due",
                    "target_dir": "unit_tests/ac_store/",
                    "angle": "discrimination",
                }
            ],
        )
        reject_ac = _base_ac_yaml(
            "ZZP-2",
            [
                {
                    "name": "test_retry_gate_runs_when_both_misspelled",
                    "target_dir": "unit_tests/ac_store/",
                    "angle": "discriminating",
                }
            ],
        )

        with tempfile.TemporaryDirectory() as tmp:
            accept_path = Path(tmp) / "accept.yaml"
            reject_path = Path(tmp) / "reject.yaml"
            accept_path.write_text(yaml.dump(accept_ac, allow_unicode=True), encoding="utf-8")
            reject_path.write_text(yaml.dump(reject_ac, allow_unicode=True), encoding="utf-8")

            accept_result = _run_validator(accept_path)
            reject_result = _run_validator(reject_path)

        assert accept_result.returncode == 0, (
            f"angle: discrimination must be accepted by the real validator CLI.\n"
            f"stdout:\n{accept_result.stdout}\nstderr:\n{accept_result.stderr}"
        )

        assert reject_result.returncode != 0, (
            "angle: discriminating (misspelling) must be rejected by the real "
            f"validator CLI.\nstdout:\n{reject_result.stdout}"
        )
        stderr = reject_result.stderr
        assert "test_retry_gate_runs_when_both_misspelled" in stderr, (
            f"rejection message must name the offending test_spec entry:\n{stderr}"
        )
        assert "angle" in stderr, f"rejection message must name the field 'angle':\n{stderr}"
        assert "discrimination" in stderr, (
            f"rejection message must list the permitted values, including "
            f"'discrimination':\n{stderr}"
        )


class TestGeneratedTicketCarriesDiscriminationAngleAndConforms:
    """angle: seam — real producer (generate_ticket_from_ac.py's write path)
    piped into the real consumer (config/test_requirements.schema.json)."""

    def test_generated_ticket_carries_discrimination_angle_and_conforms(self) -> None:
        # covers: TQ-500f-1
        # angle: seam
        """WRONG VERSION THIS CATCHES: 'add discrimination to
        ac_store_schema.json only' (AC's own INTENDED must_catch note) — the
        generator would then emit angle: discrimination onto the ticket (it
        already copies unrecognised values through, confirmed live), but
        that entry would fail jsonschema validation against
        config/test_requirements.schema.json's still-7-member enum. Both
        assertions below must hold for the fix to be real."""
        ac = make_ac(assigned_agent="python-coder")
        ac["criteria"] = "Given x\nWhen y\nThen z\n"
        ac["test_spec"] = [
            {
                "name": "test_probe_discrimination_seam",
                "target_dir": "unit_tests/ac_store/",
                "angle": "discrimination",
                "description": "probe seam entry",
            }
        ]

        gen = generate_written(ac, "ZZP-3")
        assert gen.exit_code == 0, f"generator CLI failed: {gen.warnings}"
        assert gen.has_test_requirements_heading(), "generated ticket has no ## Test Requirements section"

        entries = _parse_tests_from_ticket(gen.text)
        target = next(
            (e for e in entries if e.get("name") == "test_probe_discrimination_seam"),
            None,
        )
        assert target is not None, f"expected entry not found among: {entries}"
        assert target.get("angle") == "discrimination", (
            f"angle must be carried through verbatim, got: {target.get('angle')!r}"
        )

        errors = _validate_entry_against_schema(target)
        assert not errors, (
            "generated entry (including angle: discrimination) must validate "
            f"against config/test_requirements.schema.json: {errors}"
        )


class TestGeneratorAndDoneProofAcceptDiscriminationWithoutWarning:
    """angle: real_artifact — reads the generator's real warning stream and
    done_proof's real on-disk-schema-backed tag reader; no fixture copy of
    either."""

    def test_generator_and_done_proof_accept_discrimination_without_warning(
        self,
    ) -> None:
        # covers: TQ-500f-1
        # angle: real_artifact
        """WRONG VERSION THIS CATCHES: 'add to both schemas but not the
        generator's angle mirror' (AC's own INTENDED must_catch note) — if
        scripts/ac_store/_gtfa_constants.py's _TEST_ANGLES frozenset is not
        also updated, the generator keeps emitting an 'unrecognised test
        angle' WARNING for discrimination even though both JSON schemas now
        accept it; the warnings assertion below catches that half-applied
        fix. The done_proof half independently re-reads the real R schema
        (config/ac_store_schema.json) fresh, so it catches the schema itself
        not being widened."""
        ac = make_ac(assigned_agent="python-coder")
        ac["criteria"] = "Given x\nWhen y\nThen z\n"
        ac["test_spec"] = [
            {
                "name": "test_probe_discrimination_no_warning",
                "target_dir": "unit_tests/ac_store/",
                "angle": "discrimination",
                "description": "probe no-warning entry",
            }
        ]
        gen = generate_written(ac, "ZZP-4")
        assert "unrecognised test angle" not in gen.warnings, (
            f"generator must not warn on angle: discrimination once its own "
            f"mirror is updated. warnings:\n{gen.warnings}"
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            probe_file = root / "test_probe_done_proof.py"
            probe_file.write_text(
                "def test_probe():\n"
                "    # covers: ZZP-4\n"
                "    # angle: discrimination\n"
                "    assert True\n",
                encoding="utf-8",
            )
            records = done_proof.collect_test_tag_records(root)
            unrecognised = done_proof.find_unrecognised_angle_tags(records)

        assert unrecognised == [], (
            "done_proof's permitted-angle reader must not report 'discrimination' "
            f"as unrecognised once config/ac_store_schema.json is widened: "
            f"{unrecognised}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
