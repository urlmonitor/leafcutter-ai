"""
MODULE: unit_tests/build_orchestration/_tq500g2i_fixtures.py
GOAL: Shared REAL sandbox for the TQ-500g-2-i tests (the suite that quietly re-installs the
    correct code is caught by reading the database catalogue).
BUSINESS CONTEXT: CI has no database (user decision OQ-2 (A)), so the one stand-in is the
    third-party PostgreSQL driver (``_tq500g2i_standin_pg.py``, a JSON-file catalogue). The
    project is a real git repo, the AC store is written with yaml.safe_dump, the config with
    json.dump, and the real runner CLI runs as a subprocess against a loopback listener so the
    real ``check_test_db`` reports "reachable". The fixture suite installs fn_refresh_due from
    the file named by TQ_G2I_SOURCE in a module fixture (its setUpClass): the source file itself
    (D2) or an unaltered copy kept outside the repo (D1). No concrete address or password is held
    as a literal; both are built at run time.
ARCHITECTURE: Not a test file. Reuses the listener, address builder and JSON reader of
    ``_tq500g2ii_fixtures``. Events (connect, install, catalog_read, call, teardown, ...) go to
    one JSONL file so the order of the catalogue read against the test's phases can be asserted.
"""

from __future__ import annotations

import difflib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import unit_tests.build_orchestration._tq500f3i_fixtures as gitfx
import unit_tests.build_orchestration._tq500g2ii_fixtures as fx2

Listener = fx2.Listener
address_for = fx2.address_for
PASSWORD = fx2.PASSWORD
USER = "g2ii_user"
RUNNER = fx2.RUNNER
AC_ID = "TQ-9103"
WV_DROP = "drop the retry_due condition"
WV_OTHER = "treat any retry_due as due"
WV_UNDONE = "the fix undone"
TEST = "test_fn_refresh_due_false_retry_is_not_due"
TEST_FILE = "fx_tests/test_db.py"
SQL_REL = "db/fn_refresh_due.sql"
FUNCTION = "fn_refresh_due"
STANDIN = Path(__file__).resolve().parent / "_tq500g2i_standin_pg.py"

_SQL = ("CREATE OR REPLACE FUNCTION fn_refresh_due(refresh_due boolean, retry_due boolean)\nRETURNS boolean\n"
        "LANGUAGE sql\nAS $$\n    SELECT {expr}\n$$;\n")
BASE_SQL = _SQL.format(expr="refresh_due")
AS_WRITTEN = _SQL.format(expr="refresh_due AND retry_due")
WRONG_DROP = _SQL.format(expr="refresh_due -- altered: the retry_due condition is gone")
WRONG_OTHER = _SQL.format(expr="refresh_due OR NOT retry_due")

_SUITE = '''\
import json, os, sys
from pathlib import Path
sys.path.insert(0, @SCRIPTS@)
import pytest
from db_check.checker import resolve_test_db_address


def _ev(**fields):
    with open(os.environ["TQ_G2I_EVENTS"], "a", encoding="utf-8") as fh:
        fh.write(json.dumps(fields) + "\\n")


def _driver():
    try:
        import psycopg2 as pg
    except ImportError:
        import standin_pg as pg
    return pg


@pytest.fixture(scope="module", autouse=True)
def installed_from_source():
    conn = _driver().connect(resolve_test_db_address(Path.cwd()))
    conn.cursor().execute(Path(os.environ["TQ_G2I_SOURCE"]).read_text(encoding="utf-8"))
    conn.commit()
    _ev(ev="suite_install", conn=conn.tq_id)
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def phases(installed_from_source):
    _ev(ev="setup")
    yield
    _ev(ev="teardown")


def test_fn_refresh_due_false_retry_is_not_due(installed_from_source):
    # covers: @AC@
    _ev(ev="call", conn=installed_from_source.tq_id)
    cur = installed_from_source.cursor()
    cur.execute("SELECT fn_refresh_due(true, false)")
    assert cur.fetchone()[0] is False
'''
_BLOCKER = 'raise ImportError("blocked for the test: no PostgreSQL driver in this interpreter")\n'


@dataclass
class Project:
    root: Path
    work: Path
    test_root: Path
    ac_root: Path
    base_sha: str
    manifest: Path
    events: Path
    catalog: Path
    driver_dir: Path
    block_dir: Path | None
    source: Path
    fail_read: bool = False
    refuse: bool = False
    extra_env: dict = field(default_factory=dict)  # opt-in stand-in switches (review-fix tests)


def _wb(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def build_project(root: Path, *, address: str, source: str = "altered", others: bool = False, fail_read: bool = False,
                  refuse: bool = False, no_driver: bool = False) -> Project:
    """Build a git project with the fix (fn_refresh_due.sql) and a database test that installs from ``source``.

    Args:
        root: Empty directory to build under.
        address: The value of testing_context.db_connection_test.
        source: ``"altered"`` (D2: the suite installs the file the runner alters) or ``"unaltered"``
            (D1: it installs a copy of the code as written, kept outside the repo).
        others: Also name WV_OTHER in the test's must_catch (a second named wrong version).
        fail_read: The stand-in raises, with the address in its text, on every catalogue read.
        refuse: The stand-in ignores an install of the correct code over the wrong one.
        no_driver: No PostgreSQL driver module is importable except the suite's private one.
    """
    work, base_sha = gitfx.make_worktree(root, {"db/fn_refresh_due.sql": BASE_SQL, ".gitignore": "__pycache__/\n.pytest_cache/\n.claude/\n"})
    _wb(work / SQL_REL, AS_WRITTEN)
    _wb(work / TEST_FILE, _SUITE.replace("@SCRIPTS@", repr(str(fx2.SCRIPTS))).replace("@AC@", AC_ID))
    gitfx.commit_all(work, "the fix and its test")
    state = root / "state"
    state.mkdir(parents=True, exist_ok=True)
    cfg = work / ".claude" / "skills_config.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({"testing_context": {"db_connection_test": address}}), encoding="utf-8")
    driver = root / "driver"
    driver.mkdir()
    shutil.copyfile(STANDIN, driver / "standin_pg.py")
    if not no_driver:
        _wb(driver / "psycopg2" / "__init__.py", "from standin_pg import *  # noqa: F401,F403\n")
    block = root / "block" if no_driver else None
    for module in ("psycopg2", "psycopg", "pg8000"):
        if block is not None:
            _wb(block / f"{module}.py", _BLOCKER)
    unaltered = root / "unaltered" / "fn_refresh_due.sql"
    _wb(unaltered, AS_WRITTEN)
    spec = [{"name": TEST, "requires_db": True, "must_catch": [WV_DROP, *([WV_OTHER] if others else [])]}]
    ac_root = root / "ac_store"
    gitfx.write_ac_yaml(ac_root, AC_ID, spec)
    proj = Project(root, work, work / "fx_tests", ac_root, base_sha, state / "alterations.json", state / "events.jsonl",
                   state / "catalog.json", driver, block, work / SQL_REL if source == "altered" else unaltered, fail_read, refuse)
    versions = {WV_DROP: WRONG_DROP, **({WV_OTHER: WRONG_OTHER} if others else {})}
    _write_manifest(proj, versions)
    return proj


def _write_manifest(proj: Project, versions: dict[str, str]) -> None:
    entries = []
    for i, (name, altered) in enumerate(versions.items()):
        copy = proj.root / "altered" / f"{i}_fn_refresh_due.sql"
        _wb(copy, altered)
        diff = "".join(difflib.unified_diff(AS_WRITTEN.splitlines(True), altered.splitlines(True), "a/" + SQL_REL, "b/" + SQL_REL))
        entries.append({"name": name, "status": "prepared", "reason": None, "diff": diff,
                        "files": [{"path": SQL_REL, "altered_copy": str(copy)}]})
    proj.manifest.write_text(json.dumps({"work_key": "tq-9103-fx", "entries": entries}), encoding="utf-8")


def env_for(proj: Project, temp: Path | None = None) -> dict:
    env = {k: v for k, v in os.environ.items() if k != fx2.TIMEOUT_ENV}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    path = [str(p) for p in (proj.block_dir, proj.driver_dir) if p is not None]
    env["PYTHONPATH"] = os.pathsep.join(path + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    env.update(TQ_G2I_EVENTS=str(proj.events), TQ_G2I_CATALOG=str(proj.catalog), TQ_G2I_SOURCE=str(proj.source))
    if proj.fail_read:
        env["TQ_G2I_FAIL_READ"] = "1"
    if proj.refuse:
        env["TQ_G2I_REFUSE"] = "1"
    env.update(proj.extra_env)
    if temp is not None:
        env.update(TEMP=str(temp), TMP=str(temp), TMPDIR=str(temp))
    return env


def _command(proj: Project) -> list[str]:
    return [sys.executable, str(RUNNER), "run", "--ac-ids", AC_ID, "--test-root", str(proj.test_root), "--ac-root", str(proj.ac_root),
            "--base-ref", proj.base_sha, "--alterations", str(proj.manifest)]


def run_runner(proj: Project):
    """Run ``wrong_version_runner.py run`` at the repo root; return ``(proc, verdict)``."""
    proc = subprocess.run(_command(proj), cwd=proj.work, capture_output=True, text=True, timeout=420, env=env_for(proj))
    return proc, fx2.parse_json(proc)


def run_runner_watched(proj: Project, temp: Path):
    """Run the runner with a private TEMP and collect every file it leaves there while it runs.

    The runner's temporary files (the plugins' output files) are deleted when the run ends, so a
    poller reads each one while it exists. Returns ``(proc, verdict, files)`` with ``files`` the
    ``{name: [every distinct text seen, in order]}`` map: a snapshot is never overwritten, so a
    later empty or partial read cannot hide an earlier one.
    """
    temp.mkdir(parents=True, exist_ok=True)
    seen: dict[str, list[str]] = {}
    stop = threading.Event()

    def poll() -> None:
        while not stop.is_set():
            for path in list(temp.iterdir()):
                try:
                    text = path.read_bytes().decode("utf-8", "replace")
                except OSError:
                    continue
                snaps = seen.setdefault(path.name, [])
                if text not in snaps:
                    snaps.append(text)
            time.sleep(0.002)

    watcher = threading.Thread(target=poll, daemon=True)
    watcher.start()
    try:
        proc = subprocess.run(_command(proj), cwd=proj.work, capture_output=True, text=True, timeout=420, env=env_for(proj, temp))
    finally:
        stop.set()
        watcher.join(5)
    return proc, fx2.parse_json(proc), seen


def events(proj: Project) -> list[dict]:
    return fx2.jsonl(proj.events)


def normal(text: str) -> str:
    """Whitespace-insensitive normal form."""
    return " ".join(text.split())


def catalogue_text(proj: Project) -> str:
    try:
        return json.loads(proj.catalog.read_text(encoding="utf-8")).get(FUNCTION, "")
    except (OSError, ValueError):
        return ""


def rows(verdict: dict, wv: str | None = None) -> list[dict]:
    return [r for r in verdict.get("results", []) if str(r.get("test", "")).endswith("::" + TEST) and (wv is None or r.get("wrong_version") == wv)]


def source_bytes(proj: Project) -> bytes:
    return (proj.work / SQL_REL).read_bytes()
