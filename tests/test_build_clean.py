"""
Tests for build.py --clean mode.

These are TDD stubs written BEFORE python-coder implements the feature.
All tests in this file are expected to be RED (failing) until python-coder
implements clean_stale_artifacts() in build_phases.py and wires --clean into
build.py.

Test stubs import the functions and call them with fixture data. They should
fail with ImportError or AttributeError until the implementation exists.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BUILD_PHASES_PATH = _REPO_ROOT / "scripts" / "build_phases.py"
_BUILD_PATH = _REPO_ROOT / "scripts" / "build.py"


def _load_build_phases():
    """Load build_phases module from the scripts directory."""
    # build_phases imports from several sibling modules; ensure scripts/ is on sys.path
    scripts_dir = str(_REPO_ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    spec = importlib.util.spec_from_file_location("build_phases", _BUILD_PHASES_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["build_phases"] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_build():
    """Load build module from the scripts directory."""
    scripts_dir = str(_REPO_ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    spec = importlib.util.spec_from_file_location("_build", _BUILD_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_build"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestCleanRemovesOrphanedAgent(unittest.TestCase):
    """clean_stale_artifacts() removes agent files with no corresponding source template."""

    def test_clean_removes_orphaned_agent(self):
        """
        Given a target dir containing an agent file that has no matching source template,
        when clean_stale_artifacts() is called with that target dir and an empty
        source manifest (no agents),
        then the orphaned agent file is removed from the target dir.

        Implementation needed:
          - build_phases.clean_stale_artifacts(target_dir, source_manifests) must exist.
          - When agents dir has a file not in source_manifests['agents'], remove it.
        """
        build_phases = _load_build_phases()

        # This line should raise AttributeError until clean_stale_artifacts is implemented
        clean_fn = getattr(build_phases, "clean_stale_artifacts")

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            agents_dir = target / ".claude" / "agents"
            agents_dir.mkdir(parents=True)
            orphan = agents_dir / "orphan-agent.md"
            orphan.write_text("# Orphaned agent")

            # source_manifests with no agents → everything in agents_dir is orphaned
            source_manifests = {
                "agents": set(),
                "skills": set(),
                "hooks": set(),
            }

            removed_count = clean_fn(target, source_manifests)

            self.assertFalse(orphan.exists(), "Orphaned agent file should have been removed")
            self.assertGreater(removed_count, 0, "Should report at least one removal")


class TestCleanRemovesOrphanedSkill(unittest.TestCase):
    """clean_stale_artifacts() removes skill directories with no corresponding source template."""

    def test_clean_removes_orphaned_skill(self):
        """
        Given a target dir containing a skill directory that has no matching source template,
        when clean_stale_artifacts() is called with that target dir and an empty
        source manifest (no skills),
        then the orphaned skill directory is removed from the target dir.

        Implementation needed:
          - build_phases.clean_stale_artifacts must handle skills (directories, not files).
          - When skills dir has a subdir not in source_manifests['skills'], remove it.
        """
        build_phases = _load_build_phases()
        clean_fn = getattr(build_phases, "clean_stale_artifacts")

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            skills_dir = target / ".claude" / "skills"
            orphan_skill_dir = skills_dir / "orphan-skill"
            orphan_skill_dir.mkdir(parents=True)
            (orphan_skill_dir / "SKILL.md").write_text("# Orphaned skill")

            source_manifests = {
                "agents": set(),
                "skills": set(),
                "hooks": set(),
            }

            removed_count = clean_fn(target, source_manifests)

            self.assertFalse(
                orphan_skill_dir.exists(),
                "Orphaned skill directory should have been removed"
            )
            self.assertGreater(removed_count, 0, "Should report at least one removal")


class TestCleanRemovesOrphanedHook(unittest.TestCase):
    """clean_stale_artifacts() removes hook files with no corresponding source template."""

    def test_clean_removes_orphaned_hook(self):
        """
        Given a target dir containing a hook file that has no matching source template,
        when clean_stale_artifacts() is called with that target dir and an empty
        source manifest (no hooks),
        then the orphaned hook file is removed.

        Implementation needed:
          - build_phases.clean_stale_artifacts must handle hooks directory.
          - When hooks dir has a file not in source_manifests['hooks'], remove it.
        """
        build_phases = _load_build_phases()
        clean_fn = getattr(build_phases, "clean_stale_artifacts")

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            hooks_dir = target / ".claude" / "hooks"
            hooks_dir.mkdir(parents=True)
            orphan_hook = hooks_dir / "orphan_hook.py"
            orphan_hook.write_text("# Orphaned hook")

            source_manifests = {
                "agents": set(),
                "skills": set(),
                "hooks": set(),
            }

            removed_count = clean_fn(target, source_manifests)

            self.assertFalse(orphan_hook.exists(), "Orphaned hook file should have been removed")
            self.assertGreater(removed_count, 0, "Should report at least one removal")


class TestCleanNoopOnValidArtifacts(unittest.TestCase):
    """clean_stale_artifacts() removes nothing when all artifacts have matching sources."""

    def test_clean_noop_on_valid_artifacts(self):
        """
        Given a target dir where all artifact files have matching source templates
        (i.e. they appear in source_manifests),
        when clean_stale_artifacts() is called,
        then no files are removed and the function returns 0.

        Implementation needed:
          - clean_stale_artifacts must check source_manifests before removing.
          - Files present in source_manifests must NOT be removed.
        """
        build_phases = _load_build_phases()
        clean_fn = getattr(build_phases, "clean_stale_artifacts")

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            agents_dir = target / ".claude" / "agents"
            agents_dir.mkdir(parents=True)
            valid_agent = agents_dir / "my-agent.md"
            valid_agent.write_text("# Valid agent")

            # source_manifests includes this agent — it's NOT an orphan
            source_manifests = {
                "agents": {"my-agent.md"},
                "skills": set(),
                "hooks": set(),
            }

            removed_count = clean_fn(target, source_manifests)

            self.assertTrue(valid_agent.exists(), "Valid agent file must NOT be removed")
            self.assertEqual(removed_count, 0, "No files should be removed when all are valid")


class TestCleanDoesNotRemoveUnmanagedFiles(unittest.TestCase):
    """clean_stale_artifacts() does not remove files build.py didn't create."""

    def test_clean_does_not_remove_unmanaged_files(self):
        """
        Given a file in the target dir that build.py does NOT manage
        (e.g. a user-authored file in a non-managed subdirectory or with a
        non-managed name that doesn't follow artifact-type patterns),
        when clean_stale_artifacts() is called,
        then the unmanaged file is NOT removed.

        Implementation needed:
          - clean_stale_artifacts must only scan known artifact directories
            (.claude/agents/, .claude/skills/, .claude/hooks/).
          - Files outside those directories must never be touched.
        """
        build_phases = _load_build_phases()
        clean_fn = getattr(build_phases, "clean_stale_artifacts")

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)

            # A user-authored file in a non-managed location
            user_dir = target / "my_project"
            user_dir.mkdir(parents=True)
            user_file = user_dir / "important_file.txt"
            user_file.write_text("Do not delete me")

            # A file in .claude/ but NOT in agents/, skills/, or hooks/
            claude_dir = target / ".claude"
            claude_dir.mkdir(parents=True)
            user_claude_file = claude_dir / "my_custom_config.json"
            user_claude_file.write_text('{"user": "config"}')

            source_manifests = {
                "agents": set(),
                "skills": set(),
                "hooks": set(),
            }

            removed_count = clean_fn(target, source_manifests)

            self.assertTrue(
                user_file.exists(),
                "User file outside managed dirs must NOT be removed"
            )
            self.assertTrue(
                user_claude_file.exists(),
                "User .claude/ file outside managed subdirs must NOT be removed"
            )


class TestBuildCleanArgument(unittest.TestCase):
    """build.py main() accepts a --clean argument without error."""

    def test_clean_flag_accepted_by_argparse(self):
        """
        Given build.py's argparse block,
        when --clean is passed as a CLI argument,
        then argparse parses it without raising SystemExit or an error.

        Implementation needed:
          - build.main(argv) must include a --clean argument in its parser.
          - Parsing ['--clean', '--validate-only'] must succeed (validate-only
            prevents full build; clean flag just needs to be present).
        """
        build = _load_build()

        # Attempt to parse args that include --clean.
        # If --clean is not registered, argparse will raise SystemExit(2).
        # We call build.main() with --validate-only so it doesn't try to
        # actually run the build phases (which need a real config).
        # But first, just check the parser accepts --clean by importing
        # and calling parse_args directly.

        # Build a minimal parser mirror by parsing --help output, OR
        # just call main() and expect it to fail for config reasons (not argparse).
        # The test passes if SystemExit is NOT raised with exit code 2 (argparse error).
        try:
            # Using --validate-only with a non-existent target will fail at
            # config load, which is exit(1) not exit(2). That's acceptable.
            # If --clean is unknown, exit(2) fires before config load.
            build.main(["--clean", "--validate-only", "--target-dir", "/nonexistent-dir"])
        except SystemExit as e:
            self.assertNotEqual(
                e.code, 2,
                "--clean caused argparse error (exit code 2) — flag not registered in argparse"
            )
        except Exception:
            # Any other exception is acceptable (config load failure, etc.)
            pass


class TestCleanPrintsRemovals(unittest.TestCase):
    """clean_stale_artifacts() prints each removal to stdout."""

    def test_clean_prints_each_removal(self):
        """
        Given a target dir with orphaned artifacts,
        when clean_stale_artifacts() runs,
        then it prints one line per removed artifact containing the artifact path.

        Implementation needed:
          - clean_stale_artifacts must print each removal.
          - The print format should be: 'Removing stale artifact: <path>'
        """
        build_phases = _load_build_phases()
        clean_fn = getattr(build_phases, "clean_stale_artifacts")

        import io
        from contextlib import redirect_stdout

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            agents_dir = target / ".claude" / "agents"
            agents_dir.mkdir(parents=True)
            orphan = agents_dir / "stale-agent.md"
            orphan.write_text("# Stale agent")

            source_manifests = {
                "agents": set(),
                "skills": set(),
                "hooks": set(),
            }

            buf = io.StringIO()
            with redirect_stdout(buf):
                clean_fn(target, source_manifests)

            output = buf.getvalue()
            self.assertIn(
                "stale-agent.md",
                output,
                "clean_stale_artifacts should print the name of each removed artifact"
            )


class TestCleanNoStaleArtifactsMessage(unittest.TestCase):
    """clean_stale_artifacts() prints 'No stale artifacts found' when nothing is removed."""

    def test_clean_noop_prints_no_stale_message(self):
        """
        Given a clean state (no orphans),
        when clean_stale_artifacts() runs,
        then it prints 'No stale artifacts found' (or similar) and returns 0.

        Implementation needed:
          - When removed_count == 0, print a 'No stale artifacts found' message.
        """
        build_phases = _load_build_phases()
        clean_fn = getattr(build_phases, "clean_stale_artifacts")

        import io
        from contextlib import redirect_stdout

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            # No artifact directories created → truly empty

            source_manifests = {
                "agents": set(),
                "skills": set(),
                "hooks": set(),
            }

            buf = io.StringIO()
            with redirect_stdout(buf):
                result = clean_fn(target, source_manifests)

            self.assertEqual(result, 0)
            output = buf.getvalue()
            self.assertIn(
                "No stale artifacts found",
                output,
                "Should print 'No stale artifacts found' when nothing is removed"
            )


if __name__ == "__main__":
    unittest.main()
