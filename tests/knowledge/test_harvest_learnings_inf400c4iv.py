"""
MODULE: test_harvest_learnings_inf400c4iv
GOAL: Unit tests for INF-400c-4-iv: an absent declared knowledge-emission
    sink is a no-work run, not a failure.
BUSINESS CONTEXT: Split out of test_harvest_learnings.py (GE-127a-1 file
    -size ratchet) to keep both files under their line limit. See that
    file's module docstring for the harvester's full behavioral contract;
    this file covers only the absent-sink narrowing.
ARCHITECTURE: Mirrors test_harvest_learnings.py's bootstrap (dynamic module
    load of scripts/knowledge/harvest_learnings.py by file path) and its
    `_make_event`/`_write_sink` helpers, since this suite drives the real
    CLI via subprocess and needs real on-disk fixture sinks. Every test
    below drives the real CLI via subprocess (test_rationale: "a direct
    unit test of a resolver function would pass while the CLI still mapped
    absent to the error branch").
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from conftest import load_fixture  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HARVEST_PATH = _REPO_ROOT / "scripts" / "knowledge" / "harvest_learnings.py"

spec = importlib.util.spec_from_file_location("harvest_learnings_inf400c4iv", _HARVEST_PATH)
assert spec is not None and spec.loader is not None, f"could not load spec for {_HARVEST_PATH}"
_mod: Any = importlib.util.module_from_spec(spec)
sys.modules.setdefault("harvest_learnings_inf400c4iv", _mod)
spec.loader.exec_module(_mod)


def _make_event(
    entry_kind: str,
    destination: str,
    ticket: str = "tickets/test.md",
    timestamp: str = "2026-06-05T14:00:00Z",
    agent: str = "python-coder",
    component: str = "knowledge_system",
) -> dict:
    """Return a well-formed knowledge_captured event dict (see
    test_harvest_learnings._make_event for the full rationale)."""
    return {
        "event": "knowledge_captured",
        "timestamp": timestamp,
        "ticket": ticket,
        "agent": agent,
        "component": component,
        "destination": destination,
        "entry_kind": entry_kind,
    }


def _write_sink(path: Path, events: list[dict]) -> None:
    """Write a JSONL sink file from a list of event dicts."""
    with open(path, "w", encoding="utf-8") as fh:
        for ev in events:
            fh.write(json.dumps(ev) + "\n")


def _run_harvest_cli(
    sink: Path, state: Path, extra_args: list[str] | None = None
) -> subprocess.CompletedProcess:
    """Invoke the real harvester CLI as a subprocess (reachability, not import).

    Mirrors the inline `subprocess.run(...)` calls used throughout
    test_harvest_learnings.py, factored out once here since this section
    drives the CLI six times.
    """
    args = [sys.executable, str(_HARVEST_PATH), "--sink", str(sink), "--state", str(state)]
    if extra_args:
        args += extra_args
    return subprocess.run(args, capture_output=True, text=True, timeout=10, check=False)


class TestAbsentSinkExitStatusEqualsTheEmptySinkExitStatus(unittest.TestCase):
    """INF-400c-4-iv: an absent declared sink must exit with exactly the same
    status as an existing-but-empty sink -- the no-work outcome, not an
    error. Asserting equality BETWEEN the two runs (rather than equality to
    the literal 0) is the testable form of "the same outcome"; a future
    change to the empty-sink case must move both together or this test goes
    red (test_rationale).
    """

    def test_absent_sink_exit_status_equals_the_empty_sink_exit_status(self) -> None:
        # covers: INF-400c-4-iv
        # angle: reachability
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            absent_sink = tmp / "never_written.jsonl"
            empty_sink = tmp / "empty.jsonl"
            empty_sink.write_text("", encoding="utf-8")

            absent_proc = _run_harvest_cli(absent_sink, tmp / "absent_state.json")
            empty_proc = _run_harvest_cli(empty_sink, tmp / "empty_state.json")

            self.assertFalse(
                absent_sink.exists(),
                "the CLI invocation itself must not have created the absent sink",
            )
            self.assertEqual(
                absent_proc.returncode,
                empty_proc.returncode,
                "an absent sink must exit with exactly the same status as an "
                "existing-but-empty sink (the no-work outcome, not an error); "
                f"absent stdout={absent_proc.stdout!r} stderr={absent_proc.stderr!r}; "
                f"empty stdout={empty_proc.stdout!r} stderr={empty_proc.stderr!r}",
            )


class TestAbsentSinkReportsZeroReadAndZeroOutstanding(unittest.TestCase):
    """INF-400c-4-iv: with the declared sink absent, the run reports zero
    records read and zero outstanding, and the no-work outcome rather than
    an error outcome."""

    def test_absent_sink_reports_zero_read_and_zero_outstanding(self) -> None:
        # covers: INF-400c-4-iv
        # angle: criterion
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            absent_sink = tmp / "never_written.jsonl"

            proc = _run_harvest_cli(absent_sink, tmp / "state.json")

            self.assertEqual(
                proc.returncode,
                0,
                "a no-work run over an absent sink must exit 0, not an error "
                f"status; stdout={proc.stdout!r} stderr={proc.stderr!r}",
            )
            report = proc.stdout + proc.stderr
            self.assertIn(
                "0 learnings routed",
                report,
                f"the report must show zero records were read/routed; report={report!r}",
            )
            self.assertIn(
                "0 outstanding",
                report,
                f"the report must show zero records outstanding; report={report!r}",
            )


class TestAbsentSinkCreatesNeitherTheSinkNorItsParentDirectory(unittest.TestCase):
    """INF-400c-4-iv: a reader that mkdirs on read turns a misconfigured path
    into a silently-created empty file. Run in a temp tree containing no
    debugging/ directory at all; neither debugging/, debugging/logs/, nor
    the sink file itself may exist afterwards."""

    def test_absent_sink_creates_neither_the_sink_nor_its_parent_directory(self) -> None:
        # covers: INF-400c-4-iv
        # angle: criterion
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            declared_sink = tmp / "debugging" / "logs" / "knowledge_emissions.jsonl"
            self.assertFalse((tmp / "debugging").exists())

            proc = _run_harvest_cli(declared_sink, tmp / "harvest_state.json")

            self.assertFalse(
                (tmp / "debugging").exists(),
                "the reader must not create the sink's parent directory as a "
                f"side effect of finding it absent; stdout={proc.stdout!r}",
            )
            self.assertFalse(
                declared_sink.exists(),
                "the reader must not create the sink file itself as a side "
                f"effect of finding it absent; stdout={proc.stdout!r}",
            )
            # The no-side-effect property alone is already true of today's
            # error-branch code and would pass before this AC's fix lands
            # too, so it is not on its own a specific enough proof of THIS
            # AC. Tie it to the no-work exit status (0, per AC-1) so the
            # test is red until absence is actually split out of the
            # sink-unreadable branch.
            self.assertEqual(
                proc.returncode,
                0,
                "no side effects is necessary but not sufficient: the run "
                "must also report the no-work outcome (exit 0), not an "
                f"error status; stdout={proc.stdout!r} stderr={proc.stderr!r}",
            )


class TestAbsentSinkDoesNotWidenIntoTheOperationalStream(unittest.TestCase):
    """INF-400c-4-iv: in a tree where debugging/logs/agent_telemetry.jsonl
    holds 28 real knowledge records and the declared sink is absent, the run
    must still report zero records read and must write to no destination
    file. Real-artifact seam test: the 28-record fixture is a verbatim
    capture of the real operational stream (see
    test_harvest_learnings.TestFullCorpusAllUnroutable), piped into the real
    consumer via a real on-disk file -- not a hand-typed literal standing in
    for either side of the seam."""

    def test_absent_sink_does_not_widen_into_the_operational_stream(self) -> None:
        # covers: INF-400c-4-iv
        # angle: seam
        events = load_fixture("harvest_learnings/unroutable_corpus_28")
        self.assertEqual(len(events), 28, "fixture drift -- expected 28 events")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            operational_stream = tmp / "debugging" / "logs" / "agent_telemetry.jsonl"
            operational_stream.parent.mkdir(parents=True, exist_ok=True)
            _write_sink(operational_stream, events)

            declared_sink = tmp / "debugging" / "logs" / "knowledge_emissions.jsonl"
            self.assertFalse(declared_sink.exists())

            proc = _run_harvest_cli(declared_sink, tmp / "harvest_state.json")

            report = proc.stdout + proc.stderr
            self.assertIn(
                "0 learnings routed",
                report,
                "the absent declared sink must not be papered over by "
                f"reading the 28-record operational stream instead; report={report!r}",
            )
            self.assertNotIn(
                "28",
                report,
                "the operational stream's 28 records must never be reflected "
                f"in this run's report; report={report!r}",
            )
            for ev in events:
                dest = tmp / ev["destination"]
                self.assertFalse(
                    dest.exists(),
                    f"destination {dest} must not exist -- the operational "
                    "stream must never be substituted for the absent sink",
                )


class TestAbsentSinkReportNamesThePathItLookedFor(unittest.TestCase):
    """INF-400c-4-iv: the reported output on the absent-sink path must
    contain the resolved sink path, and a run over a deliberately wrong path
    must name that wrong path rather than the declared one, so the two runs
    are distinguishable from their reports alone."""

    def test_absent_sink_report_names_the_path_it_looked_for(self) -> None:
        # covers: INF-400c-4-iv
        # angle: criterion
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            declared_sink = tmp / "declared" / "knowledge_emissions.jsonl"
            wrong_sink = tmp / "wrong" / "knowledge_emissions.jsonl"

            declared_proc = _run_harvest_cli(declared_sink, tmp / "state_a.json")
            wrong_proc = _run_harvest_cli(wrong_sink, tmp / "state_b.json")

            declared_report = declared_proc.stdout + declared_proc.stderr
            wrong_report = wrong_proc.stdout + wrong_proc.stderr

            self.assertIn(
                str(declared_sink),
                declared_report,
                "the report must name the exact path it looked for on the "
                f"absent-sink path; report={declared_report!r}",
            )
            self.assertIn(
                str(wrong_sink),
                wrong_report,
                f"report={wrong_report!r}",
            )
            self.assertNotIn(
                str(declared_sink),
                wrong_report,
                "a run over the wrong path must not name the declared path "
                "instead of the one it actually looked for",
            )
            # Naming the path is necessary but not sufficient on its own --
            # today's error branch already logs "Sink file not found:
            # <path>" at ERROR level, so the assertions above would already
            # pass before this AC's fix. Tie the check to the no-work
            # outcome the AC actually requires (exit 0, no ERROR-level
            # framing) so the test is red until absence stops being treated
            # as an error.
            self.assertEqual(
                declared_proc.returncode,
                0,
                "naming the path is not enough on its own: the absent-sink "
                "run must also report the no-work outcome (exit 0), not an "
                f"error status; stdout={declared_proc.stdout!r} "
                f"stderr={declared_proc.stderr!r}",
            )
            self.assertNotIn(
                "ERROR",
                declared_report,
                "the absent-sink path must report a no-work outcome, not an "
                f"ERROR-level message; report={declared_report!r}",
            )


class TestASinkThatExistsButCannotBeReadKeepsItsDistinctNonzeroStatus(unittest.TestCase):
    """INF-400c-4-iv, the must-not-change half. A sink that EXISTS but
    cannot be read (mode 000) must keep its own distinct nonzero status --
    NOT equal to the absent-sink status -- and exits 2 (corrupt state), 3
    (unroutable records retained) and 4 (write failure, outranking 3) must
    all keep their existing meanings, so the absent-case change did not
    renumber anything (test_spec: "the first and last tests are a pair and
    must be read together")."""

    def test_a_sink_that_exists_but_cannot_be_read_keeps_its_distinct_nonzero_status(
        self,
    ) -> None:
        # covers: INF-400c-4-iv
        # angle: failure
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            # 1. The absent-sink baseline this test compares against.
            absent_sink = tmp / "absent.jsonl"
            absent_proc = _run_harvest_cli(absent_sink, tmp / "state_absent.json")

            # 2. A sink that EXISTS but is unreadable (mode 000).
            unreadable_sink = tmp / "unreadable.jsonl"
            unreadable_sink.write_text('{"event": "knowledge_captured"}\n', encoding="utf-8")
            unreadable_sink.chmod(0o000)
            try:
                unreadable_proc = _run_harvest_cli(
                    unreadable_sink, tmp / "state_unreadable.json"
                )
            finally:
                # Restore so TemporaryDirectory cleanup can remove the file.
                unreadable_sink.chmod(0o644)

            self.assertNotEqual(
                unreadable_proc.returncode,
                absent_proc.returncode,
                "a sink that EXISTS but cannot be read must keep a status "
                "distinct from the absent-sink no-work status; "
                f"unreadable stdout={unreadable_proc.stdout!r} "
                f"stderr={unreadable_proc.stderr!r}; "
                f"absent stdout={absent_proc.stdout!r} stderr={absent_proc.stderr!r}",
            )
            self.assertEqual(
                unreadable_proc.returncode,
                1,
                "exit 1 keeps its number, narrowed to 'sink exists but "
                f"cannot be read'; stderr={unreadable_proc.stderr!r}",
            )

            # 3. Corrupt state file -> exit 2, unchanged.
            corrupt_state_sink = tmp / "corrupt_state_sink.jsonl"
            corrupt_state_sink.write_text("", encoding="utf-8")
            corrupt_state = tmp / "corrupt_state.json"
            corrupt_state.write_text("{not valid json", encoding="utf-8")
            corrupt_state_proc = _run_harvest_cli(corrupt_state_sink, corrupt_state)
            self.assertEqual(
                corrupt_state_proc.returncode,
                2,
                f"stderr={corrupt_state_proc.stderr!r}",
            )

            # 4. Unroutable records remain -> exit 3, unchanged.
            unroutable_sink = tmp / "unroutable_sink.jsonl"
            unroutable_event = _make_event(
                entry_kind="never-seen-before-kind", destination=str(tmp / "u.md")
            )
            unroutable_event["text"] = (
                "A genuine learning with a kind the router does not know yet."
            )
            _write_sink(unroutable_sink, [unroutable_event])
            unroutable_proc = _run_harvest_cli(unroutable_sink, tmp / "state_unroutable.json")
            self.assertEqual(
                unroutable_proc.returncode,
                3,
                f"stdout={unroutable_proc.stdout!r}",
            )

            # 5. A destination write failure -> exit 4, outranking 3.
            blocker = tmp / "blocked"
            blocker.write_text("regular file, not a directory", encoding="utf-8")
            write_fail_sink = tmp / "write_fail_sink.jsonl"
            write_fail_event = _make_event(
                entry_kind="adr", destination=str(blocker / "sub" / "x.md")
            )
            write_fail_event["text"] = "A genuine learning whose write will fail."
            _write_sink(write_fail_sink, [write_fail_event])
            write_fail_proc = _run_harvest_cli(write_fail_sink, tmp / "state_write_fail.json")
            self.assertEqual(
                write_fail_proc.returncode,
                4,
                f"stdout={write_fail_proc.stdout!r}",
            )


if __name__ == "__main__":
    unittest.main()
