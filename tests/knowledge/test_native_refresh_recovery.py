"""Recovery preserves strict published evidence checks, KM-400a-3-i."""

import asyncio
from copy import deepcopy
import hashlib

import pytest

from knowledge import native_refresh
from knowledge.adapters.neo4j_backend import scope_key
from knowledge.contracts import Entity, ProjectionSnapshot, SourceReference


def _snapshot(generation, count=2):
    return ProjectionSnapshot(
        repository_id="repo",
        source_sha="a" * 40,
        generation_id=generation,
        mapper_version="7",
        nodes=[
            Entity(
                canonical_id=f"AC-{index}",
                kind="AcceptanceCriterion",
                title="Fixture",
                source=SourceReference(
                    repository_id="repo", source_sha="a" * 40, path=f"ac/{index}.yaml"
                ),
            )
            for index in range(count)
        ],
    )


def _group(snapshot, status="ready", *, partial=False, current=False):
    key = scope_key(snapshot.repository_id, snapshot.generation_id)
    return {
        "metadata": {
            "key": key,
            "repository_id": snapshot.repository_id,
            "generation_id": snapshot.generation_id,
            "source_sha": snapshot.source_sha,
            "mapper_version": snapshot.mapper_version,
            "status": status,
            "node_count": len(snapshot.nodes),
            "edge_count": 0,
            "digest": hashlib.sha256(snapshot.model_dump_json().encode()).hexdigest(),
        },
        "nodes": [
            {
                "labels": ["AC"],
                "props": {
                    "key": scope_key(key, node.canonical_id),
                    "generation_key": key,
                    "canonical_id": node.canonical_id,
                    "kind": node.kind,
                    "payload": node.model_dump_json(),
                    "content_hash": node.source.content_hash,
                    "current": current,
                },
            }
            for node in (snapshot.nodes[:1] if partial else snapshot.nodes)
        ],
        "edges": [],
    }


class _DB:
    def __init__(self, groups, active):
        self.groups = deepcopy(groups)
        self.active = active
        self.writes = []

    async def _run(self, statement, parameters=None, write=False):
        assert not write
        if "MATCH (r:Repository|KRRepository" in statement:
            return [{"props": {"repository_id": "repo", "active": self.active}}]
        if "MATCH (g:Snapshot|KRGeneration" in statement:
            return [{"props": group["metadata"]} for group in self.groups]
        group = next(g for g in self.groups if g["metadata"]["key"] == parameters["key"])
        return group["edges"] if "MATCH (a)-[r]->(b)" in statement else group["nodes"]


@pytest.mark.parametrize("status", ["building", "failed", "validated"])
def test_inspection_retains_partial_stages_without_weakening_ready_evidence(status):
    # covers: KM-400a-3-i
    # angle: seam
    old, target = _snapshot("old"), _snapshot("new")
    ready = _group(old, current=True)
    stage = _group(target, status, partial=True)
    db = _DB([ready, stage], ready["metadata"]["key"])
    plan = asyncio.run(native_refresh._inspect_refresh(db, "repo"))
    assert len(plan["generations"]) == 1
    assert plan["generations"][0]["nodes"] == ready["nodes"]
    assert plan["staged_generations"][0]["nodes"] == stage["nodes"]
    assert native_refresh._validate_resume(plan, target) is True
    assert not db.writes


@pytest.mark.parametrize(
    "fault",
    ["payload", "count", "active_stage", "current_stage", "foreign_stage", "unknown_status"],
)
def test_recovery_rejects_invalid_ready_data_and_unsafe_stages(fault):
    # covers: KM-400a-3-i
    # angle: failure
    ready = _group(_snapshot("old"), current=True)
    stage = _group(_snapshot("new"), "failed", partial=True)
    active = ready["metadata"]["key"]
    if fault == "payload":
        ready["nodes"][0]["props"]["canonical_id"] = "wrong"
    elif fault == "count":
        ready["metadata"]["node_count"] += 1
    elif fault == "active_stage":
        active = stage["metadata"]["key"]
    elif fault == "current_stage":
        stage["nodes"][0]["props"]["current"] = True
    elif fault == "foreign_stage":
        stage["metadata"]["key"] = scope_key("foreign", "new")
    else:
        stage["metadata"]["status"] = "unexpected"
    with pytest.raises(ValueError):
        asyncio.run(native_refresh._inspect_refresh(_DB([ready, stage], active), "repo"))


@pytest.mark.parametrize(
    "fault", ["digest", "source_sha", "mapper_version", "node_count", "node_payload"]
)
def test_resume_requires_the_exact_same_snapshot_and_partial_contents(fault):
    # covers: KM-400a-3-i
    # angle: failure
    target = _snapshot("new")
    stage = _group(target, "failed", partial=True)
    if fault == "node_payload":
        node = target.nodes[0].model_copy(update={"title": "Different content"})
        stage["nodes"][0]["props"]["payload"] = node.model_dump_json()
    else:
        stage["metadata"][fault] = "different" if fault != "node_count" else 999
    with pytest.raises(ValueError, match="staging"):
        native_refresh._validate_resume({"staged_generations": [stage]}, target)


def test_unrelated_failed_stage_does_not_become_the_resume_target():
    # covers: KM-400a-3-i
    # angle: boundary
    stage = _group(_snapshot("unrelated"), "failed", partial=True)
    assert (
        native_refresh._validate_resume({"staged_generations": [stage]}, _snapshot("new")) is False
    )
