"""
MODULE: commit_guardian._file_description
GOAL: Turn a size-refused file's own content into the per-file description
    GE-127e-1 requires: named constituent parts located in the file's own
    content, the portion of the measured length each accounts for, and (when
    more than one part fully accounts for the file) a division stating which
    parts fall on each side and the length each side would stand at.
BUSINESS CONTEXT: GE-127's incumbent refusal names a helper and warns against
    stripping content -- identical for every refused file, saying nothing
    about the file in hand. This module is the part that makes the refusal
    ABOUT the file: two different oversized files must never produce the same
    description, and the description must change when the file's content
    changes. See GE-127e-1's own it_requirements: extraction MAY be per kind
    (a top-level definition for Python, a top-level object statement for
    SQL), but the SELECTION of which parts to print and where to divide must
    never be a fixed inventory keyed on the file's kind -- every name and
    portion below is read out of the file that was actually refused.
ARCHITECTURE: Sibling module to check_file_size.py, inside
    templates/scripts/commit_guardian/. build_commit_guardian copies this
    whole directory verbatim, so no scripts/build_phases.py deploy-map entry
    is required for this file. check_file_size.py imports describe_file() and
    format_description_lines() and appends their output to the SAME printed
    refusal block as the existing "Lines: N (Limit: M)" finding -- no second
    stream, no second artifact (GE-127e-1's "ONE OUTCOME, NOT A SECOND
    SURFACE" constraint). Every portion and side length below is produced by
    _file_size_ratchet.count_content_lines -- the SAME pure function that
    produces the quoted whole-file length -- so reconciliation between the
    parts, the sides, and the quoted length is arithmetic, never a second
    counting rule (GE-127d is consumed here, not restated).

    COST BUDGET: describe_file() is only ever called by check_file_size.py
    for a file already judged over its permitted length; a commit that
    refuses nothing calls nothing here.

    UNDER-HALF AND UNPARSEABLE CONTENT: when the located parts cannot account
    for at least half of the quoted length, or the content cannot be parsed
    at all, describe_file() returns None -- a could-not-be-described state
    that GE-127e-3-i owns, not this module. Returning None here changes
    nothing about the refusal's verdict; it only withholds this module's
    OWN additional content, which is what the "swallow a parse error into an
    empty description" hazard this repo's error-handling policy warns against
    would otherwise produce.

DECISION HISTORY
- 2026-09-14 [GE-127e-1/python-coder]: Initial authoring.
"""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from _file_size_ratchet import count_content_lines

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

_SQL_OBJECT_RE = re.compile(
    r"^\s*CREATE\s+(?:OR\s+REPLACE\s+)?"
    r"(?P<kind>MATERIALIZED\s+VIEW|FUNCTION|PROCEDURE|TABLE|VIEW|TRIGGER|INDEX|TYPE)\s+"
    r"(?P<name>[A-Za-z_][\w.\"]*)",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass(frozen=True)
class DescribedPart:
    """One named constituent part located in the refused file's own content.

    Attributes:
        name: The part's name exactly as it appears in the file (a Python
            top-level def/class name, or a SQL object name) -- never a
            synthesized or kind-generic label.
        portion: The part's own length via ``count_content_lines``, the same
            measurement function that produces the whole-file quoted length.
    """

    name: str
    portion: int


@dataclass(frozen=True)
class FileDescription:
    """The per-file description appended to an existing size refusal.

    Attributes:
        parts: Every located named part, in file order.
        side_a: ``(names, length)`` for one side of the named division, or
            None when no division is offered (single part, or the located
            parts do not fully account for the quoted length).
        side_b: The division's other side, paired with ``side_a``.
        single_part_name: Set only when exactly one part accounts for the
            file -- the honest "no division exists" case GE-127e-1 requires
            rather than inventing a seam.
    """

    parts: list[DescribedPart]
    side_a: tuple[list[str], int] | None = None
    side_b: tuple[list[str], int] | None = None
    single_part_name: str | None = None


def _python_part_bounds(node: ast.AST) -> tuple[int, int]:
    """Return the (start_line, end_line) span of a top-level def/class node.

    Decorators are included in the span -- they are part of what an author
    reading the file sees as belonging to that part.

    Args:
        node: A top-level ``FunctionDef``/``AsyncFunctionDef``/``ClassDef``.

    Returns:
        1-indexed inclusive (start_line, end_line).
    """
    start = node.lineno
    decorators = getattr(node, "decorator_list", None)
    if decorators:
        start = min(decorator.lineno for decorator in decorators)
    return start, node.end_lineno


def extract_python_parts(content: str) -> list[DescribedPart]:
    """Locate every top-level function/class definition as a named part.

    Each part's own portion is measured by re-running
    ``count_content_lines`` over JUST that part's own line range, so a
    docstring inside one definition is stripped consistently with how the
    whole-file quoted length was produced.

    Args:
        content: The refused file's full current text.

    Returns:
        Located parts, in file order. Empty when the file has no top-level
        def/class (e.g. a script made only of module-level statements) --
        the caller treats that identically to "nothing located".

    Raises:
        SyntaxError: *content* is not parseable Python. The caller is
            responsible for catching this per the repo's error-handling
            policy.
    """
    tree = ast.parse(content)
    lines = content.splitlines()
    parts: list[DescribedPart] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start, end = _python_part_bounds(node)
            segment = "\n".join(lines[start - 1 : end])
            portion = count_content_lines(segment)
            if portion > 0:
                parts.append(DescribedPart(name=node.name, portion=portion))
    return parts


def extract_sql_parts(content: str) -> list[DescribedPart]:
    """Locate every top-level ``CREATE <OBJECT> <name>`` statement as a part.

    A part spans from its own ``CREATE`` statement to the line before the
    next one (or end of file for the last one) -- the SQL analogue of a
    Python top-level definition's span.

    Args:
        content: The refused file's full current text.

    Returns:
        Located parts, in file order. Empty when no covered object
        statement is found.
    """
    lines = content.splitlines()
    matches = list(_SQL_OBJECT_RE.finditer(content))
    parts: list[DescribedPart] = []
    for index, match in enumerate(matches):
        start_line = content.count("\n", 0, match.start()) + 1
        end_line = (
            content.count("\n", 0, matches[index + 1].start())
            if index + 1 < len(matches)
            else len(lines)
        )
        segment = "\n".join(lines[start_line - 1 : end_line])
        portion = count_content_lines(segment)
        name = match.group("name").strip('"')
        if portion > 0:
            parts.append(DescribedPart(name=name, portion=portion))
    return parts


_EXTRACTORS_BY_EXTENSION = {
    ".py": extract_python_parts,
    ".sql": extract_sql_parts,
}


def extract_parts(filepath: str, content: str) -> list[DescribedPart]:
    """Dispatch to the extraction rule for *filepath*'s own extension.

    HOW a part is recognised is necessarily kind-specific (GE-127e-1's own
    it_requirements) -- this is the only place that varies by kind. What
    part NAMES and PORTIONS are produced is never a fixed table: every
    return value here comes from parsing *content* itself.

    Args:
        filepath: The refused file's path (used only to select the
            extractor by extension).
        content: The refused file's full current text.

    Returns:
        Located parts, in file order. Empty for an extension with no
        registered extractor.

    Raises:
        SyntaxError: *content* is not parseable per its extension's
            extractor. The caller is responsible for catching this.
    """
    extractor = _EXTRACTORS_BY_EXTENSION.get(Path(filepath).suffix.lower())
    if extractor is None:
        return []
    return extractor(content)


def _select_division(
    parts: list[DescribedPart],
) -> tuple[list[DescribedPart], list[DescribedPart]]:
    """Choose the whole-part boundary closest to an even split by length.

    The candidate set is exactly the boundaries BETWEEN consecutive parts --
    never a byte or line offset inside one -- so the chosen division always
    reconciles as two whole-part sides. This is deliberately NOT "cut at
    half the measured length": a fixed-fraction cut can fall inside a part,
    which is exactly GE-127e-1's second named mutation this selection must
    resist.

    Args:
        parts: At least two located parts, in file order.

    Returns:
        (left_parts, right_parts), a partition of *parts* at one boundary.
    """
    total = sum(part.portion for part in parts)
    cumulative = 0
    best_index = 1
    best_diff = None
    for index in range(1, len(parts)):
        cumulative += parts[index - 1].portion
        diff = abs(cumulative - (total - cumulative))
        if best_diff is None or diff < best_diff:
            best_diff = diff
            best_index = index
    return parts[:best_index], parts[best_index:]


def describe_file(filepath: str, content: str, quoted_length: int) -> FileDescription | None:
    """Build the per-file description for a file ALREADY judged over its limit.

    Args:
        filepath: The refused file's path (selects the per-kind extractor).
        content: The refused file's full current content -- already read
            once by the caller to measure it; no file read happens here.
        quoted_length: The measured length already quoted for this file in
            the refusal (via ``_file_size_ratchet.count_content_lines``).
            Portions and side lengths are produced by that same function so
            reconciliation is arithmetic, never a second counting rule.

    Returns:
        A FileDescription when at least one part is located and the located
        parts' portions sum to at least half of *quoted_length*. None
        otherwise -- an under-accounted or unparseable file is a
        could-not-be-described state (GE-127e-3-i's subject), so nothing is
        printed rather than an invented or padded description.
    """
    try:
        parts = extract_parts(filepath, content)
    except SyntaxError as exc:
        logger.warning("could not parse %s for a per-file description: %s", filepath, exc)
        return None

    if not parts:
        return None

    portion_sum = sum(part.portion for part in parts)
    if 2 * portion_sum < quoted_length:
        return None

    if len(parts) == 1:
        return FileDescription(parts=parts, single_part_name=parts[0].name)

    if portion_sum != quoted_length:
        # Partial coverage: a division cannot be reconciled against the
        # WHOLE file's quoted length without inventing content for the
        # uncovered remainder, so only the located parts are offered.
        return FileDescription(parts=parts)

    left, right = _select_division(parts)
    side_a = ([part.name for part in left], sum(part.portion for part in left))
    side_b = ([part.name for part in right], sum(part.portion for part in right))
    return FileDescription(parts=parts, side_a=side_a, side_b=side_b)


def format_description_lines(description: FileDescription) -> list[str]:
    """Render *description* into the printed-block lines the refusal appends.

    See this component's ``_ge_127e_1_fixture.py`` module docstring for the
    printed-block contract this formatting fixes exactly.

    Args:
        description: A non-None result from ``describe_file``.

    Returns:
        Lines to print, in order, with no trailing newline characters.
    """
    lines = ["   Parts:"]
    for part in description.parts:
        lines.append(f"     - {part.name}: {part.portion} lines")

    if description.single_part_name is not None:
        lines.append(
            f"   No division found: {description.single_part_name} accounts for the whole file."
        )
    elif description.side_a is not None and description.side_b is not None:
        names_a, length_a = description.side_a
        names_b, length_b = description.side_b
        lines.append("   Division:")
        lines.append(f"     Side A: {', '.join(names_a)} ({length_a} lines)")
        lines.append(f"     Side B: {', '.join(names_b)} ({length_b} lines)")

    return lines


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-14 [python-coder/GE-127e-1]: Initial authoring. Per-kind
  extraction (ast top-level def/class for .py, CREATE-statement spans for
  .sql), a closest-to-even division selection constrained to whole-part
  boundaries (never a fixed-fraction cut), and an under-half / unparseable
  floor that withholds the description rather than inventing or padding
  one. New sibling module inside templates/scripts/commit_guardian/ so no
  scripts/build_phases.py deploy-map entry is needed (build_commit_guardian
  copies the directory verbatim) and so check_file_size.py stays under its
  own 400-counted-line limit.
====================================================================
"""
