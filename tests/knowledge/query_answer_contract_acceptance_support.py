"""Independent storage-boundary fixtures for public answer-contract acceptance.

MODULE: query_answer_contract_acceptance_support
GOAL: Feed actual immutable projection into the real CLI and service.
BUSINESS CONTEXT: Expected source values must not populate tool answers.
ARCHITECTURE: Only database storage is doubled; projection, disclosure and CLI are real.
"""

import json
import sys
from pathlib import Path

from knowledge.errors import BackendUnavailable

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/query_answer_contract_acceptance/source_oracles.json"
ORACLE = json.loads(FIXTURE.read_text(encoding="utf-8"))
SOURCE_SHA = ORACLE["source_revision"]
REPOSITORY_ID = "qa-answer-contract"


class ProjectionStorage:
    """A storage double containing real mapper output, never oracle answer values."""

    def __init__(self, snapshot, entity_ids, *, omit_work_status=False, unavailable=False):
        """Select actual projected records while recording real query execution."""
        self.snapshot = snapshot.model_copy(deep=True)
        self.nodes = [node for node in self.snapshot.nodes if node.canonical_id in entity_ids]
        if omit_work_status:
            for node in self.nodes:
                node.properties.pop("work_status", None)
        self.calls = []
        self.unavailable = unavailable

    async def active(self, repository_id):
        """Return only the authorized immutable snapshot."""
        return self.snapshot if repository_id == REPOSITORY_ID else None

    async def get_generation(self, repository_id, generation_id):
        """Resolve a retained snapshot only within its exact scope."""
        if repository_id == REPOSITORY_ID and generation_id == self.snapshot.generation_id:
            return self.snapshot
        return None

    async def capabilities(self):
        """Declare storage mechanisms without claiming semantic readiness."""
        return {"graph": True, "semantic": False, "hybrid": False}

    async def query(self, repository_id, generation_id, operation, arguments, limit):
        """Execute only exact entity selection; hierarchy policy is never mocked here."""
        self.calls.append((repository_id, generation_id, operation, arguments))
        if self.unavailable:
            raise BackendUnavailable()
        assert operation == "get_entities", "Independent storage stub supports exact lookup only"
        assert repository_id == REPOSITORY_ID
        assert generation_id == self.snapshot.generation_id
        selected = set(arguments["entity_ids"])
        return [node for node in self.nodes if node.canonical_id in selected][:limit]

    async def neighbors(self, repository_id, generation_id, entity_ids, edge_types, limit):
        """No relation claims are made by these exact-source disclosure tests."""
        return [], []


def public_request(identifier, *, required_fields=None):
    """Build serialized public input without supplying any expected answer value."""
    request = {
        "request_id": "independent-answer-contract",
        "repository_id": REPOSITORY_ID,
        "revision": SOURCE_SHA,
        "operation": "get_entities",
        "mode": "exact",
        "arguments": {"entity_ids": [identifier]},
        "disclosure_level": 3,
    }
    if required_fields is not None:
        request["answer_requirements"] = {
            "original_question": "What are this criterion's canonical work status and exact obligations?",
            "required_fields": required_fields,
            "scope": {"population": "returned_entities"},
            "require_complete": True,
        }
    return request


def invoke_cli(monkeypatch, tmp_path, capsys, snapshot, request, **storage_options):
    """Enter main with real argv, real request bytes and the real retrieval service."""
    from knowledge import __main__ as cli
    from knowledge.adapters.git_source import GitSourceResolver
    from knowledge.service import KnowledgeService

    storage = ProjectionStorage(snapshot, request["arguments"]["entity_ids"], **storage_options)
    service = KnowledgeService(
        storage,
        source_resolver=GitSourceResolver(ROOT, REPOSITORY_ID),
        cursor_secret=b"independent-tests-only",
    )
    monkeypatch.setattr(cli, "build_retriever", lambda config, **kwargs: service)
    path = tmp_path / "request.json"
    path.write_text(json.dumps(request), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["knowledge", "retrieve", "--repository-id", REPOSITORY_ID,
                                      "--request", str(path), "--root", str(ROOT)])
    exit_code = cli.main()
    captured = capsys.readouterr()
    payload = json.loads(captured.out or captured.err)
    return exit_code, payload, storage
