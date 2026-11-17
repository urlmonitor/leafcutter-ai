"""
MODULE: unit_tests/build_orchestration/_tq500g2ii_fixtures.py
GOAL: Shared REAL sandbox for the TQ-500g-2-ii tests (database tests in the
    wrong-version runs, the configured test database only, extras "to run later").
BUSINESS CONTEXT: CI has no database, so every project here is a real git repo
    with a real AC store (yaml.safe_dump), a real ``.claude/skills_config.json``
    (json.dump) and the real runner / writer CLIs run as subprocesses. A loopback
    TCP listener makes the real ``check_test_db`` report "reachable"; a stand-in
    ``psycopg2`` module on the pytest child's import path logs every address it is
    asked to connect to, so "on the database the setting names and on no other"
    is read from that log. Concrete loopback addresses are built at run time;
    no literal address is held in this file.
ARCHITECTURE: Not a test file (leading underscore). The DB tests resolve the
    address the INF-1100d-3-ii way (``resolve_test_db_address(Path.cwd())``), so
    they only see the setting the gate checked when the runner runs pytest with
    the repo root as cwd. The to-run-later file is written with json.dump at
    ``<git-dir>/leafcutter/to-run-later/<ac-id>.json`` (user decision OQ-1 (A)).
"""

from __future__ import annotations

import difflib
import json
import os
import secrets
import socket
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import unit_tests.build_orchestration._tq500f3i_fixtures as gitfx

REPO_ROOT = gitfx.REPO_ROOT
SCRIPTS = REPO_ROOT / "scripts"
RUNNER = SCRIPTS / "build_orchestration" / "wrong_version_runner.py"
WRITER = SCRIPTS / "build_orchestration" / "wrong_version_writer.py"
TIMEOUT_ENV = "LEAFCUTTER_DONE_PROOF_PYTEST_TIMEOUT_SECONDS"

AC_ID = "TQ-9102"
SETTING = "testing_context.db_connection_test"
WV_DROP = "drop the retry_due condition"
WV_UNDONE = "the fix undone"
WV_EXTRA = "treat a NULL retry_due as true"
# Made fresh per test process, so no fixed credential-like literal sits in the repo.
PASSWORD = "pw-" + secrets.token_hex(8)
DB1, DB2, DB3 = "test_db1_false_retry_skips", "test_db2_null_retry_skips", "test_db3_weak_gate"
PLAIN = "test_plain_false_retry_skips"
TEST_FILE = "fx_tests/test_db.py"

_BASE = 'def refresh_config(refresh_due, retry_due):\n    if refresh_due:\n        return "refresh"\n    return "skip"\n'
_FIX = _BASE.replace("if refresh_due:", "if refresh_due and retry_due:")
_EXTRA_TEXT = _FIX.replace("if refresh_due and retry_due:", "if refresh_due and (retry_due is None or retry_due):")

_DRIVER = '''\
import json, os


class _Conn:
    autocommit = False

    def cursor(self):
        raise RuntimeError("stand-in driver has no cursor")

    def rollback(self):
        pass

    def close(self):
        pass


def connect(dsn=None, *args, **kwargs):
    with open(os.environ["TQ_G2II_CONNLOG"], "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"address": dsn}) + "\\n")
    return _Conn()
'''

_HEADER = '''\
import json, os, sys
from pathlib import Path
sys.path.insert(0, @WORK@)
sys.path.insert(0, @SCRIPTS@)
from refresh_config import refresh_config


def _log(name):
    with open(os.environ["TQ_G2II_RUNLOG"], "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"test": name}) + "\\n")


def _connect():
    from db_check.checker import resolve_test_db_address
    import psycopg2
    return psycopg2.connect(resolve_test_db_address(Path.cwd()))
'''

_BODIES = {
    DB1: ("(True, False)", True), DB2: ("(True, None)", True), DB3: ("(False, False)", True),
    PLAIN: ("(True, False)", False),
}


def _test_source(work: Path, tests) -> str:
    out = [_HEADER.replace("@WORK@", repr(str(work))).replace("@SCRIPTS@", repr(str(SCRIPTS)))]
    for name in tests:
        args, uses_db = _BODIES[name]
        connect = "    _connect()\n" if uses_db else ""
        out.append(f'def {name}():\n    # covers: {AC_ID}\n    _log({name!r})\n{connect}'
                   f'    assert refresh_config{args} == "skip"\n')
    return "\n\n".join(out)


@dataclass
class Project:
    root: Path
    work: Path
    test_root: Path
    ac_root: Path
    base_sha: str
    manifest: Path
    connlog: Path
    runlog: Path
    driver_dir: Path
    address: str | None
    to_run_later: Path

    @property
    def git_dir(self) -> Path:
        return Path(gitfx.run_git(["rev-parse", "--absolute-git-dir"], cwd=self.work).strip())


class Listener:
    """A loopback TCP listener: the real ``check_test_db`` reports it "reachable"."""

    def __init__(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(16)
        self.port = self.sock.getsockname()[1]

    def __enter__(self) -> "Listener":
        return self

    def __exit__(self, *_exc) -> None:
        self.sock.close()


def closed_port() -> int:
    """A loopback port nothing listens on."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def address_for(port: int) -> str:
    """Build the concrete loopback address at run time (never held as a literal)."""
    return "postgresql://" + f"g2ii_user:{PASSWORD}@127.0.0.1:{port}/g2ii_db"


def _wb(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def build_project(root: Path, *, setting: str | None, tests=(DB1, DB2), extras=(), config_text: str | None = None,
                  with_plain: bool = False) -> Project:
    """Build a git project whose fix is ``if refresh_due and retry_due`` and whose DB tests name WV_DROP.

    Args:
        root: Empty directory to build under.
        setting: Value of testing_context.db_connection_test; ``None`` leaves the key out.
        tests: The DB test function names to write (DB3 is a weak test that survives WV_DROP).
        extras: ``(test function name, wrong version name)`` to-run-later entries.
        config_text: Raw skills_config.json text to write instead of the serialized setting.
        with_plain: Also write a non-database in-scope test (a control that must still run).
    """
    work, base_sha = gitfx.make_worktree(root, {"refresh_config.py": _BASE, ".gitignore": "__pycache__/\n.pytest_cache/\n.claude/\n"})
    names = [*tests, *([PLAIN] if with_plain else [])]
    _wb(work / "refresh_config.py", _FIX)
    _wb(work / TEST_FILE, _test_source(work, names))
    gitfx.commit_all(work, "the fix and its tests")
    state = root / "state"
    state.mkdir(parents=True, exist_ok=True)
    cfg = work / ".claude" / "skills_config.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    testing_context = {} if setting is None else {"db_connection_test": setting}
    cfg.write_text(config_text if config_text is not None else json.dumps({"testing_context": testing_context}), encoding="utf-8")
    driver = root / "driver"
    _wb(driver / "psycopg2" / "__init__.py", _DRIVER)
    ac_root = root / "ac_store"
    spec = [{"name": n, "requires_db": n != PLAIN, "must_catch": [WV_DROP]} for n in names]
    gitfx.write_ac_yaml(ac_root, AC_ID, spec)
    proj = Project(root, work, work / "fx_tests", ac_root, base_sha, state / "alterations.json", state / "conn.jsonl",
                   state / "run.jsonl", driver, setting, work / ".git")
    altered = {WV_DROP: _FIX.replace("if refresh_due and retry_due:", "if refresh_due:  # altered")}
    altered.update({wv: _EXTRA_TEXT for _t, wv in extras if wv.strip().casefold() != WV_DROP})
    _write_manifest(proj, altered)
    _write_to_run_later(proj, extras)
    return proj


def _write_manifest(proj: Project, altered_by_name: dict[str, str]) -> None:
    entries = []
    for i, (name, altered) in enumerate(altered_by_name.items()):
        copy = proj.root / "altered" / f"{i}_refresh_config.py"
        _wb(copy, altered)
        diff = "".join(difflib.unified_diff(_FIX.splitlines(True), altered.splitlines(True), "a/refresh_config.py", "b/refresh_config.py"))
        entries.append({"name": name, "status": "prepared", "reason": None, "diff": diff,
                        "files": [{"path": "refresh_config.py", "altered_copy": str(copy)}]})
    proj.manifest.write_text(json.dumps({"work_key": "tq-9102-fx", "entries": entries}), encoding="utf-8")


def _write_to_run_later(proj: Project, extras) -> None:
    """Write the OQ-1 (A) file: <git-dir>/leafcutter/to-run-later/<ac-id>.json."""
    proj.to_run_later = proj.git_dir / "leafcutter" / "to-run-later" / f"{AC_ID}.json"
    if not extras:
        return
    payload = {"ac_id": AC_ID, "to_run_later": [
        {"test": f"{TEST_FILE}::{t}", "wrong_version": wv, "reason": "the database test writer's hand-off"} for t, wv in extras]}
    proj.to_run_later.parent.mkdir(parents=True, exist_ok=True)
    proj.to_run_later.write_text(json.dumps(payload), encoding="utf-8")


def env_for(proj: Project) -> dict:
    env = {k: v for k, v in os.environ.items() if k != TIMEOUT_ENV}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(proj.driver_dir) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["TQ_G2II_CONNLOG"] = str(proj.connlog)
    env["TQ_G2II_RUNLOG"] = str(proj.runlog)
    return env


def parse_json(proc) -> dict:
    try:
        parsed = json.loads(proc.stdout.strip())
    except ValueError as exc:
        msg = f"no single JSON object (rc={proc.returncode}): stdout={proc.stdout[-400:]!r} stderr={proc.stderr[-400:]!r}"
        raise AssertionError(msg) from exc
    assert isinstance(parsed, dict), f"not a JSON object: {parsed!r}"
    return parsed


def run_runner(proj: Project):
    """Run ``wrong_version_runner.py run`` with cwd at the repo root; return (proc, verdict)."""
    cmd = [sys.executable, str(RUNNER), "run", "--ac-ids", AC_ID, "--test-root", str(proj.test_root), "--ac-root", str(proj.ac_root),
           "--base-ref", proj.base_sha, "--alterations", str(proj.manifest)]
    proc = subprocess.run(cmd, cwd=proj.work, capture_output=True, text=True, timeout=420, env=env_for(proj))
    return proc, parse_json(proc)


def run_writer_list(proj: Project):
    """Run ``wrong_version_writer.py list``; return (proc, payload)."""
    cmd = [sys.executable, str(WRITER), "list", "--ac-ids", AC_ID, "--test-root", str(proj.test_root), "--ac-root", str(proj.ac_root),
           "--base-ref", proj.base_sha]
    proc = subprocess.run(cmd, cwd=proj.work, capture_output=True, text=True, timeout=120, env=env_for(proj))
    return proc, parse_json(proc)


def label(test: str) -> str:
    return f"{TEST_FILE}::{test}"


def rows(verdict: dict, test: str | None = None, wv: str | None = None) -> list[dict]:
    return [r for r in verdict.get("results", [])
            if (test is None or str(r.get("test", "")).endswith("::" + test)) and (wv is None or r.get("wrong_version") == wv)]


def jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def ran_tests(proj: Project) -> list[str]:
    return [e["test"] for e in jsonl(proj.runlog)]


def all_output(proc) -> str:
    return proc.stdout + proc.stderr
