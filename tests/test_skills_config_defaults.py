"""
MODULE: test_skills_config_defaults
GOAL: Verify that skills_config.default.json contains the expected frontend
    configuration keys and that the config_loader flattens nested keys correctly
    for template placeholder resolution.
BUSINESS CONTEXT: frontend-coder reads its project_context_path from the
    config. If the key is missing or the loader does not flatten nested dicts,
    the agent template placeholder {{frontend.project_context_path}} will not
    resolve, leaving the agent with an unresolvable path reference.
ARCHITECTURE: Loads skills_config.default.json directly and verifies key presence.
    Also tests _flatten_nested_keys via load_config to confirm dot-notation access.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULTS_PATH = _REPO_ROOT / "config" / "skills_config.default.json"
_MODULE_PATH = _REPO_ROOT / "scripts" / "config_loader.py"

# Load config_loader module
spec = importlib.util.spec_from_file_location("config_loader", _MODULE_PATH)
_mod = importlib.util.module_from_spec(spec)
sys.modules["config_loader"] = _mod
spec.loader.exec_module(_mod)

load_config = _mod.load_config


class TestFrontendKeysPresent(unittest.TestCase):
    def setUp(self):
        with _DEFAULTS_PATH.open("r", encoding="utf-8") as f:
            self.defaults = json.load(f)

    def test_frontend_key_exists(self):
        """skills_config.default.json must have a 'frontend' top-level key."""
        self.assertIn(
            "frontend",
            self.defaults,
            "skills_config.default.json must contain a 'frontend' key"
        )

    def test_frontend_project_context_path_present(self):
        """frontend object must contain project_context_path sub-key."""
        frontend = self.defaults.get("frontend", {})
        self.assertIn(
            "project_context_path",
            frontend,
            "skills_config.default.json[frontend] must contain 'project_context_path'"
        )

    def test_frontend_optional_skills_present(self):
        """frontend object must contain optional_skills sub-key."""
        frontend = self.defaults.get("frontend", {})
        self.assertIn(
            "optional_skills",
            frontend,
            "skills_config.default.json[frontend] must contain 'optional_skills'"
        )

    def test_frontend_test_command_present(self):
        """frontend object must contain test_command sub-key."""
        frontend = self.defaults.get("frontend", {})
        self.assertIn(
            "test_command",
            frontend,
            "skills_config.default.json[frontend] must contain 'test_command'"
        )

    def test_frontend_optional_skills_default_empty_list(self):
        """frontend.optional_skills default value must be an empty list."""
        frontend = self.defaults.get("frontend", {})
        self.assertEqual(
            frontend.get("optional_skills"),
            [],
            "frontend.optional_skills must default to []"
        )

    def test_frontend_test_command_default_empty_string(self):
        """frontend.test_command default value must be an empty string."""
        frontend = self.defaults.get("frontend", {})
        self.assertEqual(
            frontend.get("test_command"),
            "",
            "frontend.test_command must default to empty string"
        )


class TestNestedKeyFlattening(unittest.TestCase):
    """Verify load_config flattens nested keys for template placeholder resolution."""

    def test_flat_key_frontend_project_context_path(self):
        """load_config must expose 'frontend.project_context_path' as a flat key."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            config = load_config(None, target)
            self.assertIn(
                "frontend.project_context_path",
                config,
                "load_config must flatten 'frontend.project_context_path' "
                "so {{frontend.project_context_path}} resolves in templates"
            )

    def test_flat_key_frontend_optional_skills(self):
        """load_config must expose 'frontend.optional_skills' as a flat key."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            config = load_config(None, target)
            self.assertIn(
                "frontend.optional_skills",
                config,
                "load_config must flatten 'frontend.optional_skills'"
            )

    def test_flat_key_frontend_test_command(self):
        """load_config must expose 'frontend.test_command' as a flat key."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            config = load_config(None, target)
            self.assertIn(
                "frontend.test_command",
                config,
                "load_config must flatten 'frontend.test_command'"
            )

    def test_nested_dict_still_accessible(self):
        """Original nested 'frontend' dict must still be accessible after flattening."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            config = load_config(None, target)
            self.assertIsInstance(
                config.get("frontend"),
                dict,
                "config['frontend'] must still be a dict after flattening"
            )

    def test_project_override_propagates_to_flat_key(self):
        """A project override of frontend.project_context_path must be visible in flat key."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            config_dir = target / ".claude"
            config_dir.mkdir()
            config_file = config_dir / "skills_config.json"
            config_file.write_text(json.dumps({
                "frontend": {
                    "project_context_path": ".custom/PROJECT_CONTEXT.md",
                    "optional_skills": ["webapp-testing"],
                    "test_command": "yarn vitest"
                }
            }))
            config = load_config(config_file, target)
            self.assertEqual(
                config.get("frontend.project_context_path"),
                ".custom/PROJECT_CONTEXT.md",
                "Project override of frontend.project_context_path must be visible as flat key"
            )


if __name__ == "__main__":
    unittest.main()
