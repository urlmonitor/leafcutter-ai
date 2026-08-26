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
]

# Categories whose deployed location is NOT a shimmed path directly under the
# repo root, so the drift gate reaches them by deriving its scan set from the
# manifest rather than from a fixed list.
#
# "rules" used to sit in _INTERNAL_CATEGORIES above as ".agents/rules", and
# this test therefore required the gate to scan a directory the build has never
# written. build_rules() is registered in build.py's ``internal_phases``, which
# invokes every phase with ``output_root`` — so rules land at
# ``<output_root>/.agents/rules/``, and ``shim_map`` deliberately has no
# ``.agents`` entry to bridge them back up. The manifest carried the same wrong
# path, which is how 16 real deployed rule files ended up scanned by no gate
# while the run reported clean (BP-100k-2). Asserting the wrong path in a third
# place would have kept that hole open, so the expectation is corrected here
# rather than restored.
_MANIFEST_DERIVED_CATEGORIES = [
    ("rules", ".leafcutter/.agents/rules", None),
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
    """check_output_drift.py must scan every shimmed directory for drift.

    This asserts BEHAVIOUR, not source shape: it runs the hook's ``main()``
    with the manifest resolution stubbed out, captures the directory list the
    hook actually hands to ``check_output_drift()``, and checks coverage. An
    earlier version AST-scanned for a module-level ``_OUTPUT_DIRS`` constant
    and broke when GE-118b made manifest resolution dynamic — a refactor that
    changed no behaviour. A presence-scan cannot tell "the gate covers this
    directory" from "a constant with that name exists", which is the
    phantom-done pattern CLAUDE.md forbids for gate tests.
    """

    def _load_drift_module(self):
        drift_script = (
            _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
            / "check_output_drift.py"
        )
        if not drift_script.exists():
            self.skipTest("check_output_drift.py not found")

        # The hook imports a sibling helper (_resolve_root); make that importable.
        guardian_dir = drift_script.parent
        if str(guardian_dir) not in sys.path:
            sys.path.insert(0, str(guardian_dir))

        spec_drift = importlib.util.spec_from_file_location(
            "check_output_drift_under_test", drift_script
        )
        module = importlib.util.module_from_spec(spec_drift)
        try:
            spec_drift.loader.exec_module(module)
        except ImportError as exc:  # pragma: no cover - environment-dependent
            self.skipTest(f"check_output_drift.py not importable: {exc}")
        return module

    def test_drift_check_covers_shimmed_dirs(self):
        module = self._load_drift_module()

        fake_root = Path("/tmp/leafcutter-drift-parity-probe")
        fake_manifest = fake_root / "pkg" / ".build_manifest.json"
        captured: dict[str, list[Path]] = {}

        def _fake_resolve(_hook_file):
            return fake_manifest, []

        def _fake_check(output_dirs, **_kwargs):
            captured["output_dirs"] = list(output_dirs)
            return 0

        original_resolve = module._resolve_manifest_path
        original_check = module.check_output_drift
        module._resolve_manifest_path = _fake_resolve
        module.check_output_drift = _fake_check
        try:
            module.main()
        finally:
            module._resolve_manifest_path = original_resolve
            module.check_output_drift = original_check

        self.assertIn(
            "output_dirs",
            captured,
            "check_output_drift.py main() never reached check_output_drift(); "
            "the drift gate would scan nothing.",
        )

        # repo_root == the manifest's OWN directory. The gate previously used
        # manifest_path.parent.parent, which assumed the manifest sits one level
        # below the tree it describes — true only in the self-host layout. Every
        # output_mappings key is computed relative to the build's target_root,
        # and the manifest is written into that same directory, so its parent IS
        # the base (BP-100k-3-i).
        repo_root = fake_manifest.parent
        drift_suffixes = {
            d.relative_to(repo_root).as_posix()
            for d in captured["output_dirs"]
        }

        all_categories = _USER_FACING_CATEGORIES + _INTERNAL_CATEGORIES
        for cat, shim_path, _ in all_categories:
            with self.subTest(category=cat, shim_path=shim_path):
                self.assertIn(
                    shim_path,
                    drift_suffixes,
                    f"check_output_drift.py does not scan '{shim_path}' for "
                    f"template category '{cat}'. It scans: {sorted(drift_suffixes)}. "
                    f"Add the directory to the output_dirs list built in main().",
                )


class TestTemplateDirectoriesHaveCategories(unittest.TestCase):
    """Every directory under templates/ that produces artifacts must be listed."""

    def test_no_unlisted_artifact_template_dirs(self):
        templates_dir = _REPO_ROOT / "templates"
        if not templates_dir.exists():
            self.skipTest("templates/ not found")

        known_categories = {
            cat
            for cat, _, _ in (
                _USER_FACING_CATEGORIES
                + _INTERNAL_CATEGORIES
                + _MANIFEST_DERIVED_CATEGORIES
            )
        }
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
