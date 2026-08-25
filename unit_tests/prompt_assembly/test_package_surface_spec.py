"""
test_package_surface_spec.py — TDD stubs for ticket 04 (EPIC-PromptAssemblyHardening).

Tests that package-surface ACs carry a machine-checkable implementation spec.

A record is a package surface because it SAYS SO — ``package_surface: true`` — not
because of what agent it is assigned to or how its component happens to be spelled
(ACS-100i-6). The fixtures below declare the surface explicitly for that reason; the
original ``assigned_agent=python-coder`` + ``component in [build_pipeline,
build-orchestration]`` proxy is retained on them only so the tests that exercise
``validate_ac.py``'s deprecated legacy fallback still reach it.

These tests are intentionally RED before implementation:
  - AC-1/AC-2 (BO-2000d-1, BO-2000d-1-i): schema conditional enforcement
    (currently the schema allows package-surface ACs without impl fields)
  - AC-3 (BO-2000d-2): validate_ac.py does not yet exist
  - AC-4 (BO-2000d-3): obligation statement absent from it-po.md
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

# Resolve the repo root (worktree root) — tests run from the repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_schema() -> dict:
    """Load config/ac_store_schema.json from the repo root."""
    schema_path = _REPO_ROOT / "config" / "ac_store_schema.json"
    with open(schema_path, encoding="utf-8") as fh:
        return json.load(fh)


def _make_package_surface_ac(**overrides) -> dict:
    """Return a minimal AC that DECLARES a package surface.

    ``package_surface: true`` is what makes this a package surface to the schema —
    the ``assigned_agent`` / ``component`` pair below is the deprecated legacy proxy,
    kept only so the ``validate_ac.py`` tests still exercise that fallback path.
    """
    base = {
        "id": "BO-999a-1",
        "title": "Test package-surface AC",
        "component": "build_pipeline",
        "status": "active",
        "criteria": "Given a package-surface AC When it is validated Then impl fields are required.",
        "assigned_agent": "python-coder",
        "package_surface": True,
        "readiness": "draft",
        "priority": "high",
    }
    base.update(overrides)
    return base


def _make_non_package_surface_ac(**overrides) -> dict:
    """Return a minimal non-package-surface AC (assigned to documentation-expert)."""
    base = {
        "id": "BO-888a-1",
        "title": "Test non-package-surface AC",
        "component": "documentation",
        "status": "active",
        "criteria": "Given docs When written Then they are accurate.",
        "assigned_agent": "documentation-expert",
        "readiness": "draft",
        "priority": "medium",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# AC-1 / AC-2: Schema requires impl fields for package-surface ACs (BO-2000d-1)
# A non-package-surface AC without them passes (BO-2000d-1-i)
# ---------------------------------------------------------------------------

class TestSchemaRequiresImplFieldsForPackageSurfaceAC(unittest.TestCase):
    """Covers AC-1 (BO-2000d-1) and AC-2 (BO-2000d-1-i)."""

    def setUp(self):
        self.schema = _load_schema()

    def test_schema_requires_impl_fields_for_package_surface_ac(self):
        # covers: BO-2000d-1
        # covers: BO-2000d-1-i
        """
        AC-1 (BO-2000d-1): The schema must reject a package-surface AC that lacks
        the implementation-requirement fields.
        AC-2 (BO-2000d-1-i): A non-package-surface AC without those fields must pass.

        Implementation requirement fields that MUST be present in it_requirements for
        package-surface ACs:
          - config_schema_fragment
          - reference_file_path
          - n_location_rule
          - required_skills
          - post_write_commands
        """
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema not installed — cannot run schema validation test")

        # --- Package-surface AC WITHOUT impl fields must FAIL validation ---
        thin_ac = _make_package_surface_ac()
        # Provide a thin it_requirements string (not the required object)
        thin_ac["it_requirements"] = "implement the feature"

        errors = list(jsonschema.Draft7Validator(self.schema).iter_errors(thin_ac))

        # After implementation the schema must raise an error for the missing object structure.
        # Currently the schema permits a plain string for it_requirements on all ACs —
        # this assertion will be RED until the schema is extended with the conditional.
        impl_field_errors = [
            e for e in errors
            if (
                "it_requirements" in str(e.path)
                or "config_schema_fragment" in str(e.message)
                or "reference_file_path" in str(e.message)
                or "n_location_rule" in str(e.message)
                or "required_skills" in str(e.message)
                or "post_write_commands" in str(e.message)
            )
        ]
        self.assertTrue(
            len(impl_field_errors) > 0,
            "Expected schema to reject a package-surface AC with thin it_requirements, "
            "but no validation error was produced. The schema conditional enforcement "
            "is not yet implemented.",
        )

        # --- Non-package-surface AC WITHOUT impl fields must PASS validation ---
        doc_ac = _make_non_package_surface_ac()
        non_ps_errors = list(jsonschema.Draft7Validator(self.schema).iter_errors(doc_ac))
        impl_errors_for_non_ps = [
            e for e in non_ps_errors
            if (
                "config_schema_fragment" in str(e.message)
                or "reference_file_path" in str(e.message)
                or "n_location_rule" in str(e.message)
            )
        ]
        self.assertEqual(
            len(impl_errors_for_non_ps),
            0,
            "A non-package-surface AC must NOT be rejected for missing impl fields. "
            f"Got errors: {impl_errors_for_non_ps}",
        )


# ---------------------------------------------------------------------------
# AC-3 (BO-2000d-2): Validator rejects thin/fictional package-surface spec
# ---------------------------------------------------------------------------

class TestValidatorRejectsFictionalReference(unittest.TestCase):
    """Covers AC-3 (BO-2000d-2)."""

    def test_validator_rejects_fictional_reference(self):
        # covers: BO-2000d-2
        """
        AC-3 (BO-2000d-2): validate_ac.py must reject a package-surface AC whose
        it_requirements contains an unresolvable reference_file_path, or a registration
        entry that is missing required keys (config_schema_fragment, n_location_rule,
        required_skills, post_write_commands).

        This test imports validate_package_surface_spec from scripts.ac_store.validate_ac.
        That module does not yet exist, so this test will be RED with ImportError until
        python-coder creates validate_ac.py.
        """
        from scripts.ac_store.validate_ac import validate_package_surface_spec  # noqa: F401

        # Thin AC with a fictional (non-existent) reference_file_path
        thin_ac = _make_package_surface_ac()
        thin_ac["it_requirements"] = {
            "config_schema_fragment": {"type": "string"},
            "reference_file_path": "/path/that/does/not/exist/nonexistent_script.py",
            "n_location_rule": "1",
            "required_skills": ["python-coder"],
            "post_write_commands": ["python scripts/build.py"],
        }

        # The validator must return an error for the unresolvable path.
        result = validate_package_surface_spec(
            thin_ac,
            repo_root=_REPO_ROOT,
        )
        self.assertFalse(
            result.ok,
            "Expected validate_package_surface_spec to reject an AC with an "
            "unresolvable reference_file_path, but it returned ok=True.",
        )
        self.assertTrue(
            any("reference_file_path" in str(e) for e in result.errors),
            f"Expected an error mentioning 'reference_file_path'. Got: {result.errors}",
        )

    def test_validator_rejects_registration_entry_missing_required_keys(self):
        # covers: BO-2000d-2
        """
        A registration entry in it_requirements that is missing required keys
        (e.g. missing n_location_rule) must also be rejected.
        """
        from scripts.ac_store.validate_ac import validate_package_surface_spec  # noqa: F401

        incomplete_ac = _make_package_surface_ac()
        incomplete_ac["it_requirements"] = {
            "config_schema_fragment": {"type": "string"},
            # reference_file_path is present and resolvable
            "reference_file_path": str(_REPO_ROOT / "config" / "ac_store_schema.json"),
            # n_location_rule is MISSING — a required key
            "required_skills": ["python-coder"],
            "post_write_commands": [],
        }

        result = validate_package_surface_spec(
            incomplete_ac,
            repo_root=_REPO_ROOT,
        )
        self.assertFalse(
            result.ok,
            "Expected validate_package_surface_spec to reject an AC with a missing "
            "n_location_rule, but it returned ok=True.",
        )
        self.assertTrue(
            any("n_location_rule" in str(e) for e in result.errors),
            f"Expected an error mentioning 'n_location_rule'. Got: {result.errors}",
        )


# ---------------------------------------------------------------------------
# AC-4 (BO-2000d-3): it-po template states the obligation
# ---------------------------------------------------------------------------

class TestItPoTemplateStatesObligation(unittest.TestCase):
    """Covers AC-4 (BO-2000d-3)."""

    def test_it_po_template_states_obligation(self):
        # covers: BO-2000d-3
        """
        AC-4 (BO-2000d-3): templates/agents/it-po.md must contain text that states
        the obligation for IT POs to populate the implementation-requirement fields for
        package-surface ACs (those assigned to python-coder in build_pipeline or
        build-orchestration components).

        This test reads the template file and asserts the obligation is stated.
        Currently the template does NOT contain this obligation, so this test is RED.
        """
        template_path = _REPO_ROOT / "templates" / "agents" / "it-po.md"
        self.assertTrue(
            template_path.exists(),
            f"it-po.md template not found at {template_path}",
        )

        content = template_path.read_text(encoding="utf-8")

        # The template must explicitly state the package-surface impl-field obligation.
        # Check for the key terms that the obligation statement must include:
        self.assertIn(
            "package-surface",
            content,
            "it-po.md must contain the term 'package-surface' as part of the "
            "obligation to populate impl fields. "
            "The obligation statement is not yet present.",
        )
        self.assertIn(
            "it_requirements",
            content,
            "it-po.md must mention 'it_requirements' in the obligation section. "
            "The obligation statement is not yet present.",
        )
        # The obligation must reference the required sub-fields
        self.assertIn(
            "reference_file_path",
            content,
            "it-po.md must mention 'reference_file_path' as a required field for "
            "package-surface ACs. The obligation statement is not yet present.",
        )


if __name__ == "__main__":
    unittest.main()
