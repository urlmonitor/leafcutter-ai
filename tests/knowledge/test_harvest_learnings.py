"""
MODULE: test_harvest_learnings
GOAL: Unit tests for scripts/knowledge/harvest_learnings.py.
BUSINESS CONTEXT: Verifies that the learning harvester correctly reads
    knowledge_captured events from knowledge_emissions.jsonl, routes each
    to the appropriate knowledge surface, tracks processed events so re-runs
    are idempotent, and handles unrecognised entry_kinds gracefully.
    These tests define the acceptance gate for INF-400c-2 (AC-2, AC-3) and
    INF-400c-2-ii (an unroutable event stays unprocessed and is surfaced,
    never marked done).

    NOTE ON SUPERSESSION: this file previously carried
    ``TestSkipsUnrecognisedEntryKind`` covering INF-400c-2-i, which asserted
    that an unrecognised entry_kind event is marked processed (added to the
    idempotency record) so it is never retried. INF-400c-2-i is now
    ``status: superseded_by: [INF-400c-2-ii]`` — a 2026-08-25 dry-run over the
    real sink found all 28 in-flight events unroutable, and the old rule would
    have silently discarded every one on first run. INF-400c-2-ii requires the
    opposite: an unroutable event must NOT be added to the idempotency record,
    so a later run reads it again. That test class has been rewritten below as
    ``TestUnrecognisedEntryKindStaysRetryable`` to assert the new contract.
    (classification: consumer_drift — the harvester's routing taxonomy
    (11 known kinds) covers only 4 of route-knowledge's 16 target_surface
    values, so the "mark unroutable events processed" rule was silently
    discarding events for the other 12 taxonomy values that real callers use;
    both the old test and old production code were stale relative to that
    real consumer set. Restoring "stays retryable" matches the taxonomy the
    real emitters produce; the test is updated to match.)
ARCHITECTURE: Pure unit tests using unittest.TestCase with tempfile.TemporaryDirectory
    for filesystem isolation. Most tests monkeypatch the capture-learning write
    call so they verify routing decisions, not file-system writes to knowledge
    surfaces. The idempotency-record tests below (TestUnrecognisedEntryKindStaysRetryable,
    TestUnroutableEventNotPersistedToState, TestFullCorpusAllUnroutable) are
    real-artifact behavioral tests per BP-1100f-2: sink/state files are real
    temp-directory files, `harvest()` is not mocked, and the on-disk state.json
    is read back directly (not merely inferred from an in-memory result) to
    prove the idempotency record itself — the durable side-effect this AC is
    about — was or was not written to.
    All tests must complete in < 5 seconds.
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

# ---------------------------------------------------------------------------
# Bootstrap: resolve harvest_learnings module without relying on installed pkg
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HARVEST_PATH = _REPO_ROOT / "scripts" / "knowledge" / "harvest_learnings.py"

spec = importlib.util.spec_from_file_location("harvest_learnings", _HARVEST_PATH)
assert spec is not None and spec.loader is not None, f"could not load spec for {_HARVEST_PATH}"
# Annotated Any: the module is loaded dynamically, so mypy cannot see its
# attributes and reports attr-defined on every access (e.g. _KNOWN_ENTRY_KINDS,
# which the retryability tests swap to extend the routing rules).
_mod: Any = importlib.util.module_from_spec(spec)
sys.modules["harvest_learnings"] = _mod
spec.loader.exec_module(_mod)

harvest = _mod.harvest
HarvestResult = _mod.HarvestResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(
    entry_kind: str,
    destination: str,
    ticket: str = "tickets/test.md",
    timestamp: str = "2026-06-05T14:00:00Z",
) -> dict:
    """Return a well-formed knowledge_captured event dict."""
    return {
        "event": "knowledge_captured",
        "timestamp": timestamp,
        "ticket": ticket,
        "destination": destination,
        "entry_kind": entry_kind,
    }


def _write_sink(path: Path, events: list[dict]) -> None:
    """Write a JSONL sink file from a list of event dicts."""
    with open(path, "w", encoding="utf-8") as fh:
        for ev in events:
            fh.write(json.dumps(ev) + "\n")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRoutesMemoryProjectEvent(unittest.TestCase):
    """AC-2: harvester routes memory-project events to destination file."""

    def test_routes_memory_project_event(self) -> None:
        # covers: INF-400c-2
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            processed = tmp / "harvest_state.json"
            dest = tmp / "memory" / "project_infra.md"

            event = _make_event(
                entry_kind="memory-project",
                destination=str(dest),
            )
            _write_sink(sink, [event])

            written_paths: list[str] = []

            def fake_capture(learning_text: str, destination_path: str) -> None:
                written_paths.append(destination_path)
                Path(destination_path).parent.mkdir(parents=True, exist_ok=True)
                with open(destination_path, "a", encoding="utf-8") as fh:
                    fh.write(learning_text + "\n")

            result = harvest(
                sink_path=sink,
                state_path=processed,
                capture_fn=fake_capture,
            )

            self.assertEqual(result.routed, 1)
            self.assertIn(str(dest), written_paths)
            self.assertEqual(result.by_kind.get("memory-project", 0), 1)


class TestRoutesPerFolderReadmeEvent(unittest.TestCase):
    """AC-2: harvester routes per-folder-readme events to destination file."""

    def test_routes_per_folder_readme_event(self) -> None:
        # covers: INF-400c-2
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            processed = tmp / "harvest_state.json"
            dest = tmp / "docs" / "acceptance-criteria" / "infrastructure" / "README.md"

            event = _make_event(
                entry_kind="per-folder-readme",
                destination=str(dest),
            )
            _write_sink(sink, [event])

            written_paths: list[str] = []

            def fake_capture(learning_text: str, destination_path: str) -> None:
                written_paths.append(destination_path)

            result = harvest(
                sink_path=sink,
                state_path=processed,
                capture_fn=fake_capture,
            )

            self.assertEqual(result.routed, 1)
            self.assertIn(str(dest), written_paths)
            self.assertEqual(result.by_kind.get("per-folder-readme", 0), 1)


class TestIdempotentNoDuplicates(unittest.TestCase):
    """AC-3: running harvester twice does not re-process already-processed events."""

    def test_idempotent_no_duplicates(self) -> None:
        # covers: INF-400c-3
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            processed = tmp / "harvest_state.json"
            dest = tmp / "memory" / "project_infra.md"

            event = _make_event(
                entry_kind="memory-project",
                destination=str(dest),
            )
            _write_sink(sink, [event])

            call_count = [0]

            def fake_capture(learning_text: str, destination_path: str) -> None:
                call_count[0] += 1

            # First run: should process the event
            result1 = harvest(
                sink_path=sink,
                state_path=processed,
                capture_fn=fake_capture,
            )
            self.assertEqual(result1.routed, 1)
            self.assertEqual(call_count[0], 1)

            # Second run: same sink, same state — should process nothing
            result2 = harvest(
                sink_path=sink,
                state_path=processed,
                capture_fn=fake_capture,
            )
            self.assertEqual(result2.routed, 0)
            self.assertEqual(result2.previously_processed, 1)
            self.assertEqual(call_count[0], 1)  # no new calls


class TestUnrecognisedEntryKindStaysRetryable(unittest.TestCase):
    """INF-400c-2-ii: harvester logs a warning for an unroutable entry_kind,
    does not crash, does NOT mark the event processed, and continues with
    subsequent events.

    REWRITTEN from the superseded TestSkipsUnrecognisedEntryKind
    (INF-400c-2-i), which asserted the opposite idempotency-record behavior.
    See the module docstring "NOTE ON SUPERSESSION" for the classification.
    """

    def test_ac2ii_unrecognized_entry_kind_stays_unprocessed(self) -> None:
        # covers: INF-400c-2-ii
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            processed = tmp / "harvest_state.json"
            dest = tmp / "memory" / "unknown.md"

            event = _make_event(
                entry_kind="unknown_surface",
                destination=str(dest),
            )
            # Add a valid event after to confirm processing continues
            valid_event = _make_event(
                entry_kind="memory-project",
                destination=str(tmp / "memory" / "project_infra.md"),
                timestamp="2026-06-05T14:01:00Z",
            )
            _write_sink(sink, [event, valid_event])

            written_paths: list[str] = []

            def fake_capture(learning_text: str, destination_path: str) -> None:
                written_paths.append(destination_path)

            with self.assertLogs("harvest_learnings", level="WARNING") as cm:
                result = harvest(
                    sink_path=sink,
                    state_path=processed,
                    capture_fn=fake_capture,
                )

            # Unknown entry_kind should produce a warning
            warning_messages = " ".join(cm.output)
            self.assertIn("unknown_surface", warning_messages)

            # Unknown event is never routed via capture_fn
            self.assertNotIn(str(dest), written_paths)

            # Valid subsequent event still processed
            self.assertEqual(result.routed, 1)

            # The run's summary must report the unroutable count SEPARATELY
            # from routed, naming the distinct unroutable entry_kind and how
            # many events carried it (AC-2-ii clause: "naming each distinct
            # unroutable entry_kind and how many events carried it").
            self.assertEqual(result.unroutable_by_kind, {"unknown_surface": 1})
            self.assertEqual(result.skipped_unknown, 1)
            summary = result.summary()
            self.assertIn("unroutable", summary)
            self.assertIn("unknown_surface", summary)

            # AC-2-ii core clause: the unroutable event must NOT be added to
            # the idempotency record, so a later run reads it again.
            # Real-artifact check: read the state file directly off disk.
            with open(processed, encoding="utf-8") as fh:
                persisted_hashes = json.load(fh)
            self.assertEqual(
                len(persisted_hashes),
                1,
                "only the valid (routed) event's hash should be persisted; "
                "the unroutable event's hash must be absent",
            )

            # Re-run over the same sink/state: the unroutable event must be
            # retried (warning fires again) and is still not routed. The
            # valid event must NOT be reprocessed (previously_processed==1).
            with self.assertLogs("harvest_learnings", level="WARNING") as cm2:
                result2 = harvest(
                    sink_path=sink,
                    state_path=processed,
                    capture_fn=fake_capture,
                )
            self.assertIn("unknown_surface", " ".join(cm2.output))
            self.assertEqual(result2.routed, 0)
            self.assertEqual(result2.previously_processed, 1)
            self.assertEqual(result2.unroutable_by_kind, {"unknown_surface": 1})


class TestEmptySinkNoOp(unittest.TestCase):
    """AC-2 edge case: empty sink produces no writes and routed=0."""

    def test_empty_sink_no_op(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            processed = tmp / "harvest_state.json"

            # Write empty sink file
            sink.write_text("", encoding="utf-8")

            call_count = [0]

            def fake_capture(learning_text: str, destination_path: str) -> None:
                call_count[0] += 1

            result = harvest(
                sink_path=sink,
                state_path=processed,
                capture_fn=fake_capture,
            )

            self.assertEqual(result.routed, 0)
            self.assertEqual(result.previously_processed, 0)
            self.assertEqual(call_count[0], 0)


class TestSummaryFormat(unittest.TestCase):
    """AC-2: summary string has the format 'N learnings routed: ...'."""

    def test_summary_string_format(self) -> None:
        # covers: INF-400c-2
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            processed = tmp / "harvest_state.json"

            events = [
                _make_event(
                    entry_kind="memory-project",
                    destination=str(tmp / "memory" / "project_infra.md"),
                    timestamp="2026-06-05T14:00:00Z",
                ),
                _make_event(
                    entry_kind="per-folder-readme",
                    destination=str(tmp / "docs" / "README.md"),
                    timestamp="2026-06-05T14:01:00Z",
                ),
                _make_event(
                    entry_kind="agent-frontmatter",
                    destination=str(tmp / ".claude" / "skills" / "signoff" / "PROJECT_CONTEXT.md"),
                    timestamp="2026-06-05T14:02:00Z",
                ),
            ]
            _write_sink(sink, events)

            def fake_capture(learning_text: str, destination_path: str) -> None:
                pass

            result = harvest(
                sink_path=sink,
                state_path=processed,
                capture_fn=fake_capture,
            )

            self.assertEqual(result.routed, 3)
            summary = result.summary()
            # Must contain total count and at least one entry_kind breakdown
            self.assertIn("3 learnings routed", summary)
            self.assertIn("memory-project", summary)
            self.assertIn("per-folder-readme", summary)
            self.assertIn("agent-frontmatter", summary)


class TestFilterNonKnowledgeEvents(unittest.TestCase):
    """Harvester must skip events where event != 'knowledge_captured'."""

    def test_ignores_non_knowledge_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            processed = tmp / "harvest_state.json"

            non_knowledge_event = {
                "event": "agent_start",
                "timestamp": "2026-06-05T14:00:00Z",
                "ticket": "tickets/test.md",
                "phase": "python-coder",
            }
            knowledge_event = _make_event(
                entry_kind="memory-project",
                destination=str(tmp / "memory" / "project.md"),
                timestamp="2026-06-05T14:01:00Z",
            )
            _write_sink(sink, [non_knowledge_event, knowledge_event])

            written_paths: list[str] = []

            def fake_capture(learning_text: str, destination_path: str) -> None:
                written_paths.append(destination_path)

            result = harvest(
                sink_path=sink,
                state_path=processed,
                capture_fn=fake_capture,
            )

            # Only the knowledge_captured event should be routed
            self.assertEqual(result.routed, 1)
            self.assertEqual(len(written_paths), 1)


# ---------------------------------------------------------------------------
# INF-400c-2-ii — an unroutable event stays unprocessed and is surfaced
# ---------------------------------------------------------------------------


class TestFullCorpusAllUnroutable(unittest.TestCase):
    """AC-2-ii: a corpus of 28 events, all unroutable, writes nothing,
    retains all 28 for a later run, and reports 28 unroutable — the
    exact scenario named in the AC criteria (a 2026-08-25 dry-run over the
    real sink found all 28 in-flight events unroutable).

    The fixture (tests/fixtures/harvest_learnings/unroutable_corpus_28.json)
    is a VERBATIM capture of the real sink as of 2026-08-26: it is the exact
    set of 28 ``knowledge_captured`` lines extracted from
    ``debugging/logs/agent_telemetry.jsonl`` (filter: ``event ==
    "knowledge_captured"``), preserving their exact key set
    (``event, timestamp, agent, component, destination, entry_kind`` — note
    there is no ``ticket`` key on any real event) and exact values, including
    the messy real ``entry_kind`` taxonomy (15 distinct values, with
    hyphen/underscore near-duplicate pairs such as ``agent-memory`` /
    ``agent_memory``, ``component-convention`` / ``component_convention``,
    and ``framing-note`` / ``framing_note`` — exactly the normalisation
    problem a future routing-rule extension has to handle). To re-derive
    this fixture: re-run the same filter over
    ``debugging/logs/agent_telemetry.jsonl`` and diff against this file.

    Real-artifact behavioral test: the fixture corpus is written to a real
    sink file, `harvest()` runs unmocked against real temp-directory paths,
    and the on-disk state.json is read back directly.
    """

    def test_ac2ii_corpus_of_28_all_unroutable(self) -> None:
        # covers: INF-400c-2-ii
        events = load_fixture("harvest_learnings/unroutable_corpus_28")
        self.assertEqual(len(events), 28, "fixture drift — expected 28 events")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            processed = tmp / "harvest_state.json"
            _write_sink(sink, events)

            call_count = [0]

            def fake_capture(learning_text: str, destination_path: str) -> None:
                call_count[0] += 1

            result = harvest(
                sink_path=sink,
                state_path=processed,
                capture_fn=fake_capture,
            )

            self.assertEqual(result.routed, 0)
            self.assertEqual(result.previously_processed, 0)
            self.assertEqual(result.skipped_unknown, 28)
            self.assertEqual(call_count[0], 0, "nothing should ever be written")
            # Real entry_kind distribution from the 2026-08-26 sink capture —
            # 15 distinct messy real-world kinds, including the
            # hyphen/underscore near-duplicate pairs a future normalisation
            # step must handle (agent-memory/agent_memory,
            # component-convention/component_convention,
            # framing-note/framing_note).
            self.assertEqual(
                result.unroutable_by_kind,
                {
                    "agent-assignment-pattern": 2,
                    "agent-learning": 5,
                    "agent-memory": 5,
                    "agent_memory": 1,
                    "component-convention": 4,
                    "component-decomposition-and-operational-note": 1,
                    "component-framing-note": 1,
                    "component_context": 1,
                    "component_convention": 2,
                    "component_framing_note": 1,
                    "framing-convention": 1,
                    "framing-note": 1,
                    "framing_decomposition": 1,
                    "framing_decomposition_note": 1,
                    "framing_note": 1,
                },
            )
            self.assertEqual(
                len(result.unroutable_by_kind),
                15,
                "expected 15 distinct real entry_kind values",
            )

            # Nothing may be persisted to the idempotency record: read the
            # real on-disk state file (or confirm it was never created).
            if processed.exists():
                with open(processed, encoding="utf-8") as fh:
                    persisted_hashes = json.load(fh)
                self.assertEqual(persisted_hashes, [])

            # Re-run over the same corpus: all 28 must be retried and
            # reported again — nothing is silently dropped.
            result2 = harvest(
                sink_path=sink,
                state_path=processed,
                capture_fn=fake_capture,
            )
            self.assertEqual(result2.routed, 0)
            self.assertEqual(result2.previously_processed, 0)
            self.assertEqual(result2.skipped_unknown, 28)
            self.assertEqual(call_count[0], 0)


class TestExtendedRoutingRulesReroutesPreviouslyUnroutable(unittest.TestCase):
    """AC-2-ii: once the routing rules are extended to cover a previously
    unroutable entry_kind, a later run over the SAME corpus routes and
    writes it.

    Real-artifact test: uses the module's real `_default_capture` (not a
    stub) so the learning text is actually written to disk and read back —
    this is the round-trip the BP-1100f-2 mandate requires, since the
    write-call itself must not be mocked away.
    """

    def test_ac2ii_previously_unroutable_event_is_routed_after_rule_extension(self) -> None:
        # covers: INF-400c-2-ii
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            processed = tmp / "harvest_state.json"
            dest = tmp / "memory" / "future_surface.md"

            event = _make_event(
                entry_kind="future-kind-not-yet-supported",
                destination=str(dest),
            )
            _write_sink(sink, [event])

            # First run: entry_kind is not yet known — unroutable.
            result1 = harvest(sink_path=sink, state_path=processed)
            self.assertEqual(result1.routed, 0)
            self.assertEqual(result1.skipped_unknown, 1)
            self.assertFalse(dest.exists())

            # Extend the routing rules (the natural seam: the module-level
            # known-kinds set) to cover the new entry_kind.
            original_known_kinds = _mod._KNOWN_ENTRY_KINDS
            _mod._KNOWN_ENTRY_KINDS = original_known_kinds | frozenset(
                {"future-kind-not-yet-supported"}
            )
            try:
                # Re-run over the SAME corpus using the REAL capture_fn
                # (default production write path) — no mocking of the write.
                result2 = harvest(sink_path=sink, state_path=processed)
            finally:
                _mod._KNOWN_ENTRY_KINDS = original_known_kinds

            self.assertEqual(result2.routed, 1)
            self.assertEqual(result2.skipped_unknown, 0)

            # Real-artifact round trip: read the actual file back off disk.
            self.assertTrue(dest.exists(), "learning must be written to the real destination file")
            written_content = dest.read_text(encoding="utf-8")
            self.assertIn("future-kind-not-yet-supported", written_content)


class TestExitStatusDistinguishesCleanVsUnroutable(unittest.TestCase):
    """AC-2-ii: "the run's exit status distinguishes 'drained cleanly' from
    'drained with unroutable events left behind', so a caller cannot read a
    run that routed nothing as a run that had nothing to route."

    This can only be observed at the CLI boundary (harvest() itself returns
    a HarvestResult, not a process exit code) so this test invokes the real
    module as a subprocess — a genuine reachability test of the production
    entry point, not a call to an in-process function.
    """

    def test_ac2ii_clean_run_exits_zero(self) -> None:
        # covers: INF-400c-2-ii
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            processed = tmp / "harvest_state.json"
            dest = tmp / "memory" / "clean.md"
            _write_sink(
                sink,
                [_make_event(entry_kind="memory-project", destination=str(dest))],
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    str(_HARVEST_PATH),
                    "--sink",
                    str(sink),
                    "--state",
                    str(processed),
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            self.assertEqual(
                proc.returncode,
                0,
                f"clean run (nothing unroutable) must exit 0; stderr={proc.stderr}",
            )

    def test_ac2ii_run_with_unroutable_events_exits_nonzero_distinct_code(self) -> None:
        # covers: INF-400c-2-ii
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            processed = tmp / "harvest_state.json"
            _write_sink(
                sink,
                [_make_event(entry_kind="never-seen-before-kind", destination=str(tmp / "x.md"))],
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    str(_HARVEST_PATH),
                    "--sink",
                    str(sink),
                    "--state",
                    str(processed),
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            # Exit code 3 is the contract this AC establishes: distinct from
            # 0 (clean), 1 (sink not found), and 2 (state file corrupted) —
            # so a caller can tell "routed nothing, nothing to route" (0)
            # apart from "routed nothing, events left behind" (3).
            self.assertEqual(
                proc.returncode,
                3,
                f"a run that leaves unroutable events behind must exit 3 "
                f"(distinct from 0/1/2); stdout={proc.stdout} stderr={proc.stderr}",
            )
            self.assertIn("unroutable", proc.stdout + proc.stderr)


class TestWriteFailureIsNotReportedAsCleanRun(unittest.TestCase):
    """A run in which destination writes fail must not look like a quiet run.

    Before this fix, `harvest()` caught the OSError raised by `capture_fn`
    and `continue`d without touching any counter. A run where every single
    write failed therefore printed the exact same summary as a run with
    nothing to do -- "0 learnings routed: none" -- and exited 0. The
    operator documentation tells the reader that 0 means "drained cleanly",
    so the failure was not merely unreported: the documented contract
    actively asserted success.
    """

    def test_failed_writes_are_counted_and_named(self) -> None:
        def always_fails(_text: str, _dest: str) -> None:
            raise OSError("simulated ENOSPC")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            _write_sink(
                sink,
                [
                    _make_event(entry_kind="adr", destination=str(tmp / "a.md")),
                    _make_event(
                        entry_kind="claude-md",
                        destination=str(tmp / "b.md"),
                        timestamp="2026-06-05T15:00:00Z",
                    ),
                ],
            )

            result = harvest(
                sink_path=sink,
                state_path=tmp / "harvest_state.json",
                capture_fn=always_fails,
            )

            self.assertEqual(result.routed, 0, "nothing was written, so nothing was routed")
            self.assertEqual(result.write_failures, 2)
            self.assertEqual(result.failed_by_kind, {"adr": 1, "claude-md": 1})
            self.assertIn("write failures", result.summary())

    def test_failed_write_leaves_the_event_retryable(self) -> None:
        """A write that failed must not be recorded as processed.

        Otherwise the transient failure is upgraded to permanent loss on the
        next run, which is the same defect INF-400c-2-ii fixed for
        unroutable events.
        """

        def always_fails(_text: str, _dest: str) -> None:
            raise OSError("simulated EACCES")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            state = tmp / "harvest_state.json"
            _write_sink(
                sink, [_make_event(entry_kind="adr", destination=str(tmp / "a.md"))]
            )

            harvest(sink_path=sink, state_path=state, capture_fn=always_fails)

            # Assert the OUTCOME (the event is still retryable), not the
            # mechanism. With every write failed there is no new hash to
            # record, so the harvester skips the no-op save entirely and the
            # state file may legitimately not exist at all -- which is
            # equivalent to an empty one, since _load_state treats a missing
            # file as "nothing processed yet".
            recorded = (
                json.loads(state.read_text(encoding="utf-8")) if state.exists() else []
            )
            self.assertEqual(
                recorded,
                [],
                "a failed write must not be recorded as processed",
            )

            # The retry proves it: a later run with a working capture_fn
            # routes the event that previously failed.
            written: list[tuple[str, str]] = []
            retry = harvest(
                sink_path=sink,
                state_path=state,
                capture_fn=lambda t, d: written.append((t, d)),
            )
            self.assertEqual(retry.routed, 1)
            self.assertEqual(len(written), 1)

    def test_write_failure_exits_four_at_the_cli(self) -> None:
        """Reachability test through the real entry point and real capture_fn.

        The destination's parent is a regular file, so `_default_capture`'s
        `mkdir` raises NotADirectoryError (an OSError subclass).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            blocker = tmp / "blocked"
            blocker.write_text("regular file, not a directory", encoding="utf-8")
            sink = tmp / "knowledge_emissions.jsonl"
            _write_sink(
                sink,
                [_make_event(entry_kind="adr", destination=str(blocker / "sub" / "x.md"))],
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    str(_HARVEST_PATH),
                    "--sink",
                    str(sink),
                    "--state",
                    str(tmp / "harvest_state.json"),
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            self.assertEqual(
                proc.returncode,
                4,
                f"a run with failed writes must exit 4, not 0; "
                f"stdout={proc.stdout} stderr={proc.stderr}",
            )
            self.assertIn("write failures", proc.stdout)


class TestStatePersistFailureIsSurfaced(unittest.TestCase):
    """A run that could not save its state is a duplicating run, not a clean one.

    Before this fix the `_save_state` OSError was swallowed with a bare
    `pass`. The learnings were written but no hash was recorded, so the next
    run re-routed every one of them and appended each learning to its
    destination a second time -- silently, and with a 0 exit code claiming
    the run drained cleanly.
    """

    def _run(self, tmp: Path):
        sink = tmp / "knowledge_emissions.jsonl"
        _write_sink(
            sink, [_make_event(entry_kind="adr", destination=str(tmp / "a.md"))]
        )
        blocker = tmp / "blocked"
        blocker.write_text("regular file, not a directory", encoding="utf-8")
        return sink, blocker / "sub" / "state.json"

    def test_state_failure_is_flagged_and_explained_in_the_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink, state = self._run(tmp)

            result = harvest(
                sink_path=sink,
                state_path=state,
                capture_fn=lambda _t, _d: None,
            )

            self.assertEqual(result.routed, 1, "the write itself succeeded")
            self.assertTrue(result.state_persist_failed)
            self.assertIn("state NOT persisted", result.summary())
            self.assertIn("re-applied on the next run", result.summary())

    def test_state_failure_exits_four_at_the_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink, state = self._run(tmp)

            proc = subprocess.run(
                [
                    sys.executable,
                    str(_HARVEST_PATH),
                    "--sink",
                    str(sink),
                    "--state",
                    str(state),
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            self.assertEqual(
                proc.returncode,
                4,
                f"a run that could not persist state must exit 4, not 0; "
                f"stdout={proc.stdout} stderr={proc.stderr}",
            )

    def test_noop_state_write_is_not_a_failure_and_does_not_mask_the_backlog(
        self,
    ) -> None:
        """An unwritable state path is harmless when nothing needed recording.

        With no new hashes the save is a no-op, so a failure there costs
        nothing -- nothing was routed, so nothing can be re-routed. Treating
        it as a failed run would raise the exit code to 4 and hide the
        exit-3 backlog on exactly the run that most needs it: an
        all-unroutable sink, which is the shape of the real corpus today.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            blocker = tmp / "blocked"
            blocker.write_text("regular file, not a directory", encoding="utf-8")
            sink = tmp / "knowledge_emissions.jsonl"
            _write_sink(
                sink,
                [
                    _make_event(
                        entry_kind="a-kind-nobody-routes",
                        destination=str(tmp / "y.md"),
                    )
                ],
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    str(_HARVEST_PATH),
                    "--sink",
                    str(sink),
                    "--state",
                    str(blocker / "sub" / "state.json"),
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            self.assertEqual(
                proc.returncode,
                3,
                f"a no-op state write must not mask the unroutable backlog; "
                f"stdout={proc.stdout} stderr={proc.stderr}",
            )
            self.assertIn("unroutable", proc.stdout)
            self.assertNotIn("state NOT persisted", proc.stdout)

    def test_failure_code_outranks_the_unroutable_code(self) -> None:
        """Exit 4 must win over exit 3 when both conditions hold.

        A broken run needs attention before a merely-retained backlog does.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            blocker = tmp / "blocked"
            blocker.write_text("regular file, not a directory", encoding="utf-8")
            sink = tmp / "knowledge_emissions.jsonl"
            _write_sink(
                sink,
                [
                    _make_event(
                        entry_kind="adr", destination=str(blocker / "sub" / "x.md")
                    ),
                    _make_event(
                        entry_kind="a-kind-nobody-routes",
                        destination=str(tmp / "y.md"),
                        timestamp="2026-06-05T16:00:00Z",
                    ),
                ],
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    str(_HARVEST_PATH),
                    "--sink",
                    str(sink),
                    "--state",
                    str(tmp / "harvest_state.json"),
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            self.assertEqual(proc.returncode, 4, f"stdout={proc.stdout}")
            self.assertIn("write failures", proc.stdout)
            self.assertIn("unroutable", proc.stdout)


if __name__ == "__main__":
    unittest.main()
