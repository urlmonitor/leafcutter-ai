"""
MODULE: unit_tests/build_orchestration/_tq500g2i_review_fixtures.py
GOAL: Project builder of the TQ-500g-2-i review-fix tests: the same real sandbox as
    ``_tq500g2i_fixtures`` (git project, yaml.safe_dump AC store, json.dump config, real runner
    CLI, stand-in driver) with the knobs the review findings need.
BUSINESS CONTEXT: Findings H-1..H-3 and M-1..M-5 need several database tests with their own
    named wrong versions, other SQL text (a quoted name, a ``%`` in a body), other driver module
    names (psycopg, pg8000) and the stand-in's opt-in switches. Not a test file.
ARCHITECTURE: :func:`build` returns an ``_tq500g2i_fixtures.Project`` whose ``extra_env`` the tests
    fill with ``TQ_G2I_*`` switches (see ``_tq500g2i_standin_pg.py``); the runner is then run with
    ``_tq500g2i_fixtures.run_runner``.
"""

from __future__ import annotations

import difflib
import json
import shutil
from pathlib import Path

import unit_tests.build_orchestration._tq500f3i_fixtures as gitfx
import unit_tests.build_orchestration._tq500g2i_fixtures as fx
import unit_tests.build_orchestration._tq500g2ii_fixtures as fx2

SECOND = "test_fn_refresh_due_second_guard"
DRIVERS = ("psycopg2", "psycopg", "pg8000")
DEFAULT_TESTS = [(fx.TEST, [fx.WV_DROP])]
DEFAULT_WRONGS = {fx.WV_DROP: fx.WRONG_DROP}

_MYFN = 'CREATE OR REPLACE FUNCTION "MyFn"()\nRETURNS integer\nLANGUAGE sql\nAS $$\n    SELECT {n}\n$$;\n'
MYFN_BASE = fx.BASE_SQL + _MYFN.format(n=1)
MYFN_WRITTEN = fx.AS_WRITTEN + _MYFN.format(n=1)
MYFN_WRONG = fx.WRONG_DROP + _MYFN.format(n=2)

_PCT = ("CREATE OR REPLACE FUNCTION fn_refresh_due(refresh_due boolean, retry_due boolean)\nRETURNS boolean\n"
        "LANGUAGE plpgsql\nAS $$\nBEGIN\n    RAISE NOTICE '%', refresh_due;\n    PERFORM format('%s', retry_due);\n"
        "    RETURN {expr};\nEND\n$$;\n")
PCT_BASE = _PCT.format(expr="refresh_due")
PCT_WRITTEN = _PCT.format(expr="refresh_due AND retry_due")
PCT_WRONG = _PCT.format(expr="refresh_due AND true")


def _wb(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _suite(names: list[str]) -> str:
    """The fixture suite with one identical test per name (all share the module-scoped install)."""
    head, tail = fx._SUITE.split("def " + fx.TEST, 1)  # noqa: SLF001 -- the one suite template
    body = "\n\n".join("def " + name + tail.rstrip("\n") for name in names)
    return (head + body + "\n").replace("@SCRIPTS@", repr(str(fx2.SCRIPTS))).replace("@AC@", fx.AC_ID)


def _manifest(proj: fx.Project, written: str, wrongs: dict[str, str]) -> None:
    entries = []
    for i, (name, altered) in enumerate(wrongs.items()):
        copy = proj.root / "altered" / f"{i}_fn_refresh_due.sql"
        _wb(copy, altered)
        diff = "".join(difflib.unified_diff(written.splitlines(True), altered.splitlines(True), "a/" + fx.SQL_REL, "b/" + fx.SQL_REL))
        entries.append({"name": name, "status": "prepared", "reason": None, "diff": diff,
                        "files": [{"path": fx.SQL_REL, "altered_copy": str(copy)}]})
    proj.manifest.write_text(json.dumps({"work_key": "tq-9103-rv", "entries": entries}), encoding="utf-8")


def _drivers(root: Path, provide: str | None) -> tuple[Path, Path | None]:
    """The driver dir (stand-in under the wanted module name) and the dir that blocks the earlier ones."""
    driver = root / "driver"
    driver.mkdir()
    shutil.copyfile(fx.STANDIN, driver / "standin_pg.py")
    blocked = [d for d in DRIVERS if provide is None or DRIVERS.index(d) < DRIVERS.index(provide)]
    if provide is not None:
        _wb(driver / provide / "__init__.py", "from standin_pg import *  # noqa: F401,F403\n")
    block = root / "block" if blocked else None
    for module in blocked:
        _wb(block / f"{module}.py", fx._BLOCKER)  # noqa: SLF001 -- the one blocker text
    return driver, block


def build(root: Path, *, address: str, tests: list[tuple[str, list[str]]] | None = None, wrongs: dict[str, str] | None = None,
          base_sql: str = fx.BASE_SQL, written_sql: str = fx.AS_WRITTEN, driver: str | None = "psycopg2",
          source: str = "altered", fail_read: bool = False, refuse: bool = False) -> fx.Project:
    """Build the project: the fix (``written_sql``) over ``base_sql`` and database tests that install from ``source``.

    Args:
        root: Empty directory to build under.
        address: The value of testing_context.db_connection_test.
        tests: ``(test function name, must_catch names)`` of each ``requires_db`` test (default: one, naming WV_DROP).
        wrongs: ``{wrong version name: altered SQL text}`` for the alterations manifest.
        base_sql: The SQL at the base ref ("the fix undone").
        written_sql: The SQL as written (the fix).
        driver: The module name the stand-in is importable as (earlier ones are blocked); ``None`` = none at all.
        source: ``"altered"`` (the suite installs the file the runner alters) or ``"unaltered"`` (a kept copy).
        fail_read: The stand-in raises, with the address in its text, on every catalogue read.
        refuse: The stand-in ignores an install of the correct code over the wrong one.
    """
    tests = tests if tests is not None else DEFAULT_TESTS
    wrongs = wrongs if wrongs is not None else DEFAULT_WRONGS
    work, base_sha = gitfx.make_worktree(root, {fx.SQL_REL: base_sql, ".gitignore": "__pycache__/\n.pytest_cache/\n.claude/\n"})
    _wb(work / fx.SQL_REL, written_sql)
    _wb(work / fx.TEST_FILE, _suite([name for name, _must in tests]))
    gitfx.commit_all(work, "the fix and its tests")
    state = root / "state"
    state.mkdir(parents=True, exist_ok=True)
    cfg = work / ".claude" / "skills_config.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({"testing_context": {"db_connection_test": address}}), encoding="utf-8")
    driver_dir, block = _drivers(root, driver)
    unaltered = root / "unaltered" / "fn_refresh_due.sql"
    _wb(unaltered, written_sql)
    ac_root = root / "ac_store"
    gitfx.write_ac_yaml(ac_root, fx.AC_ID, [{"name": n, "requires_db": True, "must_catch": list(must)} for n, must in tests])
    proj = fx.Project(root, work, work / "fx_tests", ac_root, base_sha, state / "alterations.json", state / "events.jsonl",
                      state / "catalog.json", driver_dir, block, work / fx.SQL_REL if source == "altered" else unaltered,
                      fail_read, refuse)
    _manifest(proj, written_sql, wrongs)
    return proj


def write_rows(proj: fx.Project, rows: list[dict]) -> None:
    """Hand the stand-in extra catalogue rows (``TQ_G2I_EXTRA_ROWS``)."""
    path = proj.root / "state" / "extra_rows.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    proj.extra_env["TQ_G2I_EXTRA_ROWS"] = str(path)


def gate_dir(proj: fx.Project) -> Path:
    """``<git-dir>/leafcutter/wrong-version-runs`` of the project's worktree."""
    git_dir = gitfx.run_git(["rev-parse", "--absolute-git-dir"], cwd=proj.work).strip()
    return Path(git_dir) / "leafcutter" / "wrong-version-runs"


def results_for(verdict: dict, wrong_version: str) -> list[dict]:
    """Every result row of one wrong version (any test)."""
    return [r for r in verdict.get("results", []) if r.get("wrong_version") == wrong_version]


def calls(proj: fx.Project) -> int:
    """How many database test calls the stand-in saw (baseline + each wrong-version run)."""
    return len([e for e in fx.events(proj) if e.get("ev") == "call"])


def leaked(address: str, port: int, *texts: str) -> list[str]:
    """The credential strings that appear in any of *texts* (empty = none leaked)."""
    leaks = (fx.PASSWORD, fx.USER, address, f"127.0.0.1:{port}")
    return [leak for leak in leaks for text in texts if leak in text]
