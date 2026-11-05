"""KM-400b-5-iii: write batches are bounded by payload size as well as by row count.

The 11,307-node / 28,814-relationship snapshot of the criteria is built with the real
``knowledge.contracts`` models and published through the real ``neo4j_projection.publish`` against
``BatchDouble`` (see ``_km_400b_5_writes_support`` for the full contract these tests pin).

Sizes are measured as the serialized rows of a batch (``json.dumps`` defaults), the same way the
double records them; the large rows are sized so ten of them fit the 2,000,000-byte budget.
"""

import logging

import pytest

from tests.knowledge._km_400b_5_writes_support import (
    DEFAULT_BUDGET,
    DEFAULT_ROW_CAP,
    BatchDouble,
    bulk_for,
    graded_snapshot,
    make_edge,
    make_entity,
    make_snapshot,
    node_id,
    run_publish,
    run_sync_cli,
)

SMALL_AC, SMALL_TEST, LARGE, OVERSIZED = 5125, 5875, 300, 7
NODE_TOTAL = SMALL_AC + SMALL_TEST + LARGE + OVERSIZED  # 11,307
EDGE_TOTAL, BIG_EDGES = 28814, 40


def _violations(entries, cap=DEFAULT_ROW_CAP, budget=DEFAULT_BUDGET):
    return [
        (e["phase"], e["kind"], e["ordinal"], e["rows"], e["bytes"])
        for e in entries
        if e["rows"] > cap or (e["rows"] > 1 and e["bytes"] > budget)
    ]


def _declared(outcome, cap=DEFAULT_ROW_CAP, budget=DEFAULT_BUDGET):
    """The Given of the criteria: the writer declares its row cap and payload budget."""
    writes = outcome.writes
    assert writes is not None, "publication reported no writes (publication_writes)"
    assert writes["row_cap"] == cap and writes["payload_budget_bytes"] == budget, writes
    return writes


@pytest.fixture(scope="module")
def big():
    """Publish the criteria's snapshot once: small, 200,000-byte and 2,500,000-byte nodes."""
    nodes = [make_entity(node_id("AcceptanceCriterion", i), "AcceptanceCriterion") for i in range(SMALL_AC)]
    nodes += [make_entity(node_id("Test", i), "Test") for i in range(SMALL_TEST)]
    nodes += [make_entity(node_id("ADR", i), "ADR", bulk_for(195_000)) for i in range(LARGE)]
    nodes += [make_entity(node_id("Flow", i), "Flow", bulk_for(2_500_000)) for i in range(OVERSIZED)]
    edges = [
        make_edge(
            node_id("AcceptanceCriterion", i % SMALL_AC),
            node_id("Test", (i * 7 + i // SMALL_AC) % SMALL_TEST),
            "covered_by",
            f"l{i:06d}",
            149_000 if i < BIG_EDGES else 0,  # the 40 large relationships sit together
        )
        for i in range(EDGE_TOTAL)
    ]
    snapshot = make_snapshot(nodes, edges)
    return run_publish(BatchDouble(), snapshot)


def test_no_node_batch_exceeds_the_row_cap(big):
    # covers: KM-400b-5-iii
    # angle: discrimination
    assert big.ok, big.error
    batches = big.store.batches("nodes")
    assert [b for b in batches if b["rows"] > DEFAULT_ROW_CAP] == []
    # the small nodes still fill batches to the cap, so the cap is the closing rule that bites
    small = [b for b in batches if b["kind"] == "AcceptanceCriterion"]
    assert [b["rows"] for b in small] == [250] * 20 + [125]
    # the cap is the declared one: a configured cap of 7 closes 21 same-size nodes at exactly 7
    store = BatchDouble(write_row_cap=7)
    snapshot = make_snapshot([make_entity(node_id("Test", i), "Test") for i in range(21)])
    outcome = run_publish(store, snapshot)
    assert outcome.ok, outcome.error
    assert [b["rows"] for b in store.batches("nodes")] == [7, 7, 7]


def test_no_batch_exceeds_the_payload_budget_unless_it_holds_one_record(big):
    # covers: KM-400b-5-iii
    # angle: discrimination
    assert big.ok, big.error
    entries = big.store.batches("nodes") + big.store.batches("relationships")
    assert _violations(entries) == []
    # the budget is what closes the large-record batches: they are filled, not split to single rows
    large = [b for b in big.store.batches("nodes") if b["kind"] == "ADR"]
    assert max(b["rows"] for b in large) >= 8, [b["rows"] for b in large]
    # a configured budget is honoured too: 10 rows of ~1 KB under a 5,000-byte budget
    store = BatchDouble(write_payload_budget_bytes=5_000)
    outcome = run_publish(store, make_snapshot([make_entity(node_id("Test", i), "Test") for i in range(10)]))
    assert outcome.ok, outcome.error
    assert _violations(store.batches("nodes"), budget=5_000) == []
    assert len(store.batches("nodes")) >= 2


def test_large_record_batches_hold_at_most_ten_rows(big):
    # covers: KM-400b-5-iii
    # angle: discrimination
    assert big.ok, big.error
    large = [b for b in big.store.batches("nodes") if b["kind"] == "ADR"]
    assert sum(b["rows"] for b in large) == LARGE
    assert [b["rows"] for b in large if b["rows"] > 10] == []
    assert len(large) <= 38, "large records fragmented far below what the budget requires"


def test_small_record_batches_are_not_split_below_the_row_cap(big):
    # covers: KM-400b-5-iii
    # angle: discrimination
    assert big.ok, big.error
    _declared(big)
    batches = big.store.batches("nodes")
    by_kind = {kind: [b["rows"] for b in batches if b["kind"] == kind] for kind in ("AcceptanceCriterion", "Test")}
    assert by_kind["AcceptanceCriterion"] == [250] * 20 + [125]
    assert by_kind["Test"] == [250] * 23 + [125]


def test_oversized_node_is_written_alone_and_not_dropped(big):
    # covers: KM-400b-5-iii
    # angle: discrimination
    assert big.ok, big.error  # the partitioner terminated
    flows = [b for b in big.store.batches("nodes") if b["kind"] == "Flow"]
    assert [b["rows"] for b in flows] == [1] * OVERSIZED
    assert all(b["bytes"] > DEFAULT_BUDGET for b in flows)
    assert sum(1 for g in big.store.nodes.values() if g == big.key) == NODE_TOTAL
    assert big.store.publication_counts["nodes"] == {"expected": NODE_TOTAL, "kept": NODE_TOTAL}


def test_publication_result_names_each_oversized_node(big, caplog):
    # covers: KM-400b-5-iii
    # angle: discrimination
    assert big.ok, big.error
    writes = _declared(big)
    oversized = writes["oversized_records"]
    expected_ids = {node_id("Flow", i) for i in range(OVERSIZED)}
    assert {r["id"] for r in oversized} == expected_ids and len(oversized) == OVERSIZED
    assert {r["label"] for r in oversized} == {"Flow"}
    assert all(2_400_000 <= r["payload_bytes"] <= 2_600_000 for r in oversized), oversized
    # logged at WARNING with identity and label, never the payload content
    caplog.set_level(logging.WARNING)
    store = BatchDouble()
    snapshot = make_snapshot(
        [make_entity(node_id("Flow", 0), "Flow", bulk_for(2_500_000)), make_entity(node_id("Test", 0), "Test")]
    )
    outcome = run_publish(store, snapshot)
    assert outcome.ok, outcome.error
    warned = [r for r in caplog.records if r.levelno == logging.WARNING and node_id("Flow", 0) in r.getMessage()]
    assert warned, "no WARNING names the oversized record"
    assert "Flow" in warned[0].getMessage()
    assert all("xxxxxxxx" not in r.getMessage() for r in caplog.records)
    assert [r["id"] for r in outcome.writes["oversized_records"]] == [node_id("Flow", 0)]


def test_every_node_is_written_exactly_once_across_batches(big):
    # covers: KM-400b-5-iii
    # angle: discrimination
    assert big.ok, big.error
    batches = big.store.batches("nodes")
    assert _violations(batches) == [], "the partition must obey the bounds before exactly-once means anything"
    keys = [k for b in batches for k in b["keys"]]
    assert len(keys) == NODE_TOTAL == sum(b["rows"] for b in batches)
    assert len(set(keys)) == NODE_TOTAL


def test_publication_result_states_row_cap_and_payload_budget_in_force():
    # covers: KM-400b-5-iii
    # angle: discrimination
    snapshot = make_snapshot([make_entity(node_id("Test", i), "Test") for i in range(30)])
    default = run_publish(BatchDouble(), snapshot)
    assert default.ok, default.error
    _declared(default)
    configured = run_publish(
        BatchDouble(write_row_cap=40, write_payload_budget_bytes=500_000),
        make_snapshot([make_entity(node_id("Test", i), "Test") for i in range(30)]),
    )
    assert configured.ok, configured.error
    _declared(configured, cap=40, budget=500_000)


def test_no_relationship_batch_exceeds_the_row_cap_or_payload_budget(big):
    # covers: KM-400b-5-iii
    # angle: discrimination
    assert big.ok, big.error
    batches = big.store.batches("relationships")
    assert batches and {b["kind"] for b in batches} == {"COVERED_BY"}
    assert _violations(batches) == []
    heavy = [b for b in batches if b["bytes"] > 1_000_000]
    assert heavy, "the 40 large relationships never made a heavy batch (fixture control)"
    assert max(b["rows"] for b in batches) == DEFAULT_ROW_CAP  # light batches are still full


def test_every_relationship_is_written_exactly_once_across_batches(big):
    # covers: KM-400b-5-iii
    # angle: discrimination
    assert big.ok, big.error
    batches = big.store.batches("relationships")
    assert _violations(batches) == [], "the partition must obey the bounds before exactly-once means anything"
    keys = [k for b in batches for k in b["keys"]]
    assert len(keys) == EDGE_TOTAL == sum(b["rows"] for b in batches)
    assert len(set(keys)) == EDGE_TOTAL
    assert big.store.tagged(big.key)[1] == EDGE_TOTAL
    assert big.store.publication_counts["relationships"] == {"expected": EDGE_TOTAL, "kept": EDGE_TOTAL}


def test_small_payload_snapshot_batches_match_a_row_cap_alone():
    # covers: KM-400b-5-iii
    # angle: discrimination
    def run():
        store = BatchDouble()
        outcome = run_publish(store, graded_snapshot(1000, 600, ac_bulk=0, test_bulk=0))
        assert outcome.ok, outcome.error
        return store, outcome

    store, outcome = run()
    _declared(outcome)
    sizes = {k: [b["rows"] for b in store.batches("nodes") if b["kind"] == k] for k in ("AcceptanceCriterion", "Test")}
    assert sizes == {"AcceptanceCriterion": [250, 250, 250, 250], "Test": [250, 250, 100]}
    again, _ = run()
    signature = lambda s: [(b["kind"], b["rows"], b["bytes"]) for b in s.batches("nodes")]  # noqa: E731
    assert signature(store) == signature(again), "batches differ between two runs of one snapshot"


def test_km_400b_5_iii_reachable_from_sync_entry_point(tmp_path):
    # covers: KM-400b-5-iii
    # angle: reachability
    # Entry point: `python -m knowledge sync --root <repo>` (knowledge.__main__.main() with real
    # argv, fresh subprocess); only the writer's Neo4j driver is replaced by a recording double.
    done, loaded, printed, lines = run_sync_cli(tmp_path, {"write_row_cap": 2})
    assert done.returncode == 0, done.stderr
    assert printed["status"] == "ok" and printed["published"] is True, printed
    log = next(line for line in lines if "batch_log" in line)["batch_log"]
    nodes = [e for e in log if e["phase"] == "nodes"]
    # the declared cap really bites in the standalone command, and every node is written once
    assert max(e["rows"] for e in nodes) == 2 and [e for e in nodes if e["rows"] > 2] == []
    assert sum(e["rows"] for e in nodes) == len(loaded.nodes)
    # the result the command prints states the cap in force
    assert printed["writes"]["row_cap"] == 2 and printed["writes"]["payload_budget_bytes"] == DEFAULT_BUDGET
