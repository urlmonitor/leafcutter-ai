"""
MODULE: unit_tests/evals/tq200d4v/_helpers.py
GOAL: Shared helpers for the TQ-200d-4-v tests (the test-runner row ``missing-setting-database-work``
    scored against the fixed "Database Not Configured" block read out of the template). Not a test file.
BUSINESS CONTEXT: The "fixed message only" report is never typed here: it is the fenced block
    extracted from templates/agents/test-runner.md at test time, so reverting the template changes
    the report and turns the tests red. The command checks need the checker run, so the report is
    paired with the recorded run1 transcript. No model, no network.
"""

from __future__ import annotations

import re
import shutil
import textwrap
from pathlib import Path

import unit_tests.evals.tq200d4._helpers as d4

REPO_ROOT = d4.REPO_ROOT
TEMPLATE = REPO_ROOT / "templates" / "agents" / "test-runner.md"
SENTENCE = "The database tests were not run."
RUN_CLAIM = "The database tests ran and passed."
ROW_KEY = "w1"
FIXTURE_ROW = (Path(__file__).resolve().parents[1] / "fixtures" / "tq200d-rerun"
               / "test-runner" / "missing-setting-database-work")
NOT_RUN = "report_says_not_run"


def row() -> dict:
    """The real test-runner row ``missing-setting-database-work``."""
    return d4.real_row("test-runner", ROW_KEY)


def template_block() -> str:
    """The not_configured fenced block as the template holds it (dedented, trailing newline)."""
    text = TEMPLATE.read_bytes().decode("utf-8").replace("\r\n", "\n")
    for body in re.findall(r"```[^\n]*\n(.*?)```", text, flags=re.DOTALL):
        if textwrap.dedent(body).lstrip().startswith("## Database Not Configured"):
            return textwrap.dedent(body).strip("\n") + "\n"
    msg = "templates/agents/test-runner.md has no '## Database Not Configured' fenced block"
    raise AssertionError(msg)


def output_dir(tmp_path: Path, report: str, name: str = "output") -> Path:
    """An output folder holding *report* and the recorded run1 transcript (the checker run)."""
    out = tmp_path / name
    out.mkdir(parents=True)
    (out / "report.md").write_text(report, encoding="utf-8")
    shutil.copyfile(FIXTURE_ROW / "run1" / d4.TRANSCRIPT, out / d4.TRANSCRIPT)
    return out


def score_report(tmp_path: Path, report: str) -> dict:
    """Score *report* (with the run1 transcript) as the test-runner row does."""
    return d4.score("test-runner", row(), output_dir(tmp_path, report), tmp_path / "work")


def score_probe(tmp_path: Path, run: str) -> dict:
    """Score a recorded probe folder (``run1`` or ``run2``) as it is."""
    out = tmp_path / f"probe_{run}"
    shutil.copytree(FIXTURE_ROW / run, out)
    return d4.score("test-runner", row(), out, tmp_path / f"work_{run}")


def failed_kinds(record: dict) -> list[str]:
    """The kinds of the assertions that did not pass."""
    return [a["kind"] for a in d4.failed(record)]
