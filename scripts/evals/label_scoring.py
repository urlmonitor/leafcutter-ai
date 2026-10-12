"""MODULE: label_scoring.py
GOAL: Score classifier answers without turning unavailable responses into negatives.
BUSINESS CONTEXT: Failed invocations remain failures, not invented model-quality evidence.
ARCHITECTURE: Pure row and aggregate scoring plus console reporting, re-exported by run_agent_eval.
"""
from __future__ import annotations

from typing import Any


OUTCOME_BY_COMBO: dict[tuple[bool, bool, bool], str] = {
    (True, True, True): "full-set",
    (False, True, True): "mockup+data",
    (False, False, True): "mockup-only",
    (False, True, False): "mock-data-only",
    (False, False, False): "none",
}


def derive_outcome(labels: dict[str, bool]) -> str:
    """Derive the routing outcome from the three classifier booleans.

    Pure function. Returns "inconsistent" for any combination the schema does not
    allow (the validator flags these; the harness records them rather than crash).
    """
    key = (
        bool(labels.get("needs_flow")),
        bool(labels.get("needs_mock_data")),
        bool(labels.get("needs_mockup")),
    )
    return OUTCOME_BY_COMBO.get(key, "inconsistent")


def score_label_row(predicted: dict[str, Any], expected: dict[str, Any], axes: list[str]) -> dict[str, Any]:
    """Score already validated labels with the existing boolean comparison contract."""
    per_axis = {}
    for axis in axes:
        exp, pred = bool(expected.get(axis)), bool(predicted.get(axis))
        per_axis[axis] = {"expected": exp, "predicted": pred, "correct": exp == pred}
    return {"passed": all(cell["correct"] for cell in per_axis.values()), "per_axis": per_axis}


def _axis_counts(rows: list[dict[str, Any]], axis: str) -> dict[str, int]:
    """Count observed predictions only; failed response rows have no confusion cells."""
    counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for row in rows:
        if "parse_error" in row:
            continue
        cell = row["score"]["per_axis"][axis]
        if cell["predicted"]:
            key = "tp" if cell["expected"] else "fp"
        else:
            key = "fn" if cell["expected"] else "tn"
        counts[key] += 1
    return counts


def _axis_statistics(counts: dict[str, int]) -> dict[str, float | int]:
    """Compute precision, recall and F1 from observable confusion counts."""
    tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {**counts, "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


def aggregate_label(row_results: list[dict[str, Any]], axes: list[str], derive_outcome_flag: bool) -> dict[str, Any]:
    """Keep failed rows in accuracy denominators while reporting failures separately."""
    total = len(row_results)
    passed = sum(1 for row in row_results if row["score"]["passed"])
    result = {
        "rows": total, "passed": passed, "accuracy": round(passed / total, 4) if total else 0.0,
        "invocation_failures": sum("parse_error" in row for row in row_results),
        "per_axis": {axis: _axis_statistics(_axis_counts(row_results, axis)) for axis in axes},
    }
    if derive_outcome_flag:
        correct = sum(1 for row in row_results if "parse_error" not in row
                      and row.get("expected_outcome") is not None
                      and row.get("predicted_outcome") == row.get("expected_outcome"))
        result["outcome_accuracy"] = round(correct / total, 4) if total else 0.0
    return result



def print_report(agent: str, mode: str, row_results: list[dict], aggregate: dict) -> None:
    """Print a human-readable per-row + aggregate report to stdout."""
    print(f"\n=== Agent eval: {agent}  (mode={mode}) ===")
    for r in row_results:
        mark = "PASS" if r["score"]["passed"] else "FAIL"
        detail = ""
        if "predicted_outcome" in r:
            oc = "ok" if r["predicted_outcome"] == r["expected_outcome"] else "MISS"
            detail = f"  outcome[{oc}] exp={r['expected_outcome']} got={r['predicted_outcome']}"
        print(f"  [{mark}] {r['id']}{detail}")
        if "parse_error" in r:
            print(f"         invocation/response failure: {r['parse_error']}")
        if not r["score"]["passed"]:
            for axis, cell in r["score"]["per_axis"].items():
                if not cell["correct"]:
                    print(f"         axis {axis}: expected {cell['expected']} got {cell['predicted']}")

    print("\n  --- Aggregate ---")
    print(f"  rows={aggregate['rows']} passed={aggregate['passed']} accuracy={aggregate['accuracy']:.2%}")
    print(f"  invocation/response failures={aggregate.get('invocation_failures', 0)}")
    if "outcome_accuracy" in aggregate:
        print(f"  outcome_accuracy={aggregate['outcome_accuracy']:.2%}")
    for axis, stats in aggregate.get("per_axis", {}).items():
        print(
            f"  axis {axis:16s} precision={stats['precision']:.2f} "
            f"recall={stats['recall']:.2f} f1={stats['f1']:.2f} "
            f"(tp={stats['tp']} fp={stats['fp']} fn={stats['fn']} tn={stats['tn']})"
        )


# DECISION HISTORY
# ================================================================================
# - 2026-10-05 06:37 [python-coder]: Extract label scoring to keep the harness within its size ratchet. (#TICKETLESS reason=user-authorized-evaluation-repair)
