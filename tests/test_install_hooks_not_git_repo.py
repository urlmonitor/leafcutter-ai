"""
MODULE: test_install_hooks_not_git_repo
GOAL: Regression test for BP-007 — install_hooks() must return a graceful
      "skipped (not a git repo)" status when target_root is not a git
      repository.

Bug symptom (pre-fix): calling install_hooks(target_root) where target_root
is NOT a git repository prints "[ERROR] pre-commit install failed:" with
empty/opaque stderr and returns "failed", because the function runs
'pre-commit install' unconditionally — there is no guard that detects the
absent .git directory.

Expected (post-fix): a new guard between step 3 (core.hooksPath check) and
step 4 (pre-commit install) detects that target_root is not a git repo and
returns "skipped (not a git repo)" instead of reaching 'pre-commit install'.

AC coverage:
  BP-007  — install_hooks skips gracefully when target_root is not a git repo
"""
# @ac-tag: BP-007

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MODULE_PATH = _REPO_ROOT / "scripts" / "build_helpers.py"


def _get_install_hooks():
    """Late-load install_hooks so tests fail at test-run time, not collection.

    Returns a (install_hooks callable, module object) tuple.  The module is
    exposed so callers can patch internal symbols such as _resolve_precommit_cmd
    via patch.object(mod, ...).
    """
    _scripts_dir = str(_MODULE_PATH.parent)
    if _scripts_dir not in sys.path:
        sys.path.insert(0, _scripts_dir)
    spec = importlib.util.spec_from_file_location("build_helpers_bp007", _MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, "install_hooks"), mod


class TestInstallHooksNotGitRepo(unittest.TestCase):
    """BP-007: install_hooks() must detect a non-git target_root before
    invoking 'pre-commit install' and return a graceful skip status.

    The test monkeypatches _resolve_precommit_cmd to return a dummy command
    list so that the "pre-commit not found" early-return (step 1) is bypassed
    and execution reaches — or should reach, after the fix — the git-repo
    guard.  An empty tmp directory with no .git subtree simulates the
    non-repo scenario.
    """

    def test_ac_bp007_not_a_git_repo_returns_skipped(self):
        # covers: BP-007
        """BP-007: install_hooks(target_root) where target_root has no .git
        must return a graceful skip status — NOT "failed".

        Pre-fix behaviour: _resolve_precommit_cmd() returns a real binary;
        `git config --get core.hooksPath` exits non-zero (no git repo), so
        the hooksPath guard is skipped; the function calls 'pre-commit install',
        which fails because there is no .git; CalledProcessError is caught, and
        "failed" is returned with an [ERROR] message.

        Post-fix behaviour: a guard before step 4 detects the missing .git and
        returns "skipped (not a git repo)" (or a similar string that starts
        with "skipped" and contains "git") without invoking pre-commit install.
        """
        install_hooks, mod = _get_install_hooks()

        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_path = Path(tmp_str)
            # Confirm there is genuinely no .git — this is the non-repo scenario.
            self.assertFalse(
                (tmp_path / ".git").exists(),
                "Expected tmp_path to have no .git directory; test setup is wrong.",
            )

            # Monkeypatch _resolve_precommit_cmd so the "pre-commit not found"
            # guard (step 1) is bypassed and execution reaches step 3/4 where
            # the git-repo check must (after the fix) fire.
            with patch.object(mod, "_resolve_precommit_cmd", return_value=["pre-commit"]):
                result = install_hooks(tmp_path, dry_run=False)

        # Primary assertion: the bug symptom must not occur.
        self.assertNotEqual(
            result,
            "failed",
            msg=(
                "install_hooks() returned 'failed' for a non-git directory. "
                "This is the BP-007 bug: the function reached 'pre-commit install' "
                "unconditionally and surfaced CalledProcessError as a hard failure. "
                "The fix must add a git-repo guard before step 4 that returns a "
                "graceful skip status instead."
            ),
        )

        # Secondary assertion: the return value must be a recognisable skip status.
        # Accept either the exact canonical value or any string that starts with
        # "skipped" and contains "git" (e.g. "skipped (not a git repo)").
        is_graceful_skip = result == "skipped (not a git repo)" or (
            result.startswith("skipped") and "git" in result.lower()
        )
        self.assertTrue(
            is_graceful_skip,
            msg=(
                f"install_hooks() returned {result!r} for a non-git directory. "
                "Expected 'skipped (not a git repo)' or a string that starts "
                "with 'skipped' and contains 'git' (BP-007)."
            ),
        )

    def test_ac_bp007_real_git_repo_guard_does_not_over_fire(self):
        # covers: BP-007
        """Regression guard: when target_root IS a real git repo, install_hooks()
        must NOT return "skipped (not a git repo)".

        This guards against the new git-repo check misfiring on a valid repo.
        subprocess.run is mocked so that the git config step and pre-commit
        install both succeed — the only behaviour we verify is that the new
        skip status is NOT returned for a real repo.
        """
        install_hooks, mod = _get_install_hooks()

        real_git_root = _REPO_ROOT  # leafcutter-ai has a .git at its root
        self.assertTrue(
            (real_git_root / ".git").exists(),
            "Expected leafcutter-ai repo root to have a .git directory.",
        )

        def fake_subprocess_run(cmd, **kwargs):
            """Simulate: core.hooksPath absent (rc=1), pre-commit install succeeds."""
            r = MagicMock()
            if (
                isinstance(cmd, list)
                and "config" in cmd
                and "--get" in cmd
                and "core.hooksPath" in cmd
            ):
                r.returncode = 1  # key not set — normal case
                r.stdout = ""
            else:
                r.returncode = 0
                r.stdout = b""
                r.stderr = b""
            return r

        with patch.object(mod, "_resolve_precommit_cmd", return_value=["pre-commit"]):
            with patch.object(mod, "subprocess") as mock_sub:
                mock_sub.run.side_effect = fake_subprocess_run
                mock_sub.CalledProcessError = subprocess.CalledProcessError
                result = install_hooks(real_git_root, dry_run=False)

        self.assertNotEqual(
            result,
            "skipped (not a git repo)",
            msg=(
                f"install_hooks() incorrectly returned 'skipped (not a git repo)' "
                f"for a real git repository ({real_git_root}). The new guard must "
                "only fire when there is genuinely no .git in target_root (BP-007)."
            ),
        )


if __name__ == "__main__":
    unittest.main()
