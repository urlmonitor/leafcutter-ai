"""Helpers for the TQ-200d-1-iv tests: score one produced test source through the real static kinds."""

from __future__ import annotations

import shutil
from pathlib import Path

import unit_tests.evals._tq200d1_helpers as h

COUNT = "counts_rows_and_non_null"
SEED = "asserts_known_seeded_value"
TEST_FILE = {COUNT: "test_buy_volume_window.py", SEED: "test_live_value_presence.py"}
ROW = {COUNT: "empty", SEED: "presence"}
RERUN = h.FIXTURES.parent / "tq200d-rerun" / "test-writer"
ROW_DIR = {COUNT: "empty-window", SEED: "presence-is-not-correctness"}


def score_dir(kind: str, output: Path, tmp_path: Path) -> dict:
    """Score the output dir with ONLY the named static kind, on the real row's fixture project."""
    real = h.real_row(ROW[kind])
    row = {"id": real["id"], "input": real["input"],
           "expected": {"negative": False, "fixture": real["expected"]["fixture"],
                        "assertions": [{"kind": kind, "file": TEST_FILE[kind]}]}}
    return h.score(row, output, tmp_path / "work")["score"]["assertions"][0]


def score_source(kind: str, source: str, tmp_path: Path) -> dict:
    """Write *source* as the produced test of *kind*'s row and score it."""
    out = tmp_path / "out"
    out.mkdir(parents=True, exist_ok=True)
    (out / (TEST_FILE[kind] + ".recorded")).write_text(source, encoding="utf-8")
    (out / "report.md").write_text("# Completion Report\n", encoding="utf-8")
    return score_dir(kind, out, tmp_path)


def unittest_body(*lines: str, setup: str = "") -> str:
    """A unittest.TestCase source whose test method holds *lines* after a 3-value window."""
    body = "\n".join("        " + ln for ln in lines)
    return ("import unittest\n\n\nclass T(unittest.TestCase):\n    def test_x(self):\n"
            "        window = [1.0, 0.0, 2.5]\n        volumes = list(window)\n"
            "        non_null = sum(v is not None for v in volumes)\n" + body + "\n")


def bare_body(*lines: str) -> str:
    """The bare-assert twin of unittest_body."""
    body = "\n".join("    " + ln for ln in lines)
    return ("def test_x():\n    window = [1.0, 0.0, 2.5]\n    volumes = list(window)\n"
            "    non_null = sum(v is not None for v in volumes)\n" + body + "\n")


def seed_body(*lines: str, unittest_form: bool = True) -> str:
    """A seeded-feed source asserting *lines*."""
    if unittest_form:
        body = "\n".join("        " + ln for ln in lines)
        return ('import unittest\n\n\nclass T(unittest.TestCase):\n    def test_x(self):\n'
                '        feed = {"AAPL": 190.12, "MSFT": 410.55, "TSLA": 248.50}\n        result = dict(feed)\n' + body + "\n")
    body = "\n".join("    " + ln for ln in lines)
    return 'def test_x():\n    feed = {"AAPL": 190.12, "MSFT": 410.55, "TSLA": 248.50}\n    result = dict(feed)\n' + body + "\n"


def copy_run(kind: str, run: str, dest: Path) -> Path:
    """Copy a kept re-run output into *dest* (a flat gold-output folder)."""
    src = RERUN / ROW_DIR[kind] / run
    assert src.is_dir(), f"probe fixture missing: {src}"
    shutil.copytree(src, dest)
    return dest
