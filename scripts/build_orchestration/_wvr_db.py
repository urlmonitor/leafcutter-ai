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
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path

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


def _blocked_rows(blocked: list[ScopedTest], gate_result: DbGate) -> list[dict]:
    """The ``not_run`` rows of the database tests: the baseline and each wrong version they answer for.

    Each extra of a blocked test gets one ``not_run`` row too, but non-blocking (an extra never stops the work).
    """
    detail = gate_result.detail
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
    return [t for t in tests if t not in database], _blocked_rows(database, result)
