"""
MODULE: unit_tests/ac_store/test_bo_2900g_3.py
COVERS: BO-2900g-3

GOAL: Reconcile the two disagreeing definitions of a required-proof
description:
  - config/test_requirements.schema.json: type enum
    unit/integration/manual/live_dispatch, surface_invoked required only for
    live_dispatch.
  - config/ac_store_schema.json: test_spec[].type enum
    unit/integration/e2e/behavioral, with a SEPARATE test_spec[].angle enum
    (7 values including 'reachability') and no surface_invoked property.

After reconciliation exactly one permitted-kind set must be resolvable from a
single file, the retired name 'live_dispatch' must be gone (no synonym), and
'surface_invoked' must be carried under that one name and be required for a
reachability-kind description.

CURRENT STATE (2026-08-18, updated after the coder's fix): the over-merge
defect (test_spec[].type on the AC-store side replaced with the seven angle
values) has been reverted — ac_store_schema.json's test_spec[].type is back to
the four test-LEVEL values (unit/integration/e2e/behavioral) and its
test_spec[].angle keeps the seven kind-of-proof values. In lockstep,
test_requirements.schema.json's test_entry now carries the SAME split: 'type'
holds the four test-LEVEL values (mirroring the store's test_spec[].type,
copied through verbatim by generate_ticket_from_ac.py) and 'angle' is the SOLE
statement of the seven kind-of-proof values, shared with the store's
test_spec[].angle. Both real files agree there is exactly one permitted-kind
set — carried on 'angle' in both — and the level axis is intact and
unmirrored across the fix. These tests assert against 'angle' accordingly and
are green against the present state; see the 2026-08-18 follow-up note below
for why four of the five assertions in this file were re-pointed from 'type'
to 'angle'.

FOLLOW-UP NOTE (2026-08-18, post-fix): the first automated pass at these tests
bound "the reconciled kind-of-proof enum" to
test_req["$defs"]["test_entry"]["properties"]["type"]["enum"] in four
assertions (TestSinglePermittedKindSetResolvesFromTheRealConfigFiles,
TestRetiredKindIsAbsentAndNotAcceptedAsASynonym,
TestGeneratorTestAnglesEqualsTheSchemaEnum, and the trailing check inside
TestDeployedAcSchemaGateRejectsARetiredKind). That was the SAME mis-binding as
the production defect this AC fixes, encoded into the test suite: once
test_requirements.schema.json's reconciliation landed with the kinds on
'angle' (not 'type'), those four assertions were reading the LEVEL axis and
calling it the kind-of-proof axis. Three of the four happened to still pass
(the level axis on both real files is now identical to itself, and
'live_dispatch' was never a level value, so both checks were trivially true
regardless of whether the kind-of-proof reconciliation held); one (the
_TEST_ANGLES comparison) correctly failed, because a 7-value set is never
equal to a 4-value set. All four are re-pointed at 'angle' below, and a new
assertion (TestTestReqTypeIsNotAShadowOfAngle) guards the same identity
condition on this side that TestTestLevelAxisIsUnchangedByTheReconciliation
already guards on the AC-store side: 'type' and 'angle' must never share an
enum, so a second over-merge of THIS file cannot happen invisibly again.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import jsonschema
import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_AC_SCHEMA_PATH = _REPO_ROOT / "config" / "ac_store_schema.json"
_TEST_REQ_SCHEMA_PATH = _REPO_ROOT / "config" / "test_requirements.schema.json"
HOOK_SCRIPT = (
    _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_ac_schema.py"
)


def _load(path: Path) -> dict:
    """Load a real on-disk JSON schema file with json.load (no fixture copy)."""
    return json.loads(path.read_text(encoding="utf-8"))


def _ac_test_spec_item_schema() -> dict:
    test_spec = _load(_AC_SCHEMA_PATH)["properties"]["test_spec"]
    array_branches = [b for b in test_spec["oneOf"] if b.get("type") == "array"]
    assert len(array_branches) == 1
    return array_branches[0]["items"]


class TestSinglePermittedKindSetResolvesFromTheRealConfigFiles:
    def test_bo_2900g_3_single_permitted_kind_set_resolves_from_the_real_config_files(
        self,
    ) -> None:
        # covers: BO-2900g-3
        """Both real config files, loaded fresh from disk, must resolve to one
        identical permitted-kind set.

        The kind-of-proof vocabulary is carried on 'angle' in BOTH real
        files post-reconciliation — NOT on 'type', which is the separate,
        out-of-scope test-LEVEL axis on both sides. Comparing 'type' here
        would silently pass (or fail) on the level axis instead of proving
        anything about the kind-of-proof reconciliation this AC performs.
        """
        ac_item = _ac_test_spec_item_schema()
        ac_kind_enum = set(ac_item.get("properties", {}).get("angle", {}).get("enum") or [])

        test_req = _load(_TEST_REQ_SCHEMA_PATH)
        test_req_kind_enum = set(
            test_req["$defs"]["test_entry"]["properties"]["angle"].get("enum") or []
        )

        assert ac_kind_enum == test_req_kind_enum, (
            f"the two definitions disagree on permitted kinds: "
            f"ac_store_schema={sorted(ac_kind_enum)}, "
            f"test_requirements_schema={sorted(test_req_kind_enum)}. "
            f"Exactly one statement of the permitted kinds must remain."
        )


class TestRetiredKindIsAbsentAndNotAcceptedAsASynonym:
    def test_bo_2900g_3_retired_kind_is_absent_and_not_accepted_as_a_synonym(self) -> None:
        # covers: BO-2900g-3
        """'live_dispatch' must be gone from both definitions, and a
        description carrying it must be rejected rather than silently
        translated to 'reachability'.

        Checked against 'angle' on both real files — the field that actually
        carries the kind-of-proof vocabulary post-reconciliation. Checking
        'type' (the level axis) would pass trivially: 'live_dispatch' was
        never a candidate level value on either side, live_dispatch or not.
        """
        test_req = _load(_TEST_REQ_SCHEMA_PATH)
        kind_enum = set(
            test_req["$defs"]["test_entry"]["properties"]["angle"].get("enum") or []
        )
        assert "live_dispatch" not in kind_enum, (
            f"the retired kind 'live_dispatch' must not appear in the "
            f"reconciled enum: {sorted(kind_enum)}"
        )

        ac_item = _ac_test_spec_item_schema()
        ac_kind_enum = set(ac_item.get("properties", {}).get("angle", {}).get("enum") or [])
        assert "live_dispatch" not in ac_kind_enum, ac_kind_enum

        # No translation layer: outside docs/, 'live_dispatch' must not occur
        # anywhere in the reconciled production module.
        gen_script = _REPO_ROOT / "scripts" / "ac_store" / "generate_ticket_from_ac.py"
        text = gen_script.read_text(encoding="utf-8") if gen_script.is_file() else ""
        assert "live_dispatch" not in text, (
            "no translation layer/synonym for the retired kind may exist in "
            f"{gen_script}"
        )


class TestGeneratorTestAnglesEqualsTheSchemaEnum:
    def test_bo_2900g_3_generator_test_angles_equals_the_schema_enum(self) -> None:
        # covers: BO-2900g-3
        """Cross-source set-equality: generate_ticket_from_ac._TEST_ANGLES must
        equal the reconciled single definition's permitted-kind set, read from
        its real file — not a convenience copy.

        The single definition lives on 'angle', not 'type' — 'type' is the
        separate, out-of-scope test-LEVEL axis on the real schema file.
        """
        sys.path.insert(0, str(_REPO_ROOT / "scripts" / "ac_store"))
        from generate_ticket_from_ac import _TEST_ANGLES  # noqa: PLC0415

        test_req = _load(_TEST_REQ_SCHEMA_PATH)
        single_definition_kinds = set(
            test_req["$defs"]["test_entry"]["properties"]["angle"].get("enum") or []
        )

        assert set(_TEST_ANGLES) == single_definition_kinds, (
            f"generate_ticket_from_ac._TEST_ANGLES ({sorted(_TEST_ANGLES)}) has "
            f"drifted from the single reconciled definition "
            f"({sorted(single_definition_kinds)}). There must be exactly one "
            f"source of truth, read from one file."
        )


class TestDeployedAcSchemaGateRejectsARetiredKind:
    def test_bo_2900g_3_deployed_ac_schema_gate_rejects_a_retired_kind(self) -> None:
        # covers: BO-2900g-3
        """PRODUCTION ENTRY POINT with the must_block modifier: a real AC file
        whose test_spec declares the retired 'live_dispatch' kind must be
        rejected by the deployed check-ac-schema gate with a non-zero exit
        naming the offending value."""
        # Assert, never skip. This is a DEPLOYED-layer test: its entire purpose
        # is to prove the deployed gate rejects the retired kind. If the deployed
        # script is missing — un-built tree, dropped from the deploy manifest,
        # orphaned by a stale build (KI-BP-005) — that is the precise failure this
        # test exists to catch, and skipping would report it as a pass.
        assert HOOK_SCRIPT.is_file(), (
            f"deployed hook script not found: {HOOK_SCRIPT} — run "
            f"`python scripts/build.py --target-dir .` first; a missing deployed "
            f"gate is a failure, not a reason to skip"
        )

        record = {
            "id": "ZZ-2900g-3-r",
            "title": "Fixture declaring a retired test_spec kind",
            "component": "build-orchestration",
            "components": ["build_orchestration"],
            "status": "active",
            "created_by": "tickets/00_inbox/epics/EPIC-Test/01_test.md",
            "criteria": "Given x\nWhen y\nThen z\n",
            "priority": "medium",
            "readiness": "draft",
            "test_spec": [
                {
                    "name": "test_via_retired_kind",
                    "target_dir": "unit_tests/zz/",
                    "type": "live_dispatch",
                }
            ],
        }

        import os
        import shutil

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            if _AC_SCHEMA_PATH.is_file():
                config_dir = root / "config"
                config_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(_AC_SCHEMA_PATH, config_dir / "ac_store_schema.json")
            ac_dir = root / "docs" / "acceptance-criteria"
            ac_dir.mkdir(parents=True, exist_ok=True)
            path = ac_dir / "ZZ-2900g-3-r.yaml"
            path.write_text(
                yaml.safe_dump(record, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )

            env = os.environ.copy()
            env["HOOK_ROOT"] = str(root)
            env["HOOK_TEST_STAGED_FILES"] = str(path)
            result = subprocess.run(
                [sys.executable, str(HOOK_SCRIPT)],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

        assert result.returncode != 0, (
            "an AC file whose test_spec declares the retired 'live_dispatch' "
            f"kind must be blocked by the deployed gate. Got exit "
            f"{result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        combined = (result.stdout + result.stderr).lower()
        assert "live_dispatch" in combined, (
            f"the block message must name the offending value:\n{combined}"
        )

        # Non-vacuous guard: ac_store_schema.json rejecting 'live_dispatch'
        # today is COINCIDENTAL (its type/angle enums never included that
        # value in the first place) — it says nothing about whether the
        # OTHER definition (config/test_requirements.schema.json) has also
        # been reconciled to drop it. Checked against 'angle', the field that
        # carries the kind-of-proof vocabulary post-reconciliation — 'type'
        # is the separate, out-of-scope level axis and never held
        # 'live_dispatch' either way, so checking it here would prove
        # nothing about the reconciliation.
        test_req = _load(_TEST_REQ_SCHEMA_PATH)
        test_req_kind_enum = set(
            test_req["$defs"]["test_entry"]["properties"]["angle"].get("enum") or []
        )
        assert "live_dispatch" not in test_req_kind_enum, (
            "the deployed gate blocking 'live_dispatch' via ac_store_schema.json "
            "is not sufficient proof of reconciliation: "
            "config/test_requirements.schema.json still lists 'live_dispatch' "
            f"in its angle enum: {sorted(test_req_kind_enum)}. Both real files "
            "must agree there is exactly one permitted-kind set."
        )


class TestTestReqTypeIsNotAShadowOfAngle:
    """NEGATIVE CONTROL, ticket-facing side: the same over-merge that hit
    ac_store_schema.json's test_spec[].type could, in principle, recur on
    config/test_requirements.schema.json's test_entry.type — the two files
    have parallel type/angle splits post-reconciliation. Nothing was
    previously asserting the two fields on THIS file stay distinct; this
    closes that gap the same way TestTestLevelAxisIsUnchangedByTheReconciliation
    closes it on the AC-store side.
    """

    def test_bo_2900g_3_test_req_type_and_angle_are_not_the_same_enum(self) -> None:
        # covers: BO-2900g-3
        """test_requirements.schema.json's test_entry.type (test-LEVEL) and
        .angle (kind-of-proof) must not share an enum."""
        test_req = _load(_TEST_REQ_SCHEMA_PATH)
        entry = test_req["$defs"]["test_entry"]["properties"]
        level_enum = set(entry["type"].get("enum") or [])
        angle_enum = set(entry["angle"].get("enum") or [])

        assert level_enum, "test_entry.type must declare a non-empty enum"
        assert angle_enum, "test_entry.angle must declare a non-empty enum"
        assert level_enum != angle_enum, (
            "test_requirements.schema.json's test_entry.type and .angle must "
            f"NOT share the same enum (both currently {sorted(level_enum)}). "
            "This is the ticket-facing side of the exact over-merge this AC "
            "fixes on the AC-store side: a second key mirroring the same "
            "vocabulary is itself a second statement of the permitted "
            "kinds of proof."
        )


class TestTestLevelAxisIsUnchangedByTheReconciliation:
    """NEGATIVE CONTROL for the out-of-scope third axis (BO-2900g-3's own
    test_spec entry, angle: boundary).

    test_spec[].type is the test-LEVEL axis — how heavy a test is and where
    it runs. It is orthogonal to test_spec[].angle, the kind-of-proof axis
    this AC reconciles, and the AC's own first Then clause plus its explicit
    'THE THIRD AXIS IS OUT OF SCOPE' constraint forbid touching it. The
    over-merge defect this AC exists to catch replaced type's enum with
    angle's seven values — making type a duplicate of angle, deleting the
    project's only way to say 'this is an integration test', and
    invalidating all 1,923 test_spec entries that carried a type value in
    the store (measured 2026-08-18: behavioral 891, unit 653, integration
    352, e2e 15, component 12 — zero carried an angle value). Every existing
    descriptor is already schema-SHAPED, so a hand-written fixture stays
    green through that over-merge and proves nothing; this test reads the
    real on-disk schema AND a real, untouched store record back through it.
    """

    def test_bo_2900g_3_test_level_axis_is_unchanged_by_the_reconciliation(
        self,
    ) -> None:
        # covers: BO-2900g-3
        """type still permits the test-LEVEL values, type != angle, and a
        real record carrying type: integration validates against the real
        schema."""
        item_schema = _ac_test_spec_item_schema()
        level_enum = set(
            item_schema.get("properties", {}).get("type", {}).get("enum") or []
        )
        angle_enum = set(
            item_schema.get("properties", {}).get("angle", {}).get("enum") or []
        )

        expected_level_values = {"unit", "integration", "e2e", "behavioral"}
        assert expected_level_values <= level_enum, (
            "test_spec[].type must still permit the test-LEVEL values the "
            f"real corpus uses ({sorted(expected_level_values)}); the schema "
            f"currently permits {sorted(level_enum)}. The test-level axis is "
            "the THIRD, out-of-scope axis for the BO-2900g-3 kind-of-proof "
            "reconciliation and must survive untouched — its own values, its "
            "own meaning."
        )

        assert level_enum != angle_enum, (
            "test_spec[].type and test_spec[].angle must NOT share the same "
            f"enum (both currently {sorted(level_enum)}). A second key "
            "mirroring the same vocabulary is itself a second statement of "
            "the permitted kinds of proof, which this AC's first Then "
            "clause ('exactly one statement of the permitted kinds of "
            "proof remains') forbids."
        )

        # A real, untouched store record carrying type: integration must
        # validate against the real schema read fresh from disk — not a
        # synthetic fixture. TQ-400b-1 (nobody has edited it for this AC)
        # authors four test_spec entries, all type: integration.
        real_record_path = (
            _REPO_ROOT
            / "docs"
            / "acceptance-criteria"
            / "testing-quality"
            / "TQ-400-durable-done-proof"
            / "TQ-400b-1.yaml"
        )
        record = yaml.safe_load(real_record_path.read_text(encoding="utf-8"))
        entry_types = {
            e.get("type") for e in record.get("test_spec", []) if isinstance(e, dict)
        }
        assert "integration" in entry_types, (
            f"fixture assumption broken: {real_record_path} no longer "
            f"carries a test_spec entry with type: integration "
            f"(found {sorted(t for t in entry_types if t)})"
        )

        schema = _load(_AC_SCHEMA_PATH)
        validator = jsonschema.Draft7Validator(schema)
        errors = list(validator.iter_errors(record))
        assert errors == [], (
            f"a real, untouched store record ({real_record_path.name}) "
            f"carrying type: integration must validate against the real "
            f"schema so the reconciliation invalidated no existing record. "
            "Errors:\n"
            + "\n".join(f"  {e.message} at {list(e.path)}" for e in errors)
        )

    # NOTE ON SCOPE: an exhaustive corpus sweep (walking every file under
    # docs/acceptance-criteria/ and checking every observed test_spec[].type
    # value against the schema enum) was drafted here and dropped. It found
    # 12 records carrying type: 'component' — a value outside even the
    # PRE-bug four-value level enum (unit/integration/e2e/behavioral) that
    # this AC's own doc_links describe as the original test-level
    # vocabulary. That is a pre-existing store-hygiene anomaly unrelated to
    # the over-merge this AC fixes; asserting it away here would leave a
    # test the coder's approved revert (to exactly those four values) can
    # never turn green. Flagged for a separate store-hygiene ticket rather
    # than baked into this AC's red baseline. See test-writer sign-off
    # comments for the measured detail.


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
