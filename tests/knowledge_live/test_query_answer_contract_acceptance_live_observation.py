"""Opt-in real remote observation proof; credentials never constitute consent.

This test sends only a declared synthetic fixture through the actual application
observer, then independently reads the emitted remote artifact. It does not use
Jev or embeddings and never upgrades the default unverified output to verified.
"""
import json
import os
from pathlib import Path
import sys
import time
import unittest
from uuid import uuid4

import pytest


@unittest.skipUnless(
    os.environ.get("LEAFCUTTER_KNOWLEDGE_LANGFUSE_LIVE") == "1",
    "not_run: live external observation verification was not explicitly authorized",
)
def test_authorized_remote_observation_resolves_matching_final_attempt(monkeypatch, tmp_path, capsys):
    # covers: KM-500g-1
    # angle: real_artifact
    # angle: reachability
    # The declaration is not execution proof: default outcome is explicitly not_run.
    configured = os.environ.get("LEAFCUTTER_KNOWLEDGE_LANGFUSE_CONFIG")
    assert configured and Path(configured).is_file(), "Authorized observation configuration path is missing"
    from kernel.config import load_kernel_config
    from kernel.secrets import load_secrets
    from integrations import knowledge_cli as app
    from knowledge import __main__ as cli
    from knowledge.contracts import Entity, ProjectionSnapshot, SourceReference
    from knowledge.service import KnowledgeService
    from tests.knowledge.query_answer_contract_acceptance_support import ProjectionStorage
    secrets = load_secrets()
    assert secrets.has_langfuse(), "Authorized remote observation credentials are missing"
    config = load_kernel_config(Path(configured)).model_dump(mode="json")
    config["paths"]["run_root"] = str(tmp_path / "runs")
    config["langfuse"].update(enabled=True, flush_on_exit=True, environment="acceptance-opt-in-synthetic")
    config["data_policy"]["telemetry_excerpts"] = "none"
    config_path = tmp_path / "authorized-synthetic-observation.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    repository, revision = "qa-opt-in-observation", "a" * 40
    entity = Entity(canonical_id="AC-SYNTHETIC-OBSERVATION", kind="AcceptanceCriterion",
        title="Synthetic missing-field acceptance fixture", source=SourceReference(
            repository_id=repository, source_sha=revision, path="synthetic/observation.yaml"))
    snapshot = ProjectionSnapshot(repository_id=repository, source_sha=revision,
        generation_id="synthetic-observation-generation", nodes=[entity])
    storage = ProjectionStorage(snapshot, [entity.canonical_id])
    request = {"request_id": "authorized-synthetic-" + uuid4().hex, "repository_id": repository,
        "revision": revision, "operation": "get_entities", "mode": "exact",
        "arguments": {"entity_ids": [entity.canonical_id]}, "disclosure_level": 0,
        "answer_requirements": {"original_question": "Synthetic controlled work-status question",
            "required_fields": ["work_status"], "require_complete": True,
            "scope": {"population": "returned_entities"}}}
    request_path = tmp_path / "synthetic-request.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    def controlled_storage_only(config, **kwargs):
        assert config.repository_id == repository
        return KnowledgeService(storage, cursor_secret=b"synthetic-observation-only", **kwargs)
    monkeypatch.setattr(cli, "build_retriever", controlled_storage_only)
    monkeypatch.setattr(sys, "argv", ["knowledge-app", "--observability-config", str(config_path),
        "retrieve", "--repository-id", repository, "--request", str(request_path)])
    code = app.main()
    captured = capsys.readouterr()
    assert code == 0
    output = json.loads(captured.out)
    assert output["status"] == "ok" and output["answer"]["status"] != "fulfilled"
    assert len(storage.calls) == 1
    observation = output["observation"]
    assert observation["state"] == "unverified" and observation["trace_id"]
    assert observation.get("trace_url") is None
    # Real REST readback is distinct from the default app's unverified envelope.
    matched = _remote_observation(secrets, observation["trace_id"], request["request_id"], output["retrieval_id"])
    assert matched.name == "knowledge.retrieve" and str(matched.type) == "RETRIEVER"
    assert matched.end_time is not None
    metadata = matched.metadata
    assert metadata["execution_status"] == output["status"]
    assert metadata["answer_status"] == output["answer"]["status"]
    assert metadata["completeness"] == output["answer"]["completeness"]
    assert metadata["missing_fields"] == output["answer"]["missing_fields"]
    assert metadata["required_fields"] == request["answer_requirements"]["required_fields"]
    assert metadata["scope"] == output["answer"]["scope"]
    assert metadata["source_sha"] == revision and metadata["generation_id"] == snapshot.generation_id
    assert "original_question" not in metadata and "excerpt" not in metadata


def _remote_observation(secrets, trace_id, request_id, retrieval_id):
    """Read real remote serialized observations with bounded polling and no success stub."""
    from langfuse.api import LangfuseAPI
    api = LangfuseAPI(base_url=secrets.langfuse_base_url,
        username=secrets.langfuse_public_key.get_secret_value(),
        password=secrets.langfuse_secret_key.get_secret_value(), timeout=5)
    deadline = time.monotonic() + 45
    matched = None
    while matched is None and time.monotonic() < deadline:
        cursor = None
        for _ in range(10):
            try:
                page = api.observations.get_many(trace_id=trace_id,
                    name="knowledge.retrieve", fields="core,basic,metadata", limit=1000,
                    expand_metadata="completeness,missing_fields,scope,required_fields,evidence_ids", cursor=cursor)
            except Exception:
                pytest.fail("Real remote readback failed; sensitive diagnostics withheld", pytrace=False)
            for row in page.data:
                metadata = row.metadata or {}
                if row.trace_id == trace_id and metadata.get("request_id") == request_id and metadata.get("retrieval_id") == retrieval_id:
                    matched = row
                    break
            cursor = getattr(getattr(page, "meta", None), "cursor", None)
            if matched is not None or not cursor or not page.data:
                break
        if matched is None:
            time.sleep(3)
    assert matched is not None, "No matching finalized remote observation arrived within the bounded readback window"
    return matched
