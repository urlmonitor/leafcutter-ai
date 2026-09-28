"""
MODULE: test_acs_400e_4_head_lookup_posix_path
GOAL: RED test-first regression test for ACS-400e-4 -- "The governance hook
    compares an existing AC file against its HEAD version on every platform,
    including Windows".
BUG: `_check_file()` in scripts/commit_guardian/check_ac_governance.py builds
    the repo-relative path with `str(Path(file_path).relative_to(project_root))`
    (see the module, near the `elif sim_new_file` branch) and hands that string
    straight to `_load_head_content()`, which runs
    `git show HEAD:{file_path}`. On Windows, `str(Path(...))` yields an
    OS-native backslash path (e.g. `docs\\acceptance-criteria\\sub\\f.yaml`),
    but `git show <rev>:<path>` requires forward slashes. `git show` then
    fails with exit 128 ("exists on disk, but not in 'HEAD'"),
    `_load_head_content` returns None, and the file is misclassified as a
    brand-new file. Downstream, the amended_by audit-trail check
    (ACS-400c-2) is only run `if ... not is_new_file ... `, so it is silently
    skipped for every existing, nested AC file edited on Windows.
FIX: `.as_posix()` must be applied to the repo-relative path before it is
    used to build the `git show HEAD:<path>` revision spec.
ARCHITECTURE: This is a real end-to-end reproduction, not a mock of git or of
    Path: a real git repository is initialized on disk, a real AC YAML file
    is committed to HEAD under a nested directory (so `relative_to()` yields
    multiple path segments), the working-tree copy is then modified, and the
    real hook script is invoked via subprocess exactly as the pre-commit
    hook runner would invoke it. This session runs on a real Windows host
    (win32), so `Path.relative_to(...)` naturally produces the backslash
    string described in the bug -- no simulation of the platform is needed
    or performed.

    A negative control (root-level file, zero path separators) proves the
    assertion is tied to the path-separator defect specifically, not to a
    general git-integration failure: the identical stale-amended_by scenario
    at the repo root is already correctly blocked today, because a
    single-segment relative path has no separator to get wrong.

# covers: ACS-400e-4
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HOOK_SCRIPT = _REPO_ROOT / "scripts" / "commit_guardian" / "check_ac_governance.py"
_SUBPROCESS_TIMEOUT_SECONDS = 30


def _git(args: list, cwd: Path) -> subprocess.CompletedProcess:
    """Run a real `git` subprocess against a fixture repository.

    Args:
        args: Argument list appended after `git` (e.g. ["add", "."]).
        cwd: Working directory to run git in.

    Returns:
        The completed subprocess result. Raises via check=True on failure so
        a broken fixture setup surfaces immediately rather than masquerading
        as a red test result.
    """
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "COMMIT_AGENT_MODE": "1"},
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def _init_git_repo(root: Path) -> None:
    """Initialize a real git repository with a usable local identity.

    Args:
        root: Directory to initialize as a git repository.
    """
    _git(["init", "-q"], root)
    _git(["config", "user.email", "fixture@example.invalid"], root)
    _git(["config", "user.name", "Fixture Author"], root)


def _run_hook(ac_file: Path, root: Path, agent_id: str) -> subprocess.CompletedProcess:
    """Invoke the real hook script exactly as the pre-commit runner would.

    Args:
        ac_file: Absolute path to the AC YAML file to check (HOOK_TEST_FILES).
        root: The fixture git repository root (HOOK_ROOT).
        agent_id: The committing agent identity (HOOK_AGENT_ID).

    Returns:
        The completed subprocess result (stdout/stderr/returncode).
    """
    return subprocess.run(
        [sys.executable, str(_HOOK_SCRIPT)],
        cwd=str(root),
        env={
            **os.environ,
            "HOOK_ROOT": str(root),
            "HOOK_TEST_FILES": str(ac_file),
            "HOOK_AGENT_ID": agent_id,
        },
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def _seed_and_edit_existing_ac(root: Path, ac_file: Path) -> None:
    """Commit an original AC YAML to HEAD, then edit `criteria` in-place.

    `amended_by` is deliberately left unchanged so the edit is a genuine
    ACS-400c-2 violation (criteria changed, audit trail not updated) *when
    the HEAD version is correctly loaded*.

    Args:
        root: The fixture git repository root (already `git init`-ed).
        ac_file: Absolute path of the AC YAML file to seed and then edit.
    """
    original = {
        "id": "ACS-TEST-POSIX-001",
        "title": "Existing AC used to prove the Windows HEAD-lookup bug",
        "criteria": "Given original criteria, When staged, Then this is the baseline.",
        "origin_agent": "business-analyst-v3",
        "amended_by": ["business-analyst-v3"],
    }
    ac_file.parent.mkdir(parents=True, exist_ok=True)
    ac_file.write_text(yaml.safe_dump(original, sort_keys=False), encoding="utf-8")

    _git(["add", "."], root)
    _git(["commit", "-q", "-m", "seed existing AC file"], root)

    modified = dict(original)
    modified["criteria"] = (
        "Given the criteria was modified, When compared to HEAD, "
        "Then amended_by must also be updated but was not."
    )
    ac_file.write_text(yaml.safe_dump(modified, sort_keys=False), encoding="utf-8")


class TestHeadLookupUsesPosixPathOnWindows(unittest.TestCase):
    """ACS-400e-4: HEAD comparison for an existing, nested AC file must work
    on every platform -- the repo-relative path handed to `git show HEAD:` must
    use forward slashes even when `Path.relative_to(...)` stringifies with
    OS-native (backslash, on Windows) separators.
    """

    def test_ac1_nested_existing_file_edit_is_blocked_against_head(self):
        # covers: ACS-400e-4
        # angle: reachability
        """AC-1 (ACS-400e-4): editing an existing, HEAD-committed AC file
        under a nested directory, changing `criteria` without updating
        `amended_by`, must be BLOCKED (exit 1) -- because the HEAD version
        must load successfully and be compared against the staged edit.

        If `git show HEAD:<path>` is given a backslash path on Windows, it
        fails (exit 128, "exists on disk, but not in HEAD"),
        `_load_head_content` returns None, the file is misclassified as
        brand new, and the amended_by audit-trail check (ACS-400c-2) is
        skipped entirely -- so this test observes exit 0 instead of exit 1
        on the unfixed code.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _init_git_repo(root)
            (root / "docs" / "acceptance-criteria").mkdir(parents=True, exist_ok=True)

            # Multiple nested directory segments -- this is what makes
            # str(Path(...).relative_to(...)) contain a separator at all.
            nested_dir = (
                root / "docs" / "acceptance-criteria" / "acs-400-ac-governance"
            )
            ac_file = nested_dir / "ACS-TEST-POSIX-001.yaml"
            _seed_and_edit_existing_ac(root, ac_file)

            result = _run_hook(ac_file, root, agent_id="it-po")
            combined = result.stdout + result.stderr

            # Negative signal: an EXISTING (HEAD-committed) file must never
            # be reported as requiring an origin_agent as though it were new.
            self.assertNotIn(
                "new AC file requires origin_agent",
                combined,
                "An existing, HEAD-committed AC file must never be treated as "
                "brand new. This message means the HEAD lookup silently "
                f"failed. stdout={result.stdout!r} stderr={result.stderr!r}",
            )

            self.assertEqual(
                result.returncode,
                1,
                "Expected exit 1: criteria was changed on an EXISTING "
                "(HEAD-committed) AC file without updating amended_by, which "
                "ACS-400c-2 requires to be blocked. A 0 here means the HEAD "
                "version was never loaded -- almost certainly because "
                "`git show HEAD:<path>` was given a backslash path on "
                "Windows and failed with exit 128, so the file was "
                "misclassified as new and the amended_by audit-trail check "
                f"was skipped entirely. stdout={result.stdout!r} "
                f"stderr={result.stderr!r}",
            )
            self.assertIn(
                "amended_by",
                combined,
                f"Block reason must mention amended_by. stdout={result.stdout!r} "
                f"stderr={result.stderr!r}",
            )

    def test_negative_control_root_level_existing_file_is_already_blocked(self):
        # covers: ACS-400e-4
        # angle: boundary
        """Negative control: the identical existing-file / stale-amended_by
        scenario, but with the AC file directly at the repository root (zero
        path separators in the relative path). `str(Path(...).relative_to(...))`
        has nothing to convert on any platform, so `git show HEAD:<name>`
        already succeeds today, and the file is already correctly blocked.

        This isolates the defect above to path-separator conversion
        specifically -- proving the nested-directory failure is not a
        general git-integration or fixture problem.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _init_git_repo(root)
            (root / "docs" / "acceptance-criteria").mkdir(parents=True, exist_ok=True)

            ac_file = root / "ACS-TEST-POSIX-ROOT.yaml"
            _seed_and_edit_existing_ac(root, ac_file)

            result = _run_hook(ac_file, root, agent_id="it-po")
            combined = result.stdout + result.stderr

            self.assertEqual(
                result.returncode,
                1,
                "Root-level (no nested directory) existing-file edit should "
                "already be correctly blocked today -- if this also fails, "
                f"the fixture setup itself is broken. stdout={result.stdout!r} "
                f"stderr={result.stderr!r}",
            )
            self.assertIn("amended_by", combined)


if __name__ == "__main__":
    unittest.main()
