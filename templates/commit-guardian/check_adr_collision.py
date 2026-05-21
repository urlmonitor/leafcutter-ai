"""
Pre-commit hook that detects ADR number collisions between concurrent epic worktrees.

MODULE: check_adr_collision
GOAL: Prevent two feature branches from claiming the same ADR integer, reproducing
    the 2026-05-15 ADR-024 incident where EPIC-FeedbackCollection and
    EPIC-PortableSQLAgents both authored ADR-024, causing a post-merge logical
    collision that required manual file renaming.
BUSINESS CONTEXT: ADR integer sequences are chronologically meaningful and widely
    cross-referenced. Collisions create invisible drift that surfaces only after
    merge, requiring expensive sed-based renaming across multiple files. This hook
    detects collisions at commit time — the cheapest possible intervention point.
ARCHITECTURE: Option C (ADR-029): keep integer sequence intact; add a pre-commit
    hook that scans origin/main committed ADRs plus remote in-flight branches to
    detect numeric collisions before a supervisor wires up internal cross-references.

Detection approach:
    1. Scan docs/architecture/adrs/ADR-*.md on origin/main for committed integers.
    2. Scan remote branches for in-flight ADR-NNN files not yet on origin/main.
    3. Compare the proposed ADR number (from staged files) against both sets.
    4. Exit non-zero with the next-free number if a collision is found.
    5. Exit 0 (pass silently) when no collision is detected.
    6. Exit 0 with a warning if git is unavailable or an unexpected error occurs
       (fail-open: never block legitimate commits due to script errors).

Exit Codes:
    0 — No collision detected, or script error (fail-open), or no ADR staged.
    1 — Collision detected: exit non-zero, print next-free number and remediation.
"""

import re
import subprocess
import sys
from pathlib import Path


# Pattern matching ADR filename integers: ADR-NNN-<slug>.md
_ADR_INT_RE = re.compile(r"ADR-(\d+)-.*\.md$", re.IGNORECASE)


def _run_git(*args: str, cwd: str | None = None) -> tuple[int, str, str]:
    """Run a git command and return (returncode, stdout, stderr).

    Args:
        args: Git command arguments (without the leading 'git'), passed as positional args.

    Returns:
        tuple[int, str, str]: Return code, stdout text, stderr text.
    """
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd,
    )
    return result.returncode, result.stdout, result.stderr


def get_staged_adr_numbers() -> list[int]:
    """Return the ADR integers staged in the current commit.

    Scans staged files (added or renamed) for paths matching
    docs/architecture/adrs/ADR-NNN-*.md and returns the integer list.

    Returns:
        list[int]: ADR integers from staged files. Empty if none are staged.
    """
    rc, stdout, _ = _run_git("diff", "--cached", "--name-only", "--diff-filter=AR")
    if rc != 0:
        return []
    staged_adrs = []
    for path in stdout.splitlines():
        path = path.strip()
        match = _ADR_INT_RE.search(Path(path).name)
        if match and "docs/architecture/adrs/" in path:
            staged_adrs.append(int(match.group(1)))
    return staged_adrs


def get_committed_adr_numbers(ref: str = "origin/main") -> set[int]:
    """Return the set of ADR integers committed on a given ref.

    Args:
        ref: The git ref to scan (default: origin/main).

    Returns:
        set[int]: Set of ADR integers found on the ref. Empty on any error.
    """
    rc, stdout, _ = _run_git(
        "ls-tree", "-r", "--name-only", ref, "docs/architecture/adrs/"
    )
    if rc != 0:
        return set()
    committed = set()
    for line in stdout.splitlines():
        name = Path(line.strip()).name
        match = _ADR_INT_RE.match(name)
        if match:
            committed.add(int(match.group(1)))
    return committed


def get_inflight_adr_numbers(origin_main_numbers: set[int]) -> set[int]:
    """Return ADR integers in-flight on remote branches not yet on origin/main.

    Scans all remote branches for ADR-NNN-*.md files under
    docs/architecture/adrs/ that are NOT yet committed on origin/main.

    This heuristic has a visibility gap: locally-only branches on another
    developer's machine cannot be seen. The guard is best-effort.

    Args:
        origin_main_numbers: Set of ADR integers already on origin/main
            (used to exclude them from the in-flight set).

    Returns:
        set[int]: Set of in-flight ADR integers not yet on origin/main.
    """
    rc, stdout, _ = _run_git("branch", "-r", "--format=%(refname:short)")
    if rc != 0:
        return set()
    inflight = set()
    for branch in stdout.splitlines():
        branch = branch.strip()
        if not branch or branch == "origin/main":
            continue
        rc2, ls_out, _ = _run_git(
            "ls-tree", "-r", "--name-only", branch, "docs/architecture/adrs/"
        )
        if rc2 != 0:
            continue
        for line in ls_out.splitlines():
            name = Path(line.strip()).name
            match = _ADR_INT_RE.match(name)
            if match:
                num = int(match.group(1))
                if num not in origin_main_numbers:
                    inflight.add(num)
    return inflight


def next_free_number(taken: set[int]) -> int:
    """Return the smallest positive integer not in the taken set.

    Args:
        taken: Set of integers already in use.

    Returns:
        int: The next free ADR integer (starting from 1).
    """
    if not taken:
        return 1
    candidate = max(taken) + 1
    while candidate in taken:
        candidate += 1
    return candidate


def main() -> None:
    """Run the ADR collision check.

    Designed to be fail-open: any unexpected error emits a stderr warning
    and exits 0 so legitimate commits are never blocked by script failures.
    """
    try:
        staged_numbers = get_staged_adr_numbers()
        if not staged_numbers:
            # No ADR files staged — nothing to check.
            sys.exit(0)

        committed = get_committed_adr_numbers("origin/main")
        inflight = get_inflight_adr_numbers(committed)
        all_taken = committed | inflight

        collisions = [n for n in staged_numbers if n in all_taken]
        if not collisions:
            sys.exit(0)

        for num in collisions:
            suggested = next_free_number(all_taken | set(staged_numbers) - {num})
            source = "origin/main" if num in committed else "in-flight remote branch"
            print(
                f"\033[91mERROR [check_adr_collision] "
                f"ADR-{num:03d} is already claimed on {source}.\033[0m"
            )
            print(
                f"\033[93m  Suggested next-free ADR number: {suggested:03d}\033[0m"
            )
            print(
                f"  Rename your ADR file to: "
                f"docs/architecture/adrs/ADR-{suggested:03d}-<your-slug>.md"
            )
            print(
                "  Then update all internal cross-references to use the new number "
                "before re-staging."
            )
        sys.exit(1)

    except Exception as exc:  # pylint: disable=broad-except
        print(
            f"\033[93mWARNING [check_adr_collision] "
            f"Unexpected error — skipping check (fail-open): {exc}\033[0m",
            file=sys.stderr,
        )
        sys.exit(0)


if __name__ == "__main__":
    main()


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-17 10:15 [python-coder]: Initial creation per ADR-029
  (docs/architecture/adrs/ADR-029-adr-number-collision-prevention.md).
  Implements Option C: pre-commit collision detection against origin/main
  and remote in-flight branches. Fail-open on any unexpected error.
  Ticket: tickets/99_done/TICKET-20260515-Prevent_ADR_Number_Collisions.md
====================================================================
"""
