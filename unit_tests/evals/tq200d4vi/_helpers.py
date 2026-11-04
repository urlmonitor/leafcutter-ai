"""
MODULE: unit_tests/evals/tq200d4vi/_helpers.py
GOAL: Shared helpers for the TQ-200d-4-vi tests (test-writer row missing-setting-database-work, kind
    report_says_stopped_before_database). Not a test file.
BUSINESS CONTEXT: Reports are scored through the REAL kind registry and the REAL set rows; the kept
    re-run reports are the recorded fixtures copied from the 2026-11-02 runs. No model, no network.
"""

from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path

import unit_tests.evals.tq200d4._helpers as d4

NEW_KIND = "report_says_stopped_before_database"
OLD_KIND = "report_says_not_run"
RERUN = (Path(__file__).resolve().parents[1] / "fixtures" / "tq200d-rerun" / "test-writer"
         / "missing-setting-database-work")
STOP_RE = {"run1": "before any connection", "run2": "before ever reaching"}
RED_RUN = "Ran 2 tests in 0.004s\n\nFAILED (errors=2)"
SETTING = "testing_context.db_connection_test"
DOC = d4.REPO_ROOT / "docs" / "reference" / "produced-tests-eval-assertion-kinds-database-setting.md"
README = d4.EVALS_DIR / "README.md"
TEMPLATE = d4.REPO_ROOT / "templates" / "agents" / "test-writer.md"


def row_context(report: str):
    """A RowContext holding only *report*."""
    runs = d4.module("produced_tests_runs")
    tmp = Path(tempfile.mkdtemp())
    return runs.RowContext(sandbox=tmp, work_dir=tmp, fixture_dir=tmp, base_sha="", report=report)


def new_kind(report: str) -> dict:
    """Run the new kind on *report* through the real registry (a missing kind is the absence the tests report)."""
    reports = d4.module("produced_tests_reports")
    assert NEW_KIND in reports.KINDS, f"{NEW_KIND} is not registered in produced_tests_reports.KINDS"
    return reports.KINDS[NEW_KIND](row_context(report), {"kind": NEW_KIND})


def old_kind(report: str) -> dict:
    """Run report_says_not_run on *report*."""
    reports = d4.module("produced_tests_reports")
    return reports.KINDS[OLD_KIND](row_context(report), {"kind": OLD_KIND})


def writer_report(*sentences: str) -> str:
    """A test-writer report naming the setting and holding the red run, plus *sentences*."""
    return "\n".join([f"{SETTING} is not configured.", "", "Verification run:", RED_RUN, "", *sentences])


def assertion_kinds(row: dict) -> list[str]:
    """The assertion kinds the row lists."""
    return [a["kind"] for a in row["expected"]["assertions"]]


def score_report_dir(out: Path, tmp_path: Path) -> dict:
    """Score an output folder against the real test-writer row."""
    return d4.score("test-writer", d4.real_row("test-writer", "w1"), out, tmp_path / "work")


def probe(run: str, tmp_path: Path, drop_stop_sentence: bool = False) -> Path:
    """A copy of the kept *run* output; with *drop_stop_sentence* the line holding its stop phrase is removed."""
    out = tmp_path / f"{run}-{'weak' if drop_stop_sentence else 'kept'}"
    shutil.copytree(RERUN / run, out)
    if drop_stop_sentence:
        rep = out / "report.md"
        lines = rep.read_text(encoding="utf-8").splitlines()
        kept = [ln for ln in lines if not re.search(STOP_RE[run], ln)]
        assert len(kept) < len(lines), f"{run} report holds no line with {STOP_RE[run]!r}"
        rep.write_text("\n".join(kept) + "\n", encoding="utf-8")
    return out
