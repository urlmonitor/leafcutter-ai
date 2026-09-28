"""
MODULE: test_ge_120e_1_ii
AC: GE-120e-1-ii — "A path is only an addition when the change actually
    introduced it, so editing an existing root file is not read as adding
    one"

GOAL: TDD red-baseline tests for the bug in
    templates/scripts/commit_guardian/check_root_files.py's
    get_staged_new_files() (line 51): it matches git name-status codes A, M
    AND R, under the inline comment "Only check formally added (A), or
    modified (M) files just in case". Matching M means an ordinary edit to a
    file already tracked at the root — e.g. adding a line to
    requirements-dev.txt, which is absent from root_files.allowed_files in
    commit_guardian.json — is treated as though it introduced a new root
    file, and the commit is wrongly refused.

BUSINESS CONTEXT: requirements-dev.txt is this project's actual dependency
    file (the repo does not use poetry) and is not in the allowlist, so
    under the current code it is currently un-editable by anyone — any
    pre-existing, non-allowlisted root file can never be modified again.

COVERAGE NOTE (per the AC): cover this by running the check as a real
    process against a real repository standing in the relevant staged
    state, and assert on exit status + reader-facing output — never by
    grepping the source for a status-letter substring (CLAUDE.md, "Gate /
    Workflow ACs — Verify Behaviorally, Not by Grep"). The second test below
    is the load-bearing control: without it, deleting the gate or widening
    the allowlist would also turn the first test green.

ARCHITECTURE / DEPENDENCIES: each test builds its own standalone temporary
    git repository (NOT a worktree of this project — check_root_files.py
    needs only a git repo plus the config it loads from its own directory
    via config.py's `Path(__file__).resolve().parent`, never this project's
    docs/ or CLAUDE.md), stages the scenario, and runs
    templates/scripts/commit_guardian/check_root_files.py as a real
    subprocess with cwd set to that repo (find_project_root() resolves via
    `git rev-parse --show-toplevel` against cwd, so this correctly reports
    the fixture repo as the project root without needing a deploy step).

OUT OF SCOPE (per the AC's own it_requirements — not bundled here): adding
    requirements-dev.txt to root_files.allowed_files in commit_guardian.json
    is a separate change made unnecessary by the A-only fix, since the
    reproduced change is an M; record it as a follow-up rather than shipping
    it in this ticket.

====================================================================
DECISION HISTORY
====================================================================
- 2026-09-22 [GE-120e-1-ii]: Initial TDD red-baseline. Confirmed RED by
  running this file directly against the unmodified
  check_root_files.py: the modification-only test fails (check exits 1 and
  names requirements-dev.txt as a forbidden root file); the negative-control
  test (a genuinely new root file) already passes today, since it is not
  the defect being fixed — it exists to prevent a fix that disables the
  gate entirely from appearing to satisfy the first test.
====================================================================
"""
# @ac-tag: GE-120e-1-ii

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent.parent  # unit_tests/commit_guardian -> worktree root
_CHECK_ROOT_FILES = (
    _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_root_files.py"
)

# KI-TQ-012 style hygiene: supply git identity via the environment rather
# than `git config`, which would write into a shared config file and could
# outlive the fixture. These are standalone temp repos (not worktrees of
# this project), so there is no shared-config leakage risk either way, but
# the environment form keeps identity scoped to the subprocess regardless.
_GIT_ENV_OVERRIDES = {
    "PRE_COMMIT_ALLOW_NO_CONFIG": "1",
    "GIT_AUTHOR_NAME": "GE-120e-1-ii fixture",
    "GIT_AUTHOR_EMAIL": "ge120e1ii-fixture@example.com",
    "GIT_COMMITTER_NAME": "GE-120e-1-ii fixture",
    "GIT_COMMITTER_EMAIL": "ge120e1ii-fixture@example.com",
}


def _env_base() -> dict:
    return dict(os.environ)


def _run(cmd: list[str], cwd: Path, timeout: int = 15) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env={**_env_base(), **_GIT_ENV_OVERRIDES},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("Command %s failed to run in %s: %s", cmd, cwd, exc)
        raise


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    result = _run(["git", *args], cwd=cwd)
    if result.returncode != 0:
        logger.warning(
            "git %s failed (rc=%s) in %s: %s", args, result.returncode, cwd,
            result.stderr,
        )
    return result


def _make_repo() -> Path:
    """Create a standalone temp git repo seeded with a pre-existing,
    non-allowlisted root file (requirements-dev.txt — the bug's exact
    reproduction subject) already committed and tracked."""
    suffix = uuid.uuid4().hex[:10]
    root = Path(tempfile.gettempdir()) / f"ge120e1ii-fixture-{suffix}"
    root.mkdir(parents=True, exist_ok=False)
    _run_git(["init", "-q"], cwd=root)
    (root / "requirements-dev.txt").write_text("pytest>=7.0\n", encoding="utf-8")
    _run_git(["add", "requirements-dev.txt"], cwd=root)
    commit = _run_git(
        ["commit", "-q", "-m", "base: seed tracked root file"], cwd=root,
    )
    if commit.returncode != 0:
        raise RuntimeError(
            f"Fixture setup failed: base commit did not succeed in {root}: "
            f"{commit.stderr!r}"
        )
    return root


def _teardown_repo(root: Path) -> None:
    try:
        shutil.rmtree(root, ignore_errors=True)
    except OSError as exc:
        logger.warning("Failed to remove fixture repo %s: %s", root, exc)


class TestEditingExistingNonAllowlistedRootFileIsNotBlocked(unittest.TestCase):
    """AC-GE-120e-1-ii (primary): a staged MODIFICATION to an
    already-tracked, non-allowlisted root file must not be treated as an
    addition."""

    def setUp(self) -> None:
        self.repo = _make_repo()

    def tearDown(self) -> None:
        _teardown_repo(self.repo)

    def test_ge120e1ii_editing_an_existing_non_allowlisted_root_file_is_not_blocked(
        self,
    ) -> None:
        # covers: GE-120e-1-ii
        # angle: failure
        """Symptom reproduction: append a line to requirements-dev.txt (the
        real one-line `pytest-xdist>=3.5` addition described in the bug
        report) and stage it. The file is already tracked at the root and is
        NOT in commit_guardian.json's root_files.allowed_files, so git
        reports this staged change as status 'M'.

        RED today: get_staged_new_files() (line 51) admits status M
        alongside A and R
        (`status.startswith("A") or status.startswith("M") or
        status.startswith("R")`), so this pure edit to an already-tracked
        file is wrongly reported as a forbidden new root file and the check
        exits 1.
        """
        req_file = self.repo / "requirements-dev.txt"
        req_file.write_text(
            req_file.read_text(encoding="utf-8") + "pytest-xdist>=3.5\n",
            encoding="utf-8",
        )
        _run_git(["add", "requirements-dev.txt"], cwd=self.repo)

        status = _run_git(
            ["diff", "--cached", "--name-status"], cwd=self.repo,
        ).stdout
        self.assertTrue(
            status.strip().startswith("M"),
            "Fixture setup failed: expected a staged modification (M) of "
            f"requirements-dev.txt, got: {status!r}",
        )

        result = _run(["python3", str(_CHECK_ROOT_FILES)], cwd=self.repo)
        combined = result.stdout + result.stderr
        self.assertEqual(
            0,
            result.returncode,
            "check_root_files.py must exit 0 when the only staged change is "
            "a MODIFICATION to an already-tracked, non-allowlisted root "
            "file — a modification cannot introduce a new root path. "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        self.assertNotIn(
            "requirements-dev.txt",
            combined,
            "check_root_files.py must not name requirements-dev.txt as a "
            f"forbidden root file when it was only modified. Output: {combined!r}",
        )


class TestAddingNewNonAllowlistedRootFileIsStillBlocked(unittest.TestCase):
    """AC-GE-120e-1-ii (control): a genuinely NEW, non-allowlisted root file
    must still be refused. Without this test, a fix that disables the gate
    entirely (or widens the allowlist) would also make the first test pass —
    this is the load-bearing negative control the AC's notes require."""

    def setUp(self) -> None:
        self.repo = _make_repo()

    def tearDown(self) -> None:
        _teardown_repo(self.repo)

    def test_ge120e1ii_adding_a_new_non_allowlisted_root_file_is_still_blocked(
        self,
    ) -> None:
        # covers: GE-120e-1-ii
        # angle: boundary
        """A brand-new, non-allowlisted root file staged as an addition
        (git status 'A') must still be objected to: the fix must narrow the
        matched status letters to A (and a root-destined R), not simply stop
        checking status letters altogether.
        """
        new_file = self.repo / "malicious_config.cfg"
        new_file.write_text("secret=1\n", encoding="utf-8")
        _run_git(["add", "malicious_config.cfg"], cwd=self.repo)

        status = _run_git(
            ["diff", "--cached", "--name-status"], cwd=self.repo,
        ).stdout
        self.assertTrue(
            status.strip().startswith("A"),
            "Fixture setup failed: expected a staged addition (A) of "
            f"malicious_config.cfg, got: {status!r}",
        )

        result = _run(["python3", str(_CHECK_ROOT_FILES)], cwd=self.repo)
        combined = result.stdout + result.stderr
        self.assertNotEqual(
            0,
            result.returncode,
            "check_root_files.py must still refuse a genuinely NEW, "
            "non-allowlisted root file — this control guards against a fix "
            "that satisfies the first test by disabling the gate entirely. "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        self.assertIn(
            "malicious_config.cfg",
            combined,
            "check_root_files.py must name the newly added forbidden root "
            f"file. Output: {combined!r}",
        )


if __name__ == "__main__":
    unittest.main()
