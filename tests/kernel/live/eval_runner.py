"""
MODULE: tests.kernel.live.eval_runner
GOAL: Score the live kernel against the small labelled evaluation set (answerable control,
    unanswerable, missing-information, contradictory and out-of-scope decision requests): run
    every case once through the real service and the real Jev, classify the outcome and compare it
    with the label.
BUSINESS CONTEXT: Rev 3 section 16 asks for a labelled set and for results to be reported, not
    for calibration to be assumed. The runner gives that report: which labelled outcome the live
    kernel reached for each request, how many Jev calls it used, and whether any unanswerable
    request ended as a fabricated decision.
ARCHITECTURE: Pure helpers (`load_cases`, `classify`, `task_for`, `score`) plus `run_eval`, which
    builds a production environment per case (run root in scratch, Langfuse off, a per-case Jev
    call cap, the repo-only research override) and starts one run. Cases that pause are not resumed: the labelled outcome is the
    first resting state. Run it as `LEAFCUTTER_KERNEL_LIVE=1 python -m tests.kernel.live.eval_runner`.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from kernel.bootstrap import build_environment
from kernel.config import repo_root
from kernel.contracts import TaskInput, content_hash, evidence_id
from kernel.service import KernelService
from tests.kernel.live.live_support import scratch_dir

EVAL_SET = Path(__file__).resolve().parents[1] / "fixtures" / "eval" / "eval_set.json"
CLASSES = ("completed", "waiting_host", "waiting_human", "not_decided")
CATEGORIES = ("answerable", "unanswerable", "missing_information", "contradictory",
              "out_of_scope")
MAX_CASES = 8
MAX_TOTAL_JEV_CALLS = 60
DECISION_REQUEST = "leafcutter.decision_request.v1"
#: A repo-only deployment (no host research source): plan only needs Jev is confident about. With
#: the default 0.5 a merely supporting authoritative-guidance need paused the answerable case.
REPO_ONLY_RESEARCH = {"need_supporting_threshold": 0.8}


def load_cases(path: Path = EVAL_SET) -> list[dict[str, Any]]:
    """Load the labelled cases from the fixture file."""
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def classify(status: str) -> str:
    """Map a run status to one of the outcome classes."""
    if status in ("completed", "waiting_host", "waiting_human"):
        return status
    return "not_decided"


def task_for(case: dict[str, Any], root: Path) -> TaskInput:
    """Build the TaskInput of a case over the repository at `root`."""
    extra: dict[str, Any] = {}
    payload = case.get("payload")
    if payload is not None:
        payload = dict(payload)
        if case.get("basis"):
            basis = case["basis"]
            extra["initial_evidence"] = basis
            payload["evidence_ids"] = [evidence_id(b["locator"], content_hash(b["excerpt"]))
                                       for b in basis]
        extra["input_payload_schema"] = DECISION_REQUEST
        extra["input_payload"] = payload
    return TaskInput.model_validate({
        "goal": case["goal"], "caller": {"id": "kernel-eval", "kind": "host"},
        "scope": {"workspace_id": "leafcutter-eval", "repository_root": str(root)}, **extra})


def score(case: dict[str, Any], status: str, jev_calls: int | None) -> dict[str, Any]:
    """Return the scored row of a case: outcome class, pass flag and the false-decision flag."""
    outcome = classify(status)
    return {"id": case["id"], "category": case["category"], "expected": case["expected"],
            "status": status, "outcome": outcome, "jev_calls": jev_calls,
            "within_budget": jev_calls is not None and jev_calls <= case["max_jev_calls"],
            "passed": outcome in case["expected"],
            "fabricated_decision": outcome == "completed" and "completed" not in case["expected"]}


def _override(scratch: Path, case: dict[str, Any]) -> Path:
    """Write the per-case config override (scratch run root, Langfuse off, Jev call cap)."""
    path = scratch / f"config-{case['id']}.json"
    path.write_text(json.dumps({
        "paths": {"run_root": str(scratch / "run_root" / case["id"])},
        "limits": {"max_jev_calls": case["max_jev_calls"]},
        "research": REPO_ONLY_RESEARCH,
        "langfuse": {"enabled": False}}), encoding="utf-8")
    return path


async def _start(env: Any, task: TaskInput) -> Any:
    """Start one run on the case's environment."""
    return await KernelService(env).start_run(task)


def run_case(case: dict[str, Any], scratch: Path) -> dict[str, Any]:
    """Run one case live and return its scored row (with a short note on what the run said)."""
    env = build_environment(config_path=_override(scratch, case))
    try:
        envelope = asyncio.run(_start(env, task_for(case, repo_root())))
    finally:
        env.shutdown()
    row = score(case, envelope.status.value, envelope.usage_summary.jev_calls)
    pending = envelope.pending_interaction
    row["note"] = (getattr(pending, "operation", None) or getattr(pending, "question", None)
                   or "; ".join(envelope.limitations)[:160])
    return row


def run_eval(cases: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Run every case once and return the rows with totals."""
    scratch = scratch_dir("eval")
    rows = [run_case(case, scratch) for case in (cases or load_cases())]
    return {"rows": rows, "passed": sum(r["passed"] for r in rows), "total": len(rows),
            "jev_calls": sum(r["jev_calls"] or 0 for r in rows),
            "fabricated_decisions": [r["id"] for r in rows if r["fabricated_decision"]],
            "scratch": str(scratch)}


def render(report: dict[str, Any]) -> str:
    """Return the report as a fixed-width text table."""
    lines = [f"{'case':<26}{'category':<20}{'expected':<34}{'got':<15}{'jev':>4}  ok"]
    for r in report["rows"]:
        lines.append(f"{r['id']:<26}{r['category']:<20}{'/'.join(r['expected']):<34}"
                     f"{r['outcome']:<15}{r['jev_calls'] if r['jev_calls'] is not None else '?':>4}"
                     f"  {'yes' if r['passed'] else 'NO'}")
    lines.append(f"passed {report['passed']}/{report['total']}; jev calls {report['jev_calls']}; "
                 f"fabricated decisions: {report['fabricated_decisions'] or 'none'}")
    return "\n".join(lines)


def main() -> int:
    """Run the evaluation when LEAFCUTTER_KERNEL_LIVE=1 and print the report."""
    if os.environ.get("LEAFCUTTER_KERNEL_LIVE") != "1":
        print("set LEAFCUTTER_KERNEL_LIVE=1 to run the live evaluation", file=sys.stderr)
        return 2
    report = run_eval()
    out = Path(report["scratch"]) / "eval_results.json"
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(render(report))
    print(f"results: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 17:30 [python-coder]: Paused cases are not resumed: the first resting state is the
#   labelled outcome, which keeps the set under 60 Jev calls and tests routing and decision
#   behaviour rather than the synthetic answers. (#KernelBootstrapV0/P10)
# ====================================================================
