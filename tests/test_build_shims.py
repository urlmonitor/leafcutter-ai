"""Tests for the install_shims() consolidated output root shim layer."""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_MODULE_PATH = _SCRIPTS_DIR / "build_helpers.py"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

spec = importlib.util.spec_from_file_location("build_helpers", _MODULE_PATH)
assert spec is not None and spec.loader is not None, f"could not load spec for {_MODULE_PATH}"
_mod = importlib.util.module_from_spec(spec)
sys.modules["build_helpers"] = _mod
spec.loader.exec_module(_mod)

install_shims = _mod.install_shims


def _load_build_phases():
    """Load build_phases from scripts/ (cached)."""
    if "build_phases" in sys.modules:
        return sys.modules["build_phases"]
    phases_path = _SCRIPTS_DIR / "build_phases.py"
    spec2 = importlib.util.spec_from_file_location("build_phases", phases_path)
    mod = importlib.util.module_from_spec(spec2)
    sys.modules["build_phases"] = mod
    spec2.loader.exec_module(mod)
    return mod


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
            install_shims(target, output_root=output_root, config=config)

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


class TestWorkflowShimEndToEndReachability(unittest.TestCase):
    """BP-811 regression: after a real build, workflow .js files must be reachable
    through target_root/.claude/workflows/ — the shim must not be skipped.

    Root cause (in scripts/build_phases.py):
      build_workflow_scripts() receives output_root as its first arg
      (exactly as build.py passes it — see artifact_phases loop ~line 477).
      The function must write .js files to <output_root>/workflows/ so that
      install_shims() can find the source at output_root/workflows/.

      The bug: build_workflow_scripts() writes to
      <first_arg>/.claude/workflows/ instead of <first_arg>/workflows/.
      With first_arg=output_root, files land at output_root/.claude/workflows/,
      but install_shims() checks output_root/workflows/ — path disagrees —
      shim is skipped — files are unreachable via the canonical shim layer.

    To make this test GREEN:
      Fix build_phases.py so that build_workflow_scripts() writes to
      <output_root>/workflows/ (not <output_root>/.claude/workflows/).
      Do NOT change build_helpers.py (the shim map is correct).
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._target = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_workflow_js_reachable_via_claude_workflows_shim(self) -> None:
        # covers: BP-811
        """After running build_workflow_scripts(output_root, ...) + install_shims(),
        plan-feature.js must be reachable through target_root/.claude/workflows/,
        AND it must physically reside under output_root (not under target_root).

        The test models the REAL build convention:
          - build.py calls: fn(output_root, config, dry_run, force)
            where output_root = target/.leafcutter
          - install_shims() then maps .claude/workflows -> output_root/workflows/

        Failure mode (current unmodified code in build_phases.py):
          build_workflow_scripts() writes to
          output_root/.claude/workflows/ (because it appends .claude/workflows
          to its first arg). install_shims() checks output_root/workflows/
          (which does NOT exist). install_shims() logs:
            "shim source missing: workflows/ — Skipping .claude/workflows shim"
          Result: no shim is created; plan-feature.js is unreachable.

        To make this test GREEN:
          Change build_phases.py line ~360:
            output_dir = target_root / ".claude" / "workflows"
          to:
            output_dir = target_root / "workflows"
          (where target_root is actually output_root in real build invocations)
        """
        os.environ["CLAUDE_CODE_VERSION"] = "2.1.200"
        try:
            build_phases = _load_build_phases()

            # output_root is target/.leafcutter — the consolidated output root
            # used in real consumer builds (build.py passes this as first arg).
            # Keeping it separate from target exposes the path-mismatch bug.
            output_root = self._target / ".leafcutter"
            output_root.mkdir(parents=True)

            config = {
                "workflows": {"enabled": True},
                "shim_strategy": "copy",  # copy avoids symlink permission issues in CI
                "output_root": ".leafcutter",
            }

            # Phase 1 — deploy workflow .js files (build phase).
            # Pass output_root as the first arg, EXACTLY like build.py does.
            written = build_phases.build_workflow_scripts(
                output_root, config, dry_run=False, force=True
            )
            self.assertGreater(
                written,
                0,
                "build_workflow_scripts() wrote 0 files — "
                "templates/workflows-js/ must contain at least plan-feature.js.",
            )

            # Phase 2 — install shims (shim layer).
            results = install_shims(
                self._target,
                output_root=output_root,
                config=config,
                force=True,
            )

            # Assert: the .claude/workflows shim must NOT have been skipped.
            # If build_workflow_scripts() wrote to output_root/.claude/workflows/
            # (the bug), then output_root/workflows/ does not exist and
            # install_shims() skips the entry entirely (no result emitted).
            workflows_shim_results = [
                r for r in results if r.get("canonical") == ".claude/workflows"
            ]
            self.assertGreater(
                len(workflows_shim_results),
                0,
                "install_shims() produced no result entry for '.claude/workflows'. "
                "The shim was silently skipped (source path not found). "
                "BP-811 root cause in build_phases.py: build_workflow_scripts() "
                "writes to output_root/.claude/workflows/ but install_shims() "
                "checks output_root/workflows/ — the two paths disagree.",
            )
            skipped = [
                r for r in workflows_shim_results
                if "missing" in r.get("method", "") or "skip" in r.get("method", "").lower()
            ]
            self.assertEqual(
                len(skipped),
                0,
                f"The .claude/workflows shim was skipped: {workflows_shim_results}. "
                "BP-811: fix build_phases.py to write to output_root/workflows/ "
                "instead of output_root/.claude/workflows/.",
            )

            # Assert: plan-feature.js must be reachable through the canonical path.
            canonical_js = self._target / ".claude" / "workflows" / "plan-feature.js"
            self.assertTrue(
                canonical_js.exists(),
                f"plan-feature.js is NOT reachable at {canonical_js}. "
                "After a consumer build, workflow .js files must be accessible "
                "through target_root/.claude/workflows/ (BP-811).",
            )
            self.assertGreater(
                canonical_js.stat().st_size,
                0,
                "plan-feature.js exists at the canonical path but is empty.",
            )

            # Assert: the physical file must reside under output_root, not target_root.
            # This confirms the file went through the shim layer (output_root/workflows/)
            # rather than being written directly to target_root/.claude/workflows/.
            physical_js = output_root / "workflows" / "plan-feature.js"
            self.assertTrue(
                physical_js.exists(),
                f"plan-feature.js does NOT physically reside at {physical_js}. "
                "build_workflow_scripts() must write to output_root/workflows/ "
                "(not output_root/.claude/workflows/) so the shim layer can reach it.",
            )
        finally:
            os.environ.pop("CLAUDE_CODE_VERSION", None)


if __name__ == "__main__":
    unittest.main()
