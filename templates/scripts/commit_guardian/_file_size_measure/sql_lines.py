"""
MODULE: commit_guardian._file_size_measure.sql_lines
GOAL: Find the comments of a SQL file: ``--`` line comments and NESTED
    ``/* */`` block comments (PostgreSQL / T-SQL / SQL-standard behaviour),
    never one inside a '...' string (with '' doubling), an E'...' string
    (backslash escapes), a "..." identifier or a dollar-quoted body.
BUSINESS CONTEXT: GE-127d-3-i's decision: a PL/pgSQL body is code in the same
    language, so a genuine comment inside a dollar-quoted function body is a
    comment. Treating the whole body as one opaque string would reintroduce a
    restyle asymmetry inside every SQL function.
ARCHITECTURE: The body of ``$tag$ ... $tag$`` ends at the first matching tag
    found by a raw scan, exactly as PostgreSQL does, and only then is the
    body lexed as SQL. A body that cannot itself be lexed (a LANGUAGE
    plpython3u body with an unbalanced quote) is lexically still a closed
    string, so its lines count and nothing is INDETERMINATE; only a dollar
    quote that never closes fails. ``#`` is not a SQL comment.
"""

from __future__ import annotations

import logging
import re

from .errors import UnmeasurableContentError
from .spans import Range

_LOGGER = logging.getLogger(__name__)

_INTERESTING = re.compile(r"--|/\*|['\"$]")
_BLOCK_TOKEN = re.compile(r"/\*|\*/")
_STANDARD_STRING = re.compile(r"'(?:[^']|'')*'")
_ESCAPE_STRING = re.compile(r"'(?:[^'\\]|\\.|'')*'", re.DOTALL)
_IDENTIFIER = re.compile(r'"(?:[^"]|"")*"')
_DOLLAR_TAG = re.compile(r"\$(?:[A-Za-z_\u0080-\U0010ffff][\w\u0080-\U0010ffff]*)?\$")


class _Unlexable(Exception):
    """Internal: a region of the text could not be split into SQL tokens."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


def _block_comment(text: str, index: int, end: int, out: list[Range]) -> int:
    """Consume a (nested) block comment at *index*; return the offset after it."""
    position, depth = index + 2, 1
    while depth:
        match = _BLOCK_TOKEN.search(text, position, end)
        if not match:
            detail = "unterminated block comment"
            raise _Unlexable(detail)
        depth += 1 if match.group(0) == "/*" else -1
        position = match.end()
    out.append((index, position))
    return position


def _quoted(text: str, index: int, end: int) -> int:
    """Consume a '...' string or "..." identifier at *index*; return the offset after it."""
    if text[index] == '"':
        pattern, what = _IDENTIFIER, "quoted identifier"
    else:
        escaped = index > 0 and text[index - 1] in "eE" and (index < 2 or not (text[index - 2].isalnum() or text[index - 2] == "_"))
        pattern, what = (_ESCAPE_STRING if escaped else _STANDARD_STRING), "string literal"
    match = pattern.match(text, index, end)
    if not match:
        detail = f"unterminated {what}"
        raise _Unlexable(detail)
    return match.end()


def _dollar(text: str, index: int, end: int, out: list[Range]) -> int:
    """Consume a dollar-quoted string at *index* (or a lone ``$``); return the next offset."""
    if index > 0 and (text[index - 1].isalnum() or text[index - 1] in "_$"):
        return index + 1
    tag = _DOLLAR_TAG.match(text, index, end)
    if not tag:
        return index + 1
    close = text.find(tag.group(0), tag.end(), end)
    if close < 0:
        detail = "unterminated dollar-quoted string"
        raise _Unlexable(detail)
    body: list[Range] = []
    try:
        _lex(text, tag.end(), close, body)
    except _Unlexable as exc:
        line = text.count("\n", 0, index) + 1
        _LOGGER.warning(
            "dollar-quoted body at line %d cannot be lexed as SQL (%s); its lines are counted as a string",
            line,
            exc.detail,
        )
        body = []
    out.extend(body)
    return close + len(tag.group(0))


def _lex(text: str, index: int, end: int, out: list[Range]) -> None:
    """Lex ``text[index:end]``, appending every comment range to *out*."""
    while True:
        match = _INTERESTING.search(text, index, end)
        if not match:
            return
        index, marker = match.start(), match.group(0)
        if marker == "--":
            stop = text.find("\n", index, end)
            stop = end if stop < 0 else stop
            out.append((index, stop))
            index = stop
        elif marker == "/*":
            index = _block_comment(text, index, end, out)
        elif marker == "$":
            index = _dollar(text, index, end, out)
        else:
            index = _quoted(text, index, end)


def sql_ranges(text: str) -> list[Range]:
    """Return the comment ranges of SQL *text*.

    Args:
        text: The normalised file text.

    Returns:
        Sorted half-open ``(start, end)`` offsets of every comment.

    Raises:
        UnmeasurableContentError: an unterminated block comment, string,
            identifier or dollar quote.
    """
    ranges: list[Range] = []
    try:
        _lex(text, 0, len(text), ranges)
    except _Unlexable as exc:
        raise UnmeasurableContentError("SQL", exc.detail) from exc
    return sorted(ranges)


"""
DECISION HISTORY
========================================================================
- 2026-10-20 15:19 [python-coder]: Initial authoring. Dollar-quoted bodies are found by a raw scan
  for the closing tag and then lexed as SQL, so a genuine comment inside a PL/pgSQL body is a
  comment; an unlexable body stays a closed string. (#EPIC-FilesStayWorkable/GE-127d-3)
- 2026-10-21 [python-coder]: An unlexable dollar-quoted body now logs a WARNING naming the line
  and that its lines are counted as a string, instead of being swallowed silently.
  (#EPIC-FilesStayWorkable/GE-127d-3)
"""
