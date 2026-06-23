"""
MODULE: test_check_components_integrity
GOAL: Unit tests for check_components_integrity.py pre-commit hook.
BUSINESS CONTEXT: Verifies the components.json integrity guard correctly blocks
    non-merge commits that add new components without a detail_ref, and correctly
    skips the new-component existence check when a git merge is in progress
    (MERGE_HEAD present). The merge-skip behaviour is AC ACS-300g-5.
ARCHITECTURE: Tests use a real temporary git repository (subprocess, cwd=temp)
    because the hook shells out to git commands that operate on CWD. Each test
    sets up an isolated git repo, stages a modified docs/components.json that
    adds a new component with NO detail_ref (the invalid case), then runs the
    hook as a subprocess and asserts on the returncode only.

    Two scenarios:
      1. MERGE_HEAD present → hook must exit 0 (merge-skip).  RED against
         current code (no merge-awareness implemented yet).
      2. No MERGE_HEAD → hook must exit 1 (full check runs).  GREEN regression
         guard; must stay green after the fix is applied.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path to the hook under test
# ---------------------------------------------------------------------------

HOOK_SCRIPT = (
    Path(__file__).parent.parent.parent
    / "templates"
    / "scripts"
    / "commit_guardian"
    / "check_components_integrity.py"
)

# ---------------------------------------------------------------------------
# JSON payloads used across tests
# ---------------------------------------------------------------------------

# Initial committed state — one valid existing component (no detail_ref required
# for existing components; the hook only checks newly-added keys).
_INITIAL_COMPONENTS_JSON = json.dumps(
    {
        "components": {
            "existing-component": {
                "name": "Existing Component",
                "description": "A component that was already in HEAD.",
            }
        }
    },
    indent=2,
)

# Staged state — adds "new-invalid-component" which has NO detail_ref.
# validate_new_component() returns an error immediately on missing detail_ref
# (before any disk-path resolution), so the test does not depend on
# REPO_ROOT pointing anywhere real.  This is intentional per AC ACS-300g-5.
_STAGED_COMPONENTS_JSON = json.dumps(
    {
        "components": {
            "existing-component": {
                "name": "Existing Component",
                "description": "A component that was already in HEAD.",
            },
            "new-invalid-component": {
                "name": "New Invalid Component",
                "description": "This component is missing the required detail_ref.",
                # Intentionally no 'detail_ref' key — triggers validate_new_component error.
            },
        }
    },
    indent=2,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run a git command in *cwd* and return the completed process.

    Args:
        args: List of git sub-command arguments (excluding the leading 'git').
        cwd: Working directory for the git invocation.

    Returns:
        CompletedProcess with stdout and stderr captured.
    """
    try:
        return subprocess.run(
            ["git"] + args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        raise RuntimeError(f"git {args!r} failed in {cwd}: {exc}") from exc


def _setup_temp_repo(tmp_dir: Path) -> Path:
    """Initialise a fresh git repo in *tmp_dir* and return the repo root.

    Creates docs/components.json with a single existing component, makes the
    initial commit (HEAD), then stages a modified docs/components.json that
    adds an invalid new component (no detail_ref). The repo is left with:

      - HEAD: docs/components.json containing only 'existing-component'
      - Staged index: docs/components.json also containing 'new-invalid-component'

    The hook will diff HEAD vs staged and detect the added key.

    Args:
        tmp_dir: Temporary directory to initialise as a git repo.

    Returns:
        Path to the repo root (same as tmp_dir).
    """
    repo = tmp_dir

    # Initialise repo.
    _git(["init", "-b", "main"], cwd=repo)
    _git(["config", "user.email", "test@example.com"], cwd=repo)
    _git(["config", "user.name", "Test User"], cwd=repo)

    # Create docs/ and write initial components.json.
    docs_dir = repo / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    components_path = docs_dir / "components.json"
    components_path.write_text(_INITIAL_COMPONENTS_JSON, encoding="utf-8")

    # Stage and commit as HEAD.
    _git(["add", "docs/components.json"], cwd=repo)
    _git(["commit", "-m", "chore: initial components.json"], cwd=repo)

    # Now write the modified staged version (adds invalid new component).
    components_path.write_text(_STAGED_COMPONENTS_JSON, encoding="utf-8")
    _git(["add", "docs/components.json"], cwd=repo)

    # Repo state: HEAD has only 'existing-component'; staged index has both.
    return repo


def _get_head_sha(repo: Path) -> str:
    """Return the current HEAD commit SHA in *repo*.

    Args:
        repo: Path to the git repository.

    Returns:
        The full 40-character HEAD commit SHA.
    """
    result = _git(["rev-parse", "HEAD"], cwd=repo)
    return result.stdout.strip()


def _run_hook(repo: Path) -> subprocess.CompletedProcess:
    """Run check_components_integrity.py as a subprocess with cwd=*repo*.

    The hook's git calls (git show, git diff --cached, git rev-parse) all
    operate on CWD, so cwd=repo is what scopes them to the temp repository.

    Args:
        repo: Path to the git repository to run the hook in.

    Returns:
        CompletedProcess with returncode, stdout, and stderr captured.
    """
    try:
        return subprocess.run(
            [sys.executable, str(HOOK_SCRIPT)],
            cwd=str(repo),
            capture_output=True,
            text=True,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        raise RuntimeError(f"hook subprocess failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMergeInProgressSkipsNewComponentCheck(unittest.TestCase):
    """AC ACS-300g-5: when MERGE_HEAD is present the hook must exit 0.

    This test is EXPECTED TO FAIL against the current unmodified hook because
    check_components_integrity.py has no merge-awareness today. The fix
    (not implemented here) is to detect MERGE_HEAD and return 0 early in main().
    """

    def test_merge_in_progress_skips_new_component_check(self) -> None:
        # covers: ACS-300g-5
        """Hook exits 0 when MERGE_HEAD is present, even with an invalid new component staged.

        Simulates a merge in progress by writing .git/MERGE_HEAD containing the
        HEAD SHA so that `git rev-parse -q --verify MERGE_HEAD` succeeds.
        With the invalid new component staged AND MERGE_HEAD present, the hook
        must skip the new-component existence check and exit 0.

        This test FAILS against the current code (exits 1) because the hook has
        no merge-awareness. It becomes green once main() detects MERGE_HEAD and
        returns 0 early.
        """
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _setup_temp_repo(repo)

            # Simulate a merge in progress by creating .git/MERGE_HEAD.
            # `git rev-parse -q --verify MERGE_HEAD` succeeds when this file exists
            # and contains a valid commit SHA.
            head_sha = _get_head_sha(repo)
            merge_head_path = repo / ".git" / "MERGE_HEAD"
            merge_head_path.write_text(head_sha + "\n", encoding="utf-8")

            result = _run_hook(repo)

        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "AC ACS-300g-5: hook must exit 0 (skip new-component check) when "
                "MERGE_HEAD is present. Current code exits 1 because it has no "
                f"merge-awareness. Stderr: {result.stderr}"
            ),
        )


class TestNormalCommitStillBlocksInvalidNewComponent(unittest.TestCase):
    """Regression guard: without MERGE_HEAD the hook must still exit 1.

    This test documents the existing behaviour that must be preserved after the
    merge-skip fix is applied. A non-merge commit that adds a new component
    without a detail_ref must continue to be blocked (exit 1).
    """

    def test_normal_commit_still_blocks_invalid_new_component(self) -> None:
        # covers: ACS-300g-5
        """Hook exits 1 on a normal (non-merge) commit when a new component lacks detail_ref.

        No .git/MERGE_HEAD file is present. The staged docs/components.json adds
        'new-invalid-component' which has no detail_ref. The hook must run the
        full new-component existence check and exit 1.

        This test MUST stay green after the merge-skip fix is applied — the fix
        must be scoped to merge commits only and must not weaken the guard for
        normal commits.
        """
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _setup_temp_repo(repo)

            # Confirm no MERGE_HEAD exists (belt-and-suspenders).
            merge_head_path = repo / ".git" / "MERGE_HEAD"
            self.assertFalse(
                merge_head_path.exists(),
                msg=".git/MERGE_HEAD must not exist for the normal-commit scenario.",
            )

            result = _run_hook(repo)

        self.assertEqual(
            result.returncode,
            1,
            msg=(
                "AC ACS-300g-5 regression guard: hook must exit 1 on a normal "
                "non-merge commit when a new component has no detail_ref. "
                f"Stderr: {result.stderr}"
            ),
        )


class TestRepoRootResolvesToGitToplevelForExistingDetailRef(unittest.TestCase):
    """AC ACS-300g-6: REPO_ROOT must be resolved via git rev-parse --show-toplevel,
    not via Path(__file__).parents[2].

    When the hook is invoked through the .leafcutter symlink install path,
    Path(__file__).resolve().parents[2] resolves to the real leafcutter-ai repo
    (or the .leafcutter install root), NOT to the committing repo's top-level.
    A new component whose detail_ref exists under the COMMITTING repo's docs/
    is then wrongly reported as "detail_ref file does not exist" because the
    existence check resolves against the wrong root.

    This test FAILS against the current code (REPO_ROOT = Path(__file__).parents[2])
    because docs/architecture/components/widget.md exists only in the temp repo,
    not in the leafcutter-ai repo that hosts the hook file.  Once the fix is applied
    (REPO_ROOT resolved via `git rev-parse --show-toplevel` in CWD), the hook finds
    the file in the temp repo and exits 0.
    """

    def test_repo_root_resolves_to_git_toplevel_for_existing_detail_ref(self) -> None:
        # covers: ACS-300g-6
        """Hook exits 0 when a new component's detail_ref exists under the committing repo.

        Sets up a temp git repo that contains:
          - docs/architecture/components/widget.md  (has flight_level frontmatter)
          - HEAD: docs/components.json with no 'widget' key
          - Staged index: docs/components.json that ADDS 'widget' with a valid detail_ref

        No MERGE_HEAD is present, so the new-component check runs.  The detail_ref
        file exists in the TEMP REPO.  With the current buggy REPO_ROOT derivation
        (Path(__file__).parents[2] → leafcutter-ai), the hook resolves the path
        against the wrong root and reports "detail_ref file does not exist" → exit 1.
        This test asserts returncode == 0 (the correct post-fix behaviour), so it
        FAILS (is RED) against the current unmodified hook.
        """
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            # --- Initialise the git repo ---
            _git(["init", "-b", "main"], cwd=repo)
            _git(["config", "user.email", "test@example.com"], cwd=repo)
            _git(["config", "user.name", "Test User"], cwd=repo)

            # --- Create the detail_ref doc in the temp repo ---
            doc_dir = repo / "docs" / "architecture" / "components"
            doc_dir.mkdir(parents=True, exist_ok=True)
            widget_doc = doc_dir / "widget.md"
            widget_doc.write_text(
                "---\nflight_level: \"L2-Container\"\n---\n# Widget\n\n"
                "Widget component architecture doc.\n",
                encoding="utf-8",
            )

            # --- Write initial components.json (no 'widget' key) and commit as HEAD ---
            docs_dir = repo / "docs"
            components_path = docs_dir / "components.json"
            initial_json = json.dumps(
                {
                    "components": {
                        "existing-component": {
                            "name": "Existing Component",
                            "description": "Already in HEAD.",
                        }
                    }
                },
                indent=2,
            )
            components_path.write_text(initial_json, encoding="utf-8")
            _git(["add", "docs/components.json"], cwd=repo)
            _git(["commit", "-m", "chore: initial components.json"], cwd=repo)

            # Also commit the widget doc so the working tree is clean for the diff
            _git(["add", "docs/architecture/components/widget.md"], cwd=repo)
            _git(["commit", "-m", "docs: add widget architecture doc"], cwd=repo)

            # --- Stage the updated components.json that ADDS 'widget' with a valid detail_ref ---
            staged_json = json.dumps(
                {
                    "components": {
                        "existing-component": {
                            "name": "Existing Component",
                            "description": "Already in HEAD.",
                        },
                        "widget": {
                            "name": "Widget",
                            "description": "The widget component.",
                            "detail_ref": "docs/architecture/components/widget.md",
                        },
                    }
                },
                indent=2,
            )
            components_path.write_text(staged_json, encoding="utf-8")
            _git(["add", "docs/components.json"], cwd=repo)

            # Confirm no MERGE_HEAD (belt-and-suspenders — ensures the new-component check runs)
            merge_head_path = repo / ".git" / "MERGE_HEAD"
            self.assertFalse(
                merge_head_path.exists(),
                msg=".git/MERGE_HEAD must not exist for the normal-commit scenario.",
            )

            result = _run_hook(repo)

        # Primary assertion: the hook should exit 0 because the detail_ref exists
        # under the COMMITTING repo's docs/.  This FAILS against the current code
        # because REPO_ROOT = Path(__file__).parents[2] points at the leafcutter-ai
        # repo (not the temp repo), so the file is not found → exit 1.
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "AC ACS-300g-6: hook must exit 0 when the new component's detail_ref "
                "exists under the committing repo's docs/.  Current buggy code resolves "
                "REPO_ROOT from Path(__file__).parents[2] (the leafcutter-ai repo root) "
                "instead of via git rev-parse --show-toplevel (the temp repo root), so "
                "the detail_ref path is not found and the hook exits 1. "
                f"Stderr: {result.stderr}"
            ),
        )

        # Soft secondary check: the failure mode is specifically the path-resolution one.
        # If (unexpectedly) the hook exits 1, verify the error is the detail_ref not-found
        # message, not something unrelated.
        if result.returncode != 0:
            self.assertIn(
                "detail_ref file does not exist",
                result.stderr,
                msg=(
                    "AC ACS-300g-6 diagnostic: expected exit-1 to be caused specifically "
                    "by the path-resolution bug (detail_ref file does not exist), not by "
                    f"an unrelated error.  Full stderr: {result.stderr}"
                ),
            )


if __name__ == "__main__":
    unittest.main()
