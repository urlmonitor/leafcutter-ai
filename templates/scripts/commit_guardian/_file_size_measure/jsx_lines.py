"""
MODULE: commit_guardian._file_size_measure.jsx_lines
GOAL: Walk one JSX element (tag, attributes, children, closing tag) on behalf
    of the JavaScript lexer, so JSX text -- which may carry an apostrophe, a
    double quote, ``//`` or ``/*`` -- is text and never a string or comment.
BUSINESS CONTEXT: leafcutter-web/app/architecture/page.tsx holds real JSX text
    with an apostrophe; a lexer without JSX states opens a string there and
    mis-measures every line up to the next quote. The only JSX comment is a
    ``{/* */}`` container, which is uncounted as a whole (braces included).
ARCHITECTURE: Called by c_family_lines.JsScanner at an expression-start ``<``.
    The parse is speculative: a start that is not a valid opening tag (a
    ``<T,>`` or ``<T extends X>`` type-parameter list, an unclosed element)
    returns None after rolling back every comment recorded meanwhile, and the
    caller reads ``<`` as an ordinary operator. ``{}`` containers re-enter the
    scanner's own ``scan_code``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .c_family_lines import JsScanner

_NAME = re.compile(r"[A-Za-z_$][\w$.:-]*")
_ATTRIBUTE = re.compile(r"[A-Za-z_$][\w$:.-]*")
_EXTENDS = re.compile(r"\s+extends\b")
_PLAIN_TEXT = re.compile(r"[^{<]+")
_SPACE = re.compile(r"\s+")


def scan_jsx_element(scanner: JsScanner, index: int) -> int | None:
    """Return the offset after the JSX element opening at *index*, or None.

    Args:
        scanner: The calling lexer (its ``ranges`` receive comments found
            inside attribute and child containers).
        index: Offset of the ``<`` character.

    Returns:
        The offset just past the element's closing tag (or ``/>``), or None
        when *index* does not start a well-formed element -- in which case
        nothing was recorded.
    """
    mark = len(scanner.ranges)
    end = _element(scanner, index)
    if end is None:
        del scanner.ranges[mark:]
    return end


def _element(scanner: JsScanner, index: int) -> int | None:
    text = scanner.text
    position = index + 1
    if text.startswith(">", position):
        return _children(scanner, position + 1)
    match = _NAME.match(text, position)
    if not match or _EXTENDS.match(text, match.end()):
        return None
    after_name = _skip_type_arguments(text, match.end())
    opened = None if after_name is None else _open_tag_end(scanner, after_name)
    if opened is None:
        return None
    end, self_closing = opened
    return end if self_closing else _children(scanner, end)


def _skip_type_arguments(text: str, position: int) -> int | None:
    """Skip a balanced ``<...>`` type-argument list right after a tag name.

    Returns *position* unchanged when none follows, the offset past the closing
    ``>`` (nested generics included, ``=>`` not counted), or None if unbalanced.
    """
    if not text.startswith("<", position):
        return position
    depth = 0
    while position < len(text):
        if text.startswith("=>", position):
            position += 2
            continue
        depth += {"<": 1, ">": -1}.get(text[position], 0)
        position += 1
        if depth == 0:
            return position
    return None


def _skip_space_and_comments(scanner: JsScanner, position: int) -> int:
    """Skip whitespace and any ``//`` or ``/* */`` comment between attributes."""
    text = scanner.text
    while position < scanner.size:
        match = _SPACE.match(text, position)
        if match:
            position = match.end()
        elif text.startswith("//", position):
            end = scanner._line_end(position)
            scanner.ranges.append((position, end))
            position = end
        elif text.startswith("/*", position):
            close = text.find("*/", position + 2)
            if close < 0:
                scanner.fail_unterminated("block comment", position)
            scanner.ranges.append((position, close + 2))
            position = close + 2
        else:
            break
    return position


def _attribute_value(scanner: JsScanner, position: int) -> int | None:
    """Skip an attribute value (quoted string or ``{}`` container) at *position*."""
    text = scanner.text
    position = _skip_space_and_comments(scanner, position)
    if position >= scanner.size:
        return None
    if text[position] in "\"'":
        close = text.find(text[position], position + 1)
        return None if close < 0 else close + 1
    if text[position] == "{":
        return scanner.scan_code(position + 1, until_brace=True)
    return None


def _open_tag_end(scanner: JsScanner, position: int) -> tuple[int, bool] | None:
    """Return ``(offset after the tag, self_closing)`` or None for an invalid tag."""
    text = scanner.text
    while position < scanner.size:
        position = _skip_space_and_comments(scanner, position)
        if text.startswith(">", position):
            return position + 1, False
        if text.startswith("/>", position):
            return position + 2, True
        if text.startswith("{", position):
            position = scanner.scan_code(position + 1, until_brace=True)
            continue
        match = _ATTRIBUTE.match(text, position)
        if not match:
            return None
        position = _skip_space_and_comments(scanner, match.end())
        if text.startswith("=", position):
            position = _attribute_value(scanner, position + 1)
            if position is None:
                return None
    return None


def _container(scanner: JsScanner, position: int) -> int:
    """Scan a child ``{}`` container; a comment-only one is uncounted whole."""
    mark = len(scanner.ranges)
    end = scanner.scan_code(position + 1, until_brace=True)
    found = scanner.ranges[mark:]
    if found:
        remainder, cursor = [], position + 1
        for begin, stop in found:
            remainder.append(scanner.text[cursor:begin])
            cursor = stop
        remainder.append(scanner.text[cursor : end - 1])
        if not "".join(remainder).strip():
            scanner.ranges[mark:] = [(position, end)]
    return end


def _children(scanner: JsScanner, position: int) -> int | None:
    """Walk children up to the closing tag; return the offset after it, or None."""
    text = scanner.text
    while position < scanner.size:
        plain = _PLAIN_TEXT.match(text, position)
        if plain:
            position = plain.end()
        elif text[position] == "{":
            position = _container(scanner, position)
        elif text.startswith("</", position):
            close = text.find(">", position)
            return None if close < 0 else close + 1
        elif _NAME.match(text, position + 1) or text.startswith(">", position + 1):
            nested = _element(scanner, position)
            if nested is None:
                return None
            position = nested
        else:
            position += 1
    return None


"""
DECISION HISTORY
========================================================================
- 2026-10-20 15:19 [python-coder]: Initial authoring. Speculative element parse with rollback so
  a type-parameter list (angle-bracket T-comma, or T-extends) or an unclosed element falls back to
  the less-than operator; a comment-only child container is uncounted whole.
  (#EPIC-FilesStayWorkable/GE-127d-3)
- 2026-10-21 [python-coder]: A balanced type-argument list after a tag name (nested generics
  included) is now accepted, so such an element no longer rolls back the enclosing fragment.
  (#EPIC-FilesStayWorkable/GE-127d-3)
"""
