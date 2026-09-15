"""Markdown-table context discrimination for the placeholder scanner.

Extracted from :mod:`build_placeholder_detection` so that module stays under
the 400-line size standard: adding this rule inline took it from 385 counted
lines to 415, which the size gate correctly refused.

The rule this module owns is the table-cell analogue of the scanner's heading
rule, and it is deliberately the SAME rule rather than a looser one. See
:func:`marker_is_quoted_in_table_cell`.

DECISION HISTORY
----------------
2026-09-14 — Created. The known-issues registers became generated indexes of
one row per issue, and one issue is titled
``KI-BO-021 — TODO: `BO-2400e-4` is closed on two of its four specified tests``.
As a ``###`` heading its marker sat after other heading text and the scanner's
heading rule read it as part of a title; moved verbatim into a table cell it was
reported as a stub, failing three "the real registers must scan clean" tests on
a row that creates nothing and fixes nothing. (BO-2200b-3-ii.)
"""

from __future__ import annotations

import re

# A table row, not merely a line containing a pipe: requires a leading pipe AND
# a second one. Without that bound, an ordinary sentence quoting a shell
# pipeline ("run `ls | wc -l` and then TODO: ...") would buy itself a marker
# exemption.
_MARKDOWN_TABLE_ROW = re.compile(r"^\s*\|.*\|")


def is_table_row(line: str) -> bool:
    """Return True when `line` has the shape of a markdown table row."""
    return _MARKDOWN_TABLE_ROW.match(line) is not None


def marker_is_quoted_in_table_cell(line: str, start: int) -> bool:
    """Return True when the marker at `start` is quoted rather than a stub.

    A generated index that lists document titles in a table quotes those titles
    exactly as a heading does, and needs the same discrimination for the same
    reason. So a marker inside a table cell is a quotation only when other text
    precedes it IN THAT CELL.

    A row reading ``| TODO: fill this in |`` is NOT quoted: there the marker
    opens the cell, and that is the scaffolding shape the gate exists to catch.
    A blanket table exclusion would let it through — the mistake the heading
    rule's own comment warns a future editor against in its context.

    Args:
        line: The full source line.
        start: Index in `line` where the marker match begins.

    Returns:
        True when the marker is preceded by other text in its own cell.
    """
    cell_start = line.rfind("|", 0, start)
    if cell_start == -1:
        return False
    return bool(line[cell_start + 1:start].strip())
