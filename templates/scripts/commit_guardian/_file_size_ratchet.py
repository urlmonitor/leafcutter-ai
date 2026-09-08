"""
MODULE: commit_guardian._file_size_ratchet
GOAL: Resolve each staged covered file's previous length via git, using the
    SAME measurement function used on the file's current content, and
    classify the run's previous-length SOURCE into exactly one of three
    outcomes: available (HEAD holds at least one covered file, so a
    per-file lookup proceeds), empty history (HEAD resolves to no commit
    yet, or its tree holds no covered file at all — an ordinary day-one
    state that must COMPLETE, never refuse), or indeterminate (the source
    could not be reached at all, or a resolvable blob could not be
    interpreted — the only two situations that refuse). This stops a
    broken git lookup from silently masquerading as "nothing to compare"
    (the fail-open shape KI-CG-034, KI-CG-012 and KI-CG-018 all shipped on
    this component before) WITHOUT reinstating the opposite defect: an
    empty-but-genuine history deadlocking every fresh consumer-project
    install, since the first commit that would populate it is the one a
    refusal would be blocking on. Per-file resolution consults HEAD first,
    always; only when HEAD holds nothing for a path AND a merge is
    genuinely in progress (MERGE_HEAD resolves) is the merge's other
    parent also consulted (GE-127b-2), so a file inherited unchanged from
    the incoming branch is judged against the copy it arrived with rather
    than treated as newly authored.
BUSINESS CONTEXT: Backs the GE-127b-1 / GE-127b-1-i ratchet: an already
    -oversized file may be worked on, but a change that leaves it longer
    than it stood before is refused. GE-127b-2 widens WHERE "before" is
    looked up during a merge, without changing WHETHER the ratchet applies
    or HOW a length is measured — see
    KI-CG-20260908-ratchet-reads-pre-merge-head in
    docs/known-issues/commit-guardian.md. See
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


def _read_ref_blob_bytes(ref: str, filepath: str) -> bytes:
    """Read the raw bytes of *filepath* at *ref*, without decoding them.

    Raw bytes are read (rather than text) so the caller controls exactly
    which decode step raises ``UnicodeDecodeError``. *ref* is HEAD for the
    ordinary lookup, or a MERGE_HEAD parent commit SHA for the merge-aware
    lookup added by GE-127b-2 — both are valid left-hand sides of git's
    `<rev>:<path>` blob syntax.

    Args:
        ref: A ref or literal commit SHA, already confirmed to hold a blob
            for *filepath* by the caller.
        filepath: Repository-relative path, already confirmed to exist at
            *ref* by the caller.

    Returns:
        The blob's raw bytes.

    Raises:
        PreviousLengthSourceError: git could not be invoked, or the blob
            read itself failed at the git level.
    """
    try:
        result = subprocess.run(
            ["git", "show", f"{ref}:{filepath}"],
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


def _merge_in_progress() -> bool:
    """Return whether a merge is currently in progress.

    Detected EXCLUSIVELY from git state, per GE-127b-2's it_requirements —
    never from the commit message or an environment flag, either of which
    can be rewritten or set by something unrelated. True exactly when the
    pseudo-ref MERGE_HEAD resolves.

    Returns:
        True when `git rev-parse --verify MERGE_HEAD` succeeds, False
        otherwise (the ordinary, overwhelmingly common case — not a
        failure).

    Raises:
        PreviousLengthSourceError: git itself could not be invoked.
    """
    result = _run_git(["rev-parse", "--verify", "MERGE_HEAD"])
    return result.returncode == 0


def _merge_parent_shas() -> list[str]:
    """Return every commit SHA on the MERGE_HEAD pseudo-ref, one per line.

    An octopus merge records more than one OTHER parent, one SHA per line,
    in the MERGE_HEAD file itself. `git rev-parse --verify MERGE_HEAD` only
    ever resolves and prints the FIRST line for a multi-line MERGE_HEAD, so
    it cannot be reused here without silently dropping every parent past
    the first — this resolves MERGE_HEAD's own path via git and reads the
    pseudo-ref file's lines directly instead.

    Returns:
        The parent SHAs found on MERGE_HEAD, in file order. Never empty
        when called only after ``_merge_in_progress`` returned True for the
        same repository state.

    Raises:
        PreviousLengthSourceError: MERGE_HEAD's path could not be resolved,
            or the pseudo-ref file could not be opened.
    """
    path_result = _run_git(["rev-parse", "--git-path", "MERGE_HEAD"])
    if path_result.returncode != 0:
        raise PreviousLengthSourceError(
            "the merge parents could not be read: MERGE_HEAD's path could "
            f"not be resolved ({path_result.stderr.strip()})"
        )

    merge_head_path = Path(path_result.stdout.strip())
    try:
        content = merge_head_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PreviousLengthSourceError(
            f"the merge parents could not be read: MERGE_HEAD could not be opened ({exc})"
        ) from exc

    return [line.strip() for line in content.splitlines() if line.strip()]


def _resolve_length_at_ref(ref: str, filepath: str) -> int | None:
    """Return *filepath*'s line count at *ref*, or None if *ref* has no blob for it.

    The SAME resolution shape ``get_previous_length`` has always used for
    HEAD, generalized to be reused against a MERGE_HEAD parent SHA too:
    existence is checked first via `cat-file -e`, so a genuinely absent
    blob returns None rather than raising — a file present on neither
    parent stays genuinely new, in a merge exactly as outside one.

    Args:
        ref: A ref (e.g. "HEAD") or a literal commit SHA to look up.
        filepath: Repository-relative path.

    Returns:
        The measured length via ``count_content_lines``, or None when *ref*
        holds no blob for *filepath*.

    Raises:
        PreviousLengthSourceError: *ref* holds a blob for *filepath* but it
            cannot be decoded as UTF-8, the encoding the standard reads.
    """
    existence = _run_git(["cat-file", "-e", f"{ref}:{filepath}"])
    if existence.returncode != 0:
        return None

    raw = _read_ref_blob_bytes(ref, filepath)
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PreviousLengthSourceError(
            f"the previous length for {filepath!r} could not be interpreted: "
            f"{ref} blob is not valid UTF-8 ({exc})"
        ) from exc

    return count_content_lines(content)


def _covered_paths_in_tree(ref: str, extensions: set[str]) -> list[str]:
    """List every covered-extension path in *ref*'s tree.

    Shared by ``resolve_head_covered_paths`` for both HEAD and, during a
    merge, each of MERGE_HEAD's other parents.

    Args:
        ref: A resolvable ref or literal commit SHA.
        extensions: Lower-cased extensions considered "covered".

    Returns:
        Paths in *ref*'s tree whose extension is in *extensions*.

    Raises:
        PreviousLengthSourceError: *ref* resolves but its tree could not be
            listed, or git itself could not be invoked.
    """
    tree_listing = _run_git(["ls-tree", "-r", "--name-only", ref])
    if tree_listing.returncode != 0:
        raise PreviousLengthSourceError(
            f"the previous lengths could not be read: {ref}'s tree could not "
            f"be listed ({tree_listing.stderr.strip()})"
        )
    return [
        path
        for path in tree_listing.stdout.splitlines()
        if path.strip() and Path(path).suffix.lower() in extensions
    ]


def resolve_head_covered_paths(checked_extensions: list[str]) -> list[str]:
    """Return every covered-extension path tracked in HEAD's tree, widened
    during a merge to MERGE_HEAD's other parent(s) when HEAD's tree alone
    holds none.

    This establishes the previous-length SOURCE for the run — repository
    -wide, not per-commit: whether HEAD resolves at all, and whether its
    tree holds any file of a checked kind anywhere. It does not itself
    resolve any single staged file's previous length.

    GE-127b-2: on an ORDINARY commit (no merge in progress) this function's
    behaviour is unchanged — HEAD's tree is the only source consulted. Only
    when HEAD's tree holds NO covered file AND a merge is genuinely in
    progress (MERGE_HEAD resolves) are MERGE_HEAD's other parent(s) also
    listed and unioned in — otherwise a receiving branch whose tree holds
    no covered file at all would misclassify an incoming, already
    -oversized file as "empty history" and judge it against the absolute
    limit as brand new, the same defect ``get_previous_length`` fixes
    per-file, reachable here through the repository-wide precheck instead.

    An unborn HEAD and a resolvable HEAD whose tree holds no covered file
    anywhere reachable are BOTH ordinary, COMPLETING empty-history states
    per the 2026-09-01 criteria correction — neither raises here; only an
    actual git-level failure raises.

    Args:
        checked_extensions: Extensions that count as a "covered" file kind
            (e.g. [".py", ".sql"]).

    Returns:
        The list of covered paths found at HEAD, or — only when HEAD's
        tree holds none and a merge is in progress — at MERGE_HEAD's other
        parent(s). Empty means genuine empty history — a legitimate,
        completing result, not an error.

    Raises:
        PreviousLengthSourceError: HEAD resolves but its tree could not be
            listed, git itself could not be invoked, or (once a merge is
            detected) MERGE_HEAD's parents or their trees could not be read.
    """
    head_check = _run_git(["rev-parse", "--verify", "HEAD"])
    if head_check.returncode != 0:
        # Unborn HEAD -- no commit exists yet. This is the EMPTY-HISTORY
        # completing case, not a source failure: refusing it would deadlock
        # the very first commit of every fresh consumer-project install.
        return []

    extensions = {ext.lower() for ext in checked_extensions}
    head_paths = _covered_paths_in_tree("HEAD", extensions)
    if head_paths:
        return head_paths

    if not _merge_in_progress():
        return []

    merge_paths: list[str] = []
    for sha in _merge_parent_shas():
        merge_paths.extend(_covered_paths_in_tree(sha, extensions))
    return merge_paths


def get_previous_length(filepath: str) -> int | None:
    """Return *filepath*'s previous line count, or None if it is genuinely new.

    HEAD is consulted first, exactly as before GE-127b-2: if HEAD holds a
    blob for *filepath*, that is the previous length and nothing else is
    consulted — a file present on both parents of an in-progress merge is
    judged against the receiving branch's (HEAD's) copy, never the
    incoming one. This is the entire non-merge behaviour, unchanged.

    Only when HEAD holds NO blob for *filepath*, AND a merge is genuinely in
    progress (MERGE_HEAD resolves), is the merge's other parent consulted:
    a file inherited unchanged from the incoming branch is judged against
    the copy it arrived with instead of being treated as newly authored —
    fixing KI-CG-20260908-ratchet-reads-pre-merge-head, where HEAD mid
    -merge is the receiving branch's PRE-merge tip. An octopus merge's
    several other parents are each checked; when more than one holds the
    path, the LONGEST of those lengths is used, since judging against the
    shortest would manufacture growth the merge did not author. A file
    present on NEITHER parent remains genuinely new — the None return is
    preserved verbatim; this function never exempts a merge wholesale.

    Args:
        filepath: Repository-relative path of a staged, covered file.

    Returns:
        The previous length, or None when the file has no blob at HEAD nor,
        during a merge, at any other parent — never coerced to zero.

    Raises:
        PreviousLengthSourceError: a resolvable blob (HEAD's, or a
            MERGE_HEAD parent's) exists but its content cannot be decoded
            as UTF-8, the encoding the standard reads; or MERGE_HEAD's own
            parents could not be read once a merge was detected.
    """
    previous = _resolve_length_at_ref("HEAD", filepath)
    if previous is not None:
        return previous

    if not _merge_in_progress():
        return None

    merge_lengths = [
        length
        for length in (_resolve_length_at_ref(sha, filepath) for sha in _merge_parent_shas())
        if length is not None
    ]
    if not merge_lengths:
        return None

    return max(merge_lengths)


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
        Mapping of path to previous line count, for every path
        ``get_previous_length`` resolved one for (HEAD, or — mid-merge and
        only when HEAD held nothing — MERGE_HEAD's other parent; see
        GE-127b-2). A newly added path with no blob on any of those is
        simply absent from the result rather than mapped to zero.

    Raises:
        PreviousLengthSourceError: a resolvable blob cannot be interpreted,
            or, once a merge is detected, its other parent(s) cannot be
            read.
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
- 2026-09-08 [python-coder/GE-127b-2]: Fixed
  KI-CG-20260908-ratchet-reads-pre-merge-head: during a merge, HEAD is the
  receiving branch's PRE-merge tip, so a file long-standing on the branch
  being merged IN but never held by the branch being merged INTO resolved
  to no previous length and was refused as brand new. get_previous_length()
  now consults HEAD first, unchanged; only when HEAD holds no blob for the
  path AND a merge is genuinely in progress (MERGE_HEAD resolves, detected
  via `git rev-parse --verify MERGE_HEAD` and never from the commit message
  or an environment flag) does it also consult MERGE_HEAD's other
  parent(s), taking the longest length when an octopus merge holds more
  than one. A file present on NEITHER parent is still genuinely new and is
  still refused; a merge that itself grows an already-oversized file is
  still caught, because HEAD (when it holds a blob) always wins and the
  comparison itself is unchanged — only WHERE the previous length may be
  found was widened. Renamed the former HEAD-only _read_head_blob_bytes to
  _read_ref_blob_bytes(ref, filepath) and added _merge_in_progress(),
  _merge_parent_shas(), and _resolve_length_at_ref(ref, filepath) as the
  shared per-ref lookup get_previous_length now calls twice (HEAD, then
  each MERGE_HEAD parent) rather than once. Also widened
  resolve_head_covered_paths(): a receiving branch whose tree holds NO
  covered file at all (not just none for one path) previously short
  -circuited the whole run to EMPTY HISTORY, which -- mid-merge -- let an
  incoming oversized file fall through to the absolute-limit branch by the
  same mechanism at the repository-wide precheck instead of the per-file
  lookup. It now falls back to MERGE_HEAD's other parent(s)' trees (via the
  new shared _covered_paths_in_tree(ref, extensions)) only when HEAD's own
  tree is covered-file-empty AND a merge is in progress; the ordinary path
  (HEAD's tree non-empty, or no merge in progress) is unchanged.
  (#TICKETLESS reason=ac-only-direct-fix-dispatch-ge127b2)
====================================================================
"""
