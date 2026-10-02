"""Context projection stays within the provider's remaining serialised payload budget.

Type: integration. Angles: boundary, seam, failure.
The base request and checkpointed context are immutable; only the provider copy shrinks.
"""

from __future__ import annotations

import copy
import unittest
from dataclasses import replace
from pathlib import Path

from kernel.capabilities.decision.jev_support import make_batch, noul_question
from kernel.config import load_kernel_config
from kernel.contracts import CorrelationIds, content_hash
from kernel.contracts.base import canonical_json
from kernel.contracts.context import CallerContext, ContextExcerpt, EnrichedContext
from kernel.enrichment_projection import attach_context, context_payload
from kernel.intent.classify import build_batch
from tests.kernel.helpers import make_context


def snapshot(text: str = "x" * 4000) -> EnrichedContext:
    """Build a legal, large context using the production serializer and field contracts."""
    return EnrichedContext(
        original_goal="Can you check the kernel?", workspace_id="projection-eval",
        repository_root=str(Path.cwd()), status="gathered",
        caller_context=CallerContext(host="Codex", conversation=[text, text, text]),
        evidence=[ContextExcerpt(source_id="eval.docs", locator=f"docs/kernel-{i}.md#L1",
                                 excerpt=text, content_hash=content_hash(text)) for i in range(5)],
        registered_capabilities=["research", "decision", "retrieve.repository"],
        sources_consulted=["eval.docs"], files_scanned=5)


def base_request(size: int = 30404) -> dict:
    """Make a request whose real JSON size is precisely the reviewer's counterexample size."""
    state = {"task": {"goal": "Can you check the kernel?", "input": ""},
             "criteria": ["Use the supplied evidence"]}
    state["task"]["input"] = "a" * (size - len(canonical_json(state)))
    return state


class TestContextProjection(unittest.TestCase):
    """DK-102: bounds count escaped JSON and leave the caller's work intact."""

    # covers: DK-200b-4
    # covers: DK-102
    def test_near_limit_request_fits_with_plain_or_json_escaped_context(self) -> None:
        for name, text in (("plain", "x" * 4000), ("escaped", ('"\\\n' * 1334)[:4000])):
            with self.subTest(encoding=name):
                context, base = snapshot(text), base_request()
                saved_context, saved_base = context.model_dump(), copy.deepcopy(base)
                self.assertEqual(len(canonical_json(base)), 30404)
                self.assertGreater(len(canonical_json(
                    {**base, "context_enrichment": context_payload(context)})), 60000)
                projected = attach_context(base, context, 60000)
                self.assertLessEqual(len(canonical_json(projected)), 60000)
                self.assertEqual(base, saved_base)
                self.assertEqual(context.model_dump(), saved_context)
                self.assertEqual({key: projected[key] for key in base}, saved_base)
                self.assertTrue(projected["context_enrichment"]["truncated"])
                self.assertTrue(any("budget" in note for note in
                                    projected["context_enrichment"]["limitations"]))

    # covers: DK-200b-4-i
    # covers: DK-102
    def test_no_room_omits_context_without_altering_or_oversizing_the_request(self) -> None:
        context, base = snapshot(), base_request()
        saved_context, saved_base = context.model_dump(), copy.deepcopy(base)
        with self.assertLogs("kernel.enrichment_projection", level="WARNING") as logs:
            projected = attach_context(base, context, len(canonical_json(base)))
        self.assertTrue(any("context projection omitted" in message for message in logs.output))
        self.assertEqual(projected, saved_base)
        self.assertLessEqual(len(canonical_json(projected)), 30404)
        self.assertEqual(base, saved_base)
        self.assertEqual(context.model_dump(), saved_context)

    # covers: DK-200b-4-ii
    # covers: DK-102
    def test_data_policy_removes_evidence_from_projection_but_not_checkpoint(self) -> None:
        context = snapshot("repository-only-sentinel")
        saved = context.model_dump()
        projected = attach_context({"goal": context.original_goal}, context, 60000,
                                   send_repo_excerpts=False)
        self.assertEqual(projected["context_enrichment"]["evidence"], [])
        self.assertTrue(any("withheld" in note for note in
                            projected["context_enrichment"]["limitations"]))
        self.assertTrue(context.evidence)
        self.assertEqual(context.model_dump(), saved)
        allowed = attach_context({"goal": context.original_goal}, context, 60000)
        self.assertEqual(len(allowed["context_enrichment"]["evidence"]), 5)

    # covers: DK-200b-4
    # covers: DK-102
    def test_downstream_batch_uses_configured_remaining_allowance(self) -> None:
        config = load_kernel_config()
        config = config.model_copy(update={"jev": config.jev.model_copy(
            update={"max_state_chars": 36000})})
        context, base = snapshot(), base_request()
        execution = replace(make_context(Path.cwd(), config=config), context_enrichment=context)
        question = noul_question("sufficient", "eval.projection", "Is the evidence sufficient?")
        batch = make_batch(execution, "eval.projection", base, [question])
        self.assertLessEqual(len(canonical_json(batch.state)), 36000)
        self.assertEqual(batch.state["task"], base["task"])
        self.assertTrue(batch.state["context_enrichment"]["truncated"])

    # covers: DK-200b-4
    # covers: DK-102
    def test_intent_batch_preserves_goal_while_projecting_context_with_its_budget(self) -> None:
        context = snapshot()
        goal = "g" * 4000
        baseline = build_batch(goal, [], [], CorrelationIds())
        batch = build_batch(goal, [], [], CorrelationIds(), context=context,
                            max_state_chars=8000)
        self.assertEqual(batch.questions, baseline.questions)
        self.assertEqual(batch.state["task"], baseline.state["task"])
        self.assertLessEqual(len(canonical_json(batch.state)), 8000)
        self.assertTrue(batch.state["context_enrichment"]["truncated"])


if __name__ == "__main__":
    unittest.main()
