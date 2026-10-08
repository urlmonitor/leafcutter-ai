"""
MODULE: test_public_promises
GOAL: Verify malformed JSON rejection and retrieval-run provenance through public callers.
BUSINESS CONTEXT: Promise claims need actual externally observable assertions.
ARCHITECTURE: Standalone JSON CLI with spy port and public service with fixture backend.
"""

import importlib
import json
import pytest
from tests.knowledge.test_core import api, Backend, request, retrieve


@pytest.mark.parametrize(
    "overrides,field",
    [
        ({"contract_version": "wrong"}, "contract_version"),
        ({"operation": "MATCH (n) RETURN n"}, "operation"),
        ({"mode": "semantic"}, "mode"),
        ({"budget": {"max_results": -1}}, "max_results"),
    ],
)
def test_cli_invalid_json_contract_names_error_without_retrieval(
    monkeypatch, tmp_path, capsys, overrides, field
):
    """Malformed public JSON names the field and never executes the retrieval port."""
    # covers: KM-400a-4
    # angle: criterion
    # angle: reachability
    cli = importlib.import_module("knowledge.__main__")
    calls = []

    class Port:
        """Fail if malformed JSON reaches retrieval."""

        async def retrieve(self, request):
            """Record an unexpected port call."""
            calls.append(request)
            pytest.fail("invalid request reached retrieval")

        async def close(self):
            """Close the resource-free fixture."""
            pass

    monkeypatch.setattr(cli, "build_retriever", lambda config: Port())
    payload = {
        "request_id": "invalid",
        "repository_id": "leafcutter",
        "operation": "get_entities",
        "arguments": {"entity_ids": ["A"]},
        **overrides,
    }
    path = tmp_path / "request.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["knowledge", "retrieve", "--request", str(path)])
    assert cli.main() != 0
    output = json.loads(capsys.readouterr().err)
    assert output["status"] == "error" and field in output["message"]
    assert calls == []


def test_service_evidence_identity_and_retrieval_run_identity_are_distinct():
    """Repeated service calls retain canonical identity but receive separate retrieval IDs."""
    # covers: KM-400d-5
    # angle: criterion
    # angle: reachability
    c, s = api()
    service = s.KnowledgeService(Backend(c))
    req = request(c)
    first = retrieve(service, req)
    second = retrieve(service, req.model_copy(update={"request_id": "second"}))
    assert first.evidence[0].evidence_id == second.evidence[0].evidence_id
    assert first.retrieval_id != second.retrieval_id
    assert first.source_sha == second.source_sha and first.generation_id == second.generation_id
    assert first.operation == second.operation == req.operation


# DECISION HISTORY
# ================================================================================
# - 2026-10-01 20:00 [python-coder]: Verify public proof promises instead of assigning unsupported test labels. (#TICKET-20261001-KM-400a-4)
