"""Paired live intent probe: one current classifier prompt, with and without enrichment.

This is deliberately separate from the isolated step evaluation. Each goal is classified
twice by the real provider, using identical question instructions and thresholds. Baseline
outcomes are observations, not pass requirements. Enriched classifications must meet the
independent labels. Five pairs are a smoke evaluation, not a causal or statistical claim.
Run with LEAFCUTTER_KERNEL_LIVE=1; no downstream capability or host work is executed.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from kernel.bootstrap import build_environment
from kernel.context_enrichment import gather_context
from kernel.contracts import CorrelationIds
from kernel.intent.classify import INTENT_TEMPLATE_REV, assess_intent, build_batch
from tests.kernel.enrichment.eval_runner import config_for, load_cases, task_for, write_repo

MAX_ASSESSMENTS = 10


def live_cases() -> list[dict[str, Any]]:
    """Return five labelled goals, reusing independent fixture passages where applicable."""
    by_id = {case["id"]: copy.deepcopy(case) for case in load_cases()}
    capability = by_id["original_capability_question"]
    capability["expected_intent"] = "evidence"
    conversation = by_id["conversation_resolves_referent"]
    conversation.update(id="conversation_requests_ideas", goal="Same for Zephyr, please.",
                        expected_intent="ideas")
    conversation["context"]["conversation"] = [
        "User: Give me three architectural ideas for the cache, without selecting one.",
        "Assistant: I listed three cache architecture options. Zephyr is our export manifest."]
    acronym = by_id["project_acronym"]
    acronym["expected_intent"] = "evidence"
    preference = by_id["private_preference_stays_unknown"]
    preference.update(id="clear_choice_request_with_unknown_preference",
                      goal="Should I choose memory or disk for the cache, based on my personal preference?",
                      expected_intent="decision")
    ambiguity = by_id["unrelated_repository"]
    ambiguity.update(id="genuinely_ambiguous_reference", goal="That.",
                     expected_intent="insufficient_context")
    return [capability, conversation, acronym, preference, ambiguity]


def outcome(assessment: Any) -> str:
    """Keep uncertainty/unavailability distinct from a selected answer kind."""
    return assessment.kind if assessment.kind else assessment.outcome.value


def assessment_row(assessment: Any) -> dict[str, Any]:
    """Record the judgement and usage, never credentials or private provider payloads."""
    return {"outcome": outcome(assessment), "confidence": assessment.confidence,
            "probabilities": assessment.probabilities, "reason_codes": assessment.reason_codes,
            "model_id": assessment.model_id,
            "jev_calls": sum(usage.calls for usage in assessment.usage)}


async def _run_pairs(env: Any, cases: list[dict[str, Any]], scratch: Path) -> list[dict[str, Any]]:
    """Create and close the production adapter in one event loop; each case gets two calls."""
    if env.jev_factory is None:
        raise RuntimeError("live intent evaluation requires configured Jev credentials")
    jev = env.jev_factory()
    rows = []
    try:
        for case in cases:
            root = scratch / case["id"]
            write_repo(case, root)
            task, config = task_for(case, root), config_for(case)
            context = gather_context(task, config, env.snapshot, redactor=env.redactor)
            corr = CorrelationIds()
            baseline_batch = build_batch(task.goal, [], [], corr,
                                         max_state_chars=config.jev.max_state_chars)
            enriched_batch = build_batch(task.goal, [], [], corr, context=context,
                                         max_state_chars=config.jev.max_state_chars)
            if baseline_batch.questions != enriched_batch.questions:
                raise AssertionError("paired classifications must use the same current prompt")
            baseline = await assess_intent(jev, task.goal, [], [], config.intent, corr,
                                           max_state_chars=config.jev.max_state_chars)
            enriched = await assess_intent(jev, task.goal, [], [], config.intent, corr,
                                           context=context,
                                           max_state_chars=config.jev.max_state_chars)
            before, after = assessment_row(baseline), assessment_row(enriched)
            rows.append({"id": case["id"], "goal": task.goal,
                         "expected_enriched_intent": case["expected_intent"],
                         "baseline": before, "enriched": after,
                         "changed": before["outcome"] != after["outcome"],
                         "context_status": context.status,
                         "context_files_scanned": context.files_scanned,
                         "context_sources": [item.locator for item in context.evidence],
                         "passed": after["outcome"] == case["expected_intent"]})
    finally:
        close = getattr(jev, "aclose", None)
        if close is not None:
            await close()
    return rows


def run_eval() -> dict[str, Any]:
    """Run bounded real-provider pairs through production environment configuration."""
    if os.environ.get("LEAFCUTTER_KERNEL_LIVE") != "1":
        raise RuntimeError("set LEAFCUTTER_KERNEL_LIVE=1 to run the live intent evaluation")
    cases = live_cases()
    if not cases or len(cases) * 2 > MAX_ASSESSMENTS:
        raise ValueError("the live evaluation must fit its nonempty assessment budget")
    with tempfile.TemporaryDirectory(prefix="kernel-context-live-") as temporary:
        scratch = Path(temporary)
        override = scratch / "config.json"
        override.write_text(json.dumps({"paths": {"run_root": str(scratch / "runs")},
                                        "langfuse": {"enabled": False}}), encoding="utf-8")
        env = build_environment(config_path=override)
        try:
            rows = asyncio.run(_run_pairs(env, cases, scratch))
        finally:
            env.shutdown()
    calls = sum(row[arm]["jev_calls"] for row in rows for arm in ("baseline", "enriched"))
    return {"evaluation": "paired_live_intent_after_context_enrichment",
            "intent_template_revision": INTENT_TEMPLATE_REV,
            "comparison": "Same current intent prompt; baseline omits enrichment only.",
            "interpretation": "One observation per arm and case; unchanged outcomes do not prove enrichment helped. This small probe does not establish statistical or causal improvement.",
            "rows": rows, "total": len(rows), "passed": sum(row["passed"] for row in rows),
            "assessment_attempts": len(rows) * 2, "jev_calls": calls,
            "max_assessments": MAX_ASSESSMENTS}


def main(argv: list[str] | None = None) -> int:
    """Write/print the report and fail if any enriched classification has the wrong label."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args(argv)
    if os.environ.get("LEAFCUTTER_KERNEL_LIVE") != "1":
        print("set LEAFCUTTER_KERNEL_LIVE=1 to run the live intent evaluation", file=sys.stderr)
        return 2
    report = run_eval()
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    if arguments.output:
        arguments.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
