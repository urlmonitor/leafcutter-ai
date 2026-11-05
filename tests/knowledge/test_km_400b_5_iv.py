"""KM-400b-5-iv: write verification compares content fingerprints, not stored payloads.

Publication runs through the real ``neo4j_projection.publish`` / ``neo4j_domain_build.build`` against
``BatchDouble`` (contract in ``_km_400b_5_writes_support``); the direct ``verify_rows`` tests feed it
rows shaped exactly like the ones the writer builds and the store returns (key and fingerprint).
"""

import hashlib
import importlib
import json
import logging

from tests.knowledge._km_400b_5_writes_support import (
    MARKER,
    BatchDouble,
    bulk_for,
    graded_snapshot,
    make_entity,
    make_snapshot,
    node_id,
    run_publish,
    run_sync_cli,
)

AC = "AcceptanceCriterion"


def _verification():
    return importlib.import_module("knowledge.adapters.native_verification")


def _sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def _expected(count):
    """Writer-shaped rows (identity, kind, key and fingerprint) and the matching store read-back."""
    expected, stored = [], []
    for i in range(count):
        payload = json.dumps({"id": f"KM-{i}", "body": "text " * 5})
        fingerprint = _sha(payload)
        expected.append(
            {"key": f"k{i}", "canonical_id": f"KM-{i}", "kind": AC, "payload": payload, "fingerprint": fingerprint}
        )
        stored.append({"key": f"k{i}", "fingerprint": fingerprint})
    return expected, stored


def _verify(expected, stored):
    """Return the exception verify_rows raised, or None."""
    try:
        _verification().verify_rows(expected, stored)
    except Exception as error:  # noqa: BLE001 -- the tests inspect whatever verification raised
        return error
    return None


def _returned_json(entries):
    return json.dumps([e["returned"] for e in entries], sort_keys=True)


def test_verification_readback_returns_only_identity_and_fingerprint_per_node():
    # covers: KM-400b-5-iv
    # angle: discrimination
    store = BatchDouble()
    outcome = run_publish(store, make_snapshot([make_entity(node_id(AC, i), AC, 500) for i in range(250)]))
    assert outcome.ok, outcome.error
    [batch] = store.batches("nodes")
    assert batch["rows"] == 250
    assert "properties(" not in batch["return_clause"], batch["return_clause"]
    assert "fingerprint" in batch["return_clause"], batch["return_clause"]
    returned = batch["returned"]
    assert len(returned) == 250
    assert all(set(row) == {"key", "fingerprint"} for row in returned), returned[0]
    # the identity and fingerprint are the real ones: the key sent, a SHA-256 hex digest
    assert [row["key"] for row in returned] == batch["keys"]
    assert all(len(row["fingerprint"]) == 64 and int(row["fingerprint"], 16) >= 0 for row in returned)
    assert len({row["fingerprint"] for row in returned}) == 250


def test_no_stored_payload_body_is_returned_for_verification():
    # covers: KM-400b-5-iv
    # angle: discrimination
    snapshot = graded_snapshot(20, 10, ac_bulk=100, test_bulk=100, covered_by=15, edge_bulk=100, marker=MARKER)
    assert MARKER in snapshot.nodes[0].model_dump_json() and MARKER in snapshot.edges[0].model_dump_json()
    store = BatchDouble()
    outcome = run_publish(store, snapshot)
    assert outcome.ok, outcome.error
    for phase in ("nodes", "relationships"):
        entries = store.batches(phase)
        assert entries and all(e["returned"] for e in entries), f"{phase}: nothing came back for verification"
        assert MARKER not in _returned_json(entries), f"a stored {phase} payload body was returned"
        assert "payload" not in _returned_json(entries)


def test_readback_size_is_constant_whatever_the_payload_total():
    # covers: KM-400b-5-iv
    # angle: discrimination
    def read_back(row_bytes_target):
        store = BatchDouble()
        bulk = bulk_for(row_bytes_target)
        outcome = run_publish(store, make_snapshot([make_entity(node_id("Test", i), "Test", bulk) for i in range(250)]))
        assert outcome.ok, outcome.error
        [batch] = store.batches("nodes")
        assert batch["rows"] == 250
        return batch["bytes"], len(_returned_json([batch]))

    large_total, large_back = read_back(7_000)
    small_total, small_back = read_back(1_000)
    assert large_total > 1_500_000 > 300_000 > small_total  # control: the payload totals differ widely
    assert large_back == small_back > 0


def test_matching_fingerprints_pass_verification():
    # covers: KM-400b-5-iv
    # angle: criterion
    verification = _verification()
    expected, stored = _expected(250)
    assert _verify(expected, stored) is None
    # one shared canonical serialization: key order and whitespace never change the fingerprint
    ordered, reordered = '{"a": 1, "b": [1, 2]}', '{ "b":[1,2],"a":1 }'
    assert verification.fingerprint(ordered) == verification.fingerprint(reordered)
    assert len(verification.fingerprint(ordered)) == 64
    writer_side = [dict(row, fingerprint=verification.fingerprint(row["payload"])) for row in expected]
    store_side = [
        {
            "key": row["key"],
            "fingerprint": verification.fingerprint(
                json.dumps(json.loads(row["payload"]), sort_keys=True, separators=(",", ":"))
            ),
        }
        for row in expected
    ]
    assert _verify(writer_side, store_side) is None


def test_single_character_change_fails_verification():
    # covers: KM-400b-5-iv
    # angle: discrimination
    verification = _verification()
    expected, stored = _expected(3)
    assert _verify(expected, stored) is None  # control row: the unchanged batch verifies
    long_payload = json.dumps({"id": "KM-400b-5", "body": "y" * 4_000})
    changed = long_payload[:-3] + "z" + long_payload[-2:]  # one character, far beyond the first 1,024 bytes
    fingerprint = getattr(verification, "fingerprint", None)
    assert callable(fingerprint), "native_verification.fingerprint(payload_json_text) must exist"
    assert fingerprint(long_payload) != fingerprint(changed)
    expected[1].update(payload=long_payload, fingerprint=fingerprint(long_payload))
    stored[1] = {"key": "k1", "fingerprint": fingerprint(changed)}
    error = _verify(expected, stored)
    assert isinstance(error, ValueError), repr(error)
    # a length-based or identity-only check would pass: same length, same identities
    assert len(long_payload) == len(changed)


def test_failure_names_node_label_and_both_fingerprints(caplog):
    # covers: KM-400b-5-iv
    # angle: discrimination
    expected, stored = _expected(3)
    expected[1].update(canonical_id="KM-400b-5", payload=json.dumps({"secret": MARKER}))
    expected_fp = expected[1]["fingerprint"] = _sha("expected-payload")
    stored_fp = _sha("stored-payload")
    stored[1] = {"key": "k1", "fingerprint": stored_fp}
    caplog.set_level(logging.ERROR)
    error = _verify(expected, stored)
    assert isinstance(error, ValueError), repr(error)
    message = str(error)
    assert "KM-400b-5" in message and AC in message, message
    assert expected_fp in message and stored_fp in message and expected_fp != stored_fp, message
    assert "KM-0" not in message and "KM-2" not in message, message  # not the first node of the batch
    assert MARKER not in message
    logged = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert logged, "no ERROR record for the verification failure"
    text = " ".join(r.getMessage() for r in logged)
    assert "KM-400b-5" in text and AC in text and expected_fp in text and stored_fp in text, text
    assert MARKER not in text


def test_verification_failure_removes_the_generation_with_the_original_cause():
    # covers: KM-400b-5-iv
    # angle: failure
    snapshot = graded_snapshot(30, 10, ac_bulk=200, test_bulk=200, covered_by=20, edge_bulk=50)
    target = node_id(AC, 3)
    store = BatchDouble(alter_ids={target})
    outcome = run_publish(store, snapshot)
    assert isinstance(outcome.error, ValueError), repr(outcome.error)
    entry = next(e for e in store.batches("nodes") if target in e["ids"])
    sent = entry["sent_fp"][entry["keys"][entry["ids"].index(target)]]
    stored = _sha(sent + "!")
    message = str(outcome.error)
    assert target in message and AC in message and sent in message and stored in message, message
    cause, _, removal = message.partition("failed generation removed")
    assert removal, "the removal outcome is stated after the cause: " + message
    assert "fingerprint mismatch" in cause and target in cause, message
    assert store.publication_removal["outcome"] == "removed", store.publication_removal
    assert store.tagged(outcome.key) == (0, 0)
    assert store.active_key is None  # nothing was activated


def test_missing_node_is_named_missing_not_mismatched():
    # covers: KM-400b-5-iv
    # angle: discrimination
    expected, stored = _expected(3)
    assert _verify(expected, stored) is None  # control row
    del stored[1]
    error = _verify(expected, stored)
    assert isinstance(error, ValueError), repr(error)
    message = str(error)
    assert "KM-1" in message and AC in message and "missing" in message, message
    assert "mismatch" not in message and "KM-0" not in message and "KM-2" not in message, message
    # through the writer: a node the store did not keep is named missing too
    store = BatchDouble(omit_ids={node_id(AC, 2)})
    outcome = run_publish(store, graded_snapshot(5, 3))
    assert isinstance(outcome.error, ValueError), repr(outcome.error)
    assert node_id(AC, 2) in str(outcome.error) and "missing" in str(outcome.error)
    assert "mismatch" not in str(outcome.error)


def test_relationship_batches_verify_by_fingerprint_and_name_the_failing_relationship():
    # covers: KM-400b-5-iv
    # angle: discrimination
    snapshot = lambda: graded_snapshot(30, 10, ac_bulk=100, test_bulk=100, covered_by=40, edge_bulk=300, marker=MARKER)  # noqa: E731
    store = BatchDouble()
    outcome = run_publish(store, snapshot())
    assert outcome.ok, outcome.error
    batches = store.batches("relationships")
    assert batches
    for batch in batches:
        clause = batch["return_clause"]
        assert clause and "fingerprint" in clause, f"relationship batch is not read back by fingerprint: {clause!r}"
        assert "payload" not in clause and "properties(" not in clause, clause
        assert [set(r) for r in batch["returned"]] == [{"key", "fingerprint"}] * batch["rows"]
        assert MARKER not in json.dumps(batch["returned"])
    # a changed relationship fails, naming it
    changed = BatchDouble(alter_first={("relationships", 1)})
    result = run_publish(changed, snapshot())
    first_key = changed.batches("relationships")[0]["keys"][0]
    assert isinstance(result.error, ValueError), repr(result.error)
    assert first_key in str(result.error) and "fingerprint mismatch" in str(result.error), str(result.error)
    # a missing relationship fails, naming it as missing
    lost = BatchDouble(omit_last={("relationships", 1)})
    result = run_publish(lost, snapshot())
    last_key = lost.batches("relationships")[0]["keys"][-1]
    assert isinstance(result.error, ValueError), repr(result.error)
    assert last_key in str(result.error) and "missing" in str(result.error), str(result.error)
    assert "mismatch" not in str(result.error)


def test_partial_relationship_readback_names_kind_batch_and_counts():
    # covers: KM-400b-5-iv
    # angle: boundary
    snapshot = graded_snapshot(30, 10, ac_bulk=100, test_bulk=100, covered_by=40, edge_bulk=300)
    lost = BatchDouble(write_row_cap=10, omit_last={("relationships", 2)})
    result = run_publish(lost, snapshot)
    last_key = lost.batches("relationships")[1]["keys"][-1]
    assert isinstance(result.error, ValueError), repr(result.error)
    message = str(result.error)
    assert last_key in message and "missing" in message and "mismatch" not in message, message
    # diagnosable without the store: the kind, the batch ordinal and the figures
    assert "COVERED_BY" in message and "batch 2 of 4" in message, message
    assert "expected 10" in message and "found 9" in message, message


def test_km_400b_5_iv_reachable_from_sync_entry_point(tmp_path):
    # covers: KM-400b-5-iv
    # angle: reachability
    # Entry point: `python -m knowledge sync --root <repo>` (knowledge.__main__.main() with real
    # argv, fresh subprocess); only the writer's Neo4j driver is replaced, and it stores one
    # altered payload.
    done, loaded, printed, lines = run_sync_cli(tmp_path, {"alter_ids": ["KM-FIX-1"]}, altered=["KM-FIX-1"])
    assert done.returncode == 2, done.stderr
    failure = next(line for line in lines if line.get("status") == "error")
    seen = next(line for line in lines if "altered" in line)["altered"]
    assert len(seen) == 1, seen
    message = failure["message"]
    assert "KM-FIX-1" in message and AC in message, message
    assert seen[0]["sent"] in message and seen[0]["stored"] in message, message
    assert seen[0]["sent"] != seen[0]["stored"]
