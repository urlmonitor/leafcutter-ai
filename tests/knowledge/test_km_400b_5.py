"""KM-400b-5: rebuild, rollback and cleanup preserve only owned history.

The rebuild-from-empty and foreign-data behaviour is proved here on the recording double through the
real publication path; the real-server gates stay in ``tests/knowledge_live`` and are reported as not
run (never passing) when no server is reachable. Both tests pin what the writer-batching children
(KM-400b-5-iii .. vi) add to that promise: a record larger than the payload budget is written alone
and named, and a rebuild that fails on the writer's time limit removes only its own generation.
"""

import hashlib

from tests.knowledge._km_400b_5_writes_support import (
    REPO_ID,
    BatchDouble,
    graded_snapshot,
    make_entity,
    node_id,
    run_publish,
    run_sync_cli,
)


def _expected_identities(snapshot, key):
    from knowledge.adapters.neo4j_backend import scope_key

    nodes = {scope_key(key, n.canonical_id) for n in snapshot.nodes}
    edges = {hashlib.sha256(e.model_dump_json().encode()).hexdigest() for e in snapshot.edges}
    return nodes, edges


def test_km400_b_5_behavior():
    # covers: KM-400b-5
    # angle: criterion
    snapshot = graded_snapshot(12, 6, ac_bulk=100, test_bulk=100, covered_by=9, edge_bulk=50)
    snapshot.nodes.append(make_entity(node_id("Flow", 0), "Flow", 20_000))  # larger than the budget below
    store = BatchDouble(write_payload_budget_bytes=5_000, write_row_cap=4)
    before = store.untouched_state()
    outcome = run_publish(store, snapshot)
    assert outcome.ok, outcome.error
    # the rebuilt generation has the baseline's canonical identities, relationships included
    nodes, edges = _expected_identities(snapshot, outcome.key)
    assert {k for k, g in store.nodes.items() if g == outcome.key} == nodes
    assert {k for k, g in store.relationships.items() if g == outcome.key} == edges
    # the record larger than the budget was kept, alone, and is named by the result
    flow = [b for b in store.batches("nodes") if b["kind"] == "Flow"]
    assert [b["rows"] for b in flow] == [1]
    assert [r["id"] for r in outcome.writes["oversized_records"]] == [node_id("Flow", 0)]
    # foreign repositories' generations are exactly as they were; only the new pointer moved
    after = store.untouched_state()
    assert after["snapshots"] == before["snapshots"] and after["nodes"] == before["nodes"]
    assert after["relationships"] == before["relationships"]

    # a rebuild that fails on the writer's time limit removes only its own generation
    failing = BatchDouble(write_row_cap=4, faults={("nodes", 3): ["time_limit"] * 3})
    seeded = failing.untouched_state()
    failed = run_publish(failing, graded_snapshot(12, 6, covered_by=9))
    assert failed.error is not None
    assert failing.attempts("nodes", 3) and len(failing.attempts("nodes", 3)) == 3
    assert set(failing.deleted_keys) == {failed.key}, failing.deleted_keys
    assert failing.untouched_state() == seeded
    assert failing.tagged(failed.key) == (0, 0)


def test_km400_b_5_public_reachability(tmp_path):
    # covers: KM-400b-5
    # angle: real_artifact
    # Entry point: `python -m knowledge sync --root <repo>` in a fresh process against a real Git
    # commit whose AC YAML is written by yaml.safe_dump; only the Neo4j driver is replaced. A payload
    # budget of one byte makes every record oversized, so each is written alone and named.
    done, loaded, printed, lines = run_sync_cli(
        tmp_path, {"write_row_cap": 3, "write_payload_budget_bytes": 1}
    )
    assert done.returncode == 0, done.stderr
    assert printed["status"] == "ok" and printed["published"] is True and printed["repository_id"] == REPO_ID
    log = next(line for line in lines if "batch_log" in line)["batch_log"]
    nodes = [e for e in log if e["phase"] == "nodes"]
    assert [e["rows"] for e in nodes] == [1] * len(loaded.nodes)
    # the result the command prints (the store's own count check) agrees with the batches written
    assert printed["counts"]["nodes"] == {"expected": len(loaded.nodes), "kept": len(loaded.nodes)}
    named = {r["id"] for r in printed["writes"]["oversized_records"]}
    assert named == {n.canonical_id for n in loaded.nodes}, named
    assert printed["writes"]["payload_budget_bytes"] == 1 and printed["writes"]["row_cap"] == 3
