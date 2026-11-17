"""DK-300d-1: the real service consumes interpretation context before routing."""

from pathlib import Path
from unittest.mock import patch


from kernel.contracts import CallerContext, RunStatus, schema_ids
from kernel.persistence.checkpointer import build_serializer
from tests.kernel.entity_context.support import api, build, cards, config_for, recognize, task_for
from tests.kernel.intent.support import NEEDS_CONTEXT_ID


def test_service_checkpoints_entity_context_before_classifier_consumes_it(rig):
    # covers: DK-300d-1
    # angle: reachability
    rig.prepare()
    original = rig.jev.assess
    async def classify(batch):
        if batch.purpose == "kernel.intent":
            identities = {c["identity"] for c in batch.state.get("entity_context", {}).get("entities", [])}
            rig.intents = [("change" if "zephyr" in identities else NEEDS_CONTEXT_ID, .95, .95)]
        return await original(batch)
    with patch.object(rig.jev, "assess", new=classify):
        envelope = rig.start("Make Zephyr simpler", context=CallerContext(observations=["A caller claim"]))
    values = rig.values(envelope.run_id)
    assert values["task"].intent == "change" and envelope.status == RunStatus.BLOCKED
    assert envelope.pending_interaction is None
    saved = values["entity_context"]
    assert saved.kind == "entity_context" and saved.schema_version == "1.0"
    assert saved.original_goal == "Make Zephyr simpler" and "zephyr" in cards(saved)
    assert saved.caller_context.observations == ["A caller claim"]
    assert "context_enrichment" not in values or values["context_enrichment"] is None
    names = [e.kind for e in values["events"]]
    assert names.count("context.recognized") == 1
    assert names.index("context.recognized") < names.index("intent.assessed")
    assert "context.enriched" not in names


def test_explicit_output_contract_retains_routing_with_entity_context(rig):
    # covers: DK-300d-1
    # angle: criterion
    rig.prepare()
    caller = CallerContext(conversation=["Zephyr exports manifests"], capabilities=["unverified capability"])
    envelope = rig.start("Explain Zephyr", context=caller, requested_output_schema=schema_ids.EVIDENCE_BUNDLE)
    values = rig.values(envelope.run_id)
    assert values["task"].requested_output_schema == schema_ids.EVIDENCE_BUNDLE
    assert not rig.jev.questions_asked("kernel.intent")
    assert [event.kind for event in values["events"]].count("context.recognized") == 1
    saved = values["entity_context"]
    assert saved.entities and "evidence" not in saved.model_dump()
    assert saved.caller_context == caller
    assert saved.registered_capabilities == sorted(c.id for c in rig.snapshot.descriptors)
    assert "unverified capability" not in saved.registered_capabilities


def test_pass_statuses_are_versioned_and_truthful(repo):
    # covers: DK-300d-1
    # angle: criterion
    config = config_for()
    build(repo, config)
    results = [recognize(repo, "Zephyr"), recognize(repo, "ordinary prose"),
               recognize(repo, "Zephyr Decision Kernel", config=config_for(max_entities=1)),
               recognize(repo, "Zephyr", config=config_for(enabled=False))]
    (repo / config.entity_context.index_path).unlink()
    results.append(recognize(repo, "Zephyr"))
    assert {r.status for r in results} == {"recognized", "no_matches", "partial", "disabled", "unavailable"}
    serializer = build_serializer()
    for result in results:
        restored = serializer.loads_typed(serializer.dumps_typed(result))
        assert type(restored) is type(result) and restored == result
        assert restored.kind == "entity_context" and restored.schema_version == "1.0"
        assert restored.status not in {"gathered", "no_evidence"}


def test_unknown_new_name_and_entity_free_goal_do_not_force_questions(rig):
    # covers: DK-300d-1-i
    # angle: reachability
    rig.prepare()
    for goal in ("Implement a new FooWidget", "Please consider these ordinary words"):
        rig.intents = [("change", .95, .95)]
        with patch("kernel.context_enrichment.search_source", side_effect=AssertionError("pre-intent body search")):
            envelope = rig.start(goal)
        values = rig.values(envelope.run_id)
        saved = values["entity_context"]
        assert saved.status == "no_matches" and saved.coverage.scan_complete
        assert saved.budgets.lookups == 0 and not saved.entities
        assert envelope.pending_interaction is None and values["task"].intent == "change"
        assert not values["invocations"]


def test_disabled_recognition_reports_no_examination(repo):
    # covers: DK-300d-1-i
    # angle: criterion
    config = config_for(enabled=False)
    run = api("kernel.entity_context", "recognize_entities")
    with (patch.object(Path, "read_text", side_effect=AssertionError("disabled read")),
          patch.object(Path, "read_bytes", side_effect=AssertionError("disabled read"))):
        result = run(task_for(repo, "Zephyr"), config)
    assert result.status == "disabled" and result.coverage.index_status == "disabled"
    assert not result.coverage.scan_complete and result.budgets.lookups == 0
    assert not result.entities and result.coverage.index_fingerprint is None
