"""Tests for the --migrate stale-file detection in build.py."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

_MODULE_PATH = _SCRIPTS_DIR / "build.py"

spec = importlib.util.spec_from_file_location("_build", _MODULE_PATH)
_mod = importlib.util.module_from_spec(spec)
sys.modules["_build"] = _mod
spec.loader.exec_module(_mod)

_run_migration_report = _mod._run_migration_report


class TestMigrationReport(unittest.TestCase):
    def test_migrate_detects_stale_claude_agents(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            output_root = target / ".leafcutter"
            output_root.mkdir()

            stale_agents = target / ".claude" / "agents"
            stale_agents.mkdir(parents=True)
            (stale_agents / "test.md").write_text("stale agent")

            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = _run_migration_report(target, output_root)

            self.assertEqual(result, 0)
            output = buf.getvalue()
            self.assertIn("STALE", output)
            self.assertIn(".claude/agents", output)

    def test_migrate_no_stale_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            output_root = target / ".leafcutter"
            output_root.mkdir()

            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = _run_migration_report(target, output_root)

            self.assertEqual(result, 0)
            self.assertIn("No stale", buf.getvalue())

    def test_migrate_no_deletions(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            output_root = target / ".leafcutter"
            output_root.mkdir()

            stale_agents = target / ".claude" / "agents"
            stale_agents.mkdir(parents=True)
            (stale_agents / "test.md").write_text("stale")

            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            with redirect_stdout(buf):
                _run_migration_report(target, output_root)

            self.assertTrue(stale_agents.exists())
            self.assertTrue((stale_agents / "test.md").exists())

    def test_migrate_ignores_symlinks_to_output_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            output_root = target / ".leafcutter"
            (output_root / "agents").mkdir(parents=True)
            (output_root / "agents" / "test.md").write_text("agent")

            claude_dir = target / ".claude"
            claude_dir.mkdir()
            agents_link = claude_dir / "agents"
            agents_link.symlink_to(output_root / "agents")

            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            with redirect_stdout(buf):
                result = _run_migration_report(target, output_root)

            self.assertEqual(result, 0)
            self.assertIn("No stale", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
