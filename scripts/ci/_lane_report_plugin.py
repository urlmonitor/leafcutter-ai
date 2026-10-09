"""
MODULE: _lane_report_plugin
GOAL: A tiny pytest plugin that writes the machine-readable per-test report of
    one execution: ``{"runner": <name>, "exitstatus": <int>, "expected": <int>,
    "results": {<full node id>: <status>}}`` with status ``passed`` | ``failed``
    | ``skipped``. ``exitstatus`` and ``expected`` (tests selected for the
    session) let the verdict tell a lane that finished from one that was cut short.
BUSINESS CONTEXT: TQ-600a-13-ii. The post-merge verdict must come from per-test
    results, never from pytest's exit status alone: pytest.ini's addopts carries
    ``--continue-on-collection-errors`` and exit 5 (nothing collected) is not a
    failure status. But a report written by an aborted session (pytest.exit(),
    an interrupt, an internal error) is partial, so the exit status is recorded
    too and the verdict refuses to call a partial lane green. The node ids are taken verbatim from pytest, so the retry job
    can re-execute exactly the ids the first execution reported, with no
    reconstruction from a JUnit classname.
ARCHITECTURE: Loaded by ``scripts/ci/post_merge_suite.py`` with
    ``-p scripts.ci._lane_report_plugin --lane-report <path>`` appended to the
    lane's pytest command, so the literal ``-m`` selection stays in the workflow
    file. Stdlib-only. A collection error is recorded as a failed entry under
    the collected file's node id, so a file that failed to import cannot vanish
    from the verdict.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_RANK = {"passed": 0, "skipped": 1, "failed": 2}


def pytest_addoption(parser) -> None:
    """Register ``--lane-report <path>``: where to write the per-test report."""
    parser.getgroup("lane report").addoption(
        "--lane-report", dest="lane_report", default=None, help="write the per-test lane report JSON here"
    )


def pytest_configure(config) -> None:
    """Attach the recorder when ``--lane-report`` was given."""
    path = config.getoption("lane_report", default=None)
    if path:
        config.pluginmanager.register(_Recorder(Path(path)), "lane-report-recorder")


def _status(report) -> str:
    """Map one pytest report to passed / failed / skipped."""
    if report.failed:
        return "failed"
    return "skipped" if report.skipped else "passed"


class _Recorder:
    """Collects the worst status seen for each node id and writes the report at session end."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.results: dict[str, str] = {}
        self.ran: set[str] = set()

    def _record(self, node_id: str, status: str) -> None:
        current = self.results.get(node_id)
        if current is None or _RANK[status] > _RANK[current]:
            self.results[node_id] = status

    def pytest_runtest_logreport(self, report) -> None:
        """Fold the setup, call and teardown reports of one test into one status."""
        self.ran.add(report.nodeid)
        self._record(report.nodeid, _status(report))

    def pytest_collectreport(self, report) -> None:
        """Record a collection error as a failed entry; a clean collection records nothing."""
        if report.failed:
            self._record(report.nodeid or "<collection>", "failed")

    def pytest_sessionfinish(self, session, exitstatus) -> None:
        """Write the report; an unwritable report is an error, never a silent pass.

        ``expected`` is the number of tests selected, and ``ran`` how many reported, so a session
        cut short by pytest.exit() (which may leave the exit status at 0) is still visible.
        """
        payload = {
            "runner": os.environ.get("RUNNER_NAME"),
            "exitstatus": int(exitstatus),
            "expected": int(getattr(session, "testscollected", 0)),
            "ran": len(self.ran),
            "results": dict(sorted(self.results.items())),
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError as exc:
            print(f"lane report: cannot write {self.path}: {exc}", file=sys.stderr)
            raise
