"""
MODULE: test_build_phases
GOAL: TDD red-baseline tests for build_workflow_scripts() deploying plan-feature.js.
BUSINESS CONTEXT: plan-feature.js must be deployed from templates/workflows-js/ to
    the consolidated output root's workflows/ dir (output_root/workflows/), which
    install_shims() then exposes at the consumer's .claude/workflows/ shim.
    build_workflow_scripts() writes to <root>/workflows/ (see BP-811: the earlier
    <root>/.claude/workflows/ write path broke the shim and was corrected).
ARCHITECTURE: Pure unit / integration tests using unittest.TestCase + tempfile.
    No database.  No network.  All tests must complete in < 5 seconds.

Tests in this file:
  - test_build_workflow_scripts_includes_plan_feature (unit)
  - test_plan_feature_deployed_in_consumer_config (integration)

These deploy-path assertions track build_workflow_scripts()'s output dir
(<root>/workflows/), which install_shims() exposes at .claude/workflows/ (BP-811).
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: resolve build_phases module without relying on installed package.
# build_phases imports from sibling modules (template_compiler, etc.), so
# scripts/ must be on sys.path before we load the module.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_BUILD_PHASES_PATH = _SCRIPTS_DIR / "build_phases.py"
# The E2 template is the single source of truth; build_workflow_scripts copies
# templates/workflows-js/*.js verbatim to <root>/workflows/. The legacy
# scripts/workflows/plan-feature.js was retired (one-canonical-file cleanup).
_TEMPLATES_WORKFLOWS_JS = _REPO_ROOT / "templates" / "workflows-js"
_SOURCE_PLAN_FEATURE = _TEMPLATES_WORKFLOWS_JS / "plan-feature.js"


def _load_build_phases():
    """Load build_phases from scripts/ into a fresh module object."""
    if str(_SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_DIR))

    # Re-use a cached load if already in sys.modules (avoids duplicate exec).
    if "build_phases" in sys.modules:
        return sys.modules["build_phases"]

    spec = importlib.util.spec_from_file_location("build_phases", _BUILD_PHASES_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["build_phases"] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_WORKSPACE_ANSWER_SOURCE = _TEMPLATES_WORKFLOWS_JS / "_shared" / "workspace-answer.js"


def _expected_deployed_text(source: Path) -> str:
    """The text the build deploys for ``source``: the template with its EMPTY WORKSPACE-ANSWER marker pair
    filled from the single tracked block (BO-4300c-3). A template without the pair deploys unchanged."""
    text = source.read_text(encoding="utf-8")
    start_mark, end_mark = "// WORKSPACE-ANSWER-START", "// WORKSPACE-ANSWER-END"
    start = text.find(start_mark)
    if start == -1:
        return text
    end = text.find(end_mark, start)
    block = _WORKSPACE_ANSWER_SOURCE.read_text(encoding="utf-8").strip()
    return text[: start + len(start_mark)] + "\n" + block + "\n" + text[end:]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _minimal_workflows_config() -> dict:
    """Minimal config that enables workflow scripts deployment."""
    return {"workflows": {"enabled": True}}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBuildWorkflowScriptsIncludesPlanFeature(unittest.TestCase):
    """Unit test: build_workflow_scripts() copies plan-feature.js to output dir."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._target = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_build_workflow_scripts_includes_plan_feature(self) -> None:
        # covers: UNKNOWN
        """build_workflow_scripts() must copy plan-feature.js from templates/workflows-js/
        to <output_root>/workflows/ (the location install_shims() maps to .claude/workflows;
        see BP-811).
        """
        # Arrange — mock CLAUDE_CODE_VERSION so the version-gate passes
        os.environ["CLAUDE_CODE_VERSION"] = "2.1.154"
        try:
            build_phases = _load_build_phases()
            config = _minimal_workflows_config()

            # Act
            written = build_phases.build_workflow_scripts(
                self._target, config, dry_run=False, force=True
            )

            # Assert 1 — the function reported at least one file written
            self.assertGreater(
                written,
                0,
                "build_workflow_scripts() returned 0 — no files were written. "
                "plan-feature.js is likely absent from templates/workflows-js/.",
            )

            # Assert 2 — plan-feature.js is present in the output directory.
            # build_workflow_scripts() writes to <root>/workflows/ (BP-811);
            # install_shims() exposes that dir at the consumer's .claude/workflows/.
            dest = self._target / "workflows" / "plan-feature.js"
            self.assertTrue(
                dest.exists(),
                f"plan-feature.js was NOT deployed to {dest}. "
                "Ensure templates/workflows-js/plan-feature.js exists.",
            )

            # Assert 3 — file content matches the canonical source (byte-identical)
            self.assertTrue(
                _SOURCE_PLAN_FEATURE.exists(),
                f"Source file missing: {_SOURCE_PLAN_FEATURE}. "
                "This is the E2 source-of-truth that build_workflow_scripts deploys.",
            )
            # The deployed copy is the source with the shared WORKSPACE-ANSWER block filled in (BO-4300c-3);
            # everything else must be byte-identical.
            self.assertEqual(
                hashlib.sha256(dest.read_bytes()).hexdigest(),
                hashlib.sha256(_expected_deployed_text(_SOURCE_PLAN_FEATURE).encode("utf-8")).hexdigest(),
                "Deployed plan-feature.js SHA-256 does not match the source (with its shared block filled). "
                "Content may have been corrupted or truncated during the copy.",
            )
        finally:
            os.environ.pop("CLAUDE_CODE_VERSION", None)


class TestPlanFeatureDeployedInConsumerConfig(unittest.TestCase):
    """Integration test: with config.workflows.enabled=true, plan-feature.js
    appears in the final deployment package (.claude/workflows/).
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._target = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_plan_feature_deployed_in_consumer_config(self) -> None:
        # covers: UNKNOWN
        """Simulates a consumer install: build_workflow_scripts() with
        workflows.enabled=true must produce plan-feature.js in <output_root>/workflows/
        (the dir install_shims() maps to the consumer's .claude/workflows/; see BP-811).
        """
        # Arrange — set CLAUDE_CODE_VERSION to satisfy version gate
        os.environ["CLAUDE_CODE_VERSION"] = "2.1.200"
        try:
            build_phases = _load_build_phases()

            # Simulate consumer install: minimal skills_config with workflows enabled
            config = {
                "workflows": {
                    "enabled": True,
                }
            }

            # Act — run full workflow script deployment phase
            build_phases.build_workflow_scripts(
                self._target, config, dry_run=False, force=True
            )

            # Assert 1 — deployment phase reports that plan-feature.js was written.
            # Written to <root>/workflows/ (BP-811); shimmed to .claude/workflows/.
            dest = self._target / "workflows" / "plan-feature.js"
            self.assertTrue(
                dest.exists(),
                f"Consumer deployment: plan-feature.js absent from {dest}. "
                "templates/workflows-js/plan-feature.js must be present for "
                "build_workflow_scripts() to deploy it to consumers.",
            )

            # Assert 2 — file is non-empty (guards against a zero-byte placeholder)
            self.assertGreater(
                dest.stat().st_size,
                0,
                "Deployed plan-feature.js is empty. "
                "The source in templates/workflows-js/ must have valid content.",
            )

            # Assert 3 — file size matches the source (guards against silent truncation)
            self.assertTrue(
                _SOURCE_PLAN_FEATURE.exists(),
                f"Source plan-feature.js not found at {_SOURCE_PLAN_FEATURE}.",
            )
            self.assertEqual(
                dest.stat().st_size,
                len(_expected_deployed_text(_SOURCE_PLAN_FEATURE).encode("utf-8")),
                "Deployed plan-feature.js file size differs from source (with its shared block filled). "
                "Content may have been silently truncated.",
            )
        finally:
            os.environ.pop("CLAUDE_CODE_VERSION", None)


if __name__ == "__main__":
    unittest.main()
