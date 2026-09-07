"""
MODULE: commit_guardian.check_file_size
GOAL: Pre-commit hook to block files exceeding line limits to encourage
    refactoring, AND to ratchet already-oversized files so they can be
    worked on but never made bigger.
BUSINESS CONTEXT: Keeps file complexity under control by forcing refactors of
    bloated files. The ratchet (GE-127b-1 / GE-127b-1-i) is what makes the
    absolute-limit check switchable without refusing essentially every
    commit that touches one of the ~200 files already over their limit: a
    file already over the line may shrink or stay the same size and commit
    cleanly, but a change that leaves it LONGER than it stood at HEAD is
    refused.
ARCHITECTURE: Delegates previous-length resolution and the shared line
    -counting rule to the sibling module _file_size_ratchet.py (see that
    module for the HEAD-blob lookup, the two-situation INDETERMINATE
    fail-closed floor, and why no persisted baseline / new config key is
    used). An empty previous-length history (unborn HEAD, or a HEAD tree
    with no covered file) is a legitimate, COMPLETING result named
    "EMPTY HISTORY" in the run's output, never folded into INDETERMINATE.

Pre-commit hook to block files exceeding line limits.

Line Limits:
- Python (.py): 400 lines max
- SQL (.sql): 600 lines max

Exit Codes:
    0 - All files within limits (or shrunk/unchanged while still over, or
        the previous-length history is empty)
    1 - One or more files exceed limits, or grew while already over
    2 - INDETERMINATE: the previous-length source could not be reached at
        all, or a resolvable HEAD blob could not be interpreted

Usage:
    poetry run python scripts/commit_guardian/check_file_size.py
"""

import subprocess
import sys
from pathlib import Path

from _resolve_root import find_project_root

project_root = find_project_root()

from _file_size_ratchet import (
    EMPTY_HISTORY_REASON,
    PreviousLengthSourceError,
    count_content_lines,
    resolve_head_covered_paths,
    resolve_previous_lengths,
)
from config import (
    CHECKED_EXTENSIONS,
    DEFAULT_LINE_LIMIT,
    FILE_LINE_LIMITS,
)


def get_staged_files() -> dict[str, bool]:
    """
    Get all staged files with their status (new vs modified).

    Returns:
        Dictionary mapping filepath to is_new_file boolean.
        True = newly added file, False = modified existing file.

    Raises:
        PreviousLengthSourceError: the staged file list itself could not be
            read because the previous-length source cannot be reached at
            all (the working copy is not a git repository, or git is
            unavailable). This is the "unreachable" refusing situation
            decided AT THE POINT OF RESOLUTION -- never downstream by
            treating a would-be-empty result as genuine emptiness.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-status"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        stderr_text = exc.stderr.strip() if isinstance(exc, subprocess.CalledProcessError) and exc.stderr else ""
        raise PreviousLengthSourceError(
            "the previous lengths could not be read: staged files could not "
            f"be listed via git ({stderr_text or exc})"
        ) from exc

    staged_files: dict[str, bool] = {}
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            status = parts[0]
            filepath = parts[1]
            # "A" = Added (new file), "M" = Modified, etc.
            is_new = status.startswith("A")
            staged_files[filepath] = is_new

    return staged_files


def count_lines(filepath: str) -> int:
    """
    Count all lines in a file (excluding docstrings and block comments).

    Delegates the actual counting rule to count_content_lines(), the same
    pure function used to measure a file's previous (HEAD blob) length, so
    the current-length and previous-length measurements can never drift
    apart by even one line.

    Args:
        filepath: Path to the file to count.

    Returns:
        Total number of lines in the file, or 0 if it cannot be read.
    """
    path = Path(filepath)
    if not path.exists():
        return 0

    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"⚠️  Could not read {filepath} to measure its length: {exc}", file=sys.stderr)
        return 0

    return count_content_lines(content)


def get_limit_for_extension(filepath: str) -> int:
    """
    Get the line limit for a file based on its extension.

    Args:
        filepath: Path to check.

    Returns:
        Line limit for the file type.
    """
    ext = Path(filepath).suffix.lower()
    return FILE_LINE_LIMITS.get(ext, DEFAULT_LINE_LIMIT)


def should_check_file(filepath: str) -> bool:
    """
    Determine if a file should be checked based on its extension.

    Args:
        filepath: Path to the file.

    Returns:
        True if the file should be checked.
    """
    ext = Path(filepath).suffix.lower()
    return ext in CHECKED_EXTENSIONS


def check_file(filepath: str, is_new_file: bool) -> tuple[bool, int, int]:
    """
    Check if a file passes the size limit.

    Args:
        filepath: Path to the file to check.
        is_new_file: Whether this is a newly added file.

    Returns:
        Tuple of (passes_check, line_count, limit).
    """
    limit = get_limit_for_extension(filepath)
    lines = count_lines(filepath)

    return lines <= limit, lines, limit


def _print_grown_file(filepath: str, previous_length: int, current_length: int) -> None:
    """Print the refusal block for a file that grew while already oversized.

    Args:
        filepath: The staged file's path.
        previous_length: The length it stood at, at HEAD, before the change.
        current_length: The length it stands at after the staged change.
    """
    print("❌ FILE GREW WHILE ALREADY OVER ITS LIMIT:")
    print(f"   {filepath}")
    print(f"   Previous length: {previous_length} lines")
    print(f"   New length: {current_length} lines")
    print()
    print("   An already-oversized file may still be worked on, but a change")
    print("   that leaves it LONGER than it stood before is refused. Shrink")
    print("   it, or leave its length unchanged, to commit this edit.\n")


def _print_too_large_file(filepath: str, lines: int, limit: int) -> None:
    """Print the refusal block for a file over its absolute limit.

    Args:
        filepath: The staged file's path.
        lines: The file's current length.
        limit: The permitted length for this file's extension.
    """
    print("❌ FILE TOO LARGE:")
    print(f"   {filepath}")
    print(f"   Lines: {lines} (Limit: {limit})")
    print()
    print("   Please refactor and split this file before committing.")
    print("   DO NOT simply delete blank lines, comments, or docstrings to bypass this.")
    print("   You MUST split the file to make it easier and less token consuming for agents.")
    if filepath.endswith(".md"):
        print("   Use the `@documentation-expert` agent to intelligently split this markdown file.")
    elif filepath.endswith(".py"):
        print("   Use the `/code-refactoring-specialist` slash command to intelligently split this Python file.")
    else:
        print("   Use the `/code-refactoring-specialist` slash command or relevant skill to intelligently split the file.")
    print("   (We enforce this check to force refactoring of older files over time).\n")


def _resolve_ratchet_or_indeterminate(covered_paths: list[str]) -> tuple[dict[str, int] | None, int | None]:
    """Resolve previous lengths for *covered_paths*, or the INDETERMINATE exit.

    The previous-length SOURCE is classified exactly once here, at the
    point of resolution: empty history (HEAD holds no covered file at all,
    including an unborn HEAD) is a legitimate, COMPLETING result named in
    the outcome as "EMPTY HISTORY" -- it must never be confused with the
    two REFUSING situations (source unreachable, source uninterpretable),
    which exit 2 as "INDETERMINATE". This distinction is made by which
    function raised / what it returned, never downstream by inspecting how
    many previous lengths came back.

    Args:
        covered_paths: Staged file paths of a checked extension.

    Returns:
        A (previous_lengths, exit_code) pair. On success (including empty
        history), exit_code is None and previous_lengths is the resolved
        mapping (possibly empty). On an unresolvable source, previous_lengths
        is None and exit_code is 2 — the caller must print nothing else and
        return that exit code.
    """
    if not covered_paths:
        return {}, None

    try:
        covered_at_head = resolve_head_covered_paths(CHECKED_EXTENSIONS)
    except PreviousLengthSourceError as exc:
        print(f"INDETERMINATE: reason={exc.reason}", file=sys.stderr)
        return None, 2

    if not covered_at_head:
        # Empty history (unborn HEAD, or a tree with no covered file) --
        # completes at exit 0, named distinctly from both INDETERMINATE
        # reasons so this token never gets read as a refusal.
        print(f"EMPTY HISTORY: reason={EMPTY_HISTORY_REASON}")
        return {}, None

    try:
        previous_lengths = resolve_previous_lengths(covered_paths)
    except PreviousLengthSourceError as exc:
        print(f"INDETERMINATE: reason={exc.reason}", file=sys.stderr)
        return None, 2

    return previous_lengths, None


def _classify_file(
    filepath: str, is_new: bool, previous_lengths: dict[str, int]
) -> tuple[str, int, int | None]:
    """Classify one staged, covered file into pass / grew / too-large.

    Args:
        filepath: The staged file's path.
        is_new: Whether this is a newly added file.
        previous_lengths: Mapping of path to its length at HEAD, for files
            that had one.

    Returns:
        A (verdict, current_length, reference_length) triple. verdict is
        one of "pass", "grew", or "too_large". reference_length is the
        previous length for "grew", the limit for "too_large", or None for
        "pass".
    """
    lines = count_lines(filepath)
    limit = get_limit_for_extension(filepath)
    previous = previous_lengths.get(filepath)

    if previous is not None and previous > limit:
        # This file is already past its permitted length per GE-127b: judge
        # it against its OWN previous length, never against the fixed limit.
        if lines > previous:
            return "grew", lines, previous
        return "pass", lines, None

    if lines > limit:
        return "too_large", lines, limit
    return "pass", lines, None


def main() -> int:
    """
    Main entry point for the pre-commit hook.

    Returns:
        Exit code: 0 (all files within limits, or already-oversized files
        that shrank/stayed the same, or the previous-length history is
        empty), 1 (a file exceeds its limit or grew while already
        oversized), or 2 (INDETERMINATE — the previous-length source could
        not be reached at all, or a resolvable HEAD blob could not be
        interpreted).
    """
    # Ensure header output (emojis) works on Windows
    if sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            # Python < 3.7 doesn't support reconfigure, but we're likely on modern Python
            pass

    try:
        staged_files = get_staged_files()
    except PreviousLengthSourceError as exc:
        print(f"INDETERMINATE: reason={exc.reason}", file=sys.stderr)
        return 2

    if not staged_files:
        return 0

    covered_files = {fp: is_new for fp, is_new in staged_files.items() if should_check_file(fp)}

    previous_lengths, indeterminate_exit = _resolve_ratchet_or_indeterminate(list(covered_files))
    if indeterminate_exit is not None:
        return indeterminate_exit

    grown_files: list[tuple[str, int, int]] = []
    failed_files: list[tuple[str, int, int]] = []
    passed_files: list[tuple[str, int, bool]] = []  # (path, lines, is_new)

    for filepath, is_new in covered_files.items():
        verdict, lines, reference = _classify_file(filepath, is_new, previous_lengths)
        if verdict == "grew":
            grown_files.append((filepath, reference, lines))
        elif verdict == "too_large":
            failed_files.append((filepath, lines, reference))
        else:
            passed_files.append((filepath, lines, is_new))

    # Print results
    print("\n📏 File Size Check\n")
    print(f"📊 Compared {len(previous_lengths)} file(s) against their previous length.\n")

    for filepath, previous, lines in grown_files:
        _print_grown_file(filepath, previous, lines)

    for filepath, lines, limit in failed_files:
        _print_too_large_file(filepath, lines, limit)

    if passed_files:
        print(f"✅ PASSED: {len(passed_files)} files checked")
        for filepath, lines, is_new in passed_files:
            status = "new" if is_new else "modified"
            print(f"   - {filepath} ({status}, {lines} lines - OK)")

    if grown_files or failed_files:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-01 [python-coder/GE-127b-1 + GE-127b-1-i]: Added the ratchet: an
  already-oversized file (previous HEAD length over its limit) that GROWS is
  refused, naming both the previous and new lengths; one that shrinks or
  stays the same size commits cleanly even though still over the limit. A
  file with no HEAD blob (new file) is never coerced to a previous length of
  zero. Added the INDETERMINATE (exit 2) fail-closed floor: the previous
  -length source (HEAD's tree) must resolve and must hold at least one
  covered file, or the run refuses by name (could-not-be-read /
  could-not-be-interpreted / holds-no-covered-file) rather than silently
  reporting a compared count of zero. The compared-file count is now always
  printed. Previous-length resolution and the shared count_content_lines()
  measurement function moved to the new sibling module _file_size_ratchet.py.
- 2026-09-07 [python-coder/GE-127b-1-i correction]: Narrowed the refusing
  set from three situations to two per the 2026-09-01 criteria correction:
  an unborn HEAD and a HEAD tree holding no covered file are now BOTH a
  legitimate, COMPLETING "EMPTY HISTORY" result (exit 0, named distinctly
  from INDETERMINATE) rather than a refusal -- refusing either deadlocked
  the first commit of every fresh consumer-project install. Wrapped
  get_staged_files()'s `git diff --cached` call in a try/except so a
  working copy that is not a git repository at all raises
  PreviousLengthSourceError and reports INDETERMINATE (exit 2) instead of
  crashing uncaught with a CalledProcessError.
- 2026-05-01 17:31 [Antigravity]: Updated file size check to enforce limits on all changed files, not just new ones, to drive progressive refactoring.
- 2026-03-01 10:00: Initial implementation.
====================================================================
"""
