"""
MODULE: commit_guardian._file_size_measure.rule_statement
GOAL: Generate, from what the measure ACTUALLY DOES with probe content, the
    one-line statement of what a quoted length counts and does not count.
BUSINESS CONTEXT: GE-127d-2 / GE-127d-5: the published rule must follow the
    enforced rule without a hand edit. A statement built from a table of what
    the measure is supposed to do would pass every check on the day it is
    written and drift the moment a comment style started counting again; a
    statement built from probe results cannot. The statement names a comment
    style only when the measure counts it, so no style is ever advertised as
    free.
ARCHITECTURE: ``describe(measure)`` takes the measure as an argument and the
    caller (``_file_size_ratchet.describe_measurement_rule``) resolves
    ``count_content_lines`` as a module global AT CALL TIME, so rebinding that
    name changes the statement in the same call that changes the quoted
    length. Every probe is a self-contained block of one category: a category
    the measure discards measures below the probe's physical line count, one
    it counts measures to exactly that count. The statement carries no digits
    and no dotted extension tokens, so the parity gate's kind and limit
    readers never mistake it for a claim of scope or limit.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import NamedTuple

Measure = Callable[[str, str], int]

MARKER = "MEASUREMENT RULE"
_BODY = "probe one\nprobe two\n"


class _Probe(NamedTuple):
    label: str
    extension: str
    text: str


def _comment_probes() -> tuple[_Probe, ...]:
    """One probe per comment form of each language's lexer."""
    block = "/* probe one\nprobe two */\n"
    forms = (
        ("Python", ".py", "#", None),
        ("shell", ".sh", "#", None),
        ("SQL", ".sql", "--", block),
        ("JavaScript", ".js", "//", block),
        ("TypeScript", ".ts", "//", block),
    )
    probes: list[_Probe] = []
    for language, extension, prefix, block_text in forms:
        lines = "".join(f"{prefix} {row}\n" for row in _BODY.splitlines())
        probes.append(_Probe(f"{language} line comments", extension, lines))
        if block_text is not None:
            probes.append(_Probe(f"{language} block comments", extension, block_text))
    return tuple(probes)


_COMMENT_PROBES = _comment_probes()
_STANDALONE_PROBES = (
    _Probe("docstrings", ".py", f'"""\n{_BODY}"""\n'),
    _Probe("bare standalone strings", ".py", f'x = 1\n"""\n{_BODY}"""\ny = 2\n'),
    _Probe("trailing standalone string blocks", ".py", f'x = 1\n"""\nDECISION HISTORY\n{_BODY}"""\n'),
)
_USED_PROBES = (
    _Probe("assigned strings", ".py", f'TEXT = """\n{_BODY}"""\n'),
    _Probe("strings passed as arguments", ".py", f'print("""\n{_BODY}""")\n'),
    _Probe("standalone f-strings", ".py", f'f"""\n{{x}}\n{_BODY}"""\n'),
)
_BLANK_PROBE = _Probe("blank lines", ".py", "x = 1\n\ny = 2\n")
_JOINED_PROBES = (
    _Probe("Python", ".py", "x = 1; y = 2\n"),
    _Probe("JavaScript", ".js", "a(); b();\n"),
    _Probe("TypeScript", ".ts", "a(); b();\n"),
    _Probe("SQL", ".sql", "SELECT 1; SELECT 2;\n"),
    _Probe("shell", ".sh", "a; b\n"),
)


def _per_statement(measure: Measure) -> str:
    """The clause stating which languages count a joined line once per statement, or ''."""
    languages = [probe.label for probe in _JOINED_PROBES if measure(probe.text, probe.extension) > 1]
    if not languages:
        return ""
    return (
        f"; a line holding several statements counts once per statement ({_join(languages)}), "
        "so joining statements onto one line shortens nothing"
    )

_ALL_COMMENTS = "comments of every style (line and block comments in every language measured)"
_ALL_STANDALONE = (
    "standalone strings (Python strings standing alone as statements: docstrings, bare strings and trailing blocks)"
)
_ALL_USED = (
    "every line of a used string (a Python string that is assigned, passed, returned or part of a larger "
    "expression), every line of an f-string"
)


def _join(items: list[str]) -> str:
    """Join *items* English-list style: ``a``, ``a and b``, ``a, b and c``."""
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _discards(measure: Measure, probe: _Probe) -> bool:
    """True when *measure* counts fewer lines than *probe* physically has."""
    return measure(probe.text, probe.extension) < len(probe.text.splitlines())


def _split(measure: Measure, probes: tuple[_Probe, ...]) -> tuple[list[str], list[str]]:
    """Return the labels of *probes* the measure discards and the labels it counts."""
    discarded: list[str] = []
    counted: list[str] = []
    for probe in probes:
        (discarded if _discards(measure, probe) else counted).append(probe.label)
    return discarded, counted


def _group(measure: Measure, probes: tuple[_Probe, ...], whole: str) -> tuple[list[str], list[str]]:
    """Discarded and counted phrases for *probes*, collapsed to *whole* when all are discarded."""
    discarded, counted = _split(measure, probes)
    if len(discarded) == len(probes):
        return [whole], []
    return discarded, counted


def describe(measure: Measure) -> str:
    """Describe, from *measure*'s behaviour on probes, what a quoted length counts.

    Args:
        measure: The shared measure, ``(content, extension) -> length``.

    Returns:
        One line (no newline, no pipe) suitable after a ``Measures:`` label
        or after the ``MEASUREMENT RULE:`` marker on a published surface.
    """
    comments_off, comments_on = _group(measure, _COMMENT_PROBES, _ALL_COMMENTS)
    standalone_off, standalone_on = _group(measure, _STANDALONE_PROBES, _ALL_STANDALONE)
    used_off, used_on = _split(measure, _USED_PROBES)
    blank_off = _discards(measure, _BLANK_PROBE)

    not_counted = comments_off + standalone_off + used_off + (["blank lines"] if blank_off else [])
    counted = comments_on + standalone_on + ([] if blank_off else ["blank lines outside them"])
    counted += used_on if used_off else [_ALL_USED]
    counted.append("every other line of code")
    head = f"does not count {_join(not_counted)}; " if not_counted else ""
    return f"{head}counts {_join(counted)}{_per_statement(measure)}."


"""
DECISION HISTORY
========================================================================
- 2026-10-20 15:19 [python-coder]: Initial authoring. The statement is built from probe results
  per language and per Python string role, never from a table of intended behaviour; a style is
  named only when the measure counts it, so no comment style is ever advertised as free.
  (#EPIC-FilesStayWorkable/GE-127d-5)
- 2026-10-21 [python-coder]: With blank lines never counted (BrainCandy decision), the blank-line
  probe reads as uncounted, so the generated statement lists blank lines among what is not
  counted. (#EPIC-FilesStayWorkable/GE-127d-5)
- 2026-10-23 [GE-127d-3-v]: A joined-statements probe per language adds the clause that a line
  holding several statements counts once per statement, naming only the languages where the
  measure actually does so. (#EPIC-FilesStayWorkable/GE-127d-3)
- 2026-10-25 [GE-127d-3-vi]: SQL and shell joined-statement probes added, so the clause names
  them once their lexers split joined lines. (#EPIC-FilesStayWorkable/GE-127d-3)
"""
