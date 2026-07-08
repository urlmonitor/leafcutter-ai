"""
MODULE: test_check_doc_frontmatter_worktree_pathbase
GOAL: Regression test for GE-115 — check_doc_frontmatter must resolve staged
      file paths against the git worktree top-level (from cwd) rather than the
      .leafcutter-symlink-derived find_project_root() when running inside a
      linked git worktree.
BUSINESS CONTEXT: When the hook runs in a git worktree whose root differs from
      the main working tree, staged file paths (relative to the worktree root)
      are joined against find_project_root(). But find_project_root() follows
      __file__ upward to the leafcutter-ai source root — not the worktree root
      — so read_text() receives a path that does not exist and the hook reports
      a false "Could not read file" frontmatter violation (exit 1). Real-world
      workaround today is SKIP=check-doc-frontmatter.
ARCHITECTURE: Uses a real on-disk git worktree (no mocks) per AC GE-115
      criterion 4. The hook is invoked as a subprocess with cwd=worktree root,
      simulating an actual pre-commit run. A companion positive-control test
      runs the hook from the primary checkout (cwd == project_root) to
      demonstrate that primary-checkout behaviour is unchanged by any fix.

====================================================================
DECISION HISTORY
====================================================================
- 2026-07-08 [test-writer/GE-115]: Initial TDD red-baseline for AC GE-115.
  The worktree test is RED against unmodified code (exit 1 / "Could not read
  file"). The positive-control test is GREEN on both pre- and post-fix code
  because it runs from the actual source root.
====================================================================
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

# Three levels up from this file:
#   unit_tests/commit_guardian/test_*.py
#       -> unit_tests/commit_guardian/
#           -> unit_tests/
#               -> repo root (leafcutter-ai/)
_REPO_ROOT = Path(__file__).resolve().parents[2]

_HOOK_SCRIPT = (
    _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_doc_frontmatter.py"
)

# Minimal schema-valid frontmatter for a docs/*.md file.
#   Required fields (DOC_FM_REQUIRED_FIELDS defaults):
#     title, type, status, created, last_updated, components
#   - type "how-to" is in DOC_FM_ALLOWED_TYPES
#   - status "active" is in DOC_FM_ALLOWED_STATUSES
#   - component "commit_guardian" exists in the real leafcutter-ai docs/components.json
#     AND in the temp-repo docs/components.json written below.
#     Using the same ID in both means validate_components passes regardless of
#     whether the fix uses the worktree root or the source root for registry lookup.
_VALID_DOC_FRONTMATTER = """\
---
title: "GE-115 worktree path-base regression test"
type: how-to
status: active
created: "2026-07-08"
last_updated: "2026-07-08"
components:
  - commit_guardian
---

Regression-test document for GE-115.
This file is staged inside a real git worktree to exercise the path-resolution bug.
"""

# Minimal components.json for the temp repos.
# Registers 'commit_guardian' so validate_components passes after the fix,
# regardless of whether the fix resolves the registry path to the worktree
# root or to the leafcutter-ai source root.
_COMPONENTS_JSON = """\
{
  "components": {
    "commit_guardian": {
      "name": "Commit Guardian",
      "description": "Pre-commit hook suite used by GE-115 regression test."
    }
  }
}
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git_available() -> bool:
    """Return True if git is reachable on PATH.

    Returns:
        bool: True when ``git --version`` exits 0.
    """
    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, OSError):
        return False
    else:
        return result.returncode == 0


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run a git subcommand in *cwd* with captured output.

    Args:
        args: Git sub-command arguments (excluding the leading "git").
        cwd: Working directory for the invocation.

    Returns:
        CompletedProcess with stdout and stderr captured.
    """
    return subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )


def _run_hook(
    cwd: Path,
    filenames: list[str],
    timeout: int = 30,
) -> subprocess.CompletedProcess:
    """Invoke check_doc_frontmatter.py as a subprocess with cwd=*cwd*.

    Passes *filenames* as positional arguments, which triggers the
    ``args.filenames`` branch of get_files_to_check() — the same branch
    activated when pre-commit passes staged file paths to the hook.

    Python automatically adds the script's directory to sys.path[0], so all
    commit_guardian local imports (config, _resolve_root, frontmatter_validators,
    diagram_type_validators, doc_type_validators, etc.) resolve without any
    explicit PYTHONPATH override.

    Args:
        cwd: Working directory for the subprocess.  Must be the git top-level
             to reproduce real pre-commit behaviour.
        filenames: Staged file paths relative to *cwd*.
        timeout: Seconds before the subprocess is killed.

    Returns:
        CompletedProcess with returncode, stdout, stderr captured.
    """
    return subprocess.run(
        [sys.executable, str(_HOOK_SCRIPT)] + filenames,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
    )


def _setup_primary_repo(base: Path) -> Path:
    """Create a fresh primary git repo under base/primary with an initial commit.

    The repo contains:
    - CLAUDE.md (so find_project_root() could discover it if searched from CWD)
    - docs/components.json (so load_components_registry returns a non-empty set)

    Having HEAD present means ``git show HEAD:docs/ge115_regression_test.md``
    returns CalledProcessError (file is new, not in HEAD), causing
    validate_last_updated to return [] with no warnings.

    Args:
        base: Parent directory under which primary/ is created.

    Returns:
        Path to the primary repo root.
    """
    repo = base / "primary"
    repo.mkdir(parents=True, exist_ok=True)

    _git(["init", "-b", "main"], cwd=repo)
    _git(["config", "user.email", "ge115test@example.com"], cwd=repo)
    _git(["config", "user.name", "GE-115 Test"], cwd=repo)

    # CLAUDE.md anchor — mirrors what find_project_root() looks for
    (repo / "CLAUDE.md").write_text("# GE-115 test primary repo\n", encoding="utf-8")

    # docs/components.json — the hook reads this at startup to build valid_components
    docs_dir = repo / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "components.json").write_text(_COMPONENTS_JSON, encoding="utf-8")

    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-m", "chore: ge115 test scaffold"], cwd=repo)

    return repo


# ---------------------------------------------------------------------------
# RED-PHASE TEST: worktree root != source project_root → bug manifests
# ---------------------------------------------------------------------------


class TestWorktreePathbaseResolution(unittest.TestCase):
    """AC GE-115: staged file paths must be resolved against the worktree top-level.

    RED PHASE — this class fails against the unmodified check_doc_frontmatter.py.

    Root cause of the bug
    ----------------------
    At module-level in check_doc_frontmatter.py:

        project_root = find_project_root()

    find_project_root() calls Path(__file__).resolve() and walks upward
    until it finds a .git directory or CLAUDE.md.  __file__ is always the
    hook script inside templates/scripts/commit_guardian/, so the walk
    finds the leafcutter-ai source root — not the worktree root.

    Inside a linked git worktree, the worktree root is a separate directory
    (e.g. /tmp/ge115_wt_xyz/worktree/).  The staged file path is relative to
    THAT root.  When the hook attempts:

        (project_root / "docs/ge115_regression_test.md").read_text()

    it looks inside leafcutter-ai/docs/, where the file does not exist.
    read_text() raises OSError.  validate_doc_file catches it and returns
    ["Could not read file: …"].  The hook prints a FRONTMATTER VIOLATION
    and exits 1 — a false positive.

    Fix required
    -------------
    Derive the base path for opening staged files from
    ``git rev-parse --show-toplevel`` (cwd-relative), which always resolves
    to the worktree root during a pre-commit run.
    """

    _tmpdir: str
    _base: Path
    _primary: Path
    _worktree: Path

    @classmethod
    def setUpClass(cls) -> None:
        """Create a real primary repo and a linked git worktree on disk."""
        if not _git_available():
            raise unittest.SkipTest("git not on PATH — skipping worktree tests")  # noqa: TRY003
        if not _HOOK_SCRIPT.exists():
            raise unittest.SkipTest(f"Hook script not found: {_HOOK_SCRIPT}")  # noqa: TRY003

        cls._tmpdir = tempfile.mkdtemp(prefix="ge115_wt_")
        cls._base = Path(cls._tmpdir)

        # Step 1 — primary git repo with initial HEAD commit
        cls._primary = _setup_primary_repo(cls._base)

        # Step 2 — create a REAL linked worktree via git worktree add
        # This is the crux of GE-115: the worktree top-level differs from the
        # primary repo root, which in turn differs from find_project_root().
        cls._worktree = cls._base / "worktree"
        wt_result = _git(
            ["worktree", "add", str(cls._worktree), "-b", "ge115-test-branch"],
            cwd=cls._primary,
        )
        if wt_result.returncode != 0:
            shutil.rmtree(cls._tmpdir, ignore_errors=True)
            skip_reason = (  # noqa: TRY003
                f"git worktree add failed (rc={wt_result.returncode}): "
                f"{wt_result.stderr.strip()}"
            )
            raise unittest.SkipTest(skip_reason)  # noqa: TRY003

        # Step 3 — create docs/ structure inside the worktree.
        # The worktree inherits the primary repo's committed files, but we write
        # docs/components.json explicitly to ensure it's present even if the
        # fix resolves the registry path to the worktree root.
        wt_docs = cls._worktree / "docs"
        wt_docs.mkdir(exist_ok=True)
        (wt_docs / "components.json").write_text(_COMPONENTS_JSON, encoding="utf-8")

        # Step 4 — create the staged docs/*.md with fully valid frontmatter.
        # This is the file the hook is asked to validate.
        # Its path is relative to the WORKTREE root (not the primary or source root).
        staged_file = wt_docs / "ge115_regression_test.md"
        staged_file.write_text(_VALID_DOC_FRONTMATTER, encoding="utf-8")

        # Step 5 — git add both files (simulate pre-commit staging state)
        _git(
            ["add", "docs/components.json", "docs/ge115_regression_test.md"],
            cwd=cls._worktree,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        """Remove the linked worktree and temp directory."""
        worktree = getattr(cls, "_worktree", None)
        primary = getattr(cls, "_primary", None)
        tmpdir = getattr(cls, "_tmpdir", None)
        if worktree is not None and primary is not None:
            _git(
                ["worktree", "remove", "--force", str(worktree)],
                cwd=primary,
            )
        if tmpdir is not None:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_ac_ge115_worktree_staged_file_exits_zero(self) -> None:
        # covers: GE-115
        """GE-115: hook exits 0 for a valid staged docs/*.md inside a real git worktree.

        FAILS (exits 1 with "Could not read file") against unmodified code because
        find_project_root() returns the leafcutter-ai source root (from __file__),
        not the worktree root.  The hook therefore tries to open:

            <leafcutter_ai_root>/docs/ge115_regression_test.md

        which does not exist → OSError → "Could not read file" → exit 1.

        What must be implemented to make this green:
            Replace the staged-file base path (used in validate_doc_file and
            validate_ticket_file) with a root from `git rev-parse --show-toplevel`
            run in the hook's cwd, rather than from find_project_root().
        """
        staged_relative = "docs/ge115_regression_test.md"
        result = _run_hook(cwd=self._worktree, filenames=[staged_relative])

        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "GE-115 RED: expected hook to exit 0 for a valid staged docs/*.md\n"
                "running inside a real git worktree, but got a non-zero exit code.\n\n"
                f"Exit code   : {result.returncode}\n"
                f"Worktree    : {self._worktree}\n"
                f"Primary repo: {self._primary}\n"
                f"Hook script : {_HOOK_SCRIPT}\n"
                f"Staged file : {staged_relative}\n\n"
                f"stdout:\n{result.stdout}\n\n"
                f"stderr:\n{result.stderr}\n\n"
                "ROOT CAUSE (GE-115):\n"
                "  find_project_root() resolves __file__ to leafcutter-ai source root.\n"
                "  Inside the worktree, the staged file is at:\n"
                f"    {self._worktree / staged_relative}\n"
                "  But the hook looks for:\n"
                "    <leafcutter_ai_source_root>/docs/ge115_regression_test.md\n"
                "  which does not exist -> read_text() raises -> false violation.\n\n"
                "FIX: derive the staged-file base from `git rev-parse --show-toplevel`\n"
                "  (cwd-relative) instead of find_project_root() (__file__-relative)."
            ),
        )

    def test_ac_ge115_no_false_positive_could_not_read_file_in_worktree(self) -> None:
        # covers: GE-115
        """GE-115: the hook must not emit 'Could not read file' for a valid staged
        docs/*.md when running inside a real git worktree.

        This test targets the exact symptom described in the AC: the false-positive
        violation message always contains 'Could not read file'.  After the fix,
        this string must be absent from both stdout and stderr.
        """
        staged_relative = "docs/ge115_regression_test.md"
        result = _run_hook(cwd=self._worktree, filenames=[staged_relative])

        combined = result.stdout + result.stderr
        self.assertNotIn(
            "Could not read file",
            combined,
            msg=(
                "GE-115 RED: hook output contains 'Could not read file' for a valid\n"
                "staged docs/*.md inside a git worktree. This is the exact false-positive\n"
                "symptom described in AC GE-115.\n\n"
                f"stdout:\n{result.stdout}\n\n"
                f"stderr:\n{result.stderr}\n\n"
                "Root cause: staged file path is joined against find_project_root()\n"
                "(leafcutter-ai source root, based on __file__) rather than the worktree\n"
                "top-level. read_text() raises OSError -> 'Could not read file'."
            ),
        )


# ---------------------------------------------------------------------------
# POSITIVE-CONTROL TEST: primary checkout (cwd == source root) must still pass
# ---------------------------------------------------------------------------


class TestPrimaryCheckoutPathbaseUnchanged(unittest.TestCase):
    """AC GE-115 criterion 4: primary checkout behaviour must be unchanged.

    Companion positive-control test. Creates a temporary docs/*.md file directly
    in the actual leafcutter-ai docs/ directory (the path returned by
    find_project_root()) so that `project_root / filepath` resolves to a real,
    readable file — the NON-worktree case where the bug does not manifest.

    This test PASSES both before and after the fix.  Its purpose is a regression
    guard: once the fix is applied, the primary-checkout code path must continue
    to exit 0 for a valid staged doc.

    The test is skipped when leafcutter-ai/docs/ is absent (e.g. isolated CI).
    """

    _temp_doc: Path | None = None

    @classmethod
    def setUpClass(cls) -> None:
        """Write a temporary valid docs file into the actual source repo docs/."""
        if not _git_available():
            raise unittest.SkipTest("git not on PATH — skipping positive-control test")  # noqa: TRY003
        if not _HOOK_SCRIPT.exists():
            raise unittest.SkipTest(f"Hook script not found: {_HOOK_SCRIPT}")  # noqa: TRY003

        docs_dir = _REPO_ROOT / "docs"
        if not docs_dir.exists():
            skip_reason = (  # noqa: TRY003
                "leafcutter-ai/docs/ directory not found — "
                "skipping primary-checkout positive-control test"
            )
            raise unittest.SkipTest(skip_reason)  # noqa: TRY003

        cls._temp_doc = docs_dir / "ge115_TEMP_positive_control.md"
        cls._temp_doc.write_text(_VALID_DOC_FRONTMATTER, encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        """Remove the temporary doc created during setup."""
        temp_doc = getattr(cls, "_temp_doc", None)
        if temp_doc is not None and temp_doc.exists():
            temp_doc.unlink()

    def test_ac_ge115_primary_checkout_validates_correctly(self) -> None:
        # covers: GE-115
        """GE-115 criterion 4: primary (non-worktree) checkout exits 0 for a valid
        staged docs/*.md file, both before and after the fix.

        When cwd == _REPO_ROOT == find_project_root(), the path:

            project_root / "docs/ge115_TEMP_positive_control.md"

        resolves to the file written by setUpClass. read_text() succeeds, the
        frontmatter is valid (title, type, status, created, last_updated, components
        all present and correct), and the hook exits 0.

        Passes BEFORE the fix (the bug is worktree-specific) and must stay green
        AFTER the fix to confirm no regression in the primary-checkout code path.
        """
        staged_relative = "docs/ge115_TEMP_positive_control.md"
        result = _run_hook(cwd=_REPO_ROOT, filenames=[staged_relative])

        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "GE-115 positive-control: expected hook to exit 0 for a valid staged\n"
                "docs/*.md when running from the primary (non-worktree) checkout.\n\n"
                f"Exit code   : {result.returncode}\n"
                f"Primary root: {_REPO_ROOT}\n"
                f"Hook script : {_HOOK_SCRIPT}\n"
                f"Staged file : {staged_relative}\n\n"
                f"stdout:\n{result.stdout}\n\n"
                f"stderr:\n{result.stderr}"
            ),
        )

        self.assertNotIn(
            "Could not read file",
            result.stdout + result.stderr,
            msg=(
                "GE-115 positive-control: primary-checkout validation must not produce\n"
                "a 'Could not read file' false-positive for a valid staged doc."
            ),
        )


if __name__ == "__main__":
    unittest.main()
