"""
MODULE: commit_guardian._file_size_measure.python_lines
GOAL: Find the uncounted regions of a Python file -- every comment and every
    string that stands alone as a statement -- from the standard library
    tokenizer of the RUNNING interpreter.
BUSINESS CONTEXT: GE-127d-3's rule (BrainCandy, 2026-10-16 and 2026-10-20): no
    comment counts toward a file's length, and neither does a string that is
    a statement on its own (docstring, bare string, trailing DECISION HISTORY
    block). A string that is assigned, passed, returned or part of a larger
    expression is code, and so is an f-string, because evaluating it runs the
    expressions inside it.
ARCHITECTURE: No second lexer and no fallback: only the token stream is read
    (statements are split at NEWLINE tokens and at top-level semicolons), so
    a file that tokenizes but does not parse is still measured. A tokenizer
    failure raises UnmeasurableContentError naming the running interpreter.
    Token types that only exist from Python 3.12 are looked up by name so
    this module imports cleanly on 3.10.
"""

from __future__ import annotations

import io
import re
import sys
import tokenize
from collections.abc import Iterator

from .errors import UnmeasurableContentError
from .spans import Range, line_starts, split_physical_lines

_IGNORED = frozenset(
    {tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER}
)
_PREFIX = re.compile(r"[A-Za-z]*")
_OPENERS = frozenset("([{")
_CLOSERS = frozenset(")]}")
_COMPOUND = frozenset("if elif else for while try except finally with def class async".split())


def _is_plain_string(token: tokenize.TokenInfo) -> bool:
    """True for a STRING token that is not an f-string (or t-string).

    From Python 3.12 an f-string is split into FSTRING_* tokens and never
    reaches here as a STRING; before 3.12 it is a STRING with an ``f`` prefix.
    """
    if token.type != tokenize.STRING:
        return False
    return not {"f", "t"} & set(_PREFIX.match(token.string).group(0).lower())


def _statements(
    tokens: list[tokenize.TokenInfo], body_starts: frozenset[tuple[int, int]] = frozenset()
) -> Iterator[list[tokenize.TokenInfo]]:
    """Yield the significant tokens of each statement, split at NEWLINE, top-level ';' and
    before a compound header's same-row body (*body_starts*, token start positions)."""
    pending: list[tokenize.TokenInfo] = []
    depth = 0
    for token in tokens:
        if token.type == tokenize.NEWLINE:
            if pending:
                yield pending
            pending, depth = [], 0
            continue
        if token.type in _IGNORED:
            continue
        if token.start in body_starts and pending:
            yield pending
            pending = []
        if token.type == tokenize.OP:
            depth += (token.string in _OPENERS) - (token.string in _CLOSERS)
            if token.string == ";" and depth <= 0:
                if pending:
                    yield pending
                pending = []
                continue
        pending.append(token)
    if pending:
        yield pending


def _is_standalone(group: list[tokenize.TokenInfo]) -> bool:
    """True when *group* is only plain string literals, optionally in balanced parentheses."""
    opens = 0
    while opens < len(group) and group[opens].type == tokenize.OP and group[opens].string == "(":
        opens += 1
    end = len(group)
    while end > opens and group[end - 1].type == tokenize.OP and group[end - 1].string == ")":
        end -= 1
    core = group[opens:end]
    return bool(core) and (len(group) - end) == opens and all(_is_plain_string(token) for token in core)


def _offset(starts: list[int], position: tuple[int, int]) -> int:
    """Convert a tokenizer ``(row, column)`` into an offset in the normalised text."""
    row, column = position
    return starts[row - 1] + column if row - 1 < len(starts) else starts[-1] + column


def _tokenize(text: str) -> list[tokenize.TokenInfo]:
    """Tokenize *text* with the running interpreter, or raise UnmeasurableContentError."""
    try:
        return list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, SyntaxError, ValueError) as exc:
        version = f"{sys.version_info.major}.{sys.version_info.minor}"
        detail = f"the running interpreter, Python {version}, could not tokenize it: {exc}"
        raise UnmeasurableContentError("Python", detail) from exc


def _statement_breaks(tokens: list[tokenize.TokenInfo]) -> list[tuple[int, int]]:
    """Start positions of statements that begin on the row of the one before them.

    A statement ends at a top-level ``;`` and at the ``:`` ending a compound
    header (``if x: y``); a lambda's own ``:`` is skipped. The next statement
    is a break only when its first token sits on the separator's row.
    """
    breaks: list[tuple[int, int]] = []
    statement = _Statement()
    pending_row: int | None = None
    for token in tokens:
        if token.type == tokenize.NEWLINE:
            statement, pending_row = _Statement(), None
            continue
        if token.type in _IGNORED:
            continue
        if pending_row == token.start[0]:
            breaks.append(token.start)
        pending_row = None
        if statement.ends_with(token):
            statement, pending_row = _Statement(depth=statement.depth), token.end[0]
    return breaks


class _Statement:
    """The state of the statement being read: bracket depth, open lambdas, first token."""

    __slots__ = ("depth", "first", "lambdas")

    def __init__(self, depth: int = 0) -> None:
        self.depth = depth
        self.lambdas = 0
        self.first: tokenize.TokenInfo | None = None

    def ends_with(self, token: tokenize.TokenInfo) -> bool:
        """Feed one significant token; True when it is a top-level ``;`` or a compound header's ``:``."""
        self.first = self.first or token
        if token.type == tokenize.NAME and token.string == "lambda" and self.depth <= 0:
            self.lambdas += 1
        if token.type != tokenize.OP:
            return False
        self.depth += (token.string in _OPENERS) - (token.string in _CLOSERS)
        if self.depth > 0 or token.string not in (":", ";"):
            return False
        if token.string == ";":
            return True
        if self.lambdas:
            self.lambdas -= 1
            return False
        return self.first.string in _COMPOUND


def python_lex(text: str) -> tuple[list[Range], list[int]]:
    """Return the uncounted ranges and the statement breaks of Python *text*.

    Raises:
        UnmeasurableContentError: the running interpreter's tokenizer rejects *text*.
    """
    tokens = _tokenize(text)
    starts = line_starts(split_physical_lines(text)) or [0]
    breaks = _statement_breaks(tokens)
    return _uncounted(tokens, starts, frozenset(breaks)), [_offset(starts, start) for start in breaks]


def python_ranges(text: str) -> list[Range]:
    """Return the uncounted ranges of Python *text*: comments and standalone strings.

    Args:
        text: The normalised file text.

    Returns:
        Sorted half-open ``(start, end)`` offsets.

    Raises:
        UnmeasurableContentError: the running interpreter's tokenizer rejects *text*.
    """
    return python_lex(text)[0]


def _uncounted(
    tokens: list[tokenize.TokenInfo], starts: list[int], body_starts: frozenset[tuple[int, int]]
) -> list[Range]:
    """The comment, standalone-string and ``;`` ranges of an already tokenized file.

    A ``;`` is only a separator, so it is cut from the key: ``a = 1; b = 2``
    keys exactly like the same two statements on two lines.
    """
    spans = [
        token
        for token in tokens
        if token.type == tokenize.COMMENT or (token.type == tokenize.OP and token.string == ";")
    ]
    for group in _statements(tokens, body_starts):
        if _is_standalone(group):
            # Only the string literals are uncounted: a wrapping parenthesis is a
            # token like any other, so a parenthesised multi-line standalone
            # string still counts its opening and closing parenthesis lines --
            # exactly what ast's Constant node span (parentheses excluded) says.
            spans.extend(token for token in group if token.type == tokenize.STRING)
    return sorted((_offset(starts, token.start), _offset(starts, token.end)) for token in spans)


"""
DECISION HISTORY
========================================================================
- 2026-10-20 15:19 [python-coder]: Initial authoring on the standard library tokenizer only. A
  parenthesised standalone string uncounts only its string tokens (the wrapping parentheses stay
  code), matching ast's Constant span; verified against ast+tokenize over all 2854 tracked .py
  files with zero disagreements. (#EPIC-FilesStayWorkable/GE-127d-3)
- 2026-10-23 [GE-127d-3-v]: python_lex also returns statement breaks from the same token stream: a
  statement after a top-level `;` or after a compound header's `:` on the same row (`x = 1; y = 2`,
  `if x: y`) counts as its own line. `match`/`case` are left out because they are soft keywords
  (`match: int = 1` is an annotation). (#EPIC-FilesStayWorkable/GE-127d-3)
"""
