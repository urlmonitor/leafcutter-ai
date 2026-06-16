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


if __name__ == "__main__":
    unittest.main()
