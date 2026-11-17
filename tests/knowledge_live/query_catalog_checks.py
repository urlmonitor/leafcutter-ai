"""Actual Neo4j execution of an authored two-hop query and catalog admission."""

import asyncio
import uuid

from tests.knowledge.test_query_admission import candidate
from tests.knowledge_live.neo4j_checks import api, backend


def test_real_generated_query_admission_and_restarted_public_retrieval(tmp_path):
    # covers: KM-500b-2
    # covers: KM-500b-3
    # angle: criterion
    # angle: real_artifact
    async def scenario():
        from knowledge.query_catalog import QueryCatalog
        from knowledge.query_admission import QueryAdmission
        from knowledge.service import KnowledgeService

        c, module = api()
        db = backend(module)
        repo = "km500-" + uuid.uuid4().hex

        def node(ident, kind):
            return c.Entity(
                canonical_id=ident,
                kind=kind,
                title=ident,
                source=c.SourceReference(
                    repository_id=repo, source_sha="a" * 40, path=ident + ".yaml"
                ),
            )

        nodes = [
            node("component", "Component"),
            node("ac", "AcceptanceCriterion"),
            node("test", "Test"),
        ]
        edges = [
            c.Relation(source_id="ac", target_id="component", edge_type="component_membership"),
            c.Relation(source_id="ac", target_id="test", edge_type="covered_by"),
        ]
        try:
            await db.setup()
            assert await db.publish(
                c.ProjectionSnapshot(
                    repository_id=repo,
                    source_sha="a" * 40,
                    generation_id="g1",
                    nodes=nodes,
                    edges=edges,
                )
            )
            catalog = QueryCatalog(tmp_path)
            port = QueryAdmission(catalog, db, repo)
            receipt = await port.verify_and_activate(
                candidate(), repository_id=repo, source_sha="a" * 40
            )
            assert receipt["checks"]["declared_cases_passed"] == 2
            assert receipt["checks"]["foreign_scope_rejected"]
            reopened = QueryCatalog(tmp_path)
            req = reopened.request(
                {
                    "repository_id": repo,
                    "request_id": "fresh-process",
                    "operation": "get_component_tests",
                    "mode": "graph",
                    "arguments": {"component_ids": ["component"]},
                    "revision": "a" * 40,
                }
            )
            out = await KnowledgeService(db, query_catalog=reopened).retrieve(req)
            assert out.status == "ok" and not out.truncated
            assert [item.entity.canonical_id for item in out.evidence] == ["test"]
            assert out.stats["operation_digest"] == receipt["digest"]
            assert out.source_sha == "a" * 40
        finally:
            await db.close()

    asyncio.run(scenario())


def test_real_high_fanout_and_completed_empty_are_distinct(tmp_path):
    # covers: KM-500a-3
    # covers: KM-500b-2
    # angle: criterion
    # angle: real_artifact
    async def scenario():
        from knowledge.query_catalog import QueryCatalog
        from knowledge.query_admission import QueryAdmission
        from knowledge.service import KnowledgeService

        c, module = api()
        db = backend(module)
        repo = "km500-saturated-" + uuid.uuid4().hex

        def make(ident, kind):
            return c.Entity(
                canonical_id=ident,
                kind=kind,
                title=ident,
                source=c.SourceReference(
                    repository_id=repo, source_sha="a" * 40, path=ident + ".yaml"
                ),
            )

        nodes = [make("component", "Component")]
        edges = []
        for index in range(11):
            ac, test = f"ac{index:02}", f"test{index:02}"
            nodes.extend([make(ac, "AcceptanceCriterion"), make(test, "Test")])
            edges.extend(
                [
                    c.Relation(
                        source_id=ac, target_id="component", edge_type="component_membership"
                    ),
                    c.Relation(source_id=ac, target_id=test, edge_type="covered_by"),
                ]
            )
        try:
            await db.setup()
            assert await db.publish(
                c.ProjectionSnapshot(
                    repository_id=repo,
                    source_sha="a" * 40,
                    generation_id="g1",
                    nodes=nodes,
                    edges=edges,
                )
            )
            catalog = QueryCatalog(tmp_path)
            proposed = candidate()
            proposed["cases"][0]["expected_ids"] = [f"test{i:02}" for i in range(10)]
            receipt = await QueryAdmission(catalog, db, repo).verify_and_activate(
                proposed, repository_id=repo, source_sha="a" * 40
            )
            assert receipt["checks"]["cases"][0]["expansion_truncated"]
            service = KnowledgeService(db, query_catalog=catalog)
            request = {
                "repository_id": repo,
                "request_id": "saturated",
                "operation": "get_component_tests",
                "mode": "graph",
                "arguments": {"component_ids": ["component"]},
                "revision": "a" * 40,
            }
            out = await service.retrieve(catalog.request(request))
            assert out.status == "partial" and out.truncated and len(out.evidence) == 10
            request["arguments"] = {"component_ids": ["missing"]}
            empty = await service.retrieve(catalog.request(request))
            assert empty.status == "ok" and not empty.truncated and not empty.evidence
        finally:
            await db.close()

    asyncio.run(scenario())
