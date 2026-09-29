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

    MERGE COMMITS (KI-CG-20260908-file-size-ratchet-refuses-merge-commits):
    judging a merge against HEAD alone refused nearly every ordinary
    `git merge origin/main` that touched an already-oversized file, because
    the other parent's already-accepted growth of that file looked like NEW
    growth the merge author had introduced. The permitted previous length
    during a merge is now the MOST PERMISSIVE length across every parent —
    see _file_size_ratchet.py's own MERGE COMMITS section for the full
    reasoning and the octopus-merge (MERGE_HEAD-reading) detail. An
    ordinary, non-merge commit is judged exactly as before.
ARCHITECTURE: Delegates previous-length resolution and the shared line
    -counting rule to the sibling module _file_size_ratchet.py (see that
    module for the HEAD-blob lookup, the merge-aware parent-revision
    resolution, the two-situation INDETERMINATE fail-closed floor, and why
    no persisted baseline / new config key is used). An empty previous
    -length history (unborn HEAD, or a HEAD tree with no covered file) is a
    legitimate, COMPLETING result named "EMPTY HISTORY" in the run's
    output, never folded into INDETERMINATE.

    SCOPE DECLARATION (GE-127c-1): the set of kinds a run measured, and the
    set of staged kinds it did not, are both derived once from
    CHECKED_EXTENSIONS -- config.py's runtime read of commit_guardian.json's
    file_size.checked_extensions -- via _classify_staged_extensions() and
    printed by _print_scope_declaration(), never restated as a literal list.
    A staged kind outside that scope is named by extension only, never by
    filename, so it can never be mistaken for a file that was measured and
    found within its limit.

    DESCRIPTION UNAVAILABLE (GE-127e-3-i): a file already judged too_large
    /grew for which no per-file description could be produced (content that
    would not parse, no extractor registered for its kind, an extractor
    that located no part, or a part set under-accounting for at least half
    its quoted length) has its refusal block carry a
    ``DESCRIPTION UNAVAILABLE: reason=<text>`` line naming the SPECIFIC
    cause -- reusing _file_size_ratchet.py's INDETERMINATE / EMPTY HISTORY
    ``TOKEN: reason=<text>`` line shape, but a THIRD, distinctly-named
    token, and never their exit status. A failure to DESCRIBE leaves the
    verdict already known (length measured, found over), so it stays inside
    the SAME exit-1 refusal, on stdout -- never exit 2, and never printed at
    all for a file that is not already refused.

Pre-commit hook to block files exceeding line limits.

Line Limits (see commit_guardian.json's file_size section for the
authoritative, runtime-configurable scope and limits):
- Python (.py): 400 lines max
- SQL (.sql): 600 lines max
- JavaScript (.js) / ES module (.mjs): 1000 lines max
- TypeScript (.ts) / TSX (.tsx): 400 lines max
- Shell (.sh): 400 lines max

Exit Codes:
    0 - All files within limits (or shrunk/unchanged while still over, or
        the previous-length history is empty)
    1 - One or more files exceed limits, or grew while already over
    2 - INDETERMINATE: the previous-length source could not be reached at
        all, a resolvable HEAD blob could not be interpreted, or a staged
        file's CURRENT content could not be opened or decoded (GE-127a-1-i)

Usage:
    poetry run python scripts/commit_guardian/check_file_size.py
"""

import logging
import subprocess
import sys
from pathlib import Path

from _resolve_root import find_project_root

project_root = find_project_root()

from _file_description import (
    describe_file,
    describe_file_failure_reason,
    format_could_not_describe_line,
    format_description_lines,
)
from _file_size_ratchet import (
    EMPTY_HISTORY_REASON,
    CurrentLengthUnmeasurableError,
    PreviousLengthSourceError,
    describe_measurement_rule,
    measure_current_length,
    resolve_added_measured_lines,
    resolve_head_covered_paths,
    resolve_parent_revisions,
    resolve_previous_lengths,
)
from config import (
    CHECKED_EXTENSIONS,
    DEFAULT_LINE_LIMIT,
    FILE_LINE_LIMITS,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

# GE-127d-2: the label the "what does this length measure" line is printed
# under, and the dividing-advice sentences that replace the prior
# undifferentiated "DO NOT simply delete blank lines, comments, or
# docstrings" sentence -- which named a helpful and a useless action in one
# breath. These two sentences are pinned, free-text guidance (not derived
# from count_content_lines the way describe_measurement_rule() is; see that
# function for the reproducibility-critical line).
_MEASURES_LABEL = "Measures:"
_HELPS_MARKER = "blank lines and '#' comments count toward this length and removing them WILL reduce it"
_NO_HELP_MARKER = (
    "content inside triple-quoted strings or block comments does NOT count toward "
    "this length and removing it will NOT reduce it"
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

    Delegates the actual counting rule to measure_current_length(), which in
    turn calls count_content_lines() -- the same pure function used to
    measure a file's previous (HEAD blob) length, so the current-length and
    previous-length measurements can never drift apart by even one line.

    A path that does not exist on disk (a staged DELETION) is deliberately
    NOT one of the two unmeasurable situations -- see GE-127a-1-i's scope
    boundary -- so it is checked here, before delegating, and reported as
    0 without raising. This is the ONLY caller-visible zero this function
    ever returns; every other unmeasurable state raises instead.

    Args:
        filepath: Path to the file to count.

    Returns:
        Total number of lines in the file, or 0 if the path does not exist
        (a staged deletion, out of this check's scope).

    Raises:
        CurrentLengthUnmeasurableError: the file exists but cannot be opened
            at all, or its content cannot be decoded as UTF-8 -- the two
            situations GE-127a-1-i requires to be named and refused rather
            than silently measured as zero.
    """
    if not Path(filepath).exists():
        return 0

    return measure_current_length(filepath)


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


def check_file(filepath: str) -> tuple[bool, int, int]:
    """
    Check if a file passes the size limit.

    Args:
        filepath: Path to the file to check.

    Returns:
        Tuple of (passes_check, line_count, limit).
    """
    limit = get_limit_for_extension(filepath)
    lines = count_lines(filepath)

    return lines <= limit, lines, limit


def _read_content_for_description(filepath: str) -> str | None:
    """Read *filepath*'s current content, once, for the per-file description.

    Called only for a file ALREADY judged over its permitted length -- a
    commit that refuses nothing never calls this. A read or decode failure
    is logged and yields no description rather than altering the refusal's
    verdict, which is already decided by the time this runs.

    Args:
        filepath: The refused file's path.

    Returns:
        The file's text, or None when it could not be read/decoded.
    """
    try:
        return Path(filepath).read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("could not read %s for a per-file description: %s", filepath, exc)
        return None


def _print_file_description(filepath: str, quoted_length: int) -> None:
    """Append the per-file description -- or a could-not-describe line
    naming why -- to the block just printed for *filepath*.

    Prints nothing at all when the content itself cannot be read (a read
    /decode failure is logged by ``_read_content_for_description`` and
    withheld here, per this repo's error-handling policy). Otherwise prints
    exactly one of: the Parts/Division description (``describe_file``
    succeeded), or a ``DESCRIPTION UNAVAILABLE: reason=<text>`` line naming
    the SPECIFIC cause (GE-127e-3-i) -- never both, never neither, and
    never a substitute sentence standing in for either. This function is
    reached only from the two refusal printers, both of which run only for
    a file `main()`'s classification loop has ALREADY judged too_large/grew
    from length alone -- so nothing printed here can move that verdict.

    Args:
        filepath: The refused file's path.
        quoted_length: The measured length just quoted for this file in the
            refusal block above.
    """
    content = _read_content_for_description(filepath)
    if content is None:
        return
    description = describe_file(filepath, content, quoted_length)
    if description is not None:
        for line in format_description_lines(description):
            print(line)
        print()
        return
    reason = describe_file_failure_reason(filepath, content, quoted_length)
    if reason is not None:
        print(format_could_not_describe_line(reason))
        print()


def _print_measures_line() -> None:
    """Print the shared ``Measures:`` line for a refusal block.

    Generated (GE-127d-2) from ``count_content_lines`` at call time via
    ``describe_measurement_rule`` -- never a hardcoded sentence -- so an
    author who counts every line themselves and arrives at a different
    figure can reconcile the difference from the outcome alone. Shared by
    both refusal printers (``_print_too_large_file`` and
    ``_print_grown_file``) so the wording can never drift between them.
    """
    print(f"   {_MEASURES_LABEL} {describe_measurement_rule()}")


def _print_asymmetry_advice() -> None:
    """Print the shared HELPS_MARKER / NO_HELP_MARKER asymmetry guidance.

    Distinguishes the action that actually reduces the quoted length
    (deleting blank lines / '#' comments) from the one that cannot
    (deleting an already-discarded triple-quoted or block-comment
    region). Shared by both refusal printers so an author sees identical
    guidance regardless of which refusal path (absolute-limit crossing or
    ratchet growth) they tripped.
    """
    print(f"   {_HELPS_MARKER}.")
    print(f"   {_NO_HELP_MARKER}.")


def _print_grown_file(filepath: str, previous_length: int, current_length: int, limit: int) -> None:
    """Print the refusal block for a file that grew while already oversized.

    By construction this file also stands above its permitted length
    under the rule in force (``previous_length`` already exceeds
    ``limit`` -- see ``_classify_file``), so GE-127d-2's requirement
    applies to this refusal exactly as it does to ``_print_too_large_file``'s:
    the block states the length arrived at, the length permitted, and
    (via the shared ``Measures:`` line and asymmetry advice) what that
    length measures.

    GE-127f-2: also states the GROSS measured lines the change PUT INTO the
    file and the required length that leaves (``previous_length - added``),
    recomputed here (rather than threaded through as a parameter) so this
    function's own signature stays exactly the four positional arguments
    every existing call site -- including the disposable-copy fixtures'
    hand-maintained ``main()`` overrides in this suite's test files, which
    this ticket must not edit -- already passes it.

    Args:
        filepath: The staged file's path.
        previous_length: The length it stood at, at HEAD, before the change.
        current_length: The length it stands at after the staged change.
        limit: The permitted length for this file's extension.

    Raises:
        AddedLineCountUnavailableError: the gross added-line count could not
            be re-established for this already-refused file. Deliberately
            left UNCAUGHT here -- see that exception's own docstring in
            _file_size_ratchet.py; GE-127f-2-i owns catching it.
    """
    added = resolve_added_measured_lines(filepath, resolve_parent_revisions())
    required = previous_length - added
    print("❌ FILE GREW WHILE ALREADY OVER ITS LIMIT:")
    print(f"   {filepath}")
    print(f"   Previous length: {previous_length} lines")
    print(f"   New length: {current_length} lines")
    print(f"   Limit: {limit} lines")
    print(f"   This change added {added} measured line(s).")
    print(f"   Required length: {required} lines or below (previous length minus what this change added).")
    _print_measures_line()
    print()
    _print_file_description(filepath, current_length)
    print("   An already-oversized file may still be worked on, but a change")
    print("   that puts more measured lines into it than it takes out is")
    print("   refused. Shrink it, or add no more than you remove, to commit this edit.")
    _print_asymmetry_advice()
    print()


def _print_too_large_file(filepath: str, lines: int, limit: int) -> None:
    """Print the refusal block for a file over its absolute limit.

    The block also states what ``lines`` measures, on the shared
    ``Measures:`` line (see ``_print_measures_line``), and the shared
    dividing advice (see ``_print_asymmetry_advice``) distinguishing the
    action that actually reduces the quoted length from the one that
    cannot, replacing the prior sentence that forbade both in one breath.

    Args:
        filepath: The staged file's path.
        lines: The file's current length.
        limit: The permitted length for this file's extension.
    """
    print("❌ FILE TOO LARGE:")
    print(f"   {filepath}")
    print(f"   Lines: {lines} (Limit: {limit})")
    _print_measures_line()
    print()
    _print_file_description(filepath, lines)
    print("   Please refactor and split this file before committing.")
    _print_asymmetry_advice()
    print("   You MUST split the file to make it easier and less token consuming for agents.")
    print("   (We enforce this check to force refactoring of older files over time).\n")


def _classify_staged_extensions(staged_files: dict[str, bool]) -> tuple[list[str], list[str]]:
    """Partition the staged files' extensions into measured and not-measured.

    An extension is "measured" on this run if it is a member of
    CHECKED_EXTENSIONS -- the same scope-in-force value should_check_file()
    itself consults to decide what to check -- read once here and reused,
    never a second set written into this function (GE-127c-1's anti-grep
    requirement: the declared kinds must move when the configured scope
    moves, because they are read from it rather than restated).

    Args:
        staged_files: Mapping of staged filepath to is_new_file boolean.

    Returns:
        A (measured_kinds, unmeasured_kinds) pair: two sorted lists of the
        distinct file extensions (e.g. ".py") found among the staged files,
        split by membership in CHECKED_EXTENSIONS.
    """
    staged_extensions = {Path(fp).suffix.lower() for fp in staged_files if Path(fp).suffix}
    measured = sorted(ext for ext in staged_extensions if ext in CHECKED_EXTENSIONS)
    unmeasured = sorted(ext for ext in staged_extensions if ext not in CHECKED_EXTENSIONS)
    return measured, unmeasured


def _print_scope_declaration(measured_kinds: list[str], unmeasured_kinds: list[str]) -> None:
    """Print which staged kinds this run measured, and which it did not.

    A staged kind absent from CHECKED_EXTENSIONS is stated here by
    extension only -- never by filename -- so it is never mistaken for a
    file that was looked at and found within its permitted length (GE-127c-1's
    absence clause).

    Args:
        measured_kinds: Distinct staged extensions that ARE in scope.
        unmeasured_kinds: Distinct staged extensions that are NOT in scope.
    """
    measured_text = ", ".join(measured_kinds) if measured_kinds else "(none staged)"
    print(f"📐 Measured kinds this run: {measured_text}")
    unmeasured_text = ", ".join(unmeasured_kinds) if unmeasured_kinds else "(none)"
    print(f"🚫 Not measured this run (kind not in scope): {unmeasured_text}")


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

    While a merge is in progress, the previous length resolved for each
    path is the MOST PERMISSIVE (maximum) length found across every parent
    of the commit -- HEAD plus every parent named in MERGE_HEAD -- not
    HEAD's alone (KI-CG-20260908-file-size-ratchet-refuses-merge-commits).
    A merge whose parent set cannot be established is itself an
    INDETERMINATE source, resolved by the same
    PreviousLengthSourceError floor as any other unreachable source.

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
        parent_revisions = resolve_parent_revisions()
        previous_lengths = resolve_previous_lengths(covered_paths, parent_revisions)
    except PreviousLengthSourceError as exc:
        print(f"INDETERMINATE: reason={exc.reason}", file=sys.stderr)
        return None, 2

    return previous_lengths, None


def _classify_file(
    filepath: str, previous_lengths: dict[str, int]
) -> tuple[str, int, int | None]:
    """Classify one staged, covered file into pass / grew / too-large.

    GE-127f-2: for a file already past its permitted length, the comparison
    is no longer `lines > previous` (net growth -- the forbidden, self
    -referential reading GE-127f-2's own Implementation Notes name as the
    single most likely wrong implementation). It is
    `lines > previous - added`, where `added` is the GROSS count of measured
    lines the staged change PUT INTO the file (resolve_added_measured_lines,
    denominated in the same unit as `lines`/`previous` via the shared
    count_content_lines stripping rule -- never derived by subtracting
    `lines` and `previous`, which are already in hand). This strictly
    generalises the prior comparison: it is recovered EXACTLY when
    `added == 0` (a pure deletion, or an edit touching only unmeasured
    content), which is also GE-127b-1's own reconciled boundary -- see that
    record's amended descriptor,
    test_ge_127b_1_an_oversized_file_edited_only_in_unmeasured_content_commits_at_its_previous_length.
    Per GE-127f-2's COST BUDGET note, `added` is established ONLY inside
    this branch -- a file that is not already oversized never pays for it.

    Args:
        filepath: The staged file's path.
        previous_lengths: Mapping of path to its length at HEAD, for files
            that had one.

    Returns:
        A (verdict, current_length, reference_length) triple. verdict is
        one of "pass", "grew", or "too_large". reference_length is the
        previous length for "grew", the limit for "too_large", or None for
        "pass".

    Raises:
        AddedLineCountUnavailableError: the gross added-line count could not
            be established for an already-oversized file. Deliberately left
            UNCAUGHT here -- see that exception's own docstring in
            _file_size_ratchet.py; GE-127f-2-i owns catching it.
    """
    lines = count_lines(filepath)
    limit = get_limit_for_extension(filepath)
    previous = previous_lengths.get(filepath)

    if previous is not None and previous > limit:
        # This file is already past its permitted length per GE-127b: judge
        # it against its OWN previous length, less what the change added
        # (GE-127f-2), never against the fixed limit.
        added = resolve_added_measured_lines(filepath, resolve_parent_revisions())
        required = previous - added
        if lines > required:
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
        not be reached at all, a resolvable HEAD blob could not be
        interpreted, or a staged file's CURRENT content could not be opened
        or decoded).
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
    measured_kinds, unmeasured_kinds = _classify_staged_extensions(staged_files)

    previous_lengths, indeterminate_exit = _resolve_ratchet_or_indeterminate(list(covered_files))
    if indeterminate_exit is not None:
        return indeterminate_exit

    grown_files: list[tuple[str, int, int]] = []
    failed_files: list[tuple[str, int, int]] = []
    passed_files: list[tuple[str, int, bool]] = []  # (path, lines, is_new)

    try:
        for filepath, is_new in covered_files.items():
            verdict, lines, reference = _classify_file(filepath, previous_lengths)
            if verdict == "grew":
                grown_files.append((filepath, reference, lines))
            elif verdict == "too_large":
                failed_files.append((filepath, lines, reference))
            else:
                passed_files.append((filepath, lines, is_new))
    except CurrentLengthUnmeasurableError as exc:
        print(f"INDETERMINATE: reason={exc.reason}", file=sys.stderr)
        return 2

    # Print results
    print("\n📏 File Size Check\n")
    _print_scope_declaration(measured_kinds, unmeasured_kinds)
    print(f"📊 Compared {len(previous_lengths)} file(s) against their previous length.\n")

    for filepath, previous, lines in grown_files:
        _print_grown_file(filepath, previous, lines, get_limit_for_extension(filepath))

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
- 2026-09-28 [python-coder/GE-127f-2]: `_classify_file`'s already-oversized
  branch now judges `lines > previous - added` instead of `lines > previous`
  -- `added` is the GROSS measured lines the staged change PUT INTO the
  file (`_file_size_ratchet.resolve_added_measured_lines`), never the net
  (current-minus-previous) growth, which is self-referential and collapses
  back to GE-127b unchanged (a same-length replacement would register as
  having added nothing). The new comparison is a strict generalisation of
  the old one, recovered exactly when `added == 0` -- also the shape
  GE-127b-1's own amended boundary descriptor now pins
  (`test_ge_127b_1_an_oversized_file_edited_only_in_unmeasured_content_commits_at_its_previous_length`).
  `added` is established ONLY inside this branch, per the AC's own COST
  BUDGET note -- a file that is not already oversized pays nothing new.
  `_print_grown_file` now also states the added-line count and the required
  length, recomputed internally (via the same `resolve_added_measured_lines`
  call) rather than threaded through as a new parameter, so its own
  signature -- and `_classify_file`'s, and `_resolve_ratchet_or_
  indeterminate`'s -- stay byte-for-byte the same as every existing call
  site already calls them with, including two test/fixture modules in this
  suite (`_ge_127a_1_ordinary_commit_fixture.py`'s string-replacement
  mutation targets, `_ge_127e_3_i_fixture.py`'s disposable `main()`
  override) that this ticket must not edit. Neither function's RETURN
  shape changed either, for the same reason. Verified: the full
  commit_guardian regression suite (GE-127a, GE-127b-1's four split files
  plus `_i`, GE-127c-1, GE-127d-2, GE-127e-2/3/3-i/4, the KI-CG-20260908
  merge-aware suite, and `test_ac_limits_merge_scope.py`) stayed green
  throughout, `check_file_size_rule_parity.py` exits 0, and
  `ruff check scripts unit_tests` is clean. TEMPLATES-ONLY: this change
  was not built (`scripts/build.py --force` is denied in this workspace);
  the deployed copy under `.leafcutter/`/`scripts/` reflects the PRE
  -GE-127f-2 behaviour until the next build.
- 2026-09-28 [python-coder/GE-127e-3-i]: `_print_file_description` now
  prints a `DESCRIPTION UNAVAILABLE: reason=<text>` line -- a NEW, third
  token in `_file_size_ratchet.py`'s `TOKEN: reason=<text>` line shape,
  never `INDETERMINATE`, never exit 2 -- naming the specific cause when
  `describe_file` returns None, via the new sibling
  `_file_description.describe_file_failure_reason`. `describe_file`'s own
  signature and None-on-failure return contract are UNCHANGED (see
  `_file_description.py`'s own module docstring for why: every existing
  caller across GE-127e-1/e-2/e-3's test suites, and this AC's own
  verdict-independence mutation proofs, matches on `describe_file(...) is
  None` directly). The verdict is computed by `_classify_file` from length
  alone, before this function ever runs, so nothing here can move it --
  descriptors 1/3/4/5 (verdict independence, no substitute advice, never
  refused for having guidance, never reported for an under-limit file) were
  already true of the unmodified tree and remain true unchanged.
- 2026-09-23 [python-coder/GE-127d-2 rework, H-1]: pr-reviewer found
  `_print_grown_file` (the GE-127b-1 ratchet-growth "grew" refusal) was left
  entirely outside the prior round's fix -- no permitted length, no
  `Measures:` line, no asymmetry guidance -- even though a "grew" verdict is,
  by construction, also a file standing above its permitted length
  (`_classify_file` only returns "grew" when `previous > limit`), so this
  AC's Gherkin applies to it exactly as it does to `_print_too_large_file`'s
  "too_large" verdict. Extracted the shared `Measures:` line and
  HELPS_MARKER/NO_HELP_MARKER advice into two new helpers,
  `_print_measures_line()` and `_print_asymmetry_advice()`, so the wording
  cannot drift between the two refusal printers, and had both printers call
  them -- `_print_too_large_file`'s own printed output is byte-for-byte
  unchanged, only its implementation was refactored. Extended
  `_print_grown_file`'s signature to accept `limit` (the sole call site, in
  `main()`, updated to pass `get_limit_for_extension(filepath)` -- confirmed
  by grep this is the only caller anywhere in the tree); it now also prints
  a `Limit: N lines` line, the shared `Measures:` line, and the shared
  asymmetry advice. test-writer's 9th descriptor
  (`test_ge_127d_2_a_grown_already_oversized_file_states_the_new_length_the_permitted_length_and_what_is_measured`)
  drives this path through a real `git commit` and confirms all three
  requirements now hold for the "grew" verdict too.
- 2026-09-22 [python-coder/GE-127d-2]: `_print_too_large_file` now prints a
  `Measures:` line generated (never hardcoded) from
  `_file_size_ratchet.describe_measurement_rule`, so the length quoted for a
  refused file can be reproduced independently by applying the SAME
  published statement -- the statement moves automatically with the rule
  in force because `describe_measurement_rule` probes `count_content_lines`
  as an ordinary module-global reference resolved at call time. Replaced
  the prior undifferentiated "DO NOT simply delete blank lines, comments,
  or docstrings to bypass this." sentence -- which forbade both a helpful
  and a useless action in one breath -- with two sentences that name each
  action's actual effect on the quoted length. Per architect-review's
  fifth ruling on this ticket, the discard rule is ALSO stated in
  commit_guardian.json's `file_size._comment` (already-published static
  surface) alongside the dynamic `Measures:` line, since a per-refusal
  stdout line cannot be a `published_rule_surfaces` entry
  `check_file_size_rule_parity.py` (GE-127d-1) can reconcile.
- 2026-09-21 [python-coder/GE-127d-1 rework, H-1]: pr-reviewer (10:45) and
  ac-validator (11:05) independently found the 2026-09-15 fix below had
  removed `is_new_file` from the WRONG function: `check_file()` (below) has
  no callers anywhere in this file -- `main()` calls `_classify_file()` at
  commit time, and THAT function still accepted an inert `is_new` that its
  body never read. Removed `is_new` from `_classify_file()`'s signature and
  docstring, and updated its one call site in `main()` to match. `main()`'s
  own `is_new` (from `covered_files.items()`) is untouched and still feeds
  the legitimate new/modified label in the `passed_files` report.
- 2026-09-15 [python-coder/GE-127d-1]: Removed unused, accepted-but-inert `is_new_file` from check_file() (a decoy -- see the 2026-09-21 entry above); added sibling gate check_file_size_rule_parity.py; corrected README.md's stale new-files-only claim (see 2026-05-01 below).
- 2026-09-14 [python-coder/GE-127c-1]: Widened commit_guardian.json's
  file_size.checked_extensions (pinned by GE-127c-1's it_requirements) from
  [".py", ".sql"] to [".py", ".sql", ".js", ".mjs", ".ts", ".tsx", ".sh"],
  each with its own explicit line_limits entry so none silently inherits
  DEFAULT_LINE_LIMIT. Added _classify_staged_extensions() /
  _print_scope_declaration(): every run now states, derived once from
  CHECKED_EXTENSIONS, which staged kinds it measured and which staged kinds
  it did not (by extension only, never by filename, so an unmeasured kind
  can never read as "found within its limit"). Deleted the ".md" branch of
  _print_too_large_file()'s dividing advice: ".md" is deliberately excluded
  from checked_extensions (already governed by check-doc-length), so that
  branch could never execute from any real refusal -- an unreachable
  coverage claim GE-127c-1's fourth clause forbids.
  KNOWN TEST CONFLICT (flagged, not resolved by editing the test): the
  test-writer-authored test_ge_127c_1_changing_the_scope_in_force_moves_the_
  stated_set_of_measured_kinds probes the anti-grep clause using ".sh" as
  its "currently outside scope" extension and asserts the UNMODIFIED,
  real commit_guardian.json must NOT yet contain ".sh" -- but this AC's own
  it_requirements pin ".sh" INTO real checked_extensions (limit 400, NEW),
  and the sibling deployed-config test in this same file asserts ".sh" MUST
  be present in that exact file. No production change can satisfy both
  simultaneously. Per the "no test file edits" delegation rule this was
  left for test-writer/ticket-supervisor to resolve (e.g. re-probe with a
  permanently out-of-scope extension such as ".css" instead of ".sh").
- 2026-09-08 [python-coder/KI-CG-20260908-file-size-ratchet-refuses-merge-commits]:
  Made the ratchet merge-aware. _resolve_ratchet_or_indeterminate() now
  resolves every parent revision of the commit in progress (via
  _file_size_ratchet.resolve_parent_revisions(), HEAD plus every
  MERGE_HEAD line) and passes them into resolve_previous_lengths(), which
  now takes the MAXIMUM previous length found across all of them as each
  file's permitted previous length -- fixing a defect where an ordinary
  `git merge origin/main` was refused on every already-oversized file the
  other side had already (and legitimately) grown, because judging solely
  against HEAD made that already-accepted growth look newly introduced by
  the merge. _classify_file()'s own logic is unchanged: it already judged
  a file against whatever "previous" length it was handed, so a merge with
  a correctly-resolved permissive baseline now passes without any change
  to the crossing-refusal / ratchet branching itself.
- 2026-09-07 [python-coder/GE-127a-1 + GE-127a-1-i]: Registered `check-file
  -size` in commit_guardian.json's hooks_manifest.hooks (always_run: true,
  the script resolves its own staged-file set) -- the gate previously had
  correct comparison logic but ran at no commit at all. Replaced
  count_lines()'s swallow-and-return-0 behaviour on an unreadable/undecodable
  CURRENT file with a new CurrentLengthUnmeasurableError (raised by the new
  sibling measure_current_length() in _file_size_ratchet.py), caught in
  main() and reported as INDETERMINATE (exit 2) naming which of the two
  situations occurred ("cannot be opened at all" vs. "not readable as text
  in the encoding the standard reads") -- reusing BP-100n-4-ii's verdict
  vocabulary unchanged. A staged deletion (path does not exist) is excluded
  from this branch explicitly in count_lines() and still reports 0 without
  raising, per GE-127a-1-i's own out-of-scope carve-out.
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
