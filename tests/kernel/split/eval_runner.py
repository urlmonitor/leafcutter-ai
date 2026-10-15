"""
MODULE: tests.kernel.split.eval_runner
GOAL: Load the labelled single/bundled request set and count false positives and negatives of a
    set of bundle probabilities at a threshold (DK-400a-3-i).
BUSINESS CONTEXT: The bundle threshold is biased against false positives; an opt-in live eval
    needs a checked-in labelled set to report how often it splits a single question.
ARCHITECTURE: Pure functions over tests/kernel/fixtures/eval/split_bundle.json. No provider call.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

EVAL_SET = Path(__file__).resolve().parent.parent / "fixtures" / "eval" / "split_bundle.json"


def load_cases() -> list[dict[str, Any]]:
    """Return the labelled cases, each with id, goal and label (single or bundled)."""
    return list(json.loads(EVAL_SET.read_text(encoding="utf-8"))["cases"])


def score(cases: list[dict[str, Any]], probabilities: dict[str, float],
          threshold: float) -> dict[str, int]:
    """Return false-positive and false-negative counts; bundled means p >= threshold."""
    fp = fn = 0
    for case in cases:
        bundled = probabilities[case["id"]] >= threshold
        fp += bundled and case["label"] == "single"
        fn += (not bundled) and case["label"] == "bundled"
    return {"false_positives": fp, "false_negatives": fn}
