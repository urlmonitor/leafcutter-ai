"""
MODULE: harvest_status
GOAL: Answer "has the knowledge-routing step run in this tree, and over
    which sink" -- a run-RECENCY signal, distinct from and never derived
    from ``HarvestResult.outstanding`` (the "waiting count").
BUSINESS CONTEXT: Since INF-700c-1/INF-700c-2 landed, a textless record is
    not outstanding and every retained real record is textless, so the
    waiting count reads zero for a healthy loop AND for a loop that has
    never run at all. That count can no longer answer "is this loop alive"
    -- the signal has to come from when the routing step last completed and
    what it read from. This module backs the ``harvest_learnings.py``
    ``--status`` flag (INF-700a-2) that supplies that signal, and the
    last-run marker an ordinary (non-status) completed run writes so a
    later ``--status`` query has something to read.

    Deliberately never reads ``HarvestResult``'s routing counters
    (``skipped_unknown``, ``no_learning_text``, ``outstanding``) -- those
    describe the shape of the corpus, not whether the loop is running
    (INF-700b-3's non-collision rule, which this AC's own it_requirements
    extend to this module's figures too). This module also names no figure
    the capture-health report (INF-700b-3) also produces: that report
    counts AGENT RUNS from the capture-attempt ledger; this module counts a
    single completion timestamp and a sink path, read from the routing
    side. See ``harvest_cli.py``'s ``--status`` help text for the
    reader-facing pointer between the two.
ARCHITECTURE: Helper module for the Knowledge System component
    (docs/architecture/components/knowledge-system.md). Loaded by
    ``harvest_learnings.py`` as a required sibling module (see that file's
    ``_load_required_sibling_module``) rather than a bare top-level import,
    since ``harvest_learnings.py`` is itself loaded via
    ``importlib.util.spec_from_file_location`` by several pre-existing tests
    that do not add ``scripts/knowledge/`` to ``sys.path`` first. The
    build deploys this file to ``<output_root>/scripts/knowledge/
    harvest_status.py`` (see ``build_knowledge_scripts`` in
    ``scripts/build_phases_knowledge.py``), alongside ``harvest_learnings.py``
    itself.

    Deliberately does NOT resolve a sink path itself: ``sink_resolution.
    resolve_sink_for_status`` already owns "where things live", and this
    module's own docstring goal is the marker/status round trip once a sink
    path has been resolved. Callers (``harvest_learnings.main()``) pass the
    already-resolved ``Path`` in.

# DECISION HISTORY
# - 2026-09-23 [python-coder/INF-700a-2]: Initial authoring. Three
#   constraints shape every function here: (1) ``handle_status`` must never
#   create the marker, the marker's parent directory, or the sink's parent
#   directory -- a status query that creates the marker turns the first
#   query into a run that never happened, and "never-run" becomes
#   unreachable forever after (``read_last_run`` checks ``.exists()`` before
#   ever opening the file, and never calls ``.mkdir()``). (2)
#   ``sink_exists`` is a fresh ``Path.exists()`` stat taken at answer time,
#   never inferred from the marker or from a past run's record. (3)
#   ``write_last_run_marker`` is called by ``harvest_learnings.main()``
#   exactly once, immediately after a ``harvest()`` call returns a result --
#   i.e. only on a path that did not hit ``SystemExit(1)``/``SystemExit(2)``
#   first -- so it runs regardless of ``--dry-run`` and regardless of the
#   resulting 0/3/4 exit code, per INF-400c-4-iv's existing treatment of an
#   absent sink as a completed no-work run rather than an error.
"""

from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("harvest_learnings")

#: The literal sentinel reported when the marker has never been written in
#: this tree. Never a zero/epoch timestamp and never an empty string -- both
#: would be indistinguishable from a healthy run at (or near) the epoch.
NEVER_RUN = "never-run"


def read_last_run(marker_path: Path) -> str:
    """Return the last-run marker's ``last_run`` value, or ``NEVER_RUN``.

    Side-effect free: checks existence before ever opening the file, and
    never creates the marker or its parent directory. A marker that exists
    but cannot be read or parsed is treated the same as an absent one --
    logged at WARNING, reported as ``NEVER_RUN`` -- since a corrupt marker
    carries no more information about a completed run than no marker at all,
    and ``--status`` must always answer rather than error.
    """
    if not marker_path.exists():
        return NEVER_RUN
    try:
        raw = marker_path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "Could not read last-run marker %s: %s -- reporting %s",
            marker_path,
            exc,
            NEVER_RUN,
        )
        return NEVER_RUN
    value = data.get("last_run") if isinstance(data, dict) else None
    return value if isinstance(value, str) and value else NEVER_RUN


def write_last_run_marker(marker_path: Path, sink_path: Path) -> None:
    """Write/update *marker_path* with the current UTC time and *sink_path*.

    Called once by ``harvest_learnings.main()`` after any ordinary
    (non-status, non-print-sink) invocation reaches a completed
    ``HarvestResult`` -- regardless of ``--dry-run`` and regardless of the
    resulting exit code. A write failure here must not fail an otherwise
    -completed harvest run, so it is logged and swallowed rather than
    re-raised.
    """
    payload = {"last_run": _utc_now_iso(), "sink": str(sink_path.resolve())}
    try:
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_text(json.dumps(payload), encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not write last-run marker %s: %s", marker_path, exc)


def handle_status(sink_path: Path, marker_path: Path) -> int:
    """Print the ``--status`` JSON payload to stdout and return 0, always.

    *sink_path* must already be resolved by the caller (see
    ``sink_resolution.resolve_sink_for_status``) -- this function owns only
    the marker read and the fresh existence stat, never sink resolution
    itself. Never creates the marker, the marker's parent directory, or the
    sink's parent directory.
    """
    payload: dict[str, Any] = {
        "last_run": read_last_run(marker_path),
        "sink": str(sink_path.resolve()),
        "sink_exists": sink_path.exists(),
    }
    print(json.dumps(payload))
    return 0


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string.

    Pure function (no I/O, no shared-state mutation): the clock read is a
    side effect of ``datetime.now``, not of this function's own logic, and
    the project error-handling policy's "no try/except on pure internal
    functions" rule applies to control flow this function owns, not to the
    stdlib clock itself.
    """
    return datetime.datetime.now(datetime.timezone.utc).isoformat()
