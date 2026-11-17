"""
MODULE: commit_guardian._doc_length_set_aside
GOAL: Supply check_doc_length.py with the REPORTING half of the set-aside
    mechanism: the two separately counted populations (judged / set aside),
    the stated ground each set-aside document carries, the per-location
    ``report_above_lines`` ceiling and the report for a document standing above
    it, and the validation that makes a ceiling impossible to omit.
BUSINESS CONTEXT: A document in a declared set-aside location is exempt from
    the authored length limit (GE-127g-1). Exempt must never mean invisible
    (GE-127g-2: a check that examined nothing must not look like a check that
    found nothing) and must never mean unbounded (GE-127g-5: a location may be
    set aside only together with the size beyond which its documents are
    reported). The ceiling is REPORTED, never refused: a refusal for a length
    nobody wrote and nobody can shorten is the defect this mechanism removes.
ARCHITECTURE: Sibling module inside templates/scripts/commit_guardian/, which
    build_commit_guardian deploys whole, so no deploy-map entry is needed.
    The ground and the ceiling are READ from the declaration entry that
    matched each document; this module carries no copy of either.
"""

import json
from typing import Any, NamedTuple

from _doc_length_ratchet import (
    SetAsideDeclarationError,
    is_doc_file,
    is_checked,
    is_excluded,
    measure_doc_lines,
    parse_set_aside_locations,
    read_doc_content,
)

CEILING_KEY = "report_above_lines"
DECLARATION_NAME = "commit_guardian.json (doc_length.set_aside_locations)"

# Limits applied when the config file itself cannot be loaded. These are limits
# only: there is deliberately NO fallback set of set-aside locations (GE-127g-2-i).
_FALLBACK_MAX_LINES = 300
_FALLBACK_MAX_LINES_ADR = 400
_FALLBACK_MAX_SECTIONS = 25


class DocLengthSettings(NamedTuple):
    """The gate's settings plus ONE classified outcome of reading the declaration.

    ``problem`` is None when the declaration was read and interpreted (an empty
    entry list is a completing read, not a problem); otherwise it is a
    ``(kind, detail)`` pair where kind is "read" or "interpreted".
    """

    max_lines: int
    max_lines_adr: int
    max_sections: int
    severity: str
    entries: list
    paths: tuple
    problem: tuple | None


def _interpret_declaration(entries: Any) -> tuple[tuple, tuple | None]:
    """Validate *entries*; return (paths, problem) with no paths on a problem."""
    if not isinstance(entries, list):
        return (), ("interpreted", "doc_length.set_aside_locations is not a list of entries")
    try:
        return parse_declared_set_aside(entries), None
    except SetAsideDeclarationError as exc:
        return (), ("interpreted", exc.reason)


def load_doc_length_settings() -> DocLengthSettings:
    """Load the gate settings, classifying the declaration read exactly once.

    The read is ATTEMPTED (never pre-tested for existence) and its failure
    classified at this point: the file could not be read, or its content could
    not be interpreted. Nothing downstream infers either from an entry count.

    Returns:
        DocLengthSettings: Settings; on a problem the entries/paths are empty
        (every document is judged) and the limits fall back to the defaults.
    """
    fallback = (_FALLBACK_MAX_LINES, _FALLBACK_MAX_LINES_ADR, _FALLBACK_MAX_SECTIONS, "block")
    try:
        import config
    except FileNotFoundError as exc:
        return DocLengthSettings(*fallback, [], (), ("read", str(exc).splitlines()[0]))
    except json.JSONDecodeError as exc:
        return DocLengthSettings(*fallback, [], (), ("interpreted", f"invalid JSON ({exc.msg})"))
    paths, problem = _interpret_declaration(config.DOC_LENGTH_SET_ASIDE_LOCATIONS)
    entries = [] if problem else config.DOC_LENGTH_SET_ASIDE_LOCATIONS
    return DocLengthSettings(
        config.DOC_LENGTH_MAX_LINES,
        config.DOC_LENGTH_MAX_LINES_ADR,
        config.DOC_LENGTH_MAX_SECTIONS,
        config.DOC_LENGTH_SEVERITY,
        entries,
        paths,
        problem,
    )


def render_declaration_problem(problem: tuple) -> str:
    """State that the declaration could not be read / interpreted, and name it.

    Deliberately carries no population figure: the counts are stated once, by
    ``counts_line``, from the populations as the run partitions them.
    """
    kind, detail = problem
    return (
        f"DECLARATION PROBLEM: the declaration {DECLARATION_NAME} could not be {kind}: {detail}\n"
        "Every staged document is measured against the authored limit and nothing is exempted "
        "on the strength of a declaration nobody could use. Fix the declaration."
    )


def counts_line(judged_count: int, aside_count: int) -> str:
    """The two separately counted populations, stated as one line."""
    return f"{judged_count} documents judged, {aside_count} set aside"


def parse_declared_set_aside(entries: list[dict]) -> tuple[str, ...]:
    """Validate the declaration (ground AND ceiling) and return its paths.

    The ground is validated first by ``parse_set_aside_locations``; the
    ceiling is validated here. The two failures carry different messages so
    the author of the declaration can tell which is absent.

    Args:
        entries: The ``doc_length.set_aside_locations`` list from the config.

    Returns:
        The declared paths, in declaration order.

    Raises:
        SetAsideDeclarationError: an entry lacks a ground, or lacks a positive
            integer ``report_above_lines`` (never defaulted).
    """
    paths = parse_set_aside_locations(entries)
    for index, entry in enumerate(entries):
        ceiling = entry.get(CEILING_KEY)
        if isinstance(ceiling, bool) or not isinstance(ceiling, int) or ceiling <= 0:
            raise SetAsideDeclarationError(
                index,
                f"({entry['path']!r}) declares no {CEILING_KEY} ceiling: a location may be "
                "set aside only together with the size beyond which its documents are reported",
            )
    return paths


def select_set_aside_paths(staged_files: dict[str, str], set_aside_paths: tuple[str, ...]) -> list[str]:
    """Return the staged, non-deleted docs that sit in a declared location.

    Args:
        staged_files: Mapping of filepath to git status.
        set_aside_paths: The parsed set-aside declaration.

    Returns:
        list[str]: Set-aside paths in staged order.
    """
    return [
        filepath
        for filepath, status in staged_files.items()
        if status != "D" and is_doc_file(filepath) and is_excluded(filepath, set_aside_paths)
    ]


def select_checked_paths(staged_files: dict[str, str], set_aside_paths: tuple[str, ...]) -> list[str]:
    """Return the staged, non-deleted paths the gate covers (not set aside).

    Args:
        staged_files: Mapping of filepath to git status from ``get_staged_files``.
        set_aside_paths: The parsed set-aside declaration.

    Returns:
        list[str]: Paths to measure, in staged order.
    """
    return [
        filepath
        for filepath, status in staged_files.items()
        if status != "D" and is_checked(filepath, set_aside_paths)
    ]


def format_growth_note(violation: dict) -> str | None:
    """Describe a ratchet refusal, or None when neither dimension grew.

    A "grew" refusal needs different wording from a "crossed the limit" one:
    the author is not being told to get under 300 lines, they are being told
    not to make an already-long doc longer in this commit.

    Args:
        violation: A violation dict from ``analyze_file``.

    Returns:
        The explanatory line, or None when no dimension grew.
    """
    grew = []
    if violation.get("lines_verdict") == "grew":
        grew.append(f"lines {violation['previous_lines']} → {violation['line_count']}")
    if violation.get("sections_verdict") == "grew":
        grew.append(f"sections {violation['previous_sections']} → {violation['section_count']}")
    if not grew:
        return None
    return (
        f"   📈 Already over its limit and grew further in this commit ({', '.join(grew)}).\n"
        "      Shrinking it, or leaving its size unchanged, is allowed — growing it is not."
    )


def matching_entry(filepath: str, entries: list[dict]) -> dict:
    """Return the declaration entry that set *filepath* aside.

    Args:
        filepath: Repo-relative path of a set-aside document.
        entries: The validated declaration.

    Returns:
        dict: The first entry whose path matches (membership uses the ONE
        ``is_excluded`` test).
    """
    return next(entry for entry in entries if is_excluded(filepath, (entry["path"],)))


def _ceiling_statement(filepath: str, size: int, entry: dict) -> str:
    """One paragraph stating a document stands above its location's ceiling."""
    ceiling = entry[CEILING_KEY]
    return (
        f"{filepath} stands above the ceiling its location declares: "
        f"{size} lines measured against a ceiling of {ceiling} (headroom {ceiling - size}).\n"
        "The commit is not refused. This is addressed to the owner of the source named "
        f"by the location's stated ground: {entry['ground']}"
    )


def render_population_report(judged_count: int, aside_paths: list[str], entries: list[dict]) -> str:
    """Render the two counts, each set-aside document with its ground, and any over-ceiling paragraphs.

    Both counts come from the populations as the run partitioned them. The
    over-ceiling comparison is a direct size-versus-ceiling test, independent
    of any ratchet verdict, so a document that shrank while still above its
    ceiling is still reported. It never moves a document between populations.

    Args:
        judged_count: Number of documents judged against the authored limit.
        aside_paths: Staged set-aside documents.
        entries: The validated declaration.

    Returns:
        str: The report text, blank-line-separated paragraphs; "" when there
        is nothing judged and nothing set aside.

    Raises:
        CurrentLengthUnmeasurableError: a set-aside document could not be read.
    """
    if judged_count == 0 and not aside_paths:
        return ""
    head = [counts_line(judged_count, len(aside_paths))]
    over: list[str] = []
    for filepath in aside_paths:
        entry = matching_entry(filepath, entries)
        head.append(f"  set aside: {filepath} -- ground: {entry['ground']}")
        size = measure_doc_lines(read_doc_content(filepath))
        if size > entry[CEILING_KEY]:
            over.append(_ceiling_statement(filepath, size, entry))
    return "\n\n".join(["\n".join(head), *over])
