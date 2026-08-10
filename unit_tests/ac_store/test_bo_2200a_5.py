#!/usr/bin/env python3
"""
MODULE: test_bo_2200a_5
GOAL: RED test stubs for AC BO-2200a-5.

Tests that the schema validator rejects `documentation_triggers` on any AC
that is not level L1, names the offending AC id and level in the error
message, and that the pre-existing enum-value check still fires on L1 ACs.

The key red test is `test_documentation_triggers_on_l2_is_rejected`: the
current validate_ac_schema.py validates enum values but does NOT check
whether the AC is level L1, so the assertion on the L1-only error message
fails (no such error is produced).

TICKET: 06_TICKET-20260715-BO-2200a-5.md
COVERS: BO-2200a-5
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Path setup: unit_tests/ac_store/ is three levels below the repo root
# repo_root/scripts/ac_store/ holds validate_ac_schema.py
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from validate_ac_schema import _validate_file  # noqa: E402


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _write_ac_yaml(tmpdir: Path, ac_data: dict) -> Path:
    """Serialize *ac_data* to a YAML file inside *tmpdir* and return the path."""
    path = tmpdir / f"{ac_data['id']}.yaml"
    path.write_text(yaml.dump(ac_data, allow_unicode=True), encoding="utf-8")
    return path


def _minimal_ac(
    ac_id: str,
    level: str,
    documentation_triggers: list[str] | None = None,
) -> dict:
    """Return a minimal AC dict that satisfies all fields except the one under test.

    Uses `components: ["build_orchestration"]` — the registry check is bypassed by
    passing an empty registry_ids set, so any component name works here.
    """
    ac: dict = {
        "id": ac_id,
        "readiness": "approved",
        "priority": "medium",
        "components": ["build_orchestration"],
        "level": level,
        "status": "active",
        "title": f"Fixture AC {ac_id}",
    }
    if documentation_triggers is not None:
        ac["documentation_triggers"] = documentation_triggers
    return ac


# Passing an empty registry bypasses the unknown-component check in
# _ac_components.components_field_errors (see the `if registry_ids:` guard),
# while still requiring `components` to be a non-empty list.  This keeps the
# tests self-contained (no dependency on docs/components.json on disk).
_EMPTY_REGISTRY: set[str] = set()


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestDocumentationTriggersLevelConstraint(unittest.TestCase):
    """BO-2200a-5: documentation_triggers is only permitted on L1 ACs."""

    def test_documentation_triggers_on_l2_is_rejected(self):
        # covers: BO-2200a-5
        """An L2 AC carrying documentation_triggers fails validation with an
        error naming the AC id and level and stating the field is L1-only.

        Must be RED before implementation: the current validate_ac_schema.py
        validates the enum values of documentation_triggers but does NOT check
        the AC level, so no L1-only error is produced and these assertions fail.

        What must be implemented to turn this green:
            In _validate_file(), after the existing enum-value check for
            documentation_triggers, add a level guard that rejects the field
            when data.get("level") is not "L1".  The error message must name
            the AC id (data["id"]) and the actual level.
        """
        ac_id = "BO-TEST-L2-REJECT"
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write_ac_yaml(
                Path(tmpdir),
                _minimal_ac(ac_id, level="L2", documentation_triggers=["how-to"]),
            )
            errors = _validate_file(path, _EMPTY_REGISTRY)

        # Expect at least one error containing both "L1" and "documentation_triggers"
        level_errors = [
            e for e in errors
            if "L1" in e and "documentation_triggers" in e
        ]
        self.assertGreater(
            len(level_errors),
            0,
            msg=(
                f"Expected at least one validation error mentioning 'L1' and "
                f"'documentation_triggers' for an L2 AC, but got: {errors}.\n"
                "The L1-only level constraint is not yet enforced in "
                "validate_ac_schema.py — this test is intentionally RED."
            ),
        )

        combined = " ".join(level_errors)

        # Error must name the offending AC id
        self.assertIn(
            ac_id,
            combined,
            msg=(
                f"Level-constraint error must name the offending AC id "
                f"({ac_id!r}). Got level errors: {level_errors}"
            ),
        )
        # Error must name the offending level
        self.assertIn(
            "L2",
            combined,
            msg=(
                f"Level-constraint error must name the offending level (L2). "
                f"Got level errors: {level_errors}"
            ),
        )

    def test_documentation_triggers_on_l2_l3_l0_all_rejected(self):
        # covers: BO-2200a-5
        """L2, L3, and L0 ACs that carry documentation_triggers all fail with
        an L1-only error.

        RED before implementation (same root cause as the L2 test): the current
        code does not check level before accepting the field.
        """
        for level in ("L2", "L3", "L0"):
            ac_id = f"BO-TEST-{level}-ALL-REJECT"
            with self.subTest(level=level):
                with tempfile.TemporaryDirectory() as tmpdir:
                    path = _write_ac_yaml(
                        Path(tmpdir),
                        _minimal_ac(
                            ac_id,
                            level=level,
                            documentation_triggers=["sequence-diagram"],
                        ),
                    )
                    errors = _validate_file(path, _EMPTY_REGISTRY)

                level_errors = [
                    e for e in errors
                    if "L1" in e and "documentation_triggers" in e
                ]
                self.assertGreater(
                    len(level_errors),
                    0,
                    msg=(
                        f"Expected L1-only error for level={level!r} AC "
                        f"carrying documentation_triggers. Got: {errors}"
                    ),
                )

    def test_documentation_triggers_on_l1_is_permitted(self):
        # covers: BO-2200a-5
        """An L1 AC carrying documentation_triggers passes the L1-only rule.

        Regression guard: after the L1-only check is implemented, the rule
        must NOT fire for L1 ACs.  This test currently passes (no level check
        exists yet), but it protects against an incorrect implementation that
        also rejects L1.
        """
        ac_id = "BO-TEST-L1-PERMIT"
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write_ac_yaml(
                Path(tmpdir),
                _minimal_ac(ac_id, level="L1", documentation_triggers=["how-to"]),
            )
            errors = _validate_file(path, _EMPTY_REGISTRY)

        # No error should fire the L1-only constraint for an L1 AC
        level_only_errors = [
            e for e in errors
            if "documentation_triggers" in e and "L1" in e and "only" in e.lower()
        ]
        self.assertEqual(
            level_only_errors,
            [],
            msg=(
                "An L1 AC with a valid documentation_triggers value must NOT "
                "trigger the L1-only rule.  Got level-constraint errors: "
                f"{level_only_errors}"
            ),
        )

    def test_enum_validation_still_applies_on_l1(self):
        # covers: BO-2200a-5
        """An L1 AC with an out-of-enum documentation_triggers value is rejected
        by the pre-existing enum-value check.

        Regression guard: the new L1-level-check must be added IN ADDITION TO
        the existing enum check, not replacing it.  This test ensures the enum
        check still fires after implementation.  It currently passes (the enum
        check already works in the existing code).
        """
        ac_id = "BO-TEST-L1-ENUM-INVALID"
        invalid_trigger = "not-a-valid-trigger"

        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write_ac_yaml(
                Path(tmpdir),
                _minimal_ac(
                    ac_id,
                    level="L1",
                    documentation_triggers=[invalid_trigger],
                ),
            )
            errors = _validate_file(path, _EMPTY_REGISTRY)

        # Must have an error about the invalid enum value
        enum_errors = [
            e for e in errors
            if "documentation_triggers" in e and "invalid" in e.lower()
        ]
        self.assertGreater(
            len(enum_errors),
            0,
            msg=(
                f"An L1 AC with an out-of-enum documentation_triggers value "
                f"({invalid_trigger!r}) must still be rejected by the enum "
                f"check.  Got errors: {errors}."
            ),
        )
        # Error must reference the bad value
        combined = " ".join(enum_errors)
        self.assertIn(
            invalid_trigger,
            combined,
            msg=(
                f"Enum-error message must name the invalid trigger "
                f"({invalid_trigger!r}).  Got: {enum_errors}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
