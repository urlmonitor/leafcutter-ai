"""Shared doubles and fixtures for the KM-400b-5-iii / -iv / -v / -vi writer tests.

Publication runs through the real ``neo4j_projection.publish`` and ``neo4j_domain_build.build``;
only the Neo4j driver is replaced by ``BatchDouble`` (a ``FailureDouble``, itself a ``StoreDouble``).
Snapshots are built with the real ``knowledge.contracts`` models; the CLI tests commit a real Git
repository whose AC YAML is written by ``yaml.safe_dump`` (see ``test_km_400b_2_ii``).

Contract these tests pin (the implementation must provide it):

Writer settings (one declared source, read from the backend object; the defaults apply when unset)
  * ``db.write_row_cap`` (default 250), ``db.write_payload_budget_bytes`` (default 2,000,000),
    ``db.write_max_attempts`` (default 3), ``db.write_retry_wait_seconds`` (tests set 0) and the
    existing ``db.query_timeout`` (seconds).

Batches (KM-400b-5-iii)
  * a batch is the ``UNWIND $rows`` node statement (``MERGE (n:<label> ...``) or the relationship
    statement (``MERGE (a)-[r:<TYPE> ...``). A batch closes at ``write_row_cap`` rows, or before the
    row that would take its serialized rows (JSON, ``json.dumps`` defaults) over the payload budget;
    a record larger than the budget is written alone.
  * batch descriptor: ``{phase: "nodes" | "relationships", label_or_kind, ordinal (1-based within
    the phase), total, rows, payload_bytes}``; ``label_or_kind`` is the entity kind for nodes
    (``AcceptanceCriterion``) and the upper-case edge type for relationships (``COVERED_BY``).
  * ``db.publication_writes`` = ``{row_cap, payload_budget_bytes, oversized_records: [{id, label,
    payload_bytes}], retried_batches: [{batch: descriptor, attempts, attempt_causes, max_attempts}]}``
    and the dict returned by ``cli_sync.sync`` carries the same dict under ``writes``.

Verification (KM-400b-5-iv)
  * every written row carries ``fingerprint`` (SHA-256 hex of the canonical serialization of its
    payload, ``native_verification.fingerprint(payload_json_text)``), stored in the
    ``content_fingerprint`` property of the node or relationship; the write statement's RETURN
    clause gives back only ``key`` and ``fingerprint`` per record (nodes and relationships alike);
    ``native_verification.verify_rows(expected_rows, stored_rows)`` raises ``ValueError`` naming the
    node (``canonical_id``, ``kind``) and both fingerprints with the words ``fingerprint mismatch``,
    or the node with the word ``missing`` (never ``mismatch``).

Retry and failure report (KM-400b-5-v, -vi)
  * a store error carries a structured ``cause_class`` attribute: ``time_limit``, ``read_only``,
    ``rule_violation`` or ``unavailable`` (set by ``Neo4jBackend._transaction`` from the driver's
    error classification, never from the message text). Only ``time_limit`` is retried, per batch
    and for the activation transaction, each attempt through a fresh ``db._run`` / ``db._transaction``.
  * ``db.publication_failure`` = ``{cause, time_limit_seconds (time_limit only; ``db.query_timeout``),
    phase: "nodes" | "relationships" | "activation", batch: descriptor | "not_applicable", attempts,
    attempt_causes, progress: {nodes: {written, total}, relationships: {written, total}}}``, and the
    propagated failure message states it (``writing nodes`` / ``writing relationships`` /
    ``activation``, ``batch <n> of <total>``, ``<k> rows``, ``after <k> attempts``,
    ``<limit> seconds``, ``<written> of <total> nodes``, ``no write batch`` for activation).
"""

import asyncio
import hashlib
import importlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from tests.knowledge.test_km_400b_2_ii import REPO_ID
from tests.knowledge.test_km_400b_5_i import FailureDouble

REPO_ROOT = Path(__file__).resolve().parents[2]
SHA = "a" * 40
GENERATION = "g33"
DEFAULT_ROW_CAP = 250
DEFAULT_BUDGET = 2_000_000
MARKER = "PAYLOAD-MARKER-7f3a9c"

_NODE_STATEMENT = re.compile(r"MERGE \(n:(\w+)")
_REL_STATEMENT = re.compile(r"MERGE \(a\)-\[r:(\w+)")
_FAULT_TEXT = {
    "time_limit": "backend unavailable: TransientError [Neo.TransientError.Transaction.Terminated]: terminated",
    "read_only": "store is read-only: write refused after timeout of the lock",
    "rule_violation": "backend unavailable: ConstraintError [Neo.ClientError.Schema.ConstraintValidationFailed]: uniqueness rule violated for key",
    "unavailable": "backend unavailable: ServiceUnavailable: connection lost",
}


def make_error(cause, message=None):
    """Return a BackendUnavailable carrying the structured ``cause_class`` the writer must read."""
    from knowledge.errors import BackendUnavailable

    error = BackendUnavailable(message or _FAULT_TEXT[cause])
    error.cause_class = cause
    return error


def row_bytes(row):
    """Serialized size of one row exactly as the batch tests measure it."""
    return len(json.dumps(row, sort_keys=True, default=str).encode("utf-8"))


def _kind_of_label():
    registry = importlib.import_module("knowledge.native_types.registry")
    return {physical: kind for kind, physical in registry.LABELS.items()}


class BatchDouble(FailureDouble):
    """FailureDouble that records every write batch and can inject faults per batch."""

    def __init__(
        self,
        write_row_cap=None,
        write_payload_budget_bytes=None,
        write_max_attempts=None,
        query_timeout=30,
        faults=None,
        activation_faults=None,
        store_on_fault=False,
        fault_message=None,
        alter_ids=(),
        omit_ids=(),
        alter_first=(),
        omit_last=(),
        **kwargs,
    ):
        kwargs.setdefault("active_generation", None)
        super().__init__(**kwargs)
        # Settings are set only when given, so an unset one leaves the implementation's default.
        if write_row_cap is not None:
            self.write_row_cap = write_row_cap
        if write_payload_budget_bytes is not None:
            self.write_payload_budget_bytes = write_payload_budget_bytes
        if write_max_attempts is not None:
            self.write_max_attempts = write_max_attempts
        self.write_retry_wait_seconds = 0
        self.query_timeout = query_timeout
        self.faults = dict(faults or {})  # {(phase, ordinal): [cause, ...]} one cause per attempt
        self.activation_faults = list(activation_faults or [])
        self.store_on_fault = store_on_fault
        self.fault_message = fault_message
        self.alter_ids = set(alter_ids)
        self.omit_ids = set(omit_ids)
        self.alter_first = set(alter_first)  # {(phase, ordinal)}: first stored row reads back changed
        self.omit_last = set(omit_last)  # {(phase, ordinal)}: last stored row is absent on read-back
        self.batch_log = []
        self.phase_batches = {"nodes": [], "relationships": []}
        self.transactions = []
        self._kinds = _kind_of_label()

    # -- classification -----------------------------------------------------------------------
    def _identify(self, statement):
        match = _NODE_STATEMENT.search(statement)
        if match and "UNWIND $rows" in statement:
            return "nodes", self._kinds.get(match.group(1), match.group(1))
        match = _REL_STATEMENT.search(statement)
        if match and "UNWIND $rows" in statement:
            return "relationships", match.group(1)
        return None

    async def _run(self, statement, params=None, write=False, **ignored):
        found = self._identify(statement)
        if found is None:
            return await super()._run(statement, params, write, **ignored)
        phase, kind = found
        rows = list((params or {}).get("rows", []))
        first = rows[0]["key"] if rows else None
        seen = self.phase_batches[phase]
        if first not in seen:
            seen.append(first)
        ordinal = seen.index(first) + 1
        attempt = 1 + sum(1 for e in self.batch_log if e["phase"] == phase and e["ordinal"] == ordinal)
        entry = {
            "phase": phase,
            "kind": kind,
            "ordinal": ordinal,
            "attempt": attempt,
            "rows": len(rows),
            "bytes": sum(row_bytes(r) for r in rows),
            "keys": [r["key"] for r in rows],
            "ids": [r.get("canonical_id") for r in rows],
            "sent_fp": {r["key"]: r.get("fingerprint") for r in rows},
            "statement": statement,
            "faulted": False,
            "returned": None,
        }
        self.batch_log.append(entry)
        plan = self.faults.get((phase, ordinal)) or []
        if attempt <= len(plan):
            entry["faulted"] = True
            if self.store_on_fault:
                await super()._run(statement, params, write, **ignored)
            raise make_error(plan[attempt - 1], self.fault_message)
        stored = await super()._run(statement, params, write, **ignored)
        entry["returned"] = self._shape(statement, entry, rows, stored)
        return entry["returned"]

    def _shape(self, statement, entry, rows, stored):
        tail = statement.split("RETURN", 1)[1] if "RETURN" in statement else ""
        entry["return_clause"] = tail.strip()
        if "fingerprint" not in tail or "properties(" in tail:
            return stored
        slot = (entry["phase"], entry["ordinal"])
        out = []
        for index, row in enumerate(rows):
            if entry["phase"] == "relationships" and row["key"] not in self.relationships:
                continue  # the store lost it
            if row.get("canonical_id") in self.omit_ids:
                continue
            if slot in self.omit_last and index == len(rows) - 1:
                continue
            fingerprint = row.get("fingerprint")
            if row.get("canonical_id") in self.alter_ids or (slot in self.alter_first and index == 0):
                fingerprint = hashlib.sha256(((fingerprint or "") + "!").encode()).hexdigest()
            out.append({"key": row["key"], "fingerprint": fingerprint})
        return out

    async def _transaction(self, callback, write=False, **ignored):
        self.transactions.append(write)
        if write and self.activation_faults:
            raise make_error(self.activation_faults.pop(0), self.fault_message)
        return await super()._transaction(callback, write, **ignored)

    # -- views --------------------------------------------------------------------------------
    def batches(self, phase, completed_only=True):
        return [
            e
            for e in self.batch_log
            if e["phase"] == phase and not (completed_only and e["faulted"])
        ]

    def attempts(self, phase, ordinal):
        return [e for e in self.batch_log if e["phase"] == phase and e["ordinal"] == ordinal]

    def total(self, phase):
        return len(self.phase_batches[phase])


class Outcome:
    """What one publication did: the double, the snapshot, the return value and any failure."""

    def __init__(self, store, snapshot, result, error):
        self.store = store
        self.snapshot = snapshot
        self.result = result
        self.error = error

    @property
    def ok(self):
        return self.error is None and self.result is True

    @property
    def writes(self):
        return getattr(self.store, "publication_writes", None)

    @property
    def failure(self):
        return getattr(self.store, "publication_failure", None)

    @property
    def key(self):
        return self.store.own_key_for(self.snapshot)


def run_publish(store, snapshot):
    """Run the real publish against the double; capture rather than raise a publication failure."""
    projection = importlib.import_module("knowledge.adapters.neo4j_projection")
    try:
        result = asyncio.run(projection.publish(store, snapshot, None))
    except Exception as error:  # noqa: BLE001 -- the tests inspect whatever the publication raised
        return Outcome(store, snapshot, None, error)
    return Outcome(store, snapshot, result, None)


# -- snapshot building -------------------------------------------------------------------------
def node_id(kind, index):
    return f"{kind}:{index:05d}"


def make_entity(canonical_id, kind, bulk=0, marker="", repo=REPO_ID):
    contracts = importlib.import_module("knowledge.contracts")
    blob = marker + "x" * bulk
    return contracts.Entity(
        canonical_id=canonical_id,
        kind=kind,
        title=canonical_id,
        source=contracts.SourceReference(
            repository_id=repo,
            source_sha=SHA,
            path="docs/" + canonical_id.replace(":", "-") + ".txt",
            content_hash="h",
        ),
        properties={"_native_blob": blob} if blob else {},
    )


def make_edge(source_id, target_id, edge_type, locator, bulk=0, marker="", repo=REPO_ID):
    contracts = importlib.import_module("knowledge.contracts")
    source = None
    if bulk or marker:
        source = contracts.SourceReference(
            repository_id=repo, source_sha=SHA, path="docs/edge.txt", locator=marker + "x" * bulk
        )
    return contracts.Relation(
        source=source, source_id=source_id, target_id=target_id, edge_type=edge_type, locator=locator
    )


def make_snapshot(nodes, edges=(), repo=REPO_ID, generation=GENERATION):
    contracts = importlib.import_module("knowledge.contracts")
    return contracts.ProjectionSnapshot(
        repository_id=repo, source_sha=SHA, generation_id=generation, nodes=list(nodes), edges=list(edges)
    )


_OVERHEAD = {}


def bulk_for(target_row_bytes):
    """Blob size that makes one node row serialize to about ``target_row_bytes``."""
    if "value" not in _OVERHEAD:
        build = importlib.import_module("knowledge.adapters.neo4j_domain_build").build
        backend = importlib.import_module("knowledge.adapters.neo4j_backend")
        probe = make_snapshot([make_entity(node_id("AcceptanceCriterion", 0), "AcceptanceCriterion")])
        store = BatchDouble()
        asyncio.run(build(store, probe, backend.scope_key(REPO_ID, GENERATION)))
        _OVERHEAD["value"] = store.batch_log[0]["bytes"]
    return max(0, target_row_bytes - _OVERHEAD["value"])


def graded_snapshot(ac_count, test_count, ac_bulk=20_000, test_bulk=20_000, covered_by=0, depends_on=0,
                    edge_bulk=3_000, marker=""):
    """AcceptanceCriterion and Test nodes with covered_by (AC to Test) and depends_on edges."""
    nodes = [
        make_entity(node_id("AcceptanceCriterion", i), "AcceptanceCriterion", ac_bulk, marker if i == 0 else "")
        for i in range(ac_count)
    ] + [make_entity(node_id("Test", i), "Test", test_bulk) for i in range(test_count)]
    edges = [
        make_edge(
            node_id("AcceptanceCriterion", i % ac_count),
            node_id("Test", (i * 7) % test_count),
            "covered_by",
            f"l{i:06d}",
            edge_bulk,
            marker if i == 0 else "",
        )
        for i in range(covered_by)
    ] + [
        make_edge(
            node_id("AcceptanceCriterion", i),
            node_id("AcceptanceCriterion", i + 1),
            "depends_on",
            f"d{i:06d}",
            edge_bulk,
        )
        for i in range(depends_on)
    ]
    return make_snapshot(nodes, edges)


def retry_snapshot():
    """345 AC nodes and 110 Test nodes: with a row cap of 10, 35 + 11 = 46 node batches.

    1,150 covered_by and 10 depends_on edges: with a row cap of 10, 115 + 1 = 116 relationship
    batches, covered_by first, so batch 80 of 116 is COVERED_BY.
    """
    return graded_snapshot(345, 110, covered_by=1150, depends_on=10)


def retry_store(**kwargs):
    kwargs.setdefault("write_row_cap", 10)
    kwargs.setdefault("write_max_attempts", 3)
    return BatchDouble(**kwargs)


# -- real backend classification ---------------------------------------------------------------
class _Session:
    def __init__(self, error):
        self.error = error

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute_write(self, _work):
        raise self.error

    execute_read = execute_write


class _Driver:
    """Driver double: ``connect_error`` fails the connect step, ``error`` the query step."""

    def __init__(self, error, connect_error=None):
        self.error = error
        self.connect_error = connect_error
        self.connects = 0
        self.sessions = 0

    def verify_connectivity(self):
        self.connects += 1
        if self.connect_error is not None:
            raise self.connect_error

    def session(self, database=None):
        self.sessions += 1
        return _Session(self.error)

    def close(self):
        return None


def real_backend(error, query_timeout=45, connect_error=None):
    """A real ``Neo4jBackend`` whose driver is replaced by ``_Driver`` (no network)."""
    module = importlib.import_module("knowledge.adapters.neo4j_backend")
    backend = module.Neo4jBackend("bolt://127.0.0.1:1", "u", "p", query_timeout=query_timeout)
    backend.driver.close()
    backend._connected = connect_error is None
    backend.write_retry_wait_seconds = 0
    backend.driver = _Driver(error, connect_error)
    return backend


def backend_failure(code, query_timeout=45, error=None, connect_error=None, deadline_seconds=None):
    """Run the real ``Neo4jBackend._transaction``; the server answers ``code`` unless ``error`` is given."""
    import time

    from neo4j.exceptions import Neo4jError

    from knowledge.deadlines import deadline
    from knowledge.errors import BackendUnavailable

    if error is None and code is not None:
        error = Neo4jError._hydrate_neo4j(code=code, message="server said no")
    backend = real_backend(error, query_timeout, connect_error)

    async def attempt():
        if deadline_seconds is not None:
            deadline.set(time.monotonic() + deadline_seconds)
        return await backend._transaction(lambda tx: [], True)

    try:
        asyncio.run(attempt())
    except BackendUnavailable as failure:
        return backend, failure
    return backend, None


# -- the standalone command --------------------------------------------------------------------
_DRIVER = """
import json, sys
from knowledge import cli_sync
from tests.knowledge._km_400b_5_writes_support import BatchDouble

store = BatchDouble(**%(kwargs)r)
store.source_sha = %(sha)r
store.scope_lines = %(scope)r
cli_sync.writer_backend = lambda root=None: store
sys.argv = %(argv)r
from knowledge.__main__ import main

try:
    code = main()
except SystemExit as exit_:
    code = exit_.code
log = [
    {k: e[k] for k in ("phase", "kind", "ordinal", "attempt", "rows", "bytes", "faulted", "sent_fp", "ids")}
    for e in store.batch_log
]
extra = {}
if %(altered)r:
    extra["altered"] = [
        {"id": i, "key": k, "sent": e["sent_fp"][k], "stored": r.get("fingerprint")}
        for e in store.batch_log
        if e["returned"]
        for r in e["returned"]
        for i, k in zip(e["ids"], e["keys"])
        if i in %(altered)r and k == r["key"]
    ]
print(json.dumps({"batch_log": log, "totals": {p: len(v) for p, v in store.phase_batches.items()}, **extra}), file=sys.stderr)
raise SystemExit(code or 0)
"""


def run_sync_cli(tmp_path, kwargs, altered=()):
    """`python -m knowledge sync --root <repo>` in a fresh process; only the driver is replaced.

    Returns (completed process, loaded snapshot, parsed stdout JSON or None, stderr JSON lines).
    """
    from tests.knowledge.test_km_400b_2_i import _load
    from tests.knowledge.test_km_400b_2_ii import TARGETS, _commit_repository
    from tests.knowledge.test_km_400b_5_i import store_scope_lines

    sha = _commit_repository(tmp_path, list(TARGETS))
    loaded = _load(tmp_path, sha)
    env = {k: v for k, v in os.environ.items() if not k.startswith("LEAFCUTTER_NEO4J")}
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    argv = ["knowledge", "sync", "--root", str(tmp_path), "--repository-id", REPO_ID, "--revision", sha]
    code = _DRIVER % {
        "kwargs": kwargs,
        "sha": loaded.source_sha,
        "scope": store_scope_lines(loaded),
        "argv": argv,
        "altered": list(altered),
    }
    done = subprocess.run(
        [sys.executable, "-c", code], cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=180
    )
    lines = [json.loads(line) for line in done.stderr.splitlines() if line.startswith("{")]
    out = [line for line in done.stdout.strip().splitlines() if line.startswith("{")]
    return done, loaded, (json.loads(out[-1]) if out else None), lines
