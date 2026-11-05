"""
MODULE: unit_tests/build_orchestration/_tq500g2i_standin_pg.py
GOAL: The stand-in PostgreSQL DB-API driver of the TQ-500g-2-i tests (user decision OQ-2 (A):
    no live database; CI has no server and leafcutter ships no driver).
BUSINESS CONTEXT: The catalogue is a JSON file (``TQ_G2I_CATALOG``): ``{function name: the CREATE text}``.
    Every connection, install, catalogue read and refusal is appended to ``TQ_G2I_EVENTS``.
ARCHITECTURE: Copied (not imported) into a scratch driver directory that is put on the pytest
    child's import path, as ``standin_pg`` and, unless a test removes it, as ``psycopg2``.
    - A statement with CREATE [OR REPLACE] FUNCTION/PROCEDURE installs its text under its name
      (a quoted name keeps its case, an unquoted one is lower-cased, as PostgreSQL does).
    - A statement naming pg_proc / pg_get_functiondef / pg_catalog / information_schema.routines
      is a catalogue read: one row per stored function whose name occurs in the statement or its
      parameters (all when none does). Select-list columns naming proname / routine_name give the
      name, prosrc / routine_definition give the text between the dollar quotes, anything else the
      whole stored text.
    - ``SELECT fn_refresh_due(<bool>, <bool>)`` evaluates the stored function: its body returns
      ``refresh_due AND retry_due`` when it contains "AND retry_due", otherwise ``refresh_due``.
    - TQ_G2I_FAIL_READ=1 makes every catalogue read raise an error whose TEXT holds the address.
    - TQ_G2I_FAIL_READ=run (opt-in) fails a catalogue read ONLY inside a wrong-version run: not in the
      ``put-back`` subprocess and only while the stored fn_refresh_due is the wrong code (so the baseline
      and the put-back re-read succeed -- a transient failure).
    - TQ_G2I_REFUSE=1 silently ignores an install of the correct code over the wrong one.
    Opt-in switches added by the review-fix tests (all off unless set; the behaviour above is unchanged):
    - A catalogue read whose parameters start with a list matches ``proname = ANY(<list>)`` EXACTLY
      (case-sensitive; ``lower(`` in the query compares lower-cased). Without a list parameter the
      old "name occurs in the statement" rule applies.
    - TQ_G2I_EXTRA_ROWS=<json file>: a list of extra catalogue rows ``{proname, prosrc, visible, prokind}``
      (visible defaults true, prokind "f"). A row is dropped only when the WHERE part of the query
      holds ``pg_function_is_visible`` (visible false) or a ``prokind`` predicate that excludes its
      kind; select-list columns ``prokind`` / ``pg_function_is_visible(...)`` return those values.
    - TQ_G2I_PUTBACK=crash|noparse|notobject|readfail acts only inside the ``put-back`` subprocess:
      exit with no output / print a non-JSON line / print ``5`` at the first connection, or raise on the read.
    - TQ_G2I_PLUGIN_INSTALL_FAIL=1 makes a CREATE executed from a ``_wvr_db*`` module raise.
    - TQ_G2I_PARAMSTYLE=format: a text holding ``%`` executed by a ``_wvr_db*`` module without a
      params argument raises (pg8000-like).
    - TQ_G2I_BREAK_RESTORE=<wrong-version-runs dir>: installing the wrong code deletes the gate copies.
"""

from __future__ import annotations

import glob
import itertools
import json
import os
import re
import sys

_COUNTER = itertools.count(1)
_NOARG = object()
_MARKERS = ("pg_proc", "pg_get_functiondef", "pg_catalog", "information_schema.routines")
_CREATE = re.compile(r"create\s+(?:or\s+replace\s+)?(?:function|procedure)\s+([\w.\"]+)", re.I)
_EVAL = re.compile(r"select\s+([\w.]+)\(\s*(true|false)\s*,\s*(true|false)\s*\)", re.I)
_KIND = re.compile(r"prokind\s*(not\s+in|in|<>|!=|=)\s*(\([^)]*\)|'[a-z]')")


def _event(**fields) -> None:
    fields["pid"] = os.getpid()
    with open(os.environ["TQ_G2I_EVENTS"], "a", encoding="utf-8") as fh:
        fh.write(json.dumps(fields) + "\n")


def _load() -> dict:
    try:
        with open(os.environ["TQ_G2I_CATALOG"], encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _save(catalog: dict) -> None:
    with open(os.environ["TQ_G2I_CATALOG"], "w", encoding="utf-8") as fh:
        json.dump(catalog, fh)


def _short(name: str) -> str:
    last = name.split(".")[-1]
    return last.strip('"') if last.startswith('"') else last.lower()


def _body(text: str) -> str:
    parts = text.split("$$")
    return parts[1] if len(parts) >= 3 else text


def _from_plugin() -> bool:
    frame = sys._getframe(1)
    while frame is not None:
        if os.path.basename(frame.f_code.co_filename).startswith("_wvr_db"):
            return True
        frame = frame.f_back
    return False


def _putback_mode() -> str:
    return os.environ.get("TQ_G2I_PUTBACK", "") if "put-back" in sys.argv else ""


def _extra_rows() -> list[dict]:
    try:
        with open(os.environ["TQ_G2I_EXTRA_ROWS"], encoding="utf-8") as fh:
            return json.load(fh)
    except (KeyError, OSError, ValueError):
        return []


def _list_param(params):
    if isinstance(params, (tuple, list)) and params and isinstance(params[0], (list, tuple)):
        return [str(g) for g in params[0]]
    return None


def _name_matches(name: str, low: str, params) -> bool:
    given = _list_param(params)
    if given is None:
        return name.lower() in f"{low} {str(params).lower()}"
    if "lower(" in low:
        return name.lower() in [g.lower() for g in given]
    return name in given


def _kind_ok(kind: str, where: str) -> bool:
    hit = _KIND.search(where)
    if not hit:
        return True
    letters = re.findall(r"'([a-z])'", hit.group(2))
    negated = re.sub(r"\s+", " ", hit.group(1)) in ("not in", "<>", "!=")
    return (kind not in letters) if negated else (kind in letters)


def _column(col: str, row: dict):
    if "pg_function_is_visible" in col:
        return row["visible"]
    if "prokind" in col:
        return row["kind"]
    if "proname" in col or "routine_name" in col:
        return row["name"]
    if "prosrc" in col or "routine_definition" in col:
        return row["body"]
    return row["text"]


class _Cursor:
    def __init__(self, conn: "_Conn") -> None:
        self._conn = conn
        self._rows: list[tuple] = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> None:
        return None

    def close(self) -> None:
        return None

    def execute(self, sql, params=_NOARG) -> None:
        given = params is not _NOARG
        params = params if given else None
        low = str(sql).lower()
        self._rows = []
        self._plugin_refusals(str(sql), given)
        if any(marker in low for marker in _MARKERS):
            self._read_catalogue(str(sql), low, params)
        elif _CREATE.search(str(sql)):
            self._install(str(sql))
        else:
            hit = _EVAL.search(str(sql))
            if hit:
                self._rows = [(self._evaluate(hit.group(1), hit.group(2).lower() == "true", hit.group(3).lower() == "true"),)]

    def _plugin_refusals(self, sql: str, given: bool) -> None:
        if os.environ.get("TQ_G2I_PARAMSTYLE") == "format" and not given and "%" in sql and _from_plugin():
            _event(ev="percent_refused", conn=self._conn.tq_id)
            msg = "format paramstyle: a % in the text was executed without a params argument"
            raise RuntimeError(msg)
        if _CREATE.search(sql) and os.environ.get("TQ_G2I_PLUGIN_INSTALL_FAIL") == "1" and _from_plugin():
            _event(ev="install_failed_by_standin", conn=self._conn.tq_id)
            msg = f"permission denied while installing over {self._conn.dsn}"
            raise RuntimeError(msg)

    def _install(self, sql: str) -> None:
        matches = list(_CREATE.finditer(sql))
        catalog = _load()
        for i, match in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(sql)
            name, text = _short(match.group(1)), sql[match.start():end]
            held = catalog.get(name, "")
            if os.environ.get("TQ_G2I_REFUSE") == "1" and held and "AND retry_due" not in held and "AND retry_due" in text:
                _event(ev="install_refused", conn=self._conn.tq_id, name=name)
                continue
            catalog[name] = text
            _event(ev="install", conn=self._conn.tq_id, name=name, wrong="AND retry_due" not in text)
            if "AND retry_due" not in text and name == "fn_refresh_due":
                self._break_restore()
        _save(catalog)

    def _break_restore(self) -> None:
        gate = os.environ.get("TQ_G2I_BREAK_RESTORE")
        for path in glob.glob(os.path.join(gate, "*", "copy-*")) if gate else []:
            os.unlink(path)
            _event(ev="restore_broken", conn=self._conn.tq_id)

    def _read_catalogue(self, sql: str, low: str, params) -> None:
        _event(ev="catalog_read", conn=self._conn.tq_id)
        if os.environ.get("TQ_G2I_FAIL_READ") == "1" or _putback_mode() == "readfail" or self._run_read_fails():
            _event(ev="read_raised", conn=self._conn.tq_id)
            msg = f"could not read the catalogue over {self._conn.dsn} (password rejected)"
            raise RuntimeError(msg)
        select = re.search(r"select\s+(.*?)\s+from", low, re.S)
        columns = [c.strip() for c in select.group(1).split(",")] if select else []
        where = low.split(" where ", 1)[1] if " where " in low else ""
        for row in self._candidates(low, params):
            if "pg_function_is_visible" in where and not row["visible"]:
                continue
            if _kind_ok(row["kind"], where):
                self._rows.append(tuple(_column(c, row) for c in columns) if columns else (row["text"],))

    @staticmethod
    def _run_read_fails() -> bool:
        if os.environ.get("TQ_G2I_FAIL_READ") != "run" or "put-back" in sys.argv:
            return False
        held = _load().get("fn_refresh_due", "")
        return bool(held) and "AND retry_due" not in held

    @staticmethod
    def _candidates(low: str, params) -> list[dict]:
        rows = [{"name": n, "text": t, "body": _body(t), "visible": True, "kind": "f"} for n, t in _load().items()]
        rows += [{"name": e["proname"], "text": e["prosrc"], "body": e["prosrc"], "visible": e.get("visible", True),
                  "kind": e.get("prokind", "f")} for e in _extra_rows()]
        picked = [r for r in rows if _name_matches(r["name"], low, params)]
        return picked if (picked or _list_param(params) is not None) else rows

    @staticmethod
    def _evaluate(name: str, refresh_due: bool, retry_due: bool) -> bool:
        text = _load().get(_short(name), "")
        return (refresh_due and retry_due) if "AND retry_due" in text else refresh_due

    def fetchone(self):
        return self._rows.pop(0) if self._rows else None

    def fetchall(self) -> list[tuple]:
        rows, self._rows = self._rows, []
        return rows

    def fetchmany(self, size: int = 1) -> list[tuple]:
        rows, self._rows = self._rows[:size], self._rows[size:]
        return rows

    def __iter__(self):
        return iter(self.fetchall())


class _Conn:
    autocommit = False

    def __init__(self, dsn) -> None:
        self.dsn = dsn
        self.tq_id = f"{os.getpid()}-{next(_COUNTER)}"

    def cursor(self, *_args, **_kwargs) -> _Cursor:
        return _Cursor(self)

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None

    def close(self) -> None:
        return None

    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> None:
        return None


def connect(dsn=None, *_args, **_kwargs) -> _Conn:
    mode = _putback_mode()
    if mode in ("crash", "noparse", "notobject"):
        _event(ev="putback_" + mode)
        sys.stdout.write({"noparse": "no json here\n", "notobject": "5\n"}.get(mode, ""))
        sys.stdout.flush()
        os._exit(7 if mode == "crash" else 0)
    conn = _Conn(dsn)
    _event(ev="connect", conn=conn.tq_id, address=dsn)
    return conn
