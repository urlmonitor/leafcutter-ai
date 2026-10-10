"""Native-only inspection preserves refresh safety without schema migration support."""

import asyncio
from copy import deepcopy
import hashlib
import unittest

from knowledge import native_refresh
from knowledge.adapters.neo4j_backend import scope_key
from knowledge.contracts import Relation
from tests.knowledge.test_native_refresh_recovery import _DB, _group, _snapshot


class NativeInspectionTest(unittest.TestCase):
    def test_refresh_uses_native_repository_and_snapshot_patterns_only(self):
        # covers: KM-400a-3-i
        # angle: seam
        owner = self

        class NativeDB(_DB):
            async def _run(self, statement, parameters=None, write=False):
                if statement.startswith("MATCH (r:"):
                    owner.assertEqual(
                        statement,
                        "MATCH (r:Repository {repository_id:$repo}) RETURN properties(r) AS props",
                    )
                if statement.startswith("MATCH (g:"):
                    owner.assertEqual(
                        statement,
                        "MATCH (g:Snapshot {repository_id:$repo}) RETURN properties(g) AS props ORDER BY g.key",
                    )
                return await super()._run(statement, parameters, write)

        ready = _group(_snapshot("ready"), current=True)
        plan = asyncio.run(
            native_refresh._inspect_refresh(NativeDB([ready], ready["metadata"]["key"]), "repo")
        )
        self.assertEqual(plan["generations"][0]["nodes"], ready["nodes"])
        self.assertEqual(plan["staged_generations"], [])

    def test_publication_refuses_unsupported_control_schema_before_writes(self):
        # covers: KM-400a-3-i
        # angle: failure
        from types import SimpleNamespace
        from knowledge.adapters.neo4j_projection import publish, switch_active

        snapshot = _snapshot("new")

        async def run(statement, parameters, write=False):
            self.assertFalse(write, "unsupported storage must not create a native snapshot")
            self.assertEqual(parameters, {"repo": "repo"})
            return [{"count": 1}]

        def rows(tx, statement, parameters):
            self.assertNotIn("MERGE", statement)
            self.assertNotIn(" SET ", statement)
            self.assertEqual(parameters, {"repo": "repo"})
            return [{"count": 1}]

        async def transaction(callback, write=False):
            return callback(object())

        db = SimpleNamespace(_run=run, _rows=rows, _transaction=transaction)
        with self.assertRaisesRegex(ValueError, "native storage"):
            asyncio.run(publish(db, snapshot, None))
        with self.assertRaisesRegex(ValueError, "native storage"):
            asyncio.run(switch_active(db, "repo", "new", None))

    def test_vector_identifiers_use_native_namespace_and_remain_scoped(self):
        # covers: KM-400a-3-i
        # angle: boundary
        from knowledge.adapters.neo4j_vector_build import index_name
        from knowledge.adapters.neo4j_vectors import trusted_name

        key = scope_key("repo", "ready")
        names = {index_name(key, kind) for kind in ("", "Decision", "Lesson")}
        self.assertEqual(len(names), 3)
        for name in names:
            self.assertRegex(name, r"^native_vector_[a-f0-9]{64}$")
            self.assertEqual(trusted_name(name), name)
        self.assertNotIn(index_name(scope_key("foreign", "ready")), names)
        for invalid in ("unowned", "native_vector_", "native_vector_" + "a" * 64 + " DROP INDEX"):
            with self.assertRaises(ValueError):
                trusted_name(invalid)

    def test_inspection_rejects_unknown_or_contradictory_physical_labels(self):
        # covers: KM-400a-3-i
        # angle: failure
        for labels in (["UnownedEntity"], ["AC", "ADR"], []):
            with self.subTest(labels=labels):
                group = _group(_snapshot("ready"), current=True)
                group["nodes"][0]["labels"] = labels
                db = _DB([group], group["metadata"]["key"])
                with self.assertRaisesRegex(ValueError, "node identity or kind"):
                    asyncio.run(native_refresh._inspect_refresh(db, "repo"))

    def test_inspection_rejects_edge_type_and_endpoint_scope_conflicts(self):
        # covers: KM-400a-3-i
        # angle: failure
        group = _group(_snapshot("ready"), current=True)
        key = group["metadata"]["key"]
        relation = Relation(source_id="AC-0", target_id="AC-1", edge_type="depends_on")
        payload = relation.model_dump_json()
        group["metadata"]["edge_count"] = 1
        group["edges"] = [
            {
                "type": "DEPENDS_ON",
                "props": {
                    "key": hashlib.sha256(payload.encode()).hexdigest(),
                    "generation_key": key,
                    "edge_type": relation.edge_type,
                    "payload": payload,
                },
                "source": scope_key(key, relation.source_id),
                "target": scope_key(key, relation.target_id),
                "source_scope": key,
                "target_scope": key,
            }
        ]
        valid = asyncio.run(native_refresh._inspect_refresh(_DB([group], key), "repo"))
        self.assertEqual(valid["generations"][0]["edges"], group["edges"])
        for field, value in (
            ("type", "UNOWNED_LINK"),
            ("target_scope", scope_key("other", "ready")),
        ):
            with self.subTest(field=field):
                invalid = deepcopy(group)
                invalid["edges"][0][field] = value
                with self.assertRaisesRegex(ValueError, "relationship identity or scope"):
                    asyncio.run(native_refresh._inspect_refresh(_DB([invalid], key), "repo"))


if __name__ == "__main__":
    unittest.main()
