"""
Pre-commit hook that detects ADR number collisions between concurrent epic worktrees.

MODULE: check_adr_collision
GOAL: Prevent two feature branches -- or two files staged in the same commit --
    from claiming the same ADR integer, reproducing the 2026-05-15 ADR-024
    incident where EPIC-FeedbackCollection and EPIC-PortableSQLAgents both
    authored ADR-024, causing a post-merge logical collision that required
    manual file renaming.
BUSINESS CONTEXT: ADR integer sequences are chronologically meaningful and
    widely cross-referenced. Collisions create invisible drift that surfaces
    only after merge, requiring expensive sed-based renaming across multiple
    files. This hook detects collisions at commit time -- the cheapest
    possible intervention point. GE-122a-1 adopts this existing guard (rather
    than reimplementing decision-number detection beside it) for the
    decision-number namespace of the whole-collection uniqueness effort, and
    registers it in hooks_manifest.hooks for the first time: verified
    2026-08-17, this script existed and was deployed but appeared in no
    manifest, so it had never executed.
ARCHITECTURE: Option C (ADR-029): keep integer sequence intact; add a
    pre-commit hook that scans origin/main committed ADRs plus remote
    in-flight branches to detect numeric collisions, AND detects a collision
    between two files staged together in the same commit (the case a
    history-only comparison structurally cannot see).

    Fail-open / fail-closed boundary (ADR-029 Amendment 1, 2026-08-18): the
    disposition is derived from whether the guard managed to READ the whole
    decision-number sequence, never from which exception type was caught.
    A dedicated ReadFailure exception marks every point where a required git
    read could not be completed (git unavailable, a ref/path that could not
    be listed, the remote-branch scan failing); main() treats ReadFailure as
    fail-closed (block -- nothing was established, so reporting success would
    certify an unexamined sequence) and treats any other exception as a bug
    in this guard's own reporting code AFTER a completed read, which must
    stay fail-open (warn on stderr, exit 0) so a defect here can never become
    a deployment blocker. This is a deliberate two-tier exception boundary,
    not a single blanket try/except -- a blanket handler would make every
    read failure look like an internal bug and let the unreadable-sequence
    case through silently, which is exactly the inversion Amendment 1 exists
    to prevent.

Detection approach:
    1. Scan docs/architecture/adrs/ADR-*.md on origin/main for committed integers.
    2. Scan remote branches for in-flight ADR-NNN files not yet on origin/main.
    3. Compare the staged ADR numbers against both sets AND against each other
       (a number claimed by two files in the same commit is a collision even
       when neither number was ever seen before).
    4. Exit non-zero and print the next-free number for every collision found.
    5. Exit 0 (pass silently) when no collision is detected.
    6. Exit non-zero when the sequence could not be read at all (fail-closed).
    7. Exit 0 with a warning when the sequence WAS read but something in this
       guard's own reporting code then failed unexpectedly (fail-open).

Exit Codes:
    0 - No collision detected, no ADR staged, or an internal reporting bug
        after a completed read (fail-open).
    1 - A collision was detected, or the decision-number sequence could not
        be read at all (fail-closed; see ADR-029 Amendment 1).
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

# Pattern matching ADR filename integers: ADR-NNN-<slug>.md
_ADR_INT_RE = re.compile(r"ADR-(\d+)-.*\.md$", re.IGNORECASE)

_HOOK_PREFIX = "[check_adr_collision]"
_GIT_TIMEOUT_SECONDS = 30


class ReadFailure(Exception):
    """Raised when a required git read could not be completed.

    Marks the boundary ADR-029 Amendment 1 requires: a ReadFailure means the
    decision-number sequence was not established, so the caller must not
    report success. This is distinct from any exception raised after every
    read has already completed, which is a bug in this guard's own reporting
    and must stay fail-open.
    """


def _run_git(*args: str, cwd: str | None = None) -> tuple[int, str, str]:
    """Run a git command and return (returncode, stdout, stderr).

    Args:
        args: Git command arguments (without the leading 'git'), passed as
            positional args.
        cwd: Working directory to run the command in.

    Returns:
        tuple[int, str, str]: Return code, stdout text, stderr text.

    Raises:
        ReadFailure: When git itself could not be invoked (binary missing,
            process could not be started, or the call timed out).
    """
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            check=False,
            cwd=cwd,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ReadFailure(  # noqa: TRY003
            f"git unavailable while running 'git {' '.join(args)}': {exc}"
        ) from exc
    return result.returncode, result.stdout, result.stderr


def get_staged_adr_entries() -> list[tuple[int, str]]:
    """Return the (ADR integer, path) pairs staged in the current commit.

    Scans staged files (added or renamed) for paths matching
    docs/architecture/adrs/ADR-NNN-*.md and returns one entry per FILE, so a
    number claimed by two staged files yields two entries carrying that number
    and their two distinct paths.

    Pairing the number with its own path is load-bearing rather than
    convenient: every per-file question this module asks later -- above all
    "was this file merged in, or authored here?" -- needs the path of the file
    being judged. A bare integer cannot answer it, and resolving an integer
    back to a path can only ever return one of its claimants.

    Returns:
        list[tuple[int, str]]: (number, path) per staged ADR file. Empty if
            none are staged.

    Raises:
        ReadFailure: When the staged-file listing itself could not be read.
    """
    rc, stdout, stderr = _run_git(
        "diff", "--cached", "--name-only", "--diff-filter=AR"
    )
    if rc != 0:
        raise ReadFailure(  # noqa: TRY003
            f"could not list staged files (git diff exited {rc}): {stderr.strip()}"
        )
    staged_adrs = []
    for line in stdout.splitlines():
        path = line.strip()
        match = _ADR_INT_RE.search(Path(path).name)
        if match and "docs/architecture/adrs/" in path:
            staged_adrs.append((int(match.group(1)), path))
    return staged_adrs


def get_staged_adr_numbers() -> list[int]:
    """Return the ADR integers staged in the current commit.

    Duplicates are preserved -- two staged files claiming the same number both
    appear. This is the integer view of get_staged_adr_entries(); use the
    entries form whenever the path of a specific claimant matters.

    Returns:
        list[int]: ADR integers from staged files. Empty if none are staged.

    Raises:
        ReadFailure: When the staged-file listing itself could not be read.
    """
    return [num for num, _ in get_staged_adr_entries()]


def get_committed_adr_numbers(ref: str = "origin/main") -> set[int]:
    """Return the set of ADR integers committed on a given ref.

    Args:
        ref: The git ref to scan (default: origin/main).

    Returns:
        set[int]: Set of ADR integers found on the ref.

    Raises:
        ReadFailure: When the ref's ADR tree could not be read -- this
            covers "ref does not exist" and "path absent on that ref"
            identically, per ADR-029 Amendment 1 ("the ADR directory absent"
            is named as a read-failure case, not a legitimate empty result).
    """
    rc, stdout, stderr = _run_git(
        "ls-tree", "-r", "--name-only", ref, "docs/architecture/adrs/"
    )
    if rc != 0:
        raise ReadFailure(  # noqa: TRY003
            f"could not read the decision sequence on {ref!r} "
            f"(git ls-tree exited {rc}): {stderr.strip()}"
        )
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
    developer's machine cannot be seen. The guard remains best-effort against
    *unpushed* work -- ADR-029 Amendment 1 is explicit that this limit is
    unaffected by the fail-open/fail-closed narrowing, since an unpushed
    branch is not a read failure (there is nothing there to fail to read).

    Args:
        origin_main_numbers: Set of ADR integers already on origin/main
            (used to exclude them from the in-flight set).

    Returns:
        set[int]: Set of in-flight ADR integers not yet on origin/main.

    Raises:
        ReadFailure: When the remote-branch listing itself could not be
            read. A single branch whose ADR directory cannot be listed is
            NOT treated as a read failure -- that is the ordinary, expected
            state for any branch predating the ADR directory or carrying no
            ADRs, so that per-branch case is skipped rather than raised.
    """
    rc, stdout, stderr = _run_git("branch", "-r", "--format=%(refname:short)")
    if rc != 0:
        raise ReadFailure(  # noqa: TRY003
            f"could not list remote branches (git branch -r exited {rc}): "
            f"{stderr.strip()}"
        )
    inflight = set()
    for branch in stdout.splitlines():
        branch = branch.strip()
        if not branch or branch == "origin/main":
            continue
        rc2, ls_out, _ = _run_git(
            "ls-tree", "-r", "--name-only", branch, "docs/architecture/adrs/"
        )
        if rc2 != 0:
            # Ordinary state (branch predates the directory, or has no ADRs
            # staged on it) -- not a sequence read failure, so skip it.
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


def _find_self_collisions(numbers: list[int]) -> set[int]:
    """Return numbers claimed by more than one file staged in this commit.

    A history-only comparison (staged vs. origin/main vs. in-flight
    branches) cannot see this case: two brand-new files, staged together,
    claiming the same never-before-seen number. This is the literal Gherkin
    scenario GE-122a-1 names for the decision namespace.

    Args:
        numbers: List of ADR integers extracted from staged files (may
            contain repeats).

    Returns:
        set[int]: Numbers that appear more than once in numbers.
    """
    counts = Counter(numbers)
    return {number for number, count in counts.items() if count > 1}


def _is_merge_in(num: int, path: str, committed: set[int]) -> bool:
    """Return True when THIS staged file was merged in from origin/main.

    The exemption is a property of a file, never of a number. Judging it per
    number and then dropping every staged claimant of that number discards the
    author's own file alongside the upstream one -- and when both are staged
    together, that empties the very list the collision detectors read, so the
    guard exits 0 on the exact double-claim it exists to catch (GE-122a-1-ii).
    Each caller therefore asks this question once per staged file, naming that
    file's own path.

    Both probes are on THIS PATH. "Absent from HEAD" alone does not identify a
    merged-in file -- a file the author just wrote is equally absent from HEAD
    -- so it only distinguishes anything once paired with "present upstream".
    Asking whether the NUMBER is upstream instead of whether the FILE is
    upstream is precisely the collapse that produced the defect.

    Args:
        num: ADR integer claimed by the staged file.
        path: Path of the staged file being judged.
        committed: Set of ADR integers already committed on origin/main. Used
            only as a cheap early-out: a number absent upstream cannot have an
            upstream file, so no git call is needed for it.

    Returns:
        bool: True if this exact file exists on origin/main and was not in HEAD
            before staging -- i.e. staging is what brought it in.
    """
    if num not in committed:
        return False
    rc_upstream, _, _ = _run_git("cat-file", "-e", f"origin/main:{path}")
    if rc_upstream != 0:
        # This file does not exist upstream, so it was authored here --
        # regardless of what some other staged file claiming the same
        # number did.
        return False
    rc_head, _, _ = _run_git("cat-file", "-e", f"HEAD:{path}")
    # rc != 0 means it was NOT in HEAD -> it was brought in by staging.
    return rc_head != 0


def _emit_collision(num: int, source: str, suggestion_pool: set[int]) -> None:
    """Print a collision error block for one contested ADR number.

    Args:
        num: The contested ADR integer.
        source: Human-readable description of where the collision was found.
        suggestion_pool: Set of taken numbers (excluding num) used to compute
            a suggested next-free replacement.
    """
    suggested = next_free_number(suggestion_pool)
    print(
        f"\033[91mERROR {_HOOK_PREFIX} ADR-{num:03d} is already claimed "
        f"({source}).\033[0m"
    )
    print(f"\033[93m  Suggested next-free ADR number: {suggested:03d}\033[0m")
    print(
        f"  Rename your ADR file to: "
        f"docs/architecture/adrs/ADR-{suggested:03d}-<your-slug>.md"
    )
    print(
        "  Then update all internal cross-references to use the new number "
        "before re-staging."
    )


def _run_collision_check() -> int:
    """Run the full collision check, letting ReadFailure propagate to main().

    Returns:
        int: 0 if no collisions, 1 if any collisions found.

    Raises:
        ReadFailure: Propagated from any git-reading helper when the
            decision-number sequence could not be established.
    """
    staged_entries = get_staged_adr_entries()
    if not staged_entries:
        return 0

    committed = get_committed_adr_numbers("origin/main")
    inflight = get_inflight_adr_numbers(committed)
    all_taken = committed | inflight

    # Filter FILE BY FILE, not number by number: a merge that brings an
    # upstream ADR in excuses that file only. Any other staged file claiming
    # the same number was authored here and must still be judged.
    staged_numbers = [
        num
        for num, path in staged_entries
        if not _is_merge_in(num, path, committed)
    ]
    if not staged_numbers:
        return 0

    cross_collisions = {n for n in staged_numbers if n in all_taken}
    self_collisions = _find_self_collisions(staged_numbers)
    collisions = cross_collisions | self_collisions
    if not collisions:
        return 0

    suggestion_base = all_taken | set(staged_numbers)
    for num in sorted(collisions):
        if num in committed:
            source = "origin/main"
        elif num in inflight:
            source = "in-flight remote branch"
        else:
            source = "duplicate within this commit"
        _emit_collision(num, source, suggestion_base - {num})
    return 1


def main() -> int:
    """Run the ADR collision check.

    Per ADR-029 Amendment 1, disposition is derived from whether the guard
    managed to read the whole decision-number sequence, never from which
    exception type was raised: ReadFailure means the sequence was not
    established (fail-closed -- block); any other exception means the
    sequence WAS read and something in this guard's own reporting broke
    afterward (fail-open -- warn and let the commit through).

    Returns:
        int: 0 on no collision (or a post-read reporting bug); 1 on a
            detected collision or an inability to read the sequence.
    """
    try:
        return _run_collision_check()
    except ReadFailure as exc:
        print(
            f"{_HOOK_PREFIX} BLOCKED -- could not read the decision-number "
            f"sequence: {exc}",
            file=sys.stderr,
        )
        print(
            f"{_HOOK_PREFIX} Uniqueness was not established, so this commit "
            "cannot proceed. See ADR-029 Amendment 1.",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:  # noqa: BLE001 -- deliberate fail-open boundary.
        # ReadFailure (the only "could not establish the sequence" case) is
        # caught above. Anything else reaching here happened AFTER every read
        # completed, so it is a bug in this guard's own reporting code, which
        # must never become a deployment blocker (ADR-029 Amendment 1).
        print(
            f"\033[93mWARNING {_HOOK_PREFIX} unexpected error after a "
            f"completed read -- skipping check (fail-open): {exc}\033[0m",
            file=sys.stderr,
        )
        return 0


if __name__ == "__main__":
    sys.exit(main())


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-17 10:15 [python-coder]: Initial creation per ADR-029. (#TICKETLESS reason=standalone-precommit-hook)
  (docs/architecture/adrs/ADR-029-adr-number-collision-prevention.md).
  Implements Option C: pre-commit collision detection against origin/main
  and remote in-flight branches. Fail-open on any unexpected error.
  Ticket: tickets/99_done/TICKET-20260515-Prevent_ADR_Number_Collisions.md
- 2026-05-18 00:00 [epic-supervisor/merge]: Added merge-commit detection to skip ADRs brought in from origin/main. (#EPIC-UserSurfaceVerification/merge)
- 2026-08-18 [python-coder/GE-122a-1]: Adopted for registration (was deployed
  but wired into no manifest -- see commit_guardian.json's new
  "check-decision-number-uniqueness" entry). Two behavioural changes per
  ADR-029 Amendment 1: (1) narrowed fail-open to the guard's own reporting
  defects only -- introduced ReadFailure and a two-tier exception boundary
  in main() so an inability to read the sequence (git unavailable, ref/path
  unreadable, remote-branch scan failing) now blocks the commit instead of
  exiting 0; (2) added _find_self_collisions() so two files staged together
  in the same commit that claim the same never-before-seen number are now
  detected -- a history-only comparison against origin/main and in-flight
  branches cannot see that case, and it is the literal Gherkin scenario
  GE-122a-1 names for the decision namespace.
- 2026-08-26 [python-coder/GE-122a-1-ii]: Scoped the merged-in exemption to the
  FILE instead of the NUMBER. The filter was keyed on the ADR integer and
  resolved that integer to a single staged path via a first-match lookup
  (_adr_num_to_path), so when a merge staged an upstream ADR-034 and the author
  staged their own new ADR-034 in the same commit, the lookup returned
  whichever path sorted first, the exemption dropped BOTH claimants, and
  _find_self_collisions ran on an emptied list -- the guard exited 0 on the
  double-claim it exists to catch, and did so intermittently depending on
  filename order. get_staged_adr_entries() now carries (number, path) pairs
  through to the filter, _is_merge_in() takes the path of the file it is
  judging, and _adr_num_to_path() is deleted rather than corrected so no future
  caller can reintroduce the number-to-path collapse. get_staged_adr_numbers()
  keeps its integer signature and delegates (retained as public API; the
  entries form is what this module now consumes). The exemption also gained a
  second probe: a file only counts as merged in when its own path exists on
  origin/main AND is absent from HEAD. Absence from HEAD alone cannot
  distinguish a merged-in file from one the author just wrote, so a per-file
  filter without the upstream probe still drops the authored file and still
  passes the double-claim -- verified against the test. Git-call cost per
  staged ADR: one 'git diff --cached' removed, one 'cat-file -e origin/main:'
  added, and the latter only for numbers already known to be upstream.
====================================================================
"""
