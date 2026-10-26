"""
MODULE: commit_guardian._file_size_measure.spans
GOAL: Turn the uncounted character ranges a lexer found (comments, and Python
    strings standing alone as statements) into the ordered list of COUNTED
    physical lines of a file, each keyed by its non-comment text.
BUSINESS CONTEXT: GE-127d-3's line rule is stated once for every language: a
    physical line counts only when it carries a code token outside every
    uncounted range; a whitespace-only line never counts (BrainCandy,
    2026-10-21). Keeping that rule in one place is what makes the measured length
    and the added-lines diff (GE-127d-3-iv) come from the same pass.
ARCHITECTURE: Shared by every lexer module. A lexer returns half-open
    ``(start, end)`` offsets into the NORMALISED text; this module owns the
    physical-line split (LF and CRLF identical, a missing final newline
    irrelevant) so the backstop's total line count uses the very same split.
"""

from __future__ import annotations

from bisect import bisect_right

Range = tuple[int, int]
Break = tuple[int, int]

_BOM = chr(0xFEFF)


def normalise(content: str) -> str:
    """Return *content* with CRLF turned into LF and a leading BOM removed."""
    text = content.replace("\r\n", "\n")
    return text[1:] if text.startswith(_BOM) else text


def split_physical_lines(text: str) -> list[str]:
    """Split *text* into physical lines; a trailing newline adds no empty line."""
    lines = text.replace("\r\n", "\n").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def line_starts(lines: list[str]) -> list[int]:
    """Return the offset at which each line of *lines* starts in the joined text."""
    starts: list[int] = []
    offset = 0
    for line in lines:
        starts.append(offset)
        offset += len(line) + 1
    return starts


def _mask(line: str, removals: list[Range]) -> str:
    """Return *line* with every ``(lo, hi)`` column range cut out."""
    pieces: list[str] = []
    position = 0
    for low, high in sorted(removals):
        pieces.append(line[position:low])
        position = max(position, high)
    pieces.append(line[position:])
    return "".join(pieces)


def _collect_removals(lines: list[str], ranges: list[Range]) -> tuple[dict[int, list[Range]], set[int]]:
    """Map each row to the column ranges cut from it, and note every row touched."""
    starts = line_starts(lines)
    removals: dict[int, list[Range]] = {}
    touched: set[int] = set()
    for begin, end in ranges:
        if end <= begin:
            continue
        first = bisect_right(starts, begin) - 1
        last = min(bisect_right(starts, end - 1) - 1, len(lines) - 1)
        for row in range(first, last + 1):
            low = max(begin - starts[row], 0)
            high = min(end - starts[row], len(lines[row]))
            removals.setdefault(row, []).append((low, max(low, high)))
            touched.add(row)
    return removals, touched


def _collect_breaks(lines: list[str], breaks: list[Break]) -> dict[int, dict[int, int]]:
    """Map each row to ``{column: indent step}`` for every further statement starting on it."""
    starts = line_starts(lines)
    columns: dict[int, dict[int, int]] = {}
    for offset, step in breaks:
        row = bisect_right(starts, offset) - 1
        if 0 <= row < len(lines) and 0 < offset - starts[row] < len(lines[row]):
            columns.setdefault(row, {})[offset - starts[row]] = step
    return columns


def _step(indent: str, step: int, unit: str) -> str:
    """*indent* one *unit* deeper (step 1), shallower (step -1) or unchanged."""
    if step > 0:
        return indent + unit
    if step < 0 and indent.endswith(unit):
        return indent[: -len(unit)]
    return indent


def _pieces(line: str, removals: list[Range], cuts: dict[int, int], unit: str) -> list[str]:
    """Split *line* at *cuts* and mask each piece, keyed with the indentation it would have alone."""
    indent = line[: len(line) - len(line.lstrip())]
    bounds = [0, *sorted(cuts), len(line)]
    pieces: list[str] = []
    for index, (low, high) in enumerate(zip(bounds, bounds[1:], strict=False)):
        shifted = [(max(a, low) - low, min(b, high) - low) for a, b in removals if a < high and b > low]
        masked = _mask(line[low:high], shifted)
        if index:
            indent = _step(indent, cuts[low], unit)
        pieces.append(masked if index == 0 else indent + masked.strip())
    return pieces


def counted_keys(text: str, ranges: list[Range], breaks: list[Break] | None = None, unit: str = "    ") -> list[str]:
    """Return the key of every COUNTED line of *text*, in order.

    Args:
        text: The normalised file text.
        ranges: Half-open offsets of every uncounted region.
        breaks: ``(offset, step)`` for each further statement starting on a
            line that already holds one (GE-127d-3-v). The line is counted
            once per statement; each piece is keyed as if it stood on its own
            line, its indentation moved by ``step`` units (1 for a block or
            compound body opened on the line, -1 for a closing brace or
            keyword, 0 otherwise) (GE-127d-3-vi).
        unit: One indentation level in the language (four spaces in Python,
            two in the JavaScript family).

    Returns:
        One entry per counted line (or statement piece): the line with its
        uncounted regions cut out and trailing whitespace stripped. A line
        holding no token outside every region -- whitespace-only anywhere
        (between code, inside a comment, a standalone string or a used
        string) or wholly inside a region -- is never counted.
    """
    lines = split_physical_lines(text)
    removals, _touched = _collect_removals(lines, ranges)
    cuts = _collect_breaks(lines, breaks or [])
    keys: list[str] = []
    for row, line in enumerate(lines):
        for masked in _pieces(line, removals.get(row, []), cuts.get(row, {}), unit):
            if masked.strip():
                keys.append(masked.rstrip())
    return keys


"""
DECISION HISTORY
========================================================================
- 2026-10-20 15:19 [python-coder]: Initial authoring. The line rule lives here once for every
  language, and the same pass yields the keys the added-lines diff compares, so a restyle of a
  comment never changes a key. (#EPIC-FilesStayWorkable/GE-127d-3)
- 2026-10-21 [python-coder]: Blank lines never count (BrainCandy decision). A line is counted only
  when a code token survives outside the uncounted ranges; a whitespace-only line is never counted
  or keyed, anywhere. This supersedes the 2026-10-20 rule, under which a whitespace-only line
  outside every range counted. (#EPIC-FilesStayWorkable/GE-127d-3)
- 2026-10-23 [GE-127d-3-v]: counted_keys takes the lexer's statement breaks and counts a line once
  per statement it holds. Each later piece is keyed with the line's indentation, so `a(); b();` and
  the same two statements on two lines yield identical keys: joining or splitting statements moves
  neither the measured length nor the added-lines diff. (#EPIC-FilesStayWorkable/GE-127d-3)
- 2026-10-25 [GE-127d-3-vi]: A break carries an indent step. A piece after a compound header or an
  opening block brace is keyed one unit deeper, a closing brace one unit shallower, so `if x: y` and
  `if (x) { a(); }` key exactly like their expanded forms and joining or splitting them adds 0 to the
  repayment diff. (#EPIC-FilesStayWorkable/GE-127d-3)
"""
