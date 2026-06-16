"""
MODULE: test_check_ac_schema
GOAL: Unit tests for check_ac_schema.py pre-commit hook.
BUSINESS CONTEXT: Verifies the AC schema validator correctly accepts well-formed
    AC YAML files and rejects files with missing required fields, invalid status
    values, and malformed ID formats.
ARCHITECTURE: Tests invoke the hook module's internal validation functions
    directly (not via subprocess) to keep tests fast and deterministic. A small
    number of subprocess tests verify the CLI exit-code contract. Temporary
    directories and files are used to isolate each test's filesystem state.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

HOOK_SCRIPT = (
    Path(__file__).parent.parent.parent
    / "templates"
    / "commit-guardian"
    / "check_ac_schema.py"
)

SCHEMA_FILE = (
    Path(__file__).parent.parent.parent
    / "config"
    / "ac_store_schema.json"
)

# Minimal valid AC YAML content used as a baseline in multiple tests.
_VALID_AC_YAML = textwrap.dedent("""\
    id: FIN-001
    title: "Merge main before running tests"
    component: finalize
    status: active
    created_by: "tickets/00_inbox/epics/EPIC-Test/01_test.md"
    criteria: |
      Given a feature branch exists
      When the workflow runs
      Then main is merged first
    priority: medium
    readiness: draft
""")


def _write_ac_file(directory: Path, filename: str, content: str) -> Path:
    """Write a YAML file under directory/docs/acceptance-criteria/ and return its path.

    Also copies the project schema file to directory/config/ac_store_schema.json so
    that jsonschema-based validation (including optional-field minLength checks) is
    active for every test that uses this helper.

    Args:
        directory: Temporary root directory to write into.
        filename: Filename for the AC YAML file (e.g. "FIN-001.yaml").
        content: Raw YAML content string to write.

    Returns:
        Path to the written file.
    """
    import shutil

    # Copy schema so the hook finds it and uses jsonschema validation.
    if SCHEMA_FILE.is_file():
        config_dir = directory / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SCHEMA_FILE, config_dir / "ac_store_schema.json")

    ac_dir = directory / "docs" / "acceptance-criteria"
    ac_dir.mkdir(parents=True, exist_ok=True)
    path = ac_dir / filename
    path.write_text(content, encoding="utf-8")
    return path


def _run_hook(root: Path) -> subprocess.CompletedProcess:
    """Run check_ac_schema.py as a subprocess with HOOK_ROOT set.

    Args:
        root: Temporary directory that acts as the repository root.

    Returns:
        CompletedProcess with returncode, stdout, and stderr captured.
    """
    import os

    env = os.environ.copy()
    env["HOOK_ROOT"] = str(root)
    return subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
    )


class TestValidAcPasses(unittest.TestCase):
    """Minimal valid YAML file should exit 0 with no errors."""

    def test_valid_ac_passes(self) -> None:
        """A well-formed AC YAML file exits 0."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "FIN-001.yaml", _VALID_AC_YAML)
            result = _run_hook(root)
        self.assertEqual(result.returncode, 0, msg=result.stderr)


class TestMissingRequiredField(unittest.TestCase):
    """YAML missing the criteria field should exit 1."""

    def test_missing_required_field_blocked(self) -> None:
        """A YAML file missing 'criteria' exits 1 with a descriptive error."""
        content = textwrap.dedent("""\
            id: FIN-001
            title: "Missing criteria"
            component: finalize
            status: active
            created_by: "tickets/test.md"
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "FIN-001.yaml", content)
            result = _run_hook(root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("criteria", result.stderr)


class TestInvalidStatus(unittest.TestCase):
    """YAML with an unrecognised status value should exit 1."""

    def test_invalid_status_blocked(self) -> None:
        """A YAML file with status: unknown exits 1 mentioning the bad value."""
        content = textwrap.dedent("""\
            id: FIN-001
            title: "Bad status"
            component: finalize
            status: unknown
            created_by: "tickets/test.md"
            criteria: |
              Given something
              When something
              Then something
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "FIN-001.yaml", content)
            result = _run_hook(root)
        self.assertEqual(result.returncode, 1)
        # jsonschema produces "'unknown' is not one of ..." or manual path produces
        # "invalid status 'unknown'..." — both contain "unknown".
        self.assertIn("unknown", result.stderr)


class TestInvalidIdFormat(unittest.TestCase):
    """YAML with a malformed ID should exit 1."""

    def test_invalid_id_format_blocked(self) -> None:
        """A YAML file with id: NOTVALID exits 1 mentioning the ID."""
        content = textwrap.dedent("""\
            id: NOTVALID
            title: "Bad ID"
            component: finalize
            status: active
            created_by: "tickets/test.md"
            criteria: |
              Given something
              When something
              Then something
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "bad-id.yaml", content)
            result = _run_hook(root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("id", result.stderr)


class TestDeprecatedAcPasses(unittest.TestCase):
    """YAML with status: deprecated is a valid status and should pass."""

    def test_deprecated_ac_passes(self) -> None:
        """A YAML file with status: deprecated exits 0."""
        content = textwrap.dedent("""\
            id: FIN-002
            title: "Deprecated criterion"
            component: finalize
            status: deprecated
            created_by: "tickets/test.md"
            criteria: |
              Given something old
              When it is deprecated
              Then it still validates
            priority: medium
            readiness: draft
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "FIN-002.yaml", content)
            result = _run_hook(root)
        self.assertEqual(result.returncode, 0, msg=result.stderr)


class TestNoAcDirectory(unittest.TestCase):
    """When docs/acceptance-criteria/ does not exist, hook exits 0 silently."""

    def test_no_ac_dir_exits_zero(self) -> None:
        """Hook exits 0 when no docs/acceptance-criteria/ directory exists."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Do not create the AC directory.
            result = _run_hook(root)
        self.assertEqual(result.returncode, 0, msg=result.stderr)


class TestOriginAgentOptional(unittest.TestCase):
    """AC YAML without origin_agent should pass validation (field is optional)."""

    def test_origin_agent_optional(self) -> None:
        """A valid AC YAML without origin_agent exits 0 (field is optional)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "FIN-001.yaml", _VALID_AC_YAML)
            result = _run_hook(root)
        self.assertEqual(result.returncode, 0, msg=result.stderr)


class TestOriginAgentValidString(unittest.TestCase):
    """AC YAML with a valid origin_agent string should pass validation."""

    def test_origin_agent_valid_string(self) -> None:
        """A YAML file with origin_agent: business-analyst exits 0."""
        content = textwrap.dedent("""\
            id: FIN-001
            title: "With origin agent"
            component: finalize
            status: active
            created_by: "tickets/test.md"
            criteria: |
              Given something
              When something
              Then something
            priority: medium
            readiness: draft
            origin_agent: "business-analyst"
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "FIN-001.yaml", content)
            result = _run_hook(root)
        self.assertEqual(result.returncode, 0, msg=result.stderr)


class TestOriginAgentEmptyStringBlocked(unittest.TestCase):
    """AC YAML with origin_agent: "" should fail validation (minLength: 1)."""

    def test_origin_agent_empty_string_blocked(self) -> None:
        """A YAML file with origin_agent: empty string exits 1 (minLength violation)."""
        content = textwrap.dedent("""\
            id: FIN-001
            title: "Empty origin agent"
            component: finalize
            status: active
            created_by: "tickets/test.md"
            criteria: |
              Given something
              When something
              Then something
            origin_agent: ""
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "FIN-001.yaml", content)
            result = _run_hook(root)
        self.assertEqual(result.returncode, 1)


class TestOriginAgentHistoricalValuePasses(unittest.TestCase):
    """AC YAML with a historical origin_agent value (e.g. business-analyst-v2)
    should pass validation — origin_agent is a free-form provenance string and
    must NOT be validated against the current agent registry (ACD-1100f-1).
    """

    def test_origin_agent_historical_value_passes(self) -> None:
        # covers: ACD-1100f-1
        """A YAML file with origin_agent: business-analyst-v2 exits 0.

        business-analyst-v2 is a now-deleted agent whose name appears in
        historical AC files. The schema accepts any non-empty string for
        origin_agent; registry membership is irrelevant.
        """
        content = textwrap.dedent("""\
            id: FIN-001
            title: "Historical origin agent"
            component: finalize
            status: active
            created_by: "tickets/test.md"
            criteria: |
              Given something
              When something
              Then something
            priority: medium
            readiness: draft
            origin_agent: "business-analyst-v2"
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "FIN-001.yaml", content)
            result = _run_hook(root)
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                f"origin_agent: business-analyst-v2 should be accepted as a valid "
                f"historical provenance string. Stderr: {result.stderr}"
            ),
        )
        self.assertEqual(
            result.stderr,
            "",
            msg=(
                "No error or warning should be emitted for a historical "
                f"origin_agent value. Stderr: {result.stderr}"
            ),
        )


class TestOriginAgentAllHistoricalValuePass(unittest.TestCase):
    """Parametrised edge-case tests for all seven historical origin_agent values
    enumerated in AC ACD-1100f-1-i.

    origin_agent is a free-form provenance string. The schema validator MUST
    accept every non-empty string regardless of whether the value corresponds to
    an agent that is currently registered, deleted, or has been renamed.
    No data migration or rewrite of existing origin_agent values may occur during
    a v2.0 upgrade.
    """

    # Seven representative historical values from ACD-1100f-1-i criteria.
    _HISTORICAL_VALUES = [
        "business-analyst",      # v1 name, now reused for promoted v3
        "business-analyst-v2",   # deleted agent
        "business-analyst-v3",   # old v3 name, now canonical as "business-analyst"
        "create-ticket",         # deleted agent
        "refinement",            # deleted agent
        "BrainCandy",            # human author
        "ticket-wiring",         # still-active workflow
    ]

    def _make_ac_yaml(self, origin_agent_value: str) -> str:
        """Return a minimal valid AC YAML string with the given origin_agent value.

        Args:
            origin_agent_value: The string to use as the origin_agent field value.

        Returns:
            YAML content string suitable for writing to a temporary file.
        """
        return textwrap.dedent(f"""\
            id: FIN-001
            title: "Historical origin_agent edge case"
            component: finalize
            status: active
            created_by: "tickets/test.md"
            criteria: |
              Given something
              When something
              Then something
            priority: medium
            readiness: draft
            origin_agent: "{origin_agent_value}"
        """)

    def test_business_analyst_passes(self) -> None:
        # covers: ACD-1100f-1-i
        """origin_agent: business-analyst (v1 name, now reused for v3) exits 0."""
        value = "business-analyst"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "FIN-001.yaml", self._make_ac_yaml(value))
            result = _run_hook(root)
        self.assertEqual(
            result.returncode,
            0,
            msg=f"origin_agent: {value!r} must be accepted as a free-form string. Stderr: {result.stderr}",
        )

    def test_business_analyst_v2_passes(self) -> None:
        # covers: ACD-1100f-1-i
        """origin_agent: business-analyst-v2 (deleted agent) exits 0."""
        value = "business-analyst-v2"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "FIN-001.yaml", self._make_ac_yaml(value))
            result = _run_hook(root)
        self.assertEqual(
            result.returncode,
            0,
            msg=f"origin_agent: {value!r} must be accepted as a free-form string. Stderr: {result.stderr}",
        )

    def test_business_analyst_v3_passes(self) -> None:
        # covers: ACD-1100f-1-i
        """origin_agent: business-analyst-v3 (old v3 name) exits 0."""
        value = "business-analyst-v3"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "FIN-001.yaml", self._make_ac_yaml(value))
            result = _run_hook(root)
        self.assertEqual(
            result.returncode,
            0,
            msg=f"origin_agent: {value!r} must be accepted as a free-form string. Stderr: {result.stderr}",
        )

    def test_create_ticket_passes(self) -> None:
        # covers: ACD-1100f-1-i
        """origin_agent: create-ticket (deleted agent) exits 0."""
        value = "create-ticket"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "FIN-001.yaml", self._make_ac_yaml(value))
            result = _run_hook(root)
        self.assertEqual(
            result.returncode,
            0,
            msg=f"origin_agent: {value!r} must be accepted as a free-form string. Stderr: {result.stderr}",
        )

    def test_refinement_passes(self) -> None:
        # covers: ACD-1100f-1-i
        """origin_agent: refinement (deleted agent) exits 0."""
        value = "refinement"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "FIN-001.yaml", self._make_ac_yaml(value))
            result = _run_hook(root)
        self.assertEqual(
            result.returncode,
            0,
            msg=f"origin_agent: {value!r} must be accepted as a free-form string. Stderr: {result.stderr}",
        )

    def test_brain_candy_passes(self) -> None:
        # covers: ACD-1100f-1-i
        """origin_agent: BrainCandy (human author) exits 0."""
        value = "BrainCandy"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "FIN-001.yaml", self._make_ac_yaml(value))
            result = _run_hook(root)
        self.assertEqual(
            result.returncode,
            0,
            msg=f"origin_agent: {value!r} must be accepted as a free-form string. Stderr: {result.stderr}",
        )

    def test_ticket_wiring_passes(self) -> None:
        # covers: ACD-1100f-1-i
        """origin_agent: ticket-wiring (still-active workflow) exits 0."""
        value = "ticket-wiring"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "FIN-001.yaml", self._make_ac_yaml(value))
            result = _run_hook(root)
        self.assertEqual(
            result.returncode,
            0,
            msg=f"origin_agent: {value!r} must be accepted as a free-form string. Stderr: {result.stderr}",
        )

    def test_no_migration_occurs_for_historical_values(self) -> None:
        # covers: ACD-1100f-1-i
        """Validation of AC files with historical origin_agent values leaves
        the file content unchanged — no data migration or rewrite occurs.
        """
        value = "business-analyst-v2"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original_content = self._make_ac_yaml(value)
            ac_path = _write_ac_file(root, "FIN-001.yaml", original_content)
            result = _run_hook(root)
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            # File content must be byte-for-byte identical after validation.
            after_content = ac_path.read_text(encoding="utf-8")
        self.assertEqual(
            original_content,
            after_content,
            msg=(
                "check_ac_schema.py must not rewrite origin_agent values "
                "during validation (no migration allowed)."
            ),
        )


class TestImplementsPatternWithEmptyCriteria(unittest.TestCase):
    """AC with implements_pattern and a plain-text criteria placeholder must pass.

    When an AC inherits all behavior from a reusable pattern via implements_pattern,
    the criteria field may contain a plain-text placeholder instead of a full
    Given/When/Then scenario. The schema validator must accept this form.

    See: ACS-500b-1-i, ADR-007 §Pattern-inherited ACs.
    """

    def test_implements_pattern_with_plain_text_criteria_passes(self) -> None:
        # covers: ACS-500b-1-i
        """An AC with implements_pattern set and plain-text criteria exits 0.

        The schema validator must accept a non-Gherkin criteria string when
        implements_pattern is present, because the effective behavior is
        entirely derived from the referenced pattern.
        """
        content = textwrap.dedent("""\
            id: PAG-001
            title: "Users list page — standard CRUD table (PTN-001)"
            component: users-ui
            status: active
            created_by: "tickets/test.md"
            criteria: "No page-specific behavior — all behavior inherited from pattern."
            implements_pattern: "PTN-001"
            pattern_bindings:
              entity_type: "users"
              columns:
                - "name"
                - "email"
            priority: medium
            readiness: draft
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "PAG-001.yaml", content)
            result = _run_hook(root)
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "AC with implements_pattern and plain-text criteria placeholder "
                f"must be accepted by the schema validator. Stderr: {result.stderr}"
            ),
        )

    def test_implements_pattern_null_with_gherkin_criteria_passes(self) -> None:
        # covers: ACS-500b-1-i
        """An AC with implements_pattern: null and full Gherkin criteria exits 0.

        The implements_pattern field is optional. When absent or null, the AC
        must still pass if criteria contains valid Gherkin (standard case).
        """
        content = textwrap.dedent("""\
            id: PAG-002
            title: "Login page — standard Gherkin"
            component: users-ui
            status: active
            created_by: "tickets/test.md"
            criteria: |
              Given the user is on the login page
              When they submit valid credentials
              Then they are redirected to the dashboard
            implements_pattern: null
            priority: medium
            readiness: draft
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "PAG-002.yaml", content)
            result = _run_hook(root)
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "AC with implements_pattern: null and Gherkin criteria must pass. "
                f"Stderr: {result.stderr}"
            ),
        )

    def test_implements_pattern_with_pattern_bindings_passes(self) -> None:
        # covers: ACS-500b-1-i
        """An AC with implements_pattern and pattern_bindings exits 0.

        The pattern_bindings object field must be accepted by the schema
        validator as an optional object field with unrestricted keys.
        """
        content = textwrap.dedent("""\
            id: PAG-003
            title: "Products list page — inherits PTN-001"
            component: products-ui
            status: active
            created_by: "tickets/test.md"
            criteria: "No page-specific behavior — all behavior inherited from pattern."
            implements_pattern: "PTN-001"
            pattern_bindings:
              entity_type: "products"
              columns:
                - "sku"
                - "name"
                - "price"
              filters_enabled: true
            priority: low
            readiness: draft
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "PAG-003.yaml", content)
            result = _run_hook(root)
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "AC with implements_pattern, pattern_bindings, and plain-text "
                f"criteria must pass schema validation. Stderr: {result.stderr}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
