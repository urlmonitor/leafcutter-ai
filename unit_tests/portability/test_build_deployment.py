"""
MODULE: test_build_deployment
GOAL: TDD red-baseline tests for portability and graceful no-op behaviour.
BUSINESS CONTEXT: Ticket 07 of EPIC-WorktreeQualityGateGuard. Tests cover five
    areas: (1) build.py deploys the 3 guard scripts plus the JSON manifest to the
    correct consumer directory structure; (2) partial-build detection gracefully
    no-ops when one or more scripts are missing; (3) non-worktree detection skips
    gates when running on the main tree or outside a git repo; (4) authoritative
    no-config detection skips gates when leafcutter has not been installed; and
    (5) integration tests confirm a full build.py run into a fresh consumer
    directory produces working gates, and that two sequential builds are
    byte-identical (idempotent).
ARCHITECTURE: Import-based tests call build_phases.build_commit_guardian directly
    using a tmpdir as target_root. Graceful-skip tests import the to-be-implemented
    helper functions (is_worktree, check_guardian_scripts_complete) from
    verify_precommit_active.py — these functions do not yet exist and produce
    AttributeError, which is the valid RED state. Integration tests invoke the
    build_commit_guardian phase function twice on the same tmpdir. All tests are
    RED before implementation.

====================================================================
DECISION HISTORY
====================================================================
- 2026-07-06 [EPIC-WorktreeQualityGateGuard/07]: Initial TDD red-baseline.
  Written BEFORE python-coder implements the portability + graceful no-op
  behaviour described in ticket 07. Expected RED states per group:
    Group 1 (deployment): test_ac_manifest_deployed_to_config_dir fails because
        build_commit_guardian does not yet write to config/commit_guardian/.
    Group 2 (partial-build): AttributeError — is_guardian_complete() absent.
    Group 3 (non-worktree): AttributeError — is_worktree() absent.
    Group 4 (no-config): AttributeError — check_guardian_scripts_complete() absent.
    Group 5 (integration): AssertionError — config/commit_guardian/ never created.
====================================================================
"""
# @ac-tag: BO-1700e-1
# @ac-tag: BO-1700e-3
# @ac-tag: BO-1700e-4
# @ac-tag: BO-1700e-5
# @ac-tag: BO-1700f-1

from __future__ import annotations

import json
import logging
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — make scripts/ importable regardless of cwd.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_TEMPLATES_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# ---------------------------------------------------------------------------
# Import build_phases (build_commit_guardian phase function).
# ---------------------------------------------------------------------------
try:
    from build_phases import build_commit_guardian  # type: ignore[import]
    _BUILD_PHASES_OK = True
except (ImportError, ModuleNotFoundError):
    build_commit_guardian = None  # type: ignore[assignment]
    _BUILD_PHASES_OK = False

# ---------------------------------------------------------------------------
# Import verify_precommit_active module for worktree / partial-build probes.
# Functions is_worktree() and is_guardian_complete() do not yet exist —
# tests that call them will fail with AttributeError (valid RED state).
# ---------------------------------------------------------------------------
try:
    import scripts.commit_guardian.verify_precommit_active as _vpa  # type: ignore[import]
    _VPA_IMPORT_OK = True
except (ImportError, ModuleNotFoundError):
    _vpa = None  # type: ignore[assignment]
    _VPA_IMPORT_OK = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_GUARD_SCRIPTS = (
    "verify_precommit_active.py",
    "precommit_canary.py",
    "ensure_precommit_config.py",
)
_MANIFEST_FILENAME = "commit_guardian.json"

# Minimal config dict accepted by build_commit_guardian.
_MINIMAL_CONFIG: dict = {
    "output_root": ".leafcutter",
    "agents_dir": ".claude/agents",
    "skills_dir": ".claude/skills",
}


def _run_build_commit_guardian(target_root: Path) -> int:
    """Call build_commit_guardian with minimal config; return file-written count."""
    return build_commit_guardian(target_root, _MINIMAL_CONFIG, dry_run=False, force=True)


# ===========================================================================
# Group 1 — Deployment tests
# ===========================================================================


class TestDeployment(unittest.TestCase):
    """Verify that build_commit_guardian deploys the 3 scripts and manifest."""

    def setUp(self) -> None:
        """Create an isolated temporary directory as the consumer root."""
        # covers: BO-1700e-1
        self._tmp = tempfile.TemporaryDirectory()
        self.consumer = Path(self._tmp.name)

    def tearDown(self) -> None:
        """Clean up the temporary directory."""
        self._tmp.cleanup()

    # ------------------------------------------------------------------
    def test_ac_build_deploys_all_3_guard_scripts(self) -> None:
        """AC BO-1700e-1: build_commit_guardian deploys all 3 guard .py files
        to <target>/scripts/commit_guardian/ in a fresh consumer directory."""
        # covers: BO-1700e-1
        if not _BUILD_PHASES_OK:
            self.fail("build_phases import failed — cannot run deployment test")

        _run_build_commit_guardian(self.consumer)

        deployed_dir = self.consumer / "scripts" / "commit_guardian"
        for script_name in _GUARD_SCRIPTS:
            deployed_path = deployed_dir / script_name
            self.assertTrue(
                deployed_path.exists(),
                f"Expected guard script not deployed: {script_name} "
                f"(looked in {deployed_dir})",
            )

    # ------------------------------------------------------------------
    def test_ac_deployed_scripts_byte_identical_to_templates(self) -> None:
        """AC BO-1700f-1-i: deployed guard scripts must be byte-for-byte identical
        to the originals in templates/scripts/commit_guardian/."""
        # covers: BO-1700f-1
        if not _BUILD_PHASES_OK:
            self.fail("build_phases import failed — cannot run byte-identical test")
        if not _TEMPLATES_DIR.exists():
            self.fail(f"Template source directory missing: {_TEMPLATES_DIR}")

        _run_build_commit_guardian(self.consumer)

        deployed_dir = self.consumer / "scripts" / "commit_guardian"
        for script_name in _GUARD_SCRIPTS:
            template_path = _TEMPLATES_DIR / script_name
            deployed_path = deployed_dir / script_name

            if not template_path.exists():
                self.fail(f"Template source missing: {template_path}")

            template_content = template_path.read_text(encoding="utf-8")
            deployed_content = deployed_path.read_text(encoding="utf-8")

            self.assertEqual(
                template_content,
                deployed_content,
                f"Deployed script differs from template: {script_name}",
            )

    # ------------------------------------------------------------------
    def test_ac_manifest_deployed_to_config_dir(self) -> None:
        """AC BO-1700f-1-ii: commit_guardian.json must be deployed to
        <target>/config/commit_guardian/commit_guardian.json (not scripts/).

        RED because build_commit_guardian currently only writes to
        scripts/commit_guardian/ — python-coder must add the config/ deploy path.
        """
        # covers: BO-1700f-1
        if not _BUILD_PHASES_OK:
            self.fail("build_phases import failed — cannot run manifest test")

        _run_build_commit_guardian(self.consumer)

        # Expected canonical manifest location per BO-1700f-1-ii.
        manifest_path = self.consumer / "config" / "commit_guardian" / _MANIFEST_FILENAME
        self.assertTrue(
            manifest_path.exists(),
            f"Manifest not found at expected path: {manifest_path}\n"
            "build_commit_guardian must deploy commit_guardian.json to "
            "config/commit_guardian/ (not only scripts/commit_guardian/).",
        )

        # Verify it is valid JSON.
        raw = manifest_path.read_text(encoding="utf-8")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            self.fail(f"Deployed manifest is not valid JSON: {exc}")

        self.assertIn(
            "hooks_manifest",
            data,
            "Deployed manifest missing required 'hooks_manifest' key",
        )

    # ------------------------------------------------------------------
    def test_ac_build_idempotent(self) -> None:
        """AC BO-1700f-1: Running build_commit_guardian twice produces byte-identical
        files (idempotent deployment)."""
        # covers: BO-1700f-1
        if not _BUILD_PHASES_OK:
            self.fail("build_phases import failed — cannot run idempotency test")

        _run_build_commit_guardian(self.consumer)

        # Capture all files after first build. Skip __pycache__/.pyc — those are
        # runtime-generated bytecode caches, not build artifacts, and are binary
        # (reading them as UTF-8 would spuriously fail). Compare bytes, since
        # "byte-identical" is the actual idempotency contract.
        deployed_dir = self.consumer / "scripts" / "commit_guardian"

        def _snapshot(root: Path) -> dict[str, bytes]:
            snap: dict[str, bytes] = {}
            for p in root.rglob("*"):
                if not p.is_file() or "__pycache__" in p.parts or p.suffix == ".pyc":
                    continue
                snap[str(p.relative_to(root))] = p.read_bytes()
            return snap

        first_pass = _snapshot(deployed_dir)

        _run_build_commit_guardian(self.consumer)

        # Capture all files after second build — must be byte-identical.
        for rel, second_content in _snapshot(deployed_dir).items():
            self.assertEqual(
                first_pass.get(rel),
                second_content,
                f"File content changed between build 1 and build 2: {rel}",
            )


# ===========================================================================
# Group 2 — Partial-build detection tests
# ===========================================================================


class TestPartialBuildDetection(unittest.TestCase):
    """Verify that gates gracefully skip (no error, permits operation) when one
    or more of the 3 guard scripts are absent from the consumer installation.

    All tests in this group are RED until verify_precommit_active.py gains
    is_guardian_complete() (or equivalent) and graceful-skip behaviour.
    """

    # ------------------------------------------------------------------
    def test_ac_gate_gracefully_skips_when_one_script_missing(self) -> None:
        """AC BO-1700e-3: When one guard script is absent, is_guardian_complete()
        returns False and the gate exits 0 (graceful no-op, not an error)."""
        # covers: BO-1700e-3
        with tempfile.TemporaryDirectory() as tmp:
            consumer = Path(tmp)
            scripts_dir = consumer / "scripts" / "commit_guardian"
            scripts_dir.mkdir(parents=True, exist_ok=True)

            # Deploy only 2 of the 3 scripts.
            for script_name in _GUARD_SCRIPTS[:2]:
                (scripts_dir / script_name).write_text("# stub", encoding="utf-8")

            # is_guardian_complete() must exist and return False when 1 script absent.
            # AttributeError is the expected RED failure (function not yet implemented).
            self.assertFalse(
                _vpa.is_guardian_complete(consumer),  # type: ignore[attr-defined]
                "is_guardian_complete() should return False when only 2 of 3 scripts present",
            )

    # ------------------------------------------------------------------
    def test_ac_gate_skips_all_when_all_scripts_missing(self) -> None:
        """AC BO-1700e-3: When all 3 guard scripts are absent (fresh consumer,
        no build.py run), is_guardian_complete() returns False."""
        # covers: BO-1700e-3
        with tempfile.TemporaryDirectory() as tmp:
            consumer = Path(tmp)
            # scripts/commit_guardian/ does not exist — completely uninitialised.
            self.assertFalse(
                _vpa.is_guardian_complete(consumer),  # type: ignore[attr-defined]
                "is_guardian_complete() should return False when scripts/commit_guardian/ absent",
            )

    # ------------------------------------------------------------------
    def test_ac_warning_logged_not_error_when_gates_skipped(self) -> None:
        """AC BO-1700e-3: When the gate skips due to missing scripts, the skip is
        logged at WARNING level (not ERROR) and the function returns without raising."""
        # covers: BO-1700e-3
        with tempfile.TemporaryDirectory() as tmp:
            consumer = Path(tmp)
            # No scripts present — gate must skip gracefully.

            with self.assertLogs("scripts.commit_guardian.verify_precommit_active",
                                 level=logging.WARNING) as cm:
                result = _vpa.graceful_skip_if_incomplete(consumer)  # type: ignore[attr-defined]

            # Must return True (operation permitted) — not raise.
            self.assertTrue(
                result,
                "graceful_skip_if_incomplete() must return True (permit operation) when skipping",
            )

            # At least one WARNING must mention the missing scripts.
            warning_messages = "\n".join(cm.output)
            self.assertIn(
                "missing",
                warning_messages.lower(),
                "Expected a warning mentioning missing scripts; got: " + warning_messages,
            )


# ===========================================================================
# Group 3 — Non-worktree detection tests
# ===========================================================================


class TestNonWorktreeDetection(unittest.TestCase):
    """Verify that gates skip gracefully when not in a git worktree.

    All tests are RED until verify_precommit_active.py gains is_worktree().
    """

    # ------------------------------------------------------------------
    def test_ac_gate_skips_when_git_dir_is_main_tree(self) -> None:
        """AC BO-1700e-4: is_worktree() returns False when .git is a plain
        directory (the main working tree), allowing commits without invoking gates."""
        # covers: BO-1700e-4
        with tempfile.TemporaryDirectory() as tmp:
            main_tree = Path(tmp)
            # Simulate a main working tree: .git is a directory (not a file).
            git_dir = main_tree / ".git"
            git_dir.mkdir()
            (git_dir / "config").write_text("[core]\n\trepositoryformatversion = 0\n",
                                             encoding="utf-8")

            result = _vpa.is_worktree(main_tree)  # type: ignore[attr-defined]
            self.assertFalse(
                result,
                "is_worktree() must return False when .git is a directory (main tree)",
            )

    # ------------------------------------------------------------------
    def test_ac_gate_skips_when_not_in_git_repo(self) -> None:
        """AC BO-1700e-4: is_worktree() returns False when there is no .git
        entry at all (fresh directory, non-git consumer install)."""
        # covers: BO-1700e-4
        with tempfile.TemporaryDirectory() as tmp:
            non_repo = Path(tmp)
            # No .git file or directory — not a git repo.
            result = _vpa.is_worktree(non_repo)  # type: ignore[attr-defined]
            self.assertFalse(
                result,
                "is_worktree() must return False when .git is absent (not a git repo)",
            )

    # ------------------------------------------------------------------
    def test_ac_worktree_detection_accurate_for_worktree(self) -> None:
        """AC BO-1700e-4: is_worktree() returns True when .git is a file whose
        content begins with 'gitdir:' (the worktree topology)."""
        # covers: BO-1700e-4
        with tempfile.TemporaryDirectory() as tmp:
            worktree_root = Path(tmp)

            # Simulate a git worktree: .git is a *file* containing a gitdir pointer.
            fake_gitdir = Path(tmp) / "fake_main.git" / "worktrees" / "my-wt"
            fake_gitdir.mkdir(parents=True)
            # Write .git file (worktree topology).
            (worktree_root / ".git").write_text(
                f"gitdir: {fake_gitdir.as_posix()}\n", encoding="utf-8"
            )
            # The gitdir itself must exist and have a commondir entry.
            fake_commondir = fake_gitdir / "commondir"
            fake_commondir.write_text("../../\n", encoding="utf-8")

            result = _vpa.is_worktree(worktree_root)  # type: ignore[attr-defined]
            self.assertTrue(
                result,
                "is_worktree() must return True when .git is a file (worktree topology)",
            )


# ===========================================================================
# Group 4 — "No config" detection tests
# ===========================================================================


class TestNoConfigDetection(unittest.TestCase):
    """Verify that gates opt-in only after build.py has deployed all scripts.

    All tests are RED until verify_precommit_active.py / the gate scripts gain
    the check_guardian_scripts_complete() or equivalent API.
    """

    # ------------------------------------------------------------------
    def test_ac_gate_skips_when_scripts_not_deployed(self) -> None:
        """AC BO-1700e-5: When no guard scripts exist in scripts/commit_guardian/,
        check_guardian_scripts_complete() returns False — gates must not run."""
        # covers: BO-1700e-5
        with tempfile.TemporaryDirectory() as tmp:
            uninitialised = Path(tmp)
            # scripts/commit_guardian/ is entirely absent.
            result = _vpa.check_guardian_scripts_complete(uninitialised)  # type: ignore[attr-defined]
            self.assertFalse(
                result,
                "check_guardian_scripts_complete() must return False "
                "when scripts/commit_guardian/ is absent (build.py never run)",
            )

    # ------------------------------------------------------------------
    def test_ac_gate_skips_gracefully_if_config_dir_missing(self) -> None:
        """AC BO-1700e-5: When config/commit_guardian/ does not exist (no manifest),
        check_guardian_scripts_complete() returns False without raising an exception."""
        # covers: BO-1700e-5
        with tempfile.TemporaryDirectory() as tmp:
            consumer = Path(tmp)
            # Create scripts but omit config/ entirely.
            scripts_dir = consumer / "scripts" / "commit_guardian"
            scripts_dir.mkdir(parents=True)
            for script_name in _GUARD_SCRIPTS:
                (scripts_dir / script_name).write_text("# stub", encoding="utf-8")
            # config/commit_guardian/ is absent.

            # Must not raise; must return False (manifest absent → incomplete).
            try:
                result = _vpa.check_guardian_scripts_complete(consumer)  # type: ignore[attr-defined]
            except Exception as exc:  # noqa: BLE001
                self.fail(
                    f"check_guardian_scripts_complete() raised unexpectedly "
                    f"when config/ is missing: {type(exc).__name__}: {exc}"
                )

            self.assertFalse(
                result,
                "check_guardian_scripts_complete() must return False when "
                "config/commit_guardian/commit_guardian.json is absent",
            )


# ===========================================================================
# Group 5 — Integration tests for consumer installation
# ===========================================================================


class TestConsumerIntegration(unittest.TestCase):
    """End-to-end tests: build.py phase → fresh consumer directory.

    Group 5 tests are RED because test_ac_build_produces_manifest_at_config_dir
    asserts the canonical config/ path that build_commit_guardian does not yet
    write to.
    """

    def setUp(self) -> None:
        """Create an isolated temporary directory as the consumer root."""
        # covers: BO-1700f-1
        self._tmp = tempfile.TemporaryDirectory()
        self.consumer = Path(self._tmp.name)

    def tearDown(self) -> None:
        """Clean up the temporary directory."""
        self._tmp.cleanup()

    # ------------------------------------------------------------------
    def test_ac_build_produces_working_gates_in_fresh_consumer(self) -> None:
        """AC BO-1700f-1: A single build_commit_guardian call on a fresh tmpdir
        produces all 3 guard scripts in scripts/commit_guardian/ AND the manifest
        in config/commit_guardian/commit_guardian.json."""
        # covers: BO-1700f-1
        if not _BUILD_PHASES_OK:
            self.fail("build_phases import failed — cannot run integration test")

        _run_build_commit_guardian(self.consumer)

        # Assert all 3 guard scripts exist.
        scripts_dir = self.consumer / "scripts" / "commit_guardian"
        for script_name in _GUARD_SCRIPTS:
            self.assertTrue(
                (scripts_dir / script_name).exists(),
                f"Guard script missing after build: {script_name}",
            )

        # Assert the manifest is at the canonical config/ path (BO-1700f-1-ii).
        # This assertion is RED until build_commit_guardian is updated to deploy
        # commit_guardian.json to config/commit_guardian/.
        manifest = self.consumer / "config" / "commit_guardian" / _MANIFEST_FILENAME
        self.assertTrue(
            manifest.exists(),
            f"Manifest not found at config path: {manifest}\n"
            "build_commit_guardian must be updated to deploy the manifest to "
            "config/commit_guardian/ (BO-1700f-1-ii).",
        )

    # ------------------------------------------------------------------
    def test_ac_two_builds_on_same_consumer_are_identical(self) -> None:
        """AC BO-1700f-1: Two sequential build_commit_guardian calls on the same
        consumer directory produce byte-identical results (idempotency)."""
        # covers: BO-1700f-1
        if not _BUILD_PHASES_OK:
            self.fail("build_phases import failed — cannot run idempotency test")

        _run_build_commit_guardian(self.consumer)

        # Snapshot all files in scripts/commit_guardian/ after first build.
        # Skip __pycache__/.pyc (runtime bytecode caches, not build artifacts and
        # binary); compare bytes since byte-identity is the idempotency contract.
        scripts_dir = self.consumer / "scripts" / "commit_guardian"

        def _snapshot(root: Path) -> dict[str, bytes]:
            snap: dict[str, bytes] = {}
            for p in root.rglob("*"):
                if not p.is_file() or "__pycache__" in p.parts or p.suffix == ".pyc":
                    continue
                snap[str(p.relative_to(root))] = p.read_bytes()
            return snap

        snapshot_first = _snapshot(scripts_dir)

        _run_build_commit_guardian(self.consumer)

        # Second build must produce byte-identical content for every file.
        for rel, content_second in _snapshot(scripts_dir).items():
            self.assertEqual(
                snapshot_first.get(rel),
                content_second,
                f"File changed between build 1 and build 2: {rel}\n"
                "Idempotency violation: build_commit_guardian is not stable.",
            )

        # Also verify the config/ manifest is identical (requires BO-1700f-1-ii fix).
        manifest = self.consumer / "config" / "commit_guardian" / _MANIFEST_FILENAME
        if manifest.exists():
            first_manifest = manifest.read_text(encoding="utf-8")
            _run_build_commit_guardian(self.consumer)
            second_manifest = manifest.read_text(encoding="utf-8")
            self.assertEqual(
                first_manifest,
                second_manifest,
                "Manifest changed between build 1 and build 2 "
                "(config/commit_guardian/commit_guardian.json not stable)",
            )
        else:
            # Manifest path absent → will fail once BO-1700f-1-ii is implemented.
            self.fail(
                f"Manifest not found at config path after first build: {manifest}\n"
                "build_commit_guardian must be updated (BO-1700f-1-ii)."
            )


if __name__ == "__main__":
    unittest.main()
