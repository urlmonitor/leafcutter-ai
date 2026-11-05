"""
MODULE: scripts/evals/sql_test_writer_eval/label_kinds.py
GOAL: The label-reading assertion kinds of the sql-test-writer set: every answer carries a label, and
    every ``[observed: ...]`` label quotes a verdict row that is a real observation.
BUSINESS CONTEXT: TQ-200d-2. "Observed" is legitimate only where a quoted run backs it. A run that was
    not_run, invalid or not_in_scope observed nothing, so only a caught or survived row counts.
ARCHITECTURE: Pure functions over ``RowContext.report``. A label's end is found by bracket depth, so a
    parameter id such as ``test[1]`` does not cut it short. An answer is the text from a ``Q<n>:``
    marker to the next marker, blank line, bullet or bold heading, so a label on a wrapped line counts.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable

from produced_tests_runs import RowContext

OBSERVING = ("caught", "survived")
OBSERVED_START_RE = re.compile(r"\[observed", re.IGNORECASE)
PAREN_OBSERVED_RE = re.compile(r"\(observed:", re.IGNORECASE)
MARK_RE = re.compile(r"\*{0,2}\bQ([123])\*{0,2}[:.]")
SEGMENT_END_RE = re.compile(r"\n\s*[-*] |\n\s*\n|\n\*\*")
LABEL_RE = re.compile(r"\[reasoned\]|\(reasoned\)|`reasoned`|\[observed", re.IGNORECASE)
PREFIX_LEN = len("[observed")


def _outcome(passed: bool, ok: str, bad: str) -> dict:
    """The assertion outcome: *ok* when passed, else *bad*."""
    return {"passed": passed, "detail": ok if passed else bad}


def label_end(report: str, start: int) -> int | None:
    """The index after the ``]`` that closes the bracket opened at *start*, on the same line; None when unclosed."""
    depth = 0
    for i in range(start, len(report)):
        char = report[i]
        if char == "\n":
            return None
        depth += (char == "[") - (char == "]")
        if depth == 0:
            return i + 1
    return None


def observed_labels(report: str) -> list[tuple[int, int | None]]:
    """``(start, end)`` of each ``[observed`` label; *end* is None when the label is never closed."""
    return [(m.start(), label_end(report, m.start())) for m in OBSERVED_START_RE.finditer(report)]


def answer_segments(report: str) -> list[tuple[str, str]]:
    """``(Q<n>, text)`` for every answer marker in the report."""
    marks = list(MARK_RE.finditer(report))
    segments = []
    for i, mark in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(report)
        text = report[mark.end():end]
        cut = SEGMENT_END_RE.search(text)
        segments.append((f"Q{mark.group(1)}", text[: cut.start()] if cut else text))
    return segments


def answers_labelled(ctx: RowContext, _spec: dict) -> dict:
    """Every answer segment carries a ``[reasoned]``, ``(reasoned)``, backticked reasoned or ``[observed`` label."""
    segments = answer_segments(ctx.report)
    unlabelled = [q for q, text in segments if not LABEL_RE.search(text)]
    if len(segments) < len(("Q1", "Q2", "Q3")) and not unlabelled:
        unlabelled = ["Q1", "Q2", "Q3"]
    return _outcome(not unlabelled, "every answer is labelled", f"answers without a reasoned or observed label: {', '.join(unlabelled)} (label missing)")


def _is_observation(row: object) -> bool:
    """A verdict row with result caught or survived, whose test is empty (a group row) or holds a ``::`` node id."""
    if not isinstance(row, dict) or row.get("result") not in OBSERVING:
        return False
    test = str(row.get("test", ""))
    return test == "" or "::" in test


def quotes_observation(body: str) -> bool:
    """True when the label body is a JSON verdict row, or free text with ``::`` and the word caught or survived."""
    if body.lstrip().startswith("{"):
        try:
            return _is_observation(json.loads(body))
        except ValueError:
            return False
    return "::" in body and any(re.search(rf"\b{word}\b", body) for word in OBSERVING)


def observed_labels_quote_a_run(ctx: RowContext, _spec: dict) -> dict:
    """Every observed label is well formed and quotes a caught or survived verdict row."""
    report = ctx.report
    for start, end in observed_labels(report):
        if end is None:
            return _outcome(False, "", f"malformed observed label: {report[start:start + 60]}")
        body = report[start + PREFIX_LEN:end - 1].lstrip(":").strip()
        if not quotes_observation(body):
            return _outcome(False, "", f"an observed label quotes no verdict row (caught or survived): {report[start:end][:60]}")
    paren = PAREN_OBSERVED_RE.search(report)
    if paren:
        return _outcome(False, "", f"malformed observed label: {report[paren.start():paren.start() + 60]}")
    return _outcome(True, "every observed label quotes a verdict row", "")


KINDS: dict[str, Callable[[RowContext, dict], dict]] = {
    "sql_answers_labelled": answers_labelled,
    "sql_observed_labels_quote_a_run": observed_labels_quote_a_run,
}
