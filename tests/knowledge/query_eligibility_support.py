"""Pinned real-source support; only host/Jev and storage ports are controlled."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

import yaml

from kernel.contracts import RunStatus
from knowledge.contracts import ProjectionSnapshot
from knowledge.projection.answer_fields import mapped_fields
from knowledge.projection.canonical_loader import _entity
from scripts.knowledge_query import NodeRecord
from tests.conftest import load_fixture
from tests.knowledge import public_retrieval_needs_support as public

CASES = load_fixture("_shared/query_eligibility/cases")
ORACLE = load_fixture("_shared/query_eligibility/source-oracles")
CORPUS_SHA = ORACLE["source_revision"]


@lru_cache(maxsize=1)
def fixture_repository():
    """Materialize exact reviewed bytes; its Git revision is distinct from corpus provenance."""
    directory = tempfile.TemporaryDirectory(prefix="eligibility-source-")
    root = Path(directory.name)
    blobs = load_fixture("_shared/query_eligibility/source-blobs")
    paths = {row["id"]: row for population in ORACLE["populations"].values()
             for row in [population["root"], *population["membership"]]}
    for identifier, row in paths.items():
        raw = base64.b64decode(blobs[identifier])
        assert hashlib.sha256(raw).hexdigest() == row["source_sha256"]
        target = root / row["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    for arguments in (["init", "--quiet"], ["-c", "core.autocrlf=false", "add", "docs"],
                      ["-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                       "-c", "commit.gpgsign=false", "-c", "core.hooksPath=" + str(root / "no-hooks"),
                       "commit", "--quiet", "-m", "Source fixture from " + CORPUS_SHA]):
        subprocess.run(["git", *arguments], cwd=root, check=True, capture_output=True)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    return directory, root, revision, paths


@lru_cache(maxsize=1)
def pinned_snapshot():
    """Use real mapper output; the oracle supplies provenance, never a retrieved count."""
    _, root, revision, paths = fixture_repository()
    records = {identifier: yaml.safe_load((root / row["path"]).read_bytes())
               for identifier, row in paths.items()}
    parents = {row["parent"] for row in paths.values()}
    nodes = [_entity(NodeRecord(identifier, "acs", records[identifier]["title"], "", Path(row["path"])),
        root, public.REPOSITORY, revision, records, parents) for identifier, row in paths.items()]
    return ProjectionSnapshot(repository_id=public.REPOSITORY, source_sha=revision,
        generation_id="eligibility-pinned-source", nodes=nodes, edges=[],
        supported_kinds=["AcceptanceCriterion"], supported_fields=mapped_fields(["AcceptanceCriterion"]),
        supported_relationships=["parent", "depends_on"])


def public_harness(monkeypatch, catalog=False):
    """Reuse the public service/scheduler fixture with its source revision explicitly frozen."""
    monkeypatch.setattr(public, "source_snapshot", pinned_snapshot)
    monkeypatch.setattr(public, "ROOT", fixture_repository()[1])
    return public.PublicNeedsHarness().configure(catalog_enabled=catalog)


def observe_requests(monkeypatch):
    """Observe the real KnowledgeService boundary without replacing its implementation."""
    from knowledge.service import KnowledgeService

    requests, results = [], []
    original = KnowledgeService.retrieve

    async def observe(service, request):
        requests.append(request)
        result = await original(service, request)
        results.append(result)
        return result

    monkeypatch.setattr(KnowledgeService, "retrieve", observe)
    return requests, results


async def run_case(harness, case):
    """Drive public host wait/resume using an explicitly controlled interpretation."""
    pending = await harness.service().start_run(harness.question(case["question"]))
    assert pending.status is RunStatus.WAITING_HOST
    assert pending.pending_interaction.operation == "interpret_retrieval_needs"
    assert harness.storage.calls == []
    request = public.packet_request(pending)
    expected = case["expected_requirements"]
    scope = expected["scope"]
    target = scope["root_id"] or scope["entity_ids"][0]
    response = public.controlled_needs(request, target, expected["required_fields"])
    if scope["population"] == "ac_descendants":
        response["selections"]["relationships"] = ["all_descendants"]
        response.update(completeness="exhaustive_count",
            hierarchy_scope="exclude_parents" if scope["inclusion"] == "terminal_leaves" else "exclude_root",
            hierarchy_levels=scope["levels"])
    final = await harness.service().resume_run(pending.run_id, public.host_submission(pending, response))
    return final, await harness.checkpoint_values(final.run_id)


def operation_batches(harness):
    return [batch for batch in harness.jev.batches if batch.purpose == "knowledge.operation_select"]


def choices(batch):
    return next(question.criteria for question in batch.questions if question.id == "operation")


async def admit_exact_query(harness, description):
    """Prepare an admitted exact-record recipe through real admission, with controlled storage."""
    from knowledge.adapters.neo4j_backend import scope_key

    calls = []

    async def compiled_read(statement, parameters=None, write=False):
        calls.append((statement, parameters, write))
        snapshot = pinned_snapshot()
        nodes = [node for node in snapshot.nodes if node.canonical_id in parameters["arg_ac_ids"]]
        if parameters["scope_key"] != scope_key(public.REPOSITORY, snapshot.generation_id):
            nodes = []
        return [{"payloads": [node.model_dump_json() for node in nodes], "expansion_truncated": False}]

    harness.storage._run = compiled_read
    candidate = load_fixture("_shared/query_eligibility/saved_exact")
    candidate["descriptor"]["description"] = description
    receipt = await harness.admission.verify_and_activate(candidate,
        repository_id=public.REPOSITORY, source_sha=pinned_snapshot().source_sha)
    calls.clear()
    return receipt, calls


def run(coroutine):
    return asyncio.run(coroutine)
