"""
MODULE: test_acs_300j_1_i_self_reference
GOAL: Failing test stubs for ACS-300j-1-i — self-referencing dependency rejection.
BUSINESS CONTEXT: A component entry must not list itself in depends_on.
    The validator must detect self-references as a fast-path and reject the
    entry with error: "Component '<id>' cannot depend on itself".
ARCHITECTURE: Tests load validate_depends_on from
    templates/scripts/commit_guardian/check_components_integrity.py via importlib.

AC reference: ACS-300j-1-i (self-referencing dependency is rejected)
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

_TEMPLATE_HOOK = (
    Path(__file__).resolve().parents[2]
    / "templates"
    / "scripts"
    / "commit_guardian"
    / "check_components_integrity.py"
)

try:
    _spec = importlib.util.spec_from_file_location(
        "_ci_self_ref_shim", str(_TEMPLATE_HOOK)
    )
    _mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
    _validate_depends = _mod.validate_depends_on
    _MODULE_OK = True
    _MODULE_ERR = ""
except Exception as _exc:  # noqa: BLE001
    _MODULE_OK = False
    _MODULE_ERR = str(_exc)


@unittest.skipUnless(_MODULE_OK, f"module load failed: {_MODULE_ERR}")
class TestAcs300j1iSelfReferenceRejected(unittest.TestCase):
    """ACS-300j-1-i: self-referencing depends_on entries must be rejected.

    validate_depends_on currently only checks that each depends_on element
    is in all_component_ids.  A component's own id is always in
    all_component_ids, so self-references pass silently.  These tests assert
    the additional self-reference constraint — all tests below are RED until
    the implementation adds an explicit self-reference guard.
    """

    def test_ac1_self_reference_rejected(self) -> None:
        # covers: ACS-300j-1-i
        """ACS-300j-1-i: self-referencing component is rejected by validate_depends_on.

        Given 'agent_registry' with depends_on: ['agent_registry'], where
        'agent_registry' IS in all_component_ids (so unknown-ID check passes),
        the validator must still return an error for the self-reference.
        """
        errors = _validate_depends(
            "agent_registry",
            {"depends_on": ["agent_registry"]},
            {"agent_registry"},
        )
        self.assertGreater(
            len(errors),
            0,
            msg=(
                "ACS-300j-1-i: expected an error for self-reference but got none. "
                "Current code silently passes self-references because "
                "'agent_registry' in all_component_ids is True."
            ),
        )

    def test_ac1_self_reference_error_message_format(self) -> None:
        # covers: ACS-300j-1-i
        """ACS-300j-1-i: error must contain 'cannot depend on itself'.

        AC specifies: "Component 'agent_registry' cannot depend on itself"
        """
        errors = _validate_depends(
            "agent_registry",
            {"depends_on": ["agent_registry"]},
            {"agent_registry"},
        )
        has_self_ref_message = any("cannot depend on itself" in e for e in errors)
        self.assertTrue(
            has_self_ref_message,
            msg=(
                "ACS-300j-1-i: error must contain 'cannot depend on itself'. "
                f"Actual errors: {errors!r}"
            ),
        )

    def test_ac1_self_reference_names_component_in_message(self) -> None:
        # covers: ACS-300j-1-i
        """ACS-300j-1-i: error message must name the offending component id."""
        component_id = "agent_registry"
        errors = _validate_depends(
            component_id,
            {"depends_on": [component_id]},
            {component_id},
        )
        self.assertTrue(
            len(errors) > 0 and any(component_id in e for e in errors),
            msg=(
                f"ACS-300j-1-i: error must name '{component_id}'. "
                f"Actual errors: {errors!r}"
            ),
        )

    def test_ac1_self_reference_fast_path_known_id(self) -> None:
        # covers: ACS-300j-1-i
        """ACS-300j-1-i: self-reference is rejected even when id IS in all_component_ids.

        it_requirement: 'Self-reference check must run before the full graph
        cycle detection (fast path rejection)'.

        The id is always in all_component_ids for a valid registered component,
        so the unknown-ID check silently passes it.  An explicit self-reference
        guard must fire INDEPENDENTLY of the unknown-ID check.
        """
        all_ids = {"my_comp", "other_comp_a", "other_comp_b"}
        errors = _validate_depends(
            "my_comp",
            {"depends_on": ["my_comp"]},
            all_ids,
        )
        self.assertGreater(
            len(errors),
            0,
            msg=(
                "ACS-300j-1-i: 'my_comp' depends on itself but is a known id. "
                "Existing unknown-ID check passes it silently. "
                f"A separate self-reference guard is required. Errors: {errors!r}"
            ),
        )
        self_ref_errors = [e for e in errors if "itself" in e or "self" in e.lower()]
        self.assertGreater(
            len(self_ref_errors),
            0,
            msg=(
                "ACS-300j-1-i: error must specifically identify a self-reference "
                "(contain 'itself' or 'self'), not just flag an unknown ID. "
                f"Errors: {errors!r}"
            ),
        )

    def test_ac1_each_component_checked_individually(self) -> None:
        # covers: ACS-300j-1-i
        """ACS-300j-1-i: each component is checked individually for self-inclusion.

        it_requirement: 'Must check each component's depends_on for
        self-inclusion individually'.

        Two separate calls (one per component entry) must each yield an error
        when the component lists itself.
        """
        all_ids = {"alpha", "beta", "gamma"}

        errors_alpha = _validate_depends(
            "alpha",
            {"depends_on": ["alpha"]},
            all_ids,
        )
        errors_beta = _validate_depends(
            "beta",
            {"depends_on": ["beta"]},
            all_ids,
        )

        self.assertGreater(
            len(errors_alpha),
            0,
            msg=f"ACS-300j-1-i: 'alpha' self-reference must be rejected. Got: {errors_alpha!r}",
        )
        self.assertGreater(
            len(errors_beta),
            0,
            msg=f"ACS-300j-1-i: 'beta' self-reference must be rejected. Got: {errors_beta!r}",
        )

    def test_ac1_mixed_self_and_valid_ref_catches_self_only(self) -> None:
        # covers: ACS-300j-1-i
        """ACS-300j-1-i: only the self-reference is flagged, not valid co-listed entries."""
        all_ids = {"agent_registry", "ac_store"}
        errors = _validate_depends(
            "agent_registry",
            {"depends_on": ["agent_registry", "ac_store"]},
            all_ids,
        )
        self.assertGreater(
            len(errors),
            0,
            msg=(
                "ACS-300j-1-i: self-reference 'agent_registry' must produce an error "
                f"even when valid 'ac_store' is also listed. Errors: {errors!r}"
            ),
        )
        self_ref_errors = [
            e for e in errors if "agent_registry" in e and "itself" in e
        ]
        self.assertGreater(
            len(self_ref_errors),
            0,
            msg=(
                "ACS-300j-1-i: error must name 'agent_registry' and contain 'itself'. "
                f"Actual errors: {errors!r}"
            ),
        )
        ac_store_errors = [
            e for e in errors if "ac_store" in e and "unknown" in e.lower()
        ]
        self.assertEqual(
            ac_store_errors,
            [],
            msg=(
                "ACS-300j-1-i: 'ac_store' is a valid reference and must not generate "
                f"an error. Actual errors: {errors!r}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
