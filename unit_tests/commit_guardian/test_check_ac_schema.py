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
    / "scripts"
    / "commit_guardian"
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
    try:
        return subprocess.run(
            [sys.executable, str(HOOK_SCRIPT)],
            env=env,
            capture_output=True,
            text=True,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        print(f"hook subprocess error: {exc}", file=sys.stderr)
        raise


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


class TestDeprecatedPatternReferenceBlocked(unittest.TestCase):
    """Consuming AC that implements_pattern referencing a deprecated pattern AC exits 1."""

    def test_deprecated_pattern_reference_blocked(self) -> None:
        """A consuming AC referencing a deprecated pattern exits 1 with the canonical error.

        Writes two AC YAML files into a temporary directory: a pattern AC with
        ``status: deprecated`` and a consuming AC with ``implements_pattern``
        pointing to it. Runs the hook and asserts that the process exits 1 and
        that stderr contains the canonical error string from ACS-500a-3-ii.
        """
        pattern_content = textwrap.dedent("""\
            id: PTN-001
            title: "Deprecated pattern"
            component: finalize
            status: deprecated
            created_by: "tickets/test.md"
            criteria: |
              Given something
              When something
              Then something
            priority: medium
            readiness: draft
        """)
        consuming_content = textwrap.dedent("""\
            id: FIN-010
            title: "Consuming AC referencing deprecated pattern"
            component: finalize
            status: active
            created_by: "tickets/test.md"
            criteria: |
              Given something
              When something
              Then something
            priority: medium
            readiness: draft
            implements_pattern: "PTN-001"
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "PTN-001.yaml", pattern_content)
            consuming_path = _write_ac_file(root, "FIN-010.yaml", consuming_content)
            result = _run_hook(root)
        self.assertEqual(result.returncode, 1, msg=result.stderr)
        self.assertIn(
            "implements_pattern references deprecated pattern PTN-001",
            result.stderr,
        )
        self.assertIn(
            "use its successor (see PTN-001 superseded_by field) or remove the reference",
            result.stderr,
        )
        self.assertIn(str(consuming_path.name), result.stderr)


class TestActivePatternReferenceAllowed(unittest.TestCase):
    """Consuming AC that implements_pattern referencing an active pattern AC exits 0."""

    def test_active_pattern_reference_passes(self) -> None:
        """A consuming AC referencing an active pattern exits 0 with no deprecated-pattern error.

        Writes two AC YAML files: a pattern AC with ``status: active`` and a
        consuming AC with ``implements_pattern`` pointing to it. Runs the hook
        and asserts that the process exits 0 and that no deprecated-pattern
        error appears in stderr.
        """
        pattern_content = textwrap.dedent("""\
            id: PTN-002
            title: "Active pattern"
            component: finalize
            status: active
            created_by: "tickets/test.md"
            criteria: |
              Given something
              When something
              Then something
            priority: medium
            readiness: draft
        """)
        consuming_content = textwrap.dedent("""\
            id: FIN-011
            title: "Consuming AC referencing active pattern"
            component: finalize
            status: active
            created_by: "tickets/test.md"
            criteria: |
              Given something
              When something
              Then something
            priority: medium
            readiness: draft
            implements_pattern: "PTN-002"
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "PTN-002.yaml", pattern_content)
            _write_ac_file(root, "FIN-011.yaml", consuming_content)
            result = _run_hook(root)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertNotIn("references deprecated pattern", result.stderr)


class TestDeprecatedPatternReferenceNamesConsumingFilePath(unittest.TestCase):
    """Error output for a deprecated-pattern reference includes the consuming file path."""

    def test_deprecated_pattern_error_names_consuming_path(self) -> None:
        """The error message for a deprecated-pattern reference names the consuming AC path.

        Verifies the consuming file path (FIN-012.yaml) appears in the hook
        stderr when the consuming AC's implements_pattern points to a deprecated
        pattern AC (PTN-003).
        """
        pattern_content = textwrap.dedent("""\
            id: PTN-003
            title: "Another deprecated pattern"
            component: finalize
            status: deprecated
            created_by: "tickets/test.md"
            criteria: |
              Given something
              When something
              Then something
            priority: medium
            readiness: draft
        """)
        consuming_content = textwrap.dedent("""\
            id: FIN-012
            title: "Consuming AC for path-naming test"
            component: finalize
            status: active
            created_by: "tickets/test.md"
            criteria: |
              Given something
              When something
              Then something
            priority: medium
            readiness: draft
            implements_pattern: "PTN-003"
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "PTN-003.yaml", pattern_content)
            consuming_path = _write_ac_file(root, "FIN-012.yaml", consuming_content)
            result = _run_hook(root)
        self.assertEqual(result.returncode, 1, msg=result.stderr)
        # The error must name either the relative or absolute path of the consuming file.
        # The main loop uses relative paths; the function embeds the absolute path.
        # Either form satisfies the AC requirement.
        self.assertTrue(
            str(consuming_path.name) in result.stderr
            or str(consuming_path) in result.stderr,
            msg=(
                f"Expected consuming file path ({consuming_path.name} or "
                f"{consuming_path}) in stderr:\n{result.stderr}"
            ),
        )


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
        # NOTE: The canonical check_ac_schema.py runs git diff --cached to find
        # staged modified AC files (Phase 2 implements_pattern preservation check).
        # When the hook is invoked in a test against a temp dir, git diff --cached
        # may return real staged files from the worktree; those files do not exist
        # in the temp dir, so the hook emits non-fatal WARNING messages to stderr.
        # These warnings do NOT affect the exit code (hook exits 0). We only assert
        # returncode == 0 here; asserting stderr == "" would be a false constraint
        # that breaks in any repo that has staged AC files at test time.
        # See: ticket TICKET-20260618-RemoveDeprecatedCommitGuardianTree Fix 2.


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


class TestFailOpenOnInternalError(unittest.TestCase):
    """AC1: Hook exits 0 when it encounters an unexpected internal error.

    The standalone templates version does not make git subprocess calls, so
    we trigger an unexpected exception via a malformed schema file and verify
    the __main__ exception handler catches it, exits 0, and writes a diagnostic.
    """

    def test_valid_ac_with_schema_present_exits_zero(self) -> None:
        # covers: ACS-500f-1-i (AC1 — normal path: no blocking on valid input)
        """Hook exits 0 when AC file is valid and schema is present.

        With a well-formed schema and a valid AC file the hook must exit 0.
        This confirms the hook does not incorrectly flag valid input as an error.
        """
        import os

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "FIN-001.yaml", _VALID_AC_YAML)
            env = os.environ.copy()
            env["HOOK_ROOT"] = str(root)
            result = subprocess.run(
                [sys.executable, str(HOOK_SCRIPT)],
                env=env,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_hook_exits_zero_when_no_ac_dir(self) -> None:
        # covers: ACS-500f-1-i (AC2 — exit 0 when no relevant staged files)
        """Hook exits 0 when docs/acceptance-criteria/ does not exist.

        When the AC directory is absent, _find_ac_files() returns [] and
        main() returns 0. This is the canonical no-relevant-staged-files path.
        The hook must not block the commit.
        """
        import os

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # No docs/acceptance-criteria/ directory.
            env = os.environ.copy()
            env["HOOK_ROOT"] = str(root)
            result = subprocess.run(
                [sys.executable, str(HOOK_SCRIPT)],
                env=env,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0, msg=result.stderr)


class TestFailOpenOnNoStagedRelevantFiles(unittest.TestCase):
    """AC2: Hook exits 0 when no staged AC files violate the schema.

    These tests verify the pass-through path: valid AC files present,
    no schema violations, no implements_pattern preservation issue.
    """

    def test_valid_ac_no_implements_pattern_exits_zero(self) -> None:
        # covers: ACS-500f-1-i (AC2 — no staged file has implements_pattern)
        """AC YAML with no implements_pattern field and valid schema exits 0.

        When no staged AC file has an implements_pattern field and no AC file
        violates the store schema, the hook must exit 0 and not block the commit.
        """
        import os

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "FIN-001.yaml", _VALID_AC_YAML)
            env = os.environ.copy()
            env["HOOK_ROOT"] = str(root)
            result = subprocess.run(
                [sys.executable, str(HOOK_SCRIPT)],
                env=env,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_multiple_valid_acs_no_implements_pattern_exits_zero(self) -> None:
        # covers: ACS-500f-1-i (AC2 — no staged files with implements_pattern)
        """Multiple valid AC YAML files with no implements_pattern exits 0.

        When several AC files exist and none violates the schema or has an
        implements_pattern field, the hook must exit 0 without blocking.
        """
        import os

        content_2 = textwrap.dedent("""\
            id: FIN-002
            title: "Second valid criterion"
            component: finalize
            status: active
            created_by: "tickets/test.md"
            criteria: |
              Given a second scenario
              When it validates
              Then it passes
            priority: low
            readiness: draft
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "FIN-001.yaml", _VALID_AC_YAML)
            _write_ac_file(root, "FIN-002.yaml", content_2)
            env = os.environ.copy()
            env["HOOK_ROOT"] = str(root)
            result = subprocess.run(
                [sys.executable, str(HOOK_SCRIPT)],
                env=env,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0, msg=result.stderr)


class TestMainBlockExceptionHandler(unittest.TestCase):
    """AC1: The __main__ exception handler exits 0 and writes a diagnostic to stderr.

    This test verifies that if main() raises an unhandled exception, the outer
    try/except in the __main__ block catches it, prints a diagnostic to stderr
    (containing '[check-ac-schema]'), and exits 0 rather than propagating the
    error and blocking the commit.
    """

    def test_hook_module_main_exception_exits_zero_with_diagnostic(self) -> None:
        # covers: ACS-500f-1-i (AC1 — unexpected internal error → fail-open)
        """Malformed JSON schema triggers the fail-open __main__ exception handler.

        We force an unexpected exception inside the hook by creating a malformed
        config/ac_store_schema.json. The _load_schema() function calls json.load()
        without catching json.JSONDecodeError (a ValueError subclass). The error
        propagates out of _load_schema() and out of main() to the __main__
        exception handler, which must exit 0 and write a diagnostic to stderr
        containing '[check-ac-schema]'.

        This is the canonical AC1 fail-open scenario: the hook encounters an
        unexpected internal error and must NOT block the commit.
        """
        import os

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Malformed JSON causes json.JSONDecodeError in _load_schema(),
            # which propagates to the __main__ exception handler.
            config_dir = root / "config"
            config_dir.mkdir(parents=True)
            (config_dir / "ac_store_schema.json").write_text(
                "{ invalid json !!!", encoding="utf-8"
            )
            ac_dir = root / "docs" / "acceptance-criteria"
            ac_dir.mkdir(parents=True)
            (ac_dir / "FIN-001.yaml").write_text(_VALID_AC_YAML, encoding="utf-8")
            env = os.environ.copy()
            env["HOOK_ROOT"] = str(root)
            result = subprocess.run(
                [sys.executable, str(HOOK_SCRIPT)],
                env=env,
                capture_output=True,
                text=True,
            )
        # json.JSONDecodeError propagates out of _load_schema(), caught by __main__:
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "Malformed JSON schema must trigger the fail-open __main__ exception "
                f"handler (exit 0). Stderr: {result.stderr}"
            ),
        )
        # The diagnostic must identify the hook and the error.
        self.assertIn(
            "[check-ac-schema]",
            result.stderr,
            msg=f"Diagnostic must name the hook. Stderr: {result.stderr}",
        )


class TestMalformedIdRejectedAfterWidening(unittest.TestCase):
    """Widened schema still rejects AC records with malformed ID formats.

    After adding pattern_slots to the schema, the id field pattern must
    remain unchanged — lowercase prefixes, underscore separators, and
    trailing empty leaf segments must all be rejected.

    covers: ACS-500f-3-i (AC1 — malformed id rejected after widening)
    """

    def _make_content_with_id(self, bad_id: str) -> str:
        """Return an otherwise-valid AC YAML with the given id substituted.

        Args:
            bad_id: The malformed id string to inject.

        Returns:
            YAML content string suitable for writing to a temporary file.
        """
        return textwrap.dedent(f"""\
            id: {bad_id}
            title: "Malformed ID test"
            component: finalize
            status: active
            created_by: "tickets/test.md"
            criteria: |
              Given something
              When something
              Then something
            priority: medium
            readiness: draft
        """)

    def test_lowercase_prefix_rejected(self) -> None:
        # covers: ACS-500f-3-i
        """id: acs-500 (lowercase prefix) is rejected after schema widening."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "bad-id.yaml", self._make_content_with_id("acs-500"))
            result = _run_hook(root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("id", result.stderr)

    def test_underscore_separator_rejected(self) -> None:
        # covers: ACS-500f-3-i
        """id: ACS_500 (underscore separator) is rejected after schema widening."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "bad-id.yaml", self._make_content_with_id("ACS_500"))
            result = _run_hook(root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("id", result.stderr)

    def test_trailing_empty_leaf_segment_rejected(self) -> None:
        # covers: ACS-500f-3-i
        """id: ACS-500a- (trailing empty leaf segment) is rejected after schema widening."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "bad-id.yaml", self._make_content_with_id("ACS-500a-"))
            result = _run_hook(root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("id", result.stderr)


class TestUnknownFieldRejectedAfterWidening(unittest.TestCase):
    """Widened schema still rejects AC records with unknown/misspelled fields.

    Adding pattern_slots to the schema must NOT loosen additionalProperties:
    false — unknown keys like 'critera' (misspelled) or 'foo_bar' (invented)
    must still be rejected.

    covers: ACS-500f-3-i (AC2 — unknown field rejected; widening does not loosen additionalProperties)
    """

    def test_misspelled_criteria_field_rejected(self) -> None:
        # covers: ACS-500f-3-i
        """AC with 'critera' (missing 'i') as an extra field is rejected after schema widening."""
        content = textwrap.dedent("""\
            id: FIN-001
            title: "Misspelled field test"
            component: finalize
            status: active
            created_by: "tickets/test.md"
            criteria: |
              Given something
              When something
              Then something
            priority: medium
            readiness: draft
            critera: "misspelled field"
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "FIN-001.yaml", content)
            result = _run_hook(root)
        self.assertEqual(result.returncode, 1)

    def test_invented_key_rejected(self) -> None:
        # covers: ACS-500f-3-i
        """AC with 'foo_bar' (invented key) is rejected after schema widening."""
        content = textwrap.dedent("""\
            id: FIN-001
            title: "Invented key test"
            component: finalize
            status: active
            created_by: "tickets/test.md"
            criteria: |
              Given something
              When something
              Then something
            priority: medium
            readiness: draft
            foo_bar: "invented key"
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "FIN-001.yaml", content)
            result = _run_hook(root)
        self.assertEqual(result.returncode, 1)


class TestPatternSlotsAcceptedAfterWidening(unittest.TestCase):
    """Widened schema accepts pattern_slots while still rejecting other unknown fields.

    This is the positive guard: pattern_slots is now a first-class schema field
    and must be admitted. Any other unknown field (not pattern_slots) must still
    be rejected — ensuring the widening is targeted, not open-ended.

    covers: ACS-500f-3-i (positive guard — pattern_slots admitted; widening is not open-ended)
    """

    def test_pattern_slots_accepted(self) -> None:
        # covers: ACS-500f-3-i
        """AC with pattern_slots: ['{entity_type}', '{columns}'] exits 0 after schema widening."""
        content = textwrap.dedent("""\
            id: PTN-010
            title: "Pattern AC with slots"
            component: finalize
            status: active
            created_by: "tickets/test.md"
            criteria: |
              Given a {entity_type} list
              When the user views the {columns}
              Then the data is displayed
            priority: medium
            readiness: draft
            pattern_slots:
              - "{entity_type}"
              - "{columns}"
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "PTN-010.yaml", content)
            result = _run_hook(root)
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "pattern_slots is now a first-class schema field and must be accepted. "
                f"Stderr: {result.stderr}"
            ),
        )


class TestMissingRequiredFieldAfterWidening(unittest.TestCase):
    """Widened schema still rejects AC records missing a required field.

    After adding pattern_slots, the existing required fields (id, title,
    component, status, created_by, criteria, readiness, priority) must all
    still be enforced. This class duplicates the spirit of TestMissingRequiredField
    with an explicit traceability marker for ACS-500f-3-i.

    covers: ACS-500f-3-i (AC3 — missing required field still rejected after widening)
    """

    def test_missing_criteria_rejected_after_widening(self) -> None:
        # covers: ACS-500f-3-i
        """AC missing 'criteria' is still rejected even after the schema was widened to admit pattern_slots."""
        content = textwrap.dedent("""\
            id: FIN-001
            title: "Missing criteria after widening"
            component: finalize
            status: active
            created_by: "tickets/test.md"
            priority: medium
            readiness: draft
            pattern_slots:
              - "{entity_type}"
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "FIN-001.yaml", content)
            result = _run_hook(root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("criteria", result.stderr)


if __name__ == "__main__":
    unittest.main()
