"""Reviewed baseline comparison with measured, explicitly selected gates.
MODULE: knowledge.evaluation_comparison
GOAL: Invalidate incompatible expectations and keep sample evidence below promotion claims.
BUSINESS CONTEXT: Synthetic or incomplete cases cannot establish representative semantic quality.
ARCHITECTURE: Pure report comparison; no query activation, source mutation or model training.
"""

from __future__ import annotations
import math


def compare_reports(baseline: dict, proposal: dict, gates: dict | None) -> dict:
    """Compare measured reports only under explicit baseline-bound quality and latency gates.

    Args:
        baseline: Previously measured independently reviewed report.
        proposal: Proposed behavior measured on the same reviewed cases.
        gates: Explicit baseline-bound thresholds, or None when not chosen.

    Returns:
        Compatibility, measured gate outcomes and limited/eligible/blocked promotion state.
    """
    if not gates:
        return {
            "status": "not_run",
            "promotion": "blocked",
            "limitations": [
                "measured baseline-bound quality and latency gates have not been selected"
            ],
        }
    issues = _compatibility(baseline, proposal, gates)
    if issues:
        return {"status": "invalidated", "promotion": "blocked", "limitations": issues}
    before, after = _measures(baseline), _measures(proposal)
    required = ("min_pass_rate", "max_p95_latency_ms", "min_executed_cases")
    if (
        any(not isinstance(gates.get(name), (int, float)) for name in required)
        or after["p95_latency_ms"] is None
    ):
        return {
            "status": "not_run",
            "promotion": "blocked",
            "limitations": ["explicit numeric gates and measured latency are required"],
            "baseline": before,
            "proposal": after,
        }
    checks = {
        "quality": after["pass_rate"] is not None and after["pass_rate"] >= gates["min_pass_rate"],
        "latency": after["p95_latency_ms"] <= gates["max_p95_latency_ms"],
        "case_count": after["executed"] >= gates["min_executed_cases"],
        "all_cases_executed": after["not_run"] == 0,
    }
    passed = all(checks.values())
    representative = (
        baseline.get("coverage", {}).get("representative") is True
        and proposal.get("coverage", {}).get("representative") is True
    )
    return {
        "status": "evaluated",
        "baseline": before,
        "proposal": after,
        "gates": gates,
        "checks": checks,
        "promotion": ("eligible" if representative else "limited") if passed else "blocked",
        "limitations": []
        if representative
        else ["reviewed sample is not established as a representative real benchmark"],
        "automatic_activation": False,
        "model_weight_training": False,
    }


def _compatibility(baseline: dict, proposal: dict, gates: dict) -> list[str]:
    """Invalidate changed source, question meaning, case judgments or operation scope.

    Args:
        baseline: Previously measured reviewed report.
        proposal: Candidate measured report.
        gates: Baseline identity and explicit comparison review selection.

    Returns:
        Reasons these reports cannot support a comparable promotion decision.
    """
    issues = []
    for key in ("review_fingerprint", "source_sha", "answer_semantics_version"):
        if not baseline.get(key) or baseline.get(key) != proposal.get(key):
            issues.append("changed or missing " + key + "; expectations must be reviewed again")
    if gates.get("baseline_review_fingerprint") != baseline.get("review_fingerprint"):
        issues.append("gates are not bound to this reviewed baseline")
    if _case_scope(baseline) != _case_scope(proposal):
        issues.append("case/query/model/source scope changed; explicit comparison review required")
    if baseline.get("implementation_digest") != proposal.get(
        "implementation_digest"
    ) and not gates.get("reviewed_implementation_change"):
        issues.append("executing answer contract changed without comparison review")
    return issues


def _case_scope(report: dict) -> list[tuple]:
    """Retain exact case, source, query, mapper and model identities for comparison.

    Args:
        report: Evaluator report containing case-level execution identities.

    Returns:
        Sorted identities whose differences invalidate an unchanged-expectations comparison.
    """
    fields = (
        "id",
        "source_sha",
        "query_version",
        "query_digest",
        "mapper_version",
        "embedding_model",
    )
    return sorted(tuple(str(row.get(field)) for field in fields) for row in report.get("cases", []))


def _measures(report: dict) -> dict:
    """Calculate explicit denominators and observed end-to-end latency percentiles.

    Args:
        report: Actual evaluation output including executed and not-run cases.

    Returns:
        Case counts, pass rate and measured latency with unavailable values left null.
    """
    rows = report.get("cases", [])
    executed = [row for row in rows if row.get("execution_state") == "executed"]
    passed = sum(row.get("verdict") == "passed" for row in executed)
    latencies = sorted(
        float(row.get("end_to_end_ms", row.get("latency_ms")))
        for row in executed
        if isinstance(row.get("end_to_end_ms", row.get("latency_ms")), (int, float))
    )
    return {
        "total": len(rows),
        "executed": len(executed),
        "not_run": len(rows) - len(executed),
        "passed": passed,
        "failed": len(executed) - passed,
        "pass_rate": passed / len(executed) if executed else None,
        "latency_count": len(latencies),
        "p95_latency_ms": latencies[math.ceil(len(latencies) * 0.95) - 1] if latencies else None,
    }


# DECISION HISTORY
# - 2026-10-01 [python-coder]: Require measured reviewed gates before proposing promotion. (#EPIC-RepositoryResearchAnswers/TICKET-20261001-KM-500d-3)
