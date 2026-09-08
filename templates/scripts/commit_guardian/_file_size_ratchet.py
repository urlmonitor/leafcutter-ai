"""
MODULE: commit_guardian._file_size_ratchet
GOAL: Resolve each staged covered file's previous (HEAD) length via git,
    using the SAME measurement function used on the file's current content,
    and classify the run's previous-length SOURCE into exactly one of three
    outcomes: available (HEAD holds at least one covered file, so a
    per-file lookup proceeds), empty history (HEAD resolves to no commit
    yet, or its tree holds no covered file at all — an ordinary day-one
    state that must COMPLETE, never refuse), or indeterminate (the source
    could not be reached at all, or a resolvable HEAD blob could not be
    interpreted — the only two situations that refuse). This stops a
    broken git lookup from silently masquerading as "nothing to compare"
    (the fail-open shape KI-CG-034, KI-CG-012 and KI-CG-018 all shipped on
    this component before) WITHOUT reinstating the opposite defect: an
    empty-but-genuine history deadlocking every fresh consumer-project
    install, since the first commit that would populate it is the one a
    refusal would be blocking on.
BUSINESS CONTEXT: Backs the GE-127b-1 / GE-127b-1-i ratchet: an already
    -oversized file may be worked on, but a change that leaves it longer
    than it stood at HEAD is refused, while a shrink or no-op is allowed
    even though the file is still over its limit. See
    docs/acceptance-criteria/guardrail-engine/GE-127-files-stay-workable/.
ARCHITECTURE: Sibling module to check_file_size.py, inside
    templates/scripts/commit_guardian/. build_commit_guardian copies this
    directory whole, so no scripts/build_phases.py deploy-map entry is
    required — a module imported from OUTSIDE this directory would need one.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

_SUBPROCESS_TIMEOUT_SECONDS = 15

_TRIPLE_DOUBLE_QUOTE_RE = re.compile(r'""".*?"""', re.DOTALL)
_TRIPLE_SINGLE_QUOTE_RE = re.compile(r"'''.*?'''", re.DOTALL)
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)


class PreviousLengthSourceError(Exception):
    """Raised for exactly the two REFUSING situations: the previous-length
    source cannot be reached at all (not a git repository, or git
    unavailable), or it is reached but a resolvable HEAD blob cannot be
    interpreted.

    Attributes:
        reason: Human-readable text naming which situation occurred. Printed
            verbatim by the caller after ``INDETERMINATE: reason=``.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class CurrentLengthUnmeasurableError(Exception):
    """Raised for the two REFUSING situations on a staged file's CURRENT
    (working-tree) content: it cannot be opened at all, or it can be opened
    but is not readable as text in the encoding the standard reads.

    A staged DELETION is deliberately NOT one of these situations -- see
    ``measure_current_length``'s docstring -- so this error must never be
    raised for a path that simply does not exist.

    Attributes:
        reason: Human-readable text naming which of the two situations
            occurred. Printed verbatim by the caller after
            ``INDETERMINATE: reason=``.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


# Pinned reason text for the COMPLETING empty-history situation (exit 0),
# shared verbatim between its two sub-cases — an unborn HEAD (no commit
# exists yet) and a populated HEAD whose tree holds no covered file — so
# callers can tell it apart from the two INDETERMINATE reasons above without
# borrowing that token. See the 2026-09-01 criteria correction on
# GE-127b-1-i: refusing either sub-case deadlocks a fresh consumer-project
# install, since the first commit that would populate the history is the one
# being refused.
EMPTY_HISTORY_REASON = (
    "the previous-length history holds no covered file whatsoever: HEAD "
    "resolves to no commit yet, or its tree contains no file of a checked "
    "extension"
)


def count_content_lines(content: str) -> int:
    """Count *content*'s lines after stripping docstrings and block comments.

    This is the SINGLE measurement rule used everywhere a line count is
    needed: the file's current (staged/working) content and its previous
    (HEAD blob) content. Calling this one function twice is how the
    ratchet's before/after comparison is built without risking two
    implementations of the counting rule drifting apart by even one line.

    Args:
        content: The file's full text content.

    Returns:
        The number of lines remaining after stripping docstring and
        block-comment regions.
    """
    stripped = _TRIPLE_DOUBLE_QUOTE_RE.sub("", content)
    stripped = _TRIPLE_SINGLE_QUOTE_RE.sub("", stripped)
    stripped = _BLOCK_COMMENT_RE.sub("", stripped)
    return len(stripped.splitlines())


def measure_current_length(filepath: str) -> int:
    """Measure the CURRENT (working-tree) line count of *filepath*.

    A staged DELETION is explicitly OUT OF SCOPE for this function's caller
    to resolve: this function is only ever invoked once the caller has
    already confirmed the path exists on disk, so a non-existent path (a
    deletion) never reaches here and never raises
    ``CurrentLengthUnmeasurableError``.

    The read is split into two steps -- raw bytes, then a separate decode --
    so the two REFUSING situations are distinguished by construction, never
    by inspecting the same caught exception two different ways: a read
    failure (permissions, or any other OS-level error) names the file as
    "cannot be opened at all", and a decode failure names it as "not
    readable as text in the encoding the standard reads". Neither situation
    is coerced into a measured length of zero.

    Args:
        filepath: Path to the file to measure. The caller must have already
            confirmed this path exists.

    Returns:
        The file's current length via the shared ``count_content_lines``
        measurement rule.

    Raises:
        CurrentLengthUnmeasurableError: the file could not be opened at all,
            or its content could not be decoded as UTF-8, the encoding the
            standard reads.
    """
    path = Path(filepath)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CurrentLengthUnmeasurableError(
            f"the length of {filepath!r} could not be established: cannot be opened at all ({exc})"
        ) from exc

    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CurrentLengthUnmeasurableError(
            f"the length of {filepath!r} could not be established: not readable as text in the "
            f"encoding the standard reads ({exc})"
        ) from exc

    return count_content_lines(content)


def _run_git(args: list[str]) -> subprocess.CompletedProcess:
    """Run a git command, capturing decoded output and never raising on a
    non-zero exit — the caller inspects ``.returncode``.

    Args:
        args: Arguments to pass to git (without the leading "git").

    Returns:
        The completed process.

    Raises:
        PreviousLengthSourceError: git itself could not be invoked (missing
            executable, timeout, or another OS-level failure).
    """
    try:
        return subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise PreviousLengthSourceError(
            f"the previous lengths could not be read: git could not be invoked ({exc})"
        ) from exc


def _read_head_blob_bytes(filepath: str) -> bytes:
    """Read the raw bytes of *filepath* at HEAD, without decoding them.

    Raw bytes are read (rather than text) so the caller controls exactly
    which decode step raises ``UnicodeDecodeError`` — the "uninterpretable"
    situation this record must name distinctly from "unreadable".

    Args:
        filepath: Repository-relative path, already confirmed to exist at
            HEAD by the caller.

    Returns:
        The blob's raw bytes.

    Raises:
        PreviousLengthSourceError: git could not be invoked, or the blob
            read itself failed at the git level.
    """
    try:
        result = subprocess.run(
            ["git", "show", f"HEAD:{filepath}"],
            capture_output=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise PreviousLengthSourceError(
            f"the previous length for {filepath!r} could not be read: "
            f"git could not be invoked ({exc})"
        ) from exc

    if result.returncode != 0:
        stderr_text = result.stderr.decode("utf-8", errors="replace").strip()
        raise PreviousLengthSourceError(
            f"the previous length for {filepath!r} could not be read: {stderr_text}"
        )
    return result.stdout


def resolve_head_covered_paths(checked_extensions: list[str]) -> list[str]:
    """Return every covered-extension path tracked in HEAD's tree.

    This establishes the previous-length SOURCE for the run — repository
    -wide, not per-commit: whether HEAD resolves at all, and whether its
    tree holds any file of a checked kind anywhere. It does not itself
    resolve any single staged file's previous length; that a commit stages
    only newly added covered files against a POPULATED HEAD is a different,
    legitimate state this function does not refuse.

    An unborn HEAD (no commit exists yet) and a resolvable HEAD whose tree
    holds no covered file are BOTH ordinary, COMPLETING empty-history states
    per the 2026-09-01 criteria correction — neither raises here. The caller
    tells emptiness apart from a genuine failure by the return value itself
    (empty list vs. a raised error), decided AT THIS POINT OF RESOLUTION,
    never downstream by re-inspecting collection size elsewhere: only an
    actual git-level failure (the tree could not be listed even though HEAD
    resolved, or git itself could not be invoked) raises.

    Args:
        checked_extensions: Extensions that count as a "covered" file kind
            (e.g. [".py", ".sql"]).

    Returns:
        The list of HEAD-tracked paths whose extension is covered. Empty
        means empty history (unborn HEAD, or a tree with no covered file) —
        a legitimate, completing result, not an error.

    Raises:
        PreviousLengthSourceError: HEAD resolves but its tree could not be
            listed, or git itself could not be invoked.
    """
    head_check = _run_git(["rev-parse", "--verify", "HEAD"])
    if head_check.returncode != 0:
        # Unborn HEAD -- no commit exists yet. This is the EMPTY-HISTORY
        # completing case, not a source failure: refusing it would deadlock
        # the very first commit of every fresh consumer-project install.
        return []

    tree_listing = _run_git(["ls-tree", "-r", "--name-only", "HEAD"])
    if tree_listing.returncode != 0:
        raise PreviousLengthSourceError(
            "the previous lengths could not be read: HEAD's tree could not "
            f"be listed ({tree_listing.stderr.strip()})"
        )

    extensions = {ext.lower() for ext in checked_extensions}
    return [
        path
        for path in tree_listing.stdout.splitlines()
        if path.strip() and Path(path).suffix.lower() in extensions
    ]


def get_previous_length(filepath: str) -> int | None:
    """Return the line count *filepath* had at HEAD, or None if it is new.

    Args:
        filepath: Repository-relative path of a staged, covered file.

    Returns:
        The previous length, or None when the file has no HEAD blob (it did
        not exist before this commit) — never coerced to zero.

    Raises:
        PreviousLengthSourceError: the HEAD blob exists but its content
            cannot be decoded as UTF-8, the encoding the standard reads.
    """
    existence = _run_git(["cat-file", "-e", f"HEAD:{filepath}"])
    if existence.returncode != 0:
        return None

    raw = _read_head_blob_bytes(filepath)
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PreviousLengthSourceError(
            f"the previous length for {filepath!r} could not be interpreted: "
            f"HEAD blob is not valid UTF-8 ({exc})"
        ) from exc

    return count_content_lines(content)


def resolve_previous_lengths(paths: list[str]) -> dict[str, int]:
    """Resolve the previous (HEAD) length for every path in *paths* that has one.

    Callers must first establish the previous-length SOURCE via
    ``resolve_head_covered_paths`` (repository-wide) — this function only
    performs the PER-FILE lookup and does not itself decide whether an
    empty result means "genuinely nothing to compare" versus "the source is
    empty history"; that classification happens once, at the source, not
    here.

    Args:
        paths: Staged, covered file paths to resolve a previous length for.

    Returns:
        Mapping of path to previous line count, for every path that had a
        HEAD blob. A newly added path (no HEAD blob) is simply absent from
        the result rather than mapped to zero.

    Raises:
        PreviousLengthSourceError: a resolvable HEAD blob cannot be
            interpreted.
    """
    previous_lengths: dict[str, int] = {}
    for path in paths:
        previous = get_previous_length(path)
        if previous is not None:
            previous_lengths[path] = previous
    return previous_lengths


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-01 [python-coder/GE-127b-1 + GE-127b-1-i]: Initial authoring.
  Shared count_content_lines() measurement function, HEAD-blob previous
  -length resolution via `git show HEAD:<path>` (no persisted baseline, no
  new config key — per GE-127b-1's it-po enrichment), and the
  PreviousLengthSourceError floor distinguishing "could not be read" /
  "could not be interpreted" / "holds no covered file whatsoever" per
  GE-127b-1-i, reusing BP-1600a-2-ii's INDETERMINATE vocabulary.
- 2026-09-07 [python-coder/GE-127b-1-i correction]: Narrowed the refusing
  set from three situations to two per the 2026-09-01 criteria correction.
  resolve_head_covered_paths() no longer raises for an unborn HEAD or a
  HEAD tree holding no covered file — both now return an empty list, a
  legitimate completing result (empty history), because refusing either
  deadlocks the first commit of every fresh consumer-project install.
  Added EMPTY_HISTORY_REASON as the pinned, shared naming text for that
  completing case, distinct from PreviousLengthSourceError's two remaining
  reasons (unreachable, uninterpretable) by construction. Dropped
  resolve_previous_lengths()'s internal call to resolve_head_covered_paths
  and its now-unused checked_extensions parameter — the source-level
  empty-history decision is made once, by the caller, at the point of
  resolution, never re-derived downstream from a collection's size.
====================================================================
"""
