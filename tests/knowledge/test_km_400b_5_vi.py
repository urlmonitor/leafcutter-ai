"""KM-400b-5-vi: a publication that fails on the writer's time limit names the phase and the slow batch.

``publication_failure`` (see ``_km_400b_5_writes_support``) is the discrete, machine-readable result;
the propagated message states the same facts: ``writing nodes`` / ``writing relationships`` /
``activation``, ``batch <n> of <total>``, ``<k> rows``, ``<b> bytes``, ``after <k> attempts``,
``<limit> seconds`` and ``<written> of <total> nodes`` / ``<written> of <total> relationships``.
345 AC + 110 Test nodes under a row cap of 10 give 46 node batches (batch 34 is a full AC batch of
10 rows, batch 35 the 5-row remainder); 1,160 edges give 116 relationship batches (80 is COVERED_BY).
"""

import re

from tests.knowledge._km_400b_5_writes_support import (
    backend_failure,
    retry_snapshot,
    retry_store,
    run_publish,
    run_sync_cli,
)

AC = "AcceptanceCriterion"
TIME_LIMIT = "time_limit"
BATCH_KEYS = {"phase", "label_or_kind", "ordinal", "total", "rows", "payload_bytes"}


def _failed(faults, **store_kwargs):
    store = retry_store(faults=faults, **store_kwargs)
    outcome = run_publish(store, retry_snapshot())
    assert outcome.error is not None, "the injected time limit never failed the publication"
    return outcome


def _slow(ordinal, phase="nodes", **store_kwargs):
    return _failed({(phase, ordinal): [TIME_LIMIT] * 3}, **store_kwargs)


def _failure(outcome):
    assert outcome.failure is not None, "no publication_failure was reported"
    return outcome.failure


def test_failure_states_time_limit_cause_and_the_effective_limit():
    # covers: KM-400b-5-vi
    # angle: discrimination
    for limit in (30, 12):
        outcome = _slow(34, query_timeout=limit)
        failure = _failure(outcome)
        assert failure["cause"] == TIME_LIMIT
        assert failure["time_limit_seconds"] == limit, failure
        assert f"{limit} seconds" in str(outcome.error), str(outcome.error)
    # the limit is the capped, effective one the real backend runs with, not the constructor argument
    for argument, effective in ((45, 30), (12, 12)):
        backend, error = backend_failure(
            "Neo.ClientError.Transaction.TransactionTimedOutClientConfiguration", argument
        )
        assert backend.query_timeout == effective
        assert error is not None and getattr(error, "cause_class", None) == TIME_LIMIT
        assert getattr(error, "time_limit_seconds", None) == effective, vars(error)


def test_failure_names_the_phase_as_writing_nodes():
    # covers: KM-400b-5-vi
    # angle: discrimination
    outcome = _slow(34)
    assert _failure(outcome)["phase"] == "nodes"
    assert "writing nodes" in str(outcome.error), str(outcome.error)


def test_failure_names_the_slow_batch_by_label_ordinal_rows_and_bytes():
    # covers: KM-400b-5-vi
    # angle: discrimination
    for ordinal, rows in ((34, 10), (35, 5)):  # a full batch, then the partial remainder
        outcome = _slow(ordinal)
        batch = _failure(outcome)["batch"]
        entry = outcome.store.attempts("nodes", ordinal)[-1]
        assert set(batch) == BATCH_KEYS, batch
        assert (batch["phase"], batch["label_or_kind"], batch["ordinal"], batch["total"]) == (
            "nodes",
            AC,
            ordinal,
            46,
        )
        assert batch["rows"] == rows == entry["rows"]
        assert abs(batch["payload_bytes"] - entry["bytes"]) <= 0.1 * entry["bytes"], (batch, entry["bytes"])
        message = str(outcome.error)
        assert f"batch {ordinal} of 46" in message and AC in message and f"{rows} rows" in message, message


def test_failure_states_three_attempts_were_made():
    # covers: KM-400b-5-vi
    # angle: discrimination
    outcome = _slow(34)
    failure = _failure(outcome)
    assert failure["attempts"] == 3, failure
    assert "3 attempts" in str(outcome.error), str(outcome.error)
    two = _failed({("nodes", 34): [TIME_LIMIT] * 2}, write_max_attempts=2)
    assert _failure(two)["attempts"] == 2 and "2 attempts" in str(two.error), str(two.error)


def test_failure_reports_progress_of_completed_batches_only():
    # covers: KM-400b-5-vi
    # angle: boundary
    for ordinal, written in ((34, 330), (35, 340), (1, 0)):
        outcome = _slow(ordinal)
        progress = _failure(outcome)["progress"]
        assert progress == {
            "nodes": {"written": written, "total": 455},
            "relationships": {"written": 0, "total": 1160},
        }, (ordinal, progress)
        message = str(outcome.error)
        assert re.search(rf"\b{written} of 455 nodes", message), message
        assert re.search(r"\b0 of 1,?160 relationships", message), message


def test_failure_still_reports_the_removal_outcome():
    # covers: KM-400b-5-vi
    # angle: failure
    outcome = _slow(34)
    store = outcome.store
    assert _failure(outcome)["cause"] == TIME_LIMIT
    assert store.publication_removal["outcome"] == "removed", store.publication_removal
    assert (store.publication_removal["nodes"], store.publication_removal["relationships"]) == (330, 0)
    message = str(outcome.error)
    assert "failed generation removed" in message, message
    assert "batch 34 of 46" in message, message  # the new facts sit beside the removal, not instead of it
    assert store.tagged(outcome.key) == (0, 0)


def test_time_limit_failure_is_distinguishable_from_unavailable_and_read_only():
    # covers: KM-400b-5-vi
    # angle: discrimination
    expected = {
        "Neo.ClientError.Transaction.TransactionTimedOutClientConfiguration": TIME_LIMIT,
        "Neo.ClientError.General.ForbiddenOnReadOnlyDatabase": "read_only",
        "Neo.TransientError.General.DatabaseUnavailable": "unavailable",
    }
    for code, cause in expected.items():
        _, error = backend_failure(code)
        assert error is not None and getattr(error, "cause_class", None) == cause, (code, vars(error))
    results = {}
    for cause in (TIME_LIMIT, "read_only", "unavailable"):
        outcome = _slow(34) if cause == TIME_LIMIT else _failed({("nodes", 34): [cause] * 3})
        results[cause] = (_failure(outcome), str(outcome.error))
    assert {c: f["cause"] for c, (f, _) in results.items()} == {c: c for c in expected.values()}
    for cause in ("read_only", "unavailable"):
        failure, message = results[cause]
        assert "time_limit_seconds" not in failure and failure["attempts"] == 1, failure
        assert "seconds" not in message and "time limit" not in message, message
    assert "time_limit_seconds" in results[TIME_LIMIT][0]


def _retry_real(backend):
    import asyncio

    from knowledge.adapters.neo4j_writes import with_retry

    descriptor = {"phase": "nodes", "label_or_kind": AC, "ordinal": 1, "total": 1, "rows": 1, "payload_bytes": 1}
    call = lambda: backend._run("RETURN 1", {}, True)  # noqa: E731
    try:
        asyncio.run(with_retry(backend, "nodes", descriptor, call))
    except Exception as error:  # noqa: BLE001 -- the test inspects whatever the retry raised
        return error
    return None


def test_connect_step_timeout_is_unavailable_and_not_retried():
    # covers: KM-400b-5-vi
    # angle: discrimination
    from tests.knowledge._km_400b_5_writes_support import real_backend

    backend = real_backend(None, 30, connect_error=TimeoutError("connect timed out"))
    error = _retry_real(backend)
    assert error is not None and getattr(error, "cause_class", None) == "unavailable", vars(error)
    assert not hasattr(error, "time_limit_seconds"), vars(error)
    assert backend.driver.connects == 1, "a connect timeout was retried as a query time limit"
    failure = backend.publication_failure
    assert failure["cause"] == "unavailable" and failure["attempts"] == 1, failure
    assert "time_limit_seconds" not in failure and "time limit" not in str(error), (failure, str(error))


def test_query_step_timeout_is_time_limit_and_retried():
    # covers: KM-400b-5-vi
    # angle: discrimination
    from tests.knowledge._km_400b_5_writes_support import real_backend

    backend = real_backend(TimeoutError("query timed out"), 30)
    error = _retry_real(backend)
    assert error is not None and getattr(error, "cause_class", None) == TIME_LIMIT, vars(error)
    assert backend.driver.sessions == 3, "the query time limit was not retried to the attempt cap"
    assert backend.publication_failure["attempts"] == 3 and "3 attempts" in str(error), str(error)


def test_time_limit_seconds_is_the_timeout_actually_applied():
    # covers: KM-400b-5-vi
    # angle: boundary
    code = "Neo.ClientError.Transaction.TransactionTimedOutClientConfiguration"
    _, plain = backend_failure(code, 30)
    assert plain.time_limit_seconds == 30
    _, capped = backend_failure(code, 30, deadline_seconds=5)  # a request deadline tighter than the writer's limit
    assert 0 < capped.time_limit_seconds <= 5, vars(capped)


def test_relationship_batch_failure_names_phase_kind_ordinal_rows_and_bytes():
    # covers: KM-400b-5-vi
    # angle: discrimination
    outcome = _slow(80, phase="relationships")
    failure = _failure(outcome)
    entry = outcome.store.attempts("relationships", 80)[-1]
    assert failure["phase"] == "relationships"
    batch = failure["batch"]
    assert (batch["phase"], batch["label_or_kind"], batch["ordinal"], batch["total"], batch["rows"]) == (
        "relationships",
        "COVERED_BY",
        80,
        116,
        10,
    )
    assert abs(batch["payload_bytes"] - entry["bytes"]) <= 0.1 * entry["bytes"]
    assert failure["progress"] == {
        "nodes": {"written": 455, "total": 455},
        "relationships": {"written": 790, "total": 1160},
    }
    message = str(outcome.error)
    assert "writing relationships" in message and "COVERED_BY" in message and "batch 80 of 116" in message, message


def test_activation_failure_names_the_activation_phase():
    # covers: KM-400b-5-vi
    # angle: discrimination
    store = retry_store(activation_faults=[TIME_LIMIT] * 3)
    outcome = run_publish(store, retry_snapshot())
    assert outcome.error is not None, "the activation time limit never failed the publication"
    failure = _failure(outcome)
    assert failure["phase"] == "activation", failure
    assert failure["cause"] == TIME_LIMIT and failure["attempts"] == 3, failure
    assert "activation" in str(outcome.error), str(outcome.error)
    assert store.active_key is None


def test_activation_failure_states_no_write_batch_was_involved():
    # covers: KM-400b-5-vi
    # angle: discrimination
    store = retry_store(activation_faults=[TIME_LIMIT] * 3)
    outcome = run_publish(store, retry_snapshot())
    assert outcome.error is not None
    failure = _failure(outcome)
    assert failure["batch"] == "not_applicable", failure
    message = str(outcome.error)
    assert "no write batch" in message, message
    assert not re.search(r"\b0 rows|\b0 bytes|rows 0|bytes 0|batch 0", message), message
    for stale in (AC, "Test", "COVERED_BY", "DEPENDS_ON", "batch 46", "batch 116"):
        assert stale not in message, (stale, message)
    assert failure["progress"] == {
        "nodes": {"written": 455, "total": 455},
        "relationships": {"written": 1160, "total": 1160},
    }


def test_activation_only_failure_does_not_report_the_previous_publications_progress():
    # covers: KM-400b-5-vi
    # angle: discrimination
    from knowledge.adapters.neo4j_backend import Neo4jBackend

    assert Neo4jBackend.publication_progress is None  # declared on the adapter, default none
    store = retry_store()
    first = run_publish(store, retry_snapshot())
    assert first.ok, first.error
    assert store.publication_progress["nodes"]["written"] == 455  # control: the first run set it
    store.activation_faults = [TIME_LIMIT] * 3
    second = run_publish(store, retry_snapshot())  # same content; generation already ready: no write batch, activation only
    assert second.error is not None, "the activation time limit never failed the second publication"
    assert second.failure is not None, repr(second.error)
    failure = _failure(second)
    assert failure["phase"] == "activation" and failure["batch"] == "not_applicable", failure
    assert failure["progress"] is None, failure  # nothing was written by this publication
    assert store.publication_progress is None
    assert "nodes and" not in str(second.error), str(second.error)


def test_phase_and_batch_come_from_publication_state_not_the_error_text():
    # covers: KM-400b-5-vi
    # angle: discrimination
    misleading = "TransientError terminated while writing label Test batch 2 of 99 (relationships)"
    outcome = _failed({("nodes", 34): [TIME_LIMIT] * 3}, fault_message=misleading)
    failure = _failure(outcome)
    assert failure["phase"] == "nodes"
    assert (failure["batch"]["label_or_kind"], failure["batch"]["ordinal"], failure["batch"]["total"]) == (AC, 34, 46)
    # no store round-trip was spent finding out: after the last batch written, only the failure
    # handling (mark failed, count, delete) reached the store
    log = outcome.store.log
    last_write = max(i for i, (statement, _) in enumerate(log) if "UNWIND $rows" in statement)
    after = [statement for statement, _ in log[last_write + 1 :]]
    assert after, "the failure handling never reached the store (control)"
    allowed = ('g.status="failed"', "RETURN count(", "DELETE")
    assert all(any(token in statement for token in allowed) for statement in after), after


def test_km_400b_5_vi_reachable_from_sync_entry_point(tmp_path):
    # covers: KM-400b-5-vi
    # angle: reachability
    # Entry point: `python -m knowledge sync --root <repo>` (knowledge.__main__.main() with real
    # argv, fresh subprocess); only the writer's Neo4j driver is replaced, and it times out the
    # second node batch on every attempt.
    kwargs = {"write_row_cap": 1, "write_max_attempts": 3, "faults": {("nodes", 2): [TIME_LIMIT] * 3}}
    done, loaded, printed, lines = run_sync_cli(tmp_path, kwargs)
    assert done.returncode == 2, done.stderr
    driver = next(line for line in lines if "batch_log" in line)
    failure = next(line for line in lines if line.get("status") == "unavailable")  # BackendUnavailable
    label = next(e["kind"] for e in driver["batch_log"] if e["phase"] == "nodes" and e["ordinal"] == 2)
    # "of M" is the number of node batches PLANNED for the phase. The double's own totals
    # count only the batches it received before the run aborted, so derive M from the node
    # total instead: with a row cap of 1 every node is its own batch.
    message = failure["message"]
    planned = re.search(r"\b\d+ of (\d+) nodes", message)
    assert planned, message
    total = int(planned.group(1))
    assert total > driver["totals"]["nodes"], (total, driver["totals"])  # batches after 2 never sent
    assert "writing nodes" in message and label in message, message
    assert f"batch 2 of {total}" in message and "3 attempts" in message, message
    assert [e["attempt"] for e in driver["batch_log"] if e["ordinal"] == 2 and e["phase"] == "nodes"] == [1, 2, 3]
    assert re.search(r"\b1 of \d+ nodes", message), message  # one node batch of one row completed
    # the same facts are discrete machine-readable keys in the printed error, not only in the message
    assert failure["cause_class"] == TIME_LIMIT, failure
    assert failure["time_limit_seconds"] == 30, failure
    assert failure["phase"] == "nodes" and failure["attempts"] == 3, failure
    assert failure["attempt_causes"] == [TIME_LIMIT] * 3, failure
    assert set(failure["batch"]) == BATCH_KEYS and failure["batch"]["ordinal"] == 2, failure
    assert failure["batch"]["total"] == total and failure["batch"]["label_or_kind"] == label, failure
    assert failure["progress"]["nodes"] == {"written": 1, "total": total}, failure
    assert failure["progress"]["relationships"]["written"] == 0, failure
    assert failure["writes"]["row_cap"] == 1, failure  # the write report travels with the failure
    assert {"status", "retryable", "message"} <= set(failure)  # existing keys are kept
