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

import difflib
import subprocess
from collections.abc import Callable
from pathlib import Path

from _file_size_measure import UnmeasurableContentError, counted_line_keys, extension_of, measure_lines
from _file_size_measure.rule_statement import describe

_SUBPROCESS_TIMEOUT_SECONDS = 15

# A measurement rule: full file text in, line count out. Passed explicitly by
# callers whose notion of "a line that counts" differs from this module's own
# code-oriented default (check_doc_length.py strips YAML frontmatter where
# count_content_lines strips comments and standalone strings). The parameter
# exists so the before/after comparison is ALWAYS made with one rule applied
# twice -- the invariant count_content_lines' docstring describes -- rather
# than by each caller reimplementing the git plumbing around its own counter.
Measure = Callable[[str], int]


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


class AddedLineCountUnavailableError(Exception):
    """Raised for the two REFUSING situations establishing how many measured
    lines a staged change PUT INTO an already-oversized file: the account of
    the change is UNREACHABLE (the previous content at the revision being
    diffed against could not be read, including no previous content existing
    there at all), or it is reached but the CURRENT content is
    UNINTERPRETABLE (it cannot be opened at all, or cannot be decoded as
    UTF-8).

    NEVER raised merely because a change added zero measured lines -- that
    is an ordinary, valid outcome (a pure deletion, or an edit touching only
    unmeasured content), not a failure. GE-127f-2's own Implementation Notes
    forbid a failure to establish this count silently degrading to zero: a
    zero here would be indistinguishable from a genuine zero-lines-added
    result and would let a real growth through, so this is a DISTINCT
    exception type from both ``PreviousLengthSourceError`` and
    ``CurrentLengthUnmeasurableError`` (the two failures this record wraps),
    even though its reason text may quote one of theirs verbatim.

    GE-127f-2-i catches this at both of its raising call sites in
    ``check_file_size.py`` (``_classify_file``'s classification loop in
    ``main()``, and the ``grown_files`` print loop that calls
    ``_print_grown_file``) and REUSES the pinned ``INDETERMINATE`` token and
    exit-2 contract unchanged, per architect-review's ruling -- this
    situation is the opposite shape from GE-127e-3-i's ``DESCRIPTION
    UNAVAILABLE`` (which fires AFTER a verdict is already decided): the
    unavailable count is itself an input the verdict depends on, exactly
    what ``PreviousLengthSourceError`` already models one input earlier in
    this same pipeline. No fourth token is minted; see
    ``check_file_size.py``'s shared ``_report_indeterminate`` printer.

    Attributes:
        reason: Human-readable text naming which of the two situations
            occurred, printed verbatim after ``INDETERMINATE: reason=``.
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


def count_content_lines(content: str, extension: str = ".py") -> int:
    """Count *content*'s lines under the ONE measurement rule, by *extension*'s language.

    This is the SINGLE measurement rule used everywhere a line count is
    needed: the file's current (staged/working) content and its previous
    (HEAD blob) content. Calling this one function twice is how the
    ratchet's before/after comparison is built without risking two
    implementations of the counting rule drifting apart by even one line.

    GE-127d-3 (BrainCandy, 2026-10-16 and 2026-10-20): no comment of any
    style counts, no Python string standing alone as a statement counts,
    blank lines never count (BrainCandy, 2026-10-21), and every line of a
    used string or f-string that holds a token does. The strip is done by a per-language tokenizer in the
    ``_file_size_measure`` sub-package -- never a delimiter regex.

    Args:
        content: The file's full text content.
        extension: The file's extension, dot included; selects the language.
            Defaults to ``".py"``, this module's code-oriented default.

    Returns:
        The measured length: the number of counted physical lines.

    Raises:
        UnmeasurableContentError: no tokenizer exists for *extension*, or
            *content* cannot be read as that language. Callers route this to
            INDETERMINATE; it is never turned into a raw count or a zero.
    """
    return measure_lines(content, extension)


def count_added_measured_lines(previous_content: str, current_content: str, extension: str = ".py") -> int:
    """Count the MEASURED lines a change PUT INTO the file -- gross, never net.

    GROSS, NEVER NET, AND NEVER THE SUBTRACTION ALREADY IN HAND (GE-127f-2's
    own Implementation Notes): this is NEVER
    ``count_content_lines(current_content) - count_content_lines(previous_content)``
    (floored at zero or otherwise). That reading is self-referential -- the
    quantity being constrained appears on both sides -- and collapses back
    to GE-127b's own "did it grow" comparison: a change that replaces N
    measured lines with N different measured lines nets to zero there and
    would wrongly register as having added nothing.

    GE-127d-3-iv: both sides are reduced, by the SAME tokenizer pass that
    produces the measured length, to the ordered list of their COUNTED lines
    (``counted_line_keys`` -- ``len(list) == count_content_lines``), each
    keyed by its text with every comment and standalone string removed and
    trailing whitespace stripped. A line inside a comment or standalone
    string on either side never counts as added, and rewriting a comment
    from one style to another (or a trailing ``// note`` into ``/* note */``
    on a code line) leaves every key unchanged, so it adds nothing.

    The two counted-line lists are then diffed with
    ``difflib.SequenceMatcher`` (the standard library's Ratcliff/Obershelp
    implementation, ``autojunk=False`` so no line is ever silently treated
    as "popular" and excluded from matching regardless of repeat count) and
    every INSERTED line -- the target side of an "insert" or "replace"
    opcode -- is summed; a "delete" or "equal" opcode contributes nothing.
    This is what makes replacing N measured lines with N different measured
    lines correctly count as N added (never zero), while deleting M measured
    lines and adding none counts as exactly 0.

    Args:
        previous_content: The file's full text at its previous revision
            (typically the HEAD blob), BEFORE stripping.
        current_content: The file's full text after the staged change,
            BEFORE stripping.
        extension: The file's extension, dot included; selects the language
            for BOTH sides (a rename that changes it is out of scope).

    Returns:
        The gross count of measured lines the change inserted. Zero is an
        ordinary, valid result (a pure deletion, or a change touching only
        unmeasured content) -- never conflated with a failure to establish
        the count; see ``AddedLineCountUnavailableError`` for the failure
        case, which this function never raises itself.

    Raises:
        UnmeasurableContentError: either side cannot be read as its language;
            ``resolve_added_measured_lines`` converts it.
    """
    previous_lines = counted_line_keys(previous_content, extension)
    current_lines = counted_line_keys(current_content, extension)
    matcher = difflib.SequenceMatcher(a=previous_lines, b=current_lines, autojunk=False)
    return sum(j2 - j1 for tag, _i1, _i2, j1, j2 in matcher.get_opcodes() if tag in ("replace", "insert"))


def describe_measurement_rule() -> str:
    """Describe, from the rule actually in force, what a quoted length counts.

    GENERATED FROM ``count_content_lines`` by probing its behaviour on
    every language's comment forms, on every Python string role and on blank
    lines (``_file_size_measure.rule_statement.describe``) every time this is
    called, never maintained as a separately-written sentence -- the
    GE-127d-2 reproducibility requirement, restated per language by
    GE-127d-5: a hand-written description would pass every check on the day
    it is written and silently drift the moment the rule in force changes.
    ``count_content_lines`` is referenced here as an ordinary, unqualified
    module-global name, so Python resolves it fresh on every call (ordinary
    late binding) -- a rule change that rebinds that name changes what this
    function reports in the very same call that changes the quoted length.

    Returns:
        A one-line description naming what is not counted and what is.
        Suitable after a ``Measures:`` label and, behind the
        ``MEASUREMENT RULE:`` marker, on every published surface.
    """
    return describe(count_content_lines)


def read_current_content(filepath: str) -> str:
    """Read and decode the CURRENT (working-tree) text of *filepath*.

    Factored out of ``measure_current_length`` (GE-127f-2) so a caller
    needing the raw CONTENT -- not just its measured length -- can share the
    exact same read-then-decode failure handling, rather than a second copy
    of it: ``count_added_measured_lines`` needs the current file's text to
    diff against the previous revision's, and must fail the same two ways
    ``measure_current_length`` already does, never a third.

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
    is coerced into an empty or otherwise substitute content.

    Args:
        filepath: Path to the file to read. The caller must have already
            confirmed this path exists.

    Returns:
        The file's current, decoded text content.

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
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CurrentLengthUnmeasurableError(
            f"the length of {filepath!r} could not be established: not readable as text in the "
            f"encoding the standard reads ({exc})"
        ) from exc


def measure_current_length(filepath: str) -> int:
    """Measure the CURRENT (working-tree) line count of *filepath*.

    Delegates the read-and-decode step to ``read_current_content``, then
    applies the shared ``count_content_lines`` measurement rule -- see that
    function for why a discarded region never becomes a measured line.

    Args:
        filepath: Path to the file to measure. The caller must have already
            confirmed this path exists.

    Returns:
        The file's current length via the shared ``count_content_lines``
        measurement rule, applied with the file's own language (its
        extension) -- the same selection the previous-length lookup makes.

    Raises:
        CurrentLengthUnmeasurableError: the file could not be opened at all,
            its content could not be decoded as UTF-8, the encoding the
            standard reads, or (GE-127d-3-ii) its content could not be read
            as its language. Never a zero and never a raw count.
    """
    content = read_current_content(filepath)
    try:
        return count_content_lines(content, extension_of(filepath))
    except UnmeasurableContentError as exc:
        raise CurrentLengthUnmeasurableError(
            f"the length of {filepath!r} could not be established: {exc.reason}"
        ) from exc


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


def resolve_head_matching_paths(is_covered: Callable[[str], bool]) -> list[str]:
    """Return every HEAD-tracked path *is_covered* accepts.

    The predicate form of ``resolve_head_covered_paths`` below, for callers
    whose covered set is not expressible as a set of file extensions --
    check_doc_length.py's is a path prefix plus an exclusion list. Both
    functions classify the previous-length SOURCE identically; see
    ``resolve_head_covered_paths`` for the full contract, which this function
    implements and that one now delegates to.

    Args:
        is_covered: Predicate deciding whether a HEAD-tracked path counts as
            a covered file for the calling gate.

    Returns:
        The list of HEAD-tracked paths the predicate accepted. Empty means
        empty history — a legitimate, completing result, not an error.

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

    return [path for path in tree_listing.stdout.splitlines() if path.strip() and is_covered(path)]


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
    extensions = {ext.lower() for ext in checked_extensions}
    return resolve_head_matching_paths(lambda path: Path(path).suffix.lower() in extensions)


def get_previous_content(filepath: str, revision: str = "HEAD") -> str | None:
    """Return *filepath*'s decoded text at *revision*, or None if absent there.

    Factored out of ``get_previous_length`` (GE-127f-2) so a caller needing
    the previous revision's raw CONTENT -- not just its measured length --
    can share the exact same existence check and decode-failure handling:
    ``resolve_added_measured_lines`` needs the previous blob's text to diff
    against the current content, denominated in the file's own unit, and
    must resolve "absent" and "uninterpretable" exactly as
    ``get_previous_length`` already does, never by a second, parallel git
    lookup.

    Args:
        filepath: Repository-relative path of a staged, covered file.
        revision: The revision to look the file up at. Defaults to
            ``"HEAD"`` — the ordinary, non-merge case. During a merge, callers
            pass each parent revision in turn.

    Returns:
        The previous content, or None when the file has no blob at
        *revision* (it did not exist there) — never coerced to an empty
        string standing in for "no previous content".

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
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PreviousLengthSourceError(
            f"the previous length for {filepath!r} at {revision!r} could not "
            f"be interpreted: blob is not valid UTF-8 ({exc})"
        ) from exc


def measure_previous(content: str, filepath: str, revision: str, measure: Measure | None = None) -> int:
    """Measure a previous version's *content* by the rule in force now.

    ONE MEASURE ON BOTH SIDES (GE-127d-3-iii): with no *measure* given, the
    previous content is measured by ``count_content_lines`` with the file's
    own extension -- the very selection ``measure_current_length`` makes for
    the staged content -- resolved as a module global at call time.

    Args:
        content: The previous version's decoded text.
        filepath: Repository-relative path (selects the language).
        revision: The revision the content came from (for the reason text).
        measure: Optional caller-owned rule (check_doc_length passes its own).

    Returns:
        The previous length.

    Raises:
        PreviousLengthSourceError: the content could not be read as its
            language ("could not be interpreted", GE-127b-1-i's vocabulary).
    """
    try:
        if measure is None:
            return count_content_lines(content, extension_of(filepath))
        return measure(content)
    except UnmeasurableContentError as exc:
        raise PreviousLengthSourceError(
            f"the previous length for {filepath!r} at {revision!r} could not "
            f"be interpreted: {exc.reason}"
        ) from exc


def get_previous_length(
    filepath: str, revision: str = "HEAD", measure: Measure | None = None
) -> int | None:
    """Return the line count *filepath* had at *revision*, or None if absent there.

    Delegates the existence check and content read to ``get_previous_content``,
    then applies *measure* -- see that function for the "absent vs.
    uninterpretable" distinction this one inherits unchanged.

    Args:
        filepath: Repository-relative path of a staged, covered file.
        revision: The revision to look the file up at. Defaults to
            ``"HEAD"`` — the ordinary, non-merge case. During a merge, callers
            pass each parent revision in turn (see ``resolve_previous_lengths``).
        measure: The counting rule to apply to the blob's decoded text.
            Defaults to None, meaning the path-aware code measure
            (``count_content_lines`` with the file's own extension). A caller
            passing its own rule here MUST apply that same rule to the
            file's current content, or the ratchet compares two different
            measurements and reports growth that did not happen.

    Returns:
        The previous length, or None when the file has no blob at *revision*
        (it did not exist there) — never coerced to zero.

    Raises:
        PreviousLengthSourceError: the blob exists at *revision* but its
            content cannot be decoded as UTF-8, the encoding the standard
            reads, or cannot be read as its language.
    """
    content = get_previous_content(filepath, revision)
    if content is None:
        return None
    return measure_previous(content, filepath, revision, measure)


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
    paths: list[str],
    parent_revisions: list[str] | None = None,
    measure: Measure | None = None,
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
        measure: The counting rule applied to every parent blob, forwarded
            unchanged to ``get_previous_length``. Defaults to None -- the
            path-aware code measure; see that function's ``measure`` note
            for the obligation a caller takes on by overriding it.

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
            if (length := get_previous_length(path, revision, measure)) is not None
        ]
        if lengths:
            previous_lengths[path] = max(lengths)
    return previous_lengths


def resolve_added_measured_lines(filepath: str, parent_revisions: list[str] | None = None) -> int:
    """Resolve the gross measured lines a staged change put into *filepath*.

    A staged DELETION -- *filepath* no longer exists on disk -- is
    deliberately NOT one of this function's two REFUSING situations, for
    exactly the reason ``count_lines()`` (check_file_size.py) already
    documents for its own, analogous check: a change that deletes a file
    has added nothing to it, by construction, so 0 here is a KNOWN,
    meaningful answer, never a degraded stand-in for a count that could not
    be established. This is checked FIRST, before any attempt to read the
    current content, so a deletion never reaches ``read_current_content``
    and never raises ``AddedLineCountUnavailableError`` -- BUG FIX
    (2026-09-29): before this check existed, a staged deletion of an
    already-oversized covered file crashed here with
    ``AddedLineCountUnavailableError: ... cannot be opened at all
    ([Errno 2] No such file or directory ...)``, because ``_classify_file``
    calls this function for any file whose HEAD length exceeded its limit,
    regardless of whether the file still exists in the working tree. Do NOT
    widen the ``except`` blocks below to paper over that instead -- a
    genuine read/decode failure on a file that DOES exist must still raise;
    only this narrow, explicit existence check on a nonexistent path is
    exempt, mirroring ``count_lines()``'s own scope boundary exactly rather
    than inventing a second one.

    COST BUDGET (GE-127f-2's own Implementation Notes): callers invoke this
    ONLY for a file already judged to stand above its permitted length --
    a commit that refuses nothing must do no added-line work at all, and
    this function is never called from anywhere else.

    During an ordinary commit *parent_revisions* is just ``["HEAD"]`` and
    this reduces to a single before/after diff via
    ``count_added_measured_lines``. During a merge it mirrors
    ``resolve_previous_lengths``' own MOST-PERMISSIVE-across-parents
    reasoning (see this module's MERGE COMMITS docstring section), but
    inverted: the change is responsible only for what it added BEYOND the
    MOST GENEROUS parent, so this resolves the gross added count against
    EVERY named parent that has the file and returns the MINIMUM. A change
    that merely adopts one parent's already-vetted content verbatim diffs
    to zero against THAT parent and is correctly read as having added
    nothing overall, even though it may differ substantially from a less
    -grown parent.

    Args:
        filepath: Staged, covered file path, already judged to stand above
            its permitted length.
        parent_revisions: Revision specs for every parent of the commit in
            progress, HEAD first (see ``resolve_parent_revisions``).
            Defaults to ``["HEAD"]`` when omitted, matching the ordinary,
            non-merge case.

    Returns:
        0 immediately when *filepath* does not exist on disk (a staged
        deletion) -- a change that deletes a file added nothing to it.
        Otherwise, the minimum gross count of measured lines the change
        inserted, across every named parent that has the file.

    Raises:
        AddedLineCountUnavailableError: the current content cannot be
            opened or decoded, a named parent's previous content could not
            be read, or NONE of the named parents has the file at all (so
            there is nothing to diff against). Left UNCAUGHT here by design
            — this function itself stays pure; GE-127f-2-i's floor catches
            it at both call sites in check_file_size.py and reuses the
            pinned INDETERMINATE token (see this exception's own docstring).
            Never raised for a staged deletion; see above.
    """
    if not Path(filepath).exists():
        return 0

    revisions = parent_revisions if parent_revisions is not None else ["HEAD"]

    try:
        current_content = read_current_content(filepath)
    except CurrentLengthUnmeasurableError as exc:
        raise AddedLineCountUnavailableError(
            f"the measured lines added to {filepath!r} could not be established: "
            f"the current content is uninterpretable ({exc.reason})"
        ) from exc

    added_counts: list[int] = []
    for revision in revisions:
        try:
            previous_content = get_previous_content(filepath, revision)
        except PreviousLengthSourceError as exc:
            raise AddedLineCountUnavailableError(
                f"the measured lines added to {filepath!r} could not be established: "
                f"the previous content at {revision!r} is unreachable ({exc.reason})"
            ) from exc
        if previous_content is None:
            continue
        try:
            added_counts.append(count_added_measured_lines(previous_content, current_content, extension_of(filepath)))
        except UnmeasurableContentError as exc:
            raise AddedLineCountUnavailableError(
                f"the measured lines added to {filepath!r} could not be established: {exc.reason}"
            ) from exc

    if not added_counts:
        raise AddedLineCountUnavailableError(
            f"the measured lines added to {filepath!r} could not be established: "
            f"none of {revisions!r} has previous content to compare against"
        )

    return min(added_counts)


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-29 [python-coder/GE-127f-2-i]: This module's own code is
  UNCHANGED by this ticket -- `AddedLineCountUnavailableError` and
  `resolve_added_measured_lines` were already correct and already raised
  for exactly the two situations this ticket's floor now catches. Updated
  `AddedLineCountUnavailableError`'s and `resolve_added_measured_lines`'s
  own docstrings, which previously stated (accurately, at the time of
  ticket 07) that the exception would be "deliberately left UNCAUGHT" and
  that a future ticket would print "its own named refusal token, distinct
  from INDETERMINATE" -- architect-review ruled the opposite on this
  ticket: REUSE the pinned `INDETERMINATE` token and exit 2 unchanged,
  since the unavailable count here is itself an input the verdict depends
  on (the same shape `PreviousLengthSourceError` already models one input
  earlier in this pipeline), not a post-verdict description failure like
  GE-127e-3-i's distinctly-named `DESCRIPTION UNAVAILABLE`. See
  check_file_size.py's own DECISION HISTORY entry for the two catch sites
  and the shared `_report_indeterminate` printer.
- 2026-09-29 [python-coder/GE-127f-2 bug fix]: `resolve_added_measured_lines`
  crashed the whole gate on a staged DELETION of an already-oversized
  covered file -- `_classify_file` calls it for any file whose HEAD length
  exceeded its limit regardless of whether the path still exists, so
  `read_current_content` hit a nonexistent path and raised
  `CurrentLengthUnmeasurableError` -> `AddedLineCountUnavailableError`,
  which is deliberately UNCAUGHT, crashing the hook. This was not exotic:
  this very ticket's own reconciliation of `test_ge_127b_1.py` (splitting it
  into four files, per the epic's "PROPORTION AND SPLITTING" note) stages
  that exact deletion. Fixed by adding an explicit `Path(filepath).exists()`
  check at the top of `resolve_added_measured_lines`, returning 0
  immediately for a deletion, BEFORE any attempt to read current content --
  mirroring `count_lines()`'s own documented scope boundary (a staged
  deletion is "deliberately NOT one of the two unmeasurable situations")
  rather than inventing a second one. This is not a silent-zero degradation:
  a deletion has added nothing to the file, by construction, so 0 is a
  KNOWN, correct answer, not a stand-in for a count that could not be
  established -- the distinction `AddedLineCountUnavailableError`'s own
  docstring already draws. The `except` blocks below this check are
  UNCHANGED and still raise for a genuine read/decode failure on a path
  that DOES exist; only the narrow, explicit nonexistent-path case is
  exempt. DECIDED, NOT DUPLICATED: the check lives here, in the one shared
  function both `_classify_file` and `_print_grown_file` call, rather than
  also being added as a second, parallel existence check in `_classify_file`
  -- a deleted, previously-oversized file now resolves `added=0`,
  `required=previous`, and `lines(0) > required` is always false, so
  `_classify_file` naturally returns "pass" for it without needing to know
  about deletions itself, and `_print_grown_file` (which also calls this
  function, per pr-reviewer's flagged double-call) is correspondingly safe
  by construction, without being reachable for a deleted path in the first
  place (a deleted file can never be classified "grew"). Verified end-to-end
  with a real staged deletion of a covered oversized file in a throwaway
  git repo, not just a unit test; see this ticket's sign-off comment for the
  transcript.
- 2026-09-28 [python-coder/GE-127f-2]: Added the GROSS added-line count this
  record's own Gherkin requires: what a change PUT INTO an already-oversized
  file, never the net (current-minus-previous) growth `_classify_file`
  already computed, which is self-referential and collapses back to
  GE-127b's own "did it grow" question. Factored the stripping step out of
  count_content_lines() into the new _strip_unmeasured_regions(), so the new
  count_added_measured_lines() (previous content and current content, both
  stripped, diffed via difflib.SequenceMatcher, every inserted line summed)
  shares the identical stripping rule rather than a second, independently
  -written line-classifier -- the two counting rules can never drift apart.
  Factored measure_current_length()'s read-then-decode into the new
  read_current_content(), and get_previous_length()'s existence-check-then-
  read into the new get_previous_content(), so the new
  resolve_added_measured_lines() (per-file: current content once, previous
  content per named parent, MINIMUM gross count across parents -- the
  inverse of resolve_previous_lengths()' MAXIMUM, for the same "most
  permissive across parents" reasoning during a merge) can reuse both
  exactly, never a parallel git-plumbing copy. Neither get_previous_length()
  nor measure_current_length() changed behaviour or signature -- both are
  now two-line delegations to the newly-exposed functions, verified
  byte-for-byte equivalent before this change (their own existing GE-127b-1/
  -1-i/GE-127a-1-i descriptor sets stayed green, unchanged, throughout).
  Added AddedLineCountUnavailableError -- a DISTINCT exception from
  PreviousLengthSourceError and CurrentLengthUnmeasurableError, per this
  record's own "never degrade to zero" note -- raised by
  resolve_added_measured_lines() and deliberately left UNCAUGHT at its
  check_file_size.py call sites; GE-127f-2-i (ticket 08, not yet authored)
  owns catching it and printing its own named refusal token. See
  check_file_size.py's own DECISION HISTORY entry for how the new
  comparison (`current_length > previous_length - added`) reconciles
  GE-127b-1's boundary descriptor and wires into the real refusal path
  without changing _classify_file()'s, _print_grown_file()'s, or
  _resolve_ratchet_or_indeterminate()'s call signatures or return shapes --
  several test/fixture modules in this same suite (_ge_127a_1_ordinary_
  commit_fixture.py's string-replacement mutation targets,
  _ge_127e_3_i_fixture.py's disposable main() override) depend on those
  exact shapes verbatim and are test/fixture files this record must not
  edit.
- 2026-09-23 [python-coder/GE-127d-2 rework, M-1]: pr-reviewer found the
  trailing `\n?` on all three discard regexes matches a bare LF only, so a
  CRLF-terminated file's discarded region leaves its own `\r` behind as a
  phantom entry under `str.splitlines()` -- the same overcount this record
  exists to fix, surviving for CRLF. Changed `\n?` to `\r?\n?` on all three
  patterns (`_TRIPLE_DOUBLE_QUOTE_RE`, `_TRIPLE_SINGLE_QUOTE_RE`,
  `_BLOCK_COMMENT_RE`). Verified this does not perturb any LF-input result
  before applying it: `\r?` matches zero characters when no `\r` is present,
  so on pure-LF content the substitution result is byte-for-byte identical
  to before (checked directly against representative probes, and by
  re-running the full GE-127d-2 (9) and GE-127b-1/-1-i (18) descriptor sets,
  27/27 green, unchanged from immediately before this one-token edit).
  `.gitattributes`'s `* text=auto eol=lf` still means CRLF is not expected to
  reach this function in practice; this closes the gap for the case where it
  does.
- 2026-10-20 15:19 [python-coder/GE-127d-3]: Replaced the delimiter-regex measure
  (_strip_unmeasured_regions and its three regexes) with a per-language
  tokenizer in the new _file_size_measure/ sub-package: no comment of any
  style and no Python string standing alone as a statement counts, blank lines
  outside them do, used strings and f-strings do. count_content_lines and
  count_added_measured_lines gained a trailing ``extension`` parameter
  (default ".py"); measure_current_length, get_previous_length (via the new
  measure_previous), resolve_previous_lengths (default measure now None = the
  path-aware code measure, one selection on both sides, MERGE_HEAD parents
  included) and resolve_added_measured_lines pass the file's own extension.
  A tokenizer failure (UnmeasurableContentError) is routed to the existing
  carriers -- CurrentLengthUnmeasurableError, PreviousLengthSourceError
  ("could not be interpreted") and AddedLineCountUnavailableError -- so it is
  INDETERMINATE and never a raw count or zero. describe_measurement_rule()
  delegates to rule_statement.describe(count_content_lines) and still resolves
  that name at call time. No second measure was added, and the plumbing
  check_complexity / _complexity_ratchet / _ac_governance_baseline /
  _doc_length_ratchet use keeps its signatures and return shapes (doc-length
  still passes its own measure positionally). (#EPIC-FilesStayWorkable/GE-127d-3)
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
- 2026-09-14 [doc-length ratchet]: Made this module's counting rule and
  covered-set rule pluggable so check_doc_length.py can reuse the ratchet's
  git plumbing (merge-parent resolution, the two-situation INDETERMINATE
  floor, empty-history classification) instead of growing a second, parallel
  copy of it. Added the `Measure` alias and an optional `measure` parameter
  to get_previous_length() and resolve_previous_lengths(), both defaulting to
  count_content_lines so every existing call site is byte-for-byte unchanged;
  added resolve_head_matching_paths(predicate) and reduced
  resolve_head_covered_paths() to a two-line delegation to it, since a docs/
  prefix plus an exclusion list is not expressible as a set of extensions.
  No behaviour change for check_file_size.py — the sole in-tree caller of
  either generalised function passes neither new argument.
- 2026-09-22 [python-coder/GE-127d-2]: Added describe_measurement_rule(),
  GENERATED from count_content_lines() by empirically probing its behaviour
  (_probe_discarded_categories(), against single-category synthetic probes)
  rather than maintained as a separately-written sentence -- the AC's own
  reproducibility requirement and its NAMED MUTATION 2 defence (a hand
  -written published statement must diverge from the quoted length the
  moment the rule changes; a generated one cannot). count_content_lines is
  referenced as an ordinary, unqualified module-global name inside
  describe_measurement_rule() and _probe_discarded_categories() is always
  called with it resolved AT CALL TIME, so a later rebinding of that name
  (e.g. a test's disposable override appended to this file) changes what
  is described in the same call that changes what is measured -- ordinary
  Python late binding, never a default-argument or import-time capture.
  check_file_size.py's _print_too_large_file() prints the result on a new
  "Measures:" line and replaces the prior undifferentiated dividing advice
  with two sentences that distinguish the action that reduces the quoted
  length (deleting blank lines / '#' comments) from the one that cannot
  (deleting a triple-quoted or block-comment region, already discarded).
- 2026-09-22 [python-coder/GE-127d-2 correction]: Fixed a universal off-by
  -one OVERCOUNT in count_content_lines() that GE-127d-2's own reproducibility
  descriptors surfaced: all three patterns (_TRIPLE_DOUBLE_QUOTE_RE,
  _TRIPLE_SINGLE_QUOTE_RE, _BLOCK_COMMENT_RE) stripped a matched region via
  re.sub() but never consumed the newline immediately following its closing
  delimiter, so every discarded region left a phantom blank line behind --
  overcounting by exactly one line PER DISCARDED REGION, regardless of that
  region's position in the file. This was first misdiagnosed (by an earlier
  attempt at this same record) as a position-0 edge case affecting only a
  file's leading docstring; a direct probe disproved that and showed the
  defect is universal and scales with the number of discarded regions, not
  their position (1 region -> +3 measured lines of overcount across a set of
  probes; 5 -> +7; 10 -> +12; 25 -> +27 -- the constant +2 offset is probe
  -harness overhead, not evidence of a floor). check_file_size.py's own
  previously-reported count of 293 was therefore roughly 16 too high (one per
  triple-quote pair in that file). Fixed by appending an optional trailing
  `\n?` to all three patterns, so a discarded region now contributes zero
  lines, trailing newline included -- matching the rule as PUBLISHED by
  describe_measurement_rule() above ("discards content inside ...") rather
  than the off-by-one rule the code had actually been running. Every Python
  file's counted length becomes smaller as a result (the gate only relaxes;
  nothing newly refused) and GE-127b-1's ratchet is unaffected in comparison
  outcome, because get_previous_length() recomputes the HEAD blob's length
  with this SAME corrected function, so both sides of every before/after
  comparison shift down together.
====================================================================
"""
