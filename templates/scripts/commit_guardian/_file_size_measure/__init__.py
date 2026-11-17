"""
MODULE: commit_guardian._file_size_measure
GOAL: The ONE measure of a covered file's length: no comment of any style and
    no Python string standing alone as a statement counts, and blank lines
    never count anywhere. Every other line of code and of a used string does,
    once per statement it holds (GE-127d-3-v), so joining statements onto one
    line shortens nothing.
BUSINESS CONTEXT: GE-127d-3 (BrainCandy, 2026-10-16 and 2026-10-20). The
    quoted length must be a number a formatting choice cannot move: rewriting
    ``//`` runs as ``/* */`` once cleared a growth ratchet on five workflow
    templates while every file grew raw. A per-language tokenizer, not a
    delimiter regex, is what makes the strip lexically correct.
ARCHITECTURE: Sub-package of templates/scripts/commit_guardian/, deployed by
    build_commit_guardian's rglob with no deploy-map entry. Each lexer finds
    the uncounted character ranges of its language; spans.counted_keys turns
    them into the ordered counted lines, so the measured length and the
    added-lines diff (GE-127d-3-iv) come from the same pass
    (``len(counted_line_keys(...)) == measure_lines(...)``). The language is
    chosen from the file's extension; an extension with no tokenizer, or
    content a tokenizer rejects, raises UnmeasurableContentError -- never a
    raw count and never zero.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from pathlib import Path

from .c_family_lines import js_lex
from .errors import UnmeasurableContentError
from .python_lines import python_lex
from .shell_lines import shell_lex
from .spans import Break, Range, counted_keys, normalise, split_physical_lines
from .sql_lines import sql_lex

__all__ = [
    "SUPPORTED_EXTENSIONS",
    "UnmeasurableContentError",
    "counted_line_keys",
    "extension_of",
    "language_name",
    "measure_lines",
    "total_physical_lines",
]

_Lexer = Callable[[str], tuple[list[Range], list[Break]]]

# (language name, lexer, one indentation level used to key a split-off statement)
_LEXERS: dict[str, tuple[str, _Lexer, str]] = {
    ".py": ("Python", python_lex, "    "),
    ".sql": ("SQL", sql_lex, "  "),
    ".sh": ("shell", shell_lex, "  "),
    ".js": ("JavaScript", partial(js_lex, jsx=True, language="JavaScript"), "  "),
    ".mjs": ("JavaScript", partial(js_lex, jsx=True, language="JavaScript"), "  "),
    ".ts": ("TypeScript", partial(js_lex, jsx=False, language="TypeScript"), "  "),
    ".tsx": ("TypeScript", partial(js_lex, jsx=True, language="TypeScript"), "  "),
}

SUPPORTED_EXTENSIONS = tuple(_LEXERS)


def extension_of(filepath: str) -> str:
    """Return *filepath*'s lower-cased extension, dot included ('' when none)."""
    return Path(filepath).suffix.lower()


def language_name(extension: str) -> str:
    """Return the language name for *extension*, or the extension itself when unmapped."""
    entry = _LEXERS.get(extension.lower())
    return entry[0] if entry else extension


def counted_line_keys(content: str, extension: str) -> list[str]:
    """Return the ordered COUNTED lines of *content*, each keyed by its non-comment text.

    Args:
        content: The file's full text (LF or CRLF).
        extension: The file's extension, dot included (``".py"``).

    Returns:
        One entry per counted line: its text with comments and standalone
        strings cut out and trailing whitespace stripped. The list's length
        is the measured length by construction.

    Raises:
        UnmeasurableContentError: no tokenizer exists for *extension*, or the
            content cannot be read as that language.
    """
    entry = _LEXERS.get(extension.lower())
    if entry is None:
        detail = "no tokenizer is registered for this kind"
        raise UnmeasurableContentError(extension or "(no extension)", detail)
    text = normalise(content)
    _name, lexer, unit = entry
    ranges, breaks = lexer(text)
    return counted_keys(text, ranges, breaks, unit)


def measure_lines(content: str, extension: str) -> int:
    """Return the measured length of *content* under the one rule, by *extension*'s language."""
    return len(counted_line_keys(content, extension))


def total_physical_lines(content: str) -> int:
    """Return the total physical line count, split exactly as the measure splits."""
    return len(split_physical_lines(normalise(content)))


"""
DECISION HISTORY
========================================================================
- 2026-10-20 15:19 [python-coder]: Initial authoring. One registry maps each covered extension to
  its lexer; an unmapped extension raises instead of falling back to a raw count, and the
  deployed-layout descriptor fails if any checked extension is unmapped.
  (#EPIC-FilesStayWorkable/GE-127d-3)
- 2026-10-21 [python-coder]: Blank lines never count anywhere (BrainCandy decision); the module
  docstring and the counting in spans.counted_keys were updated to match.
  (#EPIC-FilesStayWorkable/GE-127d-3)
- 2026-10-23 [GE-127d-3-v]: Each lexer returns (ranges, statement breaks); a line holding several
  statements counts once per statement (Python and the JavaScript family; SQL and shell have no
  breaks). (#EPIC-FilesStayWorkable/GE-127d-3)
- 2026-10-25 [GE-127d-3-vi]: SQL and shell supply statement breaks too, every break carries an
  indent step, and each language names its indentation unit (four spaces in Python, two
  elsewhere) so a split-off statement is keyed as it would stand on its own line.
  (#EPIC-FilesStayWorkable/GE-127d-3)
"""
