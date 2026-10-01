"""Public standalone observation checks without any external telemetry delivery.

MODULE: test_query_answer_contract_acceptance_observation
GOAL: Separate completed retrieval, local observation and verified remote visibility.
BUSINESS CONTEXT: A caller must not mistake a trace ID for a remotely inspectable trace.
ARCHITECTURE: Real public CLI over controlled storage and injected observation boundary.
"""
import json
import sys

import pytest

from knowledge import __main__ as cli
from knowledge.contracts import Entity, ProjectionSnapshot, SourceReference
from knowledge.service import KnowledgeService
from tests.knowledge.query_answer_contract_acceptance_support import (
    ProjectionStorage, REPOSITORY_ID, SOURCE_SHA, public_request,
)


@pytest.fixture
def controlled_storage():
    """Use a labeled controlled result, not a canonical-source query oracle."""
    entity = Entity(canonical_id="AC-CONTROL", kind="AcceptanceCriterion", title="Controlled metadata",
        source=SourceReference(repository_id=REPOSITORY_ID, source_sha=SOURCE_SHA,
                               path="docs/acceptance/controlled.yml"))
    snapshot = ProjectionSnapshot(repository_id=REPOSITORY_ID, source_sha=SOURCE_SHA,
        generation_id="controlled-observation-generation", nodes=[entity])
    return ProjectionStorage(snapshot, ["AC-CONTROL"])


def invoke_observed_cli(monkeypatch, tmp_path, capsys, storage, observer=None, *, require_status=False):
    """Invoke actual argv serialization and the public optional observer contract."""
    request = public_request("AC-CONTROL", required_fields=["work_status"] if require_status else None)
    request["disclosure_level"] = 0
    path = tmp_path / "observation-request.json"
    path.write_text(json.dumps(request), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["knowledge", "retrieve", "--repository-id", REPOSITORY_ID,
                                      "--request", str(path)])
    def factory(config, **kwargs):
        return KnowledgeService(storage, cursor_secret=b"qa-local-observation", **kwargs)
    monkeypatch.setattr(cli, "build_retriever", factory)
    code = cli.main() if observer is None else cli.main(observer=observer)
    captured = capsys.readouterr()
    return code, json.loads(captured.out or captured.err)


def test_public_cli_disabled_observation_is_explicit(monkeypatch, tmp_path, capsys, controlled_storage):
    # covers: KM-500g-1-i
    # angle: reachability
    """No observer produces a useful answer plus an honest disabled delivery state."""
    code, output = invoke_observed_cli(monkeypatch, tmp_path, capsys, controlled_storage)
    assert code == 0
    assert output["status"] == "ok"
    observation = output.get("observation")
    assert observation and observation["state"] == "disabled", output
    assert observation.get("trace_url") is None
    assert len(controlled_storage.calls) == 1


def test_public_cli_local_observation_is_unverified_and_once(monkeypatch, tmp_path, capsys, controlled_storage):
    # angle: reachability
    # angle: criterion
    # covers: KM-500g-1
    # angle: seam
    """A successful local sink is not evidence of remote trace visibility."""
    seen = []
    def observe(request, result):
        seen.append((request, result.model_copy(deep=True)))
        return {"state": "unverified", "trace_id": "controlled-local-id", "trace_url": None,
                "request_id": request.request_id, "retrieval_id": result.retrieval_id,
                "reason": "Local test sink only; no remote verification."}
    code, output = invoke_observed_cli(monkeypatch, tmp_path, capsys, controlled_storage, observe)
    assert code == 0
    assert len(seen) == 1
    assert len(controlled_storage.calls) == 1
    assert seen[0][1].retrieval_id == output["retrieval_id"]
    assert output["observation"]["state"] == "unverified"
    assert output["observation"]["trace_url"] is None


def test_public_cli_observer_failure_does_not_repeat_retrieval(monkeypatch, tmp_path, capsys, caplog, controlled_storage):
    # angle: criterion
    # angle: seam
    # covers: KM-500g-1-i
    # angle: failure
    """Local telemetry failure preserves the completed result without extra storage work."""
    seen = []
    def observe(request, result):
        seen.append(result.retrieval_id)
        raise RuntimeError("controlled-sensitive-observer-detail-must-not-appear")
    code, output = invoke_observed_cli(monkeypatch, tmp_path, capsys, controlled_storage, observe)
    assert code == 0
    assert output["status"] == "ok"
    assert output["evidence"][0]["entity"]["canonical_id"] == "AC-CONTROL"
    assert len(seen) == 1 and len(controlled_storage.calls) == 1
    assert output["observation"]["state"] == "unavailable"
    assert output["observation"].get("trace_url") is None
    records = [record for record in caplog.records if record.name == "knowledge.observation"]
    assert len(records) == 1
    assert records[0].levelname == "WARNING"
    assert records[0].getMessage() == "Observation delivery failed"
    assert records[0].exc_info is None and records[0].stack_info is None
    assert "controlled-sensitive-observer-detail-must-not-appear" not in caplog.text
    assert "controlled-sensitive-observer-detail-must-not-appear" not in json.dumps(output)


@pytest.mark.parametrize("delivery,expected", [("ok", "unverified"), ("degraded", "unavailable")])
def test_real_app_observer_withholds_candidate_url_until_verified(monkeypatch, tmp_path, capsys, controlled_storage, delivery, expected):
    # angle: reachability
    # angle: criterion
    # angle: seam
    # covers: KM-500g-1
    # covers: KM-500g-1-i
    # angle: discrimination
    """Actual adapter must withhold a fake tracer's plausible URL unless remote verified."""
    from integrations.knowledge_observation import RetrievalObserver
    from kernel.contracts.enums import ObservabilityStatus
    from tests.kernel.adapters.support import SegmentTracer
    tracer = SegmentTracer(status=ObservabilityStatus(delivery))
    observer = RetrievalObserver(tracer)
    code, output = invoke_observed_cli(monkeypatch, tmp_path, capsys, controlled_storage,
                                       observer.observe, require_status=True)
    assert code == 0 and output["status"] == "ok"
    assert output["answer"]["status"] != "fulfilled"
    assert output["observation"]["state"] == expected
    assert output["observation"]["trace_url"] is None, "A candidate URL is not verified remote evidence."
    assert len(controlled_storage.calls) == 1 and tracer.closed_segments == 1
    spans = tracer.named("knowledge.retrieve", "span")
    assert len(spans) == 1
    metadata = spans[0].data["metadata"]
    assert metadata["retrieval_id"] == output["retrieval_id"]
    assert metadata["execution_status"] == "ok"
    assert metadata["answer_status"] == output["answer"]["status"]
    assert metadata.get("completeness") == output["answer"]["completeness"], metadata
    assert metadata["missing_fields"] == output["answer"]["missing_fields"]


@pytest.mark.parametrize("failure", ["initialize", "shutdown"])
def test_application_cli_telemetry_failure_preserves_single_retrieval(monkeypatch, tmp_path, capsys, controlled_storage, failure):
    # covers: KM-500g-1-i
    # angle: failure
    """Real application composition preserves output across tracer init and finalization errors."""
    from types import SimpleNamespace
    from integrations import knowledge_cli as app
    from kernel.observability import langfuse_tracer
    from kernel import config as kernel_config, bootstrap, secrets
    from tests.kernel.adapters.support import SegmentTracer
    tracer = SegmentTracer()
    def broken_shutdown():
        raise RuntimeError("controlled shutdown failure")
    tracer.shutdown = broken_shutdown
    def construct(**kwargs):
        if failure == "initialize":
            raise RuntimeError("controlled initialization failure")
        return tracer
    monkeypatch.setattr(langfuse_tracer, "LangfuseTracer", construct)
    monkeypatch.setattr(kernel_config, "load_kernel_config", lambda path: SimpleNamespace(
        langfuse=object(), data_policy=object(), retrieval=SimpleNamespace(deny_globs=[])))
    monkeypatch.setattr(secrets, "load_secrets", lambda: object())
    monkeypatch.setattr(bootstrap, "resolve_run_root", lambda config, root: tmp_path)
    request = public_request("AC-CONTROL")
    request["disclosure_level"] = 0
    path = tmp_path / "app-request.json"
    path.write_text(json.dumps(request), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["app", "--observability-config", "controlled.yml", "retrieve",
        "--repository-id", REPOSITORY_ID, "--request", str(path)])
    monkeypatch.setattr(cli, "build_retriever", lambda config, **kwargs: KnowledgeService(
        controlled_storage, cursor_secret=b"qa-app-only", **kwargs))
    code = app.main()
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert code == 0 and output["status"] == "ok"
    assert len(controlled_storage.calls) == 1
    assert output["evidence"][0]["entity"]["canonical_id"] == "AC-CONTROL"
    assert output["observation"]["state"] == ("unavailable" if failure == "initialize" else "unverified")
    assert output["observation"]["trace_url"] is None


@pytest.mark.parametrize("allowance", [2048, 4096])
def test_verbose_observer_cannot_exceed_cumulative_page_budget(controlled_storage, allowance):
    # covers: KM-500g-1-i
    # angle: boundary
    """Actual continuation output, including long observer fields, stays within total budget."""
    import asyncio
    from knowledge.contracts import KnowledgeRetrievalRequest
    from knowledge.errors import KnowledgeError
    nodes = [controlled_storage.nodes[0].model_copy(deep=True) for _ in range(3)]
    for index, node in enumerate(nodes):
        node.canonical_id = "AC-CONTROL-" + str(index)
    controlled_storage.nodes = nodes
    controlled_storage.snapshot.nodes = nodes
    seen = []
    def verbose_observer(request, result):
        seen.append(result.retrieval_id)
        return {"state": "unverified", "trace_id": "x" * 512, "reason": "r" * 512,
                "request_id": "q" * 512, "retrieval_id": "i" * 512, "trace_url": "https://trace.example/" + "u" * 480}
    service = KnowledgeService(controlled_storage, cursor_secret=b"qa-observer-pages", observer=verbose_observer)
    raw = public_request(nodes[0].canonical_id)
    raw["arguments"]["entity_ids"] = [node.canonical_id for node in nodes]
    raw["disclosure_level"] = 0
    raw["budget"] = {"max_results": 1, "max_candidates": 50, "max_rounds": 3,
                     "max_content_bytes": allowance, "max_estimated_tokens": allowance // 4}
    async def pages():
        total = 0
        for _ in range(3):
            try:
                result = await service.retrieve(KnowledgeRetrievalRequest.model_validate(raw))
            except KnowledgeError:
                break  # Exhausted cumulative response allowance is an explicit boundary failure.
            total += len(result.model_dump_json().encode())
            assert total <= allowance, (total, allowance, result.model_dump())
            assert result.observation.get("trace_url") is None
            if not result.continuation:
                break
            raw["continuation"] = result.continuation
        assert total > 0
        assert len(seen) <= len(controlled_storage.calls)
    asyncio.run(pages())
