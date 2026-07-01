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
        return [AcNode(ac_id=i, level=lvl, depends_on=d) for i, lvl, d in specs]

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
        return [AcNode(ac_id=i, level=lvl, depends_on=d) for i, lvl, d in specs]

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
        return [AcNode(ac_id=i, level=lvl, depends_on=d) for i, lvl, d in specs]

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

            staged = [f"docs/acceptance-criteria/ACS-100{suffix}.yaml" for suffix in "abc"]
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


# ---------------------------------------------------------------------------
# Regression test for GE-106: cross-link depends_on entries inflate child count
# ---------------------------------------------------------------------------


class TestBuildChildrenMapCrossLinkBug(unittest.TestCase):
    """Regression test for GE-106: _build_children_map must attribute each L2
    node to its id-derived structural parent only, NOT to every same-tier
    depends_on entry.

    Bug symptom: an L2 node whose depends_on lists a sibling L1 as a cross-link
    (in addition to its true structural parent) was incorrectly counted as a
    child of that sibling L1, inflating its child count and causing false
    "exceeds max 5" blocks.

    Example: INF-400e-1 has depends_on=[INF-400e, INF-400a].  Its structural
    parent is INF-400e (derived from its id).  The buggy code appended it to
    INF-400a's children as well, because INF-400a also appears in depends_on
    at the correct level (L1 → L2 mapping).
    """

    def _nodes(self, specs: list[tuple[str, str, list[str]]]) -> list:
        """Build AcNode list from (id, level, depends_on) tuples."""
        return [AcNode(ac_id=i, level=lv, depends_on=d) for i, lv, d in specs]

    @_requires_import
    def test_ac_ge106_cross_link_does_not_inflate_sibling_l1_child_count(self) -> None:
        # covers: GE-106
        """GE-106: L2 nodes that cross-link a sibling L1 in depends_on must NOT
        be counted as children of that sibling L1.

        Scenario:
          INF-900  (L0)  — root
          INF-900a (L1)  — parent under test; true id-derived children are
                           INF-900a-1 and INF-900a-2 only  (count = 2)
          INF-900b (L1)  — sibling L1; structural parent of INF-900b-{1,2,3}
          INF-900a-1 (L2) — structural child of INF-900a; depends_on=[INF-900a]
          INF-900a-2 (L2) — structural child of INF-900a; depends_on=[INF-900a]
          INF-900b-1 (L2) — structural child of INF-900b; CROSS-LINKS INF-900a
                            depends_on=[INF-900b, INF-900a]
          INF-900b-2 (L2) — same; depends_on=[INF-900b, INF-900a]
          INF-900b-3 (L2) — same; depends_on=[INF-900b, INF-900a]

        The buggy _build_children_map iterates over ALL depends_on entries and
        appends INF-900b-{1,2,3} to INF-900a's children (because INF-900a is L1
        and those nodes are L2, so the level pair matches).  This produces a
        spurious child count of 5 for INF-900a.

        The CORRECT behaviour is: INF-900a has exactly 2 id-derived children.
        This assertion FAILS against the current (unmodified) code, confirming
        the red baseline for GE-106.
        """
        nodes = self._nodes([
            # Root
            ("INF-900",   "L0", []),
            # L1 pair
            ("INF-900a",  "L1", ["INF-900"]),
            ("INF-900b",  "L1", ["INF-900"]),
            # True id-derived children of INF-900a
            ("INF-900a-1", "L2", ["INF-900a"]),
            ("INF-900a-2", "L2", ["INF-900a"]),
            # Children of INF-900b that ALSO cross-link INF-900a in depends_on
            ("INF-900b-1", "L2", ["INF-900b", "INF-900a"]),
            ("INF-900b-2", "L2", ["INF-900b", "INF-900a"]),
            ("INF-900b-3", "L2", ["INF-900b", "INF-900a"]),
        ])

        cm = _build_children_map(nodes)

        # INF-900a must have exactly 2 id-derived children.
        # Against the CURRENT buggy code this assertion FAILS (count is 5).
        self.assertEqual(
            len(cm["INF-900a"]),
            2,
            msg=(
                "GE-106 regression: INF-900a should have 2 id-derived children "
                f"(INF-900a-1, INF-900a-2) but _build_children_map counted "
                f"{len(cm['INF-900a'])} — cross-linked siblings are being "
                "incorrectly attributed to INF-900a via depends_on membership."
            ),
        )

    @_requires_import
    def test_ac_ge106_sibling_l1_retains_its_own_children(self) -> None:
        # covers: GE-106
        """GE-106 companion: INF-900b must still have its own 3 structural children.

        Even after the fix, the cross-linking nodes must remain attributed to
        INF-900b (their id-derived parent) and not be lost.
        Against the current buggy code this test PASSES because the buggy code
        still appends cross-linking nodes to INF-900b as well (it appends to
        BOTH parents).  This test documents the expected correct count for
        INF-900b as 3 and serves as a guard against over-correction.
        """
        nodes = [AcNode(ac_id=i, level=lv, depends_on=d) for i, lv, d in [
            ("INF-900",   "L0", []),
            ("INF-900a",  "L1", ["INF-900"]),
            ("INF-900b",  "L1", ["INF-900"]),
            ("INF-900a-1", "L2", ["INF-900a"]),
            ("INF-900a-2", "L2", ["INF-900a"]),
            ("INF-900b-1", "L2", ["INF-900b", "INF-900a"]),
            ("INF-900b-2", "L2", ["INF-900b", "INF-900a"]),
            ("INF-900b-3", "L2", ["INF-900b", "INF-900a"]),
        ]]
        cm = _build_children_map(nodes)
        self.assertEqual(
            len(cm["INF-900b"]),
            3,
            msg=(
                "INF-900b must have 3 id-derived children "
                "(INF-900b-1, INF-900b-2, INF-900b-3)."
            ),
        )

    @_requires_import
    def test_ac_ge106_false_violation_not_raised_when_within_limit(self) -> None:
        # covers: GE-106
        """GE-106 end-to-end: a parent with 2 true children and 3 cross-linked
        siblings must NOT trigger a 'exceeds max 5' hard violation even when
        one of its true children is staged.

        This mirrors the original bug symptom: INF-400a blocked commits because
        cross-linked L2s inflated its count to 9, past the limit of 5.

        Against the current buggy code, INF-900a's child count is 5 — exactly
        at the limit, so no violation fires for this particular scenario.
        A stronger variant (5 cross-linked siblings instead of 3) would fire.
        We use 5 cross-linked siblings to guarantee the test is RED right now.
        """
        # Extend the cross-link set to 5 siblings so the buggy count (2+5=7)
        # exceeds the limit of 5 and the violation fires under the buggy code.
        specs = [
            ("INF-900",   "L0", []),
            ("INF-900a",  "L1", ["INF-900"]),
            ("INF-900b",  "L1", ["INF-900"]),
            # 2 genuine children of INF-900a
            ("INF-900a-1", "L2", ["INF-900a"]),
            ("INF-900a-2", "L2", ["INF-900a"]),
            # 5 children of INF-900b that cross-link INF-900a
            ("INF-900b-1", "L2", ["INF-900b", "INF-900a"]),
            ("INF-900b-2", "L2", ["INF-900b", "INF-900a"]),
            ("INF-900b-3", "L2", ["INF-900b", "INF-900a"]),
            ("INF-900b-4", "L2", ["INF-900b", "INF-900a"]),
            ("INF-900b-5", "L2", ["INF-900b", "INF-900a"]),
        ]
        nodes = [AcNode(ac_id=i, level=lv, depends_on=d) for i, lv, d in specs]
        cm = _build_children_map(nodes)
        # Stage one genuine child of INF-900a
        staged_ids = {"INF-900a-1"}
        violations, _ = _check_limits(nodes, cm, staged_ids)

        violation_parents = [v.parent_id for v in violations]
        self.assertNotIn(
            "INF-900a",
            violation_parents,
            msg=(
                "GE-106 regression: INF-900a has only 2 id-derived children and "
                "must NOT appear in violations. Current buggy code counts "
                "cross-linked siblings in depends_on and inflates the count to 7, "
                f"triggering a false violation. violations={violations}"
            ),
        )


# ---------------------------------------------------------------------------
# Tests for ACS-100c-6: superseded children excluded from child-count cap
# ---------------------------------------------------------------------------


def _make_l2_superseded(ac_id: str, parent_l1: str, status: str) -> str:
    """Minimal L2 AC YAML with an explicit status field.

    Args:
        ac_id: The AC identifier string.
        parent_l1: ID of the L1 parent.
        status: The status string (e.g. 'superseded_by', 'superseded', 'active').

    Returns:
        YAML content as a string.
    """
    return textwrap.dedent(f"""\
        id: {ac_id}
        title: "L2 behavior"
        level: L2
        component: test-component
        status: {status}
        depends_on:
          - {parent_l1}
        criteria: |
          Given something
          When something
          Then {ac_id}
    """)


class TestSupersededChildrenExcludedFromCount(unittest.TestCase):
    """ACS-100c-6: superseded_by (and legacy superseded) children are excluded
    from the child-count cap enforced by _check_limits.

    All four tests in this class are RED against the current code because
    AcNode has no 'status' field and _check_limits uses len(children) without
    any status filtering.
    """

    def _make_node(
        self,
        ac_id: str,
        level: str,
        depends_on: list[str],
        status: str = "active",
        child_limit_override: "int | None" = None,
    ) -> "AcNode":
        """Build an AcNode with a status attribute and optional override.

        The current AcNode dataclass does NOT have a status field. This helper
        calls AcNode and then attempts to set node.status, which is the
        interface the fixed code must provide. Against the current code,
        constructing with a status kwarg raises TypeError (RED signal).

        Args:
            ac_id: AC identifier.
            level: AC level string.
            depends_on: List of dependency ID strings.
            status: Status string — 'active', 'superseded_by', or 'superseded'.
            child_limit_override: Optional integer override for the child cap.

        Returns:
            AcNode with status and optional child_limit_override set.
        """
        return AcNode(
            ac_id=ac_id,
            level=level,
            depends_on=depends_on,
            status=status,
            child_limit_override=child_limit_override,
        )

    @_requires_import
    def test_acs100c6_at_cap_with_one_superseded_passes(self) -> None:
        # covers: ACS-100c-6
        """ACS-100c-6 scenario 1: parent at cap=5 with 1 superseded_by child.

        Effective count = 4 active children → does NOT exceed cap of 5 → PASSES.
        Against the current code this test is RED because:
          - AcNode has no 'status' kwarg → TypeError on construction, OR
          - _check_limits counts all 5 children without filtering → violation
            fires when it should not.
        """
        # 5 children total; 1 has status superseded_by
        nodes = [
            self._make_node("ACS-200", "L0", []),
            self._make_node("ACS-200a", "L1", ["ACS-200"]),
            self._make_node("ACS-200a-1", "L2", ["ACS-200a"], status="active"),
            self._make_node("ACS-200a-2", "L2", ["ACS-200a"], status="active"),
            self._make_node("ACS-200a-3", "L2", ["ACS-200a"], status="active"),
            self._make_node("ACS-200a-4", "L2", ["ACS-200a"], status="active"),
            self._make_node("ACS-200a-5", "L2", ["ACS-200a"], status="superseded_by"),
        ]
        cm = _build_children_map(nodes)
        staged_ids = {"ACS-200a-4"}  # one active child staged
        violations, _ = _check_limits(nodes, cm, staged_ids)

        self.assertEqual(
            violations,
            [],
            msg=(
                "ACS-100c-6: parent 'ACS-200a' has 5 children but 1 is superseded_by; "
                "effective count=4 must not exceed cap=5. "
                f"Got violations: {violations}"
            ),
        )

    @_requires_import
    def test_acs100c6_all_children_superseded_passes(self) -> None:
        # covers: ACS-100c-6-i
        """ACS-100c-6-i: ALL children superseded_by → effective count = 0 → PASSES.

        Against the current code this test is RED because _check_limits counts
        all children regardless of status, so the effective count equals the
        total child count and a sparse advisory (not a violation) fires.
        More critically AcNode has no 'status' field → TypeError on construction.
        """
        nodes = [
            self._make_node("ACS-300", "L0", []),
            self._make_node("ACS-300a", "L1", ["ACS-300"]),
            self._make_node("ACS-300a-1", "L2", ["ACS-300a"], status="superseded_by"),
            self._make_node("ACS-300a-2", "L2", ["ACS-300a"], status="superseded_by"),
            self._make_node("ACS-300a-3", "L2", ["ACS-300a"], status="superseded_by"),
        ]
        cm = _build_children_map(nodes)
        staged_ids = {"ACS-300a-1"}
        violations, _ = _check_limits(nodes, cm, staged_ids)

        self.assertEqual(
            violations,
            [],
            msg=(
                "ACS-100c-6-i: all 3 children are superseded_by; "
                "effective count=0 must not trigger a violation. "
                f"Got violations: {violations}"
            ),
        )

    @_requires_import
    def test_acs100c6_override_composes_with_filtered_count(self) -> None:
        # covers: ACS-100c-6-ii
        """ACS-100c-6-ii: status exclusion composes with child_limit_override.

        Setup: override=7, default=5, 7 children total with 3 superseded_by.
        Filtered count = 4; effective cap = max(5, 7) = 7.
        4 < 7 → PASSES.

        Against the current code:
          - AcNode has no 'status' kwarg → TypeError on construction, OR
          - count = 7 (no filtering); cap = max(5,7) = 7; 7 is NOT > 7
            → no violation fires today, BUT the filtered count would be
            incorrectly 7 (not 4). The test asserts the FILTERED count is
            used, so we also verify no false violation occurs AND that the
            raw total would only pass because of the override (which is the
            wrong reason). We confirm this by asserting no violation fires
            when filtered count=4 < default=5 (override not needed). To make
            this RED we push the raw count beyond the override too: 8 children,
            3 superseded → filtered=5, raw=8; raw>7 fires a violation under
            the current code but filtered=5 <= cap=7 must pass.
        """
        # 8 children raw, 3 superseded_by, filtered = 5; override=7
        # Current code: raw=8 > effective cap=7 → violation (RED).
        # Fixed code: filtered=5 <= 7 → passes.
        nodes = [
            self._make_node("ACS-400", "L0", []),
            self._make_node("ACS-400a", "L1", ["ACS-400"], child_limit_override=7),
            self._make_node("ACS-400a-1", "L2", ["ACS-400a"], status="active"),
            self._make_node("ACS-400a-2", "L2", ["ACS-400a"], status="active"),
            self._make_node("ACS-400a-3", "L2", ["ACS-400a"], status="active"),
            self._make_node("ACS-400a-4", "L2", ["ACS-400a"], status="active"),
            self._make_node("ACS-400a-5", "L2", ["ACS-400a"], status="active"),
            self._make_node("ACS-400a-6", "L2", ["ACS-400a"], status="superseded_by"),
            self._make_node("ACS-400a-7", "L2", ["ACS-400a"], status="superseded_by"),
            self._make_node("ACS-400a-8", "L2", ["ACS-400a"], status="superseded_by"),
        ]
        cm = _build_children_map(nodes)
        staged_ids = {"ACS-400a-5"}
        violations, _ = _check_limits(nodes, cm, staged_ids)

        self.assertEqual(
            violations,
            [],
            msg=(
                "ACS-100c-6-ii: 8 children total, 3 superseded_by → filtered=5; "
                "override=7; effective cap=max(5,7)=7; 5 <= 7 must pass. "
                f"Got violations: {violations}"
            ),
        )

    @_requires_import
    def test_acs100c6_legacy_superseded_status_also_excluded(self) -> None:
        # covers: ACS-100c-6
        """Legacy 'superseded' (not 'superseded_by') is also excluded.

        Same structure as scenario 1 but with the legacy 'superseded' spelling.
        Effective count = 4 active children → does NOT exceed cap of 5 → PASSES.
        Against the current code this test is RED for the same reasons as
        test_acs100c6_at_cap_with_one_superseded_passes.
        """
        nodes = [
            self._make_node("ACS-500", "L0", []),
            self._make_node("ACS-500a", "L1", ["ACS-500"]),
            self._make_node("ACS-500a-1", "L2", ["ACS-500a"], status="active"),
            self._make_node("ACS-500a-2", "L2", ["ACS-500a"], status="active"),
            self._make_node("ACS-500a-3", "L2", ["ACS-500a"], status="active"),
            self._make_node("ACS-500a-4", "L2", ["ACS-500a"], status="active"),
            self._make_node("ACS-500a-5", "L2", ["ACS-500a"], status="superseded"),
        ]
        cm = _build_children_map(nodes)
        staged_ids = {"ACS-500a-4"}
        violations, _ = _check_limits(nodes, cm, staged_ids)

        self.assertEqual(
            violations,
            [],
            msg=(
                "ACS-100c-6 legacy: parent 'ACS-500a' has 5 children but 1 has "
                "legacy status='superseded'; effective count=4 must not exceed cap=5. "
                f"Got violations: {violations}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
