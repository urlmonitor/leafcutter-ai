"""
MODULE: test_declares_side_effect_schema_reachability
GOAL: Prove the BP-1100f-5 side-effect gate is REACHABLE from the canonical
      /plan-feature -> /build-ac path — i.e. an AC record that carries
      `declares_side_effect: true` both (a) passes AC-store schema validation
      and (b) actually causes the real generator CLI to route
      `user-surface-smoker` into the generated ticket's agents map.

COVERS: BP-1100f-5, BP-1100f-5-i

BACKGROUND (the bug this file guards against)
---------------------------------------------
`scripts/ac_store/generate_ticket_from_ac.py` reads `ac.get("declares_side_effect")`
and uses it to route the `user-surface-smoker` phase agent. That gate was fully
implemented and unit-tested (see `test_bp_1100f_5.py`) — but
`config/ac_store_schema.json` never declared the property, and its root carries
`additionalProperties: false`. So any AC actually carrying the field was REJECTED
at validation time:

    schema violation at <root> — Additional properties are not allowed
    ('declares_side_effect' was unexpected)

Net effect: the gate fired on zero real work. `test_bp_1100f_5.py` could not catch
this because it exercises the router with in-memory fixture dicts that are never
validated against the store schema — the two halves were each green in isolation
while the pipeline between them was severed.

The tests below deliberately run BOTH halves against ONE shared fixture record, so
the pair can only pass if a schema-valid AC also routes. Re-severing either half
turns this file red.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Path setup: unit_tests/ac_store/ is 3 levels below the repo root
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCHEMA_PATH = _REPO_ROOT / "config" / "ac_store_schema.json"
_GENERATOR = _REPO_ROOT / "scripts" / "ac_store" / "generate_ticket_from_ac.py"
_VALIDATOR_DIR = _REPO_ROOT / "scripts" / "ac_store"

_FIXTURE_AC_ID = "BP-9999f-9"

# ONE shared record used by BOTH halves of this file: the schema-validation test
# and the real-generator routing test. Using a single fixture is the point — it
# is what makes "schema-valid" and "actually routes" a single provable claim
# rather than two independently-green facts about different objects.
_SIDE_EFFECT_AC: dict = {
    "id": _FIXTURE_AC_ID,
    "title": "Fixture AC declaring a durable observable side-effect",
    # NOTE: kebab 'component' is the AC-store namespace key (index.yaml), a
    # SEPARATE axis from the 'components' graph-id list. 'build-pipeline' also
    # keeps the fixture out of the schema's package-surface if/then branch,
    # which would otherwise demand a structured it_requirements object.
    "component": "build-pipeline",
    "components": ["build_pipeline"],
    "status": "active",
    "readiness": "approved",
    "priority": "high",
    "level": "L2",
    "work_status": "todo",
    "assigned_agent": "python-coder",
    "estimated_complexity": "S",
    "change_target": "pipeline",
    "risk_surface": "contract_boundary",
    "test_required": False,
    "declares_side_effect": True,
    "criteria": (
        "Given an AC declares a durable, observable side-effect,\n"
        "When a ticket is generated from that AC,\n"
        "Then user-surface-smoker is routed as a needed phase agent."
    ),
}


def _load_schema() -> dict:
    """Read and parse config/ac_store_schema.json."""
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _schema_errors(record: dict) -> list[str]:
    """Validate *record* against the AC store schema; return error strings.

    Uses jsonschema.Draft7Validator against config/ac_store_schema.json — the
    identical mechanism and the identical schema file used by BOTH
    `templates/scripts/commit_guardian/check_ac_schema.py` (the check-ac-schema
    pre-commit hook, via `_ac_schema_validators.validate_with_jsonschema`) and
    `scripts/ac_store/validate_ac_schema.py`.

    Args:
        record: Parsed AC record.

    Returns:
        Human-readable violation strings; empty list when the record is valid.
    """
    import jsonschema  # noqa: PLC0415 — optional dep, imported at call time

    validator = jsonschema.Draft7Validator(_load_schema())
    return [
        f"at {'.'.join(str(p) for p in err.absolute_path) or '<root>'} — {err.message}"
        for err in sorted(validator.iter_errors(record), key=str)
    ]


def _parse_frontmatter(stdout: str) -> dict:
    """Extract and parse the leading YAML frontmatter block from generator output.

    The generator prints ``---\\n<yaml>\\n---`` followed by the ticket body. The
    body itself can contain ``---`` lines, so this scans for the FIRST two
    fence lines rather than naively splitting on the delimiter.

    Args:
        stdout: Full captured stdout of the generator CLI.

    Returns:
        Parsed frontmatter mapping, or an empty dict when no block is found.
    """
    lines = stdout.splitlines()
    fences = [i for i, line in enumerate(lines) if line.strip() == "---"]
    if len(fences) < 2:
        return {}
    block = "\n".join(lines[fences[0] + 1:fences[1]])
    parsed = yaml.safe_load(block)
    return parsed if isinstance(parsed, dict) else {}


def _generate_ticket_frontmatter(record: dict) -> dict:
    """Write *record* to a temp AC store, run the REAL generator CLI, parse output.

    Invokes ``scripts/ac_store/generate_ticket_from_ac.py --dry-run`` in a FRESH
    subprocess — the actual command the /build-ac path runs — rather than calling
    an internal helper such as ``_build_agents_map`` directly. That matters: the
    bug this file guards against lived in the gap BETWEEN the store record and the
    router, so a test that hands a dict straight to the router cannot see it.

    The record is serialised with ``yaml.safe_dump`` so the generator parses the
    real on-disk data format, not a hand-indented literal.

    Args:
        record: AC record to write into the temporary store.

    Returns:
        The generated ticket's parsed frontmatter mapping.

    Raises:
        AssertionError: if the generator exits non-zero.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        ac_root = Path(tmpdir) / "docs" / "acceptance-criteria"
        component_dir = ac_root / "fixture-component"
        component_dir.mkdir(parents=True)
        (component_dir / f"{record['id']}.yaml").write_text(
            yaml.safe_dump(record, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

        proc = subprocess.run(
            [
                sys.executable,
                str(_GENERATOR),
                "--ac", str(record["id"]),
                "--ac-root", str(ac_root),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

    assert proc.returncode == 0, (
        f"generate_ticket_from_ac.py --dry-run exited {proc.returncode}.\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    return _parse_frontmatter(proc.stdout)


class TestDeclaresSideEffectIsSchemaValid(unittest.TestCase):
    """Half (a): the field must survive AC-store schema validation."""

    def test_side_effect_ac_validates_against_store_schema(self) -> None:
        # covers: BP-1100f-5
        """An AC carrying declares_side_effect: true must be schema-VALID.

        RED before the fix with exactly:
            at <root> — Additional properties are not allowed
            ('declares_side_effect' was unexpected)
        because the root object declares additionalProperties: false and the
        property was undeclared.
        """
        errors = _schema_errors(_SIDE_EFFECT_AC)

        self.assertEqual(
            errors,
            [],
            "An AC carrying declares_side_effect: true must validate against "
            "config/ac_store_schema.json. While the property is undeclared and "
            "the root sets additionalProperties: false, every such AC is rejected "
            "at authoring time, so the BP-1100f-5 user-surface-smoker gate can "
            f"never fire on real work. Violations: {errors!r}",
        )

    def test_schema_declares_the_property_explicitly(self) -> None:
        # covers: BP-1100f-5
        """The property must be DECLARED, not merely tolerated.

        Guards the test above against a vacuous pass: flipping the root to
        additionalProperties: true would make any unknown key validate, silently
        restoring the discoverability gap (nothing would tell an it-po or
        business-analyst that the field exists or what it does).
        """
        schema = _load_schema()

        self.assertIs(
            schema.get("additionalProperties"),
            False,
            "The AC store schema root must keep additionalProperties: false; "
            "loosening it would make the reachability test above vacuous.",
        )

        prop = schema.get("properties", {}).get("declares_side_effect")
        self.assertIsNotNone(
            prop,
            "config/ac_store_schema.json must declare a 'declares_side_effect' "
            "property so AC authors can discover the field. It is currently "
            "absent, which is the root cause of the unreachable BP-1100f-5 gate.",
        )

        description = prop.get("description", "")
        self.assertIn(
            "user-surface-smoker",
            description,
            "The declares_side_effect description must name user-surface-smoker "
            "so an author can see what setting the field actually does. "
            f"Current description: {description!r}",
        )

    def test_property_accepts_boolean_and_null_and_rejects_other_types(self) -> None:
        # covers: BP-1100f-5
        """declares_side_effect must accept true / false / null, and nothing else."""
        for value in (True, False, None):
            with self.subTest(value=value):
                record = copy.deepcopy(_SIDE_EFFECT_AC)
                record["declares_side_effect"] = value
                self.assertEqual(
                    _schema_errors(record),
                    [],
                    f"declares_side_effect: {value!r} must be schema-valid.",
                )

        record = copy.deepcopy(_SIDE_EFFECT_AC)
        record["declares_side_effect"] = "yes"
        self.assertNotEqual(
            _schema_errors(record),
            [],
            "A non-boolean declares_side_effect (e.g. the string 'yes') must be "
            "rejected — a truthy string would otherwise route the smoker while "
            "reading as a typo to a human reviewer.",
        )


class TestDeclaresSideEffectRoutesSmokerViaRealGenerator(unittest.TestCase):
    """Half (b): a schema-valid record must actually route user-surface-smoker.

    This is the half that proves REACHABILITY. It runs the real generator CLI in
    a fresh subprocess on the SAME fixture the schema test validates.
    """

    def test_real_generator_routes_user_surface_smoker(self) -> None:
        # covers: BP-1100f-5
        """generate_ticket_from_ac.py must emit user-surface-smoker: needed."""
        frontmatter = _generate_ticket_frontmatter(_SIDE_EFFECT_AC)

        self.assertTrue(
            frontmatter.get("declares_side_effect"),
            "The generated ticket frontmatter must carry declares_side_effect: true "
            f"when the source AC declares it. Frontmatter: {frontmatter!r}",
        )

        agents = frontmatter.get("agents") or {}
        self.assertEqual(
            agents.get("user-surface-smoker"),
            "needed",
            "Running the REAL generator CLI on a schema-valid AC that declares a "
            "durable side-effect must route user-surface-smoker as 'needed'. This "
            "is the whole point of BP-1100f-5: the only automatic guard against "
            "'the code was built but is not wired into anything'. "
            f"Agents map: {agents!r}",
        )

    def test_ac_without_the_field_is_not_force_routed(self) -> None:
        # covers: BP-1100f-5-i
        """Negative control — proves the routing above is caused by the field.

        Without this, the assertion above could pass on a generator that routes
        user-surface-smoker unconditionally, which would prove nothing about the
        field being read.
        """
        record = copy.deepcopy(_SIDE_EFFECT_AC)
        del record["declares_side_effect"]

        self.assertEqual(
            _schema_errors(record),
            [],
            "The control fixture must itself be schema-valid; otherwise this "
            "test proves nothing about routing.",
        )

        frontmatter = _generate_ticket_frontmatter(record)
        agents = frontmatter.get("agents") or {}

        self.assertNotEqual(
            agents.get("user-surface-smoker"),
            "needed",
            "An AC that declares NO durable side-effect must not be force-routed "
            "to user-surface-smoker (BP-1100f-5-i). If this fails, the positive "
            "test above is vacuous — the smoker is being wired unconditionally "
            f"rather than from declares_side_effect. Agents map: {agents!r}",
        )


class TestStandaloneValidatorAcceptsTheField(unittest.TestCase):
    """The CLI validator agents actually run must accept the field too.

    scripts/ac_store/validate_ac_schema.py is what a human or agent runs over the
    store (and what CLAUDE.md's bulk pre-flight recipe invokes). It loads the same
    schema file, so this closes the loop from the authoring surface, not just from
    a direct jsonschema call.
    """

    def test_validate_ac_schema_accepts_declares_side_effect(self) -> None:
        # covers: BP-1100f-5
        """_validate_file() must report no errors for the side-effect fixture."""
        if str(_VALIDATOR_DIR) not in sys.path:
            sys.path.insert(0, str(_VALIDATOR_DIR))
        import validate_ac_schema  # noqa: PLC0415

        schema, warning = validate_ac_schema.load_ac_store_schema()
        self.assertIsNone(
            warning,
            f"The AC store schema must be loadable for this test to mean anything: {warning}",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / f"{_FIXTURE_AC_ID}.yaml"
            path.write_text(
                yaml.safe_dump(_SIDE_EFFECT_AC, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
            errors = validate_ac_schema._validate_file(path, None, schema)

        self.assertEqual(
            errors,
            [],
            "scripts/ac_store/validate_ac_schema.py must accept an AC carrying "
            f"declares_side_effect: true. Errors: {errors!r}",
        )


if __name__ == "__main__":
    unittest.main()
