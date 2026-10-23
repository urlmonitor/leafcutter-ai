"""
MODULE: scripts/build_orchestration/_wvr_db.py
GOAL: The per-run database gate of the wrong-version runner: database tests are run
    only when the configured test database is reachable, and otherwise are reported
    ``not_run`` (never caught, never passed) and leave the work unfinished.
BUSINESS CONTEXT: TQ-500g-2-ii (fail closed, alignment question 2). A database test
    that cannot reach a database fails (or hangs) for the wrong reason, which would
    read as a catch. A project with no ``testing_context.db_connection_test`` (P2), one
    whose setting cannot be parsed or read, or whose database cannot be reached (P3)
    gets ``not_run`` rows that say why; the non-database tests still run as before.
ARCHITECTURE: A test is a database test only when its own AC ``test_spec`` entry says
    ``requires_db: true`` (``_wvr_records.requires_db_names``; never inferred from code).
    :func:`gate` calls ``scripts/db_check/checker.check_test_db(<repo root>)`` ONCE per run,
    the one resolver of the setting. The runner never reads the setting, never builds,
    defaults or passes an address (no flag, no environment variable): the tests resolve it
    themselves with the pytest child's working directory at the repo root. Any status other
    than ``reachable``, and the check failing to run at all, is closed. The row detail is
    ``"<status>: <checker message>"`` (for ``unreachable`` a fixed sentence naming the setting, never the address); the checker's message never holds a password or the
    raw value, and nothing else from the setting is copied here.

    TQ-500g-2-i adds the catalogue step of a run whose alteration changes a ``.sql`` file over a
    database test: :func:`begin` / :func:`begin_baseline` build a :class:`Session` (a temp config and
    a temp findings file; the plugin ``_wvr_db_plugin`` is loaded into the same single pytest run),
    :func:`finish` puts the database back through the plugin's own entry point (``sys.executable``)
    and :func:`judge` turns the findings into the rows: the wrong version held = the row stands; the
    code as written held = ``invalid``; neither / unreadable / no capture = ``not_run``. No address,
    user name or driver text is read or kept here.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import _wvr_db_plugin as plugin
from _wvr_sql_objects import ObjectsError, parse_definitions
from _wvr_scope import UNDONE_NAME, ScopedTest
from _wvr_verdict import row

_LOG = logging.getLogger("wrong_version_runner")
REACHABLE = "reachable"
SETTING = "testing_context.db_connection_test"


@dataclass
class DbGate:
    """The outcome of the one database check of a run."""

    status: str
    message: str

    @property
    def open(self) -> bool:
        """True only when the configured database is reachable."""
        return self.status == REACHABLE

    @property
    def detail(self) -> str:
        """The row detail: ``<status>: <checker message>``; for ``unreachable`` a fixed sentence (no address)."""
        if self.status == "unreachable":
            return f"{self.status}: the configured database could not be reached ({SETTING})"
        return f"{self.status}: {self.message}"


def check(root: Path) -> DbGate:
    """Ask the one resolver whether the configured test database is reachable (fails closed)."""
    scripts = str(Path(__file__).resolve().parents[1])
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    try:
        from db_check.checker import check_test_db  # noqa: PLC0415 -- deployed beside this package; imported only when needed

        report = check_test_db(root)
        return DbGate(str(report["status"]), str(report["message"]))
    except Exception as exc:  # noqa: BLE001 -- any failure of the check means "do not run database tests"
        _LOG.warning("the test database check could not run: %r", exc)
        return DbGate("check_failed", f"the test database check could not run ({type(exc).__name__})")


def _blocked_rows(blocked: list[ScopedTest], detail: str) -> list[dict]:
    """The ``not_run`` rows of the database tests: the baseline and each wrong version they answer for.

    Each extra of a blocked test gets one ``not_run`` row too, but non-blocking (an extra never stops the work).
    """
    rows: list[dict] = []
    for test in blocked:
        names = ["", *(n for n in test.versions.values() if n != UNDONE_NAME), UNDONE_NAME]
        rows += [row(test.label, name, "not_run", detail) for name in names]
        rows += [{**row(test.label, name, "not_run", detail), "blocking": False} for name in test.extras.values()]
    return rows


def gate(tests: list[ScopedTest], db_names: set[str], root: Path) -> tuple[list[ScopedTest], list[dict]]:
    """Split *tests* by the database gate; return ``(tests to run, not_run rows)``.

    Args:
        tests: The in-scope tests whose nodes resolved.
        db_names: The ``test_spec`` names that declare ``requires_db: true``.
        root: The repo root (the git toplevel the runner resolved).

    Returns:
        With no database test, or a reachable database, every test and no rows. Otherwise only the
        non-database tests, and a ``not_run`` blocking row for each database test and run. The check
        is made at most once, and only when some in-scope test is a database test.
    """
    database = [t for t in tests if t.function in db_names]
    if not database:
        return tests, []
    result = check(root)
    if result.open:
        return tests, []
    return [t for t in tests if t not in database], _blocked_rows(database, result.detail)


REDEPLOY = "the suite put the correct code back before the tests ran"
_PUT_BACK_SECONDS = 120


class DbPutBackError(Exception):
    """The database could not be put back to the code as written (the drive stops)."""

    def __init__(self, names: str, *, verified: bool = True) -> None:
        what = "still differs from the code as written" if verified else "could not be verified against the code as written"
        super().__init__(f"the database was not put back: {names} {what}")


@dataclass
class Session:
    """The database side of one pytest run; inert (``child`` is ``None``) when the run needs none."""

    config: str = ""
    output: str = ""
    problem: str = ""
    objects: str = ""
    root: Path | None = None
    verify: bool = False
    paths: list[str] = field(default_factory=list)

    @property
    def active(self) -> bool:
        """True when the run carries the plugin or has a problem to report."""
        return bool(self.config or self.problem)

    @property
    def child(self) -> tuple[str, dict[str, str]] | None:
        """``(plugin module, environment)`` for the pytest child, or ``None`` when inert."""
        if not self.config:
            return None
        return plugin.__name__, {plugin.CONFIG_ENV: self.config, plugin.OUTPUT_ENV: self.output}

    def __enter__(self) -> Session:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.cleanup()

    def cleanup(self) -> None:
        """Remove the temp files of this session."""
        for path in self.paths:
            with contextlib.suppress(OSError):
                os.unlink(path)
        self.paths.clear()

    def fail(self, problem: str) -> Session:
        """Record *problem*: no config is left, so no child gets one and nothing is installed."""
        self.cleanup()
        self.config = self.output = ""
        self.problem = problem
        return self

    def found(self) -> dict:
        """Read the plugin's findings; ``{}`` when the file is absent or unreadable (no capture recorded)."""
        if not self.output:
            return {"status": "problem", "detail": self.problem}
        try:
            with open(self.output, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return {}


def _temp(session: Session, suffix: str, text: str = "") -> str:
    """Create a private temp file (honours TEMP/TMP/TMPDIR) holding *text*; it is listed in *session* at once."""
    fd, path = tempfile.mkstemp(suffix=suffix, prefix="leafcutter_wvr_db_")
    session.paths.append(path)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def _objects(pairs: dict[str, tuple[str, str]]) -> dict[str, dict[str, str]]:
    """Identify the objects of every ``rel: (as written, wrong)`` pair; raise ``ObjectsError(rel)`` when unclear."""
    objects: dict[str, dict[str, str]] = {}
    for rel, (original, wrong) in pairs.items():
        try:
            before, after = parse_definitions(original), parse_definitions(wrong)
        except ObjectsError as exc:
            raise ObjectsError(rel) from exc
        if set(before) != set(after):
            raise ObjectsError(rel)
        objects.update({n: {"original": before[n][1], "wrong": after[n][1], "schema": before[n][0]}
                        for n in before if before[n][1] != after[n][1]})
    return objects


def _make(root: Path, pairs: dict[str, tuple[str, str]], tests: list[ScopedTest], *, wrong: bool) -> Session:
    """Build the session for ``rel: (as written, wrong)`` pairs over the database *tests*."""
    session = Session(root=root, verify=wrong)
    try:
        objects = _objects(pairs)
        if wrong and not objects:
            return session.fail("the wrong version and the code as written are indistinguishable in the catalogue")
        if not wrong:  # the baseline installs the code as written and reads nothing
            objects = {}
        config = {"root": str(root), "install": [pair[1 if wrong else 0] for pair in pairs.values()], "objects": objects,
                  "restore": [pair[0] for pair in pairs.values()], "read": wrong, "db_tests": [t.node.identity for t in tests]}
        session.config = _temp(session, ".json", json.dumps(config))
        session.output = _temp(session, ".json")
        session.objects = ", ".join(objects)
    except ObjectsError as exc:
        return session.fail(f"the database objects of {exc} cannot be identified unambiguously")
    except OSError as exc:
        return session.fail(f"the database check files could not be written ({type(exc).__name__})")
    except BaseException:
        session.cleanup()
        raise
    return session


def _texts(root: Path, rels: list[str]) -> dict[str, str]:
    """The as-written text of each file (``""`` for one that does not exist yet)."""
    out: dict[str, str] = {}
    for rel in rels:
        try:
            out[rel] = (root / rel).read_text(encoding="utf-8")
        except FileNotFoundError:
            out[rel] = ""
    return out


def begin(root: Path, files: dict[str, bytes], tests: list[ScopedTest], db_names: set[str]) -> Session:
    """The session of one wrong-version run: inert unless a ``.sql`` file is altered over a database test."""
    sql = [rel for rel in files if rel.endswith(".sql")]
    database = [t for t in tests if t.function in db_names]
    if not sql or not database:
        return Session()
    try:
        before = _texts(root, sql)
        pairs = {rel: (before[rel], files[rel].decode("utf-8")) for rel in sql}
    except (OSError, UnicodeDecodeError) as exc:
        return Session(problem=f"a .sql file cannot be read as text ({type(exc).__name__})")
    return _make(root, pairs, database, wrong=True)


def begin_baseline(root: Path, rels: list[str], tests: list[ScopedTest], db_names: set[str]) -> Session:
    """The session of the baseline run: the as-written definitions are installed, nothing is read."""
    database = [t for t in tests if t.function in db_names]
    rels = [rel for rel in rels if rel.endswith(".sql")]
    if not rels or not database:
        return Session()
    try:
        before = _texts(root, rels)
    except (OSError, UnicodeDecodeError) as exc:
        return Session(problem=f"a .sql file cannot be read as text ({type(exc).__name__})")
    return _make(root, {rel: (text, text) for rel, text in before.items()}, database, wrong=False)


def _put_back(session: Session) -> dict:
    """Run the plugin's own entry point with this interpreter; its one JSON object, or ``unreadable``."""
    try:
        done = subprocess.run([sys.executable, plugin.__file__, "put-back", session.config], capture_output=True, text=True,
                              timeout=_PUT_BACK_SECONDS, cwd=session.root, check=False)
        result = json.loads(done.stdout.strip().splitlines()[-1])
    except (OSError, subprocess.TimeoutExpired, ValueError, IndexError):
        return {"status": "unreadable", "names": session.objects}
    return result if isinstance(result, dict) else {"status": "unreadable", "names": session.objects}


def finish(session: Session) -> dict:
    """Put the database back after a wrong-version run; return the plugin's findings.

    The put-back installs the code as written and reads the catalogue again. Only "nothing to put
    back" (no driver, no address) and a verified put-back let the drive go on.

    Raises:
        DbPutBackError: The re-install failed, the definition still differs, or the put-back could
            not be verified (whatever the run's own captures showed); names the objects.
    """
    found = session.found()
    if not (session.verify and session.config):
        return found
    result = _put_back(session)
    status = str(result.get("status"))
    if status in ("ok", "nothing"):
        return found
    names = result.get("names")
    raise DbPutBackError(names if isinstance(names, str) and names else session.objects, verified=status in ("install_failed", "mismatch"))


def baseline_problem(session: Session) -> str:
    """Why the baseline run did not have the as-written SQL installed ("" when it did, or needed none)."""
    if not session.active:
        return ""
    found = session.found()
    if found.get("status") == "ok":
        return ""
    return str(found.get("detail") or "no record of the database install was written (crash, timeout or interruption)")


def baseline_rows(tests: list[ScopedTest], session: Session, db_names: set[str]) -> list[dict]:
    """The ``not_run`` rows (baseline and every wrong version) of the database tests when the baseline had no as-written SQL installed."""
    why = baseline_problem(session)
    if not why:
        return []
    detail = f"the code as written was not installed in the test database for this run: {why}"
    return _blocked_rows([t for t in tests if t.function in db_names], detail)


def _verdict_of(entries: list[dict]) -> tuple[str, str, str]:
    """Fold one test's captures into ``(state, object names, detail)``; any non-wrong capture decides."""
    for state in ("neither", "unreadable", "original"):
        hit = [e for e in entries if e["state"] == state]
        if hit:
            return state, hit[0]["names"], hit[0]["detail"]
    return "wrong", "", ""


def _judged(r: dict, entries: list[dict], found: dict) -> dict:
    """The row of one database test given what the catalogue showed (only a valid read keeps it)."""
    if not entries:
        why = found.get("detail") or "no catalogue capture was recorded for this test (crash, timeout or interruption)"
        return row(r["test"], r["wrong_version"], "not_run", why)
    state, names, detail = _verdict_of(entries)
    if state == "wrong":
        return r
    if state == "original":
        return row(r["test"], r["wrong_version"], "invalid", f"{REDEPLOY}: {names} held the code as written")
    return row(r["test"], r["wrong_version"], "not_run", (detail or f"the catalogue held neither version of {names}"))


def judge(rows: list[dict], session: Session, found: dict, tests: list[ScopedTest], db_names: set[str],
          wrong_version: str) -> list[dict]:
    """Replace the rows of the database tests by what the catalogue showed (a cut-short ``not_run`` stays).

    Every database test that was run is judged, also one the run left without a row (a pass is only
    listed for the tests that name the wrong version). A group row "no test in scope failed" is
    dropped when any database test had no valid run.
    """
    if not session.active:
        return rows
    by_label = {t.label: t.node.identity for t in tests if t.function in db_names}
    mine = [row(label, wrong_version, "survived", "") for label in by_label if label not in {r["test"] for r in rows}]
    ok = found.get("status") == "ok"
    out: list[dict] = []
    for r in [*rows, *mine]:
        done = r if r["test"] not in by_label or r["result"] == "not_run" else _judged(
            r, found.get("tests", {}).get(by_label[r["test"]], []) if ok else [], found)
        if done is not r or not any(r is m for m in mine):
            out.append(done)
    if len(out) != len(rows) or any(o is not r for o, r in zip(out, rows)):  # some test had no valid run
        out = [o for o in out if not (o["test"] == "" and o["result"] == "survived")]
    return out
