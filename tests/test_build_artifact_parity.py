"""Parity test: every template category that produces user-facing artifacts must
be wired into all four build infrastructure layers.

This test prevents the class of bug where a new template category is added as a
build phase but its supporting infrastructure (shim, manifest, stale cleanup,
drift detection) is forgotten — causing silent deployment failures.

Layers validated:
1. shim_map in install_shims() — bridges output_root paths to canonical .claude/ paths
2. _MANAGED_ARTIFACT_DIRS in build_phases.py — stale artifact cleanup coverage
3. _build_source_manifests() in build.py — source manifest for cleanup validation
4. _OUTPUT_DIRS in check_output_drift.py — drift detection coverage
"""

from __future__ import annotations

import ast
import importlib.util
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Import build modules
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

_HELPERS_PATH = _SCRIPTS_DIR / "build_helpers.py"
spec = importlib.util.spec_from_file_location("build_helpers", _HELPERS_PATH)
_helpers_mod = importlib.util.module_from_spec(spec)
sys.modules.setdefault("build_helpers", _helpers_mod)
spec.loader.exec_module(_helpers_mod)

_PHASES_PATH = _SCRIPTS_DIR / "build_phases.py"
spec2 = importlib.util.spec_from_file_location("build_phases", _PHASES_PATH)
_phases_mod = importlib.util.module_from_spec(spec2)
sys.modules.setdefault("build_phases", _phases_mod)
spec2.loader.exec_module(_phases_mod)

# ---------------------------------------------------------------------------
# Constants: the authoritative list of user-facing template categories
# ---------------------------------------------------------------------------

# Each entry: (template_dir_name, shim_canonical_path, managed_artifact_key)
# Template dirs that produce user-facing outputs reachable via .claude/ shims.
_USER_FACING_CATEGORIES = [
    ("agents", ".claude/agents", "agents"),
    ("skills", ".claude/skills", "skills"),
    ("hooks", ".claude/hooks", "hooks"),
    ("workflows-js", ".claude/workflows", "workflows"),
]

# Template dirs that produce outputs but are NOT shimmed to .claude/
# (e.g. .gemini/, .agents/rules/). These only need manifest coverage.
_INTERNAL_CATEGORIES = [
    ("workflows", ".claude/commands", None),
    ("rules", ".agents/rules", None),
]


class TestShimMapCoversAllUserFacingCategories(unittest.TestCase):
    """Every user-facing template category must have a shim_map entry."""

    def test_shim_map_has_entry_for_each_user_facing_category(self):
        source = _HELPERS_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)

        shim_canonical_paths: set[str] = set()
        for node in ast.walk(tree):
            # Handle both ast.Assign and ast.AnnAssign (type-annotated)
            target_name = None
            value = None
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                target_name = node.target.id
                value = node.value
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "shim_map":
                        target_name = t.id
                        value = node.value

            if target_name == "shim_map" and isinstance(value, ast.List):
                for elt in value.elts:
                    if isinstance(elt, ast.Tuple) and len(elt.elts) >= 1:
                        first = elt.elts[0]
                        if isinstance(first, ast.Constant):
                            shim_canonical_paths.add(first.value)

        self.assertTrue(
            len(shim_canonical_paths) > 0,
            "Could not parse shim_map from build_helpers.py — AST extraction found 0 entries.",
        )

        for _, shim_path, _ in _USER_FACING_CATEGORIES:
            with self.subTest(shim_path=shim_path):
                self.assertIn(
                    shim_path,
                    shim_canonical_paths,
                    f"shim_map is missing entry for '{shim_path}'. "
                    f"Add (\"{shim_path}\", \"<output_rel>\") to shim_map in "
                    f"build_helpers.py install_shims().",
                )


class TestManagedArtifactDirsCoversAllCategories(unittest.TestCase):
    """Every user-facing category must have a _MANAGED_ARTIFACT_DIRS entry."""

    def test_managed_dirs_has_entry_for_each_category(self):
        managed = _phases_mod._MANAGED_ARTIFACT_DIRS

        for cat, _, managed_key in _USER_FACING_CATEGORIES:
            if managed_key is None:
                continue
            with self.subTest(category=cat):
                self.assertIn(
                    managed_key,
                    managed,
                    f"_MANAGED_ARTIFACT_DIRS is missing key '{managed_key}' "
                    f"for template category '{cat}'. Add it to build_phases.py.",
                )


class TestSourceManifestsCoversAllCategories(unittest.TestCase):
    """_build_source_manifests() must return a key for each managed category."""

    def test_source_manifests_returns_all_keys(self):
        build_py_path = _REPO_ROOT / "scripts" / "build.py"
        spec3 = importlib.util.spec_from_file_location("build_main", build_py_path)
        build_mod = importlib.util.module_from_spec(spec3)
        sys.modules.setdefault("build_main", build_mod)
        spec3.loader.exec_module(build_mod)

        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            manifests = build_mod._build_source_manifests(output_root)

        for cat, _, managed_key in _USER_FACING_CATEGORIES:
            if managed_key is None:
                continue
            with self.subTest(category=cat):
                self.assertIn(
                    managed_key,
                    manifests,
                    f"_build_source_manifests() is missing key '{managed_key}' "
                    f"for template category '{cat}'. Add scanning logic to build.py.",
                )


class TestOutputDriftCoversAllShimmedDirs(unittest.TestCase):
    """check_output_drift.py _OUTPUT_DIRS must cover all shimmed directories."""

    def test_drift_check_covers_shimmed_dirs(self):
        drift_script = (
            _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
            / "check_output_drift.py"
        )
        if not drift_script.exists():
            self.skipTest("check_output_drift.py not found")

        source = drift_script.read_text(encoding="utf-8")
        tree = ast.parse(source)

        # Extract path suffixes from _OUTPUT_DIRS list
        drift_suffixes: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target_node in node.targets:
                    if isinstance(target_node, ast.Name) and target_node.id == "_OUTPUT_DIRS":
                        if isinstance(node.value, ast.List):
                            for elt in node.value.elts:
                                # Each element is _REPO_ROOT / "x" / "y"
                                parts = _extract_path_parts(elt)
                                if parts:
                                    drift_suffixes.add("/".join(parts))

        all_categories = _USER_FACING_CATEGORIES + _INTERNAL_CATEGORIES
        for cat, shim_path, _ in all_categories:
            with self.subTest(category=cat, shim_path=shim_path):
                self.assertIn(
                    shim_path,
                    drift_suffixes,
                    f"check_output_drift.py _OUTPUT_DIRS is missing '{shim_path}' "
                    f"for template category '{cat}'. Add it to the _OUTPUT_DIRS list.",
                )


class TestTemplateDirectoriesHaveCategories(unittest.TestCase):
    """Every directory under templates/ that produces artifacts must be listed."""

    def test_no_unlisted_artifact_template_dirs(self):
        templates_dir = _REPO_ROOT / "templates"
        if not templates_dir.exists():
            self.skipTest("templates/ not found")

        known_categories = {cat for cat, _, _ in _USER_FACING_CATEGORIES + _INTERNAL_CATEGORIES}
        # Also allow non-artifact template dirs that don't produce shimmed outputs
        non_artifact_dirs = {
            "acceptance-criteria",
            "commands",
            "commit-guardian",
            "config",
            "scripts",
            "doc-compliance",
            "ticket-lifecycle",
            "feedback",
            "sync_platforms",
            "antigravity_instructions",
            "config-scaffolds",
            "roadmap",
            "vision",
            "docs",
        }

        for d in sorted(templates_dir.iterdir()):
            if not d.is_dir():
                continue
            if d.name in non_artifact_dirs:
                continue
            with self.subTest(template_dir=d.name):
                self.assertIn(
                    d.name,
                    known_categories,
                    f"Template directory '{d.name}' exists but is not listed in "
                    f"test_build_artifact_parity.py. Either add it to "
                    f"_USER_FACING_CATEGORIES / _INTERNAL_CATEGORIES, or add it "
                    f"to non_artifact_dirs if it doesn't produce shimmed outputs.",
                )


class TestPreCommitFilesPatternCoversAllShimmedDirs(unittest.TestCase):
    """check-output-drift hook files: regex must match all shimmed output dirs."""

    def test_precommit_files_pattern_covers_shimmed_dirs(self):
        cg_json = _REPO_ROOT / "templates" / "commit-guardian" / "commit_guardian.json"
        if not cg_json.exists():
            self.skipTest("commit_guardian.json not found")

        import json
        import re

        data = json.loads(cg_json.read_text(encoding="utf-8"))
        hooks = data.get("hooks_manifest", {}).get("hooks", [])
        drift_hook = next((h for h in hooks if isinstance(h, dict) and h.get("id") == "check-output-drift"), None)
        self.assertIsNotNone(drift_hook, "check-output-drift hook not found in commit_guardian.json")

        pattern = drift_hook["files"]

        all_categories = _USER_FACING_CATEGORIES + _INTERNAL_CATEGORIES
        for cat, shim_path, _ in all_categories:
            test_path = shim_path + "/some-file.py"
            with self.subTest(category=cat, shim_path=shim_path):
                self.assertIsNotNone(
                    re.search(pattern, test_path),
                    f"commit_guardian.json check-output-drift 'files' pattern "
                    f"does not match '{shim_path}/' for category '{cat}'. "
                    f"Add '\\.{shim_path.lstrip('.')}/' to the files regex.",
                )


def _extract_path_parts(node: ast.expr) -> list[str] | None:
    """Extract string parts from a Path division chain like _REPO_ROOT / 'x' / 'y'."""
    parts: list[str] = []
    current = node
    while isinstance(current, ast.BinOp) and isinstance(current.op, ast.Div):
        if isinstance(current.right, ast.Constant) and isinstance(current.right.value, str):
            parts.insert(0, current.right.value)
        current = current.left
    return parts if parts else None


if __name__ == "__main__":
    unittest.main()
