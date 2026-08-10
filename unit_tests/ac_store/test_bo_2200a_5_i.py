#!/usr/bin/env python3
"""
MODULE: test_bo_2200a_5_i
GOAL: Regression tests for AC BO-2200a-5-i — independence of the enum-value
      check and the L1-only level check on `documentation_triggers`.

AC: BO-2200a-5-i
Title: A valid documentation_triggers enum value on a non-L1 AC is still
       rejected for being off-level.

Independence rule (from the AC):
  - A valid enum value MUST NOT suppress the L1-only level check.
  - The L1-level-OK condition MUST NOT suppress the enum-value check.
  - An AC can fail one, the other, or both — the two checks run and report
    independently.

Test file: unit_tests/ac_store/test_bo_2200a_5_i.py
TICKET: 07_TICKET-20260715-BO-2200a-5-i.md
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Path setup: repo_root/scripts/ac_store/ holds validate_ac_schema.py
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from validate_ac_schema import _validate_file  # noqa: E402


# ---------------------------------------------------------------------------
# Test helpers (mirrors the pattern in test_bo_2200a_5.py)
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
    """Return a minimal AC dict that satisfies all required fields.

    Uses `components: ["build_orchestration"]` — the registry check is
    bypassed by passing an empty registry_ids set (the `if registry_ids:`
    guard in `_ac_components.components_field_errors` exits early for an
    empty set), so any component name works here.
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


# An empty registry bypasses the unknown-component check, keeping tests
# self-contained (no dependency on docs/components.json on disk).
_EMPTY_REGISTRY: set[str] = set()


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestDocumentationTriggersIndependence(unittest.TestCase):
    """BO-2200a-5-i: enum check and L1-only level check are independent.

    Each test isolates one axis of independence:
    - test_valid_enum_on_l2_still_fails_off_level: valid enum does NOT mask
      the level check (L2 + valid enum → level error present, no enum error).
    - test_invalid_enum_on_l1_fails_enum_check: L1-permitted level does NOT
      mask the enum check (L1 + invalid enum → enum error present, no level
      error).
    - test_both_checks_fire_when_both_violated: when both rules are violated
      simultaneously (L2 + invalid enum), both errors appear — neither masks
      the other.
    """

    def test_valid_enum_on_l2_still_fails_off_level(self):
        # covers: BO-2200a-5-i
        """An L2 AC with a *valid* enum value in documentation_triggers still
        fails on the L1-only level rule.

        Independence assertion: a valid enum value must NOT suppress the level
        check.  The level error must be present; the enum error must NOT be
        present (because the enum value is valid).

        This test is a regression guard for the independence property.
        It will be RED if the level check is gated behind the enum check
        (i.e., the implementation only runs the level check when the enum
        check also fails).

        Implementation target (validate_ac_schema._validate_file):
            The level check must run even when the enum-value check produces
            no error.  The two `if` branches must be independent and not
            short-circuit each other.
        """
        ac_id = "BO-INDEP-L2-VALID-ENUM"
        valid_trigger = "reference-doc"  # Valid enum member

        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write_ac_yaml(
                Path(tmpdir),
                _minimal_ac(ac_id, level="L2", documentation_triggers=[valid_trigger]),
            )
            errors = _validate_file(path, _EMPTY_REGISTRY)

        # --- Must fail: level check must fire for L2 ---
        level_errors = [
            e for e in errors
            if "L1" in e and "documentation_triggers" in e
        ]
        self.assertGreater(
            len(level_errors),
            0,
            msg=(
                f"Expected at least one validation error stating "
                f"'documentation_triggers' is L1-only, for an L2 AC whose "
                f"enum value is valid ({valid_trigger!r}). Got: {errors}.\n"
                "Independence violation: a valid enum value must NOT suppress "
                "the level check.  The level check must run independently."
            ),
        )

        # Error must name the AC id
        combined_level = " ".join(level_errors)
        self.assertIn(
            ac_id,
            combined_level,
            msg=(
                f"Level-constraint error must name the offending AC id "
                f"({ac_id!r}).  Got level errors: {level_errors}"
            ),
        )

        # Error must name the offending level
        self.assertIn(
            "L2",
            combined_level,
            msg=(
                f"Level-constraint error must name the offending level ('L2'). "
                f"Got level errors: {level_errors}"
            ),
        )

        # --- Must not fail on the enum check (valid value was supplied) ---
        # "invalid" appears in the enum error message template:
        #   "contains invalid values: ..."
        enum_errors = [
            e for e in errors
            if "invalid" in e.lower() and "documentation_triggers" in e
        ]
        self.assertEqual(
            enum_errors,
            [],
            msg=(
                f"Enum check must NOT fire for a valid enum value "
                f"({valid_trigger!r}) — only the level error should appear. "
                f"Got unexpected enum errors: {enum_errors}"
            ),
        )

    def test_invalid_enum_on_l1_fails_enum_check(self):
        # covers: BO-2200a-5-i
        """An L1 AC with an *invalid* enum value in documentation_triggers
        fails on the enum-value check even though the level is permitted.

        Independence assertion: the level being correct (L1) must NOT suppress
        the enum check.  The enum error must be present; NO level/L1-only error
        must appear (because L1 is permitted).

        This test is a regression guard for the independence property.
        It will be RED if the enum check is gated behind the level check
        (i.e., the implementation skips the enum check for L1 ACs, or the
        level check incorrectly fires for L1 ACs).

        Implementation target (validate_ac_schema._validate_file):
            The enum check must run and report even when the level is L1.
            The level check must NOT report an error for L1 ACs.
        """
        ac_id = "BO-INDEP-L1-INVALID-ENUM"
        invalid_trigger = "tutorial"  # NOT in the valid enum set

        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write_ac_yaml(
                Path(tmpdir),
                _minimal_ac(ac_id, level="L1", documentation_triggers=[invalid_trigger]),
            )
            errors = _validate_file(path, _EMPTY_REGISTRY)

        # --- Must fail: enum check must fire ---
        # The enum error message contains "invalid values:"
        enum_errors = [
            e for e in errors
            if "documentation_triggers" in e and "invalid" in e.lower()
        ]
        self.assertGreater(
            len(enum_errors),
            0,
            msg=(
                f"Expected at least one validation error for the invalid enum "
                f"value ({invalid_trigger!r}) on an L1 AC. Got: {errors}.\n"
                "Independence violation: a permitted level (L1) must NOT "
                "suppress the enum-value check."
            ),
        )

        # Error must name the invalid value
        combined_enum = " ".join(enum_errors)
        self.assertIn(
            invalid_trigger,
            combined_enum,
            msg=(
                f"Enum error must name the invalid trigger value "
                f"({invalid_trigger!r}).  Got enum errors: {enum_errors}"
            ),
        )

        # --- Must NOT fail on the level check (L1 is permitted) ---
        # The level error message contains "only on L1" or similar
        level_errors = [
            e for e in errors
            if "documentation_triggers" in e and "L1" in e and "only" in e.lower()
        ]
        self.assertEqual(
            level_errors,
            [],
            msg=(
                f"Level check must NOT fire for an L1 AC — L1 is the permitted "
                f"level.  Got unexpected level errors: {level_errors}"
            ),
        )

    def test_both_checks_fire_when_both_violated(self):
        # covers: BO-2200a-5-i
        """When an L2 AC has an *invalid* enum value, BOTH the enum check
        AND the level check must produce separate errors.

        Independence assertion: neither rule masks the other.  When an AC
        violates both rules simultaneously, both error messages must appear
        in the error list as separate entries.

        This test is a regression guard for the full independence property —
        it would catch implementations that only report ONE of the two errors
        (e.g., short-circuiting after the first failing check).
        """
        ac_id = "BO-INDEP-L2-INVALID-ENUM"
        invalid_trigger = "tutorial"  # invalid enum value
        level = "L2"  # non-L1 level

        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write_ac_yaml(
                Path(tmpdir),
                _minimal_ac(
                    ac_id,
                    level=level,
                    documentation_triggers=[invalid_trigger],
                ),
            )
            errors = _validate_file(path, _EMPTY_REGISTRY)

        # Must have an enum error
        enum_errors = [
            e for e in errors
            if "documentation_triggers" in e and "invalid" in e.lower()
        ]
        self.assertGreater(
            len(enum_errors),
            0,
            msg=(
                f"Expected an enum-value error for {invalid_trigger!r} on "
                f"an L2 AC, but got: {errors}"
            ),
        )

        # Must ALSO have a level error — separately
        level_errors = [
            e for e in errors
            if "L1" in e and "documentation_triggers" in e
        ]
        self.assertGreater(
            len(level_errors),
            0,
            msg=(
                f"Expected a level-constraint error for level={level!r} AC "
                f"alongside the enum error. Got: {errors}.\n"
                "Both checks must run and report independently."
            ),
        )

        # The two error messages must be DISTINCT entries in the list
        # (not merged into a single combined message)
        self.assertGreaterEqual(
            len(errors),
            2,
            msg=(
                f"Expected at least 2 separate error entries when both the "
                f"enum check and the level check fail. Got {len(errors)} "
                f"error(s): {errors}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
