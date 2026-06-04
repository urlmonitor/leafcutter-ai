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


if __name__ == "__main__":
    unittest.main()
