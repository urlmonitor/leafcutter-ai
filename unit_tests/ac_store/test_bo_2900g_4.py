"""
MODULE: unit_tests/ac_store/test_bo_2900g_4.py
COVERS: BO-2900g-4

GOAL: Every descriptor generate_ticket_from_ac.py emits into a ticket's
## Test Requirements block — on EITHER route (criteria-derived fallback or
authored test_spec) — must validate against the single reconciled definition
BO-2900g-3 establishes (config/test_requirements.schema.json's test_entry
shape: name/description/type/target_dir/covers, with surface_invoked required
on a reachability-kind entry).

CURRENT STATE (2026-08-18): the emitted shape uses 'file' (not 'target_dir'),
'covers' as a LIST (schema wants a string), 'angle' (not part of the
test_entry schema at all), and no 'description' key on derived entries — the
"6+ counts" of non-conformance the AC's notes describe, confirmed live at
HEAD. These tests are RED against that shape.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

# Same regex the production ticket guard uses to extract the fenced YAML block
# from ## Test Requirements — _build_test_requirements_section returns the
# FULL markdown section (heading + ```yaml fence), not raw YAML.
_TESTS_BLOCK_RE = re.compile(
    r"##\s+Test\s+Requirements\b.*?```(?:yaml)?\s*(.*?)```",
    re.DOTALL | re.IGNORECASE,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_TEST_REQ_SCHEMA_PATH = _REPO_ROOT / "config" / "test_requirements.schema.json"
_GEN_SCRIPT = _REPO_ROOT / "scripts" / "ac_store" / "generate_ticket_from_ac.py"

sys.path.insert(0, str(_REPO_ROOT / "scripts" / "ac_store"))

from generate_ticket_from_ac import (  # noqa: E402
    _build_test_requirements_section,
)


def _load_schema() -> dict:
    return json.loads(_TEST_REQ_SCHEMA_PATH.read_text(encoding="utf-8"))


def _entry_schema() -> dict:
    return _load_schema()["$defs"]["test_entry"]


def _validate_entry(entry: dict) -> list[str]:
    """Validate one descriptor against the single real on-disk definition."""
    import jsonschema  # noqa: PLC0415

    validator = jsonschema.Draft7Validator(_entry_schema())
    return [
        f"at {'.'.join(str(p) for p in err.absolute_path) or '<root>'} — {err.message}"
        for err in sorted(validator.iter_errors(entry), key=str)
    ]


def _parse_tests(section_markdown: str) -> list[dict]:
    match = _TESTS_BLOCK_RE.search(section_markdown)
    assert match is not None, (
        f"no fenced ## Test Requirements YAML block found:\n{section_markdown[:1000]}"
    )
    parsed = yaml.safe_load(match.group(1))
    assert isinstance(parsed, dict) and isinstance(parsed.get("tests"), list)
    return [e for e in parsed["tests"] if isinstance(e, dict)]


_DERIVED_AC = {
    "id": "ZZ-2900g-4-derived",
    "assigned_agent": "python-coder",
    "criteria": "Given a thing\nWhen it happens\nThen the thing is recorded\n",
}

_AUTHORED_AC = {
    "id": "ZZ-2900g-4-authored",
    "assigned_agent": "python-coder",
    "criteria": "Given a thing\nWhen it happens\nThen the thing is recorded\n",
    "test_spec": [
        {
            "name": "test_authored_entry",
            "target_dir": "unit_tests/zz/",
            "description": "authored description",
        }
    ],
}


class TestEveryEmittedDescriptorValidatesAgainstTheSingleDefinition:
    def test_bo_2900g_4_every_emitted_descriptor_validates_against_the_single_definition(
        self,
    ) -> None:
        # covers: BO-2900g-4
        """Each descriptor from the derived-fallback route must validate
        against the single real definition, including surface_invoked on the
        reachability descriptor."""
        section = _build_test_requirements_section(dict(_DERIVED_AC), _DERIVED_AC["id"])
        entries = _parse_tests(section)
        assert entries, "expected at least one descriptor"

        offenders = {e.get("name"): _validate_entry(e) for e in entries}
        offenders = {k: v for k, v in offenders.items() if v}
        assert not offenders, (
            f"emitted descriptors do not conform to the single definition: {offenders}"
        )


class TestDerivedAndAuthoredPlansValidateIdentically:
    def test_bo_2900g_4_derived_and_authored_plans_validate_identically(self) -> None:
        # covers: BO-2900g-4
        """Pipe the real criteria-derived route's output and the real
        authored-test_spec route's output through the SAME real validator and
        assert both pass — a reader cannot tell from the vocabulary alone
        which route produced which."""
        derived_entries = _parse_tests(
            _build_test_requirements_section(dict(_DERIVED_AC), _DERIVED_AC["id"])
        )
        authored_entries = _parse_tests(
            _build_test_requirements_section(dict(_AUTHORED_AC), _AUTHORED_AC["id"])
        )

        derived_errors = {e["name"]: _validate_entry(e) for e in derived_entries}
        authored_errors = {e["name"]: _validate_entry(e) for e in authored_entries}

        derived_offenders = {k: v for k, v in derived_errors.items() if v}
        authored_offenders = {k: v for k, v in authored_errors.items() if v}

        assert not derived_offenders, derived_offenders
        assert not authored_offenders, authored_offenders


class TestEmittedPlanConformsWhenReadFromTheRealDefinitionFile:
    def test_bo_2900g_4_emitted_plan_conforms_when_read_from_the_real_definition_file(
        self,
    ) -> None:
        # covers: BO-2900g-4
        """Validate against the definition loaded from its real on-disk file
        with json.load, never against an enum restated in the test."""
        schema = _load_schema()
        assert "test_entry" in schema.get("$defs", {}), (
            f"real schema file must define test_entry: {_TEST_REQ_SCHEMA_PATH}"
        )
        section = _build_test_requirements_section(dict(_DERIVED_AC), _DERIVED_AC["id"])
        entries = _parse_tests(section)
        offenders = {e.get("name"): _validate_entry(e) for e in entries}
        offenders = {k: v for k, v in offenders.items() if v}
        assert not offenders, offenders


class TestGeneratedTicketConformsViaTheGeneratorCli:
    def test_bo_2900g_4_generated_ticket_conforms_via_the_generator_cli(self) -> None:
        # covers: BO-2900g-4
        """PRODUCTION ENTRY POINT: run generate_ticket_from_ac.py for one AC on
        each route, parse the ## Test Requirements YAML out of the ticket
        files the CLI actually wrote, and validate both against the real
        definition file."""
        for ac in (_DERIVED_AC, _AUTHORED_AC):
            ac_id = str(ac["id"])
            with tempfile.TemporaryDirectory() as tmpdir:
                ac_root = Path(tmpdir) / "docs" / "acceptance-criteria"
                component_dir = ac_root / "fixture-component"
                component_dir.mkdir(parents=True)
                record = dict(ac)
                record["title"] = "Fixture"
                record["component"] = "build-pipeline"
                record["components"] = ["build_pipeline"]
                record["status"] = "active"
                record["readiness"] = "approved"
                record["priority"] = "medium"
                record["level"] = "L2"
                record["work_status"] = "todo"
                (component_dir / f"{ac_id}.yaml").write_text(
                    yaml.safe_dump(record, sort_keys=False, allow_unicode=True),
                    encoding="utf-8",
                )
                tickets_root = Path(tmpdir) / "tickets"
                tickets_root.mkdir(parents=True)

                proc = subprocess.run(
                    [
                        sys.executable,
                        str(_GEN_SCRIPT),
                        "--ac",
                        ac_id,
                        "--ac-root",
                        str(ac_root),
                        "--tickets-root",
                        str(tickets_root),
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                    cwd=str(_REPO_ROOT),
                )
                assert proc.returncode == 0, (
                    f"generator CLI failed for {ac_id} (exit {proc.returncode})\n"
                    f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
                )
                written = list(tickets_root.rglob("*.md"))
                assert written, f"generator CLI wrote no ticket for {ac_id}"
                ticket_text = written[0].read_text(encoding="utf-8")

            # _parse_tests already searches for the '## Test Requirements'
            # heading + fenced block and extracts the inner YAML itself (see
            # its use at lines 108/129-130/154 above, where it is always
            # handed the FULL section/ticket text, never an already-unwrapped
            # inner YAML string). Re-extracting the fence here before calling
            # it double-extracts: the second search runs against YAML that no
            # longer contains a '## Test Requirements' heading or a fence, so
            # it always fails regardless of what the generator produced. Pass
            # the whole ticket text through once, exactly like the other
            # tests in this module.
            entries = _parse_tests(ticket_text)
            offenders = {e.get("name"): _validate_entry(e) for e in entries}
            offenders = {k: v for k, v in offenders.items() if v}
            assert not offenders, f"{ac_id}: {offenders}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
