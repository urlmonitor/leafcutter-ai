"""KM-400b-5-vii: planning or writing batches before ``begin_writes`` is refused by name.

``begin_writes`` sets ``publication_writes`` and ``publication_progress``; ``neo4j_projection``
resets both to ``None`` when a publication starts. A caller that plans or writes batches in
between must get a ``RuntimeError`` naming ``begin_writes`` before anything reaches the store,
not a ``TypeError``/``AttributeError`` from deep inside the writer, and not a silent pass when
no record happens to be oversized. ``with_retry`` needs the report only to record a retried
batch, so its failure classification (KM-400b-5-vi) and activation still run without it.
"""

import asyncio

import pytest

from knowledge.adapters import neo4j_writes as writes
from knowledge.errors import BackendUnavailable
from tests.knowledge._km_400b_5_writes_support import make_error, real_backend

AC = "AcceptanceCriterion"
STATEMENT = "UNWIND $rows AS row MERGE (n:AC {key:row.key})"
TIME_LIMIT = "time_limit"


class _NeverBegun:
    """A writer whose publication state was reset by ``neo4j_projection`` and never begun.

    ``_write_settings`` is left over from an earlier publication on the same backend, so the
    writer gets past its settings and reaches the report it was never given.
    """

    publication_writes = None
    publication_progress = None
    write_max_attempts = 3
    write_retry_wait_seconds = 0

    def __init__(self):
        self._write_settings = {"row_cap": 250, "payload_budget_bytes": 100, "max_attempts": 3, "wait": 0}
        self.statements = []

    async def _run(self, statement, params, write=False):
        self.statements.append(statement)
        return params["rows"]


def _oversized_row():
    return {"key": "k1", "canonical_id": "AC-1", "bulk": "x" * 500}


def test_make_plan_before_begin_writes_raises_naming_begin_writes():
    # covers: KM-400b-5-vii
    # angle: failure
    db = _NeverBegun()
    with pytest.raises(RuntimeError, match="begin_writes") as caught:
        writes.make_plan(db, "nodes", AC, STATEMENT, [_oversized_row()])
    assert "publication_writes" in str(caught.value)
    # an ordinary row, which never touches the oversized list, is refused just the same
    with pytest.raises(RuntimeError, match="begin_writes"):
        writes.make_plan(db, "nodes", AC, STATEMENT, [{"key": "k2", "canonical_id": "AC-2"}])


def test_make_plan_on_a_fresh_backend_raises_naming_begin_writes():
    # covers: KM-400b-5-vii
    # angle: boundary
    backend = real_backend(error=None)  # the real Neo4jBackend, class defaults, no settings declared
    with pytest.raises(RuntimeError, match="begin_writes"):
        writes.make_plan(backend, "nodes", AC, STATEMENT, [{"key": "k2", "canonical_id": "AC-2"}])


def test_write_batches_before_begin_writes_raises_and_sends_nothing_to_the_store():
    # covers: KM-400b-5-vii
    # angle: failure
    db = _NeverBegun()
    plan = writes.Plan(AC, STATEMENT, [([{"key": "k1"}], 12)])
    with pytest.raises(RuntimeError, match="begin_writes") as caught:
        asyncio.run(writes.write_batches(db, "nodes", [plan], "R1:g33", lambda _rows, _actual: None))
    assert "publication_progress" in str(caught.value)
    assert db.statements == []


def test_with_retry_recording_a_retried_batch_before_begin_writes_raises_naming_begin_writes():
    # covers: KM-400b-5-vii
    # angle: failure
    db = _NeverBegun()
    calls = []

    async def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise make_error(TIME_LIMIT)
        return []

    descriptor = {"phase": "nodes", "label_or_kind": AC, "ordinal": 1, "total": 1, "rows": 1, "payload_bytes": 12}
    with pytest.raises(RuntimeError, match="begin_writes") as caught:
        asyncio.run(writes.with_retry(db, "nodes", descriptor, flaky))
    assert "publication_writes" in str(caught.value)
    assert len(calls) == 2  # the retry ran; only recording it needs the report


def test_with_retry_failure_of_a_batch_before_begin_writes_still_reports_the_store_failure():
    # covers: KM-400b-5-vii
    # angle: boundary
    db = _NeverBegun()

    async def unavailable():
        raise make_error("unavailable")

    descriptor = {"phase": "nodes", "label_or_kind": AC, "ordinal": 1, "total": 1, "rows": 1, "payload_bytes": 12}
    with pytest.raises(BackendUnavailable) as caught:
        asyncio.run(writes.with_retry(db, "nodes", descriptor, unavailable))
    assert caught.value.cause_class == "unavailable"
    assert db.publication_failure["attempts"] == 1


def test_activation_without_begin_writes_still_runs():
    # covers: KM-400b-5-vii
    # angle: boundary
    db = _NeverBegun()

    async def activate():
        return "activated"

    assert asyncio.run(writes.with_retry(db, "activation", None, activate)) == "activated"
