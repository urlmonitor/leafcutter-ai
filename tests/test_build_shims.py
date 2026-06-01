"""Tests for the install_shims() consolidated output root shim layer."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MODULE_PATH = _REPO_ROOT / "scripts" / "build_helpers.py"

spec = importlib.util.spec_from_file_location("build_helpers", _MODULE_PATH)
_mod = importlib.util.module_from_spec(spec)
sys.modules["build_helpers"] = _mod
spec.loader.exec_module(_mod)

install_shims = _mod.install_shims


class TestInstallShimsSymlink(unittest.TestCase):
    def test_install_shims_symlink_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            output_root = target / ".leafcutter"
            (output_root / "agents").mkdir(parents=True)
            (output_root / "agents" / "test.md").write_text("agent")
            (output_root / "skills").mkdir(parents=True)
            (output_root / "skills" / "test.md").write_text("skill")

            config = {"shim_strategy": "symlink", "output_root": ".leafcutter"}
            results = install_shims(target, output_root=output_root, config=config)

            agents_shim = target / ".claude" / "agents"
            self.assertTrue(agents_shim.is_symlink() or agents_shim.is_dir())
            self.assertTrue((agents_shim / "test.md").exists())

    def test_install_shims_copy_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            output_root = target / ".leafcutter"
            (output_root / "agents").mkdir(parents=True)
            (output_root / "agents" / "test.md").write_text("agent content")

            config = {"shim_strategy": "auto", "output_root": ".leafcutter"}

            with patch("os.symlink", side_effect=PermissionError("no symlinks")):
                results = install_shims(target, output_root=output_root, config=config)

            agents_path = target / ".claude" / "agents"
            self.assertTrue(agents_path.is_dir())
            self.assertFalse(agents_path.is_symlink())
            self.assertEqual(
                (agents_path / "test.md").read_text(), "agent content"
            )
            copy_results = [r for r in results if "copy" in r["method"]]
            self.assertTrue(len(copy_results) > 0)

    def test_install_shims_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            output_root = target / ".leafcutter"
            (output_root / "agents").mkdir(parents=True)
            (output_root / "agents" / "test.md").write_text("agent")

            config = {"shim_strategy": "auto", "output_root": ".leafcutter"}
            results = install_shims(
                target, output_root=output_root, config=config, dry_run=True
            )

            self.assertFalse((target / ".claude" / "agents").exists())
            self.assertTrue(any("dry-run" in r["method"] for r in results))

    def test_shim_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            output_root = target / ".leafcutter"
            (output_root / "agents").mkdir(parents=True)
            (output_root / "agents" / "test.md").write_text("agent")

            config = {"shim_strategy": "copy", "output_root": ".leafcutter"}
            install_shims(target, output_root=output_root, config=config)
            install_shims(target, output_root=output_root, config=config)

            agents_path = target / ".claude" / "agents"
            self.assertTrue(agents_path.is_dir())
            self.assertEqual(
                (agents_path / "test.md").read_text(), "agent"
            )

    def test_skips_nonexistent_source_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            output_root = target / ".leafcutter"
            output_root.mkdir()

            config = {"shim_strategy": "auto", "output_root": ".leafcutter"}
            results = install_shims(target, output_root=output_root, config=config)

            self.assertEqual(len(results), 0)


if __name__ == "__main__":
    unittest.main()
