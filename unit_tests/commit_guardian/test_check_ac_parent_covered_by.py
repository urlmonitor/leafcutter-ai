"""
MODULE: test_check_ac_parent_covered_by
GOAL: Unit tests for the check_ac_parent_covered_by.py pre-commit hook that
    blocks commits when a staged child AC YAML file's parent AC does not include
    the child in its covered_by field.
BUSINESS CONTEXT: Verifies that the hook correctly detects when a parent AC's
    covered_by list omits a staged child AC ID, emits a human-readable error
    naming both the child and parent AC IDs and the parent file path, and allows
    the commit when the parent's covered_by is correctly updated. Also verifies
    fail-open behaviour on parse errors and missing parent files.
ARCHITECTURE: Tests call the hook module's internal functions directly to keep
    tests fast and deterministic. Temporary directories simulate the AC store.
    HOOK_TEST_FILES env var is used to inject staged file paths without a real
    git repo. HOOK_ROOT env var pins the project root.

# covers: ACS-100i-2
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HOOK_SCRIPT = (
    _REPO_ROOT / "scripts" / "commit_guardian" / "check_ac_parent_covered_by.py"
)


def _load_hook_module():
    """Load check_ac_parent_covered_by as a module without installing it."""
    spec = importlib.util.spec_from_file_location(
        "check_ac_parent_covered_by", str(_HOOK_SCRIPT)
    )
    if spec is None or spec.loader is None:
        msg = f"Cannot load module from {_HOOK_SCRIPT}"
        raise ImportError(msg)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

_PARENT_YAML_TEMPLATE = textwrap.dedent(
    """\
    id: {parent_id}
    title: Parent AC
    req_status: approved
    criteria: Some criteria.
    covered_by: {covered_by}
    origin_agent: BrainCandy
    """
)

_CHILD_YAML_TEMPLATE = textwrap.dedent(
    """\
    id: {child_id}
    title: Child AC
    req_status: approved
    criteria: Child criteria.
    depends_on: [{parent_id}]
    origin_agent: BrainCandy
    """
)


class TestExtractCoveredBy(unittest.TestCase):
    """Tests for _extract_covered_by."""

    def setUp(self):
        self.mod = _load_hook_module()

    def test_list_with_entries(self):
        data = {"covered_by": ["ACS-100a", "ACS-100b"]}
        result = self.mod._extract_covered_by(data)
        self.assertEqual(result, ["ACS-100a", "ACS-100b"])

    def test_empty_list(self):
        data = {"covered_by": []}
        result = self.mod._extract_covered_by(data)
        self.assertEqual(result, [])

    def test_absent_field(self):
        data = {}
        result = self.mod._extract_covered_by(data)
        self.assertEqual(result, [])

    def test_none_value(self):
        data = {"covered_by": None}
        result = self.mod._extract_covered_by(data)
        self.assertEqual(result, [])

    def test_string_fallback_with_brackets(self):
        """Minimal fallback parser returns string; should be parsed correctly."""
        data = {"covered_by": "[ACS-100a, ACS-100b]"}
        result = self.mod._extract_covered_by(data)
        self.assertIn("ACS-100a", result)
        self.assertIn("ACS-100b", result)

    def test_empty_brackets_string(self):
        data = {"covered_by": "[]"}
        result = self.mod._extract_covered_by(data)
        self.assertEqual(result, [])


class TestCheckFileCoveredByMissing(unittest.TestCase):
    """Tests for _check_file: parent covered_by does NOT include child — should block."""

    def setUp(self):
        self.mod = _load_hook_module()
        self._old_env = {}

    def tearDown(self):
        for k, v in self._old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _set_env(self, key, value):
        self._old_env.setdefault(key, os.environ.get(key))
        os.environ[key] = value

    def test_parent_covered_by_empty_blocks(self):
        """Child is staged; parent covered_by is []; should produce a violation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_store = Path(tmpdir) / "docs" / "acceptance-criteria" / "ACS-300h"
            ac_store.mkdir(parents=True)

            parent_file = ac_store / "ACS-300h.yaml"
            parent_file.write_text(
                _PARENT_YAML_TEMPLATE.format(
                    parent_id="ACS-300h",
                    covered_by="[]",
                )
            )

            child_file = ac_store / "ACS-300h-4.yaml"
            child_file.write_text(
                _CHILD_YAML_TEMPLATE.format(
                    child_id="ACS-300h-4",
                    parent_id="ACS-300h",
                )
            )

            self._set_env("HOOK_ROOT", tmpdir)

            # Derive parent id function from module
            derive_fn = self.mod._get_derive_parent_id()
            violations = self.mod._check_file(str(child_file), derive_fn)

            self.assertTrue(
                len(violations) == 1,
                f"Expected 1 violation, got {len(violations)}: {violations}",
            )
            v = violations[0]
            self.assertIn("ACS-300h-4", v)
            self.assertIn("ACS-300h", v)
            self.assertIn(str(parent_file), v)

    def test_error_message_names_child_id(self):
        """The violation message must name the child AC ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_store = Path(tmpdir) / "docs" / "acceptance-criteria" / "ACS-300h"
            ac_store.mkdir(parents=True)
            parent_file = ac_store / "ACS-300h.yaml"
            parent_file.write_text(
                _PARENT_YAML_TEMPLATE.format(parent_id="ACS-300h", covered_by="[]")
            )
            child_file = ac_store / "ACS-300h-4.yaml"
            child_file.write_text(
                _CHILD_YAML_TEMPLATE.format(child_id="ACS-300h-4", parent_id="ACS-300h")
            )
            self._set_env("HOOK_ROOT", tmpdir)
            derive_fn = self.mod._get_derive_parent_id()
            violations = self.mod._check_file(str(child_file), derive_fn)
            self.assertTrue(any("ACS-300h-4" in v for v in violations))

    def test_error_message_names_parent_id(self):
        """The violation message must name the parent AC ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_store = Path(tmpdir) / "docs" / "acceptance-criteria" / "ACS-300h"
            ac_store.mkdir(parents=True)
            parent_file = ac_store / "ACS-300h.yaml"
            parent_file.write_text(
                _PARENT_YAML_TEMPLATE.format(parent_id="ACS-300h", covered_by="[]")
            )
            child_file = ac_store / "ACS-300h-4.yaml"
            child_file.write_text(
                _CHILD_YAML_TEMPLATE.format(child_id="ACS-300h-4", parent_id="ACS-300h")
            )
            self._set_env("HOOK_ROOT", tmpdir)
            derive_fn = self.mod._get_derive_parent_id()
            violations = self.mod._check_file(str(child_file), derive_fn)
            self.assertTrue(any("ACS-300h" in v for v in violations))

    def test_error_message_includes_parent_file_path(self):
        """The violation message must include the parent file path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_store = Path(tmpdir) / "docs" / "acceptance-criteria" / "ACS-300h"
            ac_store.mkdir(parents=True)
            parent_file = ac_store / "ACS-300h.yaml"
            parent_file.write_text(
                _PARENT_YAML_TEMPLATE.format(parent_id="ACS-300h", covered_by="[]")
            )
            child_file = ac_store / "ACS-300h-4.yaml"
            child_file.write_text(
                _CHILD_YAML_TEMPLATE.format(child_id="ACS-300h-4", parent_id="ACS-300h")
            )
            self._set_env("HOOK_ROOT", tmpdir)
            derive_fn = self.mod._get_derive_parent_id()
            violations = self.mod._check_file(str(child_file), derive_fn)
            parent_path_str = str(parent_file.resolve())
            self.assertTrue(
                any(parent_path_str in v for v in violations),
                f"Parent path '{parent_path_str}' not found in violations: {violations}",
            )

    def test_error_message_states_must_include(self):
        """The violation message must state that covered_by must include the child."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_store = Path(tmpdir) / "docs" / "acceptance-criteria" / "ACS-300h"
            ac_store.mkdir(parents=True)
            parent_file = ac_store / "ACS-300h.yaml"
            parent_file.write_text(
                _PARENT_YAML_TEMPLATE.format(parent_id="ACS-300h", covered_by="[]")
            )
            child_file = ac_store / "ACS-300h-4.yaml"
            child_file.write_text(
                _CHILD_YAML_TEMPLATE.format(child_id="ACS-300h-4", parent_id="ACS-300h")
            )
            self._set_env("HOOK_ROOT", tmpdir)
            derive_fn = self.mod._get_derive_parent_id()
            violations = self.mod._check_file(str(child_file), derive_fn)
            # Message must communicate that covered_by needs to be updated
            self.assertTrue(
                any("covered_by" in v for v in violations),
                f"Expected 'covered_by' in violation message; got: {violations}",
            )


class TestCheckFileCoveredByPresent(unittest.TestCase):
    """Tests for _check_file: parent covered_by DOES include child — should allow."""

    def setUp(self):
        self.mod = _load_hook_module()
        self._old_env = {}

    def tearDown(self):
        for k, v in self._old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _set_env(self, key, value):
        self._old_env.setdefault(key, os.environ.get(key))
        os.environ[key] = value

    def test_parent_includes_child_allows(self):
        """Parent covered_by already includes child; no violations expected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_store = Path(tmpdir) / "docs" / "acceptance-criteria" / "ACS-300h"
            ac_store.mkdir(parents=True)
            parent_file = ac_store / "ACS-300h.yaml"
            parent_file.write_text(
                _PARENT_YAML_TEMPLATE.format(
                    parent_id="ACS-300h",
                    covered_by="[ACS-300h-4]",
                )
            )
            child_file = ac_store / "ACS-300h-4.yaml"
            child_file.write_text(
                _CHILD_YAML_TEMPLATE.format(child_id="ACS-300h-4", parent_id="ACS-300h")
            )
            self._set_env("HOOK_ROOT", tmpdir)
            derive_fn = self.mod._get_derive_parent_id()
            violations = self.mod._check_file(str(child_file), derive_fn)
            self.assertEqual(violations, [], f"Expected no violations; got: {violations}")


class TestCheckFileEdgeCases(unittest.TestCase):
    """Edge-case and fail-open tests for _check_file."""

    def setUp(self):
        self.mod = _load_hook_module()
        self._old_env = {}

    def tearDown(self):
        for k, v in self._old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _set_env(self, key, value):
        self._old_env.setdefault(key, os.environ.get(key))
        os.environ[key] = value

    def test_no_depends_on_skips(self):
        """A child with no depends_on field should produce no violations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_store = Path(tmpdir) / "docs" / "acceptance-criteria"
            ac_store.mkdir(parents=True)
            child_file = ac_store / "ACS-300h-4.yaml"
            child_file.write_text(
                textwrap.dedent(
                    """\
                    id: ACS-300h-4
                    title: Orphan child
                    req_status: draft
                    """
                )
            )
            self._set_env("HOOK_ROOT", tmpdir)
            derive_fn = self.mod._get_derive_parent_id()
            violations = self.mod._check_file(str(child_file), derive_fn)
            self.assertEqual(violations, [])

    def test_root_ac_no_parent_skips(self):
        """A root-level AC (ACS-300) staged without a depends_on should not block."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_store = Path(tmpdir) / "docs" / "acceptance-criteria"
            ac_store.mkdir(parents=True)
            root_file = ac_store / "ACS-300.yaml"
            root_file.write_text(
                textwrap.dedent(
                    """\
                    id: ACS-300
                    title: Root AC
                    req_status: approved
                    covered_by: []
                    origin_agent: BrainCandy
                    """
                )
            )
            self._set_env("HOOK_ROOT", tmpdir)
            derive_fn = self.mod._get_derive_parent_id()
            violations = self.mod._check_file(str(root_file), derive_fn)
            self.assertEqual(violations, [])

    def test_parent_file_not_found_fail_open(self):
        """When parent YAML file is absent on disk, hook fails open (no violation)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_store = Path(tmpdir) / "docs" / "acceptance-criteria"
            ac_store.mkdir(parents=True)
            child_file = ac_store / "ACS-300h-4.yaml"
            child_file.write_text(
                _CHILD_YAML_TEMPLATE.format(child_id="ACS-300h-4", parent_id="ACS-300h")
            )
            self._set_env("HOOK_ROOT", tmpdir)
            derive_fn = self.mod._get_derive_parent_id()
            # No parent file exists — should fail open
            violations = self.mod._check_file(str(child_file), derive_fn)
            self.assertEqual(violations, [], f"Expected fail-open; got: {violations}")

    def test_no_id_field_skips(self):
        """A YAML file with no id field should produce no violations (not an AC)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_store = Path(tmpdir) / "docs" / "acceptance-criteria"
            ac_store.mkdir(parents=True)
            yaml_file = ac_store / "some-config.yaml"
            yaml_file.write_text("some_key: some_value\ndepends_on: [ACS-300h]\n")
            self._set_env("HOOK_ROOT", tmpdir)
            derive_fn = self.mod._get_derive_parent_id()
            violations = self.mod._check_file(str(yaml_file), derive_fn)
            self.assertEqual(violations, [])

    def test_immediate_parent_not_in_depends_on_skips(self):
        """Child has depends_on referencing a non-immediate-parent; skip check."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Child ACS-300h-4 whose structural parent is ACS-300h,
            # but depends_on references ACS-999 (some other AC).
            ac_store = Path(tmpdir) / "docs" / "acceptance-criteria"
            ac_store.mkdir(parents=True)
            child_file = ac_store / "ACS-300h-4.yaml"
            child_file.write_text(
                textwrap.dedent(
                    """\
                    id: ACS-300h-4
                    title: Child AC
                    req_status: approved
                    depends_on: [ACS-999]
                    origin_agent: BrainCandy
                    """
                )
            )
            self._set_env("HOOK_ROOT", tmpdir)
            derive_fn = self.mod._get_derive_parent_id()
            violations = self.mod._check_file(str(child_file), derive_fn)
            # Structural parent ACS-300h is not in depends_on → skip check
            self.assertEqual(violations, [])


class TestMainExitCodes(unittest.TestCase):
    """Integration tests for main() exit codes using HOOK_TEST_FILES."""

    def setUp(self):
        self.mod = _load_hook_module()
        self._old_env = {}

    def tearDown(self):
        for k, v in self._old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _set_env(self, key, value):
        self._old_env.setdefault(key, os.environ.get(key))
        os.environ[key] = value

    def test_main_exits_0_when_no_staged_files(self):
        """main() exits 0 when no staged files provided."""
        self._set_env("HOOK_TEST_FILES", "")
        self._set_env("HOOK_NO_GIT", "1")
        result = self.mod.main()
        self.assertEqual(result, 0)

    def test_main_exits_0_when_parent_correct(self):
        """main() exits 0 when staged child has parent with correct covered_by."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_store = Path(tmpdir) / "docs" / "acceptance-criteria" / "ACS-300h"
            ac_store.mkdir(parents=True)
            parent_file = ac_store / "ACS-300h.yaml"
            parent_file.write_text(
                _PARENT_YAML_TEMPLATE.format(
                    parent_id="ACS-300h",
                    covered_by="[ACS-300h-4]",
                )
            )
            child_file = ac_store / "ACS-300h-4.yaml"
            child_file.write_text(
                _CHILD_YAML_TEMPLATE.format(child_id="ACS-300h-4", parent_id="ACS-300h")
            )
            self._set_env("HOOK_ROOT", tmpdir)
            self._set_env("HOOK_TEST_FILES", str(child_file))
            result = self.mod.main()
            self.assertEqual(result, 0)

    def test_main_exits_1_when_parent_missing_child(self):
        """main() exits 1 when staged child is missing from parent's covered_by."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_store = Path(tmpdir) / "docs" / "acceptance-criteria" / "ACS-300h"
            ac_store.mkdir(parents=True)
            parent_file = ac_store / "ACS-300h.yaml"
            parent_file.write_text(
                _PARENT_YAML_TEMPLATE.format(parent_id="ACS-300h", covered_by="[]")
            )
            child_file = ac_store / "ACS-300h-4.yaml"
            child_file.write_text(
                _CHILD_YAML_TEMPLATE.format(child_id="ACS-300h-4", parent_id="ACS-300h")
            )
            self._set_env("HOOK_ROOT", tmpdir)
            self._set_env("HOOK_TEST_FILES", str(child_file))
            result = self.mod.main()
            self.assertEqual(result, 1)

    def test_main_exits_0_no_ac_store(self):
        """main() exits 0 when AC store directory does not exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._set_env("HOOK_ROOT", tmpdir)
            self._set_env("HOOK_NO_GIT", "1")
            result = self.mod.main()
            self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
