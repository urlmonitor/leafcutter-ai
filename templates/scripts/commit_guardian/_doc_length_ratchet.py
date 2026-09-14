"""
MODULE: commit_guardian._doc_length_ratchet
GOAL: Supply check_doc_length.py with everything its ratchet needs that is
    SPECIFIC to documentation — the counting rules (lines after YAML
    frontmatter; top-level ``##`` sections), the covered-set predicates
    (under ``docs/``, ends ``.md``, basename not excluded), the per-file
    limit selection (ADRs get their own), and the pass/grew/over verdict —
    while deliberately owning NONE of the git plumbing. Parent-revision
    resolution, merge awareness, the two-situation INDETERMINATE floor and
    the empty-history classification all come from _file_size_ratchet.py,
    which this module imports rather than reimplements.
BUSINESS CONTEXT: check-doc-length shipped as severity ``warn`` and so always
    exited 0 — the reason three known-issues registers reached ~4,500 lines
    against a 300-line limit without one commit being stopped. Flipping it to
    ``block`` against an absolute limit would instead freeze the 59 docs
    already over, including those same append-heavy registers, so the gate
    would be turned off again within a day. The ratchet is what makes
    blocking survivable: a doc may not CROSS its limit, and a doc already
    over it may not GROW, but shrinking or holding steady is always allowed.
    That is the same posture check_file_size.py took for code under
    GE-127a-1 / GE-127b-1, and reusing its module is what keeps the two
    gates' semantics from drifting apart.
ARCHITECTURE: Sibling module inside templates/scripts/commit_guardian/.
    build_commit_guardian copies this directory whole, so no
    scripts/build_phases.py deploy-map entry is required — a module imported
    from OUTSIDE this directory would need one (see CLAUDE.md, "New Hook /
    Gate Dependencies Must Be in the Build Deploy-Manifest").
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from _file_size_ratchet import (
    CurrentLengthUnmeasurableError,
    PreviousLengthSourceError,
    resolve_head_matching_paths,
    resolve_parent_revisions,
    resolve_previous_lengths,
)

# YAML frontmatter regex (opening --- to closing ---)
_FRONTMATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)

# Top-level sections: lines starting with ## (but not ###)
_SECTION_RE = re.compile(r"^##\s+(.+)$")

# The COMPLETING empty-history outcome, worded for this gate's covered set.
# Deliberately a distinct string from _file_size_ratchet.EMPTY_HISTORY_REASON
# (which names "a checked extension") so each gate states the truth about its
# own population, and deliberately NOT borrowing the INDETERMINATE token,
# which the pinned verdict contract binds to exit 2.
DOC_EMPTY_HISTORY_REASON = (
    "the previous-length history holds no checked documentation file "
    "whatsoever: HEAD resolves to no commit yet, or its tree contains no "
    "non-excluded docs/**.md file"
)


# ---------------------------------------------------------------------------
# Measurement rules
# ---------------------------------------------------------------------------

def strip_frontmatter(content: str) -> str:
    """Remove YAML frontmatter from the beginning of a markdown file.

    Args:
        content: Full file content as a string.

    Returns:
        str: Content with frontmatter stripped.
    """
    return _FRONTMATTER_RE.sub("", content, count=1)


def count_lines_and_sections(content: str) -> tuple[int, list[tuple[str, int, int]]]:
    """Count content lines and identify top-level (##) sections with their spans.

    Args:
        content: Markdown content with frontmatter already stripped.

    Returns:
        tuple: (line_count, sections) where sections is a list of
            (title, start_line, line_count) tuples.
    """
    lines = content.split("\n")
    line_count = len(lines)

    section_starts: list[tuple[str, int]] = []
    for i, line in enumerate(lines):
        match = _SECTION_RE.match(line)
        if match:
            section_starts.append((match.group(1).strip(), i + 1))

    sections: list[tuple[str, int, int]] = []
    for idx, (title, start) in enumerate(section_starts):
        if idx + 1 < len(section_starts):
            end = section_starts[idx + 1][1] - 1
        else:
            end = line_count
        sections.append((title, start, end - start + 1))

    return line_count, sections


def measure_doc_lines(content: str) -> int:
    """Measure *content*'s line count under this gate's rule.

    This is the SINGLE line-counting rule, applied both to a staged file's
    current text and to its text at every parent revision. Routing both
    sides through one function is what stops the ratchet comparing two
    different measurements and reporting growth that did not happen.

    Args:
        content: Full file content, frontmatter included.

    Returns:
        The number of lines after frontmatter is stripped.
    """
    return count_lines_and_sections(strip_frontmatter(content))[0]


def measure_doc_sections(content: str) -> int:
    """Measure *content*'s top-level (``##``) section count.

    The section counterpart to ``measure_doc_lines``, and used the same way
    on both sides of the comparison.

    Args:
        content: Full file content, frontmatter included.

    Returns:
        The number of top-level sections after frontmatter is stripped.
    """
    return len(count_lines_and_sections(strip_frontmatter(content))[1])


def read_doc_content(filepath: str) -> str:
    """Read *filepath*'s current text, refusing rather than skipping on failure.

    The read is split into raw bytes then a separate decode so the two
    refusing situations are distinguished by construction rather than by
    inspecting one caught exception two ways — the same split
    ``_file_size_ratchet.measure_current_length`` makes, and the reason this
    function raises instead of returning None: under a blocking gate, a doc
    whose length cannot be established must produce a named INDETERMINATE
    verdict, never a silent skip that reads to the author as a pass.

    Args:
        filepath: Path to the staged doc. The caller must have already
            confirmed it is not a staged deletion.

    Returns:
        The file's decoded text.

    Raises:
        CurrentLengthUnmeasurableError: the file could not be opened at all,
            or its content could not be decoded as UTF-8.
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


# ---------------------------------------------------------------------------
# Covered-set predicates
# ---------------------------------------------------------------------------

def is_doc_file(filepath: str) -> bool:
    """Check whether a file path is a documentation markdown file in docs/.

    Args:
        filepath: Relative file path from the project root.

    Returns:
        bool: True if the file is a docs/*.md file.
    """
    return filepath.startswith("docs/") and filepath.endswith(".md")


def is_adr_file(filepath: str) -> bool:
    """Check whether a file path is an Architecture Decision Record.

    Args:
        filepath: Relative file path from the project root.

    Returns:
        bool: True if the file is in docs/architecture/adrs/.
    """
    return filepath.startswith("docs/architecture/adrs/")


def is_excluded(filepath: str, excluded_files: set[str]) -> bool:
    """Check whether a file should be excluded from checking.

    Args:
        filepath: Relative file path from the project root.
        excluded_files: Set of filenames (basenames) to exclude.

    Returns:
        bool: True if the file should be skipped.
    """
    return Path(filepath).name in excluded_files


def is_checked(filepath: str, excluded_files: set[str]) -> bool:
    """Check whether *filepath* is in this gate's covered set.

    The single definition of "a file this gate judges", used both to filter
    the staged set and — via ``resolve_doc_ratchet`` — to decide whether
    HEAD holds any covered file at all. One predicate for both keeps the
    empty-history classification honest about the same population the run
    actually checks.

    Args:
        filepath: Relative file path from the project root.
        excluded_files: Set of basenames to exclude.

    Returns:
        bool: True if the file is checked by this gate.
    """
    return is_doc_file(filepath) and not is_excluded(filepath, excluded_files)


# ---------------------------------------------------------------------------
# Ratchet resolution and classification
# ---------------------------------------------------------------------------

def resolve_doc_ratchet(
    paths: list[str], excluded_files: set[str]
) -> tuple[tuple[dict[str, int], dict[str, int]] | None, int | None]:
    """Resolve previous line and section counts for *paths*, or the INDETERMINATE exit.

    The previous-value SOURCE is classified exactly once, here, at the point
    of resolution: empty history (HEAD holds no covered doc at all, including
    an unborn HEAD) is a legitimate COMPLETING result named as "EMPTY
    HISTORY", never confused with the two REFUSING situations (source
    unreachable, source uninterpretable) which exit 2 as "INDETERMINATE".
    The distinction is made by which function raised or what it returned,
    never downstream by inspecting how many previous values came back.

    Args:
        paths: Staged, covered doc paths to resolve previous values for.
        excluded_files: Set of basenames excluded from this gate.

    Returns:
        A (previous_values, exit_code) pair. On success (including empty
        history), exit_code is None and previous_values is a
        (previous_lines, previous_sections) pair of mappings, each possibly
        empty. On an unresolvable source, previous_values is None and
        exit_code is 2 — the caller must print nothing else and return it.
    """
    if not paths:
        return ({}, {}), None

    try:
        covered_at_head = resolve_head_matching_paths(
            lambda path: is_checked(path, excluded_files)
        )
    except PreviousLengthSourceError as exc:
        print(f"INDETERMINATE: reason={exc.reason}", file=sys.stderr)
        return None, 2

    if not covered_at_head:
        print(f"EMPTY HISTORY: reason={DOC_EMPTY_HISTORY_REASON}")
        return ({}, {}), None

    try:
        parent_revisions = resolve_parent_revisions()
        previous_lines = resolve_previous_lengths(paths, parent_revisions, measure_doc_lines)
        previous_sections = resolve_previous_lengths(paths, parent_revisions, measure_doc_sections)
    except PreviousLengthSourceError as exc:
        print(f"INDETERMINATE: reason={exc.reason}", file=sys.stderr)
        return None, 2

    return (previous_lines, previous_sections), None


def classify_dimension(current: int, previous: int | None, limit: int) -> str:
    """Classify one measured dimension into pass / grew / over.

    The ratchet rule, stated once and applied to both dimensions: a file
    already past its limit at every parent is judged against its OWN
    previous value, never against the fixed limit — so it may shrink or hold
    steady while still over. Only a file that CROSSES the limit, or GROWS
    while already over, is refused.

    Args:
        current: The value measured on the staged content.
        previous: The most permissive value across every parent revision, or
            None when the file existed at no parent (a genuinely new file).
        limit: The configured maximum for this dimension.

    Returns:
        "grew" (already over and now larger), "over" (crossed the limit this
        commit, or arrived new and over), or "pass".
    """
    if previous is not None and previous > limit:
        return "grew" if current > previous else "pass"
    return "over" if current > limit else "pass"


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-14 [doc-length ratchet]: Initial authoring. Moved the measurement
  rules (strip_frontmatter, count_lines_and_sections) and the path
  predicates (is_doc_file, is_adr_file, is_excluded) out of
  check_doc_length.py so both the current-content and previous-revision
  sides of the comparison call ONE counting function, and so this module can
  supply the HEAD-covered-set predicate without importing its caller. Added
  measure_doc_lines / measure_doc_sections as the two pluggable rules handed
  to _file_size_ratchet.resolve_previous_lengths(), resolve_doc_ratchet() as
  the source classifier (mirroring check_file_size._resolve_ratchet_or_
  indeterminate, including the EMPTY HISTORY vs INDETERMINATE split), and
  classify_dimension() as the shared pass/grew/over rule for both the line
  and section dimensions. read_doc_content() raises
  CurrentLengthUnmeasurableError where check_doc_length.read_file_content()
  returned None: a silent skip was tolerable while the gate only warned, and
  is the fail-open shape KI-CG-034 / KI-CG-012 / KI-CG-018 all shipped once
  the gate can actually refuse.
====================================================================
"""
