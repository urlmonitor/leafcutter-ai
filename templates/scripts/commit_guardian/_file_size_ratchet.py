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

    MERGE COMMITS (KI-CG-20260908-file-size-ratchet-refuses-merge-commits):
    the ratchet's previous-length lookup originally read HEAD alone. During
    an ordinary `git merge origin/main`, HEAD names only the branch being
    merged INTO — the other parent (`MERGE_HEAD`) can already carry a longer
    length for the very same already-oversized file, grown there in commits
    that were themselves vetted by this same gate on that side. Comparing
    only against HEAD's length made every one of those already-accepted
    growths look like NEW growth the merge author was responsible for,
    refusing nearly every merge that touched a file over its limit. The fix:
    a merge's permitted previous length is the MOST PERMISSIVE (maximum)
    length across every parent — HEAD plus every line of `MERGE_HEAD` — not
    HEAD's alone. Growth beyond what EVERY parent already had is the only
    growth a commit is actually responsible for; the same reasoning applies
    to the absolute-limit crossing refusal (a file already over its limit on
    ANY parent was not taken over the limit by this commit). `MERGE_HEAD` is
    located via `git rev-parse --git-path MERGE_HEAD` — which resolves
    correctly inside a linked worktree — and EVERY non-blank line of it is
    read, not just the first: `git rev-parse -q --verify MERGE_HEAD` (the
    naive probe) resolves only the first line and silently drops every
    additional parent of an octopus merge, exactly the mistake
    check_package_surface_declaration.py's docstring documents. An ordinary,
    single-parent commit is unaffected: its parent set is just `["HEAD"]`,
    identical to the pre-fix behaviour. A merge whose parent set or whose
    parents' lengths genuinely cannot be resolved raises
    PreviousLengthSourceError (INDETERMINATE) rather than silently falling
    back to a smaller, wrong baseline — fail CLOSED on ambiguity, per
    GE-127b-1-i's own floor.
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


def _read_blob_bytes(filepath: str, revision: str) -> bytes:
    """Read the raw bytes of *filepath* at *revision*, without decoding them.

    Raw bytes are read (rather than text) so the caller controls exactly
    which decode step raises ``UnicodeDecodeError`` — the "uninterpretable"
    situation this record must name distinctly from "unreadable".

    Args:
        filepath: Repository-relative path, already confirmed to exist at
            *revision* by the caller.
        revision: The revision to read the blob from (``"HEAD"`` for an
            ordinary commit; a parent SHA from ``MERGE_HEAD`` while a merge
            is in progress — see ``merge_parent_revisions``).

    Returns:
        The blob's raw bytes.

    Raises:
        PreviousLengthSourceError: git could not be invoked, or the blob
            read itself failed at the git level.
    """
    try:
        result = subprocess.run(
            ["git", "show", f"{revision}:{filepath}"],
            capture_output=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise PreviousLengthSourceError(
            f"the previous length for {filepath!r} at {revision!r} could not "
            f"be read: git could not be invoked ({exc})"
        ) from exc

    if result.returncode != 0:
        stderr_text = result.stderr.decode("utf-8", errors="replace").strip()
        raise PreviousLengthSourceError(
            f"the previous length for {filepath!r} at {revision!r} could not "
            f"be read: {stderr_text}"
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


def get_previous_length(filepath: str, revision: str = "HEAD") -> int | None:
    """Return the line count *filepath* had at *revision*, or None if absent there.

    Args:
        filepath: Repository-relative path of a staged, covered file.
        revision: The revision to look the file up at. Defaults to
            ``"HEAD"`` — the ordinary, non-merge case. During a merge, callers
            pass each parent revision in turn (see ``resolve_previous_lengths``).

    Returns:
        The previous length, or None when the file has no blob at *revision*
        (it did not exist there) — never coerced to zero.

    Raises:
        PreviousLengthSourceError: the blob exists at *revision* but its
            content cannot be decoded as UTF-8, the encoding the standard
            reads.
    """
    existence = _run_git(["cat-file", "-e", f"{revision}:{filepath}"])
    if existence.returncode != 0:
        return None

    raw = _read_blob_bytes(filepath, revision)
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PreviousLengthSourceError(
            f"the previous length for {filepath!r} at {revision!r} could not "
            f"be interpreted: blob is not valid UTF-8 ({exc})"
        ) from exc

    return count_content_lines(content)


def _merge_head_path() -> Path | None:
    """Return the on-disk path of ``MERGE_HEAD``, or None when not merging.

    Uses ``git rev-parse --git-path MERGE_HEAD`` rather than
    ``git rev-parse -q --verify MERGE_HEAD`` — the latter resolves only the
    FIRST line of the file and silently drops every additional parent of an
    octopus merge (see this module's MERGE COMMITS docstring section, and
    check_package_surface_declaration.py's ``_merge_head_path`` for the
    original reproduction of this exact mistake). ``--git-path`` also
    resolves correctly inside a linked worktree, where ``MERGE_HEAD`` lives
    under the worktree's private git-dir rather than a plain
    ``<repo>/.git/MERGE_HEAD``.

    Returns:
        The absolute path git reports for ``MERGE_HEAD``.

    Raises:
        PreviousLengthSourceError: git itself could not resolve the path —
            an ambiguous, refusing situation, never treated as "not merging".
    """
    result = _run_git(["rev-parse", "--git-path", "MERGE_HEAD"])
    if result.returncode != 0:
        raise PreviousLengthSourceError(
            "the previous lengths could not be read: the MERGE_HEAD path "
            f"could not be resolved ({result.stderr.strip()})"
        )
    text = result.stdout.strip()
    if not text:
        raise PreviousLengthSourceError(
            "the previous lengths could not be read: "
            "`git rev-parse --git-path MERGE_HEAD` returned no path"
        )
    path = Path(text)
    return path if path.is_absolute() else Path.cwd() / path


def merge_parent_revisions() -> list[str]:
    """Return every parent SHA a merge in progress names, one per line of MERGE_HEAD.

    ``MERGE_HEAD`` holds one SHA per line: exactly one for an ordinary
    two-parent merge, and one per additional branch for an octopus merge.
    Reading every non-blank line (rather than only the first) is what
    correctly attributes an octopus merge's third and later parents. An
    absent ``MERGE_HEAD`` file means no merge is in progress — a legitimate,
    non-refusing "[]" result, not an error.

    Returns:
        Every non-blank line of ``MERGE_HEAD``, or ``[]`` when no merge is
        in progress.

    Raises:
        PreviousLengthSourceError: git could not resolve the MERGE_HEAD path
            at all, or the file exists but could not be read — a merge is
            known to be in progress but its parent set cannot be
            established, which must refuse rather than silently be treated
            as "not merging".
    """
    path = _merge_head_path()
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PreviousLengthSourceError(
            f"the previous lengths could not be read: MERGE_HEAD exists at "
            f"{path} but could not be read ({exc})"
        ) from exc
    return [line.strip() for line in text.splitlines() if line.strip()]


def resolve_parent_revisions() -> list[str]:
    """Return the revision specs naming every parent of the commit in progress.

    ``["HEAD"]`` for an ordinary commit; ``["HEAD", <merge-head-sha>, ...]``
    while a merge is in progress, one entry per line of ``MERGE_HEAD`` —
    every parent other than the first, including all additional parents of
    an octopus merge.

    Returns:
        The parent revision specs, HEAD first.

    Raises:
        PreviousLengthSourceError: a merge is in progress but its parent set
            cannot be established (see ``merge_parent_revisions``).
    """
    return ["HEAD", *merge_parent_revisions()]


def resolve_previous_lengths(
    paths: list[str], parent_revisions: list[str] | None = None
) -> dict[str, int]:
    """Resolve each path's permitted previous length across every parent.

    Callers must first establish the previous-length SOURCE via
    ``resolve_head_covered_paths`` (repository-wide) — this function only
    performs the PER-FILE lookup and does not itself decide whether an
    empty result means "genuinely nothing to compare" versus "the source is
    empty history"; that classification happens once, at the source, not
    here.

    During an ordinary commit ``parent_revisions`` is just ``["HEAD"]`` and
    this reduces exactly to reading each path's HEAD length. During a merge
    it also includes every ``MERGE_HEAD`` line: the permitted previous
    length for a path is the MOST PERMISSIVE (maximum) length found across
    every parent that has the file — see this module's MERGE COMMITS
    docstring section for why the maximum, rather than HEAD's length alone,
    is the correct baseline. A path absent from every parent is a genuinely
    new file and is simply absent from the result rather than mapped to
    zero.

    Args:
        paths: Staged, covered file paths to resolve a previous length for.
        parent_revisions: Revision specs for every parent of the commit
            being written, HEAD first (see ``resolve_parent_revisions``).
            Defaults to ``["HEAD"]`` when omitted, matching the pre-merge
            -aware behaviour exactly.

    Returns:
        Mapping of path to its permitted previous line count, for every path
        that had a blob in at least one named parent.

    Raises:
        PreviousLengthSourceError: a resolvable blob at some parent cannot
            be interpreted.
    """
    revisions = parent_revisions if parent_revisions is not None else ["HEAD"]
    previous_lengths: dict[str, int] = {}
    for path in paths:
        lengths = [
            length
            for revision in revisions
            if (length := get_previous_length(path, revision)) is not None
        ]
        if lengths:
            previous_lengths[path] = max(lengths)
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
  GE-127b-1-i, reusing BP-100n-4-ii's INDETERMINATE vocabulary.
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
- 2026-09-08 [python-coder/KI-CG-20260908-file-size-ratchet-refuses-merge-commits]:
  Made the ratchet merge-aware. Generalised _read_head_blob_bytes() and
  get_previous_length() to take an explicit `revision` (default "HEAD"),
  added _merge_head_path()/merge_parent_revisions()/resolve_parent_revisions()
  reading MERGE_HEAD via `git rev-parse --git-path MERGE_HEAD` (every
  non-blank line, not just the first, per check_package_surface_declaration
  .py's documented octopus-merge fix), and changed resolve_previous_lengths()
  to accept a `parent_revisions` list and resolve each path's permitted
  previous length as the MAXIMUM found across all of them, not HEAD alone.
  An unresolvable MERGE_HEAD path or an unreadable-but-present MERGE_HEAD
  file now raises PreviousLengthSourceError (INDETERMINATE) rather than
  being silently treated as "not merging" — fail closed on ambiguity.
====================================================================
"""
