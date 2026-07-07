"""
MODULE: test_ticket_frontmatter_guard.py
GOAL: Unit tests for the change_target and risk_surface validators added to
    ticket_frontmatter_guard.py as part of EPIC-ComputedQualityGates ticket 02.
BUSINESS CONTEXT: The computed quality gates system requires every ticket to
    declare a two-axis classification (change_target + risk_surface) so the
    agent map can be computed during generation. These tests verify that the
    guard accepts all valid enum values and rejects invalid ones, while
    remaining backward-compatible with existing tickets that omit the fields.
    AC-BO-610-5 tests verify list-value input handling and "Valid values:"
    error message wording.
ARCHITECTURE: Tests import _check_change_target and _check_risk_surface
    directly from templates/hooks/ticket_frontmatter_guard to keep the test
    surface narrow and independent of the hook's stdin/stdout plumbing.
"""
# @ac-tag: BO-610-1
# @ac-tag: BO-610-2
# @ac-tag: BO-610-3
# @ac-tag: BO-610-4
# @ac-tag: BO-610-3-i
# @ac-tag: BO-610-4-i
# @ac-tag: BO-610-5

from __future__ import annotations

import os
import sys
import unittest

# ---------------------------------------------------------------------------
# Path setup — make templates/hooks/ importable regardless of working directory.
# ---------------------------------------------------------------------------
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "templates", "hooks"),
)

from ticket_frontmatter_guard import (
    ALLOWED_CHANGE_TARGETS,
    ALLOWED_RISK_SURFACES,
    _check_change_target,
    _check_risk_surface,
)


# ===========================================================================
# AC-BO-610-1 / AC-BO-610-3 / AC-BO-610-3-i
# change_target: 10 valid values + invalid + absent
# ===========================================================================


class TestChangeTargetValidation(unittest.TestCase):
    """Covers AC-BO-610-1 (10-value enum), AC-BO-610-3 (guard blocks invalid),
    and AC-BO-610-3-i (all 10 values exercised in tests).
    """

    def test_all_valid_change_targets_produce_no_errors(self):
        """Each of the 10 valid change_target values must return an empty list."""
        # covers: BO-610-1, BO-610-3-i
        expected_values = (
            "code",
            "schema",
            "ui",
            "infrastructure",
            "pipeline",
            "prompt",
            "model",
            "config",
            "docs",
            "dependency",
        )
        self.assertEqual(
            len(expected_values),
            10,
            msg="Sanity check: expected_values must contain exactly 10 items (AC-BO-610-1).",
        )
        self.assertEqual(
            set(expected_values),
            set(ALLOWED_CHANGE_TARGETS),
            msg=(
                "ALLOWED_CHANGE_TARGETS constant does not match the expected 10-value set "
                "(AC-BO-610-1). Diff: "
                f"extra={set(ALLOWED_CHANGE_TARGETS) - set(expected_values)}, "
                f"missing={set(expected_values) - set(ALLOWED_CHANGE_TARGETS)}"
            ),
        )
        for value in expected_values:
            with self.subTest(change_target=value):
                errors = _check_change_target({"change_target": value})
                self.assertEqual(
                    errors,
                    [],
                    msg=(
                        f"change_target='{value}' is a valid value but produced errors: "
                        f"{errors} (AC-BO-610-3-i)"
                    ),
                )

    def test_invalid_change_target_produces_error(self):
        """A value outside the enum must return exactly one error (AC-BO-610-3)."""
        # covers: BO-610-3
        errors = _check_change_target({"change_target": "database"})
        self.assertEqual(
            len(errors),
            1,
            msg=(
                "Expected exactly one error for an invalid change_target, "
                f"got {len(errors)}: {errors}"
            ),
        )
        self.assertIn(
            "database",
            errors[0],
            msg="Error message should mention the offending value 'database'.",
        )

    def test_absent_change_target_passes(self):
        """Missing change_target field must return no errors (backward compatibility)."""
        # covers: BO-610-3
        errors = _check_change_target({})
        self.assertEqual(
            errors,
            [],
            msg=(
                "Absent change_target should produce no errors for backward "
                f"compatibility, got: {errors}"
            ),
        )

    def test_null_change_target_passes(self):
        """Explicit None (YAML null) change_target must return no errors."""
        # covers: BO-610-3
        errors = _check_change_target({"change_target": None})
        self.assertEqual(
            errors,
            [],
            msg=(
                "change_target: null should produce no errors (treated as absent), "
                f"got: {errors}"
            ),
        )

    def test_error_message_lists_allowed_values(self):
        """Error message for an invalid value must list the allowed values."""
        # covers: BO-610-3
        errors = _check_change_target({"change_target": "api"})
        self.assertTrue(
            len(errors) > 0,
            msg="Expected at least one error for change_target='api'.",
        )
        # Every allowed value should be mentioned somewhere in the error message.
        combined = " ".join(errors)
        for allowed in ALLOWED_CHANGE_TARGETS:
            self.assertIn(
                allowed,
                combined,
                msg=(
                    f"Allowed value '{allowed}' is not mentioned in the error message. "
                    f"Full message: {combined!r}"
                ),
            )

    def test_change_target_error_message_format(self):
        """Error message must use 'Valid values:' not 'Allowed:' (AC-BO-610-5)."""
        # covers: BO-610-5
        errors = _check_change_target({"change_target": "database"})
        self.assertTrue(
            len(errors) > 0,
            msg="Expected at least one error for change_target='database'.",
        )
        combined = " ".join(errors)
        self.assertIn(
            "Valid values:",
            combined,
            msg=(
                "Error message must contain 'Valid values:' (not 'Allowed:'). "
                f"Full message: {combined!r}"
            ),
        )
        self.assertNotIn(
            "Allowed:",
            combined,
            msg=(
                "Error message must not use 'Allowed:' — use 'Valid values:' instead. "
                f"Full message: {combined!r}"
            ),
        )

    def test_change_target_list_mixed(self):
        """List with valid+invalid entries: only invalid entries produce errors (AC-BO-610-5)."""
        # covers: BO-610-5 scenario 3
        errors = _check_change_target({"change_target": ["code", "database"]})
        # "code" is valid — must not appear in any error
        combined = " ".join(errors)
        self.assertEqual(
            len(errors),
            1,
            msg=(
                "Expected exactly one error (for 'database' only), "
                f"got {len(errors)}: {errors}"
            ),
        )
        self.assertIn(
            "database",
            combined,
            msg=f"Error must mention the invalid entry 'database'. Full: {combined!r}",
        )
        # "code" is valid and must not appear in the error
        self.assertNotIn(
            "'code'",
            combined,
            msg=f"Valid entry 'code' must not appear in the error message. Full: {combined!r}",
        )


# ===========================================================================
# AC-BO-610-2 / AC-BO-610-4 / AC-BO-610-4-i
# risk_surface: 6 valid values + invalid + absent
# ===========================================================================


class TestRiskSurfaceValidation(unittest.TestCase):
    """Covers AC-BO-610-2 (6-value enum), AC-BO-610-4 (guard blocks invalid),
    and AC-BO-610-4-i (all 6 values exercised in tests).
    """

    def test_all_valid_risk_surfaces_produce_no_errors(self):
        """Each of the 6 valid risk_surface values must return an empty list."""
        # covers: BO-610-2, BO-610-4-i
        expected_values = (
            "internal",
            "contract_boundary",
            "auth",
            "privacy",
            "safety",
            "cost",
        )
        self.assertEqual(
            len(expected_values),
            6,
            msg="Sanity check: expected_values must contain exactly 6 items (AC-BO-610-2).",
        )
        self.assertEqual(
            set(expected_values),
            set(ALLOWED_RISK_SURFACES),
            msg=(
                "ALLOWED_RISK_SURFACES constant does not match the expected 6-value set "
                "(AC-BO-610-2). Diff: "
                f"extra={set(ALLOWED_RISK_SURFACES) - set(expected_values)}, "
                f"missing={set(expected_values) - set(ALLOWED_RISK_SURFACES)}"
            ),
        )
        for value in expected_values:
            with self.subTest(risk_surface=value):
                errors = _check_risk_surface({"risk_surface": value})
                self.assertEqual(
                    errors,
                    [],
                    msg=(
                        f"risk_surface='{value}' is a valid value but produced errors: "
                        f"{errors} (AC-BO-610-4-i)"
                    ),
                )

    def test_invalid_risk_surface_produces_error(self):
        """A value outside the enum must return exactly one error (AC-BO-610-4)."""
        # covers: BO-610-4
        errors = _check_risk_surface({"risk_surface": "reputation"})
        self.assertEqual(
            len(errors),
            1,
            msg=(
                "Expected exactly one error for an invalid risk_surface, "
                f"got {len(errors)}: {errors}"
            ),
        )
        self.assertIn(
            "reputation",
            errors[0],
            msg="Error message should mention the offending value 'reputation'.",
        )

    def test_absent_risk_surface_passes(self):
        """Missing risk_surface field must return no errors (backward compatibility)."""
        # covers: BO-610-4
        errors = _check_risk_surface({})
        self.assertEqual(
            errors,
            [],
            msg=(
                "Absent risk_surface should produce no errors for backward "
                f"compatibility, got: {errors}"
            ),
        )

    def test_null_risk_surface_passes(self):
        """Explicit None (YAML null) risk_surface must return no errors."""
        # covers: BO-610-4
        errors = _check_risk_surface({"risk_surface": None})
        self.assertEqual(
            errors,
            [],
            msg=(
                "risk_surface: null should produce no errors (treated as absent), "
                f"got: {errors}"
            ),
        )

    def test_error_message_lists_allowed_values(self):
        """Error message for an invalid value must list the allowed values."""
        # covers: BO-610-4
        errors = _check_risk_surface({"risk_surface": "compliance"})
        self.assertTrue(
            len(errors) > 0,
            msg="Expected at least one error for risk_surface='compliance'.",
        )
        combined = " ".join(errors)
        for allowed in ALLOWED_RISK_SURFACES:
            self.assertIn(
                allowed,
                combined,
                msg=(
                    f"Allowed value '{allowed}' is not mentioned in the error message. "
                    f"Full message: {combined!r}"
                ),
            )

    def test_risk_surface_error_message_format(self):
        """Error message must use 'Valid values:' not 'Allowed:' (AC-BO-610-5)."""
        # covers: BO-610-5
        errors = _check_risk_surface({"risk_surface": "reputation"})
        self.assertTrue(
            len(errors) > 0,
            msg="Expected at least one error for risk_surface='reputation'.",
        )
        combined = " ".join(errors)
        self.assertIn(
            "Valid values:",
            combined,
            msg=(
                "Error message must contain 'Valid values:' (not 'Allowed:'). "
                f"Full message: {combined!r}"
            ),
        )
        self.assertNotIn(
            "Allowed:",
            combined,
            msg=(
                "Error message must not use 'Allowed:' — use 'Valid values:' instead. "
                f"Full message: {combined!r}"
            ),
        )

    def test_risk_surface_list_mixed(self):
        """List with valid+invalid entries: only invalid entries produce errors (AC-BO-610-5)."""
        # covers: BO-610-5 scenario 3
        errors = _check_risk_surface({"risk_surface": ["internal", "reputation"]})
        combined = " ".join(errors)
        self.assertEqual(
            len(errors),
            1,
            msg=(
                "Expected exactly one error (for 'reputation' only), "
                f"got {len(errors)}: {errors}"
            ),
        )
        self.assertIn(
            "reputation",
            combined,
            msg=f"Error must mention the invalid entry 'reputation'. Full: {combined!r}",
        )
        # "internal" is valid and must not appear in the error
        self.assertNotIn(
            "'internal'",
            combined,
            msg=f"Valid entry 'internal' must not appear in the error message. Full: {combined!r}",
        )


# ===========================================================================
# AC-2: Guard enum ↔ guardrail_gates.yaml vocabulary contract
# The YAML's top-level keys must equal ALLOWED_CHANGE_TARGETS and each
# target's sub-keys must equal ALLOWED_RISK_SURFACES.
# This test is intentionally RED before ticket-07 fix (vocabulary is disjoint).
# ===========================================================================

import os as _os

_REPO_ROOT_FOR_YAML = _os.path.join(_os.path.dirname(__file__), "..")
_GUARDRAIL_YAML_PATH = _os.path.join(
    _REPO_ROOT_FOR_YAML, "config", "guardrail_gates.yaml"
)


class TestGuardrailYamlVocabularyContract(unittest.TestCase):
    """AC-2: guardrail_gates.yaml vocabulary must match the ADR-017 guard enums.

    These tests are RED before the ticket-07 fix and GREEN after the YAML is
    rebuilt to the canonical vocabulary.
    """

    def _load_yaml(self):
        import yaml as _yaml
        with open(_GUARDRAIL_YAML_PATH, encoding="utf-8") as fh:
            return _yaml.safe_load(fh)

    def test_ac2_yaml_top_level_keys_equal_allowed_change_targets(self):
        # covers: AC-2
        """AC-2: The top-level keys of guardrail_gates.yaml (excluding the
        flow_change_gates sentinel key) must be identical to the set defined by
        ALLOWED_CHANGE_TARGETS in ticket_frontmatter_guard.py (10 ADR-017 values:
        code, schema, ui, infrastructure, pipeline, prompt, model, config, docs,
        dependency).

        This test FAILS before the fix because the YAML currently uses a different
        vocabulary ({documentation, test, hook, skill, template, data, ...}) that
        is disjoint from the guard enum.
        """
        data = self._load_yaml()
        yaml_change_targets = {
            k for k in data.keys() if k != "flow_change_gates"
        }
        guard_set = set(ALLOWED_CHANGE_TARGETS)

        self.assertEqual(
            yaml_change_targets,
            guard_set,
            msg=(
                "guardrail_gates.yaml top-level keys do not match ALLOWED_CHANGE_TARGETS.\n"
                f"  YAML keys:  {sorted(yaml_change_targets)}\n"
                f"  Guard enum: {sorted(guard_set)}\n"
                f"  Extra in YAML (must be removed):   {sorted(yaml_change_targets - guard_set)}\n"
                f"  Missing from YAML (must be added): {sorted(guard_set - yaml_change_targets)}\n"
                "Rebuild guardrail_gates.yaml to use the 10 ADR-017 change_target values."
            ),
        )

    def test_ac2_yaml_risk_surface_subkeys_equal_allowed_risk_surfaces(self):
        # covers: AC-2
        """AC-2: For every change_target section in guardrail_gates.yaml, the set of
        sub-keys must be identical to ALLOWED_RISK_SURFACES (6 ADR-017 values:
        internal, contract_boundary, auth, privacy, safety, cost).

        This test FAILS before the fix because the YAML currently uses a different
        sub-key vocabulary ({production, staging, integration, unit, none, all}) that
        is disjoint from the guard enum.
        """
        data = self._load_yaml()
        guard_risk_surfaces = set(ALLOWED_RISK_SURFACES)
        failures: list[str] = []

        for change_target, surface_map in data.items():
            if change_target == "flow_change_gates":
                continue
            if not isinstance(surface_map, dict):
                continue
            yaml_surfaces = set(surface_map.keys())
            if yaml_surfaces != guard_risk_surfaces:
                failures.append(
                    f"  change_target='{change_target}':\n"
                    f"    YAML sub-keys: {sorted(yaml_surfaces)}\n"
                    f"    Guard enum:    {sorted(guard_risk_surfaces)}\n"
                    f"    Extra in YAML: {sorted(yaml_surfaces - guard_risk_surfaces)}\n"
                    f"    Missing:       {sorted(guard_risk_surfaces - yaml_surfaces)}"
                )

        self.assertEqual(
            failures,
            [],
            msg=(
                "guardrail_gates.yaml risk_surface sub-keys do not match "
                "ALLOWED_RISK_SURFACES for the following change_target(s):\n"
                + "\n".join(failures)
                + "\nRebuild each section to use the 6 ADR-017 risk_surface values."
            ),
        )


if __name__ == "__main__":
    unittest.main()
