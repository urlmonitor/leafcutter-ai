"""Tests for output_root and shim_strategy config fields."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MODULE_PATH = _REPO_ROOT / "scripts" / "config_loader.py"

spec = importlib.util.spec_from_file_location("config_loader", _MODULE_PATH)
assert spec is not None and spec.loader is not None, f"could not load spec for {_MODULE_PATH}"
_mod = importlib.util.module_from_spec(spec)
sys.modules["config_loader"] = _mod
spec.loader.exec_module(_mod)

load_config = _mod.load_config
validate_config = _mod.validate_config
ConfigValidationError = _mod.ConfigValidationError


class TestOutputRootDefault(unittest.TestCase):
    def test_output_root_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            config = load_config(None, target)
            self.assertEqual(config.get("output_root"), ".leafcutter")

    def test_output_root_custom(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            config_dir = target / ".claude"
            config_dir.mkdir()
            config_file = config_dir / "skills_config.json"
            config_file.write_text(json.dumps({"output_root": ".my-output"}))
            config = load_config(config_file, target)
            self.assertEqual(config["output_root"], ".my-output")


class TestShimStrategy(unittest.TestCase):
    def test_shim_strategy_defaults_to_auto(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            config = load_config(None, target)
            self.assertEqual(config.get("shim_strategy"), "auto")

    def test_shim_strategy_invalid_raises(self):
        config = {"shim_strategy": "teleport"}
        with self.assertRaises(ConfigValidationError) as ctx:
            validate_config(config)
        self.assertIn("teleport", str(ctx.exception))
        self.assertIn("symlink", str(ctx.exception))

    def test_shim_strategy_valid_values(self):
        for val in ("symlink", "copy", "auto"):
            config = {"shim_strategy": val}
            errors = validate_config(config)
            # Should not raise; errors may be from jsonschema not installed
            self.assertNotIn("Invalid shim_strategy", " ".join(errors))


if __name__ == "__main__":
    unittest.main()
