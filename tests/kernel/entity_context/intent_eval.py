"""Paired intent observations; caller context is identical in both comparison arms.

This harness accepts an explicit provider. Offline tests use a controlled provider;
live callers can pass their configured Jev adapter without changing the experiment.
It never turns historical DK-200 recognition scores into DK-300 evidence.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from kernel.context_enrichment import gather_context
from kernel.contracts import CallerContext, CorrelationIds
from kernel.intent.classify import assess_intent
from tests.conftest import load_fixture
from tests.kernel.entity_context.support import api, build, config_for, task_for, write_repo


async def run_pairs(provider, cases=None) -> dict:
    """Measure real assessments separately from deterministic recognition work."""
    selected = load_fixture("entity_evaluation/corpus")["intent_pairs"] if cases is None else cases
    if not selected:
        raise ValueError("paired intent evaluation requires at least one case")
    rows = []
    with tempfile.TemporaryDirectory(prefix="entity-intent-pairs-") as temporary:
        for case in selected:
            root = Path(temporary) / case["id"]
            write_repo(root)
            config = config_for()
            config = config.model_copy(update={"context_enrichment": config.context_enrichment.model_copy(update={"source_ids": ["eval.entities"]})})
            build(root, config)
            caller = CallerContext.model_validate(case["context"])
            task = task_for(root, case["goal"], context=caller)
            baseline = gather_context(task, config)
            entity = api("kernel.entity_context", "recognize_entities")(task, config)
            assert baseline.caller_context == entity.caller_context, "paired caller context changed"
            arms = {}
            for label, kwargs in (("baseline", {"context": baseline}), ("entity", {"entity_context": entity})):
                assessment = await assess_intent(provider, task.goal, [], [], config.intent,
                                                 CorrelationIds(), max_state_chars=config.jev.max_state_chars, **kwargs)
                outcome = assessment.kind or assessment.outcome.value
                arms[label] = {"intent": outcome, "clarification": outcome == "insufficient_context",
                               "model_calls": sum(usage.calls or 0 for usage in assessment.usage),
                               "caller_context": caller.model_dump(mode="json")}
            rows.append({"id": case["id"], "expected": case["expected"], **arms,
                         "recognition_model_calls": entity.budgets.jev_calls,
                         "passed": arms["entity"]["intent"] == case["expected"]})
    return {"evaluation": "paired_intent", "baseline": "historical lexical gather_context with same caller context",
            "rows": rows, "total": len(rows), "passed": sum(row["passed"] for row in rows),
            "model_calls": sum(row[arm]["model_calls"] for row in rows for arm in ("baseline", "entity")),
            "interpretation": "Controlled or live provider as explicitly supplied; this comparison does not establish causal or statistical improvement."}
