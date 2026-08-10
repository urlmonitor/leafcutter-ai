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
    components:
      - finalize
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

    Sets HOOK_TEST_STAGED_FILES to all .yaml files found under
    root/docs/acceptance-criteria/ so that the hook treats them as staged.
    This preserves the original test behaviour (validate every file written
    into the temp directory) while exercising the staged-scope code path
    added in TICKET-20260622-AcSchemaHookStagedScope (AC-6).

    Args:
        root: Temporary directory that acts as the repository root.

    Returns:
        CompletedProcess with returncode, stdout, and stderr captured.
    """
    import os

    env = os.environ.copy()
    env["HOOK_ROOT"] = str(root)

    # Collect all .yaml files in the temp AC store so the hook's Phase 1
    # validates them all (mirrors the pre-staged-scope behaviour).
    ac_dir = root / "docs" / "acceptance-criteria"
    yaml_files: list[str] = []
    if ac_dir.is_dir():
        yaml_files = [
            str(p) for p in sorted(ac_dir.rglob("*.yaml"))
            if p.name != "index.yaml"
        ]
    env["HOOK_TEST_STAGED_FILES"] = os.pathsep.join(yaml_files)

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
            components:
              - finalize
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
            components:
              - finalize
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
            components:
              - finalize
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
            components:
              - finalize
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
            components:
              - finalize
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
            components:
              - finalize
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
            components:
              - finalize
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
            components:
              - finalize
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
            components:
              - finalize
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
            components:
              - finalize
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


class TestSchemaAuthoritativeOverManual(unittest.TestCase):
    """GE-112: JSON Schema is authoritative; validate_manually() must NOT run on jsonschema success path.

    The bug: in _validate_file(), the `if not errors: errors.extend(validate_manually(data))`
    block runs validate_manually() whenever jsonschema PASSES (errors empty), instead of
    only as a fallback when jsonschema was unavailable.  validate_manually() enforces
    stricter rules than the authoritative config/ac_store_schema.json:
      - REQUIRED_FIELDS includes 'created_by' (the JSON Schema does NOT require it)
      - _ID_REGEX is ^[A-Z]{2,6}-[0-9]{3}$ (rejects hierarchical ids like ACS-300g-1)

    These tests assert the POST-FIX correct behaviour: a file that satisfies
    config/ac_store_schema.json must exit 0 even if it omits 'created_by' and uses a
    hierarchical id that the narrow manual regex rejects.

    Both tests FAIL against the current (unfixed) check_ac_schema.py — which is the
    intended red state for the TDD phase.
    """

    def test_ac1_hierarchical_id_without_created_by_passes_when_schema_valid(self) -> None:
        # covers: GE-112
        """AC-1 (GE-112): An AC YAML valid per JSON Schema but omitting `created_by` and
        using a hierarchical id (e.g. ACS-300g-1) must exit 0 when jsonschema is available.

        This test MUST FAIL against unmodified check_ac_schema.py because:
          - validate_manually() runs on the jsonschema-success path (if not errors: …)
          - validate_manually() requires 'created_by' → emits "missing required field: 'created_by'"
          - validate_manually() rejects 'ACS-300g-1' against ^[A-Z]{2,6}-[0-9]{3}$ → id error

        The fix requires validate_manually() to run ONLY as a fallback when jsonschema
        did not actually run (schema is None or jsonschema not importable).

        To make this test green:
          Change the `if not errors:` guard in _validate_file() so that validate_manually()
          is gated on schema being None (or jsonschema unavailable), NOT on jsonschema
          passing cleanly.
        """
        # Deliberately omit 'created_by'; use a hierarchical id that the JSON Schema
        # allows but that the narrow manual regex ^[A-Z]{2,6}-[0-9]{3}$ rejects.
        content = textwrap.dedent("""\
            id: ACS-300g-1
            title: "Schema-valid AC with hierarchical id and no created_by"
            component: ac-store
            components:
              - ac_store
            status: active
            criteria: |
              Given a hierarchical AC id
              When check_ac_schema.py validates the file with jsonschema available
              Then the file passes and the hook does not reject it
            priority: medium
            readiness: draft
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # _write_ac_file copies config/ac_store_schema.json so jsonschema validation
            # is active.  The schema does NOT list 'created_by' under required[], and
            # its id pattern allows hierarchical forms like ACS-300g-1.
            _write_ac_file(root, "ACS-300g-1.yaml", content)
            result = _run_hook(root)
        # Phase 2 (git diff --cached) may emit non-fatal WARNING lines to stderr
        # for files that exist in the real worktree but not in the temp dir.
        # Those warnings do NOT change the exit code — assert only on returncode.
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "An AC YAML file that satisfies config/ac_store_schema.json (hierarchical "
                "id ACS-300g-1, no created_by field) must exit 0.  The hook currently "
                "rejects it because validate_manually() runs on the jsonschema SUCCESS "
                "path (if not errors: …) and applies stricter rules than the schema.  "
                f"Stderr: {result.stderr}"
            ),
        )


# ---------------------------------------------------------------------------
# NEW TESTS — AC-1 through AC-6 (staged-scope rework)
# These tests are RED stubs. They will FAIL until python-coder implements the
# HOOK_TEST_STAGED_FILES seam in check_ac_schema.py and scopes Phase 1
# validation to staged files only.
#
# Staging simulation convention (AC-6):
#   Set env var HOOK_TEST_STAGED_FILES to a pathsep-separated list of
#   absolute (or HOOK_ROOT-relative) paths.  The hook treats those paths as
#   the staged AC files for Phase 1 validation, exactly as
#   HOOK_TEST_FILES_MODIFIED already does for Phase 2.
#   When HOOK_TEST_STAGED_FILES is set, the hook MUST NOT fall back to
#   _find_ac_files() for Phase 1.
# ---------------------------------------------------------------------------


def _run_hook_with_staged(root: Path, staged_paths: list[Path]) -> "subprocess.CompletedProcess[str]":
    """Run check_ac_schema.py with HOOK_TEST_STAGED_FILES set to simulate staging.

    Args:
        root: Temporary directory acting as the repository root.
        staged_paths: Absolute paths that should be treated as staged AC files.

    Returns:
        CompletedProcess with returncode, stdout, and stderr captured.
    """
    import os

    env = os.environ.copy()
    env["HOOK_ROOT"] = str(root)
    env["HOOK_TEST_STAGED_FILES"] = os.pathsep.join(str(p) for p in staged_paths)
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


class TestAC1UnstagedFilesNotValidated(unittest.TestCase):
    """AC-1: Phase 1 must NOT validate AC files that are present in the store
    but are NOT staged.

    A store file with a schema violation must NOT cause exit 1 when that file
    is not listed in HOOK_TEST_STAGED_FILES.  Before the fix, _find_ac_files()
    scans the whole store and validates everything — so this test is RED until
    python-coder scopes Phase 1 to staged files.
    """

    def test_unstaged_invalid_file_does_not_block_commit(self) -> None:
        # covers: AC-1 (TICKET-20260622-AcSchemaHookStagedScope)
        """An AC file with a schema violation that is NOT staged must not block the commit.

        The test places a schema-violating file (missing criteria) in the AC store
        but does NOT include it in HOOK_TEST_STAGED_FILES.  A different, valid file
        IS listed as staged.  The hook must exit 0 because the violating file is
        unstaged.

        FAILS before the fix: the current implementation calls _find_ac_files()
        for Phase 1 which validates ALL files in the store, not just staged ones.
        """
        violating_content = textwrap.dedent("""\
            id: FIN-001
            title: "Missing criteria — unstaged"
            component: finalize
            status: active
            created_by: "tickets/test.md"
        """)
        valid_content = textwrap.dedent("""\
            id: FIN-002
            title: "Valid staged file"
            component: finalize
            components:
              - finalize
            status: active
            created_by: "tickets/test.md"
            criteria: |
              Given something
              When something
              Then something
            priority: medium
            readiness: draft
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Violating file lives in the store but is NOT staged.
            _write_ac_file(root, "FIN-001.yaml", violating_content)
            # Valid file IS staged.
            staged_path = _write_ac_file(root, "FIN-002.yaml", valid_content)
            result = _run_hook_with_staged(root, [staged_path])
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "The violating file (FIN-001.yaml) is NOT staged, so Phase 1 must "
                "not validate it. Only staged files should be checked. "
                f"Stderr: {result.stderr}"
            ),
        )

    def test_unstaged_file_with_invalid_status_does_not_block(self) -> None:
        # covers: AC-1 (TICKET-20260622-AcSchemaHookStagedScope)
        """An AC file with status: unknown that is NOT staged must not block the commit.

        FAILS before the fix: whole-store scan in Phase 1 validates the unstaged
        file and exits 1.
        """
        unstaged_bad = textwrap.dedent("""\
            id: FIN-003
            title: "Bad status — unstaged"
            component: finalize
            status: unknown
            created_by: "tickets/test.md"
            criteria: |
              Given something
              When something
              Then something
        """)
        valid_staged = textwrap.dedent("""\
            id: FIN-004
            title: "Valid staged"
            component: finalize
            components:
              - finalize
            status: active
            created_by: "tickets/test.md"
            criteria: |
              Given something
              When something
              Then something
            priority: medium
            readiness: draft
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "FIN-003.yaml", unstaged_bad)
            staged_path = _write_ac_file(root, "FIN-004.yaml", valid_staged)
            result = _run_hook_with_staged(root, [staged_path])
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "FIN-003.yaml has status: unknown but is NOT staged — Phase 1 must "
                "not validate it. "
                f"Stderr: {result.stderr}"
            ),
        )


class TestAC2StagedInvalidFileBlocksCommit(unittest.TestCase):
    """AC-2: A staged AC file that violates the schema must still block the commit
    (exit 1) with per-file error reporting.

    These tests use HOOK_TEST_STAGED_FILES to simulate a file being staged.
    They will be RED until python-coder wires up the HOOK_TEST_STAGED_FILES seam
    for Phase 1.
    """

    def test_staged_missing_criteria_blocks_commit(self) -> None:
        # covers: AC-2 (TICKET-20260622-AcSchemaHookStagedScope)
        """A staged AC file with missing 'criteria' exits 1 with an error mentioning criteria.

        FAILS before the fix: HOOK_TEST_STAGED_FILES is not yet a Phase 1 seam so
        the hook still scans the whole store — after the fix the behavior should be
        identical but driven via the staged list, not the whole store.
        """
        content = textwrap.dedent("""\
            id: FIN-010
            title: "Missing criteria — staged"
            component: finalize
            status: active
            created_by: "tickets/test.md"
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staged_path = _write_ac_file(root, "FIN-010.yaml", content)
            result = _run_hook_with_staged(root, [staged_path])
        self.assertEqual(result.returncode, 1)
        self.assertIn("criteria", result.stderr)

    def test_staged_invalid_status_blocks_commit(self) -> None:
        # covers: AC-2 (TICKET-20260622-AcSchemaHookStagedScope)
        """A staged AC file with status: unknown exits 1 mentioning the bad value.

        FAILS before the fix: HOOK_TEST_STAGED_FILES seam for Phase 1 not wired.
        """
        content = textwrap.dedent("""\
            id: FIN-011
            title: "Bad status — staged"
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
            staged_path = _write_ac_file(root, "FIN-011.yaml", content)
            result = _run_hook_with_staged(root, [staged_path])
        self.assertEqual(result.returncode, 1)
        self.assertIn("unknown", result.stderr)

    def test_staged_malformed_id_blocks_commit(self) -> None:
        # covers: AC-2 (TICKET-20260622-AcSchemaHookStagedScope)
        """A staged AC file with id: NOTVALID exits 1 mentioning the id error.

        FAILS before the fix: HOOK_TEST_STAGED_FILES seam for Phase 1 not wired.
        """
        content = textwrap.dedent("""\
            id: NOTVALID
            title: "Malformed id — staged"
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
            staged_path = _write_ac_file(root, "bad-id.yaml", content)
            result = _run_hook_with_staged(root, [staged_path])
        self.assertEqual(result.returncode, 1)
        self.assertIn("id", result.stderr)


class TestAC3NoStagedAcFilesExitsZero(unittest.TestCase):
    """AC-3: When no AC YAML file is staged, the hook must exit 0 immediately
    without scanning the store at all.

    These tests set HOOK_TEST_STAGED_FILES to empty-string (no files) and verify
    that even a store full of invalid files does not cause a failure.
    They will be RED until python-coder implements the staged-scope change.
    """

    def test_empty_staged_list_exits_zero_even_with_invalid_store(self) -> None:
        # covers: AC-3 (TICKET-20260622-AcSchemaHookStagedScope)
        """No staged AC files: exit 0 even when the store contains schema violations.

        We place an invalid file (missing criteria) in the store but pass an
        empty HOOK_TEST_STAGED_FILES.  The hook must exit 0.

        FAILS before the fix: the current hook scans the whole store regardless
        of what is staged (HOOK_TEST_STAGED_FILES is not yet a Phase 1 seam).
        """
        import os

        invalid_content = textwrap.dedent("""\
            id: FIN-020
            title: "Invalid — not staged"
            component: finalize
            status: active
            created_by: "tickets/test.md"
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "FIN-020.yaml", invalid_content)
            env = os.environ.copy()
            env["HOOK_ROOT"] = str(root)
            # Explicit empty string = no staged files.
            env["HOOK_TEST_STAGED_FILES"] = ""
            result = subprocess.run(
                [sys.executable, str(HOOK_SCRIPT)],
                env=env,
                capture_output=True,
                text=True,
            )
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "No AC YAML files are staged (HOOK_TEST_STAGED_FILES='').  "
                "The hook must exit 0 without scanning the store. "
                f"Stderr: {result.stderr}"
            ),
        )

    def test_hook_test_staged_files_unset_falls_back_to_git(self) -> None:
        # covers: AC-3 (TICKET-20260622-AcSchemaHookStagedScope — production path)
        """When HOOK_TEST_STAGED_FILES is absent, the hook queries git diff --cached.

        In a temp dir with no git repo the git call will fail gracefully and the
        hook must still exit 0 (no staged files found = no Phase 1 validation).
        This verifies AC-3 on the real git path and AC-5 (fail-open on git error).

        FAILS before the fix: without the staged-scope seam, _find_ac_files() runs
        unconditionally and validates the whole store.
        """
        invalid_content = textwrap.dedent("""\
            id: FIN-021
            title: "Invalid — no git repo"
            component: finalize
            status: active
            created_by: "tickets/test.md"
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "FIN-021.yaml", invalid_content)
            import os

            env = os.environ.copy()
            env["HOOK_ROOT"] = str(root)
            # Do NOT set HOOK_TEST_STAGED_FILES — production path.
            env.pop("HOOK_TEST_STAGED_FILES", None)
            # HOOK_NO_GIT skips only the Phase 2 field-preservation path today;
            # we intentionally do NOT set it here so the test exercises the real
            # git-diff-cached path failing gracefully.
            env.pop("HOOK_NO_GIT", None)
            result = subprocess.run(
                [sys.executable, str(HOOK_SCRIPT)],
                env=env,
                capture_output=True,
                text=True,
            )
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "In a non-git temp dir, git diff --cached fails gracefully → no "
                "staged files → Phase 1 must exit 0. "
                f"Stderr: {result.stderr}"
            ),
        )


class TestAC4CrossFilePatternChecksUseFullStore(unittest.TestCase):
    """AC-4: Cross-file pattern checks (deprecated-pattern reference, etc.) must
    continue to resolve referenced pattern ACs against the full on-disk store
    even when only a subset of files is staged.

    Only the set of files *validated* in Phase 1 is narrowed — the lookup index
    used by cross-file checks must NOT be narrowed.

    These tests will be RED until python-coder wires up HOOK_TEST_STAGED_FILES
    for Phase 1 while keeping the full-store lookup index for cross-file checks.
    """

    def test_staged_consuming_ac_can_find_unstaged_deprecated_pattern(self) -> None:
        # covers: AC-4 (TICKET-20260622-AcSchemaHookStagedScope)
        """A staged consuming AC that implements_pattern a deprecated (unstaged) pattern
        must still exit 1 with the deprecated-pattern error.

        The pattern AC (PTN-099) lives in the store but is NOT staged.
        The consuming AC (FIN-099) IS staged.
        Because the cross-file lookup index covers the full store, the hook must
        detect the deprecated reference and exit 1.

        FAILS before the fix: with HOOK_TEST_STAGED_FILES wired for Phase 1 but
        the lookup index correctly spanning the full store, this test should pass.
        Before that, the hook either exits 0 (does not validate the staged consuming
        file at all) or exits 1 for the wrong reason (whole-store scan picks up
        the deprecated reference, but the unit test cannot distinguish the scoping).
        The test is designed to be RED until both conditions hold simultaneously:
        (a) Phase 1 validates ONLY the staged consuming file, and
        (b) the cross-file lookup still resolves the unstaged pattern.
        """
        pattern_content = textwrap.dedent("""\
            id: PTN-099
            title: "Deprecated pattern — unstaged"
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
            id: FIN-099
            title: "Consuming AC referencing deprecated pattern — staged"
            component: finalize
            status: active
            created_by: "tickets/test.md"
            criteria: |
              Given something
              When something
              Then something
            priority: medium
            readiness: draft
            implements_pattern: "PTN-099"
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Pattern is NOT staged.
            _write_ac_file(root, "PTN-099.yaml", pattern_content)
            # Consuming file IS staged.
            staged_consuming = _write_ac_file(root, "FIN-099.yaml", consuming_content)
            result = _run_hook_with_staged(root, [staged_consuming])
        self.assertEqual(
            result.returncode,
            1,
            msg=(
                "The staged consuming file (FIN-099.yaml) implements_pattern a "
                "deprecated (unstaged) pattern. The cross-file lookup index must "
                "span the full store, so this must exit 1. "
                f"Stderr: {result.stderr}"
            ),
        )
        self.assertIn(
            "implements_pattern references deprecated pattern PTN-099",
            result.stderr,
            msg=f"Expected deprecated-pattern error in stderr: {result.stderr}",
        )

    def test_staged_consuming_ac_validates_against_unstaged_active_pattern(self) -> None:
        # covers: AC-4 (TICKET-20260622-AcSchemaHookStagedScope)
        """A staged consuming AC referencing an active (unstaged) pattern exits 0.

        The lookup index must find the active pattern even though it is not staged,
        so no deprecated-pattern error is emitted.

        FAILS before the fix: HOOK_TEST_STAGED_FILES not yet a Phase 1 seam.
        """
        pattern_content = textwrap.dedent("""\
            id: PTN-098
            title: "Active pattern — unstaged"
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
            id: FIN-098
            title: "Consuming AC referencing active pattern — staged"
            component: finalize
            components:
              - finalize
            status: active
            created_by: "tickets/test.md"
            criteria: |
              Given something
              When something
              Then something
            priority: medium
            readiness: draft
            implements_pattern: "PTN-098"
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "PTN-098.yaml", pattern_content)
            staged_consuming = _write_ac_file(root, "FIN-098.yaml", consuming_content)
            result = _run_hook_with_staged(root, [staged_consuming])
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "Staged consuming AC references an active (unstaged) pattern — "
                "must exit 0. "
                f"Stderr: {result.stderr}"
            ),
        )
        self.assertNotIn(
            "references deprecated pattern",
            result.stderr,
        )


class TestAC5FailOpenOnGitUnavailable(unittest.TestCase):
    """AC-5: The hook must remain fail-open when git is unavailable or
    git diff --cached fails.  A failure to enumerate staged files must
    NOT hard-block the commit.

    These tests verify that the staged-files lookup failing gracefully means
    Phase 1 skips (or runs with an empty staged list) rather than crashing.

    These tests will be RED until python-coder wires up the staged-scope
    change because the current code doesn't call git diff --cached for Phase 1
    at all — after the change it must fail gracefully when git is absent.
    """

    def test_hook_no_git_env_makes_phase1_use_empty_staged_list(self) -> None:
        # covers: AC-5 (TICKET-20260622-AcSchemaHookStagedScope)
        """When HOOK_NO_GIT is set, the staged-files lookup must return [] for
        Phase 1 (just as it does for Phase 2), so the hook exits 0 even when
        an invalid file sits in the store.

        FAILS before the fix: HOOK_NO_GIT currently guards only Phase 2 path;
        Phase 1 still scans the whole store and would exit 1 for the invalid file.
        After the fix, Phase 1 also respects HOOK_NO_GIT (or uses the empty staged
        list returned when git is unavailable).
        """
        import os

        invalid_content = textwrap.dedent("""\
            id: FIN-030
            title: "Invalid — git unavailable"
            component: finalize
            status: active
            created_by: "tickets/test.md"
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "FIN-030.yaml", invalid_content)
            env = os.environ.copy()
            env["HOOK_ROOT"] = str(root)
            env["HOOK_NO_GIT"] = "1"
            # Do NOT set HOOK_TEST_STAGED_FILES — production fail-open path.
            env.pop("HOOK_TEST_STAGED_FILES", None)
            result = subprocess.run(
                [sys.executable, str(HOOK_SCRIPT)],
                env=env,
                capture_output=True,
                text=True,
            )
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "HOOK_NO_GIT=1 simulates git unavailable.  Phase 1 must not "
                "hard-block: it should use an empty staged list and exit 0. "
                f"Stderr: {result.stderr}"
            ),
        )


class TestAC6StagingSeamWiredForExistingExitOneTests(unittest.TestCase):
    """AC-6: The existing exit-1 schema tests must exercise the staged-files
    path via HOOK_TEST_STAGED_FILES rather than passing trivially because
    nothing is staged.

    These tests confirm that HOOK_TEST_STAGED_FILES is wired as a Phase 1 seam:
    if the seam is working, a file listed there is validated (and can fail the
    hook).  If the seam is NOT wired, the hook exits 0 trivially (nothing staged
    → nothing validated) even for a file with a schema violation.

    All tests here are RED until python-coder wires up the HOOK_TEST_STAGED_FILES
    seam for Phase 1.
    """

    def test_seam_wired_missing_criteria_exits_one(self) -> None:
        # covers: AC-6 (TICKET-20260622-AcSchemaHookStagedScope)
        """HOOK_TEST_STAGED_FILES seam is wired: a file with missing criteria exits 1.

        This test is the canonical AC-6 guard.  It passes ONLY when the seam is
        wired — i.e. Phase 1 validates the file listed in HOOK_TEST_STAGED_FILES
        rather than ignoring it (no staging in a temp dir → trivially passes
        without the seam).

        FAILS before the fix: seam not wired, hook exits 0 (nothing staged in
        the temp dir's git state).
        """
        content = textwrap.dedent("""\
            id: FIN-040
            title: "Missing criteria — seam test"
            component: finalize
            status: active
            created_by: "tickets/test.md"
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staged_path = _write_ac_file(root, "FIN-040.yaml", content)
            result = _run_hook_with_staged(root, [staged_path])
        self.assertEqual(
            result.returncode,
            1,
            msg=(
                "HOOK_TEST_STAGED_FILES must be wired as a Phase 1 seam.  "
                "The file listed there is schema-invalid (missing criteria) so "
                "the hook must exit 1.  "
                f"Stderr: {result.stderr}"
            ),
        )
        self.assertIn("criteria", result.stderr)

    def test_seam_wired_valid_file_exits_zero(self) -> None:
        # covers: AC-6 (TICKET-20260622-AcSchemaHookStagedScope)
        """HOOK_TEST_STAGED_FILES seam is wired: a valid file listed there exits 0.

        Complement to test_seam_wired_missing_criteria_exits_one: a valid file
        must still pass.  This guards against a naive implementation that always
        exits 1 when the seam is set.

        FAILS before the fix: seam not wired; after fix this should pass
        trivially (valid file → no errors → exit 0).
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staged_path = _write_ac_file(root, "FIN-041.yaml", _VALID_AC_YAML)
            result = _run_hook_with_staged(root, [staged_path])
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "A valid file listed in HOOK_TEST_STAGED_FILES must exit 0. "
                f"Stderr: {result.stderr}"
            ),
        )

    def test_seam_empty_string_ignores_store_violations(self) -> None:
        # covers: AC-6 + AC-3 (TICKET-20260622-AcSchemaHookStagedScope)
        """HOOK_TEST_STAGED_FILES='' (empty) means no staged files → exit 0.

        Even when an invalid file lives in the store, an empty staged list
        means no Phase 1 validation runs and the hook exits 0.

        FAILS before the fix: without the seam, Phase 1 still scans the whole
        store.
        """
        import os

        invalid_content = textwrap.dedent("""\
            id: FIN-042
            title: "Invalid — staged-files empty string"
            component: finalize
            status: active
            created_by: "tickets/test.md"
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "FIN-042.yaml", invalid_content)
            env = os.environ.copy()
            env["HOOK_ROOT"] = str(root)
            env["HOOK_TEST_STAGED_FILES"] = ""
            result = subprocess.run(
                [sys.executable, str(HOOK_SCRIPT)],
                env=env,
                capture_output=True,
                text=True,
            )
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "HOOK_TEST_STAGED_FILES='' means nothing staged → exit 0 "
                "even with invalid files in the store. "
                f"Stderr: {result.stderr}"
            ),
        )

    def test_seam_file_not_in_store_is_ignored_gracefully(self) -> None:
        # covers: AC-6 (TICKET-20260622-AcSchemaHookStagedScope — edge case)
        """A path in HOOK_TEST_STAGED_FILES that does not exist is skipped gracefully.

        The seam must not raise an exception when a listed path is absent from
        disk (e.g. a deleted file).  The hook must exit 0 (fail-open).

        FAILS before the fix: the seam is not implemented, so the hook exits 0
        for the wrong reason (whole-store fallback with empty store).  After the
        fix, the hook exits 0 for the right reason (missing path skipped
        gracefully, no violations found).
        """
        import os

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Create the AC dir so the hook has a root to work with.
            ac_dir = root / "docs" / "acceptance-criteria"
            ac_dir.mkdir(parents=True)
            # Staged path that does NOT exist on disk.
            missing_path = ac_dir / "DOES-NOT-EXIST.yaml"
            env = os.environ.copy()
            env["HOOK_ROOT"] = str(root)
            env["HOOK_TEST_STAGED_FILES"] = str(missing_path)
            result = subprocess.run(
                [sys.executable, str(HOOK_SCRIPT)],
                env=env,
                capture_output=True,
                text=True,
            )
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "A non-existent path in HOOK_TEST_STAGED_FILES must be skipped "
                "gracefully (fail-open). "
                f"Stderr: {result.stderr}"
            ),
        )


# ---------------------------------------------------------------------------
# AC-1 / AC-2: change_target and risk_surface schema fields (ticket 08)
# ---------------------------------------------------------------------------
# AC-1: ac_store_schema.json accepts optional change_target (str or list of the
#        10 blast-radius values) and risk_surface (str, 6 values). These tests are
#        RED because ac_store_schema.json does not yet define these fields —
#        jsonschema rejects them as additional properties.
# AC-2: Validator rejects present-but-invalid values. These tests are RED because
#        the "additional property" error does not name the bad enum value in stderr.
# ---------------------------------------------------------------------------


_VALID_AC_WITH_CHANGE_TARGET_CODE = textwrap.dedent("""\
    id: FIN-050
    title: "AC with valid change_target str"
    component: finalize
    components:
      - finalize
    status: active
    created_by: "tickets/test.md"
    criteria: |
      Given something
      When something
      Then something
    priority: medium
    readiness: draft
    change_target: code
""")

_VALID_AC_WITH_RISK_SURFACE_INTERNAL = textwrap.dedent("""\
    id: FIN-051
    title: "AC with valid risk_surface"
    component: finalize
    components:
      - finalize
    status: active
    created_by: "tickets/test.md"
    criteria: |
      Given something
      When something
      Then something
    priority: medium
    readiness: draft
    risk_surface: internal
""")


class TestAcChangeTargetSchemaValidationAc1(unittest.TestCase):
    """AC-1: AC schema accepts valid change_target (str / list) and risk_surface values.

    All tests are RED before the fix: ac_store_schema.json currently has
    additionalProperties: false and does not define change_target or risk_surface.
    jsonschema therefore rejects any AC that carries these fields as
    "Additional properties are not allowed".
    """

    def test_ac1_valid_change_target_str_passes(self) -> None:
        # covers: UNKNOWN
        """AC-1: change_target: 'code' (valid scalar string) must exit 0.

        RED before fix: the schema does not define change_target, so jsonschema
        rejects it as an additional property → returncode 1.
        Fix: add change_target (enum, optional) to ac_store_schema.json.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "FIN-050.yaml", _VALID_AC_WITH_CHANGE_TARGET_CODE)
            result = _run_hook(root)
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "AC with change_target: 'code' must be accepted by the schema validator. "
                "Currently exits 1: 'change_target' is not in ac_store_schema.json "
                f"(additionalProperties: false). Stderr: {result.stderr}"
            ),
        )

    def test_ac1_valid_change_target_list_passes(self) -> None:
        # covers: UNKNOWN
        """AC-1: change_target: [code, schema] (valid list form) must exit 0.

        RED before fix: list form also rejected as additional property.
        """
        content = textwrap.dedent("""\
            id: FIN-052
            title: "AC with change_target list"
            component: finalize
            components:
              - finalize
            status: active
            created_by: "tickets/test.md"
            criteria: |
              Given something
              When something
              Then something
            priority: medium
            readiness: draft
            change_target:
              - code
              - schema
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "FIN-052.yaml", content)
            result = _run_hook(root)
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "AC with change_target: [code, schema] (list form) must exit 0. "
                "Currently fails because change_target is an additional property. "
                f"Stderr: {result.stderr}"
            ),
        )

    def test_ac1_valid_risk_surface_passes(self) -> None:
        # covers: UNKNOWN
        """AC-1: risk_surface: 'internal' (valid value) must exit 0.

        RED before fix: risk_surface rejected as additional property.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "FIN-051.yaml", _VALID_AC_WITH_RISK_SURFACE_INTERNAL)
            result = _run_hook(root)
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "AC with risk_surface: 'internal' must exit 0. Currently fails because "
                f"risk_surface is an additional property. Stderr: {result.stderr}"
            ),
        )

    def test_ac1_both_axes_present_and_valid_passes(self) -> None:
        # covers: UNKNOWN
        """AC-1: AC carrying both change_target and risk_surface (valid values) exits 0.

        RED before fix: both fields are additional properties — rejected by jsonschema.
        """
        content = textwrap.dedent("""\
            id: FIN-056
            title: "AC with both axes valid"
            component: finalize
            components:
              - finalize
            status: active
            created_by: "tickets/test.md"
            criteria: |
              Given something
              When something
              Then something
            priority: medium
            readiness: draft
            change_target: schema
            risk_surface: contract_boundary
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "FIN-056.yaml", content)
            result = _run_hook(root)
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "AC with change_target: schema and risk_surface: contract_boundary must exit 0. "
                f"Stderr: {result.stderr}"
            ),
        )


class TestAcChangeTargetSchemaValidationAc2(unittest.TestCase):
    """AC-2: Validator rejects change_target / risk_surface with out-of-enum value.

    These tests are RED because, before the fix, the hook rejects the fields as
    "additional properties" — an error that does NOT name the bad enum value.
    The assertIn(bad_value, result.stderr) assertion fails, making the test RED.
    """

    def test_ac2_invalid_change_target_rejected_names_bad_value(self) -> None:
        # covers: UNKNOWN
        """AC-2: change_target: 'bogus_target' exits 1 and stderr names 'bogus_target'.

        RED before fix: the hook exits 1 (correct) but for the wrong reason —
        'Additional properties are not allowed (change_target was unexpected)' does not
        contain 'bogus_target'. After the fix, the enum error names the bad value.
        """
        content = textwrap.dedent("""\
            id: FIN-053
            title: "AC with invalid change_target"
            component: finalize
            status: active
            created_by: "tickets/test.md"
            criteria: |
              Given something
              When something
              Then something
            priority: medium
            readiness: draft
            change_target: bogus_target
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "FIN-053.yaml", content)
            result = _run_hook(root)
        self.assertEqual(result.returncode, 1)
        # This assertion is the RED indicator: the additional-property error does not
        # mention 'bogus_target'. After the fix, the enum error will name the bad value.
        self.assertIn(
            "bogus_target",
            result.stderr,
            msg=(
                "The enum error for change_target: 'bogus_target' must name the bad value. "
                "Currently the hook rejects it as additional property without naming the value. "
                f"Stderr: {result.stderr}"
            ),
        )

    def test_ac2_invalid_risk_surface_rejected_names_bad_value(self) -> None:
        # covers: UNKNOWN
        """AC-2: risk_surface: 'bogus_surface' exits 1 and stderr names 'bogus_surface'.

        RED before fix: additional-property error does not mention 'bogus_surface'.
        """
        content = textwrap.dedent("""\
            id: FIN-054
            title: "AC with invalid risk_surface"
            component: finalize
            status: active
            created_by: "tickets/test.md"
            criteria: |
              Given something
              When something
              Then something
            priority: medium
            readiness: draft
            risk_surface: bogus_surface
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "FIN-054.yaml", content)
            result = _run_hook(root)
        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "bogus_surface",
            result.stderr,
            msg=(
                "The enum error for risk_surface: 'bogus_surface' must name the bad value. "
                f"Stderr: {result.stderr}"
            ),
        )

    def test_ac2_change_target_list_with_invalid_entry_names_bad_value(self) -> None:
        # covers: UNKNOWN
        """AC-2: change_target: [code, bogus_target] exits 1 and names 'bogus_target'.

        RED before fix: additional-property error does not name individual list items.
        """
        content = textwrap.dedent("""\
            id: FIN-055
            title: "AC with mixed valid/invalid change_target list"
            component: finalize
            status: active
            created_by: "tickets/test.md"
            criteria: |
              Given something
              When something
              Then something
            priority: medium
            readiness: draft
            change_target:
              - code
              - bogus_target
        """)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac_file(root, "FIN-055.yaml", content)
            result = _run_hook(root)
        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "bogus_target",
            result.stderr,
            msg=(
                "The enum error for a list change_target with invalid entry must name "
                "'bogus_target'. "
                f"Stderr: {result.stderr}"
            ),
        )


# ---------------------------------------------------------------------------
# AC-3: vocabulary contract (ticket 08)
# ---------------------------------------------------------------------------
# Asserts that the enum values for both axes are identical across three
# canonical sources: ac_store_schema.json, ticket_frontmatter_guard.py, and
# guardrail_gates.yaml top-level keys.
# RED: ac_store_schema.json does not yet define change_target or risk_surface.
# ---------------------------------------------------------------------------


class TestAcAxesVocabularyContractAc3(unittest.TestCase):
    """AC-3: change_target and risk_surface enum identical in schema, guard, and gates YAML.

    Tests are RED because ac_store_schema.json does not define these fields yet.
    """

    def test_ac3_change_target_enum_identical_across_sources(self) -> None:
        # covers: UNKNOWN
        """AC-3: The change_target enum in ac_store_schema.json, ALLOWED_CHANGE_TARGETS
        in ticket_frontmatter_guard.py, and the non-flow-change top-level keys of
        guardrail_gates.yaml must all be identical.

        RED before fix: ac_store_schema.json does not define 'change_target' property
        — assertIn('change_target', props) fails.
        Fix: add change_target (enum, optional) to ac_store_schema.json.
        """
        import importlib.util
        import json

        import yaml as _yaml

        repo_root = Path(__file__).resolve().parent.parent.parent

        # 1. Load schema and check change_target property exists
        schema_path = repo_root / "config" / "ac_store_schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        props = schema.get("properties", {})

        self.assertIn(
            "change_target",
            props,
            msg=(
                "ac_store_schema.json must define a 'change_target' property. "
                "It is currently absent (additionalProperties: false rejects it). "
                "Add change_target as an optional enum field (10 blast-radius values)."
            ),
        )

        # Extract enum values from schema (handles str-only or anyOf/oneOf for str|list forms)
        ct_prop = props["change_target"]
        schema_ct_enum: set[str] = set()
        if "enum" in ct_prop:
            schema_ct_enum = set(ct_prop["enum"])
        for container_key in ("anyOf", "oneOf"):
            for sub in ct_prop.get(container_key, []):
                if sub.get("type") == "string" and "enum" in sub:
                    schema_ct_enum.update(sub["enum"])
                elif sub.get("type") == "array":
                    items = sub.get("items", {})
                    if "enum" in items:
                        schema_ct_enum.update(items["enum"])

        # 2. Load ALLOWED_CHANGE_TARGETS from ticket_frontmatter_guard.py
        guard_path = repo_root / "templates" / "hooks" / "ticket_frontmatter_guard.py"
        spec = importlib.util.spec_from_file_location("ticket_frontmatter_guard", guard_path)
        guard_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(guard_mod)
        guard_ct: set[str] = set(guard_mod.ALLOWED_CHANGE_TARGETS)

        # 3. Load guardrail_gates.yaml top-level keys, excluding the non-change-target
        #    policy sections. These are gate-policy blocks that legitimately sit at the
        #    top level but are NOT change_target vocab entries and must not participate
        #    in the vocab-parity check:
        #      - flow_change_gates: flow-change pair gates
        #      - documentation_gates: doc-coverage triggers (BO-2200a-1)
        #      - surgical_removal_guard: surgical-removal policy (BO-2200d-1-i)
        _NON_CHANGE_TARGET_SECTIONS = {
            "flow_change_gates",
            "documentation_gates",
            "surgical_removal_guard",
        }
        guardrail_path = repo_root / "config" / "guardrail_gates.yaml"
        gates = _yaml.safe_load(guardrail_path.read_text(encoding="utf-8"))
        yaml_ct: set[str] = {k for k in gates if k not in _NON_CHANGE_TARGET_SECTIONS}

        self.assertEqual(
            schema_ct_enum,
            guard_ct,
            msg=(
                f"change_target enum in ac_store_schema.json ({sorted(schema_ct_enum)}) "
                f"must equal ALLOWED_CHANGE_TARGETS from ticket_frontmatter_guard.py "
                f"({sorted(guard_ct)}). Drift detected — single source of truth violated."
            ),
        )
        self.assertEqual(
            schema_ct_enum,
            yaml_ct,
            msg=(
                f"change_target enum in ac_store_schema.json ({sorted(schema_ct_enum)}) "
                f"must equal the non-flow-change top-level keys of guardrail_gates.yaml "
                f"({sorted(yaml_ct)}). Drift detected."
            ),
        )

    def test_ac3_risk_surface_enum_identical_across_sources(self) -> None:
        # covers: UNKNOWN
        """AC-3: The risk_surface enum in ac_store_schema.json must equal
        ALLOWED_RISK_SURFACES in ticket_frontmatter_guard.py.

        RED before fix: ac_store_schema.json does not define 'risk_surface' property.
        Fix: add risk_surface (enum, optional) to ac_store_schema.json.
        """
        import importlib.util
        import json

        repo_root = Path(__file__).resolve().parent.parent.parent

        schema_path = repo_root / "config" / "ac_store_schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        props = schema.get("properties", {})

        self.assertIn(
            "risk_surface",
            props,
            msg=(
                "ac_store_schema.json must define a 'risk_surface' property. "
                "It is currently absent. Add risk_surface as optional enum (6 blast-radius values)."
            ),
        )

        rs_prop = props["risk_surface"]
        schema_rs_enum: set[str] = set()
        if "enum" in rs_prop:
            schema_rs_enum = set(rs_prop["enum"])
        for container_key in ("anyOf", "oneOf"):
            for sub in rs_prop.get(container_key, []):
                if sub.get("type") == "string" and "enum" in sub:
                    schema_rs_enum.update(sub["enum"])

        guard_path = repo_root / "templates" / "hooks" / "ticket_frontmatter_guard.py"
        spec = importlib.util.spec_from_file_location("ticket_frontmatter_guard_rs", guard_path)
        guard_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(guard_mod)
        guard_rs: set[str] = set(guard_mod.ALLOWED_RISK_SURFACES)

        self.assertEqual(
            schema_rs_enum,
            guard_rs,
            msg=(
                f"risk_surface enum in ac_store_schema.json ({sorted(schema_rs_enum)}) "
                f"must equal ALLOWED_RISK_SURFACES from ticket_frontmatter_guard.py "
                f"({sorted(guard_rs)}). Drift detected."
            ),
        )


if __name__ == "__main__":
    unittest.main()
