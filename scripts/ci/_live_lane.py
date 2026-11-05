"""
MODULE: _live_lane
GOAL: Everything specific to the live-database lane of the post-merge run: the
    reachability check that precedes any test, the one classification of a lane
    report into passed / failed / unreachable skips / other skips, the lane's own
    verdict object (``live_database``) and its merge into the run's combined verdict.
BUSINESS CONTEXT: TQ-600a-13-xxi / -xxii / -xxiii / -xxv. The live-database tests skip
    when no database is reachable, which is right in the per-PR shards and wrong in
    the lane that exists to supply one. So here a skip is never a pass, a database
    that never answered (or answered a probe and then refused the first connection)
    ends the lane as ``live_database_startup`` with no failing node ids, and a test
    that skipped for want of a database ends it as ``live_database_unreachable``.
    The fix proof of -xxv judges live tests with ``classify_live_results`` too, so the
    rule is stated once.
ARCHITECTURE: Pure functions except ``check_database`` (TCP connects) and
    ``write_unreachable_report`` / ``stamp_reachability`` (one report file). The caller
    ``post_merge_suite`` hands in its own ``execute_lane`` so this module never imports
    it. ``live_verdict`` is the only thing the verdict builder calls; ``merge_verdicts``
    ranks did_not_complete above red above green. The three disposable database
    instances (``INSTANCES``) are defined once, for the workflow copies and the fix
    proof's start step to match. Stdlib-only apart from ``_post_merge_stages`` and
    ``_flaky_window``.
"""

from __future__ import annotations

import json
import logging
import socket
import time
from collections.abc import Mapping
from pathlib import Path

from scripts.ci._flaky_window import flaky_fields
from scripts.ci._post_merge_stages import (
    FAILED_STATES,
    REPORT_UNREADABLE,
    STAGE_CANCELLED,
    STAGE_LIVE_STARTUP,
    STAGE_LIVE_UNREACHABLE,
    STAGE_MOSTLY_SKIPPED,
    STAGE_NOTHING_PASSED,
    STAGE_UNKNOWN,
    STAGE_UNREADABLE,
    report_stage,
)

logger = logging.getLogger("post_merge_suite")

UNREACHABLE = "live database unreachable"  # a no-database skip reason STARTS with this; owned here, used by the tests
SELECTION = "manual or not manual"  # every test of the live folder, the default `-m` deselection overridden
# Set to "1" only in a live-lane pytest session, after its database check passed (TQ-600a-13-xxvii): a test that needs the
# lane's databases skips without it, instead of failing in the correctness lane, which selects `manual` tests too.
LANE_MARKER = "POST_MERGE_LIVE_LANE"


def lane_environ(environ: Mapping[str, str]) -> dict[str, str]:
    """The environment of a live-lane pytest session: ``environ`` plus the lane marker."""
    return {**environ, LANE_MARKER: "1"}

DEFAULT_ADDRESS = "127.0.0.1:17687"
DEFAULT_STARTUP_LIMIT = 300.0
SECOND_CONNECTION_LIMIT = 3.0
HOLD_SECONDS = 0.3  # how long the first connection is held before it is judged alive
INSTANCES = (  # image, host port, credential, memory: the Proof-of-done job's three instances, copied by the workflows
    {"name": "knowledge-retrieval", "image": "neo4j:5.26-community", "port": 17687, "auth": "neo4j/leafcutter-local-tests"},
    {"name": "knowledge-domain", "image": "neo4j:5.26-community", "port": 18087, "auth": "neo4j/leafcutter-domain-tests"},
    {"name": "knowledge-native", "image": "neo4j:5.26-community", "port": 18088, "auth": "neo4j/leafcutter-native-tests"},
)
MEMORY = {"heap_initial": "256m", "heap_max": "512m", "pagecache": "128m"}


# --------------------------------------------------------------------------- the one classification
def classify_live_results(report: dict | None) -> dict:
    """Classify a lane report into ``{passed, failed, unreachable_skips, skipped: [{id, reason}]}`` (ids sorted).

    A skip is never a pass. A skip whose reason STARTS with ``UNREACHABLE`` is an unreachable skip; any other skip
    is an ordinary one, named with its reason. A ``failed`` or ``error`` result is failed.
    """
    results = (report or {}).get("results") or {}
    reasons = (report or {}).get("skip_reasons") or {}
    skipped = [i for i, status in results.items() if status == "skipped"]
    unreachable = [i for i in skipped if str(reasons.get(i, "")).startswith(UNREACHABLE)]
    return {
        "passed": sorted(i for i, status in results.items() if status == "passed"),
        "failed": sorted(i for i, status in results.items() if status in FAILED_STATES),
        "unreachable_skips": sorted(unreachable),
        "skipped": [{"id": i, "reason": str(reasons.get(i, ""))} for i in sorted(skipped) if i not in unreachable],
    }


def _reachable(report: dict | None) -> bool:
    """False only when the lane recorded a failed reachability result (a report without one is not a start-up ending)."""
    reach = (report or {}).get("reachability")
    return not (isinstance(reach, dict) and reach.get("reachable") is False)


def without_targets(command: list[str]) -> list[str]:
    """``command`` minus its test path arguments (existing files or folders), so a retry runs exactly its node ids.

    A folder left in the command would collect the whole folder again beside the ids. The ``-m pytest`` module name is kept.
    """
    return [t for i, t in enumerate(command) if i == 0 or t.startswith("-") or command[i - 1] == "-m" or not Path(t).exists()]


# --------------------------------------------------------------------------- the reachability check
def startup_limit(environ: Mapping[str, str]) -> float:
    """The seconds the lane waits for its database: ``LIVE_DB_STARTUP_LIMIT`` or the default; ValueError names the variable when it is malformed."""
    raw = environ.get("LIVE_DB_STARTUP_LIMIT", DEFAULT_STARTUP_LIMIT)
    message = f"LIVE_DB_STARTUP_LIMIT must be a number of seconds, got {raw!r}"
    try:
        limit = float(raw)
    except ValueError as exc:
        raise ValueError(message) from exc
    if not limit >= 0:  # negative, or NaN (every comparison with NaN is False)
        raise ValueError(message)
    return limit


def _connect(host: str, port: int, deadline: float) -> socket.socket | None:
    """A connected socket to ``host:port``, trying until ``deadline`` (monotonic); None when none was made."""
    while True:
        try:
            return socket.create_connection((host, port), timeout=2.0)
        except OSError as exc:
            failure = exc
        if time.monotonic() >= deadline:
            logger.warning("live database %s:%s not reachable: %s", host, port, failure)
            return None
        time.sleep(0.2)


def check_database(address: str, limit: float) -> dict:
    """Return ``{"reachable": bool, "detail": str}``: the address answers a probe AND accepts a first connection.

    A probe that passes is not trusted by itself: it is followed by a second, real connection that is held while it
    is made. ``limit`` seconds bound the wait for the probe; the second connection is given ``SECOND_CONNECTION_LIMIT``.
    """
    host, _, port = address.rpartition(":")
    try:
        number = int(port)
    except ValueError:
        return {"reachable": False, "detail": f"{address!r} is not host:port"}
    probe = _connect(host or "127.0.0.1", number, time.monotonic() + max(0.0, limit))
    if probe is None:
        return {"reachable": False, "detail": f"no answer from {address} within {limit:g}s"}
    probe.close()
    connection = _connect(host or "127.0.0.1", number, time.monotonic() + SECOND_CONNECTION_LIMIT)
    if connection is None:
        return {"reachable": False, "detail": f"{address} answered a probe, then refused the first connection"}
    with connection:  # a connection that is accepted and then reset (a listener that went away) is not a connection
        time.sleep(HOLD_SECONDS)
        connection.setblocking(False)
        try:
            alive = connection.recv(1, socket.MSG_PEEK) != b""
        except BlockingIOError:
            alive = True  # nothing sent and nothing closed: a server waiting for the client to speak
        except OSError as exc:
            logger.warning("the first connection to %s was reset: %s", address, exc)
            alive = False
    return {"reachable": True, "detail": ""} if alive else {"reachable": False, "detail": f"{address} answered a probe, then reset the first connection"}


def write_unreachable_report(path: Path, reach: dict, runner: str | None) -> None:
    """Write the report of a lane that executed no test because its database was unreachable."""
    payload: dict[str, object] = {"runner": runner, "exitstatus": 0, "expected": 0, "ran": 0, "collection_errors": [], "results": {}, "skip_reasons": {}, "reachability": reach}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.warning("cannot write the live report %s: %s", path, exc)
        raise


def stamp_reachability(path: Path, reach: dict) -> None:
    """Add the (successful) reachability result to the report the session wrote."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["reachability"] = reach
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except (OSError, ValueError) as exc:
        logger.warning("cannot add the reachability result to %s: %s", path, exc)
        raise


# --------------------------------------------------------------------------- the lane's verdict
def _startup_stage(first: dict | None, retry: dict | None, ctx: dict) -> str | None:
    """The stage the dependency results and the reachability results alone decide, or None."""
    run_result, retry_result = ctx["run_result"], ctx["retry_result"]
    if "cancelled" in (run_result, retry_result):
        return STAGE_CANCELLED
    if first is None:
        if ctx["first_state"] == REPORT_UNREADABLE:
            return STAGE_UNREADABLE
        return {"failure": STAGE_LIVE_STARTUP, "success": STAGE_UNREADABLE}.get(run_result, STAGE_UNKNOWN)
    if run_result not in ("", "success"):
        return STAGE_UNKNOWN
    if not _reachable(first) or not _reachable(retry):
        return STAGE_LIVE_STARTUP
    return None


def _retry_stage(failures: list[str], retry: dict | None, retry_result: str) -> str | None:
    """The stage of a live retry that did not confirm the first-run failures, or None."""
    if not failures:
        return None
    if retry_result == STAGE_UNKNOWN:
        return STAGE_UNKNOWN
    if retry_result == "failure":
        return STAGE_LIVE_STARTUP  # the retry machine's database never became healthy: its job failed before any step
    if retry_result == "success" and retry is None:
        return STAGE_UNREADABLE
    return None


def _stage(first: dict | None, retry: dict | None, ctx: dict, failures: list[str], unreachable: list[str]) -> str | None:
    """The stage at which the live lane stopped, or None when it ran to completion."""
    early = _startup_stage(first, retry, ctx)
    if early or first is None:
        return early
    content = report_stage(first)
    content = None if content == STAGE_MOSTLY_SKIPPED else content  # an ordinary skip alone neither fails nor aborts the lane
    if content and content != STAGE_NOTHING_PASSED:
        return content
    if unreachable:
        return STAGE_LIVE_UNREACHABLE
    return content or _retry_stage(failures, retry, ctx["retry_result"])


def _retried_results(failed: list[str], retry: dict | None) -> dict:
    """The retry's result for each first-run failure (None when the retry has no result for it)."""
    results = (retry or {}).get("results", {})
    return {i: results.get(i) for i in failed}


def _merged_skips(first_skips: list[dict], retry_skips: list[dict], retried: dict) -> dict:
    """The ordinary skips by id: the first run's, overlaid with the retry's skips of retried failures."""
    skips = {s["id"]: s for s in first_skips}
    skips.update({s["id"]: s for s in retry_skips if s["id"] in retried})
    return skips


def live_verdict(first: dict | None, retry: dict | None, ctx: dict, history: list | None, tunables: dict) -> dict:
    """Build the ``live_database`` object from the live first-run and retry reports (None = absent).

    ``ctx`` carries ``run_result``, ``retry_result`` and ``first_state``. Skips are never passes: only first-run
    passes are ``passed``, only executed-to-a-result tests are ``collected_ids``. A first-run failure is
    passed-on-retry only when the retry passed it; a retry that did not pass it (a skip included) leaves it failing, unless
    the retry skip is the no-database one, which ends the lane as did_not_complete instead. A lane that stopped at the
    start-up stage names no failing test.
    """
    usable = first if first is not None and _reachable(first) and _reachable(retry) else None
    one, two = classify_live_results(usable), classify_live_results(retry if usable else None)
    retried = _retried_results(one["failed"], retry) if usable else {}
    passed_on_retry = [i for i in one["failed"] if retried[i] == "passed"]
    unreachable = sorted({*one["unreachable_skips"], *(i for i in two["unreachable_skips"] if i in retried)})
    failing = [i for i in one["failed"] if retried[i] != "passed" and i not in unreachable]  # a retry skip never confirms a pass; only the no-database skip ends the lane instead
    skips = _merged_skips(one["skipped"], two["skipped"], retried)
    stage = _stage(first, retry, ctx, one["failed"], unreachable)
    failing = [] if stage == STAGE_LIVE_STARTUP else failing
    executed = sorted([*one["passed"], *one["failed"]])
    window, _read, repeated = flaky_fields(passed_on_retry, [(e or {}).get("live_database") for e in history or []], tunables, escalate=not stage)
    verdict = "did_not_complete" if stage else ("red" if failing or repeated else "green")
    return {
        "verdict": verdict, "stage": stage, "collected": len(executed), "collected_ids": executed, "passed": one["passed"],
        "first_run_failures": one["failed"], "failing": failing, "passed_on_retry": passed_on_retry,
        "pass_on_retry_window": window, "repeated_pass_on_retry": repeated,
        "skipped": [skips[i] for i in sorted(skips)], "unreachable_skips": unreachable,
        "run_runner": (first or {}).get("runner"), "retry_runner": (retry or {}).get("runner"),
    }


def merge_verdicts(correctness: dict, live: dict | None) -> dict:
    """The combined ``{verdict, stage}``: did_not_complete (correctness lane first) outranks red outranks green."""
    if live is None:
        return {"verdict": correctness["verdict"], "stage": correctness["stage"]}
    if correctness["verdict"] == "did_not_complete":
        return {"verdict": "did_not_complete", "stage": correctness["stage"]}
    if live["verdict"] == "did_not_complete":
        return {"verdict": "did_not_complete", "stage": live["stage"]}
    red = "red" in (correctness["verdict"], live["verdict"])
    return {"verdict": "red" if red else "green", "stage": None}
