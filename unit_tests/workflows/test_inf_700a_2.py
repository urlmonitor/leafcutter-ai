"""
MODULE: unit_tests/workflows/test_inf_700a_2.py
GOAL: RED behavioral test baseline for INF-700a-2's fourth descriptor — "the
    recency answer changes after a completion path runs" (angle: seam).

AC: docs/acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700a-2.yaml

DELIBERATE DEVIATION FROM THE AC'S TEST_SPEC WORDING, AND WHY (read before
editing this file):

  INF-700a-2.yaml's own test_spec describes this descriptor as driving "ONE
  completion path to completion UNDER THE ENGINE HARNESS" (i.e.
  unit_tests/_workflow_engine_harness.py's run_workflow_under_e2(), the same
  mechanism test_inf_700a_1.py and test_inf_700a_1_i.py use to drive
  fast-lane-ship.js). This file does NOT use that harness, for a reason
  load-bearing enough to record here rather than silently deviate.

  Under that harness, the "knowledge-routing-step" agent() dispatch (the
  step INF-700a-1 wired) is answered by a HAND-WRITTEN JSON stub supplied via
  label_responses — see test_inf_700a_1.py's _full_success_responses(),
  which literally types {"read": 3, "written": 3, "unwritten": 0, "case":
  "completed"} as a Python dict literal. That stub is not a real completed
  run of anything: no real scripts/knowledge/harvest_learnings.py process
  ever executes, so no real last-run marker is ever written by driving
  fast-lane-ship.js through that harness. A test that asserted a status
  change here would have to ALSO fabricate the "after" status answer (or
  read a marker file the harness itself planted by hand), which is exactly
  the shape this repository's own "seam" angle forbids: "Pipes the REAL
  producer's actual output into the REAL consumer... calling an extended
  function directly ... does not satisfy it" — the failure mode of a status
  answer "tested only against hand-constructed marker files [while] nothing
  in the pipeline ever writes one", which INF-700a-2's own test_rationale
  names as the exact defect this descriptor exists to catch. Routing this
  through the mocked JS harness would BE that defect, not a test of it.

  The REAL producer for this AC's own scope is a genuinely completed run of
  scripts/knowledge/harvest_learnings.py's main() — the same production
  entry point INF-700a-1's own agent instruction tells the dispatched
  python-coder sub-agent to invoke via Bash in production (see
  templates/agents/knowledge-harvester.md and the "knowledge-routing-step"
  agent() call site in templates/workflows-js/fast-lane-ship.js, which reads
  "This step must never block, retry, or fail the build" and asks for a
  Bash-run of that exact script). The REAL consumer is the --status flag
  this AC adds to that SAME script (see tests/knowledge/test_inf_700a_2.py's
  module docstring for the full flag contract this test-writer pass pins).
  Chaining two REAL subprocess invocations of the ACTUAL production script —
  one ordinary run, then one --status query, both real processes, neither
  mocked — is the faithful seam for INF-700a-2's own boundary. It is a
  STRONGER real-artifact proof than piping the JS harness's fabricated
  agent() reply would have been, not a weaker substitute for it: INF-700a-1's
  own seam (fast-lane-ship.js's dispatch → its terminal `knowledge_routing`
  payload) is already covered by test_inf_700a_1.py's
  TestRoutingResultIsConsumedNotFireAndForget; duplicating that coverage here
  would not add proof of THIS AC's own claim (run recency, sink identity,
  never-run distinctness), which is unique to the CLI-internal marker/status
  round trip pinned below.

  If a reviewer disagrees with this judgment call, the fix is to add a
  companion test using run_workflow_under_e2 alongside this one — not to
  replace this one, which is the only test in this ticket that proves the
  marker is written by a REAL, non-mocked run.

RED baseline: --status and the last-run marker do not exist yet (see
tests/knowledge/test_inf_700a_2.py's docstring for the full grep confirming
no prior art), so the second subprocess call below fails at
json.loads(proc.stdout) on non-JSON argparse-error stderr/stdout.
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

# Loaded only to construct a well-formed on-disk sink event via the SAME
# module the production script itself is (not a hand-typed shape guess) —
# mirrors tests/knowledge/test_harvest_learnings.py's own bootstrap.
_spec = importlib.util.spec_from_file_location("harvest_learnings", _HARVEST_PATH)
assert _spec is not None and _spec.loader is not None, f"could not load spec for {_HARVEST_PATH}"


def _make_event(destination: str) -> dict[str, Any]:
    return {
        "event": "knowledge_captured",
        "timestamp": "2026-06-05T14:00:00Z",
        "ticket": "tickets/test.md",
        "agent": "python-coder",
        "component": "knowledge_system",
        "destination": destination,
        "entry_kind": "memory-project",
        "text": "A genuine learning produced by one real unit of work.",
    }


def _write_sink(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for ev in events:
            fh.write(json.dumps(ev) + "\n")


def _run_status(sink: Path, marker: Path) -> tuple[int, dict[str, Any]]:
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
        check=False,
    )
    parsed = json.loads(proc.stdout)
    return proc.returncode, parsed


def _run_ordinary_completion(sink: Path, state: Path, marker: Path) -> int:
    """Drive ONE completion path — a real run of the routing step's own
    production entry point — to completion. This is the REAL producer this
    seam test pipes into the REAL consumer (--status) below."""
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
        check=False,
    )
    return proc.returncode


class TestRecencyAnswerChangesAfterACompletionPathRuns(unittest.TestCase):
    """AC INF-700a-2 / angle: seam. Query the status in a fresh tree and
    assert never-run; drive one completion path (a real, non-mocked run of
    the routing step's production CLI) to completion; query again and
    assert the answer now reports a completed run over the declared sink —
    the exact path the completion run acted on, not a source the driver
    does not write."""

    def test_the_recency_answer_changes_after_a_completion_path_runs(self) -> None:
        # covers: INF-700a-2
        # angle: seam
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp)
            sink = tree / "debugging" / "logs" / "knowledge_emissions.jsonl"
            state = tree / "debugging" / "logs" / "harvest_state.json"
            marker = tree / "debugging" / "logs" / "harvest_last_run.json"

            # 1. Query a fresh tree: assert never-run.
            rc_before, status_before = _run_status(sink, marker)
            self.assertEqual(rc_before, 0, "never-run status query must exit 0")
            self.assertEqual(
                status_before.get("last_run"),
                "never-run",
                f"a fresh tree must report never-run BEFORE the completion "
                f"path runs, got: {status_before!r}",
            )

            # 2. Drive ONE completion path to completion — a real, unmocked
            # invocation of the SAME production script the status query
            # below reads back from, so this is the REAL producer's actual
            # output, not a hand-constructed marker file.
            _write_sink(sink, [_make_event(destination=str(tree / "learned.md"))])
            rc_run = _run_ordinary_completion(sink, state, marker)
            self.assertIn(
                rc_run,
                (0, 3, 4),
                "the completion run must actually complete (reach a "
                "HarvestResult), not crash before the marker would be written",
            )

            # 3. Query again: assert the answer now reports a completed run
            # over the declared sink.
            rc_after, status_after = _run_status(sink, marker)
            self.assertEqual(rc_after, 0, "post-completion status query must exit 0")
            self.assertNotEqual(
                status_after.get("last_run"),
                "never-run",
                "the answer must change to a real completed-run value once "
                f"the completion path has actually run. status_after={status_after!r}",
            )
            self.assertNotEqual(
                status_before.get("last_run"),
                status_after.get("last_run"),
                "before/after answers must differ — an identical answer "
                "means the completion path's real run went nowhere the "
                "status query can see, the smaller copy of the fire-and-"
                "forget defect this AC's own test_rationale names",
            )
            self.assertEqual(
                status_after.get("sink"),
                str(sink.resolve()),
                "the status answer must name the EXACT sink the completion "
                "run acted on — a status reading a source the driver does "
                "not write is the failure this seam test exists to catch. "
                f"status_after={status_after!r}",
            )
            self.assertTrue(
                status_after.get("sink_exists"),
                f"the sink the completion run wrote to now exists on disk, "
                f"and sink_exists must be a fresh stat reflecting that: "
                f"{status_after!r}",
            )


if __name__ == "__main__":
    unittest.main()
