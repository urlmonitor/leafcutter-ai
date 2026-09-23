"""
MODULE: tests/knowledge/test_inf_700a_2.py
GOAL: RED behavioral test baseline for INF-700a-2 — "A loop that has never
    run is distinguishable from a loop with nothing to do".

AC: docs/acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700a-2.yaml

CONTRACT THIS FILE ESTABLISHES FOR python-coder (TDD: this is the spec):

  Since INF-700c-1/INF-700c-2 landed, ``HarvestResult.outstanding`` (the
  "waiting count") reads 0 both for a healthy loop and for a loop that has
  never run at all, because a textless record is not outstanding and every
  retained real record is textless. That count can therefore no longer serve
  as the "is this loop alive" signal INF-700a's own L1 asked for; the signal
  has to come from RUN RECENCY instead.

  This AC requires a NEW production entry point — a ``--status`` flag on the
  existing harvester CLI (``scripts/knowledge/harvest_learnings.py``), per
  its own it_requirements: "A subcommand or flag on the existing harvester
  CLI is sufficient and preferable to a new script." The contract this test
  file pins for that flag (there is no prior art to inherit from — grep
  confirms no marker/status concept exists anywhere in this codebase today):

    --status
        Prints ONE line of JSON to stdout and exits 0 — ALWAYS 0, never an
        error code, even when nothing has ever run (it_requirements: "not as
        an error"). Side-effect free: must not create the marker file, the
        marker's parent directory, or the sink's parent directory (mirrors
        --print-sink's existing "reads the declaration only" contract).
        Shape: {"last_run": <str>, "sink": <str>, "sink_exists": <bool>}.
          - last_run: the literal sentinel string "never-run" when the
            marker has never been written in this tree, otherwise an
            ISO-8601 UTC timestamp string for the last COMPLETED run
            (main() reaching a result without SystemExit(1)/(2)).
          - sink: the resolved sink path (same resolution --print-sink /
            an ordinary run already use), as a string, ALWAYS present —
            even when the sink does not exist and even when no run has
            ever happened, so a reader always knows which sink up front.
          - sink_exists: a FRESH Path.exists() stat taken at answer time —
            never inferred from the marker or from any past run's record.
    --marker PATH
        New optional arg (mirrors the existing --state arg's shape),
        default Path("debugging/logs/harvest_last_run.json") — the last-run
        marker file. An ordinary (non-status, non-print-sink) invocation
        that reaches a completed harvest() call (regardless of --dry-run,
        regardless of the resulting exit code 0/3/4, regardless of whether
        the sink existed — INF-400c-4-iv already treats an absent sink as a
        completed no-work run, not an error) writes/updates this file with
        {"last_run": "<ISO-8601 UTC now>", "sink": "<resolved sink path>"}.

  Both trees in the discriminating-pair test below have
  ``HarvestResult.outstanding == 0`` — this is deliberately asserted, not
  avoided, because INF-700a-2 replaces the waiting count as the liveness
  signal; it does not restore it as a non-zero backlog (INF-700c's own hard
  constraint forbids exactly that).

RED baseline: --status does not exist on this CLI today (confirmed: grep for
"last_run"/"last-run"/"--status" across scripts/knowledge/ and
tests/knowledge/ returns nothing), so argparse rejects it with exit code 2
and "unrecognized arguments" on stderr for every test below.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
import unittest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HARVEST_PATH = _REPO_ROOT / "scripts" / "knowledge" / "harvest_learnings.py"
_TIMEOUT = 10

_spec = importlib.util.spec_from_file_location("harvest_learnings", _HARVEST_PATH)
assert _spec is not None and _spec.loader is not None, f"could not load spec for {_HARVEST_PATH}"
_mod: Any = importlib.util.module_from_spec(_spec)
sys.modules["harvest_learnings"] = _mod
_spec.loader.exec_module(_mod)
_harvest = _mod.harvest


# ---------------------------------------------------------------------------
# Shared helpers (mirrors tests/knowledge/test_harvest_learnings.py's own
# _make_event / _write_sink so this file's fixtures are drawn from the same
# on-disk shape the real corpus and the real CLI both use, not a bespoke one).
# ---------------------------------------------------------------------------


def _make_event(entry_kind: str, destination: str, text: str | None = None) -> dict:
    event: dict[str, Any] = {
        "event": "knowledge_captured",
        "timestamp": "2026-06-05T14:00:00Z",
        "ticket": "tickets/test.md",
        "agent": "python-coder",
        "component": "knowledge_system",
        "destination": destination,
        "entry_kind": entry_kind,
    }
    if text is not None:
        event["text"] = text
    return event


def _write_sink(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for ev in events:
            fh.write(json.dumps(ev) + "\n")


def _run_status(sink: Path, marker: Path, cwd: Path | None = None) -> tuple[int, dict]:
    """Invoke the REAL harvester CLI's --status flag as a subprocess.

    Returns (returncode, parsed_json_stdout). Raises AssertionError (via
    json.loads) if stdout is not valid JSON -- the flag does not exist yet,
    so today this always fails with argparse's exit-2 "unrecognized
    arguments" and non-JSON stderr, which is the intended RED state.
    """
    proc = subprocess.run(
        [
            sys.executable,
            str(_HARVEST_PATH),
            "--status",
            "--sink",
            str(sink),
            "--marker",
            str(marker),
        ],
        capture_output=True,
        text=True,
        timeout=_TIMEOUT,
        cwd=str(cwd) if cwd else None,
        check=False,
    )
    parsed = json.loads(proc.stdout)
    return proc.returncode, parsed


def _run_ordinary(sink: Path, state: Path, marker: Path, cwd: Path | None = None) -> int:
    """Invoke the REAL harvester CLI's ordinary (non-status) run -- the
    production entry point a completed 'knowledge-routing-step' dispatch
    performs in production (per INF-700a-1's own agent instruction: run this
    script via Bash). This is "the completion path" for this AC's own scope.
    """
    proc = subprocess.run(
        [
            sys.executable,
            str(_HARVEST_PATH),
            "--sink",
            str(sink),
            "--state",
            str(state),
            "--marker",
            str(marker),
        ],
        capture_output=True,
        text=True,
        timeout=_TIMEOUT,
        cwd=str(cwd) if cwd else None,
        check=False,
    )
    return proc.returncode


class TestNeverRunTreeAndRanAfterEveryUnitOfWorkTreeReportDifferently(unittest.TestCase):
    """AC INF-700a-2: the discriminating pair the AC's own notes name
    verbatim. A tree where the routing step ran after each of five units of
    work and a tree where it never ran both report a waiting count of zero
    -- but their status answers must differ, or this AC is not satisfied
    whatever else the answer reports."""

    def test_a_never_run_tree_and_a_ran_after_every_unit_of_work_tree_report_differently(
        self,
    ) -> None:
        # covers: INF-700a-2
        # angle: criterion
        with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
            tree_a = Path(tmp_a)
            tree_b = Path(tmp_b)

            sink_a = tree_a / "debugging" / "logs" / "knowledge_emissions.jsonl"
            state_a = tree_a / "debugging" / "logs" / "harvest_state.json"
            marker_a = tree_a / "debugging" / "logs" / "harvest_last_run.json"

            # Five units of work: each appends one textless event (matching
            # the real 28-record corpus's shape) and then runs the routing
            # step to completion -- exactly the Given clause's "runs after
            # every unit of work".
            events: list[dict] = []
            for i in range(5):
                events.append(
                    _make_event(entry_kind="memory-project", destination=str(tree_a / f"m{i}.md"))
                )
                _write_sink(sink_a, events)
                rc = _run_ordinary(sink_a, state_a, marker_a)
                self.assertIn(
                    rc,
                    (0, 3, 4),
                    f"ordinary run {i} must complete (exit 0/3/4), not crash before "
                    f"reaching a HarvestResult",
                )

            # Tree B: sink present at the SAME conceptual location but the
            # routing step has never been invoked here at all.
            sink_b = tree_b / "debugging" / "logs" / "knowledge_emissions.jsonl"
            state_b = tree_b / "debugging" / "logs" / "harvest_state.json"
            marker_b = tree_b / "debugging" / "logs" / "harvest_last_run.json"
            _write_sink(sink_b, [_make_event(entry_kind="memory-project", destination="x.md")])

            # The "waiting count" (HarvestResult.outstanding) is asserted via
            # the pure harvest() function directly -- never through the CLI
            # -- so checking it can never itself constitute "the routing step
            # ran" for either tree (only main(), the CLI entry point, writes
            # the marker; harvest() the pure function never does).
            result_a = _harvest(sink_a, state_a)
            result_b = _harvest(sink_b, state_b)
            self.assertEqual(
                result_a.outstanding,
                0,
                "tree A (ran 5 times) must read a waiting count of zero -- "
                "this is the AC's own stated precondition, not a target to avoid",
            )
            self.assertEqual(
                result_b.outstanding,
                0,
                "tree B (never run) must ALSO read a waiting count of zero -- "
                "both trees are zero; only the status answer may differ",
            )

            rc_a, status_a = _run_status(sink_a, marker_a)
            rc_b, status_b = _run_status(sink_b, marker_b)
            self.assertEqual(rc_a, 0, "status query must exit 0")
            self.assertEqual(rc_b, 0, "status query must exit 0")

            self.assertNotEqual(
                status_a.get("last_run"),
                status_b.get("last_run"),
                "An answer that cannot tell these two trees apart has not "
                "satisfied this criterion, whatever else it reports. "
                f"status_a={status_a!r} status_b={status_b!r}",
            )
            self.assertNotEqual(
                status_a,
                status_b,
                f"Full status answers must differ: status_a={status_a!r} "
                f"status_b={status_b!r}",
            )


class TestAbsentRunMarkerReportsNoRunRecordedAndIsNotAnError(unittest.TestCase):
    """AC INF-700a-2: fresh-clone simulation. debugging/logs/ is gitignored
    (.gitignore:60) so a fresh clone or fresh install has no marker and no
    sink at all -- that absence must be reported as "no run recorded", never
    as an error, a zero timestamp, or a run that happened. The query itself
    must not create the very state whose absence it is reporting."""

    def test_an_absent_run_marker_reports_no_run_recorded_and_is_not_an_error(self) -> None:
        # covers: INF-700a-2
        # angle: failure
        with tempfile.TemporaryDirectory() as tmp:
            fresh_clone = Path(tmp)
            # Deliberately do NOT create fresh_clone / "debugging" at all --
            # this is the fresh-clone/fresh-install shape .gitignore:60
            # produces for real.
            sink = fresh_clone / "debugging" / "logs" / "knowledge_emissions.jsonl"
            marker = fresh_clone / "debugging" / "logs" / "harvest_last_run.json"

            rc, status = _run_status(sink, marker, cwd=fresh_clone)

            # (1) the never-run value is present
            self.assertIn(
                "last_run",
                status,
                f"status answer must carry a 'last_run' key at all: {status!r}",
            )
            last_run = status.get("last_run")
            self.assertEqual(
                last_run,
                "never-run",
                f"a tree with no marker must report the never-run sentinel, "
                f"got: {last_run!r}",
            )
            # (2) it is NOT a zero timestamp
            self.assertNotIn(
                "1970-01-01",
                str(last_run),
                "never-run must not be rendered as a zero/epoch timestamp -- "
                "that is indistinguishable from a healthy run at the epoch",
            )
            # (3) it is NOT an empty string
            self.assertNotEqual(
                last_run,
                "",
                "never-run must not be rendered as an empty string",
            )
            # (4) the exit status is not an error status
            self.assertEqual(
                rc,
                0,
                f"never-run is a normal, expected answer, not an error -- "
                f"exit code must be 0, got {rc}",
            )
            # (5) querying created neither the marker nor its directory
            self.assertFalse(
                marker.exists(),
                "the status query must not create the marker file as a "
                "side effect -- doing so would make never-run unreachable "
                "forever after the FIRST query",
            )
            self.assertFalse(
                marker.parent.exists(),
                "the status query must not create the marker's parent "
                "directory (debugging/logs/) as a side effect either",
            )


class TestAnswerReportsWhetherTheNamedSinkExistsAndNamesIt(unittest.TestCase):
    """AC INF-700a-2: reachability via the production CLI entry point, run
    as a real subprocess (not an in-process import). Two trees, identical
    (never-run) last-run state, differing only in whether the declared sink
    exists on disk -- the existence field must differ, and both answers must
    name the sink they are talking about."""

    def test_the_answer_reports_whether_the_named_sink_exists_and_names_it(self) -> None:
        # covers: INF-700a-2
        # angle: reachability
        # surface_invoked: the routing-status query run through its
        # production CLI entry point via subprocess (scripts/knowledge/
        # harvest_learnings.py --status), never an in-process function call.
        with tempfile.TemporaryDirectory() as tmp_present, tempfile.TemporaryDirectory() as tmp_absent:
            tree_present = Path(tmp_present)
            tree_absent = Path(tmp_absent)

            sink_present = tree_present / "debugging" / "logs" / "knowledge_emissions.jsonl"
            marker_present = tree_present / "debugging" / "logs" / "harvest_last_run.json"
            sink_present.parent.mkdir(parents=True, exist_ok=True)
            sink_present.write_text("", encoding="utf-8")

            sink_absent = tree_absent / "debugging" / "logs" / "knowledge_emissions.jsonl"
            marker_absent = tree_absent / "debugging" / "logs" / "harvest_last_run.json"
            # sink_absent is deliberately never created.

            # Both trees held at identical (never-run) last-run state: no
            # marker file has been written in either.
            self.assertFalse(marker_present.exists())
            self.assertFalse(marker_absent.exists())

            rc_present, status_present = _run_status(sink_present, marker_present)
            rc_absent, status_absent = _run_status(sink_absent, marker_absent)
            self.assertEqual(rc_present, 0)
            self.assertEqual(rc_absent, 0)

            self.assertTrue(
                status_present.get("sink_exists"),
                f"sink IS present on disk; sink_exists must read True: {status_present!r}",
            )
            self.assertFalse(
                status_absent.get("sink_exists"),
                f"sink is NOT present on disk; sink_exists must read False: {status_absent!r}",
            )
            self.assertNotEqual(
                status_present.get("sink_exists"),
                status_absent.get("sink_exists"),
                "A routing step running happily against a path no producer "
                "writes to must be visible as that, not as a quiet success.",
            )

            # Both answers must NAME the sink they are talking about --
            # never blank/null/absent -- and each must name the path it was
            # actually pointed at, so a reader can tell an unemitted-to sink
            # from a misconfigured one.
            self.assertEqual(status_present.get("sink"), str(sink_present.resolve()))
            self.assertEqual(status_absent.get("sink"), str(sink_absent.resolve()))


if __name__ == "__main__":
    unittest.main()
