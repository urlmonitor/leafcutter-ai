"""
MODULE: test_bp016_shim_symlinks_not_tracked
GOAL: Guard against build-output shims (scripts/commit_guardian,
    scripts/doc_compliance, scripts/feedback) being committed to the
    repository as symlinks whose targets are absolute, developer-machine
    paths.
BUSINESS CONTEXT: install_shims() (scripts/build_helpers.py, ADR-016) creates
    these three paths as shims into the consolidated output root exactly like
    .claude/agents, .claude/skills and .gemini — all of which are correctly
    gitignored and untracked. BP-016 documents two independent defects: (1)
    the three paths were nonetheless committed (mode 120000 in the git
    index), so .gitignore — which has no effect on already-tracked files —
    was inert; and (2) two of the three .gitignore entries carry a trailing
    slash (`scripts/commit_guardian/`), which only matches a DIRECTORY, not
    the symlink git actually stores, so even once untracked the pattern
    cannot re-catch them; `scripts/feedback` has no entry at all. The
    dangling absolute-path targets (pointing at a deleted worktree) make
    guardian-dependent gates silently no-op locally, producing false-green
    local runs while CI (which rebuilds the shims via build.py) behaves
    differently.
ARCHITECTURE: Queries the REAL repository git index and working tree via
    `git -C <repo_root>` subprocess calls — never a synthetic temp repo. A
    synthetic fixture would only prove the assertion logic is internally
    consistent; it would reproduce whatever assumption is baked into it and
    could pass while the real repo stays broken (see repo CLAUDE.md,
    "Real-artifact behavioral spot-check before declaring done"). Covers both
    defects: a generic scan of the whole index for any mode-120000 entry
    whose blob content is an absolute path (catches this class of bug anywhere
    in the tree, not just the three known paths), and a specific
    `git check-ignore` check for each of the three named shim paths.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

_KNOWN_SHIM_PATHS = (
    "scripts/commit_guardian",
    "scripts/doc_compliance",
    "scripts/feedback",
)


def _git_available() -> bool:
    """True iff `git` is on PATH and _REPO_ROOT is inside a real git repo."""
    if shutil.which("git") is None:
        return False
    try:
        result = subprocess.run(
            ["git", "-C", str(_REPO_ROOT), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and result.stdout.strip() == "true"


pytestmark = pytest.mark.skipif(
    not _git_available(),
    reason="git is unavailable or unit_tests/build_guards is not inside a git repo",
)


def _ls_files_stage() -> list[str]:
    """Return raw `git ls-files -s` lines for the whole real repo index."""
    result = subprocess.run(
        ["git", "-C", str(_REPO_ROOT), "ls-files", "-s"],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def _cat_file_blob(sha: str) -> str:
    """Return the decoded content of a git blob object (a symlink target)."""
    result = subprocess.run(
        ["git", "-C", str(_REPO_ROOT), "cat-file", "-p", sha],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    return result.stdout


class TestBP016ShimSymlinksNotTracked:
    """Guard: build-output shims must never be tracked as absolute symlinks.

    FAILS today (RED — BP-016 is `work_status: todo`) because
    scripts/commit_guardian, scripts/doc_compliance, and scripts/feedback are
    all currently tracked at git mode 120000 with absolute-path targets, and
    the corresponding .gitignore entries do not match them.
    """

    def test_ac_bp016_no_tracked_symlink_has_absolute_target(self) -> None:
        # covers: BP-016
        """Generic scan: no index entry anywhere is a symlink (mode 120000)
        whose blob content is an absolute filesystem path.

        Written generically over the whole index (not hardcoded to the three
        known offenders) so it also catches the next build-output shim that
        gets accidentally committed. Reports every offending path + target in
        the assertion message.
        """
        offenders: list[str] = []
        for line in _ls_files_stage():
            # Format: "<mode> <sha> <stage>\t<path>"
            meta, _, path = line.partition("\t")
            parts = meta.split()
            if len(parts) < 2:
                continue
            mode, sha = parts[0], parts[1]
            if mode != "120000":
                continue
            target = _cat_file_blob(sha).strip()
            if target.startswith("/"):
                offenders.append(f"{path!r} -> {target!r}")

        assert offenders == [], (
            "BP-016 FAILED: found tracked symlink(s) whose blob content is an "
            "absolute filesystem path — these are build-output shims that must "
            "never be committed (install_shims(), ADR-016); a fresh clone would "
            "receive symlinks pointing at paths that exist only on one "
            "developer's machine. Offenders:\n  " + "\n  ".join(offenders)
        )

    def test_ac_bp016_known_shim_paths_are_check_ignore_matched(self) -> None:
        # covers: BP-016
        """Specific check: each known shim path is reported ignored by
        `git check-ignore`, so install_shims() rebuilding them cannot
        silently re-add them to the index.

        `scripts/commit_guardian/` and `scripts/doc_compliance/` currently
        carry a trailing slash in .gitignore, which matches only a
        DIRECTORY — git stores these paths as symlinks (mode 120000), not
        directories, so the pattern never matches them even once untracked.
        `scripts/feedback` has no .gitignore entry at all. `git check-ignore`
        exits 1 (not ignored) for all three today.
        """
        not_ignored: list[str] = []
        for rel_path in _KNOWN_SHIM_PATHS:
            result = subprocess.run(
                ["git", "-C", str(_REPO_ROOT), "check-ignore", "-v", rel_path],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode != 0:
                not_ignored.append(
                    f"{rel_path!r} (check-ignore exit={result.returncode}, "
                    f"stdout={result.stdout.strip()!r})"
                )

        assert not_ignored == [], (
            "BP-016 FAILED: the following build-output shim paths are NOT "
            "matched by .gitignore, so a rebuild via install_shims() could "
            "silently re-add them to the index once untracked. Fix the "
            ".gitignore patterns (drop the trailing slash that restricts the "
            "match to directories; add a missing entry for scripts/feedback):"
            "\n  " + "\n  ".join(not_ignored)
        )

    def test_ac_bp016_known_shim_paths_are_not_tracked(self) -> None:
        # covers: BP-016
        """Specific check: none of the three named shim paths is present in
        the git index at all (any mode).

        This is the direct symptom check from BP-016's criteria: "none of
        those three shim paths is present in the git index." Currently all
        three ARE present at mode 120000 (see
        test_ac_bp016_no_tracked_symlink_has_absolute_target for the blob
        target detail).
        """
        tracked: list[str] = []
        for rel_path in _KNOWN_SHIM_PATHS:
            result = subprocess.run(
                ["git", "-C", str(_REPO_ROOT), "ls-files", "--error-unmatch", rel_path],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0:
                tracked.append(rel_path)

        assert tracked == [], (
            "BP-016 FAILED: the following build-output shim paths are still "
            "tracked in the git index and must be removed with `git rm "
            f"--cached`: {tracked!r}"
        )
