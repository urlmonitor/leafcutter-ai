"""Native query boundary checks for the existing KM-400a-3-i contract."""

import asyncio
import re
import unittest
from types import SimpleNamespace

from knowledge.adapters.domain_schema import NODE_LABELS, RELATIONSHIPS
from knowledge.adapters.neo4j_backend import Neo4jBackend, scope_key
from knowledge.adapters.neo4j_domain_build import set_current
from knowledge.adapters.neo4j_queries import CATALOG, neighbors, query
from knowledge.contracts import Entity, Relation, SourceReference


class RecordingTransaction:
    """Capture exactly what reaches the driver without an adapter rewrite."""

    def __init__(self, rows=()):
        self.rows = rows
        self.calls = []

    def run(self, statement, parameters):
        self.calls.append((statement, parameters))
        return [SimpleNamespace(data=lambda row=row: row) for row in self.rows]


class NativeQueriesTest(unittest.TestCase):
    def assert_native(self, statement):
        self.assertNotRegex(statement, r"\b(?:KREntity|KR_LINK|KRGeneration|KRRepository)\b")

    def test_rows_preserves_trusted_statement_literals_and_parameters(self):
        # covers: KM-400a-3-i
        # angle: boundary
        statement = "RETURN ':KREntity ' AS example, $value AS value"
        parameters = {"value": ":KR_LINK DELETE n"}
        expected = [{"example": ":KREntity ", "value": parameters["value"]}]
        tx = RecordingTransaction(expected)
        backend = object.__new__(Neo4jBackend)
        self.assertEqual(backend._rows(tx, statement, parameters), expected)
        self.assertEqual(tx.calls, [(statement, parameters)])
        self.assertIs(tx.calls[0][1], parameters)

    def test_native_manifest_reads_pass_repository_and_revision_as_parameters(self):
        # covers: KM-400a-3-i
        # angle: seam
        tx = RecordingTransaction()
        backend = object.__new__(Neo4jBackend)

        async def transaction(callback, write=False):
            self.assertFalse(write)
            return callback(tx)

        backend._transaction = transaction

        async def scenario():
            self.assertIsNone(await backend.active("repo"))
            self.assertIsNone(await backend.get_generation("repo", "generation"))
            self.assertIsNone(await backend.get_revision("repo", "a" * 40))

        asyncio.run(scenario())
        self.assertEqual(len(tx.calls), 3)
        for statement, _ in tx.calls:
            self.assert_native(statement)
            self.assertIn(":Snapshot ", statement)
        self.assertIn(":Repository ", tx.calls[0][0])
        self.assertEqual(tx.calls[0][1], {"repo": "repo"})
        self.assertEqual(tx.calls[1][1], {"key": scope_key("repo", "generation")})
        self.assertEqual(tx.calls[2][1], {"repo": "repo", "sha": "a" * 40})

    def test_registered_reads_and_neighbors_emit_native_patterns_with_bound_ids(self):
        # covers: KM-400a-3-i
        # angle: boundary
        entity = Entity(
            canonical_id="result",
            kind="Test",
            title="Fixture",
            source=SourceReference(repository_id="repo", source_sha="a" * 40, path="test.py"),
        )
        relation = Relation(source_id="seed", target_id="result", edge_type="covered_by")
        calls = []
        hostile_id = "seed'}) DETACH DELETE n //"

        async def generation(repo, revision):
            self.assertEqual((repo, revision), ("repo", "generation"))
            return SimpleNamespace(
                supported_kinds=["AcceptanceCriterion", "ADR", "Decision", "Lesson", "Test"],
                supported_fields={"AcceptanceCriterion": ["structural_parent"]},
            )

        async def run(statement, parameters, write=False):
            self.assertFalse(write)
            self.assert_native(statement)
            self.assertNotIn(hostile_id, statement)
            self.assertEqual(parameters["ids"], [hostile_id])
            self.assertEqual(parameters["key"], scope_key("repo", "generation"))
            self.assertEqual(parameters["limit"], 200)
            self.assertIn("generation_key:$key", statement)
            calls.append((statement, parameters))
            return [{"payload": entity.model_dump_json(), "relation": relation.model_dump_json()}]

        db = SimpleNamespace(get_generation=generation, _run=run)

        async def scenario():
            for operation in ["get_entities", "_get_ac_children", *CATALOG]:
                result = await query(
                    db, "repo", "generation", operation, {"entity_ids": [hostile_id]}, 999
                )
                self.assertEqual(result, [entity])
            nodes, edges = await neighbors(
                db, "repo", "generation", [hostile_id], ["covered_by"], 999
            )
            self.assertEqual((nodes, edges), ([entity], [relation]))

        asyncio.run(scenario())
        for statement, parameters in calls:
            self.assertTrue(
                set(re.findall(r"(?:n|s):([\w|]+)", statement)[0].split("|"))
                <= set(NODE_LABELS.split("|"))
            )
            if "edge_type" in parameters:
                self.assertIn("[r:" + RELATIONSHIPS[parameters["edge_type"]] + "]", statement)
                self.assertIn("r.generation_key=$key", statement)

    def test_current_markers_remain_scoped_and_atomic_at_transaction_boundary(self):
        # covers: KM-400a-3-i
        # angle: seam
        backend, tx = object.__new__(Neo4jBackend), RecordingTransaction()
        key = scope_key("repo", "generation")
        set_current(backend, tx, key, False)
        self.assertEqual(len(tx.calls), 2)
        for statement, parameters in tx.calls:
            self.assert_native(statement)
            self.assertIn("generation_key:$key", statement)
            self.assertIn(".current=$current", statement)
            self.assertEqual(parameters, {"key": key, "current": False})


if __name__ == "__main__":
    unittest.main()
