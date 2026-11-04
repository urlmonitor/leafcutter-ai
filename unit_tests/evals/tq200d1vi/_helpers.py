"""
MODULE: unit_tests/evals/tq200d1vi/_helpers.py
GOAL: Shared helpers for the TQ-200d-1-vi tests (report_mentions also_accepts). Not a test file.
BUSINESS CONTEXT: A report is scored through the REAL score_row on the REAL set row (its report_mentions
    assertion only), so the spec under test is read from the set file, never retyped here.
    NOTE: the kept live report.md files of the 2026-11-02 re-runs were not available on this machine
    (the fixture copies hold a placeholder), so the re-run wordings are the exact phrases the AC quotes.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import unit_tests.evals._tq200d1_helpers as h

RUNNER_SET = h.EVALS_DIR / "sets" / "test-runner.jsonl"
EMPTY, PRESENCE = h.ROW_IDS["empty"], h.ROW_IDS["presence"]
# The wordings of the kept re-run 1 and re-run 2 reports (quoted by the AC and the known issue).
EMPTY_RERUNS = ["Guards: exact-count and non-`None`-count guards; an empty or all-`None` window fails.",
                "The test asserts the exact non-None count, so an empty or all-`None` window fails."]
PRESENCE_RERUNS = ["The test asserts the exact expected value from the feed.",
                   "It checks the exact expected value from the feed for each symbol."]


def load(path: Path) -> list[dict]:
    """The rows of a set file."""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def mention_specs(path: Path) -> list[tuple[str, dict]]:
    """(row id, report_mentions spec) for every report_mentions assertion in a set file."""
    return [(r["id"], a) for r in load(path) for a in r["expected"]["assertions"] if a["kind"] == "report_mentions"]


def score_report(report: str, tmp_path: Path, row_id: str, path: Path = h.SET_PATH) -> dict:
    """Score *report* against row *row_id*'s report_mentions assertion alone; return that assertion's record."""
    row = copy.deepcopy(next(r for r in load(path) if r["id"] == row_id))
    row["expected"]["assertions"] = [a for a in row["expected"]["assertions"] if a["kind"] == "report_mentions"]
    out = tmp_path / "output"
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text(report, encoding="utf-8")
    row["expected"]["gold_output"] = str(out)
    record = h.score(row, out, tmp_path / "work")
    (assertion,) = record["score"]["assertions"]
    return assertion
