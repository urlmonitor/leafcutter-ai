"""
MODULE: scripts/build_orchestration/_wvr_effect.py
GOAL: The effect check's pure functions (TQ-500g-1-xiv): the as-written line numbers a wrong
    version changes, and whether a test ran any of them.
BUSINESS CONTEXT: A test held to a wrong version that changes no line the test runs is reported
    ``not_executed`` (unfinished), never as a survivor: the wrong version could not reach that test,
    which says nothing about whether the test is weak.
ARCHITECTURE: Pure functions, no I/O. ``changed_lines`` compares the as-written bytes with the altered
    bytes (difflib on the LF form, so a CRLF file numbers its lines the same) and always answers in the
    AS-WRITTEN numbering, because that is the numbering of the run on the code as written, which is
    where the lines a test ran are recorded. ``reached`` combines those changed lines with the lines a
    test ran (``_wvr_trace``) into one of three words; ``not traceable`` means the check cannot judge
    and the caller keeps the run-decided verdict.
"""

from __future__ import annotations

import difflib

REACHED = "reached"
NOT_REACHED = "not reached"
NOT_TRACEABLE = "not traceable"


def _lines(data: bytes) -> list[str]:
    """Split *data* into lines on the LF form (a CRLF file numbers its lines like an LF one)."""
    return data.decode("utf-8", errors="replace").replace("\r\n", "\n").split("\n")


def changed_lines(as_written: bytes, altered: bytes) -> set[int]:
    """Return the 1-based as-written line numbers *altered* changes.

    Every as-written line of a replace or delete is a changed line; a pure insert changes the
    as-written line just before the insertion point (line 1 for an insert at the top).

    Args:
        as_written: The file's bytes on the code as written.
        altered: The file's bytes under the wrong version.

    Returns:
        The changed as-written line numbers (empty when the bytes agree).
    """
    matcher = difflib.SequenceMatcher(None, _lines(as_written), _lines(altered), autojunk=False)
    changed: set[int] = set()
    for tag, i1, i2, _j1, _j2 in matcher.get_opcodes():
        if tag in ("replace", "delete"):
            changed.update(range(i1 + 1, i2 + 1))
        elif tag == "insert":
            changed.add(max(i1, 1))
    return changed


def reached(executed: dict[str, set[int]], changes: dict[str, set[int]], untraceable: set[str]) -> str:
    """Say whether a test ran a changed line.

    Args:
        executed: ``{repo-relative path: lines the test ran}`` (its own lines plus those run at import).
        changes: ``{repo-relative path: as-written lines the wrong version changes}`` per altered file.
        untraceable: Altered files whose run-or-not-run could not be traced.

    Returns:
        ``reached`` when the test ran at least one changed line of a traceable file; ``not reached`` when
        every altered file is traceable and it ran none; ``not traceable`` otherwise.
    """
    for rel, lines in changes.items():
        if rel not in untraceable and lines & executed.get(rel, set()):
            return REACHED
    return NOT_TRACEABLE if untraceable & set(changes) else NOT_REACHED


# ================================================================================
# DECISION HISTORY
# ================================================================================
# - 2026-10-25 18:50 [coordinator]: Skeleton so the declared must_catch test fails by reaching the code,
#   not by failing to import it (red-baseline reader, TQ-500f-3-i). (#EPIC-OnceANamedWrongVersionIsPreparedAnd/04)
# - 2026-10-25 20:10 [python-coder]: Body written: changed lines in the as-written numbering, and the
#   three-word reached(). (#EPIC-OnceANamedWrongVersionIsPreparedAnd/04)
