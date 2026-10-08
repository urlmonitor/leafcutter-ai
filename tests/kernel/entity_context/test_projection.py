"""DK-300d-2: size is the exact receiver state-plus-questions envelope."""

import asyncio
from dataclasses import replace

import pytest

from kernel.capabilities.decision.jev_support import make_batch, noul_question
from kernel.contracts import CallerContext, CorrelationIds
from kernel.intent.classify import assess_intent, build_batch
from kernel.providers.base import JevPayloadTooLarge
from kernel.providers.fakes import ScriptedJev, choice_answer
from kernel.providers.jev_wire import question_to_wire
from tests.kernel.entity_context.support import build, compact_size, config_for, payload, recognize
from tests.kernel.helpers import make_context


def wire(batch):
    """The actual Jev receiver contract, including escaped questions and key overhead."""
    return {"state": batch.state, "questions": {q.id: question_to_wire(q) for q in batch.questions}}


def _large(repo):
    build(repo)
    caller = CallerContext(conversation=['"\\\n' * 1000] * 3)
    return recognize(repo, "Zephyr", context=caller)


def test_exact_receiver_envelope_fits_after_optional_context_reduction(repo):
    # covers: DK-300d-2
    # angle: boundary
    context = _large(repo)
    goal = ' \n' + ('ü"\\\n' * 1000) + ' tail '
    base = build_batch(goal, [], [], CorrelationIds())
    cap = compact_size(wire(base)) + 1800
    saved = context.model_dump_json()
    batch = build_batch(goal, [], [], CorrelationIds(), entity_context=context, max_state_chars=cap)
    assert compact_size(wire(batch)) <= cap
    assert batch.state["task"]["goal"] == goal and batch.questions == base.questions
    assert batch.state["task"] == base.state["task"]
    assert context.model_dump_json() == saved
    assert "entity_context" in batch.state
    assert batch.state["entity_context"]["limitations"]


def test_projection_retains_identity_occurrence_provenance_without_mutating_checkpoint(repo):
    # covers: DK-300d-2
    # angle: criterion
    build(repo)
    context = recognize(repo, " ".join(["Zephyr"] * 100))
    before = context.model_dump_json()
    projected = payload(context)
    card = projected["entities"][0]
    assert card["identity"] == "zephyr" and card["occurrence_count"] == 100
    assert len(card["matches"]) == 1
    assert card["provenance"] == context.entities[0].provenance.model_dump(mode="json")
    assert "evidence" not in projected
    assert "meaning" in projected["trust"].lower() and "approval" in projected["trust"].lower()
    assert context.model_dump_json() == before and len(context.entities[0].matches) == 100


def test_native_judgments_share_the_actual_receiver_budget(repo):
    # covers: DK-300d-2
    # angle: seam
    context = _large(repo)
    config = config_for()
    config = config.model_copy(update={"jev": config.jev.model_copy(update={"max_state_chars": 2500})})
    execution = replace(make_context(repo, config=config), entity_context=context)
    question = noul_question("sufficient", "entity.native", "Is the evidence sufficient?" + '\\"' * 80)
    state = {"task": {"goal": "Zephyr"}, "required": "retain me"}
    batch = make_batch(execution, "entity.native", state, [question])
    assert compact_size(wire(batch)) <= 2500
    assert batch.state["task"] == state["task"] and batch.state["required"] == "retain me"
    assert batch.questions == [question]
    intent = build_batch("Zephyr", [], [], CorrelationIds(), entity_context=context, max_state_chars=2500)
    assert compact_size(wire(intent)) <= 2500


def test_required_envelope_overflow_rejects_before_provider_call(repo):
    # covers: DK-300d-2-i
    # angle: boundary
    context = _large(repo)
    goal = '"\\\n' * 1000 + " tail"
    required = build_batch(goal, [], [], CorrelationIds())
    cap = compact_size(wire(required)) - 1
    assert compact_size(required.state) < cap  # specifically catches state-only sizing
    provider = ScriptedJev().script("kernel.intent", "intent.*", choice_answer("evidence"))
    with pytest.raises(JevPayloadTooLarge):
        asyncio.run(assess_intent(provider, goal, [], [], config_for().intent, CorrelationIds(),
                                 entity_context=context, max_state_chars=cap))
    assert not provider.batches
    assert required.state["task"]["goal"] == goal


def test_exact_fit_required_envelope_omits_optional_context_safely(repo, caplog):
    # covers: DK-300d-2-i
    # angle: criterion
    context = _large(repo)
    base = build_batch("Zephyr", [], [], CorrelationIds())
    cap = compact_size(wire(base))
    batch = build_batch("Zephyr", [], [], CorrelationIds(), entity_context=context, max_state_chars=cap)
    assert batch.state == base.state and batch.questions == base.questions
    assert compact_size(wire(batch)) == cap
    assert any("omit" in record.message.lower() for record in caplog.records)
