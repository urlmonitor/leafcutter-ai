"""
MODULE: commit_guardian._file_size_measure.c_family_lines
GOAL: Find the comments of a JavaScript, ES-module, TypeScript or TSX file
    with a small hand-written lexer, so a comment marker inside a string,
    template literal, regular expression or JSX text is never mistaken for a
    comment (GE-127d-3-i's KI-CG-20261009 defect, in its home language).
BUSINESS CONTEXT: No standard-library tokenizer exists for these languages,
    and a language-blind ``/\\*.*?\\*/`` swallowed hundreds of real code lines.
    The lexer tracks code, line and block comments, quoted strings, template
    literals with a ``${}`` nesting stack, regular-expression literals with
    character classes, and (through jsx_lines) JSX element states.
ARCHITECTURE: ``JsScanner.scan_code`` is re-entered for every ``${}`` and JSX
    ``{}`` container, so each re-entry owns its own brace depth, parenthesis
    stack and previous-token kind. The previous significant token decides
    regex versus division; an if / while / for / with header ``)`` allows a
    regex to follow. Only an unterminated block comment or template literal
    is a tokenization failure -- an unterminated quoted string ends at its
    line, as the TypeScript scanner treats it.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import NoReturn

from .errors import UnmeasurableContentError
from .jsx_lines import scan_jsx_element
from .spans import Range

_IDENT = re.compile(r"[A-Za-z_$\u0080-\U0010ffff][\w$\u0080-\U0010ffff]*")
_NUMBER = re.compile(r"\.?\d(?:[eE][+-]|[\w.])*")
_SPACE = re.compile(r"[\s﻿]+")
_FLAGS = re.compile(r"[A-Za-z]*")
_NOT_A_STATEMENT = frozenset("\n})];,")
_REGEX_AFTER_WORDS = frozenset(
    "return typeof instanceof in of new delete void throw case do else yield await".split()
)
_CONTROL_HEADERS = frozenset({"if", "while", "for", "with"})
_EXPRESSION_START = frozenset({"start", "op", "open", "kw", "ctrl", "block"})
_EXPRESSION_END = frozenset({"ident", "num", "close", "str", "tmpl", "regex", "jsx"})


class _State:
    """Per-``scan_code`` context: previous token kind, last word, braces, parens."""

    __slots__ = ("brace_marks", "depth", "kind", "parens", "word")

    def __init__(self) -> None:
        self.kind = "start"
        self.word = ""
        self.depth = 0
        self.parens: list[bool] = []
        # len(parens) at each open brace: a ';' is a statement separator only when no
        # parenthesis opened since the innermost brace is still open.
        self.brace_marks: list[int] = []


class JsScanner:
    """Single-pass comment finder for the JavaScript / TypeScript family."""

    def __init__(self, text: str, *, jsx: bool, language: str) -> None:
        self.text = text
        self.size = len(text)
        self.jsx = jsx
        self.language = language
        self.ranges: list[Range] = []
        self.breaks: list[int] = []
        self._dispatch: dict[str, Callable[[int, _State], int]] = {
            ";": self._semicolon,
            "/": self._slash,
            '"': self._quoted,
            "'": self._quoted,
            "`": self._template,
            "(": self._open_paren,
            ")": self._close_paren,
            "[": self._open_bracket,
            "]": self._close_bracket,
            "{": self._open_brace,
            "<": self._less_than,
            "+": self._plus_minus,
            "-": self._plus_minus,
        }

    def fail_unterminated(self, what: str, start: int) -> NoReturn:
        """Raise the could-not-measure failure for an unterminated *what* begun at *start*."""
        line = self.text.count("\n", 0, start) + 1
        detail = f"unterminated {what} starting at line {line}"
        raise UnmeasurableContentError(self.language, detail)

    def run(self) -> list[Range]:
        """Scan the whole text and return the sorted comment ranges."""
        start = 0
        if self.text.startswith("#!"):
            start = self._line_end(0)
            self.ranges.append((0, start))
        self.scan_code(start, until_brace=False)
        return sorted(self.ranges)

    def _line_end(self, index: int) -> int:
        found = self.text.find("\n", index)
        return self.size if found < 0 else found

    def scan_code(self, index: int, *, until_brace: bool) -> int:
        """Scan code from *index*; return the offset after the closing ``}`` or the end."""
        state = _State()
        text = self.text
        while index < self.size:
            char = text[index]
            if char == "}":
                if state.depth == 0 and until_brace:
                    return index + 1
                state.depth = max(0, state.depth - 1)
                if state.brace_marks:
                    state.brace_marks.pop()
                state.kind = "block"
                index += 1
                continue
            handler = self._dispatch.get(char)
            if handler is not None:
                index = handler(index, state)
            else:
                index = self._other(index, state)
        return index

    def _other(self, index: int, state: _State) -> int:
        """Whitespace, identifiers, numbers and plain punctuation."""
        text = self.text
        match = _SPACE.match(text, index)
        if match:
            return match.end()
        match = _IDENT.match(text, index)
        if match:
            word = match.group(0)
            after_dot = index > 0 and text[index - 1] == "."
            state.word = word
            state.kind = "kw" if word in _REGEX_AFTER_WORDS and not after_dot else "ident"
            return match.end()
        match = _NUMBER.match(text, index)
        if match:
            state.kind = "num"
            return match.end()
        state.kind = "op"
        return index + 1

    def _slash(self, index: int, state: _State) -> int:
        text = self.text
        following = text[index + 1 : index + 2]
        if following == "/":
            end = self._line_end(index)
            self.ranges.append((index, end))
            return end
        if following == "*":
            close = text.find("*/", index + 2)
            if close < 0:
                self.fail_unterminated("block comment", index)
            self.ranges.append((index, close + 2))
            return close + 2
        if state.kind in _EXPRESSION_START:
            end = self._regex_end(index)
            if end:
                state.kind = "regex"
                return end
        state.kind = "op"
        return index + 1

    def _regex_end(self, index: int) -> int:
        """Offset after a regex literal opening at *index*, or 0 if it is not one."""
        text = self.text
        position, in_class = index + 1, False
        while position < self.size:
            char = text[position]
            if char == "\n":
                return 0
            if char == "\\":
                if text[position + 1 : position + 2] == "\n":
                    return 0
                position += 2
                continue
            if char == "[":
                in_class = True
            elif char == "]":
                in_class = False
            elif char == "/" and not in_class:
                return _FLAGS.match(text, position + 1).end()
            position += 1
        return 0

    def _quoted(self, index: int, state: _State) -> int:
        text = self.text
        quote = text[index]
        position = index + 1
        state.kind = "str"
        while position < self.size:
            char = text[position]
            if char == "\\":
                position += 2
                continue
            if char == quote:
                return position + 1
            if char == "\n":
                return position
            position += 1
        return self.size

    def _template(self, index: int, state: _State) -> int:
        text = self.text
        position = index + 1
        while position < self.size:
            char = text[position]
            if char == "\\":
                position += 2
            elif char == "`":
                state.kind = "tmpl"
                return position + 1
            elif char == "$" and text.startswith("{", position + 1):
                position = self.scan_code(position + 2, until_brace=True)
            else:
                position += 1
        return self.fail_unterminated("template literal", index)

    def _semicolon(self, index: int, state: _State) -> int:
        """A ``;`` outside parentheses followed, on its line, by another statement is a break."""
        state.kind = "op"
        if len(state.parens) == (state.brace_marks[-1] if state.brace_marks else 0):
            following = index + 1
            while following < self.size and self.text[following] in " \t":
                following += 1
            rest = self.text[following : following + 2]
            if rest and rest[0] not in _NOT_A_STATEMENT and rest not in ("//", "/*"):
                self.breaks.append(following)
        return index + 1

    def _open_paren(self, index: int, state: _State) -> int:
        state.parens.append(state.kind == "ident" and state.word in _CONTROL_HEADERS)
        state.kind = "open"
        return index + 1

    def _close_paren(self, index: int, state: _State) -> int:
        control = state.parens.pop() if state.parens else False
        state.kind = "ctrl" if control else "close"
        return index + 1

    def _open_bracket(self, index: int, state: _State) -> int:
        state.kind = "open"
        return index + 1

    def _close_bracket(self, index: int, state: _State) -> int:
        state.kind = "close"
        return index + 1

    def _open_brace(self, index: int, state: _State) -> int:
        state.depth += 1
        state.brace_marks.append(len(state.parens))
        state.kind = "open"
        return index + 1

    def _less_than(self, index: int, state: _State) -> int:
        if self.jsx and state.kind in _EXPRESSION_START:
            end = scan_jsx_element(self, index)
            if end is not None:
                state.kind = "jsx"
                return end
        state.kind = "op"
        return index + 1

    def _plus_minus(self, index: int, state: _State) -> int:
        doubled = self.text.startswith(self.text[index] * 2, index)
        if doubled and state.kind in _EXPRESSION_END:
            return index + 2
        state.kind = "op"
        return index + (2 if doubled else 1)


def js_ranges(text: str, *, jsx: bool, language: str) -> list[Range]:
    """Return the comment ranges of JavaScript/TypeScript *text*.

    Args:
        text: The normalised file text.
        jsx: Whether JSX elements are recognised (on for .js, .mjs and .tsx;
            off for .ts, where ``<T>expr`` is a type assertion).
        language: The language name used in a failure's reason.

    Returns:
        Sorted half-open ``(start, end)`` offsets of every comment.

    Raises:
        UnmeasurableContentError: an unterminated block comment or template literal.
    """
    return js_lex(text, jsx=jsx, language=language)[0]


def js_lex(text: str, *, jsx: bool, language: str) -> tuple[list[Range], list[int]]:
    """Return the comment ranges and the statement breaks of JavaScript/TypeScript *text*.

    A break is the offset of a statement that follows a ``;`` (outside any
    parentheses, so a ``for (;;)`` header is one statement) on the same line.

    Raises:
        UnmeasurableContentError: an unterminated block comment or template literal.
    """
    scanner = JsScanner(text, jsx=jsx, language=language)
    return scanner.run(), sorted(scanner.breaks)


"""
DECISION HISTORY
========================================================================
- 2026-10-20 15:19 [python-coder]: Initial authoring of the hand-written JS/TS lexer. Measured
  against the TypeScript compiler's comment ranges over all 203 tracked JS/MJS/TS/TSX files: every
  file agrees except the 35 .tsx files holding a standalone JSX comment container, which this
  lexer uncounts whole (braces included) per GE-127d-3 while the compiler oracle counts the two
  brace characters as code. (#EPIC-FilesStayWorkable/GE-127d-3)
- 2026-10-23 [GE-127d-3-v]: The scanner records statement breaks: a `;` outside parentheses
  followed on its line by anything but a closer, a separator, a comment or the line end. js_lex
  returns them with the comment ranges, so `a(); b();` counts two lines. "Outside parentheses"
  means outside any parenthesis opened since the innermost brace, so a callback body inside a call
  (`xs.forEach((x) => { a(x); b(x); })`) splits while a `for (;;)` header does not.
  (#EPIC-FilesStayWorkable/GE-127d-3)
"""
