"""
MODULE: unit_tests/evals/tq200d2iii/_helpers.py
GOAL: Shared helpers for the TQ-200d-2-iii tests (a WHERE-filtered COUNT(*) is a non-NULL count in
    the sql-test-writer "empty window, database shape" row). Not a test file.
BUSINESS CONTEXT: Every variant is built from the REAL kept output of the 2026-11-02 re-run 1
    (unit_tests/evals/fixtures/tq200d-rerun/...), keeping its header and setUp and replacing only the
    queries and assertions of its first test, so a variant can only fail for the reason it carries.
"""

from __future__ import annotations

from pathlib import Path

import unit_tests.evals.tq200d2._helpers as h

RERUN = h.FIXTURES.parent / "tq200d-rerun" / "sql-test-writer" / "empty-window-database-shape" / "run1"
PROBE = RERUN / "test_buy_volume_window.py.recorded"
KI_STEM = "ki-tq-20261102-sql-non-null-count-misses-count-star-where-not-null"
HEAD_MARK = "        symbols = list(_SEEDED_ROWS)\n"
TAIL_MARK = '\n\nif __name__ == "__main__":'
VIEW = "buy_volume_window"
EXACT = "self.assertEqual(self.cur.fetchone()[0], len(_SEEDED_ROWS))"
ROWS = (f"SELECT COUNT(*) FROM {VIEW} WHERE symbol = ANY(%s)", EXACT)


def filtered(where: str, count: str = "COUNT(*)", assertion: str = EXACT) -> tuple[str, str]:
    """A (query, assertion) pair counting with *count* over the view under the WHERE clause *where*."""
    return f"SELECT {count} FROM {VIEW} {where}", assertion


def build(queries: list[tuple[str, str]], tmp_path: Path, name: str = "variant") -> Path:
    """The row's gold output with its produced test replaced by the real probe's header and *queries*."""
    text = PROBE.read_text(encoding="utf-8")
    head = text.split(HEAD_MARK)[0] + HEAD_MARK
    body = "".join(f'        self.cur.execute("{sql}", (symbols,))\n        {check}\n' for sql, check in queries)
    row = h.real_row("empty")
    target = tmp_path / f"{name}.py.recorded"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(head + body + TAIL_MARK + "\n    unittest.main()\n", encoding="utf-8")
    return h.output_with(row, tmp_path / f"{name}_out", {h.EMPTY_TEST_FILE: target})


def passes(queries: list[tuple[str, str]], tmp_path: Path, name: str) -> dict:
    """Score a variant; the count kind passes (and the whole row with it)."""
    row = h.real_row("empty")
    return h.expect_passes(row, tmp_path / f"{name}_s", build(queries, tmp_path, name))


def fails(queries: list[tuple[str, str]], tmp_path: Path, name: str, *words: str, absent: tuple[str, ...] = ()) -> dict:
    """Score a variant; ONLY the count kind fails, naming *words*."""
    row = h.real_row("empty")
    return h.expect_fails_only(row, tmp_path / f"{name}_s", build(queries, tmp_path, name), h.K_COUNTS, *words, absent=absent)
