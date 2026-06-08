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


class TestThreeLevelAncestryChain(unittest.TestCase):
    """Tests for ACS-100i-3: three-level ancestry chain (L1 → L2 → L3).

    When a new L3 AC is staged, only the immediate parent (L2) must list it in
    covered_by. The grandparent (L1) is NOT required to list the L3 AC directly.
    """

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

    def _build_three_level_store(self, tmpdir, l2_covered_by="[]"):
        """Create a three-level AC store under tmpdir.

        L1 (ACS-300g): covered_by: ["ACS-300g-1"]
        L2 (ACS-300g-1): covered_by: <l2_covered_by>
        L3 (ACS-300g-1-ii): staged child, depends_on: [ACS-300g-1]

        Returns:
            Tuple (l3_file, l2_file, l1_file) as Path objects.
        """
        ac_store = Path(tmpdir) / "docs" / "acceptance-criteria" / "ACS-300g"
        ac_store.mkdir(parents=True)

        l1_file = ac_store / "ACS-300g.yaml"
        l1_file.write_text(
            textwrap.dedent(
                f"""\
                id: ACS-300g
                title: L1 grandparent AC
                req_status: approved
                criteria: Root criteria.
                covered_by: ["ACS-300g-1"]
                origin_agent: BrainCandy
                """
            )
        )

        l2_file = ac_store / "ACS-300g-1.yaml"
        l2_file.write_text(
            textwrap.dedent(
                f"""\
                id: ACS-300g-1
                title: L2 parent AC
                req_status: approved
                criteria: L2 criteria.
                depends_on: [ACS-300g]
                covered_by: {l2_covered_by}
                origin_agent: BrainCandy
                """
            )
        )

        l3_file = ac_store / "ACS-300g-1-ii.yaml"
        l3_file.write_text(
            textwrap.dedent(
                """\
                id: ACS-300g-1-ii
                title: L3 child AC
                req_status: draft
                criteria: L3 criteria.
                depends_on: [ACS-300g-1]
                origin_agent: BrainCandy
                """
            )
        )

        return l3_file, l2_file, l1_file

    def test_l3_staged_l2_empty_covered_by_blocks(self):
        """L3 staged; L2 covered_by is []; commit is blocked with a violation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            l3_file, l2_file, _l1_file = self._build_three_level_store(
                tmpdir, l2_covered_by="[]"
            )
            self._set_env("HOOK_ROOT", tmpdir)
            self._set_env("HOOK_TEST_FILES", str(l3_file))

            result = self.mod.main()

            self.assertEqual(
                result,
                1,
                "Expected exit code 1 (blocked) when L3 staged but L2 covered_by is []",
            )

    def test_l3_staged_error_names_immediate_parent_l2(self):
        """Error message names the immediate parent (L2 = ACS-300g-1), not grandparent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            l3_file, l2_file, _l1_file = self._build_three_level_store(
                tmpdir, l2_covered_by="[]"
            )
            self._set_env("HOOK_ROOT", tmpdir)
            derive_fn = self.mod._get_derive_parent_id()
            violations = self.mod._check_file(str(l3_file), derive_fn)

            self.assertTrue(
                len(violations) == 1,
                f"Expected exactly 1 violation; got {len(violations)}: {violations}",
            )
            self.assertIn(
                "ACS-300g-1",
                violations[0],
                "Violation message must name the immediate parent 'ACS-300g-1'",
            )

    def test_l3_staged_error_does_not_require_grandparent(self):
        """Grandparent (ACS-300g) is NOT required to list L3 in its covered_by."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # L1 covered_by only lists ACS-300g-1 (does NOT list ACS-300g-1-ii).
            # This is correct — the grandparent only lists direct children.
            # Hook must not require L1 to list L3.
            l3_file, l2_file, _l1_file = self._build_three_level_store(
                tmpdir, l2_covered_by="[ACS-300g-1-ii]"
            )
            self._set_env("HOOK_ROOT", tmpdir)
            self._set_env("HOOK_TEST_FILES", str(l3_file))

            result = self.mod.main()

            # When L2 correctly lists L3, commit is allowed — even though L1
            # does not list L3. Grandparent coverage is not required.
            self.assertEqual(
                result,
                0,
                "Expected exit code 0 (allowed): grandparent need not list L3 directly",
            )

    def test_l3_staged_l2_correct_covered_by_allows(self):
        """L3 staged; L2 covered_by correctly includes L3; commit is allowed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            l3_file, l2_file, _l1_file = self._build_three_level_store(
                tmpdir, l2_covered_by="[ACS-300g-1-ii]"
            )
            self._set_env("HOOK_ROOT", tmpdir)
            derive_fn = self.mod._get_derive_parent_id()
            violations = self.mod._check_file(str(l3_file), derive_fn)

            self.assertEqual(
                violations,
                [],
                f"Expected no violations when L2 correctly lists L3; got: {violations}",
            )

    def test_violation_message_names_l3_child_id(self):
        """Violation message names the staged child (L3 = ACS-300g-1-ii)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            l3_file, _l2_file, _l1_file = self._build_three_level_store(
                tmpdir, l2_covered_by="[]"
            )
            self._set_env("HOOK_ROOT", tmpdir)
            derive_fn = self.mod._get_derive_parent_id()
            violations = self.mod._check_file(str(l3_file), derive_fn)

            self.assertTrue(
                any("ACS-300g-1-ii" in v for v in violations),
                f"Violation must name child ID 'ACS-300g-1-ii'; got: {violations}",
            )

    def test_violation_message_names_l2_parent_file_path(self):
        """Violation message includes the L2 parent file path for actionable guidance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            l3_file, l2_file, _l1_file = self._build_three_level_store(
                tmpdir, l2_covered_by="[]"
            )
            self._set_env("HOOK_ROOT", tmpdir)
            derive_fn = self.mod._get_derive_parent_id()
            violations = self.mod._check_file(str(l3_file), derive_fn)

            l2_abs = str(l2_file.resolve())
            self.assertTrue(
                any(l2_abs in v for v in violations),
                f"Violation must include L2 parent file path '{l2_abs}'; got: {violations}",
            )


class TestPreCommitHookEdgeCases(unittest.TestCase):
    """Edge-case tests for the pre-commit hook covering unusual or adversarial inputs.

    Each test documents the expected (fail-open) behaviour for inputs that are
    malformed, structurally unusual, or outside the normal AC store path tree.
    Where a test uncovers a real implementation bug, the assertion is written to
    reflect what the hook *should* do (fail-open), and the test is expected to
    fail against the current implementation — that failure is the bug report.
    """

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

    # ------------------------------------------------------------------
    # Scenario 1: staged YAML file with completely empty content (0 bytes)
    # ------------------------------------------------------------------

    def test_empty_file_fails_open(self):
        """A zero-byte staged YAML file must not block the commit (fail-open).

        yaml.safe_load("") returns None, which _load_yaml_safe converts to None,
        causing _check_file to return [] (no violations).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_store = Path(tmpdir) / "docs" / "acceptance-criteria"
            ac_store.mkdir(parents=True)
            empty_file = ac_store / "ACS-500a.yaml"
            empty_file.write_bytes(b"")  # exactly 0 bytes

            self._set_env("HOOK_ROOT", tmpdir)
            derive_fn = self.mod._get_derive_parent_id()
            violations = self.mod._check_file(str(empty_file), derive_fn)

            self.assertEqual(
                violations,
                [],
                "Empty file must produce no violations (fail-open); "
                f"got: {violations}",
            )

    # ------------------------------------------------------------------
    # Scenario 2: valid YAML but no `id` field
    # ------------------------------------------------------------------

    def test_valid_yaml_no_id_field_skips(self):
        """A parseable YAML file with no 'id' field is not an AC and must be skipped.

        The hook extracts child_id = "" (empty) and returns [] immediately.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_store = Path(tmpdir) / "docs" / "acceptance-criteria"
            ac_store.mkdir(parents=True)
            yaml_file = ac_store / "ACS-500b.yaml"
            yaml_file.write_text(
                textwrap.dedent(
                    """\
                    title: Missing ID file
                    req_status: draft
                    depends_on: [ACS-500]
                    covered_by: []
                    """
                )
            )

            self._set_env("HOOK_ROOT", tmpdir)
            derive_fn = self.mod._get_derive_parent_id()
            violations = self.mod._check_file(str(yaml_file), derive_fn)

            self.assertEqual(
                violations,
                [],
                "File with no 'id' field must be skipped; "
                f"got: {violations}",
            )

    # ------------------------------------------------------------------
    # Scenario 3: `covered_by` is a string instead of a list
    # ------------------------------------------------------------------

    def test_covered_by_plain_string_is_handled(self):
        """Parent's covered_by is a plain string (not YAML list) — hook should not crash.

        When covered_by is a bare string like 'ACS-500a-1', _extract_covered_by
        falls into the str branch, strips brackets (none present), and splits on
        commas. A bare ID 'ACS-500a-1' with no brackets should be treated as a
        single-element list containing that ID.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_store = Path(tmpdir) / "docs" / "acceptance-criteria" / "ACS-500a"
            ac_store.mkdir(parents=True)

            # Parent uses a plain string for covered_by (no square brackets)
            parent_file = ac_store / "ACS-500a.yaml"
            parent_file.write_text(
                textwrap.dedent(
                    """\
                    id: ACS-500a
                    title: Parent AC
                    req_status: approved
                    criteria: Some criteria.
                    covered_by: ACS-500a-1
                    origin_agent: BrainCandy
                    """
                )
            )

            child_file = ac_store / "ACS-500a-1.yaml"
            child_file.write_text(
                _CHILD_YAML_TEMPLATE.format(
                    child_id="ACS-500a-1",
                    parent_id="ACS-500a",
                )
            )

            self._set_env("HOOK_ROOT", tmpdir)
            derive_fn = self.mod._get_derive_parent_id()
            violations = self.mod._check_file(str(child_file), derive_fn)

            # covered_by: ACS-500a-1 (plain string) must be parsed to include the child
            self.assertEqual(
                violations,
                [],
                "Plain-string covered_by containing the child ID must be recognised; "
                f"got: {violations}",
            )

    # ------------------------------------------------------------------
    # Scenario 4: `covered_by` is null/None
    # ------------------------------------------------------------------

    def test_covered_by_null_produces_violation(self):
        """Parent's covered_by is null — child is staged but parent lists nothing.

        PyYAML parses 'covered_by: null' / 'covered_by: ~' / 'covered_by:' as None.
        _extract_covered_by returns [] for None. The child ID is therefore absent
        from covered_by, and the hook must raise a violation.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_store = Path(tmpdir) / "docs" / "acceptance-criteria" / "ACS-500b"
            ac_store.mkdir(parents=True)

            parent_file = ac_store / "ACS-500b.yaml"
            parent_file.write_text(
                textwrap.dedent(
                    """\
                    id: ACS-500b
                    title: Parent AC
                    req_status: approved
                    criteria: Some criteria.
                    covered_by: null
                    origin_agent: BrainCandy
                    """
                )
            )

            child_file = ac_store / "ACS-500b-1.yaml"
            child_file.write_text(
                _CHILD_YAML_TEMPLATE.format(
                    child_id="ACS-500b-1",
                    parent_id="ACS-500b",
                )
            )

            self._set_env("HOOK_ROOT", tmpdir)
            derive_fn = self.mod._get_derive_parent_id()
            violations = self.mod._check_file(str(child_file), derive_fn)

            self.assertEqual(
                len(violations),
                1,
                "null covered_by must produce exactly 1 violation; "
                f"got {len(violations)}: {violations}",
            )
            self.assertIn("ACS-500b-1", violations[0])

    # ------------------------------------------------------------------
    # Scenario 5: child ID whose derived parent doesn't exist as a file
    # ------------------------------------------------------------------

    def test_parent_file_absent_fails_open(self):
        """Child references a parent ID that has no matching YAML on disk.

        _resolve_parent_file scans the AC store and finds no file whose id
        matches the parent. Hook warns and returns [] (fail-open, no violation).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_store = Path(tmpdir) / "docs" / "acceptance-criteria"
            ac_store.mkdir(parents=True)

            # Child exists; parent file does NOT exist anywhere in the AC store
            child_file = ac_store / "ACS-501a-1.yaml"
            child_file.write_text(
                _CHILD_YAML_TEMPLATE.format(
                    child_id="ACS-501a-1",
                    parent_id="ACS-501a",
                )
            )

            self._set_env("HOOK_ROOT", tmpdir)
            derive_fn = self.mod._get_derive_parent_id()
            violations = self.mod._check_file(str(child_file), derive_fn)

            self.assertEqual(
                violations,
                [],
                "Missing parent file on disk must fail-open (no violation); "
                f"got: {violations}",
            )

    # ------------------------------------------------------------------
    # Scenario 6: parent YAML file exists but is malformed (not valid YAML)
    # ------------------------------------------------------------------

    def test_malformed_parent_yaml_fails_open(self):
        """Parent file exists but contains invalid YAML — hook must not crash.

        _load_yaml_safe returns None on parse error. _check_file detects None
        parent_data and returns [] (fail-open), printing a WARNING to stderr.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_store = Path(tmpdir) / "docs" / "acceptance-criteria" / "ACS-502a"
            ac_store.mkdir(parents=True)

            # Parent file: syntactically invalid YAML (mapping key collision / bad indent)
            parent_file = ac_store / "ACS-502a.yaml"
            parent_file.write_text(
                textwrap.dedent(
                    """\
                    id: ACS-502a
                    covered_by: [ACS-502a-1
                      bad_indent: this is not valid yaml: [
                    """
                )
            )

            child_file = ac_store / "ACS-502a-1.yaml"
            child_file.write_text(
                _CHILD_YAML_TEMPLATE.format(
                    child_id="ACS-502a-1",
                    parent_id="ACS-502a",
                )
            )

            self._set_env("HOOK_ROOT", tmpdir)
            derive_fn = self.mod._get_derive_parent_id()
            violations = self.mod._check_file(str(child_file), derive_fn)

            # Malformed parent must cause fail-open, not a violation or exception
            self.assertEqual(
                violations,
                [],
                "Malformed parent YAML must fail-open; "
                f"got: {violations}",
            )

    # ------------------------------------------------------------------
    # Scenario 7: multiple staged children pointing to same parent; parent
    #             lists only one of them (missing the second)
    # ------------------------------------------------------------------

    def test_multiple_children_parent_missing_one_produces_one_violation(self):
        """Two children staged; parent covered_by lists only first child.

        The hook processes each staged path independently via main(). When it
        processes the second child, it detects the omission and emits 1 violation.
        Overall, main() exits 1.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_store = Path(tmpdir) / "docs" / "acceptance-criteria" / "ACS-503a"
            ac_store.mkdir(parents=True)

            # Parent lists only child-1, not child-2
            parent_file = ac_store / "ACS-503a.yaml"
            parent_file.write_text(
                _PARENT_YAML_TEMPLATE.format(
                    parent_id="ACS-503a",
                    covered_by="[ACS-503a-1]",
                )
            )

            child1_file = ac_store / "ACS-503a-1.yaml"
            child1_file.write_text(
                _CHILD_YAML_TEMPLATE.format(
                    child_id="ACS-503a-1",
                    parent_id="ACS-503a",
                )
            )

            child2_file = ac_store / "ACS-503a-2.yaml"
            child2_file.write_text(
                _CHILD_YAML_TEMPLATE.format(
                    child_id="ACS-503a-2",
                    parent_id="ACS-503a",
                )
            )

            self._set_env("HOOK_ROOT", tmpdir)
            # Stage both children
            staged = os.pathsep.join([str(child1_file), str(child2_file)])
            self._set_env("HOOK_TEST_FILES", staged)

            result = self.mod.main()

            # child-1 is in covered_by → no violation; child-2 is not → 1 violation
            self.assertEqual(
                result,
                1,
                "Expected exit code 1: parent lists child-1 but omits child-2; "
                f"got exit code {result}",
            )

    def test_multiple_children_parent_missing_one_violation_names_missing_child(self):
        """Violation message for the missing child must name the missing child ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_store = Path(tmpdir) / "docs" / "acceptance-criteria" / "ACS-503b"
            ac_store.mkdir(parents=True)

            parent_file = ac_store / "ACS-503b.yaml"
            parent_file.write_text(
                _PARENT_YAML_TEMPLATE.format(
                    parent_id="ACS-503b",
                    covered_by="[ACS-503b-1]",
                )
            )

            child1_file = ac_store / "ACS-503b-1.yaml"
            child1_file.write_text(
                _CHILD_YAML_TEMPLATE.format(
                    child_id="ACS-503b-1",
                    parent_id="ACS-503b",
                )
            )

            child2_file = ac_store / "ACS-503b-2.yaml"
            child2_file.write_text(
                _CHILD_YAML_TEMPLATE.format(
                    child_id="ACS-503b-2",
                    parent_id="ACS-503b",
                )
            )

            self._set_env("HOOK_ROOT", tmpdir)
            derive_fn = self.mod._get_derive_parent_id()

            violations_child1 = self.mod._check_file(str(child1_file), derive_fn)
            violations_child2 = self.mod._check_file(str(child2_file), derive_fn)

            self.assertEqual(violations_child1, [], "child-1 is in covered_by; must not violate")
            self.assertEqual(len(violations_child2), 1, "child-2 is missing; must produce 1 violation")
            self.assertIn("ACS-503b-2", violations_child2[0])

    # ------------------------------------------------------------------
    # Scenario 8: child AC staged alongside its parent AC (both in same commit)
    # ------------------------------------------------------------------

    def test_child_and_parent_both_staged_parent_correct(self):
        """Both child and parent are staged; parent on disk already has correct covered_by.

        The hook reads the parent from disk (not from the git index). If the
        parent file on disk is correctly updated before the pre-commit hook runs,
        both staged files should pass with exit 0.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_store = Path(tmpdir) / "docs" / "acceptance-criteria" / "ACS-504a"
            ac_store.mkdir(parents=True)

            parent_file = ac_store / "ACS-504a.yaml"
            parent_file.write_text(
                _PARENT_YAML_TEMPLATE.format(
                    parent_id="ACS-504a",
                    covered_by="[ACS-504a-1]",
                )
            )

            child_file = ac_store / "ACS-504a-1.yaml"
            child_file.write_text(
                _CHILD_YAML_TEMPLATE.format(
                    child_id="ACS-504a-1",
                    parent_id="ACS-504a",
                )
            )

            self._set_env("HOOK_ROOT", tmpdir)
            # Stage both parent and child
            staged = os.pathsep.join([str(parent_file), str(child_file)])
            self._set_env("HOOK_TEST_FILES", staged)

            result = self.mod.main()

            self.assertEqual(
                result,
                0,
                "Child + parent staged together with correct covered_by must exit 0; "
                f"got exit code {result}",
            )

    def test_child_and_parent_both_staged_parent_missing_child(self):
        """Both staged but parent on disk does NOT list the child — must block.

        Even though both files are staged, the hook reads parent from disk and
        finds the child absent from covered_by. Must exit 1.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_store = Path(tmpdir) / "docs" / "acceptance-criteria" / "ACS-504b"
            ac_store.mkdir(parents=True)

            parent_file = ac_store / "ACS-504b.yaml"
            parent_file.write_text(
                _PARENT_YAML_TEMPLATE.format(
                    parent_id="ACS-504b",
                    covered_by="[]",  # parent NOT updated
                )
            )

            child_file = ac_store / "ACS-504b-1.yaml"
            child_file.write_text(
                _CHILD_YAML_TEMPLATE.format(
                    child_id="ACS-504b-1",
                    parent_id="ACS-504b",
                )
            )

            self._set_env("HOOK_ROOT", tmpdir)
            staged = os.pathsep.join([str(parent_file), str(child_file)])
            self._set_env("HOOK_TEST_FILES", staged)

            result = self.mod.main()

            self.assertEqual(
                result,
                1,
                "Parent staged but covered_by empty must still block; "
                f"got exit code {result}",
            )

    # ------------------------------------------------------------------
    # Scenario 9: YAML file outside docs/acceptance-criteria/ path
    # ------------------------------------------------------------------

    def test_yaml_outside_ac_store_via_hook_test_files_is_processed(self):
        """A YAML outside docs/acceptance-criteria/ injected via HOOK_TEST_FILES.

        _get_staged_ac_paths() does NOT filter HOOK_TEST_FILES by path prefix —
        it only filters by .yaml extension. So the hook WILL attempt to process
        a YAML from any path when injected via HOOK_TEST_FILES.

        If the file has no 'id' field, the hook skips it cleanly (no violation,
        no crash). This scenario verifies the hook doesn't crash on out-of-tree
        files.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # No AC store — file is outside any AC path
            outside_dir = Path(tmpdir) / "config"
            outside_dir.mkdir(parents=True)

            outside_file = outside_dir / "settings.yaml"
            outside_file.write_text(
                textwrap.dedent(
                    """\
                    version: 1
                    debug: false
                    database_url: sqlite:///app.db
                    """
                )
            )

            # AC store does not exist in this tmpdir → main() exits 0 early
            self._set_env("HOOK_ROOT", tmpdir)
            self._set_env("HOOK_TEST_FILES", str(outside_file))

            result = self.mod.main()

            # main() exits 0 because there is no AC store directory
            self.assertEqual(
                result,
                0,
                "YAML outside AC store path must not block (no AC store → exit 0); "
                f"got exit code {result}",
            )

    def test_yaml_outside_ac_store_with_ac_store_present(self):
        """Out-of-tree YAML injected via HOOK_TEST_FILES when AC store exists.

        When the AC store directory IS present, main() proceeds to call _check_file
        on the injected path regardless of its location. If the out-of-tree file
        has no 'id' field, _check_file skips it (no violation, no crash).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create AC store directory so main() doesn't exit early
            ac_store = Path(tmpdir) / "docs" / "acceptance-criteria"
            ac_store.mkdir(parents=True)

            # File outside AC store path
            outside_dir = Path(tmpdir) / "config"
            outside_dir.mkdir(parents=True)
            outside_file = outside_dir / "myconfig.yaml"
            outside_file.write_text("key: value\nother: 123\n")

            self._set_env("HOOK_ROOT", tmpdir)
            self._set_env("HOOK_TEST_FILES", str(outside_file))

            result = self.mod.main()

            # No 'id' field → skipped → no violation
            self.assertEqual(
                result,
                0,
                "Out-of-tree YAML with no 'id' field must be skipped (exit 0); "
                f"got exit code {result}",
            )

    # ------------------------------------------------------------------
    # Scenario 10: .yaml extension with binary (non-UTF-8) content
    # ------------------------------------------------------------------

    def test_binary_content_yaml_file_fails_open(self):
        """A .yaml file with binary (non-UTF-8) content must not crash the hook.

        _load_file_yaml uses path.read_text(encoding='utf-8'). Binary content
        raises UnicodeDecodeError, which is NOT a subclass of OSError and is
        therefore NOT caught by the 'except OSError' guard in _load_file_yaml.

        Expected (correct) behaviour: hook fails open — exit 0, no crash.
        Current behaviour: UnicodeDecodeError propagates uncaught through
        _check_file and main(), causing main() to raise instead of return 1 or 0.

        NOTE: This test documents a real bug. It is written to assert the
        *desired* fail-open behaviour. If the test fails with UnicodeDecodeError,
        that is a confirmed bug in _load_file_yaml (except clause should also
        catch ValueError / UnicodeDecodeError).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_store = Path(tmpdir) / "docs" / "acceptance-criteria"
            ac_store.mkdir(parents=True)

            binary_file = ac_store / "ACS-505a.yaml"
            # Write non-UTF-8 binary bytes (Latin-1 encoded text with high bytes)
            binary_file.write_bytes(b"\xff\xfe\x00id:\x00 \x00A\x00C\x00S\x00")

            self._set_env("HOOK_ROOT", tmpdir)
            self._set_env("HOOK_TEST_FILES", str(binary_file))

            # The hook MUST fail open: either return 0 or silently skip the file.
            # If this raises UnicodeDecodeError, it is a confirmed implementation bug.
            try:
                result = self.mod.main()
            except UnicodeDecodeError as exc:
                self.fail(
                    f"BUG: _load_file_yaml does not catch UnicodeDecodeError. "
                    f"Binary .yaml files crash the hook instead of failing open. "
                    f"Fix: add 'except (OSError, ValueError)' in _load_file_yaml. "
                    f"Exception: {exc}"
                )

            self.assertEqual(
                result,
                0,
                "Binary .yaml file must fail open (exit 0); "
                f"got exit code {result}",
            )


if __name__ == "__main__":
    unittest.main()
