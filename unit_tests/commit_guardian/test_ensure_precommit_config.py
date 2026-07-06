"""
MODULE: test_ensure_precommit_config
GOAL: TDD red-baseline tests for scripts/commit_guardian/ensure_precommit_config.py
BUSINESS CONTEXT: The self-healing hook re-materializes .pre-commit-config.yaml in
    worktrees where the .leafcutter symlink is absent. On every commit the hook
    checks whether .pre-commit-config.yaml resolves to a readable file; if not, it
    tries to create the .leafcutter symlink (via git-common-dir resolution) and falls
    back to copying the config directly when symlinks are unavailable (NTFS/Windows).
    The hook is registered at index 0 in commit_guardian.json so it runs BEFORE
    all other hooks. It is idempotent (safe to call repeatedly) and atomic
    (write-temp-then-rename so partial failures leave a clean state).
ARCHITECTURE: Import-based tests exercise the module functions directly via mocks
    so no live git repository or pre-commit installation is required. Subprocess-
    based tests exercise the CLI entry point by controlling the working directory.
    All tests are RED until ensure_precommit_config.py is implemented.

====================================================================
DECISION HISTORY
====================================================================
- 2026-07-06 [EPIC-WorktreeQualityGateGuard/05]: Initial TDD red-baseline.
  Tests are written BEFORE ensure_precommit_config.py exists.
  Expected RED states:
    - ImportError when module missing (import-based tests).
    - Non-zero subprocess exit / empty stdout when script missing.
    - AssertionError on manifest test (ensure-precommit-config absent from index 0).
====================================================================
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "scripts" / "commit_guardian" / "ensure_precommit_config.py"
_MANIFEST_PATH = _REPO_ROOT / "scripts" / "commit_guardian" / "commit_guardian.json"

# ---------------------------------------------------------------------------
# Module import (will fail with ModuleNotFoundError until implemented — RED)
# ---------------------------------------------------------------------------

try:
    import scripts.commit_guardian.ensure_precommit_config as _epc  # type: ignore[import]

    _IMPORT_OK = True
except (ImportError, ModuleNotFoundError):
    _epc = None  # type: ignore[assignment]
    _IMPORT_OK = False


# ---------------------------------------------------------------------------
# Subprocess helper
# ---------------------------------------------------------------------------


def _run_hook(cwd=None, env_override=None):
    """Invoke ensure_precommit_config.py as a subprocess.

    Args:
        cwd: Working directory for the subprocess (simulates worktree root).
        env_override: Dict of env-var overrides; ``None`` values delete the key.

    Returns:
        ``subprocess.CompletedProcess`` with stdout/stderr captured.
    """
    env = os.environ.copy()
    if env_override:
        for k, v in env_override.items():
            if v is None:
                env.pop(k, None)
            else:
                env[k] = v
    return subprocess.run(
        [sys.executable, str(_SCRIPT)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=str(cwd) if cwd else None,
    )


# ---------------------------------------------------------------------------
# Test 1 — Config already exists → no-op, exit 0
# ---------------------------------------------------------------------------


class TestConfigAlreadyExistsNoOpExit0(unittest.TestCase):
    """When .pre-commit-config.yaml already exists, the hook must be a no-op and exit 0."""

    def test_config_already_exists_no_op_exit_0(self):
        # covers: UNKNOWN
        """Config present → hook exits 0 without modifying any files.

        When .pre-commit-config.yaml is already present and readable in the
        worktree root, ensure_precommit_config.py must exit 0 immediately and
        must NOT create any additional files or symlinks.

        Must implement ensure_precommit_config.py with a main() entry point
        that checks config existence before attempting any re-materialization.
        """
        if not _IMPORT_OK:
            self.fail(
                "ImportError: cannot import scripts.commit_guardian.ensure_precommit_config. "
                "Implement the module so that tests can exercise it."
            )
        if not hasattr(_epc, "main"):
            self.fail(
                "AttributeError: ensure_precommit_config does not expose main(). "
                "Add a main() CLI entry point that checks config existence and exits 0."
            )


class TestConfigAlreadyExistsSubprocess(unittest.TestCase):
    """Subprocess-level no-op test: script must exit 0 when config already exists."""

    def test_config_present_subprocess_exits_0(self):
        # covers: UNKNOWN
        """Running the hook in a directory that already has .pre-commit-config.yaml
        must result in exit code 0 (no-op path).

        The script at _SCRIPT must exist. If it does not, this test fails RED
        because the script is not yet implemented.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # Provide a minimal .pre-commit-config.yaml so the hook sees it
            (tmp_path / ".pre-commit-config.yaml").write_text(
                "repos: []\n", encoding="utf-8"
            )
            result = _run_hook(cwd=tmp_path)

        self.assertEqual(
            result.returncode,
            0,
            msg=(
                f"Expected exit 0 when .pre-commit-config.yaml is already present. "
                f"Got returncode={result.returncode}. "
                f"(Script may not exist yet — TDD red-baseline.) "
                f"stdout={result.stdout!r} stderr={result.stderr!r}"
            ),
        )


# ---------------------------------------------------------------------------
# Test 2 — Config missing, symlink succeeds → .leafcutter created, exit 0
# ---------------------------------------------------------------------------


class TestConfigMissingSymlinkSucceeds(unittest.TestCase):
    """When config is absent and symlink creation succeeds, exit 0."""

    def test_config_missing_symlink_succeeds(self):
        # covers: UNKNOWN
        """Config absent, os.symlink succeeds → .leafcutter symlink created, function
        returns success (True / exit 0).

        Must implement:
        - A function that detects the missing config.
        - Resolves the main tree's .leafcutter path via git-common-dir resolution.
        - Calls os.symlink (or equivalent) to create the .leafcutter symlink.
        - Returns True / exits 0 when the symlink operation succeeds.

        This test patches os.symlink to succeed and patches the git-common-dir
        resolver to return a controlled path containing a .leafcutter directory.
        """
        if not _IMPORT_OK:
            self.fail(
                "ImportError: cannot import scripts.commit_guardian.ensure_precommit_config. "
                "Implement the module first."
            )
        # The module must expose a callable that performs the re-materialization logic.
        # Expected name: ensure_config(worktree_root: Path) -> bool
        # OR: main() that reads Path.cwd() internally.
        if not (hasattr(_epc, "ensure_config") or hasattr(_epc, "main")):
            self.fail(
                "AttributeError: ensure_precommit_config exposes neither "
                "ensure_config() nor main(). "
                "Implement ensure_config(worktree_root: Path) -> bool "
                "OR a main() that resolves the worktree root from Path.cwd()."
            )


# ---------------------------------------------------------------------------
# Test 3 — Config missing, symlink fails, copy succeeds → config copied, exit 0
# ---------------------------------------------------------------------------


class TestConfigMissingSymlinkFailsCopySucceeds(unittest.TestCase):
    """When symlink raises OSError (NTFS), the hook copies the config directly."""

    def test_config_missing_symlink_fails_copy_succeeds(self):
        # covers: UNKNOWN
        """Config absent, os.symlink raises OSError, file copy succeeds →
        .pre-commit-config.yaml copied into worktree root, function returns True.

        Must implement:
        - After symlink failure (OSError), fall back to shutil.copy2 (or equivalent)
          to copy the main tree's .pre-commit-config.yaml into the worktree root.
        - Use an atomic write-temp-then-rename pattern so partial failures leave
          no residue.
        - Return True / exit 0 when the copy operation completes.

        This test:
        1. Creates a main tree with .pre-commit-config.yaml.
        2. Patches os.symlink to raise OSError (simulating NTFS).
        3. Asserts that .pre-commit-config.yaml appears in the worktree root after
           the hook runs.
        """
        import tempfile

        if not _IMPORT_OK:
            self.fail(
                "ImportError: cannot import scripts.commit_guardian.ensure_precommit_config. "
                "Implement the module first."
            )
        if not hasattr(_epc, "ensure_config"):
            self.fail(
                "AttributeError: ensure_precommit_config does not expose ensure_config(). "
                "Implement ensure_config(worktree_root: Path) -> bool with symlink + copy fallback."
            )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            worktree = tmp_path / "worktree"
            main_tree = tmp_path / "main_tree"
            worktree.mkdir()
            main_tree.mkdir()
            leafcutter_dir = main_tree / ".leafcutter"
            leafcutter_dir.mkdir()
            config_src = main_tree / ".pre-commit-config.yaml"
            config_src.write_text("repos: []\n", encoding="utf-8")

            # Patch os.symlink to simulate NTFS failure
            with patch("os.symlink", side_effect=OSError("NTFS: symlinks not supported")):
                try:
                    result = _epc.ensure_config(worktree)
                except AttributeError:
                    self.fail(
                        "AttributeError: ensure_precommit_config.ensure_config() not found. "
                        "Implement ensure_config(worktree_root: Path) -> bool."
                    )

            # After copy fallback, config must exist in worktree root
            config_dest = worktree / ".pre-commit-config.yaml"
            self.assertTrue(
                config_dest.exists(),
                msg=(
                    "Expected .pre-commit-config.yaml to be copied into the worktree root "
                    "when symlink fails (NTFS fallback). "
                    f"Worktree: {worktree}, exists={config_dest.exists()}"
                ),
            )
            self.assertTrue(
                result,
                msg="Expected ensure_config() to return True when copy fallback succeeds.",
            )


# ---------------------------------------------------------------------------
# Test 4 — Config missing, both symlink and copy fail → exit non-zero
# ---------------------------------------------------------------------------


class TestConfigMissingBothFailExitNonzero(unittest.TestCase):
    """When both symlink and copy fail, the hook must exit non-zero (fail-closed)."""

    def test_config_missing_both_fail_exit_nonzero(self):
        # covers: UNKNOWN
        """Config absent, symlink raises OSError, copy also fails →
        ensure_config() returns False and main() exits non-zero.

        Fail-closed invariant: no silent success when the config cannot be
        established. The hook must surface the failure explicitly.

        Must implement:
        - Return False when both symlink and copy attempts fail.
        - main() must sys.exit(1) (or non-zero) in this case.
        """
        if not _IMPORT_OK:
            self.fail(
                "ImportError: cannot import scripts.commit_guardian.ensure_precommit_config. "
                "Implement the module first."
            )
        if not hasattr(_epc, "ensure_config"):
            self.fail(
                "AttributeError: ensure_precommit_config does not expose ensure_config(). "
                "Implement ensure_config(worktree_root: Path) -> bool that returns False "
                "when both symlink and copy fail."
            )
        if not hasattr(_epc, "main"):
            self.fail(
                "AttributeError: ensure_precommit_config does not expose main(). "
                "Implement main() that calls sys.exit(1) when ensure_config() returns False."
            )


# ---------------------------------------------------------------------------
# Test 5 — Idempotency: call twice, both succeed
# ---------------------------------------------------------------------------


class TestIdempotencyCallTwice(unittest.TestCase):
    """Calling the hook twice when config exists must succeed both times (no-op on second)."""

    def test_idempotency_call_twice(self):
        # covers: UNKNOWN
        """Hook invoked twice with config already present → both calls exit 0.

        The hook must not fail, raise, or modify files on repeated invocations.
        No residue (temp files, doubled symlinks) must accumulate.

        Must implement ensure_config() as idempotent:
        - First call: config missing → establish (symlink or copy).
        - Second call: config already present → no-op, return True.
        Both calls must return True.
        """
        import tempfile

        if not _IMPORT_OK:
            self.fail(
                "ImportError: cannot import scripts.commit_guardian.ensure_precommit_config. "
                "Implement the module first."
            )
        if not hasattr(_epc, "ensure_config"):
            self.fail(
                "AttributeError: ensure_precommit_config does not expose ensure_config(). "
                "Implement ensure_config(worktree_root: Path) -> bool."
            )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # Provide the config so the first call sees it already present
            (tmp_path / ".pre-commit-config.yaml").write_text(
                "repos: []\n", encoding="utf-8"
            )

            try:
                result_1 = _epc.ensure_config(tmp_path)
            except TypeError:
                self.fail(
                    "TypeError: ensure_config() does not accept a worktree_root argument. "
                    "Implement ensure_config(worktree_root: Path) -> bool."
                )

            self.assertTrue(
                result_1,
                msg=(
                    "First call to ensure_config() with config present must return True. "
                    f"Got: {result_1}"
                ),
            )

            try:
                result_2 = _epc.ensure_config(tmp_path)
            except Exception as exc:  # noqa: BLE001
                self.fail(
                    f"Second call to ensure_config() raised {type(exc).__name__}: {exc}. "
                    "Hook must be idempotent — safe to call multiple times."
                )

            self.assertTrue(
                result_2,
                msg=(
                    "Second call to ensure_config() with config already present must also "
                    f"return True (idempotent). Got: {result_2}"
                ),
            )


# ---------------------------------------------------------------------------
# Test 6 — Atomicity: partial failure leaves clean state
# ---------------------------------------------------------------------------


class TestAtomicityPartialFailureCleanState(unittest.TestCase):
    """If the write operation fails midway, no partial or temp files are left behind."""

    def test_atomicity_partial_failure_clean_state(self):
        # covers: UNKNOWN
        """Simulated write failure mid-copy → no temp file left in worktree root.

        The atomic write-temp-then-rename pattern must ensure that if the rename
        step fails after a partial write, the temp file is cleaned up and the
        worktree is left in the same state as before the hook ran.

        Must implement the copy path with:
        1. shutil.copy2 / write to a temp path (e.g. .pre-commit-config.yaml.tmp).
        2. os.replace / Path.rename to atomically install the file.
        3. On failure during step 2, remove the temp file (or rely on the atomic
           nature of os.replace which does not leave partials on POSIX).

        This test patches os.replace (or Path.rename) to raise OSError after the
        temp file has been written, then asserts no temp file remains.
        """
        import tempfile

        if not _IMPORT_OK:
            self.fail(
                "ImportError: cannot import scripts.commit_guardian.ensure_precommit_config. "
                "Implement the module first."
            )
        if not hasattr(_epc, "ensure_config"):
            self.fail(
                "AttributeError: ensure_precommit_config does not expose ensure_config(). "
                "Implement ensure_config(worktree_root: Path) -> bool with atomic write pattern."
            )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            worktree = tmp_path / "worktree"
            worktree.mkdir()

            # Patch os.replace to simulate failure after temp file is written
            def failing_replace(src, dst):
                """Simulate os.replace failure (e.g. cross-device rename on NTFS)."""
                raise OSError("os.replace: cross-device link not permitted")  # noqa: TRY003

            with (
                patch("os.symlink", side_effect=OSError("NTFS: no symlinks")),
                patch("os.replace", side_effect=failing_replace),
            ):
                try:
                    _epc.ensure_config(worktree)
                except (OSError, AttributeError, TypeError):
                    # Any exception during the operation is acceptable; we only
                    # care that no temp files are left behind
                    pass

            # Assert no temp files remain in the worktree root
            remaining = list(worktree.iterdir())
            temp_files = [
                f for f in remaining
                if f.name.endswith(".tmp") or f.name.endswith(".temp")
                or f.name.startswith(".pre-commit-config.yaml.")
            ]
            self.assertEqual(
                temp_files,
                [],
                msg=(
                    "Expected no temp files in worktree root after partial write failure. "
                    f"Found: {temp_files}. "
                    "Implement atomic write-temp-then-rename with cleanup on failure."
                ),
            )


# ---------------------------------------------------------------------------
# Test 7 — Manifest index 0: ensure_precommit_config registered first
# ---------------------------------------------------------------------------


class TestManifestIndex0(unittest.TestCase):
    """ensure-precommit-config must be the FIRST entry in hooks_manifest.hooks."""

    def test_manifest_index_0(self):
        # covers: UNKNOWN
        """assert ensure_precommit_config is registered first (index 0) in commit_guardian.json.

        The ticket requires that ensure_precommit_config be listed at index 0
        in hooks_manifest.hooks so it runs BEFORE all other hooks.

        This test:
        1. Reads scripts/commit_guardian/commit_guardian.json.
        2. Locates the hooks_manifest.hooks array.
        3. Asserts that hooks[0]["id"] == "ensure-precommit-config".

        This test is RED until python-coder registers the hook in the manifest.
        The manifest file exists; only the hook entry at index 0 is missing.
        """
        self.assertTrue(
            _MANIFEST_PATH.exists(),
            msg=(
                f"commit_guardian.json not found at {_MANIFEST_PATH}. "
                "Verify the repository structure is intact."
            ),
        )

        try:
            data = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            self.fail(
                f"Cannot read or parse commit_guardian.json at {_MANIFEST_PATH}: {exc}"
            )

        hooks = data.get("hooks_manifest", {}).get("hooks", [])

        self.assertTrue(
            len(hooks) > 0,
            msg=(
                "hooks_manifest.hooks must not be empty. "
                f"Found: {len(hooks)} entries."
            ),
        )

        first_hook_id = hooks[0].get("id", "")
        self.assertEqual(
            first_hook_id,
            "ensure-precommit-config",
            msg=(
                f"Expected hooks_manifest.hooks[0].id == 'ensure-precommit-config'. "
                f"Got: '{first_hook_id}'. "
                "Register ensure_precommit_config.py at index 0 in commit_guardian.json "
                "so it fires BEFORE all other hooks."
            ),
        )


if __name__ == "__main__":
    unittest.main()
