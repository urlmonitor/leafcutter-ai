"""KM-400b-2-i: identical relationships collapse to one before any write, with a reported source.

The fixture repository is a real Git commit whose AC YAML is produced by yaml.safe_dump and loaded
through the real snapshot loader; publication runs through the real neo4j_projection.publish with
a database double that records every statement it is handed.
"""

import asyncio
import importlib
import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
AC_PATH = "docs/acs/criterion.yaml"
TARGET = "tests/test_widget.py"


def _git(root, *args, input=None):
    return subprocess.run(
        ["git", "-C", str(root), *args], input=input, text=True, capture_output=True, check=True
    ).stdout.strip()


def _commit(root):
    _git(root, "add", ".")
    tree = _git(root, "write-tree")
    sha = _git(
        root,
        "-c", "user.name=Fixture",
        "-c", "user.email=fixture@example.invalid",
        "commit-tree", tree,
        input="synthetic test fixture\n",
    )
    _git(root, "update-ref", "refs/heads/main", sha)
    return sha


def _repository(root, implemented_by):
    """Commit a repository whose single AC lists ``implemented_by`` (written by yaml.safe_dump)."""
    _git(root, "init", "-b", "main")
    (root / "config").mkdir()
    (root / "docs/acs").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / TARGET).write_text("def test_widget():\n    pass\n", encoding="utf-8")
    surfaces = {
        "acs": {
            "path": "docs/acs/",
            "edge_fields": ["components", "depends_on", "covered_by", "implemented_by"],
            "file_path_fields": ["covered_by", "implemented_by"],
        },
        "components": {"path": "docs/components.json", "edge_fields": []},
    }
    (root / "config/paths.json").write_text(json.dumps({"surfaces": surfaces}), encoding="utf-8")
    (root / "docs/components.json").write_text(
        json.dumps({"components": {"knowledge_management": {"name": "Knowledge"}}}),
        encoding="utf-8",
    )
    record = {
        "id": "KM-FIX-1",
        "title": "Original title",
        "component": "knowledge-management",
        "status": "active",
        "readiness": "approved",
        "priority": "medium",
        "criteria": "Given a snapshot\nWhen indexed\nThen its identity is preserved",
        "components": ["knowledge_management"],
        "depends_on": [],
        "implemented_by": implemented_by,
    }
    (root / AC_PATH).write_text(yaml.safe_dump(record), encoding="utf-8")
    return _commit(root)


def _load(root, sha):
    loader = importlib.import_module("knowledge.projection.canonical_loader")
    return loader.load_snapshot(root, "repo", sha)


def _implemented_by(snapshot):
    return [
        e
        for e in snapshot.edges
        if e.edge_type == "implemented_by" and e.source_id == "KM-FIX-1"
    ]


class RecordingDb:
    """Database double: records every statement, echoing node batches back as a faithful store."""

    def __init__(self):
        self.calls = []  # (statement, params, write)

    async def _run(self, statement, params=None, write=False, **_ignored):
        self.calls.append((statement, params or {}, write))
        if "MATCH (n) RETURN count(n)" in statement or "MATCH ()-[r]->() RETURN count(r)" in statement:
            return [{"count": 0}]  # whole-database usage: this double stores nothing
        if "SHOW DATABASE" in statement:
            return [{"access": "read-write"}]
        if "generation_key IS NULL" in statement:
            return [{"count": 0}]
        if "MERGE (g:Snapshot" in statement:
            return [{"digest": params["meta"]["digest"], "status": "building"}]
        if "UNWIND $rows" in statement:
            return [{"key": r["key"], "props": r} for r in params["rows"]]
        return []

    def writes(self):
        return [c for c in self.calls if c[2]]


def _publish(snapshot, monkeypatch):
    projection = importlib.import_module("knowledge.adapters.neo4j_projection")

    async def no_counts(*args, **kwargs):
        return None

    async def activated(*args, **kwargs):
        return True

    # Only the post-build count check and the pointer switch are stubbed: the snapshot hand-off to
    # the writer (the behaviour under test) runs unmodified.
    monkeypatch.setattr(projection, "_validate_counts", no_counts)
    monkeypatch.setattr(projection, "switch_active", activated)
    db = RecordingDb()
    result = asyncio.run(projection.publish(db, snapshot, None))
    return db, result


def _first_write_meta(db):
    writes = db.writes()
    assert writes, "publication wrote nothing"
    statement, params, _ = writes[0]
    assert "MERGE (g:Snapshot" in statement, "first write must be the generation record"
    return params["meta"]


def _edge_rows(db, target=TARGET):
    rows = []
    for statement, params, _ in db.writes():
        if "MERGE (a)-[r:" in statement:
            for row in params["rows"]:
                payload = json.loads(row["payload"])
                if payload["target_id"] == target and payload["edge_type"] == "implemented_by":
                    rows.append(payload)
    return rows


def _diagnostics(db, result):
    meta = _first_write_meta(db)
    listed = json.loads(meta["diagnostics"])
    extra = [result] if isinstance(result, (dict, list, str)) else []
    return [str(x) for x in listed] + [json.dumps(x) for x in extra]


def test_identical_relationships_from_real_ac_yaml_collapse_before_any_write(tmp_path, monkeypatch):
    # covers: KM-400b-2-i
    # angle: real_artifact
    sha = _repository(tmp_path, [TARGET, TARGET])
    snapshot = _load(tmp_path, sha)
    duplicated = _implemented_by(snapshot)
    # control: the real loader really does yield two identical relationships for the repeated path
    assert len(duplicated) == 2
    assert duplicated[0].model_dump_json() == duplicated[1].model_dump_json()
    total = len(snapshot.edges)

    db, result = _publish(snapshot, monkeypatch)

    # the publication is neither failed nor refused on account of the duplicate
    assert result is True
    # before any node or relationship is written, the generation record already counts the set
    assert _first_write_meta(db)["edge_count"] == total - 1
    # exactly one relationship for the pair reaches the writer
    rows = _edge_rows(db)
    assert len(rows) == 1
    assert rows[0]["source_id"] == "KM-FIX-1"
    # the collapse is reported with its source, in a single diagnostic
    named = [d for d in _diagnostics(db, result) if TARGET in d]
    assert len(named) >= 1
    line = named[0]
    assert "implemented_by" in line
    assert AC_PATH in line
    assert re.search(r"(?<![\w.])2(?![\w.])", line), line


def test_relationships_differing_in_provenance_are_not_collapsed(tmp_path, monkeypatch):
    # covers: KM-400b-2-i
    # angle: boundary
    sha = _repository(tmp_path, [TARGET])
    snapshot = _load(tmp_path, sha)
    (original,) = _implemented_by(snapshot)
    other_source = original.source.model_copy(update={"locator": "/implemented_by/1"})
    sibling = original.model_copy(update={"source": other_source})
    assert sibling.model_dump_json() != original.model_dump_json()
    snapshot = snapshot.model_copy(update={"edges": [*snapshot.edges, sibling]})

    db, result = _publish(snapshot, monkeypatch)

    assert result is True
    assert _first_write_meta(db)["edge_count"] == len(snapshot.edges)
    rows = _edge_rows(db)
    assert len(rows) == 2
    assert {r["source"]["locator"] for r in rows} == {"/implemented_by", "/implemented_by/1"}
    assert [d for d in _diagnostics(db, result) if TARGET in d] == []


_ZERO = re.compile(r"(?i)(collapsed\D{0,40}(?<![\w.])0(?![\w.])|(?<![\w.])0(?![\w.])\D{0,40}collapsed)")


def test_zero_collapsed_relationships_is_reported_explicitly(tmp_path, monkeypatch):
    # covers: KM-400b-2-i
    # angle: failure
    clean = _load(tmp_path / "clean", _clean_repo(tmp_path / "clean"))
    dirty_root = tmp_path / "dirty"
    dirty = _load(dirty_root, _dirty_repo(dirty_root))

    clean_db, clean_result = _publish(clean, monkeypatch)
    dirty_db, dirty_result = _publish(dirty, monkeypatch)

    clean_lines = _diagnostics(clean_db, clean_result)
    # the zero figure is stated, not omitted
    assert any(_ZERO.search(d) for d in clean_lines), clean_lines
    # control: a snapshot that did collapse something does not state the zero figure
    assert not any(_ZERO.search(d) for d in _diagnostics(dirty_db, dirty_result))
    assert clean_lines != _diagnostics(dirty_db, dirty_result)


def _clean_repo(root):
    root.mkdir()
    return _repository(root, [TARGET])


def _dirty_repo(root):
    root.mkdir()
    return _repository(root, [TARGET, TARGET])


_DRIVER = textwrap.dedent(
    """
    import json, sys
    from knowledge.adapters import neo4j_backend
    from knowledge.adapters import neo4j_projection

    calls = []

    class Fake(neo4j_backend.Neo4jBackend):
        def __init__(self, *a, **k):
            pass

        async def _run(self, statement, params=None, write=False, **_ignored):
            calls.append((statement, params or {}, write))
            if "MATCH (n) RETURN count(n)" in statement or "MATCH ()-[r]->() RETURN count(r)" in statement:
                return [{"count": 0}]
            if "SHOW DATABASE" in statement:
                return [{"access": "read-write"}]
            if "generation_key IS NULL" in statement:
                return [{"count": 0}]
            if "MERGE (g:Snapshot" in statement:
                return [{"digest": params["meta"]["digest"], "status": "building"}]
            if "UNWIND $rows" in statement:
                return [{"key": r["key"], "props": r} for r in params["rows"]]
            return []

        async def active(self, repository_id):
            return None

        async def close(self):
            return None

    async def no_counts(*a, **k):
        return None

    async def activated(*a, **k):
        return True

    neo4j_projection._validate_counts = no_counts
    neo4j_projection.switch_active = activated
    from knowledge import cli_sync
    cli_sync.writer_backend = lambda root=None: Fake()
    from knowledge.__main__ import main

    try:
        main_code = main()
    except SystemExit as exit_:
        main_code = exit_.code
    first = [c for c in calls if c[2] and "meta" in c[1]][0]
    sys.stderr.write(json.dumps({"edge_count": first[1]["meta"]["edge_count"],
                                 "diagnostics": first[1]["meta"]["diagnostics"]}) + "\\n")
    raise SystemExit(main_code or 0)
    """
)


def test_km_400b_2_i_reachable_from_entry_point(tmp_path):
    # covers: KM-400b-2-i
    # angle: reachability
    # Entry point: `python -m knowledge sync --root <repo>` (knowledge.__main__.main() with real
    # argv, fresh subprocess); only the writer's Neo4j driver class is replaced.
    sha = _repository(tmp_path, [TARGET, TARGET])
    env = {k: v for k, v in os.environ.items() if not k.startswith("LEAFCUTTER_NEO4J")}
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    argv = ["knowledge", "sync", "--root", str(tmp_path), "--repository-id", "repo",
            "--revision", sha]
    code = _DRIVER.replace("from knowledge.__main__ import main",
                           "from knowledge.__main__ import main\nsys.argv = %r" % (argv,))
    done = subprocess.run(
        [sys.executable, "-c", code], cwd=REPO_ROOT, env=env, capture_output=True, text=True,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr
    report = json.loads(done.stderr.strip().splitlines()[-1])
    listed = json.loads(report["diagnostics"])
    assert any(TARGET in str(d) and "implemented_by" in str(d) for d in listed), listed
    payload = json.loads(done.stdout.strip().splitlines()[-1])
    assert payload["status"] == "ok"
    assert payload["edge_count"] == report["edge_count"]
