"""
MODULE: test_check_surface_components_e3
GOAL: Unit tests for check_surface_components_e3.py, the pre-commit hook that
    blocks commits when a staged agent/skill/roadmap registry JSON entry lacks
    a non-empty `components` field.
BUSINESS CONTEXT: KM-KGS-100e-3. Verifies that the hook correctly detects
    violations on synthetic registry JSON fixtures AND exercises the glossary
    exemption (edge_fields: []) derived from paths.json at runtime.
ARCHITECTURE: Tests load the hook from templates/scripts/commit_guardian/ via
    importlib (matching the convention in test_check_ac_circular_deps.py).
    HOOK_TEST_FILES, HOOK_ROOT, and HOOK_NO_GIT env vars are used for isolation.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_HOOK_PATH = (
    _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
    / "check_surface_components_e3.py"
)

try:
    _MODULE_NAME = "check_surface_components_e3_test_shim"
    _spec = importlib.util.spec_from_file_location(_MODULE_NAME, str(_HOOK_PATH))
    _mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
    sys.modules[_MODULE_NAME] = _mod
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]

    _load_registry_surfaces = _mod._load_registry_surfaces
    _extract_entries = _mod._extract_entries
    _check_entry_components = _mod._check_entry_components
    _check_registry_file = _mod._check_registry_file
    _get_staged_registry_paths = _mod._get_staged_registry_paths
    _main = _mod.main
    _IMPORT_OK = True
    _IMPORT_ERROR = ""
except (FileNotFoundError, AttributeError, ImportError, SyntaxError, TypeError, ValueError) as _exc:
    _IMPORT_OK = False
    _IMPORT_ERROR = str(_exc)


def _requires_import(func):
    """Skip test if the hook module failed to import."""
    if not _IMPORT_OK:
        return unittest.skip(
            f"check_surface_components_e3 not importable: {_IMPORT_ERROR}"
        )(func)
    return func


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_json(root: Path, rel_path: str, data: dict) -> Path:
    """Write JSON to root/rel_path, creating parent dirs as needed."""
    p = root / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return p


def _write_paths_json(root: Path, surfaces: dict) -> Path:
    """Write a minimal paths.json to root/config/paths.json."""
    return _write_json(root, "config/paths.json", {"surfaces": surfaces})


# ---------------------------------------------------------------------------
# _load_registry_surfaces
# ---------------------------------------------------------------------------


@_requires_import
class TestLoadRegistrySurfaces(unittest.TestCase):
    """Tests for paths.json-driven registry surface discovery."""

    def test_membership_surface_included(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write_paths_json(root, {
                "agents": {
                    "path": "config/agent_registry.json",
                    "edge_fields": ["spawn_allowlist", "components"],
                }
            })
            surfaces = _load_registry_surfaces(root)
            self.assertIn("agents", surfaces)
            self.assertEqual(surfaces["agents"], "config/agent_registry.json")

    def test_glossary_excluded_empty_edge_fields(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write_paths_json(root, {
                "glossary": {
                    "path": "docs/glossary.md",
                    "edge_fields": [],
                }
            })
            surfaces = _load_registry_surfaces(root)
            self.assertNotIn("glossary", surfaces)

    def test_directory_surface_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write_paths_json(root, {
                "tickets": {
                    "path": "tickets/",
                    "edge_fields": ["components"],
                }
            })
            surfaces = _load_registry_surfaces(root)
            self.assertNotIn("tickets", surfaces)

    def test_missing_paths_json_uses_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            surfaces = _load_registry_surfaces(root)
            # Should return fallback dict with the three known registry surfaces
            self.assertIn("agents", surfaces)
            self.assertIn("skills", surfaces)
            self.assertIn("roadmap", surfaces)

    def test_surface_without_components_in_edge_fields_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write_paths_json(root, {
                "agents": {
                    "path": "config/agent_registry.json",
                    "edge_fields": ["spawn_allowlist", "spawned_by"],
                }
            })
            surfaces = _load_registry_surfaces(root)
            self.assertNotIn("agents", surfaces)


# ---------------------------------------------------------------------------
# _extract_entries
# ---------------------------------------------------------------------------


@_requires_import
class TestExtractEntries(unittest.TestCase):
    """Tests for the registry entry extraction helper."""

    def test_list_data_returned_as_is(self) -> None:
        entries = _extract_entries([{"id": "a"}, {"id": "b"}], "agents")
        self.assertEqual(len(entries), 2)

    def test_dict_with_surface_key_used(self) -> None:
        data = {"agents": [{"id": "a"}]}
        entries = _extract_entries(data, "agents")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["id"], "a")

    def test_dict_with_fallback_skills_key(self) -> None:
        data = {"skills": [{"id": "s1"}]}
        entries = _extract_entries(data, "my_surface")
        self.assertEqual(len(entries), 1)

    def test_dict_with_fallback_phases_key(self) -> None:
        data = {"phases": [{"id": "phase_1"}]}
        entries = _extract_entries(data, "roadmap")
        self.assertEqual(len(entries), 1)

    def test_empty_dict_returns_empty(self) -> None:
        entries = _extract_entries({}, "agents")
        self.assertEqual(entries, [])


# ---------------------------------------------------------------------------
# _check_entry_components
# ---------------------------------------------------------------------------


@_requires_import
class TestCheckEntryComponents(unittest.TestCase):
    """Tests for the entry-level components validation."""

    def test_valid_entry_passes(self) -> None:
        entry = {"id": "python-coder", "components": ["build-pipeline"]}
        errs = _check_entry_components(entry, "agents:python-coder")
        self.assertEqual(errs, [])

    def test_missing_components_blocked(self) -> None:
        entry = {"id": "python-coder", "name": "Python Coder"}
        errs = _check_entry_components(entry, "agents:python-coder")
        self.assertTrue(len(errs) > 0)
        self.assertTrue(any("missing required" in e for e in errs))

    def test_empty_components_blocked(self) -> None:
        entry = {"id": "python-coder", "components": []}
        errs = _check_entry_components(entry, "agents:python-coder")
        self.assertTrue(len(errs) > 0)

    def test_error_message_names_entry(self) -> None:
        entry = {"id": "test-skill"}
        errs = _check_entry_components(entry, "skills:test-skill")
        self.assertTrue(any("skills:test-skill" in e for e in errs))


# ---------------------------------------------------------------------------
# _check_registry_file
# ---------------------------------------------------------------------------


@_requires_import
class TestCheckRegistryFile(unittest.TestCase):
    """Tests for per-file registry validation."""

    def test_valid_agent_registry_passes(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            p = _write_json(root, "config/agent_registry.json", {
                "agents": [
                    {"id": "python-coder", "components": ["build-pipeline"]},
                ]
            })
            errs = _check_registry_file(str(p), "agents", None)
            self.assertEqual(errs, [])

    def test_agent_missing_components_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            p = _write_json(root, "config/agent_registry.json", {
                "agents": [
                    {"id": "python-coder", "name": "Python Coder"},
                ]
            })
            errs = _check_registry_file(str(p), "agents", None)
            self.assertEqual(len(errs), 1)

    def test_roadmap_phases_checked(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            p = _write_json(root, "docs/roadmap.json", {
                "phases": [
                    {"id": "phase_1", "title": "Phase 1"},
                ]
            })
            errs = _check_registry_file(str(p), "roadmap", None)
            self.assertEqual(len(errs), 1)

    def test_nonexistent_file_returns_empty(self) -> None:
        errs = _check_registry_file("/tmp/nonexistent_reg.json", "agents", None)
        self.assertEqual(errs, [])

    def test_non_dict_entries_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            p = _write_json(root, "config/skill_registry.json", {
                "skills": ["not_a_dict", 42, None]
            })
            errs = _check_registry_file(str(p), "skills", None)
            self.assertEqual(errs, [])


# ---------------------------------------------------------------------------
# main() — end-to-end via HOOK_TEST_FILES
# ---------------------------------------------------------------------------


@_requires_import
class TestMainWithTestFiles(unittest.TestCase):
    """End-to-end tests for main() using the HOOK_TEST_FILES env seam."""

    def setUp(self) -> None:
        self._orig_env = os.environ.copy()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._orig_env)

    def test_main_returns_0_no_staged(self) -> None:
        os.environ["HOOK_NO_GIT"] = "1"
        os.environ.pop("HOOK_TEST_FILES", None)
        self.assertEqual(_main(), 0)

    def test_main_returns_0_valid_registry(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            p = _write_json(root, "config/agent_registry.json", {
                "agents": [{"id": "python-coder", "components": ["build-pipeline"]}]
            })
            os.environ["HOOK_TEST_FILES"] = str(p)
            self.assertEqual(_main(), 0)

    def test_main_returns_1_missing_components(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            p = _write_json(root, "config/agent_registry.json", {
                "agents": [{"id": "python-coder", "name": "Python Coder"}]
            })
            os.environ["HOOK_TEST_FILES"] = str(p)
            self.assertEqual(_main(), 1)


# ---------------------------------------------------------------------------
# Real-fixture behavioral verification
# ---------------------------------------------------------------------------


@_requires_import
class TestRealFixtureBehavior(unittest.TestCase):
    """Exercises the hook against the real agent_registry.json.

    The real registry has no `components` field on any entry. This test verifies
    that the hook DETECTS these violations (not silently skips the file) — which
    is exactly why the hook is disabled: enabling it would block all registry
    changes until the backfill runs.
    """

    _AGENT_REGISTRY = _REPO_ROOT / "config" / "agent_registry.json"

    def test_real_agent_registry_violations_detected(self) -> None:
        """Stripping components from the real registry must flag EXACTLY every entry.

        The real agent_registry.json was backfilled (PR #268) so every entry now
        carries a `components` field. Two guarantees are asserted against
        real-shaped data:

        1. Companion assertion: the real (backfilled) registry yields ZERO
           violations — the hook does not spuriously flag valid entries.
        2. Anti-silent-skip guard: when `components` is stripped from a copy of
           every real entry, the hook flags EXACTLY that many entries (count-exact).
           This proves the hook genuinely detects missing components on the real
           registry's structure rather than silently skipping entries.
        """
        if not self._AGENT_REGISTRY.exists():
            self.skipTest("Real agent_registry.json not present in this environment")

        # (1) The real, backfilled registry must produce no violations.
        real_errs = _check_registry_file(str(self._AGENT_REGISTRY), "agents", None)
        self.assertEqual(
            real_errs,
            [],
            "Real agent_registry.json is backfilled (PR #268): every entry must "
            "carry a non-empty `components` field, so the hook must report 0 "
            f"violations. Got: {real_errs}",
        )

        # (2) Strip `components` from a copy of every real entry and assert the
        #     hook flags EXACTLY every stripped entry (count-exact).
        data = json.loads(self._AGENT_REGISTRY.read_text(encoding="utf-8"))
        entries = _extract_entries(data, "agents")
        dict_entries = [e for e in entries if isinstance(e, dict)]
        self.assertGreater(
            len(dict_entries),
            0,
            "Expected at least 1 agent entry in the real registry",
        )
        for entry in dict_entries:
            entry.pop("components", None)

        with tempfile.TemporaryDirectory() as d:
            stripped_path = Path(d) / "agent_registry_stripped.json"
            stripped_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            stripped_errs = _check_registry_file(str(stripped_path), "agents", None)

        self.assertEqual(
            len(stripped_errs),
            len(dict_entries),
            "Every entry with `components` stripped must be flagged exactly once. "
            f"Expected {len(dict_entries)} violations, got {len(stripped_errs)}. "
            "A lower count means the hook is silently skipping entries.",
        )

    def test_real_agent_registry_is_parseable(self) -> None:
        """Verify the hook can parse the real agent_registry.json."""
        if not self._AGENT_REGISTRY.exists():
            self.skipTest("Real agent_registry.json not present in this environment")

        try:
            raw = self._AGENT_REGISTRY.read_text(encoding="utf-8")
        except (OSError, ValueError):
            self.skipTest("Cannot read real agent_registry.json")

        data = json.loads(raw)
        entries = _extract_entries(data, "agents")
        self.assertGreater(
            len(entries),
            0,
            "Expected at least 1 agent entry in the real registry",
        )


if __name__ == "__main__":
    unittest.main()
