"""Real Neo4j property/readback proof for native field exposure (KM-400a-3-i)."""

import asyncio
from datetime import date
import uuid

from knowledge.adapters.neo4j_backend import Neo4jBackend
from knowledge.contracts import Entity, ProjectionSnapshot, SourceReference
from knowledge.native_properties import decode
from knowledge.native_types.common import NativeRecord
from knowledge.projection.native_metadata import apply_record


def test_native_metadata_is_typed_queryable_and_round_trips_in_neo4j():
    # covers: KM-400a-3-i
    # angle: real_artifact
    async def scenario():
        db = Neo4jBackend(
            "bolt://127.0.0.1:18088", "neo4j", "leafcutter-native-tests", query_timeout=30
        )
        repo = "native-" + uuid.uuid4().hex
        raw = {
            "id": "authored-id",
            "current": "authored-value",
            "priority": "high",
            "created": date(2026, 10, 2),
            "test_required": True,
            "notes": "Exact authored notes\nwith whitespace.\n",
            "test_spec": [
                {"name": "first", "requires_db": True},
                {"name": "second", "requires_db": False},
            ],
            "depends_on": ["AC-1", "AC-2"],
            "superseded_by": None,
            "empty_object": {},
            "empty_list": [],
            "large_integer": 2**63,
            2**80: "large typed key",
        }
        entity = Entity(
            canonical_id="AC-100",
            kind="AcceptanceCriterion",
            title="Readable title",
            source=SourceReference(
                repository_id=repo, source_sha="a" * 40, path="docs/ac.yaml", content_hash="fixture"
            ),
        )
        entity = apply_record(
            entity,
            NativeRecord(
                kind="AcceptanceCriterion",
                native_id="AC-100",
                source_path="docs/ac.yaml",
                metadata=raw,
            ),
        )
        snapshot = ProjectionSnapshot(
            repository_id=repo, source_sha="a" * 40, generation_id="one", nodes=[entity]
        )
        try:
            await db.setup()
            assert await db.publish(snapshot)
            found = await db._run(
                "MATCH (n:AC {repository_id:$repo}) WHERE n.current=true AND n.priority='high' AND n.test_required=true AND n.`/test_spec/0/requires_db`=true RETURN properties(n) AS props",
                {"repo": repo},
            )
            assert len(found) == 1
            props = found[0]["props"]
            assert props["/current"] == "authored-value" and props["current"] is True
            assert props["/test_spec/1/name"] == "second"
            assert props["depends_on"] == ["AC-1", "AC-2"]
            assert props["notes"] == raw["notes"]
            assert props["large_integer"] == str(2**63)
            assert decode(props) == raw
            retained = await db.query(repo, "one", "get_entities", {"entity_ids": ["AC-100"]}, 10)
            assert retained[0].canonical_id == "AC-100"
            assert decode(retained[0].properties["_native_projection"]) == raw
        finally:
            await db.close()

    asyncio.run(scenario())
