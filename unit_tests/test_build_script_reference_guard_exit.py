"""
MODULE: test_build_script_reference_guard_exit
GOAL: Unit tests for AC BP-900b-3 — build.py exits non-zero when broken
    script references are found and writes no partial output.
BUSINESS CONTEXT: When a template references a script that will not be deployed
    to the consumer project, the build must abort before writing any files to
    the target directory. These tests exercise the preflight guard introduced in
    build.py to satisfy AC BP-900b-3.
ARCHITECTURE: Tests import _check_script_reference_guard and
    _get_source_deployable_scripts from build.py via sys.path manipulation. Each
    test uses tempfile.TemporaryDirectory to isolate file system operations.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))


def _import_check_guard():
    """Lazily import _check_script_reference_guard from build."""
    import build as _build
    return _build._check_script_reference_guard


def _import_get_source_deployable():
    """Lazily import _get_source_deployable_scripts from build."""
    import build as _build
    return _build._get_source_deployable_scripts


class TestGetSourceDeployableScripts(unittest.TestCase):
    """Tests for _get_source_deployable_scripts()."""

    def test_ac_bp900b3_includes_ac_store_scripts(self):
        """_get_source_deployable_scripts includes scripts/ac_store/<name> entries.

        Given a package_root with scripts/ac_store/ac_prioritizer.py
        Then the deployable set includes "scripts/ac_store/ac_prioritizer.py".
        """
        get_source_deployable = _import_get_source_deployable()
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            ac_store = pkg / "scripts" / "ac_store"
            ac_store.mkdir(parents=True)
            (ac_store / "ac_prioritizer.py").write_text("# stub", encoding="utf-8")

            # feedback dir must exist to avoid spurious failures
            (pkg / "scripts" / "feedback").mkdir(parents=True)
            (pkg / "templates" / "scripts").mkdir(parents=True)

            result = get_source_deployable(pkg)

        self.assertIn(
            "scripts/ac_store/ac_prioritizer.py",
            result,
            "deployable set must include ac_store scripts",
        )

    def test_ac_bp900b3_includes_standalone_scripts(self):
        """_get_source_deployable_scripts includes templates/scripts standalone scripts.

        Given a package_root with templates/scripts/goal_to_epic.py
        Then the deployable set includes "scripts/goal_to_epic.py".
        """
        get_source_deployable = _import_get_source_deployable()
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            templates_scripts = pkg / "templates" / "scripts"
            templates_scripts.mkdir(parents=True)
            (templates_scripts / "goal_to_epic.py").write_text("# stub", encoding="utf-8")

            (pkg / "scripts" / "ac_store").mkdir(parents=True)
            (pkg / "scripts" / "feedback").mkdir(parents=True)

            result = get_source_deployable(pkg)

        self.assertIn(
            "scripts/goal_to_epic.py",
            result,
            "deployable set must include standalone scripts",
        )

    def test_ac_bp900b3_includes_feedback_scripts(self):
        """_get_source_deployable_scripts includes scripts/feedback named scripts.

        Given a package_root with scripts/feedback/submit_feedback.py
        Then the deployable set includes "scripts/feedback/submit_feedback.py".
        """
        get_source_deployable = _import_get_source_deployable()
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            feedback = pkg / "scripts" / "feedback"
            feedback.mkdir(parents=True)
            (feedback / "submit_feedback.py").write_text("# stub", encoding="utf-8")

            (pkg / "scripts" / "ac_store").mkdir(parents=True)
            (pkg / "templates" / "scripts").mkdir(parents=True)

            result = get_source_deployable(pkg)

        self.assertIn(
            "scripts/feedback/submit_feedback.py",
            result,
            "deployable set must include feedback scripts",
        )

    def test_ac_bp900b3_excludes_pyc_files(self):
        """_get_source_deployable_scripts excludes .pyc compiled bytecode.

        Given a package_root with scripts/ac_store/ac_prioritizer.pyc
        Then the deployable set does NOT include a .pyc path.
        """
        get_source_deployable = _import_get_source_deployable()
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            ac_store = pkg / "scripts" / "ac_store"
            ac_store.mkdir(parents=True)
            (ac_store / "ac_prioritizer.pyc").write_bytes(b"stub")

            (pkg / "scripts" / "feedback").mkdir(parents=True)
            (pkg / "templates" / "scripts").mkdir(parents=True)

            result = get_source_deployable(pkg)

        for path in result:
            self.assertFalse(
                path.endswith(".pyc"),
                f"deployable set must not include .pyc files, got: {path}",
            )

    def test_ac_bp900b3_empty_when_no_sources(self):
        """_get_source_deployable_scripts returns empty set when no source dirs exist."""
        get_source_deployable = _import_get_source_deployable()
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            result = get_source_deployable(pkg)
        self.assertEqual(
            len(result),
            0,
            "deployable set must be empty when no source directories exist",
        )


class TestCheckScriptReferenceGuardReturnCode(unittest.TestCase):
    """Tests for _check_script_reference_guard() exit-code behaviour (AC BP-900b-3)."""

    def test_ac_bp900b3_returns_zero_when_no_refs(self):
        """Guard returns 0 when templates have no script path references.

        Given a package_root with empty agents/ and skills/ template dirs
        When _check_script_reference_guard runs
        Then it returns 0 (build may continue).
        """
        check_guard = _import_check_guard()
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            (pkg / "templates" / "agents").mkdir(parents=True)
            (pkg / "templates" / "skills").mkdir(parents=True)
            (pkg / "scripts" / "ac_store").mkdir(parents=True)
            (pkg / "scripts" / "feedback").mkdir(parents=True)
            (pkg / "templates" / "scripts").mkdir(parents=True)

            result = check_guard(pkg)

        self.assertEqual(result, 0, "guard must return 0 when no refs found")

    def test_ac_bp900b3_returns_zero_when_all_refs_deployed(self):
        """Guard returns 0 when all template script refs are in the deployable set.

        Given a template that references scripts/ac_store/ac_prioritizer.py
        And that script is present in scripts/ac_store/
        When _check_script_reference_guard runs
        Then it returns 0.
        """
        check_guard = _import_check_guard()
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            agents_dir = pkg / "templates" / "agents"
            agents_dir.mkdir(parents=True)
            # Template that references a deployed script
            (agents_dir / "test-agent.md").write_text(
                "Run: python3 scripts/ac_store/ac_prioritizer.py\n",
                encoding="utf-8",
            )
            (pkg / "templates" / "skills").mkdir(parents=True)

            # Corresponding source script exists
            ac_store = pkg / "scripts" / "ac_store"
            ac_store.mkdir(parents=True)
            (ac_store / "ac_prioritizer.py").write_text("# stub", encoding="utf-8")

            (pkg / "scripts" / "feedback").mkdir(parents=True)
            (pkg / "templates" / "scripts").mkdir(parents=True)

            result = check_guard(pkg)

        self.assertEqual(result, 0, "guard must return 0 when all refs are deployed")

    def test_ac_bp900b3_returns_one_when_broken_ref_found(self):
        """Guard returns 1 when a template references a script that will not be deployed.

        Given a template that references scripts/missing_tool.py
        And that script is NOT present in any source directory
        When _check_script_reference_guard runs
        Then it returns 1 (build must abort).
        """
        check_guard = _import_check_guard()
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            agents_dir = pkg / "templates" / "agents"
            agents_dir.mkdir(parents=True)
            # Template references a script that does not exist in source
            (agents_dir / "test-agent.md").write_text(
                "Run: python3 scripts/missing_tool.py\n",
                encoding="utf-8",
            )
            (pkg / "templates" / "skills").mkdir(parents=True)

            # No corresponding source script — deployable set will be empty
            (pkg / "scripts" / "ac_store").mkdir(parents=True)
            (pkg / "scripts" / "feedback").mkdir(parents=True)
            (pkg / "templates" / "scripts").mkdir(parents=True)

            result = check_guard(pkg)

        self.assertEqual(
            result,
            1,
            "guard must return 1 when broken script references are found",
        )

    def test_ac_bp900b3_returns_one_when_multiple_broken_refs(self):
        """Guard returns 1 when multiple broken references are found.

        Given two templates each referencing a script not in the deployable set
        When _check_script_reference_guard runs
        Then it returns 1.
        """
        check_guard = _import_check_guard()
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            agents_dir = pkg / "templates" / "agents"
            agents_dir.mkdir(parents=True)
            (agents_dir / "agent-a.md").write_text(
                "Run: python3 scripts/tool_a.py\n",
                encoding="utf-8",
            )
            (agents_dir / "agent-b.md").write_text(
                "Run: python3 scripts/tool_b.py\n",
                encoding="utf-8",
            )
            (pkg / "templates" / "skills").mkdir(parents=True)

            (pkg / "scripts" / "ac_store").mkdir(parents=True)
            (pkg / "scripts" / "feedback").mkdir(parents=True)
            (pkg / "templates" / "scripts").mkdir(parents=True)

            result = check_guard(pkg)

        self.assertEqual(
            result,
            1,
            "guard must return 1 when multiple broken script references are found",
        )

    def test_ac_bp900b3_partial_refs_broken_exits_nonzero(self):
        """Guard returns 1 even when only one of several refs is broken.

        Given a template with one deployed ref and one broken ref
        When _check_script_reference_guard runs
        Then it returns 1 (the one broken ref is enough to fail).
        """
        check_guard = _import_check_guard()
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp)
            agents_dir = pkg / "templates" / "agents"
            agents_dir.mkdir(parents=True)
            # One good reference, one broken
            (agents_dir / "mixed-agent.md").write_text(
                "Run: python3 scripts/ac_store/ac_prioritizer.py\n"
                "Also: python3 scripts/nonexistent_tool.py\n",
                encoding="utf-8",
            )
            (pkg / "templates" / "skills").mkdir(parents=True)

            # Only the good script exists in source
            ac_store = pkg / "scripts" / "ac_store"
            ac_store.mkdir(parents=True)
            (ac_store / "ac_prioritizer.py").write_text("# stub", encoding="utf-8")

            (pkg / "scripts" / "feedback").mkdir(parents=True)
            (pkg / "templates" / "scripts").mkdir(parents=True)

            result = check_guard(pkg)

        self.assertEqual(
            result,
            1,
            "guard must return 1 when even one broken reference is present",
        )


class TestBuildPyNoPartialDeployment(unittest.TestCase):
    """AC BP-900b-3 integration: main() does not call _run_phases when guard fails.

    Verifies that _run_phases is NOT invoked when _check_script_reference_guard
    returns 1, satisfying the 'no partial deployment' requirement.
    """

    def test_ac_bp900b3_run_phases_not_called_on_broken_ref(self):
        """main() must not call _run_phases() when the script reference guard fails.

        Given _check_script_reference_guard returns 1
        When main() executes
        Then _run_phases() is never called
        And main() returns 1.
        """
        import build as _build

        with patch.object(_build, "_check_script_reference_guard", return_value=1) as mock_guard, \
             patch.object(_build, "_run_phases") as mock_phases, \
             patch.object(_build, "_validate_all", return_value=0), \
             patch.object(_build, "_validate_ac_store_source", return_value=0), \
             patch.object(_build, "load_config", return_value={}), \
             patch.object(_build, "_inject_file_size_limits"), \
             patch.object(_build, "_inject_changelogs_dir"), \
             tempfile.TemporaryDirectory() as tmpdir:
            exit_code = _build.main(["--target-dir", tmpdir])

        mock_guard.assert_called_once()
        mock_phases.assert_not_called()
        self.assertEqual(exit_code, 1, "main() must return 1 when guard detects broken refs")

    def test_ac_bp900b3_run_phases_called_when_guard_passes(self):
        """main() calls _run_phases() when the script reference guard returns 0.

        Given _check_script_reference_guard returns 0
        When main() executes (up to _run_phases call)
        Then _run_phases() is called.
        """
        import build as _build

        with patch.object(_build, "_check_script_reference_guard", return_value=0), \
             patch.object(_build, "_validate_all", return_value=0), \
             patch.object(_build, "_validate_ac_store_source", return_value=0), \
             patch.object(_build, "load_config", return_value={}), \
             patch.object(_build, "_inject_file_size_limits"), \
             patch.object(_build, "_inject_changelogs_dir"), \
             patch.object(_build, "_run_phases", return_value=0) as mock_phases, \
             patch.object(_build, "get_uptodate_count", return_value=0), \
             patch.object(_build, "reset_uptodate_count"), \
             patch.object(_build, "_compute_version_str", return_value="v0.0.0"), \
             patch.object(_build, "_read_package_version", return_value="0.0.0"), \
             patch.object(_build, "write_build_manifest"), \
             patch.object(_build, "_cleanup_stale_paths", return_value=0), \
             patch.object(_build, "_install_shims"), \
             patch.object(_build, "_install_hooks"), \
             patch.object(_build, "scan_for_placeholders", return_value=[]), \
             patch.object(_build, "check_referential_integrity", return_value=[]), \
             patch.object(_build, "validate_agent_self_description", return_value=(0, 0)), \
             patch.object(_build, "check_halt_guard") as mock_halt, \
             tempfile.TemporaryDirectory() as tmpdir:
            # Halt guard needs a mock return that has should_halt = False
            mock_halt.return_value = type("R", (), {"should_halt": False})()
            _build.main(["--target-dir", tmpdir, "--no-shims"])

        mock_phases.assert_called_once()


if __name__ == "__main__":
    unittest.main()
