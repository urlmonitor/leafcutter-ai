"""
MODULE: scripts/build_orchestration/_wvr_trace_plugin.py
GOAL: The in-suite half of the effect check: a pytest plugin (loaded with ``-p`` into the one baseline
    run, beside ``_kind_plugin`` and, when present, the database plugin) that records which lines of the
    given files each test ran.
BUSINESS CONTEXT: TQ-500g-1-xiv. A wrong version that changes no line a test runs cannot be noticed by
    that test, so the test must not be counted as a survivor. Run-or-not-run is judged per test: a line
    run inside a test's own setup, call or teardown belongs to that test only, and a line run outside
    any test (module import during collection) is recorded under ``""`` and counts for every test.
ARCHITECTURE: Standard library only (coverage.py is not a dependency). ``sys.monitoring`` LINE events
    where the interpreter has them (3.12+), ``sys.settrace`` otherwise. Reads the absolute paths to
    record from env ``LEAFCUTTER_WVR_TRACE_PATHS`` (a JSON list) and writes one JSON file named by env
    ``LEAFCUTTER_WVR_TRACE_OUT``: ``{<abs path>::<test chain>: {<abs path>: [lines]}, "": {...}}``.
    Only code of the given files is observed; every other code location is switched off at its first
    event, so the cost stays small.
"""

from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path

import pytest

PATHS_ENV = "LEAFCUTTER_WVR_TRACE_PATHS"
OUTPUT_ENV = "LEAFCUTTER_WVR_TRACE_OUT"
_TOOL_ID = 4  # sys.monitoring ids 0, 1, 2 and 5 belong to debugger, coverage, profiler and optimizer

_targets: set[str] = set()
_canon: dict[str, str | None] = {}  # co_filename -> canonical target path, or None for code not observed
_lines: dict[str, dict[str, set[int]]] = {"": {}}
_current = ""
_mode = ""


def _canonical(filename: str) -> str | None:
    """Return the target path *filename* names, or ``None`` when it is not one of the given files."""
    if filename not in _canon:
        real = os.path.realpath(filename)
        _canon[filename] = real if real in _targets else None
    return _canon[filename]


def _record(filename: str, line: int) -> bool:
    """Record one executed line of a target file; return False when the file is not a target."""
    path = _canonical(filename)
    if path is None:
        return False
    _lines.setdefault(_current, {}).setdefault(path, set()).add(line)
    return True


def _on_line(code: object, line: int) -> object:
    """``sys.monitoring`` LINE callback: record target lines, switch every other location off."""
    if _record(code.co_filename, line):  # type: ignore[attr-defined]
        return None
    return sys.monitoring.DISABLE


def _global_trace(frame: object, _event: str, _arg: object) -> object:
    """``sys.settrace`` global function: trace only frames of target files."""
    return _local_trace if _canonical(frame.f_code.co_filename) else None  # type: ignore[attr-defined]


def _local_trace(frame: object, event: str, _arg: object) -> object:
    """``sys.settrace`` local function: record each line event."""
    if event == "line":
        _record(frame.f_code.co_filename, frame.f_lineno)  # type: ignore[attr-defined]
    return _local_trace


def _start() -> None:
    """Begin observing (monitoring when available, settrace otherwise)."""
    global _mode
    mon = getattr(sys, "monitoring", None)
    if mon is not None:
        try:
            mon.use_tool_id(_TOOL_ID, "leafcutter_wvr_trace")
        except ValueError:
            mon = None
    if mon is not None:
        mon.register_callback(_TOOL_ID, mon.events.LINE, _on_line)
        mon.set_events(_TOOL_ID, mon.events.LINE)
        _mode = "monitoring"
        return
    sys.settrace(_global_trace)
    threading.settrace(_global_trace)
    _mode = "settrace"


def _stop() -> None:
    """Stop observing."""
    if _mode == "monitoring":
        sys.monitoring.set_events(_TOOL_ID, 0)
        sys.monitoring.register_callback(_TOOL_ID, sys.monitoring.events.LINE, None)
        sys.monitoring.free_tool_id(_TOOL_ID)
    elif _mode == "settrace":
        sys.settrace(None)
        threading.settrace(None)  # type: ignore[arg-type]


def pytest_configure(config: pytest.Config) -> None:
    """Read the paths to observe and start observing before collection imports anything."""
    try:
        paths = json.loads(os.environ.get(PATHS_ENV, "[]"))
    except ValueError as exc:
        print(f"[wvr-trace] unreadable {PATHS_ENV}: {exc}", file=sys.stderr)
        return
    _targets.update(os.path.realpath(p) for p in paths)
    if _targets:
        _start()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item: pytest.Item, nextitem: object):  # noqa: ANN201
    """Attribute every line run during one test's setup, call and teardown to that test alone."""
    global _current
    _current = Path(str(item.path)).resolve().as_posix() + "::" + item.nodeid.partition("::")[2]
    try:
        yield
    finally:
        _current = ""


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Stop observing and write the recorded lines to the output file."""
    out = os.environ.get(OUTPUT_ENV, "")
    if not _mode or not out:
        return
    _stop()
    data = {key: {path: sorted(lines) for path, lines in per.items()} for key, per in _lines.items()}
    try:
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
    except OSError as exc:
        print(f"[wvr-trace] could not write {out}: {exc}", file=sys.stderr)


# ================================================================================
# DECISION HISTORY
# ================================================================================
# - 2026-10-25 20:30 [python-coder]: Created: per-test line trace (sys.monitoring, settrace fallback), import-time
#   lines under "". (#EPIC-OnceANamedWrongVersionIsPreparedAnd/04)
