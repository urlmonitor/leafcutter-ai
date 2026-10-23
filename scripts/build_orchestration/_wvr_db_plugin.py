"""
MODULE: scripts/build_orchestration/_wvr_db_plugin.py
GOAL: The in-suite half of the database wrong-version check: a pytest plugin (loaded with
    ``-p`` beside ``_kind_plugin``) that puts the SQL definitions into the test database and,
    after the call phase of each database test, reads which definition the database held.
BUSINESS CONTEXT: TQ-500g-2-i. A database suite that re-installs every stored procedure from
    the project's source files each time it starts silently puts the correct code back, so a
    wrong version applied to the file only never reaches the tests. The catalogue, not the file
    on disk, decides whether a run is valid: the wrong version = valid, the code as written =
    invalid (the suite put it back), anything else or unreadable = not run.
ARCHITECTURE: Two doors, one module. As a plugin it reads a JSON config (env
    ``LEAFCUTTER_WVR_DB_CONFIG``: texts to install and to restore, the objects with their normal forms, the
    database tests) and writes its findings to a JSON file (env ``LEAFCUTTER_WVR_DB_OUTPUT``,
    created by the runner through ``tempfile``). As a script (``python _wvr_db_plugin.py
    put-back <config>``) it re-installs the code as written and re-reads the catalogue, printing one
    JSON result. The address comes only from ``db_check.checker.resolve_test_db_address``; it is
    never printed, written or passed on, and driver exception text is never copied (class name
    only). The driver is whichever of psycopg2, psycopg, pg8000 the interpreter can import.
    Known limit (user decision OQ-5 (A)): a re-install inside a test's own uncommitted
    transaction cannot be seen from this separate connection.
    Known limit: a wrong version caught only in setUpClass / setup (a test with no call-phase
    capture) reads as ``not_run`` (conservative), never as a catch.
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any
from urllib.parse import unquote, urlparse

import pytest
from _wvr_sql_objects import ObjectsError, normal, parse_objects  # noqa: F401 -- ObjectsError, parse_objects re-exported

_LOG = logging.getLogger("wrong_version_runner")
CONFIG_ENV = "LEAFCUTTER_WVR_DB_CONFIG"
OUTPUT_ENV = "LEAFCUTTER_WVR_DB_OUTPUT"
DRIVERS = ("psycopg2", "psycopg", "pg8000")
NO_DRIVER = f"no PostgreSQL driver importable in the test interpreter (tried {', '.join(DRIVERS)})"
_KINDS = "p.prokind IN ('f', 'p')"
CATALOGUE_SQL = ("SELECT p.proname, p.prosrc FROM pg_catalog.pg_proc p "
                 f"WHERE p.proname = ANY(%s) AND {_KINDS} AND pg_catalog.pg_function_is_visible(p.oid)")
SCHEMA_SQL = ("SELECT p.proname, p.prosrc FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace "
              f"WHERE p.proname = ANY(%s) AND {_KINDS} AND n.nspname = %s")
_PARAMS = re.compile(r"\[[^\]]*\]$")


def judge(held: dict[str, list[str]], objects: dict[str, dict[str, str]]) -> tuple[str, str]:
    """Compare the held definitions with the objects' two forms; return ``(state, object names)``.

    States: ``wrong`` (every object holds the wrong version), ``original`` (the code as written
    is back in at least one, none is unknown) and ``neither``.
    """
    state: dict[str, str] = {}
    for name, forms in objects.items():
        bodies = held.get(name, [])
        mine = normal(bodies[0]) if len(bodies) == 1 else None
        state[name] = "wrong" if mine == forms["wrong"] else "original" if mine == forms["original"] else "neither"
    unknown = sorted(n for n, s in state.items() if s == "neither")
    back = sorted(n for n, s in state.items() if s == "original")
    if unknown or not back:
        return ("neither", ", ".join(unknown)) if unknown else ("wrong", "")
    return "original", ", ".join(back)


def find_driver() -> tuple[ModuleType | None, str]:
    """Return the first importable PostgreSQL driver module and its name."""
    for name in DRIVERS:
        try:
            return importlib.import_module(name), name
        except ImportError:
            continue
    return None, ""


def _connect(driver: ModuleType, name: str, address: str):  # noqa: ANN202 -- a third-party DB-API connection
    """Open a connection; pg8000 takes keywords, the others the address itself."""
    if name != "pg8000":
        return driver.connect(address)
    parts = urlparse(address)
    return driver.connect(user=unquote(parts.username or ""), password=unquote(parts.password or ""),
                          host=parts.hostname or "localhost", port=parts.port or 5432, database=parts.path.lstrip("/"))


class Database:
    """The test database as the plugin and the put-back use it; never exposes the address."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.status = "ok"
        self.detail = ""
        driver, self._name = find_driver()
        self._driver: Any = driver
        self._address = ""
        if driver is None:
            self.status, self.detail = "no_driver", NO_DRIVER
            return
        scripts = str(Path(__file__).resolve().parents[1])
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        try:
            from db_check.checker import resolve_test_db_address  # noqa: PLC0415 -- deployed beside this package

            self._address = resolve_test_db_address(root)
        except Exception as exc:  # noqa: BLE001 -- any failure means no database; only the class name is kept
            _LOG.warning("the test database address could not be resolved: %s", type(exc).__name__)
            self.status, self.detail = "no_address", f"the test database address could not be resolved ({type(exc).__name__})"

    def install(self, texts: list[str]) -> str:
        """Execute each source text on a fresh connection; return ``""`` or the failure's class name.

        Each text goes with an explicit params argument, so no driver reads a ``%`` in it as a
        placeholder: psycopg2 and psycopg leave a statement alone when it is ``None`` (an empty tuple
        would still be formatted); pg8000 takes an empty tuple.
        """
        params = () if self._name == "pg8000" else None
        try:
            conn = _connect(self._driver, self._name, self._address)
            try:
                for text in texts:
                    conn.cursor().execute(text, params)
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:  # noqa: BLE001 -- driver text can echo the address; keep the class name only
            _LOG.warning("installing the definitions failed: %s", type(exc).__name__)
            return type(exc).__name__
        return ""

    def read(self, objects: dict[str, dict[str, str]]) -> dict[str, list[str]] | str:
        """Read the stored bodies of *objects* on this call's OWN connection; a failure gives its class name.

        An object without a schema is looked up among the functions visible on the search path, an
        object named with a schema in that schema; only functions and procedures count, and a name
        keeps its exact case.
        """
        held: dict[str, list[str]] = {}
        try:
            conn = _connect(self._driver, self._name, self._address)
            try:
                for sql, params in _queries(objects):
                    cur = conn.cursor()
                    cur.execute(sql, params)
                    for proname, body in cur.fetchall():
                        held.setdefault(str(proname), []).append(str(body))
            finally:
                conn.close()
        except Exception as exc:  # noqa: BLE001 -- driver text can echo the address; keep the class name only
            _LOG.warning("reading the catalogue failed: %s", type(exc).__name__)
            return type(exc).__name__
        return held


def _queries(objects: dict[str, dict[str, str]]) -> list[tuple[str, tuple]]:
    """The catalogue queries for *objects*: one for the unqualified names, one per named schema."""
    plain = [name for name, forms in objects.items() if not forms.get("schema")]
    by_schema: dict[str, list[str]] = {}
    for name, forms in objects.items():
        if forms.get("schema"):
            by_schema.setdefault(forms["schema"], []).append(name)
    return ([(CATALOGUE_SQL, (plain,))] if plain else []) + [(SCHEMA_SQL, (names, schema)) for schema, names in by_schema.items()]


def _load_config() -> dict:
    """Read the config named by the environment (empty dict when absent or unreadable)."""
    try:
        with open(os.environ[CONFIG_ENV], encoding="utf-8") as fh:
            return json.load(fh)
    except (KeyError, OSError, ValueError) as exc:
        _LOG.warning("the database plugin config could not be read: %s", type(exc).__name__)
        return {}


class _Session:
    """The plugin's state for one pytest session."""

    def __init__(self) -> None:
        self.config = _load_config()
        self.out: dict = {"status": "error", "detail": "the database plugin had no config", "tests": {}}
        self.db: Database | None = None

    def flush(self) -> None:
        """Write the findings (no address, no driver text) where the runner reads them."""
        try:
            with open(os.environ[OUTPUT_ENV], "w", encoding="utf-8") as fh:
                json.dump(self.out, fh)
        except (KeyError, OSError) as exc:
            _LOG.warning("the database plugin output could not be written: %s", type(exc).__name__)

    def start(self) -> None:
        """Install the definitions at session start, before any test or setUpClass runs."""
        if not self.config:
            return
        self.db = Database(Path(self.config["root"]))
        self.out = {"status": self.db.status, "detail": self.db.detail, "tests": {}}
        if self.db.status == "ok":
            failed = self.db.install(self.config["install"])
            if failed:
                self.out.update(status="install_failed", detail=f"the definitions could not be installed ({failed})")
        self.flush()

    def capture(self, item: pytest.Item) -> None:
        """Read the catalogue once, on its own connection, and record what the database held."""
        if self.db is None or self.out["status"] != "ok" or not self.config.get("read"):
            return
        ident = _PARAMS.sub("", str(Path(str(item.path)).resolve().as_posix()) + "::" + "::".join(item.nodeid.split("::")[1:]))
        if ident not in self.config["db_tests"]:
            return
        held = self.db.read(self.config["objects"])
        if isinstance(held, str):
            entry = {"state": "unreadable", "names": "", "detail": f"the catalogue could not be read ({held})"}
        else:
            state, names = judge(held, self.config["objects"])
            entry = {"state": state, "names": names, "detail": ""}
        self.out["tests"].setdefault(ident, []).append(entry)
        self.flush()


_SESSION: _Session | None = None


def pytest_sessionstart(session: pytest.Session) -> None:  # noqa: ARG001 -- pytest hook signature
    """Install the definitions before any test runs."""
    global _SESSION  # noqa: PLW0603 -- one plugin state per pytest process
    _SESSION = _Session()
    _SESSION.start()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item: pytest.Item):  # noqa: ANN201 -- hookwrapper generator
    """After the test's call phase and before its teardown, capture what the database held."""
    yield
    if _SESSION is not None:
        _SESSION.capture(item)


def put_back(config: dict) -> dict:
    """Re-install the code as written, re-read the catalogue and report; never raises.

    Returns:
        ``{"status": ok|nothing|install_failed|mismatch|reread_failed|unreadable, "names": <object names>}``.
        ``nothing`` means no driver or address exists, so nothing can have been installed.
    """
    db = Database(Path(config["root"]))
    names = ", ".join(config["objects"])
    if db.status != "ok":
        return {"status": "nothing", "names": names}
    if db.install(config["restore"]):
        return {"status": "install_failed", "names": names}
    objects = {n: {"wrong": f["original"], "original": f["original"], "schema": f.get("schema", "")} for n, f in config["objects"].items()}
    held = db.read(objects)
    if isinstance(held, str):
        return {"status": "reread_failed", "names": names}
    state, bad = judge(held, objects)
    return {"status": "ok", "names": ""} if state == "wrong" else {"status": "mismatch", "names": bad or names}


def main(argv: list[str]) -> int:
    """Entry for ``put-back <config>``: print one JSON result line (no address, no driver text)."""
    try:
        with open(argv[1], encoding="utf-8") as fh:
            result = put_back(json.load(fh))
    except (IndexError, OSError, ValueError, KeyError) as exc:
        result = {"status": "unreadable", "names": "", "detail": type(exc).__name__}
    sys.stdout.write(json.dumps(result) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
