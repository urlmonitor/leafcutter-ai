"""
MODULE: test_check_ac_limits
GOAL: Unit tests for the check_ac_limits.py pre-commit hook that enforces
    AC tree depth limits (ACS-100c-1 hard cap and ACS-100c-2 advisory).
BUSINESS CONTEXT: Verifies that the validator correctly blocks commits when a
    parent AC would exceed its child count limit (>7 L1s per L0, >5 L2s per
    L1) and emits a non-blocking advisory when a parent has fewer than 3
    children.
ARCHITECTURE: Tests call the hook module's internal functions directly (not
    via subprocess) to keep tests fast and deterministic. A small number of
    subprocess integration tests verify the CLI exit-code contract. Temporary
    directories and HOOK_TEST_FILES / HOOK_ROOT env vars are used to isolate
    filesystem state. All tests complete in < 5 seconds.

# covers: ACS-100c-1
# covers: ACS-100c-2
# covers: ACS-100a-6
"""

from __future__ import annotations

import importlib.util
import sys
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HOOK_SCRIPT = _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_ac_limits.py"

# Load the module directly from the scripts path using importlib to avoid
# package import issues (the hook is a standalone file, not a proper package).
# The module must be added to sys.modules before exec_module so that the
# @dataclass decorator can resolve the module namespace correctly (Python 3.12).
try:
    _MODULE_NAME = "check_ac_limits_test_shim"
    _spec = importlib.util.spec_from_file_location(_MODULE_NAME, _HOOK_SCRIPT)
    _mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
    sys.modules[_MODULE_NAME] = _mod
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
    _load_yaml_data = _mod._load_yaml_data
    _parse_depends_on = _mod._parse_depends_on
    _load_ac_store = _mod._load_ac_store
    _build_children_map = _mod._build_children_map
    _check_limits = _mod._check_limits
    AcNode = _mod.AcNode
    _IMPORT_OK = True
except (FileNotFoundError, AttributeError, ImportError, SyntaxError, TypeError, ValueError) as _exc:
    _IMPORT_OK = False
    _IMPORT_ERROR = str(_exc)


def _requires_import(func):
    """Skip test if the hook module failed to import."""
    if not _IMPORT_OK:
        return unittest.skip(f"check_ac_limits not importable: {_IMPORT_ERROR}")(func)
    return func


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_ac(directory: Path, filename: str, content: str) -> Path:
    """Write a YAML AC file under directory/docs/acceptance-criteria/.

    Args:
        directory: Temporary root directory.
        filename: Relative filename (e.g. 'ACS-100.yaml').
        content: YAML content string.

    Returns:
        Path to the written file.
    """
    ac_dir = directory / "docs" / "acceptance-criteria"
    target = ac_dir / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def _make_l0(ac_id: str) -> str:
    """Minimal valid L0 AC YAML string.

    Args:
        ac_id: The AC identifier string.

    Returns:
        YAML content as a string.
    """
    return textwrap.dedent(f"""\
        id: {ac_id}
        title: "L0 goal"
        level: L0
        component: test-component
        status: active
        depends_on: []
        criteria: |
          Tagline for {ac_id}
    """)


def _make_l1(ac_id: str, parent_l0: str) -> str:
    """Minimal valid L1 AC YAML string.

    Args:
        ac_id: The AC identifier string.
        parent_l0: ID of the L0 parent.

    Returns:
        YAML content as a string.
    """
    return textwrap.dedent(f"""\
        id: {ac_id}
        title: "L1 feature"
        level: L1
        component: test-component
        status: active
        depends_on:
          - {parent_l0}
        criteria: |
          Feature tagline for {ac_id}
    """)


def _make_l2(ac_id: str, parent_l1: str) -> str:
    """Minimal valid L2 AC YAML string.

    Args:
        ac_id: The AC identifier string.
        parent_l1: ID of the L1 parent.

    Returns:
        YAML content as a string.
    """
    return textwrap.dedent(f"""\
        id: {ac_id}
        title: "L2 behavior"
        level: L2
        component: test-component
        status: active
        depends_on:
          - {parent_l1}
        criteria: |
          Given something
          When something
          Then {ac_id}
    """)


# ---------------------------------------------------------------------------
# Unit tests for _parse_depends_on
# ---------------------------------------------------------------------------


class TestParseDependsOn(unittest.TestCase):
    """_parse_depends_on handles all YAML representations of the field."""

    @_requires_import
    def test_list_input(self) -> None:
        """A YAML list depends_on parses to a list of strings."""
        result = _parse_depends_on(["ACS-100", "ACS-200"])
        self.assertEqual(result, ["ACS-100", "ACS-200"])

    @_requires_import
    def test_none_input(self) -> None:
        """None depends_on returns an empty list."""
        result = _parse_depends_on(None)
        self.assertEqual(result, [])

    @_requires_import
    def test_empty_list(self) -> None:
        """Empty list depends_on returns an empty list."""
        result = _parse_depends_on([])
        self.assertEqual(result, [])

    @_requires_import
    def test_string_single(self) -> None:
        """A bare string depends_on returns a single-element list."""
        result = _parse_depends_on("ACS-100")
        self.assertEqual(result, ["ACS-100"])

    @_requires_import
    def test_string_comma_separated(self) -> None:
        """Inline YAML list string parses to multiple elements."""
        result = _parse_depends_on("[ACS-100, ACS-200]")
        self.assertEqual(result, ["ACS-100", "ACS-200"])


# ---------------------------------------------------------------------------
# Unit tests for _build_children_map
# ---------------------------------------------------------------------------


class TestBuildChildrenMap(unittest.TestCase):
    """_build_children_map correctly derives parent->children from AcNode list."""

    def _nodes(self, specs: list[tuple[str, str, list[str]]]) -> list:
        """Build AcNode list from (id, level, depends_on) tuples.

        Args:
            specs: List of (ac_id, level, depends_on) tuples.

        Returns:
            List of AcNode objects.
        """
        return [AcNode(ac_id=i, level=l, depends_on=d) for i, l, d in specs]

    @_requires_import
    def test_single_l0_with_l1_children(self) -> None:
        """An L0 with 3 L1 children appears in the children map with count 3."""
        nodes = self._nodes([
            ("ACS-100", "L0", []),
            ("ACS-100a", "L1", ["ACS-100"]),
            ("ACS-100b", "L1", ["ACS-100"]),
            ("ACS-100c", "L1", ["ACS-100"]),
        ])
        cm = _build_children_map(nodes)
        self.assertEqual(len(cm["ACS-100"]), 3)

    @_requires_import
    def test_l1_with_l2_children(self) -> None:
        """An L1 with 2 L2 children appears in the children map with count 2."""
        nodes = self._nodes([
            ("ACS-100", "L0", []),
            ("ACS-100a", "L1", ["ACS-100"]),
            ("ACS-100a-1", "L2", ["ACS-100a"]),
            ("ACS-100a-2", "L2", ["ACS-100a"]),
        ])
        cm = _build_children_map(nodes)
        self.assertEqual(len(cm["ACS-100a"]), 2)
        self.assertEqual(len(cm["ACS-100"]), 1)

    @_requires_import
    def test_no_children(self) -> None:
        """An L0 with no L1 children has an empty children list."""
        nodes = self._nodes([("ACS-100", "L0", [])])
        cm = _build_children_map(nodes)
        self.assertEqual(cm.get("ACS-100", []), [])

    @_requires_import
    def test_cross_level_link_not_counted(self) -> None:
        """An L2 depending on an L0 is NOT counted as an L0 child (wrong level pair)."""
        nodes = self._nodes([
            ("ACS-100", "L0", []),
            ("ACS-100a-1", "L2", ["ACS-100"]),  # L2 depending on L0 — wrong pair
        ])
        cm = _build_children_map(nodes)
        # L0->L1 children: none (ACS-100a-1 is L2, not L1)
        self.assertEqual(len(cm.get("ACS-100", [])), 0)


# ---------------------------------------------------------------------------
# Unit tests for _check_limits — hard violations
# ---------------------------------------------------------------------------


class TestCheckLimitsHardCap(unittest.TestCase):
    """_check_limits emits TreeViolation when parent exceeds its child limit."""

    def _nodes(self, specs: list[tuple[str, str, list[str]]]) -> list:
        return [AcNode(ac_id=i, level=l, depends_on=d) for i, l, d in specs]

    @_requires_import
    def test_l0_over_7_l1s_blocks(self) -> None:
        """L0 with 8 L1 children triggers a violation."""
        specs: list[tuple[str, str, list[str]]] = [("ACS-100", "L0", [])]
        l1_ids = [f"ACS-100{c}" for c in "abcdefgh"]  # 8 children
        for l1_id in l1_ids:
            specs.append((l1_id, "L1", ["ACS-100"]))

        nodes = self._nodes(specs)
        cm = _build_children_map(nodes)
        staged_ids = set(l1_ids)
        violations, advisories = _check_limits(nodes, cm, staged_ids)

        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].parent_id, "ACS-100")
        self.assertEqual(violations[0].child_count, 8)
        self.assertEqual(violations[0].limit, 7)

    @_requires_import
    def test_l0_with_exactly_7_l1s_passes(self) -> None:
        """L0 with exactly 7 L1 children does NOT trigger a violation."""
        specs: list[tuple[str, str, list[str]]] = [("ACS-100", "L0", [])]
        l1_ids = [f"ACS-100{c}" for c in "abcdefg"]  # exactly 7
        for l1_id in l1_ids:
            specs.append((l1_id, "L1", ["ACS-100"]))

        nodes = self._nodes(specs)
        cm = _build_children_map(nodes)
        staged_ids = set(l1_ids)
        violations, _ = _check_limits(nodes, cm, staged_ids)

        self.assertEqual(violations, [])

    @_requires_import
    def test_l1_over_5_l2s_blocks(self) -> None:
        """L1 with 6 L2 children triggers a violation."""
        specs: list[tuple[str, str, list[str]]] = [
            ("ACS-100", "L0", []),
            ("ACS-100a", "L1", ["ACS-100"]),
        ]
        l2_ids = [f"ACS-100a-{i}" for i in range(1, 7)]  # 6 children
        for l2_id in l2_ids:
            specs.append((l2_id, "L2", ["ACS-100a"]))

        nodes = self._nodes(specs)
        cm = _build_children_map(nodes)
        staged_ids = set(l2_ids)
        violations, _ = _check_limits(nodes, cm, staged_ids)

        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].parent_id, "ACS-100a")
        self.assertEqual(violations[0].child_count, 6)
        self.assertEqual(violations[0].limit, 5)

    @_requires_import
    def test_l1_with_exactly_5_l2s_passes(self) -> None:
        """L1 with exactly 5 L2 children does NOT trigger a violation."""
        specs: list[tuple[str, str, list[str]]] = [
            ("ACS-100", "L0", []),
            ("ACS-100a", "L1", ["ACS-100"]),
        ]
        l2_ids = [f"ACS-100a-{i}" for i in range(1, 6)]  # exactly 5
        for l2_id in l2_ids:
            specs.append((l2_id, "L2", ["ACS-100a"]))

        nodes = self._nodes(specs)
        cm = _build_children_map(nodes)
        staged_ids = set(l2_ids)
        violations, _ = _check_limits(nodes, cm, staged_ids)

        self.assertEqual(violations, [])

    @_requires_import
    def test_unstaged_overcrowded_parent_not_flagged(self) -> None:
        """An overcrowded L0 is NOT flagged when none of its children are staged."""
        specs: list[tuple[str, str, list[str]]] = [("ACS-100", "L0", [])]
        l1_ids = [f"ACS-100{c}" for c in "abcdefgh"]  # 8 children
        for l1_id in l1_ids:
            specs.append((l1_id, "L1", ["ACS-100"]))

        nodes = self._nodes(specs)
        cm = _build_children_map(nodes)
        # None of the ACS-100 children staged — a different node is staged
        staged_ids = {"ACS-200a"}
        violations, _ = _check_limits(nodes, cm, staged_ids)

        # Should not flag ACS-100 since its children are not staged
        self.assertEqual(violations, [])


# ---------------------------------------------------------------------------
# Unit tests for _check_limits — sparse advisory
# ---------------------------------------------------------------------------


class TestCheckLimitsSparseAdvisory(unittest.TestCase):
    """_check_limits emits TreeAdvisory when a staged parent has fewer than 3 children."""

    def _nodes(self, specs: list[tuple[str, str, list[str]]]) -> list:
        return [AcNode(ac_id=i, level=l, depends_on=d) for i, l, d in specs]

    @_requires_import
    def test_l0_with_1_l1_child_advisory(self) -> None:
        """L0 with only 1 L1 child triggers a sparse advisory."""
        nodes = self._nodes([
            ("ACS-100", "L0", []),
            ("ACS-100a", "L1", ["ACS-100"]),
        ])
        cm = _build_children_map(nodes)
        staged_ids = {"ACS-100a"}
        _, advisories = _check_limits(nodes, cm, staged_ids)

        self.assertEqual(len(advisories), 1)
        self.assertEqual(advisories[0].parent_id, "ACS-100")
        self.assertEqual(advisories[0].child_count, 1)

    @_requires_import
    def test_l0_with_2_l1_children_advisory(self) -> None:
        """L0 with 2 L1 children triggers a sparse advisory."""
        nodes = self._nodes([
            ("ACS-100", "L0", []),
            ("ACS-100a", "L1", ["ACS-100"]),
            ("ACS-100b", "L1", ["ACS-100"]),
        ])
        cm = _build_children_map(nodes)
        staged_ids = {"ACS-100a"}
        _, advisories = _check_limits(nodes, cm, staged_ids)

        self.assertEqual(len(advisories), 1)
        self.assertEqual(advisories[0].child_count, 2)

    @_requires_import
    def test_l0_with_3_l1_children_no_advisory(self) -> None:
        """L0 with exactly 3 L1 children does NOT trigger a sparse advisory."""
        nodes = self._nodes([
            ("ACS-100", "L0", []),
            ("ACS-100a", "L1", ["ACS-100"]),
            ("ACS-100b", "L1", ["ACS-100"]),
            ("ACS-100c", "L1", ["ACS-100"]),
        ])
        cm = _build_children_map(nodes)
        staged_ids = {"ACS-100a"}
        _, advisories = _check_limits(nodes, cm, staged_ids)

        self.assertEqual(advisories, [])

    @_requires_import
    def test_advisory_does_not_block(self) -> None:
        """Sparse advisory does not produce any violations (non-blocking)."""
        nodes = self._nodes([
            ("ACS-100", "L0", []),
            ("ACS-100a", "L1", ["ACS-100"]),
        ])
        cm = _build_children_map(nodes)
        staged_ids = {"ACS-100a"}
        violations, _ = _check_limits(nodes, cm, staged_ids)

        self.assertEqual(violations, [])


# ---------------------------------------------------------------------------
# Integration tests via subprocess
# ---------------------------------------------------------------------------


class TestCheckAcLimitsCLI(unittest.TestCase):
    """CLI integration tests: verify exit codes via subprocess."""

    def _run_hook(
        self, root: Path, staged_files: list[str]
    ) -> "subprocess.CompletedProcess[str]":
        """Run check_ac_limits.py as a subprocess with env var injection.

        Args:
            root: Temporary directory acting as the repo root.
            staged_files: List of relative paths to simulate as staged.

        Returns:
            CompletedProcess with returncode, stdout, stderr.
        """
        import os

        env = os.environ.copy()
        env["HOOK_ROOT"] = str(root)
        env["HOOK_TEST_FILES"] = "\n".join(staged_files)

        return subprocess.run(
            [sys.executable, str(_HOOK_SCRIPT)],
            env=env,
            capture_output=True,
            text=True,
        )

    def test_no_staged_files_exits_zero(self) -> None:
        """Hook exits 0 when no AC YAML files are staged."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self._run_hook(root, [])
        self.assertEqual(result.returncode, 0)

    def test_no_ac_store_exits_zero(self) -> None:
        """Hook exits 0 when docs/acceptance-criteria/ does not exist."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self._run_hook(root, ["docs/acceptance-criteria/test/ACS-100a.yaml"])
        self.assertEqual(result.returncode, 0)

    def test_valid_tree_exits_zero(self) -> None:
        """Hook exits 0 when a well-formed tree (3 L1s per L0) is staged."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac(root, "ACS-100.yaml", _make_l0("ACS-100"))
            for letter in "abc":
                _write_ac(
                    root,
                    f"ACS-100{letter}.yaml",
                    _make_l1(f"ACS-100{letter}", "ACS-100"),
                )

            staged = [f"docs/acceptance-criteria/ACS-100{l}.yaml" for l in "abc"]
            result = self._run_hook(root, staged)
        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_overcrowded_l0_exits_one(self) -> None:
        """Hook exits 1 when an L0 would have 8 L1 children and one is staged."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac(root, "ACS-100.yaml", _make_l0("ACS-100"))
            letters = "abcdefgh"  # 8 L1 children
            for letter in letters:
                _write_ac(
                    root,
                    f"ACS-100{letter}.yaml",
                    _make_l1(f"ACS-100{letter}", "ACS-100"),
                )

            # Stage only the last one (the one that pushed over the limit)
            staged = ["docs/acceptance-criteria/ACS-100h.yaml"]
            result = self._run_hook(root, staged)
        self.assertEqual(result.returncode, 1, msg=result.stdout)
        self.assertIn("ACS-100c-1", result.stderr)

    def test_overcrowded_l1_exits_one(self) -> None:
        """Hook exits 1 when an L1 would have 6 L2 children and one is staged."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac(root, "ACS-100.yaml", _make_l0("ACS-100"))
            _write_ac(root, "ACS-100a.yaml", _make_l1("ACS-100a", "ACS-100"))
            for i in range(1, 7):  # 6 L2 children
                _write_ac(
                    root,
                    f"ACS-100a-{i}.yaml",
                    _make_l2(f"ACS-100a-{i}", "ACS-100a"),
                )

            staged = ["docs/acceptance-criteria/ACS-100a-6.yaml"]
            result = self._run_hook(root, staged)
        self.assertEqual(result.returncode, 1, msg=result.stdout)
        self.assertIn("ACS-100c-1", result.stderr)

    def test_sparse_advisory_exits_zero(self) -> None:
        """Hook exits 0 (no block) when a sparse parent advisory is emitted."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_ac(root, "ACS-100.yaml", _make_l0("ACS-100"))
            _write_ac(root, "ACS-100a.yaml", _make_l1("ACS-100a", "ACS-100"))
            # Only 1 L1 child — sparse advisory should fire but not block

            staged = ["docs/acceptance-criteria/ACS-100a.yaml"]
            result = self._run_hook(root, staged)
        self.assertEqual(result.returncode, 0, msg=result.stdout)
        self.assertIn("ACS-100c-2", result.stderr)


# ---------------------------------------------------------------------------
# Tests for skill deployment and registration
# ---------------------------------------------------------------------------


class TestAcTreeSplitSkillDeployment(unittest.TestCase):
    """Verifies the ac-tree-split skill is registered and deployable.

    These tests are read-only against the package source — they do not write
    any files. They confirm that:
      1. skill_registry.json contains an entry for ac-tree-split.
      2. templates/skills/ac-tree-split/SKILL.md exists on disk.
      3. The SKILL.md has the expected frontmatter fields.
    """

    _REGISTRY_PATH = _REPO_ROOT / "config" / "skill_registry.json"
    _SKILL_DIR = _REPO_ROOT / "templates" / "skills" / "ac-tree-split"
    _SKILL_MD = _SKILL_DIR / "SKILL.md"

    def test_registry_has_ac_tree_split(self) -> None:
        """skill_registry.json must include an entry with id 'ac-tree-split'."""
        import json
        with self._REGISTRY_PATH.open(encoding="utf-8") as fh:
            registry = json.load(fh)
        ids = [s["id"] for s in registry["skills"]]
        self.assertIn(
            "ac-tree-split",
            ids,
            msg="Expected 'ac-tree-split' entry in config/skill_registry.json",
        )

    def test_skill_md_exists(self) -> None:
        """templates/skills/ac-tree-split/SKILL.md must exist on disk."""
        self.assertTrue(
            self._SKILL_MD.is_file(),
            msg=f"Expected SKILL.md at {self._SKILL_MD}",
        )

    def test_skill_md_frontmatter_has_name(self) -> None:
        """SKILL.md frontmatter must include name: ac-tree-split."""
        content = self._SKILL_MD.read_text(encoding="utf-8")
        self.assertIn("name: ac-tree-split", content,
                      msg="Expected 'name: ac-tree-split' in SKILL.md frontmatter")

    def test_skill_md_frontmatter_is_portable(self) -> None:
        """SKILL.md frontmatter must declare portable: true."""
        content = self._SKILL_MD.read_text(encoding="utf-8")
        self.assertIn("portable: true", content,
                      msg="Expected 'portable: true' in SKILL.md frontmatter")

    def test_registry_entry_has_required_fields(self) -> None:
        """The ac-tree-split registry entry must have id, name, portable, domain, dependencies."""
        import json
        with self._REGISTRY_PATH.open(encoding="utf-8") as fh:
            registry = json.load(fh)
        entry = next(
            (s for s in registry["skills"] if s["id"] == "ac-tree-split"),
            None,
        )
        self.assertIsNotNone(entry, msg="No ac-tree-split entry found")
        for required_field in ("id", "name", "portable", "domain", "dependencies"):
            self.assertIn(
                required_field,
                entry,  # type: ignore[arg-type]
                msg=f"ac-tree-split entry missing required field '{required_field}'",
            )


class TestAgentTemplatesSkillsUsed(unittest.TestCase):
    """product-owner.md and business-analyst.md must reference ac-tree-split."""

    _AGENTS_DIR = _REPO_ROOT / "templates" / "agents"

    def _read_agent(self, filename: str) -> str:
        path = self._AGENTS_DIR / filename
        self.assertTrue(path.is_file(), msg=f"Agent template {filename} not found")
        return path.read_text(encoding="utf-8")

    def test_product_owner_v3_has_ac_tree_split(self) -> None:
        """product-owner.md must include ac-tree-split in skills_used."""
        content = self._read_agent("product-owner.md")
        self.assertIn(
            "ac-tree-split",
            content,
            msg="Expected 'ac-tree-split' in product-owner.md skills_used",
        )

    def test_business_analyst_v3_has_ac_tree_split(self) -> None:
        """business-analyst.md must include ac-tree-split in skills_used."""
        content = self._read_agent("business-analyst.md")
        self.assertIn(
            "ac-tree-split",
            content,
            msg="Expected 'ac-tree-split' in business-analyst.md skills_used",
        )

    def test_product_owner_v3_skills_used_is_in_frontmatter(self) -> None:
        """skills_used must appear within the frontmatter block (between --- markers)."""
        content = self._read_agent("product-owner.md")
        parts = content.split("---", 2)
        self.assertGreaterEqual(len(parts), 3, msg="No frontmatter found in product-owner.md")
        frontmatter = parts[1]
        self.assertIn(
            "skills_used",
            frontmatter,
            msg="'skills_used' must be in the frontmatter of product-owner.md",
        )
        self.assertIn(
            "ac-tree-split",
            frontmatter,
            msg="'ac-tree-split' must be in the skills_used frontmatter of product-owner.md",
        )

    def test_business_analyst_v3_skills_used_is_in_frontmatter(self) -> None:
        """skills_used must appear within the frontmatter block (between --- markers)."""
        content = self._read_agent("business-analyst.md")
        parts = content.split("---", 2)
        self.assertGreaterEqual(len(parts), 3, msg="No frontmatter found in business-analyst.md")
        frontmatter = parts[1]
        self.assertIn(
            "skills_used",
            frontmatter,
            msg="'skills_used' must be in the frontmatter of business-analyst.md",
        )
        self.assertIn(
            "ac-tree-split",
            frontmatter,
            msg="'ac-tree-split' must be in the skills_used frontmatter of business-analyst.md",
        )


class TestHookRegisteredInCommitGuardian(unittest.TestCase):
    """check_ac_limits.py must be registered in the hooks_manifest."""

    _TEMPLATE_CG_JSON = (
        _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "commit_guardian.json"
    )

    def test_hook_registered_in_template_cg_json(self) -> None:
        """commit_guardian.json hooks_manifest must include check-ac-tree-limits."""
        import json
        with self._TEMPLATE_CG_JSON.open(encoding="utf-8") as fh:
            cg = json.load(fh)
        hook_ids = [h["id"] for h in cg.get("hooks_manifest", {}).get("hooks", [])]
        self.assertIn(
            "check-ac-tree-limits",
            hook_ids,
            msg=(
                "Expected 'check-ac-tree-limits' hook in templates/"
                "scripts/commit_guardian/commit_guardian.json hooks_manifest"
            ),
        )

    def test_hook_script_exists(self) -> None:
        """templates/scripts/commit_guardian/check_ac_limits.py must exist."""
        script = _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_ac_limits.py"
        self.assertTrue(
            script.is_file(),
            msg=f"Expected check_ac_limits.py at {script}",
        )

    def test_template_hook_script_exists(self) -> None:
        """templates/scripts/commit_guardian/check_ac_limits.py must exist."""
        template_script = (
            _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_ac_limits.py"
        )
        self.assertTrue(
            template_script.is_file(),
            msg=f"Expected check_ac_limits.py template at {template_script}",
        )


if __name__ == "__main__":
    unittest.main()
