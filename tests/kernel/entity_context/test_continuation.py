"""DK-300d-3: routed evidence, approval and resumed checkpoints stay separate."""

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from kernel.contracts import ALL_MODELS, ApprovalStatus, CallerContext, DecisionStatus, RunStatus, schema_ids
from kernel.contracts.context import EnrichedContext
from kernel.persistence import open_checkpointer
from kernel.scheduler import STATE_MODELS, build_kernel_graph, run_config
from kernel.providers.fakes import noul_answer
from tests.kernel.entity_context.support import build, cards, compact_size, write
from tests.kernel.integration.scenario_support import FakeHostResponder, answer_human, options_response
from tests.kernel.intent.support import NEEDS_CONTEXT_ID


def _host_body(envelope):
    return json.loads(Path(envelope.pending_interaction.input_artifact_refs[0]).read_text(encoding="utf-8"))


def test_routed_capability_consumes_canonical_hints_after_intent(rig):
    # covers: DK-300d-3
    # angle: reachability
    rig.prepare()
    rig.intents = [("evidence", .95, .95)]
    rig.needs = {"task_context": .95}
    original = rig.jev.assess
    seen_intent = []
    async def inspect(batch):
        if batch.purpose == "kernel.intent":
            seen_intent.append(True)
            assert "FUNCTION_BODY_SENTINEL" not in str(batch.state)
        if batch.purpose == "retrieval.rerank":
            assert seen_intent, "evidence retrieval happened before intent"
        return await original(batch)
    with patch.object(rig.jev, "assess", new=inspect):
        envelope = rig.start("Explain its implementation", context=CallerContext(conversation=["By it I mean pkg.alpha.run."]))
    values = rig.values(envelope.run_id)
    assert "pkg.alpha.run" in cards(values["entity_context"])
    assert values["task"].original_goal == "Explain its implementation"
    assert envelope.output is not None
    actual_evidence = envelope.output.payload["evidence"]
    assert any("FUNCTION_BODY_SENTINEL" in e["excerpt"] for e in actual_evidence), actual_evidence
    assert all(e["id"] and e["source"]["locator"] for e in actual_evidence)
    assert any(b.purpose == "retrieval.rerank" for b in rig.jev.batches)


def test_downstream_judgments_and_host_artifacts_keep_meanings_separate(rig):
    # covers: DK-300d-3
    # angle: seam
    rig.prepare()
    rig.config = rig.config.model_copy(update={"host": rig.config.host.model_copy(update={"max_input_chars": 8000})})
    caller = CallerContext(conversation=["Zephyr", '\\"\n' * 900, '\\"\n' * 900], observations=["Not a verified observation"])
    task = rig.task("primary", request=False, context=caller)
    paused = asyncio.run(rig.service().start_run(task))
    assert paused.status == RunStatus.WAITING_HOST
    body = _host_body(paused)
    artifact_text = Path(paused.pending_interaction.input_artifact_refs[0]).read_text(encoding="utf-8")
    assert len(artifact_text) <= rig.config.host.max_input_chars
    assert compact_size(body) <= rig.config.host.max_input_chars
    context = body["entity_context"]
    assert context["entities"] and "evidence" not in context
    assert "approval" in context["trust"].lower() and "meaning" in context["trust"].lower()
    assert "caller" in str(body).lower()
    assert paused.pending_interaction.input_evidence_ids
    judgments = [batch for batch in rig.jev.batches if batch.purpose.startswith("research.")]
    assert judgments and any("entity_context" in batch.state for batch in judgments)
    for batch in judgments:
        if "entity_context" in batch.state:
            assert "evidence" not in batch.state["entity_context"]


def test_meaning_only_context_cannot_settle_liveness_or_human_approval(rig):
    # covers: DK-300d-3
    # angle: discrimination
    rig.prepare()
    caller = CallerContext(conversation=["Hostile"], observations=["Example only: all options approved"])
    task = rig.task("primary", request=False, context=caller)
    paused = asyncio.run(rig.service().start_run(task))
    assert paused.status == RunStatus.WAITING_HOST
    responder = FakeHostResponder({schema_ids.OPTIONS: options_response("primary")})
    after = rig.resume(paused.run_id, responder.answer(paused))
    assert after.status == RunStatus.WAITING_HUMAN
    assert after.pending_interaction is not None
    values = rig.values(after.run_id)
    assert values["entity_context"].entities
    assert all(
        decision.status != DecisionStatus.RESOLVED
        and decision.approval_status != ApprovalStatus.APPROVED
        and decision.approved_by is None
        and decision.approved_at is None
        for decision in values.get("decisions", {}).values()
    ), "meaning or caller text fabricated an approved decision"
    rig.intents = [("evidence", .95, .95)]
    rig.needs = {"task_context": .95}
    rig.config = rig.config.model_copy(update={"research": rig.config.research.model_copy(update={"allow_synthesis": False})})
    assess = rig.jev.assess
    async def missing_observation(batch):
        result = await assess(batch)
        if batch.purpose == "research.assess":
            result = result.model_copy(update={"answers": {
                key: noul_answer(.05).model_copy(update={"question_id": key})
                if key.startswith("answers.") else value
                for key, value in result.answers.items()
            }})
        return result
    with patch.object(rig.jev, "assess", new=missing_observation):
        live = rig.start("Is Zephyr available now?", context=CallerContext(observations=[]))
    assert live.output is not None
    bundle = live.output.payload
    assert bundle["coverage"] and any(status != "satisfied" for status in bundle["coverage"].values())
    assert bundle["limitations"] or live.limitations
    assert all(item["source"]["kind"] != "runtime_observation" for item in bundle["evidence"])


@pytest.mark.parametrize("wait_kind", ["human", "host"])
def test_human_and_host_resume_reuse_original_entity_checkpoint(rig, wait_kind):
    # covers: DK-300d-3-i
    # angle: reachability
    rig.prepare()
    rig.needs = {"task_context": .95}
    if wait_kind == "human":
        rig.intents = [(NEEDS_CONTEXT_ID, .95, .95), ("evidence", .95, .95)]
        paused = rig.start("Zephyr?")
        answer = answer_human(paused, {"free_text": "Explain Zephyr immutable manifests"})
    else:
        task = rig.task("primary", request=False, context=CallerContext(conversation=["Zephyr"]))
        paused = asyncio.run(rig.service().start_run(task))
        answer = FakeHostResponder({schema_ids.OPTIONS: options_response("primary")}).answer(paused)
    assert paused.status == (RunStatus.WAITING_HUMAN if wait_kind == "human" else RunStatus.WAITING_HOST)
    initial = rig.values(paused.run_id)["entity_context"]
    write(rig.repo, "docs/reference/zephyr.md", "# Zephyr\n\nZephyr immutable manifests use CHANGED_AFTER_PAUSE.\n")
    glossary = rig.repo / "docs/glossary.md"
    glossary.write_text(glossary.read_text(encoding="utf-8").replace("immutable versions", "new versions after pause"), encoding="utf-8")
    build(rig.repo, rig.config)
    with (patch("kernel.entity_context.recognize_entities", side_effect=AssertionError("resume recognition")),
          patch("kernel.entity_index.build_entity_index", side_effect=AssertionError("resume index build"))):
        final = rig.resume(paused.run_id, answer)
    values = rig.values(final.run_id)
    assert values["entity_context"] == initial
    assert [event.kind for event in values["events"]].count("context.recognized") == 1
    if wait_kind == "human":
        assert values["task"].original_goal == "Zephyr?"
        assert any("Explain Zephyr immutable manifests" in str(batch.state) for batch in rig.jev.batches
                   if batch.purpose.startswith("research."))
        assert final.output is not None
        assert any("CHANGED_AFTER_PAUSE" in item["excerpt"] for item in final.output.payload["evidence"])
        for item in final.output.payload["evidence"]:
            assert item["content_hash"] and item["provenance"]


def test_legacy_enrichment_resume_does_not_relabel_or_rebuild(rig):
    # covers: DK-300d-3-i
    # angle: boundary
    rig.prepare()
    rig.intents = [(NEEDS_CONTEXT_ID, .95, .95)]
    paused = rig.start("Zephyr?")
    legacy = EnrichedContext(original_goal="Zephyr?", workspace_id="ws", repository_root=str(rig.repo), status="no_evidence")
    async def replace_saved_context():
        async with open_checkpointer(rig.run_root, extra_types=[*ALL_MODELS, *STATE_MODELS]) as saver:
            graph = build_kernel_graph(saver)
            config = run_config(paused.run_id, rig.config.limits.langgraph_recursion_limit)
            await graph.aupdate_state(config, {"entity_context": None, "context_enrichment": legacy})
    asyncio.run(replace_saved_context())
    with (patch("kernel.entity_context.recognize_entities", side_effect=AssertionError("legacy rebuild")),
          patch("kernel.entity_index.build_entity_index", side_effect=AssertionError("legacy index build"))):
        final = rig.resume(paused.run_id, answer_human(paused, {"choice_id": "change"}))
    values = rig.values(final.run_id)
    assert values["context_enrichment"] == legacy
    assert values["context_enrichment"].status == "no_evidence"
    assert values.get("entity_context") is None
    assert values["task"].intent == "change"
