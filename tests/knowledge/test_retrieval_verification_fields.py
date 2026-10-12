"""Public packet/consumer regressions; host and Jev answers are controlled.

These tests prove wiring, source fidelity and no deterministic field expansion.
The separate frozen blind-host evaluation measures semantic selection quality.
"""

import asyncio
import json
import subprocess
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import pytest
import yaml

from kernel.capabilities.host.retrieval_needs import RetrievalNeeds
from kernel.contracts import RunStatus, schema_ids
from kernel.contracts.retrieval_needs import RetrievalNeedsRequest
from tests.knowledge.public_retrieval_needs_support import (
    ROOT, PublicNeedsHarness, answer_assessments, controlled_needs,
    host_submission, packet_request, source_snapshot,
)


@pytest.fixture
def harness(request):
    value = PublicNeedsHarness().configure(catalog_enabled=request.param)
    yield value
    value.doCleanups()


def _source(identifier):
    node = next(item for item in source_snapshot().nodes if item.canonical_id == identifier)
    raw = subprocess.check_output(
        ["git", "show", f"{node.source.source_sha}:{node.source.path}"], cwd=ROOT)
    return node, yaml.safe_load(raw)


@pytest.mark.parametrize("harness", [False, True], indirect=True)
@pytest.mark.parametrize("identifier", ["KM-500c-1", "KM-500c-2"])
def test_public_verification_fields_reach_pinned_source(harness, identifier):
    # covers: KM-500e-1-i
    # covers: KM-500e-2
    # angle: seam
    """Both accepted obligations survive the real packet, ledger, query and source boundary."""
    async def check():
        question = f"For {identifier}, what must tests demonstrate?"
        task = harness.question(question)
        assert "answer_requirements" not in task.input_payload
        pending = await harness.service().start_run(task)
        assert pending.status is RunStatus.WAITING_HOST
        packet = pending.pending_interaction
        assert packet.operation == "interpret_retrieval_needs"
        artifact = json.loads(Path(packet.input_artifact_refs[0]).read_text(encoding="utf-8"))
        request = RetrievalNeedsRequest.model_validate(artifact["request"])
        assert request.original_question == question
        assert request.catalog["target_ids"] == {identifier: request.catalog["target_ids"][identifier]}
        assert {"criteria", "test_spec"} <= request.catalog["required_fields"].keys()
        assert all(line in packet.output_requirements for line in RetrievalNeeds().requirements(request))
        assert artifact["request_schema"] == schema_ids.RETRIEVAL_NEEDS_REQUEST
        assert not harness.storage.calls
        assert pending.usage_summary.jev_calls == 0
        response = controlled_needs(artifact["request"], identifier, ("criteria", "test_spec"))
        final = await harness.service().resume_run(pending.run_id, host_submission(pending, response))
        values = await harness.checkpoint_values(final.run_id)
        assert final.status is RunStatus.COMPLETED, final.model_dump_json()
        assert final.usage_summary.host_operations == 1
        requests = [item for item in values["requests"].values()
                    if item.payload_schema == schema_ids.RETRIEVAL_REQUEST]
        assert requests
        for child in requests:
            assert child.payload["retrieval_needs"]["original_question"] == question
            assert child.payload["retrieval_needs"]["source_scope"] == request.source_scope
            assert child.payload["answer_requirements"]["required_fields"] == ["criteria", "test_spec"]
            assert child.payload["answer_requirements"]["scope"]["entity_ids"] == [identifier]
        source_node, source = _source(identifier)
        other_id = "KM-500c-1" if identifier == "KM-500c-2" else "KM-500c-2"
        _, other_source = _source(other_id)
        assert source["criteria"] != other_source["criteria"]
        assert source["test_spec"] and source["test_spec"] != other_source["test_spec"]
        evidence = list(values["evidence"].values())
        for field in ("criteria", "test_spec"):
            matches = [item for item in evidence if item.source.section_locator == "/" + field]
            assert len(matches) == 1
            item = matches[0]
            actual = yaml.safe_load(item.excerpt) if field == "test_spec" else item.excerpt
            assert actual == source[field]
            uri = urlsplit(item.source.locator)
            query = parse_qs(uri.query)
            assert unquote(uri.path).strip("/") == identifier
            assert query["path"] == [source_node.source.path]
            assert query["locator"] == ["/" + field]
            assert item.source.source_version.commit == source_node.source.source_sha
        answers = answer_assessments(values)
        assert answers and all(answer["status"] == "fulfilled" for answer in answers)
        assert all(not answer["missing_fields"] for answer in answers)
        assert all(call[2:] == ("get_entities", {"entity_ids": [identifier]})
                   for call in harness.storage.calls)
        if harness.catalog:
            assert harness.catalog.descriptors() == harness.catalog_before
            assert not harness.catalog.root.exists()
    asyncio.run(check())


@pytest.mark.parametrize("harness", [False, True], indirect=True)
@pytest.mark.parametrize("field,question", [
    ("criteria", "Show only the acceptance obligations of KM-500c-2; omit its test plan."),
    ("test_spec", "Show only the authored test specification for KM-500c-2."),
    ("work_status", "What is the implementation work status of KM-500c-2?"),
])
def test_public_minimal_field_selection_is_not_expanded(harness, field, question):
    # covers: KM-500e-1-i
    # angle: discrimination
    """The application cannot fix semantics by forcing both fields on every accepted request."""
    async def check():
        pending = await harness.service().start_run(harness.question(question))
        assert pending.status is RunStatus.WAITING_HOST
        request = packet_request(pending)
        response = controlled_needs(request, fields=(field,))
        final = await harness.service().resume_run(pending.run_id, host_submission(pending, response))
        assert final.status is RunStatus.COMPLETED, final.model_dump_json()
        values = await harness.checkpoint_values(final.run_id)
        requests = [item for item in values["requests"].values()
                    if item.payload_schema == schema_ids.RETRIEVAL_REQUEST]
        assert requests
        for child in requests:
            assert child.payload["answer_requirements"]["required_fields"] == [field]
            assert child.payload["retrieval_needs"]["selections"]["required_fields"] == [field]
            assert child.payload["retrieval_needs"]["original_question"] == question
        answers = answer_assessments(values)
        assert answers and all(answer["required_fields"] == [field] for answer in answers)
        assert all(answer["status"] == "fulfilled" for answer in answers)
        if field != "test_spec":
            assert all(item.source.section_locator != "/test_spec"
                       for item in values["evidence"].values())
    asyncio.run(check())
