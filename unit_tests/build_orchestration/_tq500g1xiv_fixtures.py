"""
MODULE: unit_tests/build_orchestration/_tq500g1xiv_fixtures.py
GOAL: Shared REAL sandbox and CLI driver for the TQ-500g-1-xiv test family (a test held to a wrong version
    that changes no line the test runs is reported not executed and unfinished, never as a survivor).
BUSINESS CONTEXT: The sandbox is a real git repo whose ``sitecustomize_chain.py`` goes from a base version to
    the committed fix (so the run's derived scope contains it), real pytest tests T1/T2/T3 (T1 calls
    chain_sitecustomize(), T2 never does, T3 calls it and still passes under the alteration), a real SQL
    migration, a real AC store (yaml.safe_dump) and an alterations manifest (json.dump) in the TQ-500g-1-iv
    shape. No pytest output is hand-typed. The runner is only ever driven through its CLI (subprocess).
ARCHITECTURE: Not a test file (leading underscore). The altered copies are the committed fix with exactly
    one line replaced, so the changed line is known from this module's own constants, never from the code
    under test.
"""

from __future__ import annotations

import difflib
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import unit_tests.build_orchestration._tq500f3i_fixtures as gitfx
import unit_tests.build_orchestration._tq500g1_fixtures as g1

REPO_ROOT = g1.REPO_ROOT
RUNNER = g1.RUNNER
AC_ID = "TQ-9114"
WV_NAIVE = "naive chain re-invokes the previous sitecustomize"
WV_SQL = "the migration leaves the column nullable"
WV_CONST = "the module constant is altered"
T1, T2, T3 = "test_t1_calls_the_chain", "test_t2_never_calls_the_chain", "test_t3_weak_chain_check"
T4 = "test_t4_calls_the_chain_in_a_child_process"
TS1, TS2 = "test_ts1_column_is_not_null", "test_ts2_unrelated_check"
MOD, SQL_REL = "sitecustomize_chain.py", "migrations/001_add_col.sql"
NOT_EXECUTED = "not executed: the test runs none of the changed lines"
UNTRACED = "run-or-not-run could not be traced for"

BASE_MOD = 'MODULE_CONST = "base"\n\n\ndef chain_sitecustomize():\n    return "base"\n'
FIX_MOD = ('import os\n\nMODULE_CONST = "fix"\n\n\ndef chain_sitecustomize():\n'
           '    previous = os.environ.get("PREV_SITE")\n    if previous:\n        return "chained"\n    return "none"\n')
BASE_SQL = "-- add column c\nALTER TABLE t ADD COLUMN c TEXT;\n"
FIX_SQL = "-- add column c\nALTER TABLE t ADD COLUMN c TEXT NOT NULL;\n"
# (relative path, as-written text, the one line replaced, its replacement)
CHAIN_LINE = (MOD, FIX_MOD, "    if previous:", "    if True:")
CONST_LINE = (MOD, FIX_MOD, 'MODULE_CONST = "fix"', 'MODULE_CONST = "altered"')
SQL_LINE = (SQL_REL, FIX_SQL, "TEXT NOT NULL;", "TEXT NULL;")

_PY_HEAD = "import sys\n\nsys.path.insert(0, @WORK@)\nimport sitecustomize_chain as sc\n"
_PY_BODIES = {
    T1: (f'def {T1}(monkeypatch):\n    # covers: {AC_ID}\n    monkeypatch.delenv("PREV_SITE", raising=False)\n'
         f'    assert sc.chain_sitecustomize() == "none"\n'),
    T2: f'def {T2}():\n    # covers: {AC_ID}\n    assert sc.MODULE_CONST == "fix"\n',
    T3: (f'def {T3}(monkeypatch):\n    # covers: {AC_ID}\n    monkeypatch.setenv("PREV_SITE", "x")\n'
         f'    assert sc.chain_sitecustomize() == "chained"\n'),
    # T4 runs the changed line only inside a child interpreter, out of the in-process trace's sight.
    T4: (f'def {T4}(monkeypatch):\n    # covers: {AC_ID}\n    import os\n    import subprocess\n'
         f'    monkeypatch.delenv("PREV_SITE", raising=False)\n'
         f'    code = "import sitecustomize_chain as sc; print(sc.chain_sitecustomize())"\n'
         f'    where = os.path.dirname(sc.__file__)\n'
         f'    out = subprocess.run([sys.executable, "-c", code], cwd=where, capture_output=True, text=True)\n'
         f'    assert out.stdout.strip() == "none", out\n'),
}
_SQL_HEAD = "from pathlib import Path\n\nSQL = Path(@WORK@) / @REL@\n"
_SQL_BODIES = {
    TS1: f'def {TS1}():\n    # covers: {AC_ID}\n    assert "NOT NULL" in SQL.read_text(encoding="utf-8")\n',
    TS2: f'def {TS2}():\n    # covers: {AC_ID}\n    assert 1 + 1 == 2\n',
}


@dataclass
class Sandbox:
    root: Path
    work: Path
    test_root: Path
    ac_root: Path
    base_sha: str
    manifest: Path
    written: dict[str, bytes] = field(default_factory=dict)


def _wb(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def entry(name: str, *must_catch: str) -> dict:
    """One test_spec entry that names *must_catch*."""
    return {"name": name, "must_catch": list(must_catch)}


def altered_text(line: tuple[str, str, str, str]) -> str:
    """The as-written text of *line*'s file with exactly that one line replaced."""
    _rel, text, old, new = line
    assert text.count(old) == 1, f"{old!r} must be exactly one line of the fixture file"
    return text.replace(old, new)


def build(root: Path, spec: list[dict], versions: dict[str, tuple[str, str, str, str]]) -> Sandbox:
    """Build the sandbox: tests are written for the names *spec* lists; *versions* maps name -> altered line."""
    work, base_sha = gitfx.make_worktree(root, {".gitignore": "__pycache__/\n.pytest_cache/\n", MOD: BASE_MOD, SQL_REL: BASE_SQL})
    _wb(work / MOD, FIX_MOD)
    _wb(work / SQL_REL, FIX_SQL)
    names = [e["name"] for e in spec]
    fx = work / "fx_tests"
    py = [_PY_BODIES[n] for n in names if n in _PY_BODIES]
    sql = [_SQL_BODIES[n] for n in names if n in _SQL_BODIES]
    if py:
        _wb(fx / "test_chain.py", "\n\n".join([_PY_HEAD.replace("@WORK@", repr(str(work))), *py]))
    if sql:
        head = _SQL_HEAD.replace("@WORK@", repr(str(work))).replace("@REL@", repr(SQL_REL))
        _wb(fx / "test_migration.py", "\n\n".join([head, *sql]))
    gitfx.commit_all(work, "the fix and its tests")
    ac_root = root / "ac_store"
    gitfx.write_ac_yaml(ac_root, AC_ID, spec)
    state = root / "state"
    sb = Sandbox(root, work, fx, ac_root, base_sha, state / "alterations.json",
                 {MOD: FIX_MOD.encode("utf-8"), SQL_REL: FIX_SQL.encode("utf-8")})
    _write_manifest(sb, versions)
    return sb


def _write_manifest(sb: Sandbox, versions: dict[str, tuple[str, str, str, str]]) -> None:
    entries = []
    for i, (name, line) in enumerate(versions.items()):
        rel, text = line[0], line[1]
        copy = sb.root / "altered" / f"{i}_{Path(rel).name}"
        _wb(copy, altered_text(line))
        diff = "".join(difflib.unified_diff(text.splitlines(True), altered_text(line).splitlines(True), "a/" + rel, "b/" + rel))
        entries.append({"name": name, "status": "prepared", "reason": None, "diff": diff,
                        "files": [{"path": rel, "altered_copy": str(copy)}]})
    sb.manifest.parent.mkdir(parents=True, exist_ok=True)
    sb.manifest.write_text(json.dumps({"work_key": "tq-9114-fx", "entries": entries}), encoding="utf-8")


def command(sb: Sandbox, runner: Path = RUNNER) -> list[str]:
    """The runner CLI's ``run`` command line for *sb*."""
    return [sys.executable, str(runner), "run", "--ac-ids", AC_ID, "--test-root", str(sb.test_root),
            "--ac-root", str(sb.ac_root), "--base-ref", sb.base_sha, "--alterations", str(sb.manifest)]


def run(sb: Sandbox, runner: Path = RUNNER):
    """Run the runner CLI (subprocess) at the repo root; return ``(proc, verdict)``."""
    proc = subprocess.run(command(sb, runner), cwd=sb.work, capture_output=True, text=True, timeout=420, env=g1._env())
    return proc, g1.parse_json(proc)


def rows(verdict: dict, test: str, wv: str | None = None) -> list[dict]:
    """The verdict rows of the test named *test* (repo-relative ``path::name`` labels), optionally for *wv*."""
    return [r for r in verdict.get("results", []) if str(r.get("test", "")).endswith("::" + test)
            and (wv is None or r.get("wrong_version") == wv)]


def results_of(verdict: dict, test: str, wv: str) -> list[str]:
    """The result words of one test's rows under one wrong version."""
    return [r["result"] for r in rows(verdict, test, wv)]


def survivor_tests(verdict: dict) -> list[str]:
    """The bare test names in the verdict's survivors."""
    return sorted(str(s["test"]).rsplit("::", 1)[-1] for s in verdict.get("survivors", []))


def spec_t1_t2() -> list[dict]:
    """T1 and T2 both name the naive-chain wrong version (the AC's own example)."""
    return [entry(T1, WV_NAIVE), entry(T2, WV_NAIVE)]
