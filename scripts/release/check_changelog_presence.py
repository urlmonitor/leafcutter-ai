"""
MODULE: check_changelog_presence
GOAL: CI gate that fails when a PR changes releasable content but adds no
    changelog entry, ensuring work cannot silently merge to main without a
    release-triggering entry in changelogs/.
BUSINESS CONTEXT: The auto-release flow (compute_next_version.py) only bumps
    the version when a changelogs/ entry exists since the last v* tag. Without
    this gate a PR can merge code, docs, or config without a changelog entry
    and be silently excluded from the next version bump — making it invisible
    to package consumers downstream.
ARCHITECTURE: Single-module CLI (stdlib-only, no third-party imports). Exposes
    a pure core function evaluate() for unit testability — the test suite can
    drive all logic without spawning any git process. Thin git helpers
    _get_changed_paths() and _has_added_changelog() provide the inputs for
    the CLI path. Modelled on compute_next_version.py (_resolve_repo_root
    pattern, DECISION HISTORY block, error-handling conventions).
    Invoked from .github/workflows/ci.yml on pull_request events only.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Files whose path starts with one of these prefixes do NOT require a changelog
# entry. A PR whose entire diff is confined to these prefixes is considered
# non-releasable and passes this gate without a changelogs/ addition.
#
# To add or remove a prefix: edit this tuple and add a DECISION HISTORY entry
# at the bottom of this file so the change is auditable.
EXEMPT_PREFIXES: tuple[str, ...] = (
    "changelogs/",
    "tickets/",
    "docs/acceptance-criteria/",
)

# Maximum number of releasable files printed in the failure message.
# Keep low enough for a readable CI log line, high enough to be useful.
_MAX_FILES_IN_MESSAGE: int = 15


# ---------------------------------------------------------------------------
# Pure core logic (no git, fully unit-testable)
# ---------------------------------------------------------------------------


def evaluate(
    changed_paths: list[str],
    added_changelog: bool,
) -> tuple[bool, str]:
    """Determine whether the changelog-presence requirement is satisfied.

    This is the pure logic kernel of the gate. It performs no I/O; all
    inputs are pre-computed by the caller. This makes it directly testable
    without a git repository.

    Args:
        changed_paths: Every file path changed in the PR (any diff status —
            added, modified, renamed, etc.). Paths should be repo-relative
            (e.g. ``"scripts/release/check_changelog_presence.py"``).
        added_changelog: True when at least one file was *added* (git status A)
            under ``changelogs/`` with a ``.md`` extension.

    Returns:
        A ``(ok, message)`` pair. ``ok`` is True when the gate passes.
        When ``ok`` is False the message explains the violation and the fix.
        When ``ok`` is True the message is a one-line summary suitable for
        printing to CI output.
    """
    releasable = [
        p for p in changed_paths
        if not any(p.startswith(prefix) for prefix in EXEMPT_PREFIXES)
    ]

    if not releasable:
        return True, "OK: no releasable files changed — changelog entry not required."

    if added_changelog:
        return True, (
            f"OK: changelog entry present ({len(releasable)} releasable file(s) changed)."
        )

    shown = releasable[:_MAX_FILES_IN_MESSAGE]
    listed = "\n  ".join(shown)
    overflow = ""
    if len(releasable) > _MAX_FILES_IN_MESSAGE:
        overflow = f"\n  ... and {len(releasable) - _MAX_FILES_IN_MESSAGE} more file(s)."

    message = (
        f"FAIL: {len(releasable)} releasable file(s) changed but no changelogs/ "
        f"entry was added.\n"
        f"\nReleasable files that triggered this check:\n"
        f"  {listed}{overflow}\n"
        f"\nFix: run `/changelog` or manually add a `changelogs/*.md` entry to this PR.\n"
        f"     A changelog entry is required for any PR that changes files outside of:\n"
        f"     {', '.join(EXEMPT_PREFIXES)}"
    )
    return False, message


# ---------------------------------------------------------------------------
# Self-location helper (mirrors compute_next_version.py topology)
# ---------------------------------------------------------------------------


def _resolve_repo_root() -> Path:
    """Compute the repository root from this script's own location.

    Supports three topologies (same as compute_next_version.py):

    1. Package development workspace:
       ``__file__ = <repo_root>/scripts/release/check_changelog_presence.py``
       parents[2] == <repo_root> and ``.git`` is present.
    2. Consumer project (copy-installed):
       parents[2] == <consumer>/leafcutter/ — no ``.git``.
       parents[3] == <consumer>/ — ``.git`` is a directory.
    3. Consumer project submodule:
       parents[2] == <consumer>/leafcutter/ — ``.git`` is a *file*
       (submodule pointer). ``(p2 / ".git").exists()`` catches both
       directory and file forms.
    """
    resolved_self = Path(__file__).resolve()
    p2 = resolved_self.parents[2]
    if (p2 / ".git").exists():
        return p2
    return resolved_self.parents[3]


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _get_changed_paths(base: str, repo_root: Path) -> list[str]:
    """Return all paths changed between *base* and HEAD using a three-dot diff.

    Runs ``git diff --name-only --diff-filter=ACMR <base>...HEAD`` so only
    added, copied, modified, and renamed files are returned (not deletes).

    Args:
        base: The merge-base ref, e.g. ``"origin/main"``.
        repo_root: Absolute path to the repository root (used as cwd).

    Returns:
        A list of repo-relative file paths, possibly empty.

    Raises:
        subprocess.CalledProcessError: When git exits non-zero.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACMR", f"{base}...HEAD"],
            capture_output=True,
            text=True,
            cwd=repo_root,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(
            f"[check_changelog_presence] git diff --name-only failed "
            f"(exit {exc.returncode}): {exc.stderr.strip()}",
            file=sys.stderr,
        )
        raise

    return [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]


def _has_added_changelog(base: str, repo_root: Path) -> bool:
    """Return True when the PR *adds* at least one ``changelogs/*.md`` file.

    Runs ``git diff --name-status <base>...HEAD`` and checks for lines whose
    status starts with ``A`` (added), whose path is under ``changelogs/``,
    and whose path ends with ``.md``.

    Args:
        base: The merge-base ref, e.g. ``"origin/main"``.
        repo_root: Absolute path to the repository root (used as cwd).

    Returns:
        True if an added changelog entry is found, False otherwise.

    Raises:
        subprocess.CalledProcessError: When git exits non-zero.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-status", f"{base}...HEAD"],
            capture_output=True,
            text=True,
            cwd=repo_root,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(
            f"[check_changelog_presence] git diff --name-status failed "
            f"(exit {exc.returncode}): {exc.stderr.strip()}",
            file=sys.stderr,
        )
        raise

    for line in result.stdout.strip().split("\n"):
        parts = line.split("\t", 1)
        if len(parts) == 2:
            status, path = parts
            if (
                status.startswith("A")
                and path.startswith("changelogs/")
                and path.endswith(".md")
            ):
                return True
    return False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for check_changelog_presence.

    Returns the exit code: 0 when the gate passes, 1 when it fails or when
    an unexpected error occurs.
    """
    parser = argparse.ArgumentParser(
        prog="check_changelog_presence",
        description=(
            "Fail (exit 1) when a PR changes releasable content but adds no "
            "changelogs/ entry. Exit 0 means the gate passes."
        ),
    )
    parser.add_argument(
        "--base",
        required=True,
        metavar="REF",
        help="Base ref for the three-dot diff, e.g. 'origin/main'.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Override repo-root detection (for testing). Defaults to auto-detection.",
    )
    args = parser.parse_args(argv)

    repo_root = args.repo_root if args.repo_root is not None else _resolve_repo_root()

    try:
        changed_paths = _get_changed_paths(args.base, repo_root)
        added_changelog = _has_added_changelog(args.base, repo_root)
    except subprocess.CalledProcessError:
        # Error already printed to stderr by the helper.
        return 1

    ok, message = evaluate(changed_paths, added_changelog)
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (subprocess.SubprocessError, OSError) as exc:
        print(
            f"[check_changelog_presence] unexpected error: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-11 [python-coder/feat/ci-changelog-presence-gate]:
#   Created module. Implements a PR-scoped changelog-presence CI gate so
#   releasable work cannot merge to main without triggering the auto-release
#   flow (which only bumps the version when a changelogs/ entry exists since
#   the last v* tag). Design choices:
#
#   - Pure evaluate() function accepts pre-computed git data so the full
#     logic is unit-testable without any real git repository.
#   - Three-dot diff (base...HEAD) is used for both helpers to capture
#     exactly the commits introduced by the PR branch, consistent with the
#     done-proof and component-vocab CI jobs.
#   - EXEMPT_PREFIXES covers changelogs/, tickets/, and
#     docs/acceptance-criteria/ — the three path families that carry
#     metadata, AC definitions, and changelog entries themselves, none of
#     which represent releasable code or config changes.
#   - _MAX_FILES_IN_MESSAGE = 15 caps the failure output so CI logs
#     stay readable even when a large refactor triggers the gate.
#   - _resolve_repo_root() mirrors compute_next_version.py exactly,
#     supporting standalone dev, copy-installed, and submodule topologies.
#   - Stdlib-only, consistent with all other scripts/release/ scripts.
# ====================================================================
