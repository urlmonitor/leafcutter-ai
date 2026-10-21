"""KM-400f-3: the setup-preflight and retry cases of the capacity gate.

Split out of ``tests.knowledge.test_km_400f_3`` to keep both files under the size limit. This module holds
the cases where ``cli_sync.run`` calls ``backend.setup()`` against a read-only store (the read-only
capacity condition must still surface with measured usage) and where a rerun's already-stored generation
must, or must not, be counted again. The shared doubles and helpers are imported from the main module.
"""

import asyncio
import importlib

import pytest

from tests.knowledge.test_km_400b_2_ii import REPO_ID, TARGETS, _commit_repository
from tests.knowledge.test_km_400f_3 import (
    READ_ONLY_REJECTION,
    REFUSE_NODES,
    CapacityDouble,
    _ceiling,
    _flat,
    _prepare,
    _sync,
)


class SetupWritesDouble(CapacityDouble):
    """CapacityDouble whose setup() issues the schema write the real backend issues (CREATE CONSTRAINT)."""

    async def setup(self):
        await self._run("CREATE CONSTRAINT km_key IF NOT EXISTS FOR (n:Snapshot) REQUIRE n.key IS UNIQUE", {}, True)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"access": "read-only", "write_rejection": READ_ONLY_REJECTION},  # SHOW DATABASE answers
        {"show_refused": True, "write_rejection": READ_ONLY_REJECTION},  # SHOW refused: classify setup's rejection
    ],
    ids=["preflight_via_show_database", "setup_rejection_classified"],
)
def test_cli_run_reports_read_only_with_usage_not_a_raw_setup_failure(tmp_path, monkeypatch, kwargs):
    # covers: KM-400f-3
    # angle: failure
    # H-1: cli_sync.run calls backend.setup() (schema writes) before sync(); against a latched store that
    # must still surface the read-only capacity condition with measured usage, not a raw rejection.
    from argparse import Namespace

    from knowledge.errors import BackendUnavailable

    cli_sync = importlib.import_module("knowledge.cli_sync")
    sha = _commit_repository(tmp_path, list(TARGETS))
    store = SetupWritesDouble((20_000, 50_000), **kwargs)
    monkeypatch.setattr(cli_sync, "writer_backend", lambda root=None: store)
    args = Namespace(command="sync", root=str(tmp_path), repository_id=REPO_ID, revision=sha, surfaces=None,
                     retention_max_generations=None, retention_min_age_seconds=None, capacity_max_nodes=None,
                     capacity_max_relationships=None, capacity_refuse_percent=None, capacity_warn_percent=None)

    with pytest.raises(BackendUnavailable) as caught:
        asyncio.run(cli_sync.run(args))

    message = _flat(caught.value)
    assert "read-only" in message and "20000" in message and "50000" in message, message
    assert "capacity condition" in message and "0 generations reclaimed" in message
    assert store.publication_capacity["verdict"] == "read_only" and store.publication_capacity["satisfied"] is False
    if "access" in kwargs:
        assert store.writes == []  # refused before setup's schema writes
    else:
        assert isinstance(caught.value.__cause__, BackendUnavailable)  # original rejection chained
        assert "ForbiddenOnReadOnlyDatabase" in str(caught.value.__cause__)


@pytest.mark.parametrize("status", ["ready", "validated"])
def test_existing_generation_is_not_double_counted_on_retry(tmp_path, status):
    # covers: KM-400f-3
    # angle: boundary
    # H-2: a rerun / resume whose generation is already stored has its records inside the measured usage.
    # Usage alone sits exactly at the refuse threshold (not over); counting the snapshot again would refuse.
    import hashlib

    sha, loaded, store = _prepare(tmp_path, (REFUSE_NODES, 50_000))
    key = store.scope_key(REPO_ID, loaded.generation_id)
    store._seed(REPO_ID, loaded.generation_id, status, store.t0, 0.0)
    store.nodes = {k: v for k, v in store.nodes.items() if v != key}  # the record exists; a rebuild starts clean
    store.relationships = {k: v for k, v in store.relationships.items() if v != key}
    store.snapshots[key]["digest"] = hashlib.sha256(loaded.model_dump_json().encode()).hexdigest()
    n = len(loaded.nodes)
    assert n >= 1  # control: counting the snapshot on top WOULD exceed the refuse threshold

    result = _sync(tmp_path, sha, store, _ceiling())

    cap = result["capacity"]
    assert result["published"] is True and cap["verdict"] == "warning"
    assert cap["snapshot_already_stored"] is True and "already stored" in cap["statement"]
    assert cap["nodes"]["snapshot"] == 0 and cap["relationships"]["snapshot"] == 0  # what will be ADDED
    assert cap["nodes"]["usage"] == REFUSE_NODES and cap["nodes"]["shortfall"] == 0


def test_partially_written_generation_is_still_counted_in_full(tmp_path):
    # covers: KM-400f-3
    # angle: discrimination
    # Wrong version: skip the snapshot whenever a generation record exists. A building record is partial.
    import hashlib

    sha, loaded, store = _prepare(tmp_path, (REFUSE_NODES, 50_000))
    key = store.scope_key(REPO_ID, loaded.generation_id)
    store._seed(REPO_ID, loaded.generation_id, "building", store.t0, 0.0)
    store.snapshots[key]["digest"] = hashlib.sha256(loaded.model_dump_json().encode()).hexdigest()

    with pytest.raises(ValueError):
        _sync(tmp_path, sha, store, _ceiling())

    cap = store.publication_capacity
    assert cap["verdict"] == "refused" and cap["snapshot_already_stored"] is False
    assert cap["nodes"]["snapshot"] == len(loaded.nodes) and store.writes == []
