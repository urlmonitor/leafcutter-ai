"""KM-400b-5-v: a write batch that hits the writer's time limit is retried a bounded number of times.

Only time-limit failures are retried; the class of a failure is read from the structured
``cause_class`` the store error carries (``BatchDouble`` raises errors whose message text would
mislead a message matcher). 345 AC + 110 Test nodes under a row cap of 10 give 46 node batches
(AcceptanceCriterion batch 34 is a full 10-row batch), 1,160 edges give 116 relationship batches.
"""

import asyncio
import logging
import time

from tests.knowledge._km_400b_5_writes_support import (
    MARKER,
    backend_failure,
    retry_snapshot,
    retry_store,
    run_publish,
    run_sync_cli,
)

AC = "AcceptanceCriterion"
TIME_LIMIT = "time_limit"
NODES_TOTAL, EDGES_TOTAL = 455, 1160


def _chain(error):
    while error is not None:
        yield error
        error = error.__cause__ or error.__context__


def _retried_once(**store_kwargs):
    store = retry_store(faults={("nodes", 34): [TIME_LIMIT]}, **store_kwargs)
    return run_publish(store, retry_snapshot())


def test_retry_repeats_only_the_failed_batch_and_continues_with_the_next():
    # covers: KM-400b-5-v
    # angle: discrimination
    outcome = _retried_once()
    assert outcome.ok, outcome.error
    store = outcome.store
    assert store.total("nodes") == 46  # control: the fixture really has 46 node batches
    ordinals = [e["ordinal"] for e in store.batch_log if e["phase"] == "nodes"]
    assert ordinals == [*range(1, 34), 34, 34, *range(35, 47)], ordinals
    assert store.attempts("nodes", 34)[0]["kind"] == AC


def test_retried_batch_rows_exist_exactly_once_after_the_retry():
    # covers: KM-400b-5-v
    # angle: discrimination
    outcome = _retried_once(store_on_fault=True)  # the abandoned attempt had already stored its rows
    assert outcome.ok, outcome.error
    first, second = outcome.store.attempts("nodes", 34)
    assert first["faulted"] and not second["faulted"]
    # the retry resends the batch whole, by key: identical rows, identical statement
    assert second["keys"] == first["keys"] and len(set(second["keys"])) == 10
    assert second["statement"] == first["statement"] and "MERGE (n:" in second["statement"]
    assert "{key:row.key}" in second["statement"]
    assert sum(1 for g in outcome.store.nodes.values() if g == outcome.key) == NODES_TOTAL
    assert all(outcome.store.nodes[k] == outcome.key for k in second["keys"])


def test_count_check_figures_are_unchanged_by_a_retry():
    # covers: KM-400b-5-v
    # angle: discrimination
    plain = run_publish(retry_store(), retry_snapshot())
    assert plain.ok, plain.error
    retried = _retried_once(store_on_fault=True)
    assert retried.ok, retried.error
    expected = {
        "nodes": {"expected": NODES_TOTAL, "kept": NODES_TOTAL},
        "relationships": {"expected": EDGES_TOTAL, "kept": EDGES_TOTAL},
    }
    assert plain.store.total("nodes") == retried.store.total("nodes") == 46
    assert [e["faulted"] for e in retried.store.attempts("nodes", 34)] == [True, False]  # a real retry
    assert plain.store.publication_counts == expected
    assert retried.store.publication_counts == expected


def test_publication_succeeds_when_the_second_attempt_succeeds():
    # covers: KM-400b-5-v
    # angle: criterion
    outcome = _retried_once()
    store = outcome.store
    assert [e["faulted"] for e in store.attempts("nodes", 34)] == [True, False]  # batch 34 was retried
    assert outcome.error is None, outcome.error
    assert outcome.result is True
    assert store.active_key == outcome.key  # the pointer switched
    assert store.snapshots[outcome.key]["status"] == "ready"
    assert store.deleted_keys == [] and store.publication_removal == {"outcome": "nothing_stored"}


def test_result_reports_the_retried_batch_with_rows_and_bytes():
    # covers: KM-400b-5-v
    # angle: discrimination
    outcome = _retried_once()
    assert outcome.ok, outcome.error
    retried = outcome.writes["retried_batches"]
    assert len(retried) == 1, retried
    record = retried[0]
    batch, entry = record["batch"], outcome.store.attempts("nodes", 34)[-1]
    assert (batch["phase"], batch["label_or_kind"], batch["ordinal"], batch["total"]) == ("nodes", AC, 34, 46)
    assert batch["rows"] == 10
    assert abs(batch["payload_bytes"] - entry["bytes"]) <= 0.1 * entry["bytes"], (batch, entry["bytes"])
    assert (record["attempts"], record["max_attempts"], record["attempt_causes"]) == (2, 3, [TIME_LIMIT])


def test_no_fourth_attempt_is_made():
    # covers: KM-400b-5-v
    # angle: boundary
    store = retry_store(faults={("nodes", 34): [TIME_LIMIT] * 6})
    outcome = run_publish(store, retry_snapshot())
    assert outcome.error is not None
    assert len(store.attempts("nodes", 34)) == 3
    assert store.attempts("nodes", 35) == []  # and the publication did not go on past it
    # a declared limit of 2 is honoured as well
    two = retry_store(faults={("nodes", 34): [TIME_LIMIT] * 6}, write_max_attempts=2)
    run_publish(two, retry_snapshot())
    assert len(two.attempts("nodes", 34)) == 2


def test_exhausted_retries_fail_the_publication_and_remove_the_generation():
    # covers: KM-400b-5-v
    # angle: failure
    from knowledge.errors import BackendUnavailable

    store = retry_store(faults={("nodes", 34): [TIME_LIMIT] * 3})
    outcome = run_publish(store, retry_snapshot())
    assert len(store.attempts("nodes", 34)) == 3, "the batch was not tried three times"
    assert isinstance(outcome.error, BackendUnavailable), repr(outcome.error)
    assert store.publication_removal["outcome"] == "removed", store.publication_removal
    assert store.publication_removal["nodes"] == 330  # the 33 completed batches, none from batch 34
    assert store.tagged(outcome.key) == (0, 0)
    assert store.active_key is None and store.snapshots.get(outcome.key, {}).get("status") != "ready"


def test_exhausted_result_states_time_limit_cause_after_three_attempts(caplog):
    # covers: KM-400b-5-v
    # angle: discrimination
    caplog.set_level(logging.WARNING)
    store = retry_store(faults={("nodes", 34): [TIME_LIMIT] * 3})
    outcome = run_publish(store, retry_snapshot())
    failure = outcome.failure
    assert failure is not None, "no publication_failure was reported"
    assert failure["cause"] == TIME_LIMIT
    assert failure["attempts"] == 3 and failure["attempt_causes"] == [TIME_LIMIT] * 3, failure
    assert "after 3 attempts" in str(outcome.error), str(outcome.error)
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert errors, "exhausted retries were not logged at ERROR"
    assert MARKER not in " ".join(r.getMessage() for r in caplog.records)
    assert "xxxxxxxx" not in " ".join(r.getMessage() for r in caplog.records)


def _not_retried(monkeypatch, cause):
    """A control time-limit retry, then a non-retryable fault on the same batch."""
    control = _retried_once()
    assert control.ok, control.error  # the control row: a time-limit failure IS retried
    sleeps = []

    async def fake_async_sleep(delay=0, *_a, **_k):
        sleeps.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_async_sleep)
    monkeypatch.setattr(time, "sleep", lambda delay: sleeps.append(delay))
    store = retry_store(faults={("nodes", 34): [cause] * 3})
    outcome = run_publish(store, retry_snapshot())
    return outcome, store, sleeps


def test_read_only_refusal_is_not_retried_and_fails_at_once(monkeypatch):
    # covers: KM-400b-5-v
    # angle: discrimination
    outcome, store, sleeps = _not_retried(monkeypatch, "read_only")
    assert outcome.error is not None
    assert len(store.attempts("nodes", 34)) == 1  # its message even says "timeout": text is not the test
    assert sleeps == []
    # the real backend classifies the server's refusal by its code
    _, refusal = backend_failure("Neo.ClientError.General.ForbiddenOnReadOnlyDatabase")
    assert refusal is not None and getattr(refusal, "cause_class", None) == "read_only"
    assert store.attempts("nodes", 35) == []


def test_uniqueness_violation_is_not_retried(monkeypatch):
    # covers: KM-400b-5-v
    # angle: discrimination
    outcome, store, sleeps = _not_retried(monkeypatch, "rule_violation")
    assert outcome.error is not None
    assert len(store.attempts("nodes", 34)) == 1
    assert sleeps == []
    _, violation = backend_failure("Neo.ClientError.Schema.ConstraintValidationFailed")
    assert violation is not None and getattr(violation, "cause_class", None) == "rule_violation"


def test_read_only_refusal_is_the_reported_cause(monkeypatch):
    # covers: KM-400b-5-v
    # angle: discrimination
    outcome, store, _ = _not_retried(monkeypatch, "read_only")
    message = str(outcome.error)
    assert "store is read-only: write refused" in message, message
    assert any(getattr(e, "cause_class", None) == "read_only" for e in _chain(outcome.error))
    assert outcome.failure["cause"] == "read_only" and outcome.failure["attempts"] == 1, outcome.failure
    assert "time limit" not in message and "retries" not in message.lower(), message


def test_uniqueness_violation_is_the_reported_cause(monkeypatch):
    # covers: KM-400b-5-v
    # angle: discrimination
    outcome, store, _ = _not_retried(monkeypatch, "rule_violation")
    message = str(outcome.error)
    assert "uniqueness rule violated for key" in message, message
    assert any(getattr(e, "cause_class", None) == "rule_violation" for e in _chain(outcome.error))
    assert outcome.failure["cause"] == "rule_violation", outcome.failure
    assert "time limit" not in message, message


def test_two_retried_batches_are_both_reported():
    # covers: KM-400b-5-v
    # angle: discrimination
    store = retry_store(faults={("nodes", 12): [TIME_LIMIT], ("nodes", 34): [TIME_LIMIT]})
    outcome = run_publish(store, retry_snapshot())
    assert outcome.ok, outcome.error
    retried = outcome.writes["retried_batches"]
    assert [r["batch"]["ordinal"] for r in retried] == [12, 34], retried
    assert [r["attempts"] for r in retried] == [2, 2]
    # a retried relationship batch is reported alongside, from a later phase
    rel = retry_store(faults={("nodes", 12): [TIME_LIMIT], ("relationships", 80): [TIME_LIMIT]})
    both = run_publish(rel, retry_snapshot())
    assert both.ok, both.error
    assert [(r["batch"]["phase"], r["batch"]["ordinal"]) for r in both.writes["retried_batches"]] == [
        ("nodes", 12),
        ("relationships", 80),
    ]


def test_retry_settings_are_validated_before_any_write():
    # covers: KM-400b-5-v
    # angle: boundary
    import pytest

    from knowledge.adapters.neo4j_writes import begin_writes
    from tests.knowledge._km_400b_5_writes_support import make_snapshot

    def settings(attempts, wait):
        store = retry_store(write_max_attempts=attempts)
        store.write_retry_wait_seconds = wait
        return begin_writes(store, make_snapshot([]))

    assert settings(1, 0)["max_attempts"] == 1 and settings(3, 0.5)["wait"] == 0.5  # controls
    for attempts in (0, -1, 2.5, "3", True):
        with pytest.raises(ValueError, match="write_max_attempts"):
            settings(attempts, 1.0)
    for wait in (-1, float("nan"), float("inf"), "1", True):
        with pytest.raises(ValueError, match="write_retry_wait_seconds"):
            settings(3, wait)
    store = retry_store(write_max_attempts=0)
    outcome = run_publish(store, retry_snapshot())
    assert isinstance(outcome.error, ValueError), repr(outcome.error)
    assert store.batches("nodes") == [], "a write was sent despite an invalid retry setting"


def test_km_400b_5_v_reachable_from_sync_entry_point(tmp_path):
    # covers: KM-400b-5-v
    # angle: reachability
    # Entry point: `python -m knowledge sync --root <repo>` (knowledge.__main__.main() with real
    # argv, fresh subprocess); only the writer's Neo4j driver is replaced, and it times out the
    # second node batch once.
    kwargs = {"write_row_cap": 1, "write_max_attempts": 3, "faults": {("nodes", 2): [TIME_LIMIT]}}
    done, loaded, printed, lines = run_sync_cli(tmp_path, kwargs)
    assert done.returncode == 0, done.stderr
    assert printed["status"] == "ok" and printed["published"] is True, printed
    log = next(line for line in lines if "batch_log" in line)["batch_log"]
    assert [e["attempt"] for e in log if e["phase"] == "nodes" and e["ordinal"] == 2] == [1, 2]
    retried = printed["writes"]["retried_batches"]
    assert len(retried) == 1 and retried[0]["batch"]["ordinal"] == 2 and retried[0]["attempts"] == 2, retried
    assert printed["counts"]["nodes"] == {"expected": len(loaded.nodes), "kept": len(loaded.nodes)}

