"""
MODULE: scripts/build_orchestration/_wvr_sql_objects.py
GOAL: Read the CREATE FUNCTION / PROCEDURE statements of a SQL source text: which database
    objects it defines, in which schema (when qualified) and with which body.
BUSINESS CONTEXT: TQ-500g-2-i. The wrong-version check compares what the catalogue holds with
    the two forms of each object, so a phantom object (a CREATE inside a comment, a string or a
    dollar-quoted body) would make a valid run read as ambiguous or invalid.
ARCHITECTURE: Pure text functions, no I/O. :func:`scan` blanks comments, single-quoted strings
    and dollar-quoted regions (nested block comments included) and records the dollar-quoted
    bodies; the CREATE pattern then runs on the blanked text only. A quoted name keeps its
    exact case; an unquoted one folds ASCII letters only, as PostgreSQL does.
"""

from __future__ import annotations

import re
import string

_TOKEN = re.compile(r"--[^\n]*|/\*|(?<![\w$])[Ee]'(?:[^'\\]|\\.|'')*'|'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"|(?<![\w$])\$(?:[A-Za-z_]\w*)?\$")
_BLOCK = re.compile(r"/\*|\*/")
_WORD = r"[^\W\d][\w$]*"
_NAME = rf"(?:\"(?:[^\"]|\"\")*\"|{_WORD})"
_CREATE = re.compile(rf"\bcreate\s+(?:or\s+replace\s+)?(?:function|procedure)\s+({_NAME}(?:\s*\.\s*{_NAME})*)", re.I)
_PART = re.compile(rf"\"((?:[^\"]|\"\")*)\"|({_WORD})")
_PAREN = re.compile(r"\"(?:[^\"]|\"\")*\"|[()]")
_AS = re.compile(r"\bas\b", re.I)
_ASCII_UPPER = str.maketrans(string.ascii_uppercase, string.ascii_lowercase)


class ObjectsError(ValueError):
    """The database objects of a source text cannot be identified unambiguously."""


def normal(text: str) -> str:
    """The whitespace-insensitive normal form of a stored body."""
    return " ".join(text.split())


def _block_end(text: str, pos: int) -> int:
    """The index just after the (nestable) block comment whose opener ends at *pos*."""
    depth = 1
    while depth:
        hit = _BLOCK.search(text, pos)
        if hit is None:
            return len(text)
        depth += 1 if hit.group(0) == "/*" else -1
        pos = hit.end()
    return pos


def scan(text: str) -> tuple[str, list[tuple[int, int, str]]]:
    """Blank the non-code regions of *text*; return ``(blanked text, [(start, end, dollar body)])``.

    Raises:
        ObjectsError: A dollar-quoted region is never closed.
    """
    chars, bodies, pos = list(text), [], 0
    while (hit := _TOKEN.search(text, pos)) is not None:
        token = hit.group(0)
        if token.startswith('"'):
            pos = hit.end()
            continue
        end = hit.end()
        if token == "/*":
            end = _block_end(text, end)
        elif token.startswith("$"):
            close = text.find(token, end)
            if close < 0:
                raise ObjectsError("")
            bodies.append((hit.start(), close + len(token), text[end:close]))
            end = close + len(token)
        chars[hit.start():end] = " " * (end - hit.start())
        pos = end
    return "".join(chars), bodies


def _parts(token: str) -> list[str]:
    """The name parts of a (possibly qualified) CREATE name, folded the way PostgreSQL folds them."""
    return [(m.group(1).replace('""', '"') if m.group(1) is not None else m.group(2).translate(_ASCII_UPPER)) for m in _PART.finditer(token)]


def _signature_end(blanked: str, pos: int) -> int:
    """The index just after the parameter list that starts at or after *pos*; ``-1`` when there is none."""
    depth = 0
    for hit in _PAREN.finditer(blanked, pos):
        if hit.group(0) == "(":
            depth += 1
        elif hit.group(0) == ")":
            depth -= 1
            if depth == 0:
                return hit.end()
        if depth == 0:
            return -1
    return -1


def _body_of(text: str, blanked: str, bodies: list[tuple[int, int, str]], start: int, limit: int) -> str | None:
    """The dollar-quoted body that follows the AS keyword after the signature; ``None`` when it is not one."""
    after = _signature_end(blanked, start)
    keyword = _AS.search(blanked, after, limit) if after >= 0 else None
    if keyword is None:
        return None
    pos = keyword.end()
    while pos < len(text) and text[pos].isspace():
        pos += 1
    return next((b[2] for b in bodies if b[0] == pos and b[1] <= limit), None)


def parse_definitions(text: str) -> dict[str, tuple[str, str]]:
    """Return ``{object name: (schema or "", normal form of its dollar-quoted body)}`` for *text*.

    Raises:
        ObjectsError: No CREATE FUNCTION/PROCEDURE, a name twice, or a body that does not follow AS
            as a dollar-quoted string.
    """
    blanked, bodies = scan(text)
    matches = list(_CREATE.finditer(blanked))
    found: dict[str, tuple[str, str]] = {}
    for i, match in enumerate(matches):
        parts = _parts(match.group(1))
        name, schema = parts[-1], (parts[-2] if len(parts) > 1 else "")
        limit = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = _body_of(text, blanked, bodies, match.end(), limit)
        if body is None or name in found:
            raise ObjectsError(name)
        found[name] = (schema, normal(body))
    if not found:
        raise ObjectsError("")
    return found


def parse_objects(text: str) -> dict[str, str]:
    """Return ``{object name: normal form of its dollar-quoted body}`` of the CREATE statements in *text*.

    Raises:
        ObjectsError: See :func:`parse_definitions`.
    """
    return {name: body for name, (_schema, body) in parse_definitions(text).items()}
