"""Shared harness for the KM-400d-4 family tests (no tests live here).

Every scenario runs the real retrieval path in a FRESH subprocess: real argv, real
``knowledge.__main__.main``, real ``KnowledgeService`` and the real ``Neo4jBackend._transaction``
worker thread. Only two things are replaced, by a prelude module written into the scratch directory:

* ``socket.getaddrinfo`` is a recording fake resolver whose delays are ``time.sleep`` (not
  cancellable, exactly like a stalled system resolver);
* ``neo4j.GraphDatabase`` is a fake driver whose session opens by looking up the configured server
  name (and optionally a different reader name) from the transaction's worker thread, then spends the
  connect delay (first connection only: a connection pool connects once), and whose queries sleep per a
  script indexed by query number. Like neo4j 6.0.3 it is LAZY: ``session()`` and ``__enter__`` do
  nothing; the lookups and the connect delay happen on ``verify_connectivity()`` or on the first
  ``execute_read``/``execute_write``.

Behaviour is configured through the ``KM_FAKE`` JSON environment variable (see ``fake``).
"""

import json
import os
import site
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVER = "graph.example.test"
READER = "reader.example.test"
PORT = 7687
BLOCK = 20.0  # a delay no test waits out: the call is abandoned, never joined
ENTITY_ID = "KM-400a-1"

_PRELUDE = '''\
import json, os, socket, sys, threading, time

CFG = json.loads(os.environ["KM_FAKE"])
RESOLVER_RECORD = os.environ["KM_RESOLVER_RECORD"]
DRIVER_RECORD = os.environ["KM_DRIVER_RECORD"]
ANSWER = {"ip": "192.0.2.10"}
SERVER = "graph.example.test"
READER = "reader.example.test"


def _append(path, payload):
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\\n")


def fake_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    _append(RESOLVER_RECORD, {"name": host, "port": port, "family": int(family),
                              "thread": threading.current_thread().name, "t": time.time()})
    v4 = int(family) == int(socket.AF_INET)
    time.sleep(CFG["v4_delay"] if v4 else CFG["any_delay"])
    if v4 and host in CFG.get("v4_fail", []):
        raise socket.gaierror(socket.EAI_NONAME, "no such address")
    if not v4 and CFG.get("any_answer") == "ipv6":
        return [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2001:db8::1", port, 0, 0))]
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ANSWER["ip"], port))]


socket.getaddrinfo = fake_getaddrinfo

import neo4j  # noqa: E402

_STATE = {"tx_runs": 0, "connected": False}
_LOCK = threading.Lock()


def _manifest():
    return {"repository_id": "leafcutter", "source_sha": "a" * 40, "generation_id": "g1",
            "mapper_version": "1", "node_count": 1, "edge_count": 0, "diagnostics": "[]",
            "supported_fields": "{}", "supported_kinds": [], "supported_relationships": []}


def _payload():
    from knowledge.contracts import Entity, SourceReference

    return Entity(
        canonical_id=os.environ.get("KM_ENTITY_ID", "KM-400a-1"), kind="AcceptanceCriterion",
        title="t", summary="Approved explanation",
        source=SourceReference(repository_id="leafcutter", source_sha="a" * 40,
                               path="docs/ac.yaml", locator="/criteria", content_hash="h"),
    ).model_dump_json()


class _Record:
    def __init__(self, row):
        self._row = row

    def data(self):
        return self._row

    def __getitem__(self, key):
        return self._row[key]


class _Tx:
    def run(self, statement, parameters=None):
        with _LOCK:
            index = _STATE["tx_runs"]
            _STATE["tx_runs"] += 1
        script = CFG.get("query_script", [])
        time.sleep(script[index] if index < len(script) else CFG.get("query_default", 0))
        _append(DRIVER_RECORD, {"event": "query", "index": index})
        if "(r:Repository" in statement or "(g:Snapshot" in statement:
            return [_Record({"g": _manifest()})]
        if "r.payload AS relation" in statement:
            return []
        if "n.payload AS payload" in statement:
            return [_Record({"payload": _payload()})]
        return []


def _acquire_connection():
    """Like the real driver's pool: lookups happen when a connection is acquired, the TCP/TLS
    connect delay only for the first connection ever made."""
    names = [SERVER] + ([READER] if CFG.get("lookup_reader") else [])
    for name in names:
        try:
            found = socket.getaddrinfo(name, 7687, 0, socket.SOCK_STREAM)
            _append(DRIVER_RECORD, {"event": "lookup", "name": name,
                                    "addresses": [item[4][0] for item in found]})
        except OSError as error:
            _append(DRIVER_RECORD, {"event": "lookup_error", "name": name, "error": repr(error)})
            raise
    with _LOCK:
        first = not _STATE["connected"]
        refused = CFG.get("refuse_first_connect") and not _STATE.get("refused")
        if refused:
            _STATE["refused"] = True
        else:
            _STATE["connected"] = True
    if refused:
        raise neo4j.exceptions.ServiceUnavailable("connection refused")
    if first:
        time.sleep(CFG.get("connect_delay", 0))


class _Session:
    """Lazy like neo4j 6.0.3: creating or entering a session touches nothing; the first
    execute_read/execute_write acquires the connection."""

    def __init__(self, database):
        self.database = database

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        time.sleep(CFG.get("close_delay", 0))
        return False

    def execute_read(self, work, *args, **kwargs):
        _acquire_connection()
        return work(_Tx(), *args, **kwargs)

    execute_write = execute_read


class _Driver:
    def session(self, database=None, **kwargs):
        return _Session(database)

    def verify_connectivity(self, **config):
        _acquire_connection()

    def close(self):
        time.sleep(CFG.get("driver_close_delay", 0))


class _GraphDatabase:
    @staticmethod
    def driver(uri, **kwargs):
        _append(DRIVER_RECORD, {"event": "driver", "uri": uri})
        return _Driver()


neo4j.GraphDatabase = _GraphDatabase
'''

_ENTRY = '''\
import json, os, sys, time

import km_fake_prelude  # noqa: F401  (installs the fake resolver and driver)

time.sleep(float(km_fake_prelude.CFG.get("start_sleep", 0)))
import knowledge.service as service

_original = service.KnowledgeService.retrieve


async def _retrieve(self, request):
    km_fake_prelude._append(os.environ["KM_START_RECORD"], {"retrieval_start": time.time()})
    return await _original(self, request)


service.KnowledgeService.retrieve = _retrieve

from knowledge.__main__ import main

sys.exit(main())
'''

_TWO_REQUESTS = '''\
import asyncio, json, os, sys

import km_fake_prelude  # noqa: F401

from knowledge.config import KnowledgeConfig, build_retriever
from knowledge.contracts import KnowledgeRetrievalRequest


async def go(count):
    retriever = build_retriever(KnowledgeConfig(backend="neo4j"))
    outs = []
    for number in range(count):
        request = KnowledgeRetrievalRequest.model_validate_json(open(sys.argv[2]).read())
        request = request.model_copy(update={"request_id": "request-%d" % number})
        outs.append((await retriever.retrieve(request)).model_dump(mode="json"))
    await retriever.close()
    return outs


print(json.dumps(asyncio.run(go(int(sys.argv[1])))))
'''

_OUTSIDE = '''\
import asyncio, json, socket, sys, threading, time

import km_fake_prelude as p

from knowledge.adapters.neo4j_backend import Neo4jBackend

backend = Neo4jBackend("neo4j+s://%s" , "user", "pw")
asyncio.run(backend._run("MATCH (r:Repository) RETURN g"))
inflight = threading.Thread(
    target=lambda: asyncio.run(backend._run("MATCH (g:Snapshot) RETURN g")), name="inflight")
inflight.start()
time.sleep(0.2)
p._append(p.RESOLVER_RECORD, {"mark": "outside-start"})
calls = {}


def outside(tag):
    calls[tag] = {
        "unrelated": [item[4][0] for item in socket.getaddrinfo("unrelated.example.test", 80, 0)],
        "server": [item[4][0] for item in socket.getaddrinfo("%s", 7687, 0)],
    }


second = threading.Thread(target=outside, args=("second",), name="outside-thread")
second.start()
second.join()
outside("main")
inflight.join()
before = len(open(p.RESOLVER_RECORD).read().splitlines())
p.ANSWER["ip"] = "198.51.100.9"
again = [item[4][0] for item in socket.getaddrinfo("%s", 7687, 0, socket.SOCK_STREAM)]
after = len(open(p.RESOLVER_RECORD).read().splitlines())
print(json.dumps({"calls": calls, "again": again, "resolver_calls_added": after - before}))
''' % (SERVER, SERVER, SERVER)


_THIRD_PARTY = '''\
import asyncio, json, socket

import km_fake_prelude as p

from knowledge.adapters.neo4j_backend import Neo4jBackend

backend = Neo4jBackend("neo4j+s://graph.example.test", "user", "pw")
asyncio.run(backend._run("MATCH (r:Repository) RETURN g"))  # the adapter installs its policy here

previous = socket.getaddrinfo
wrapped_calls = []


def third_party(*args, **kwargs):  # e.g. a tracing or test library wrapping the resolver afterwards
    wrapped_calls.append(args[0])
    return previous(*args, **kwargs)


socket.getaddrinfo = third_party
out = {}
try:
    asyncio.run(backend._run("MATCH (g:Snapshot) RETURN g"))
    out["adapter"] = "ok"
except RecursionError:
    out["adapter"] = "recursion"
p._append(p.RESOLVER_RECORD, {"mark": "outside-start"})
try:
    socket.getaddrinfo("unrelated.example.test", 80, 0)
    socket.getaddrinfo("unrelated.example.test", 80, socket.AF_INET6)
    out["outside"] = "ok"
except RecursionError:
    out["outside"] = "recursion"
out["wrapper_saw_outside"] = wrapped_calls.count("unrelated.example.test")
print(json.dumps(out))
'''


def fake(**overrides):
    """Default fake: instant lookups (either family), no connect or query delay."""
    config = {"v4_delay": 0.0, "any_delay": 0.0, "connect_delay": 0.0, "query_script": []}
    config.update(overrides)
    return config


def _write_support_files(scratch):
    (scratch / "km_fake_prelude.py").write_text(_PRELUDE, encoding="utf-8")
    for name, text in (("entry.py", _ENTRY), ("two_requests.py", _TWO_REQUESTS),
                       ("outside.py", _OUTSIDE), ("third_party.py", _THIRD_PARTY)):
        (scratch / name).write_text(text, encoding="utf-8")
    (scratch / ".env").write_text("", encoding="utf-8")
    (scratch / "home").mkdir(exist_ok=True)


def _env(scratch, config, extra_env):
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(scratch / "home"),  # a scratch home: nothing may be stored in the real one
        "PYTHONUSERBASE": site.getuserbase(),  # keeps the real user site-packages importable
        "PYTHONPATH": os.pathsep.join([str(REPO_ROOT), str(scratch)]),
        "LEAFCUTTER_ENV_FILE": str(scratch / ".env"),
        "LEAFCUTTER_NEO4J_URI": f"neo4j+s://{SERVER}",
        "LEAFCUTTER_NEO4J_USERNAME": "user",
        "LEAFCUTTER_NEO4J_PASSWORD": "pw",
        "KM_FAKE": json.dumps(config),
        "KM_RESOLVER_RECORD": str(scratch / "resolver.jsonl"),
        "KM_DRIVER_RECORD": str(scratch / "driver.jsonl"),
        "KM_START_RECORD": str(scratch / "start.jsonl"),
    }
    for name in ("TMPDIR", "TEMP", "TMP"):
        env[name] = os.environ.get(name, str(scratch))
    env.update(extra_env or {})
    return env


def write_request(scratch, deadline_ms=10000, operation="get_entities", arguments=None, extra=None):
    path = scratch / "request.json"
    path.write_text(json.dumps({
        "request_id": "request-0", "repository_id": "leafcutter", "operation": operation,
        "arguments": arguments or {"entity_ids": [ENTITY_ID]},
        "budget": {"deadline_ms": deadline_ms}, **(extra or {}),
    }), encoding="utf-8")
    return path


def _lines(path):
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


class Run:
    """One finished subprocess: parsed answer, exit facts and the recorded lookups."""

    def __init__(self, scratch, completed, returned_at):
        self.completed = completed
        self.returncode = completed.returncode
        self.stdout = completed.stdout
        self.stderr = completed.stderr
        self.returned_at = returned_at
        self.resolver = [r for r in _lines(scratch / "resolver.jsonl") if "name" in r]
        self.driver = _lines(scratch / "driver.jsonl")
        starts = _lines(scratch / "start.jsonl")
        self.retrieval_start = starts[0]["retrieval_start"] if starts else None

    @property
    def answer(self):
        try:
            return json.loads(self.stdout)
        except ValueError:
            pytest.fail(f"stdout is not one JSON document: {self.stdout!r} stderr={self.stderr[-500:]!r}")

    @property
    def stats(self):
        return self.answer["stats"]


def _run(scratch, argv, config, extra_env, timeout):
    _write_support_files(scratch)
    started = time.time()
    try:
        completed = subprocess.run(argv, env=_env(scratch, config, extra_env), cwd=str(scratch),
                                   capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        pytest.fail(f"the process did not exit within {timeout} s (a blocked call held it)")
    return Run(scratch, completed, time.time()), started


def run_retrieve(scratch, config=None, deadline_ms=10000, extra_env=None, timeout=8,
                 operation="get_entities", arguments=None, request_extra=None):
    """Run ``python -m knowledge retrieve --backend neo4j`` through the real main()."""
    config = config or fake()
    request = write_request(scratch, deadline_ms, operation, arguments, request_extra)
    argv = [sys.executable, str(scratch / "entry.py"), "retrieve", "--backend", "neo4j",
            "--request", str(request)]
    run, _ = _run(scratch, argv, config, extra_env, timeout)
    return run


def run_requests(scratch, count, config=None, extra_env=None, timeout=30):
    """Build one retriever through build_retriever and run ``count`` requests; returns the results."""
    request = write_request(scratch)
    argv = [sys.executable, str(scratch / "two_requests.py"), str(count), str(request)]
    run, _ = _run(scratch, argv, config or fake(), extra_env, timeout)
    if run.returncode != 0:
        pytest.fail(f"the child process failed: {run.stderr[-800:]}")
    return json.loads(run.stdout), run


def run_outside_lookups(scratch, config=None, timeout=30):
    """Run the adapter-level child: one adapter transaction, then lookups made outside the adapter."""
    _write_support_files(scratch)
    config = config or fake(query_script=[0.0, 1.5])
    completed = subprocess.run([sys.executable, str(scratch / "outside.py")],
                               env=_env(scratch, config, None), cwd=str(scratch),
                               capture_output=True, text=True, timeout=timeout)
    if completed.returncode != 0:
        pytest.fail(f"the child process failed: {completed.stderr[-800:]}")
    records = _lines(scratch / "resolver.jsonl")
    result = json.loads(completed.stdout)
    marker = next(i for i, record in enumerate(records) if record.get("mark") == "outside-start")
    # The child's closing "again" lookup proves nothing is remembered; it is not one of the
    # outside lookups under test, so cut it off before filtering.
    end = len(records) - result["resolver_calls_added"]
    outside = [r for r in records[marker + 1:end]
               if r.get("thread") in {"MainThread", "outside-thread"}]
    return result, outside


def run_third_party_wrap(scratch, timeout=30):
    """Run the child where a third party wraps socket.getaddrinfo after the adapter's policy was
    installed; returns the child's verdict and the resolver calls made after the outside marker."""
    _write_support_files(scratch)
    completed = subprocess.run([sys.executable, str(scratch / "third_party.py")],
                               env=_env(scratch, fake(), None), cwd=str(scratch),
                               capture_output=True, text=True, timeout=timeout)
    if completed.returncode != 0:
        pytest.fail(f"the child process failed: {completed.stderr[-800:]}")
    records = _lines(scratch / "resolver.jsonl")
    marker = next(i for i, record in enumerate(records) if record.get("mark") == "outside-start")
    return json.loads(completed.stdout), records[marker + 1:]


def lookups_of(run, name):
    return [r for r in run.resolver if r["name"] == name]


def server_lookups(run):
    return [r for r in run.resolver if r["name"] == SERVER]


def tree(root):
    return sorted(str(p.relative_to(root)) for p in Path(root).rglob("*"))
