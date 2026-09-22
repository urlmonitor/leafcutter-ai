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

# BP-1500g-1 moved the migration report out of build.py's private
# _run_migration_report(target_root, output_root) into build_ownership.py as
# the public run_migration_report(target_root, output_root, strategy,
# claim_set) -- see build_ownership.py's own docstring and build.py's
# DECISION HISTORY near _maybe_run_migration_report. Load it from its new
# home directly rather than reaching into build.py, which no longer defines
# the symbol at all.
_MODULE_PATH = _SCRIPTS_DIR / "build_ownership.py"

spec = importlib.util.spec_from_file_location("build_ownership", _MODULE_PATH)
assert spec is not None and spec.loader is not None, f"could not load spec for {_MODULE_PATH}"
_mod = importlib.util.module_from_spec(spec)
sys.modules["build_ownership"] = _mod
spec.loader.exec_module(_mod)

# These tests exercise the STALE-detection sweep only, in isolation from the
# real shim claim tables (build_helpers.shim_map / file_shims) -- so an empty
# claim_set and the default "auto" strategy reproduce the same no-claims
# scenario the pre-BP-1500g-1 report-only function always ran under. A
# non-empty claim_set / "copy" strategy interaction is exercised separately
# where build_ownership.assemble_claim_set and resolve_removal_verdict are
# under direct test.
_DEFAULT_STRATEGY = "auto"
_EMPTY_CLAIM_SET: set[str] = set()


def _run_migration_report(target_root: Path, output_root: Path) -> int:
    """Thin wrapper pinning this file's tests to the no-claims scenario."""
    return _mod.run_migration_report(
        target_root, output_root, _DEFAULT_STRATEGY, _EMPTY_CLAIM_SET
    )


class TestMigrationReport(unittest.TestCase):
    def test_migrate_detects_stale_claude_agents(self):
        """AMENDED 2026-09-21 (BP-1500g-1 rename + ownership model). The old
        fixture wrote real content into .claude/agents/test.md and expected
        it to be reported STALE. Under the ownership-aware verdict this
        function now consults (build_ownership.owns_installed_path, per
        BP-1500g-1 / ADR-041), a real non-empty directory is classified
        "adopter_owned" and listed as PROTECTED, never STALE -- reporting a
        path holding content the build cannot attribute to itself as safe to
        remove is exactly the KI-BP-009 defect this model exists to prevent.
        A genuinely stale, package-produced leftover is instead a real but
        EMPTY directory (see owns_installed_path's docstring), so the
        fixture now plants an empty .claude/agents/ to match what "stale"
        actually means post-BP-1500g-1.
        """
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            output_root = target / ".leafcutter"
            output_root.mkdir()

            stale_agents = target / ".claude" / "agents"
            stale_agents.mkdir(parents=True)

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
