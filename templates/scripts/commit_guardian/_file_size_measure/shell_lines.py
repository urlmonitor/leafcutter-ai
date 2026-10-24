"""
MODULE: commit_guardian._file_size_measure.shell_lines
GOAL: Find the comments of a shell script: a ``#`` that starts a word (at line
    start or after unquoted whitespace, ``;``, ``&``, ``|``, ``(`` or ``)``).
BUSINESS CONTEXT: A ``#`` is code inside '...', "...", $'...', backticks,
    ``$(...)``, ``${...}``, a here-document body and mid-word (``a#b``, ``$#``,
    ``${#x}``, ``16#ff``). There are no block comments and no triple quotes,
    so none of those forms may ever be read as one (GE-127d-3-i).
ARCHITECTURE: One scanner over the normalised text. Here-document operators
    (``<<WORD``, ``<<-WORD``, quoted or backslashed WORD, several per line;
    ``<<<`` here-strings excluded; ``<<`` inside ``(( ))``, ``$(( ))`` and
    ``[[ ]]`` is a shift or comparison, not an operator) queue their
    terminator, and the bodies are
    consumed, line by line, at the next newline. An unterminated quote or
    substitution is a tokenization failure; an unterminated here-document
    simply runs to the end of the file, as the shell does.
"""

from __future__ import annotations

import re
from typing import NoReturn

from .errors import UnmeasurableContentError
from .spans import Range

_HEREDOC_WORD = re.compile(r"""[ \t]*(?:'([^']*)'|"([^"]*)"|\\?([^\s;&|()<>'"\\]+))""")
_SEPARATORS = frozenset(";&|()")


class _ShellScanner:
    """Single-pass scanner collecting comment ranges of shell text."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.size = len(text)
        self.ranges: list[Range] = []
        self.heredocs: list[tuple[str, bool]] = []
        self.in_test = False

    def fail(self, what: str, start: int) -> NoReturn:
        """Raise the could-not-measure failure for an unterminated *what*."""
        line = self.text.count("\n", 0, start) + 1
        detail = f"unterminated {what} starting at line {line}"
        raise UnmeasurableContentError("shell", detail)

    def run(self) -> list[Range]:
        """Scan the whole text and return the comment ranges."""
        text, index, word_start = self.text, 0, True
        while index < self.size:
            char = text[index]
            if char == "\n":
                index = self._heredoc_bodies(index + 1)
                word_start, self.in_test = True, False
            elif char in " \t":
                index, word_start = index + 1, True
            elif char == "#" and word_start:
                end = text.find("\n", index)
                end = self.size if end < 0 else end
                self.ranges.append((index, end))
                index = end
            else:
                index, word_start = self._token(index)
        return self.ranges

    def _token(self, index: int) -> tuple[int, bool]:
        """Consume one non-space token start; return ``(next offset, word_start)``."""
        text, char = self.text, self.text[index]
        if char == "\\":
            return min(index + 2, self.size), text[index + 1 : index + 2] == "\n"
        if char == "'":
            close = text.find("'", index + 1)
            if close < 0:
                self.fail("single-quoted string", index)
            return close + 1, False
        if char == '"':
            return self._double_quoted(index), False
        if char == "`":
            return self._backtick(index), False
        if char == "$":
            return self._dollar(index), False
        if char == "<":
            return self._redirect(index), False
        if char == "(" and text.startswith("((", index):
            return self._balanced(index, "(", ")"), False
        if char == "[" and text.startswith("[[", index):
            self.in_test = True
        elif char == "]" and text.startswith("]]", index):
            self.in_test = False
        return index + 1, char in _SEPARATORS

    def _double_quoted(self, index: int) -> int:
        text, position = self.text, index + 1
        while position < self.size:
            char = text[position]
            if char == '"':
                return position + 1
            if char == "\\":
                position += 2
            elif char == "$" and text[position + 1 : position + 2] in ("(", "{"):
                position = self._dollar(position)
            elif char == "`":
                position = self._backtick(position)
            else:
                position += 1
        return self.fail("double-quoted string", index)

    def _backtick(self, index: int) -> int:
        text, position = self.text, index + 1
        while position < self.size:
            if text[position] == "`":
                return position + 1
            position += 2 if text[position] == "\\" else 1
        return self.fail("backtick substitution", index)

    def _dollar(self, index: int) -> int:
        following = self.text[index + 1 : index + 2]
        if following == "(":
            return self._balanced(index + 1, "(", ")")
        if following == "{":
            return self._balanced(index + 1, "{", "}")
        if following == "'":
            return self._ansi_c_quoted(index + 1)
        return min(index + 2, self.size)

    def _ansi_c_quoted(self, index: int) -> int:
        text, position = self.text, index + 1
        while position < self.size:
            if text[position] == "'":
                return position + 1
            position += 2 if text[position] == "\\" else 1
        return self.fail("ANSI-C quoted string", index)

    def _balanced(self, index: int, opener: str, closer: str) -> int:
        """Skip a balanced ``$( )`` or ``${ }``, quote-aware, starting at its opener."""
        text, position, depth = self.text, index, 0
        while position < self.size:
            char = text[position]
            if char == opener:
                depth += 1
            elif char == closer:
                depth -= 1
                if depth == 0:
                    return position + 1
            elif char == "'":
                close = text.find("'", position + 1)
                if close < 0:
                    self.fail("single-quoted string", position)
                position = close
            elif char == '"':
                position = self._double_quoted(position) - 1
            elif char == "\\":
                position += 1
            position += 1
        return self.fail("substitution", index)

    def _redirect(self, index: int) -> int:
        """Consume ``<``; queue the terminator of a ``<<`` here-document operator."""
        text = self.text
        if text.startswith("<<<", index):
            return index + 3
        if self.in_test or not text.startswith("<<", index):
            return index + 1
        position = index + 2
        strip_tabs = text.startswith("-", position)
        position += 1 if strip_tabs else 0
        match = _HEREDOC_WORD.match(text, position)
        if not match:
            return index + 2
        word = next(group for group in match.groups() if group is not None)
        self.heredocs.append((word, strip_tabs))
        return match.end()

    def _heredoc_bodies(self, index: int) -> int:
        """Consume every queued here-document body starting at *index*."""
        text = self.text
        for word, strip_tabs in self.heredocs:
            while index < self.size:
                end = text.find("\n", index)
                end = self.size if end < 0 else end
                line = text[index:end]
                index = min(end + 1, self.size)
                if (line.lstrip("\t") if strip_tabs else line) == word:
                    break
        self.heredocs.clear()
        return index


def shell_ranges(text: str) -> list[Range]:
    """Return the comment ranges of shell *text*.

    Args:
        text: The normalised file text.

    Returns:
        Sorted half-open ``(start, end)`` offsets of every comment.

    Raises:
        UnmeasurableContentError: an unterminated quote or substitution.
    """
    return _ShellScanner(text).run()


"""
DECISION HISTORY
========================================================================
- 2026-10-20 15:19 [python-coder]: Initial authoring. A hash starts a comment only at the start of
  a word; here-document bodies are consumed line by line at the next newline so body lines
  beginning with a hash count as code. (#EPIC-FilesStayWorkable/GE-127d-3)
- 2026-10-21 [python-coder]: A double less-than inside (( )), $(( )) or [[ ]] is a shift or
  comparison, never a here-document operator, so later lines are no longer swallowed.
  (#EPIC-FilesStayWorkable/GE-127d-3)
"""
