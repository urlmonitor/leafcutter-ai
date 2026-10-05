"""DK-300e-1: recognition accounting never claims later work was avoided."""

import itertools
from unittest.mock import patch

from tests.kernel.entity_context.support import api, task_for


def test_trace_stages_report_scoped_recognition_work_before_intent(rig):
    # covers: DK-300e-1
    # angle: reachability
    rig.prepare()
    rig.intents = [("change", .95, .95)]
    envelope = rig.start("Zephyr")
    saved = rig.values(envelope.run_id)["entity_context"]
    calls = [call for tracer in rig.tracers for call in tracer.calls]
    names = [call.name for call in calls]
    stages = ["entity.recognition", "entity.resolution", "entity.projection", "context.recognized"]
    assert all(stage in names for stage in stages)
    assert [names.index(stage) for stage in stages] == sorted(names.index(stage) for stage in stages)
    summary = next(call.data["payload"] for call in calls if call.name == "context.recognized")
    assert summary["coverage"] == saved.coverage.model_dump(mode="json")
    assert summary["budgets"]["jev_calls"] == 0
    assert summary["budgets"]["lookups"] == saved.budgets.lookups == 1
    assert summary["budgets"]["serialized_chars"] == saved.budgets.serialized_chars
    assert summary["budgets"]["elapsed_ms"] >= 0
    assert len(rig.jev.batches) == 1 and rig.jev.batches[0].purpose == "kernel.intent"
    assert "A manifest exporter" not in str(summary)


def test_trace_distinguishes_incomplete_scan_omitted_cards_and_later_work(rig):
    # covers: DK-300e-1
    # angle: seam
    rig.prepare(max_entities=1)
    rig.intents = [("evidence", .95, .95)]
    rig.needs = {"task_context": .95}
    envelope = rig.start("Explain Zephyr and Decision Kernel")
    saved = rig.values(envelope.run_id)["entity_context"]
    assert saved.coverage.scan_complete and saved.coverage.counts.omitted > 0
    assert saved.budgets.jev_calls == 0
    assert any(batch.purpose == "retrieval.rerank" for batch in rig.jev.batches)
    assert len(rig.jev.batches) > 1
    summary = next(call.data["payload"] for tracer in rig.tracers for call in tracer.calls if call.name == "context.recognized")
    assert summary["coverage"]["scan_complete"] is True
    assert summary["coverage"]["counts"]["omitted"] > 0
    run = api("kernel.entity_context", "recognize_entities")
    with patch("time.monotonic", side_effect=itertools.chain([0.0], itertools.repeat(3.0))):
        expired = run(task_for(rig.repo, "Zephyr and Decision Kernel"), rig.config)
    assert not expired.coverage.scan_complete and expired.budgets.lookups == 0
    assert expired.limitations != saved.limitations
