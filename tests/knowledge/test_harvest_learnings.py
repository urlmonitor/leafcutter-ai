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

import hashlib
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
    agent: str = "python-coder",
    component: str = "knowledge_system",
) -> dict:
    """Return a well-formed knowledge_captured event dict.

    Conforms to the reconciled record shape INF-400b-2-ii made authoritative
    (signoff Sec7 step 4): every producer supplies `agent` and `component` --
    both are required by `_event_hash` (INF-400b-2-i) and a record missing
    either now raises `KeyError` rather than being silently hashed on a
    defaulted-to-empty substitute. `ticket` remains optional and is kept
    here only for callers that want it present on the record; it never
    contributes to the digest (see
    TestDigestIgnoresFieldsAbsentFromRequiredShape). Before INF-400b-2-ii
    this helper supplied `ticket` but never `agent`/`component` -- the
    pre-reconciliation shape -- which is why every call site here predates
    the real corpus's actual shape (see `_make_bare_event` below, which was
    already written to match it).
    """
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


def _make_bare_event(
    entry_kind: str,
    destination: str,
    agent: str = "test-agent",
    component: str = "test-component",
    timestamp: str = "2026-06-05T14:00:00Z",
) -> dict:
    """Return a knowledge_captured event shaped like the REAL corpus.

    Unlike ``_make_event`` above, this carries no ``ticket`` key and no
    ``text`` key at all -- matching
    ``tests/fixtures/harvest_learnings/unroutable_corpus_28.json`` exactly
    (event, timestamp, agent, component, destination, entry_kind). This is
    the textless-record shape INF-700c-1 requires the harvester to classify
    as ineligible. Callers add a ``text`` key themselves when a test needs a
    record WITH real learning content.
    """
    return {
        "event": "knowledge_captured",
        "timestamp": timestamp,
        "agent": agent,
        "component": component,
        "destination": destination,
        "entry_kind": entry_kind,
    }


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
            event["text"] = "A genuine learning about project infrastructure."
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
            event["text"] = "A genuine learning captured in a per-folder README."
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
            event["text"] = "A genuine learning routed exactly once across two runs."
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
            # Has text but an unrecognised entry_kind -- this is what actually
            # makes the record *unroutable* rather than *textless*; without a
            # real text value the new no-learning-text check (which runs
            # before entry_kind routing) would classify it as no_learning_text
            # instead, and this test would no longer exercise the unroutable
            # path it is named for.
            event["text"] = "Has text but an unrecognised entry_kind."
            # Add a valid event after to confirm processing continues
            valid_event = _make_event(
                entry_kind="memory-project",
                destination=str(tmp / "memory" / "project_infra.md"),
                timestamp="2026-06-05T14:01:00Z",
            )
            valid_event["text"] = "A genuine learning that should still be routed."
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

            event1 = _make_event(
                entry_kind="memory-project",
                destination=str(tmp / "memory" / "project_infra.md"),
                timestamp="2026-06-05T14:00:00Z",
            )
            event1["text"] = "A genuine learning about project infra."
            event2 = _make_event(
                entry_kind="per-folder-readme",
                destination=str(tmp / "docs" / "README.md"),
                timestamp="2026-06-05T14:01:00Z",
            )
            event2["text"] = "A genuine learning captured in a per-folder README."
            event3 = _make_event(
                entry_kind="agent-frontmatter",
                destination=str(tmp / ".claude" / "skills" / "signoff" / "PROJECT_CONTEXT.md"),
                timestamp="2026-06-05T14:02:00Z",
            )
            event3["text"] = "A genuine learning about an agent's frontmatter."
            events = [event1, event2, event3]
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
            knowledge_event["text"] = "A genuine learning that should be routed."
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
    """AC-2-ii / INF-700c-1: a corpus of 28 events, all writes nothing and
    retains all 28 for a later run — the exact scenario named in the AC
    criteria (a 2026-08-25 dry-run over the real sink found all 28 in-flight
    events unroutable).

    UPDATED for INF-700c-1: the 28 real records carry no ``text`` field at
    all (see ``_make_bare_event`` / the fixture note below), so under the
    AC's classification-order rule -- no-learning-text is checked BEFORE
    entry_kind routing -- they now land in ``no_learning_text``, not
    ``skipped_unknown``. This is the true state of the corpus (it was always
    textless; INF-700c-1 only added the check that notices), so the fixture
    itself is untouched -- only this test's expectation changes to match the
    AC's ordering rule.

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
        # covers: INF-700c-1
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
            # All 28 records are textless (no `text` key at all), so under
            # INF-700c-1's classification order they land in
            # no_learning_text, never reaching entry_kind routing.
            self.assertEqual(result.skipped_unknown, 0)
            self.assertEqual(result.no_learning_text, 28)
            self.assertEqual(call_count[0], 0, "nothing should ever be written")
            # Real entry_kind distribution from the 2026-08-26 sink capture —
            # 15 distinct messy real-world kinds, including the
            # hyphen/underscore near-duplicate pairs a future normalisation
            # step must handle (agent-memory/agent_memory,
            # component-convention/component_convention,
            # framing-note/framing_note). The distribution itself is
            # unchanged by INF-700c-1 -- only which bucket dict it is
            # reported under moved from unroutable_by_kind to
            # no_learning_by_kind.
            self.assertEqual(
                result.no_learning_by_kind,
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
                len(result.no_learning_by_kind),
                15,
                "expected 15 distinct real entry_kind values",
            )
            self.assertEqual(result.unroutable_by_kind, {})

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
            self.assertEqual(result2.skipped_unknown, 0)
            self.assertEqual(result2.no_learning_text, 28)
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
            # Real, hand-composed learning content -- the record needs its
            # own genuine text so that (a) the first run is unroutable
            # because of its entry_kind, not because it is textless, and
            # (b) the second run's write can be verified as a faithful
            # round-trip of real content rather than a synthesised
            # placeholder.
            real_text = "The router now understands the future-surface emitter's output shape."
            event["text"] = real_text
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
            #
            # NOTE on this assertion's shape: the original version asserted
            # that the written content contained the literal entry_kind
            # string ("future-kind-not-yet-supported"). That only ever
            # passed because of the deleted placeholder
            # (f"[{entry_kind}] Learning from {ticket}"), which always
            # embedded entry_kind verbatim. Forcing a *real* text value to
            # coincidentally contain the entry_kind string would be an
            # artificial coupling on the record's own metadata, not a
            # property this AC actually cares about. What this test is
            # actually about (per its own docstring) is: once the routing
            # rules are extended, a previously-unroutable record's REAL
            # content is written, verbatim, to the correct destination. So
            # the assertion is pinned to that round-trip instead -- the exact
            # `text` the record carried must be what lands on disk, at the
            # destination this event named.
            self.assertTrue(dest.exists(), "learning must be written to the real destination file")
            written_content = dest.read_text(encoding="utf-8")
            self.assertIn(real_text, written_content)


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
            unroutable_event = _make_event(
                entry_kind="never-seen-before-kind", destination=str(tmp / "x.md")
            )
            # Real text is required so this record is genuinely unroutable
            # (unknown entry_kind), not textless -- the no-learning-text
            # check runs first and would otherwise absorb it before the
            # entry_kind routing this test is exercising.
            unroutable_event["text"] = "A genuine learning with a kind the router does not know yet."
            _write_sink(sink, [unroutable_event])

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
            adr_event = _make_event(entry_kind="adr", destination=str(tmp / "a.md"))
            adr_event["text"] = "A genuine learning that will fail to write."
            claude_md_event = _make_event(
                entry_kind="claude-md",
                destination=str(tmp / "b.md"),
                timestamp="2026-06-05T15:00:00Z",
            )
            claude_md_event["text"] = "Another genuine learning that will fail to write."
            _write_sink(sink, [adr_event, claude_md_event])

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
            retryable_event = _make_event(entry_kind="adr", destination=str(tmp / "a.md"))
            retryable_event["text"] = "A genuine learning that must survive a failed write."
            _write_sink(sink, [retryable_event])

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
            blocked_event = _make_event(
                entry_kind="adr", destination=str(blocker / "sub" / "x.md")
            )
            blocked_event["text"] = "A genuine learning whose destination is blocked."
            _write_sink(sink, [blocked_event])

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
        writable_event = _make_event(entry_kind="adr", destination=str(tmp / "a.md"))
        writable_event["text"] = "A genuine learning whose write succeeds but state save fails."
        _write_sink(sink, [writable_event])
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
            unroutable_event = _make_event(
                entry_kind="a-kind-nobody-routes",
                destination=str(tmp / "y.md"),
            )
            # Real text so this record is genuinely unroutable (unknown
            # entry_kind, producing the exit-3 backlog this test is about)
            # rather than textless.
            unroutable_event["text"] = "A genuine learning with a kind nobody routes yet."
            _write_sink(sink, [unroutable_event])

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
            blocked_event = _make_event(
                entry_kind="adr", destination=str(blocker / "sub" / "x.md")
            )
            blocked_event["text"] = "A genuine learning whose write will fail."
            unroutable_event = _make_event(
                entry_kind="a-kind-nobody-routes",
                destination=str(tmp / "y.md"),
                timestamp="2026-06-05T16:00:00Z",
            )
            unroutable_event["text"] = "A genuine learning with a kind nobody routes yet."
            _write_sink(sink, [blocked_event, unroutable_event])

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


# ---------------------------------------------------------------------------
# INF-700c-1 — nothing enters the knowledge record that is not real knowledge
# ---------------------------------------------------------------------------


class TestTextlessRecordAppendsNothing(unittest.TestCase):
    """INF-700c-1: a record with no learning text must not touch its
    destination at all -- capture_fn is never invoked and the destination's
    bytes are unchanged."""

    def test_record_without_text_appends_nothing_and_leaves_destination_unchanged(
        self,
    ) -> None:
        # covers: INF-700c-1
        # angle: criterion
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            processed = tmp / "harvest_state.json"
            dest = tmp / "memory" / "existing.md"
            dest.parent.mkdir(parents=True)
            original_content = "# Existing knowledge\n\nSome real hand-written learning.\n"
            dest.write_text(original_content, encoding="utf-8")
            before_hash = hashlib.sha256(dest.read_bytes()).hexdigest()

            event = _make_bare_event(entry_kind="adr", destination=str(dest))
            _write_sink(sink, [event])

            capture_calls: list[tuple[str, str]] = []

            def fake_capture(learning_text: str, destination_path: str) -> None:
                capture_calls.append((learning_text, destination_path))

            harvest(sink_path=sink, state_path=processed, capture_fn=fake_capture)

            self.assertEqual(
                capture_calls, [], "capture_fn must never be invoked for a textless record"
            )
            after_hash = hashlib.sha256(dest.read_bytes()).hexdigest()
            self.assertEqual(before_hash, after_hash, "destination bytes must be unchanged")
            self.assertEqual(dest.read_text(encoding="utf-8"), original_content)


class TestTextlessRecordCreatesNoDestinationFile(unittest.TestCase):
    """INF-700c-1: a textless record naming a destination that has never
    existed must leave the path absent -- covers the one of ten real
    destinations (memory/feedback_itpo_bo1700_worktree_gate_parity.md) that
    was never created."""

    def test_record_without_text_creates_no_destination_file(self) -> None:
        # covers: INF-700c-1
        # angle: boundary
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            processed = tmp / "harvest_state.json"
            dest = tmp / "memory" / "never_created.md"

            event = _make_bare_event(entry_kind="adr", destination=str(dest))
            _write_sink(sink, [event])

            capture_called = [False]

            def fake_capture(_text: str, _dest: str) -> None:
                capture_called[0] = True

            harvest(sink_path=sink, state_path=processed, capture_fn=fake_capture)

            self.assertFalse(capture_called[0])
            self.assertFalse(dest.exists())
            self.assertFalse(
                dest.parent.exists(),
                "the writer must not mkdir the destination's parent for an ineligible record",
            )


class TestNoPlaceholderSynthesised(unittest.TestCase):
    """INF-700c-1: the harvester must never compose a
    '[<entry_kind>] Learning from <ticket>' stand-in line, and must not be
    fooled by an emitter that inlines the same restatement as real `text`."""

    def test_no_placeholder_line_is_synthesised_from_descriptive_fields(self) -> None:
        # covers: INF-700c-1
        # angle: criterion
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            processed = tmp / "harvest_state.json"
            dest = tmp / "memory" / "no_placeholder.md"

            event = _make_bare_event(
                entry_kind="agent-assignment-pattern", destination=str(dest)
            )
            _write_sink(sink, [event])

            captured_texts: list[str] = []

            def fake_capture(learning_text: str, destination_path: str) -> None:
                captured_texts.append(learning_text)

            result = harvest(sink_path=sink, state_path=processed, capture_fn=fake_capture)

            self.assertEqual(captured_texts, [])
            summary = result.summary()
            for surface in (summary, *captured_texts):
                self.assertNotRegex(
                    surface,
                    r"\[agent-assignment-pattern\] Learning from",
                    "the deleted placeholder pattern must not appear anywhere in the run's output",
                )

            # Restatement guard (it_requirements #3): a `text` value that is
            # merely the record's own descriptive fields glued together --
            # the exact string the deleted default used to compose -- must
            # also be treated as no-learning-text, not as real content.
            restated_dest = tmp / "memory" / "restated.md"
            restated_event = _make_bare_event(
                entry_kind="agent-assignment-pattern",
                destination=str(restated_dest),
                timestamp="2026-06-05T14:01:00Z",
            )
            restated_event["text"] = "[agent-assignment-pattern] Learning from "
            sink2 = tmp / "sink2.jsonl"
            _write_sink(sink2, [restated_event])

            result2 = harvest(
                sink_path=sink2, state_path=tmp / "state2.json", capture_fn=fake_capture
            )
            self.assertEqual(captured_texts, [])
            self.assertEqual(
                result2.no_learning_text,
                1,
                "a restated placeholder must be classified as no-learning-text, "
                "not accepted as real content",
            )


class TestTextlessRecordsCountedSeparately(unittest.TestCase):
    """INF-700c-1: the no-learning-text bucket is distinct from routed,
    skipped_unknown and write_failures, and the four (plus previously
    processed) buckets sum to the number of knowledge records read."""

    def test_textless_records_are_counted_separately_from_unroutable_and_written(
        self,
    ) -> None:
        # covers: INF-700c-1
        # angle: criterion
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            processed = tmp / "harvest_state.json"

            textless_known_kind = _make_bare_event(
                entry_kind="adr", destination=str(tmp / "a.md")
            )
            unroutable_kind = _make_bare_event(
                entry_kind="totally-unknown-kind",
                destination=str(tmp / "b.md"),
                timestamp="2026-06-05T14:01:00Z",
            )
            # Has text but an unrecognised entry_kind -- this is what actually
            # makes the record *unroutable* rather than *textless*. Under the
            # AC's classification-order rule (no-learning-text is checked
            # BEFORE entry_kind), a record with no text at all can never land
            # in skipped_unknown regardless of its entry_kind, so this record
            # needs real content to exercise the unroutable-kind path this
            # test is actually about.
            unroutable_kind["text"] = "Has text but an unknown kind."
            real_record = dict(
                _make_bare_event(
                    entry_kind="claude-md",
                    destination=str(tmp / "c.md"),
                    timestamp="2026-06-05T14:02:00Z",
                )
            )
            real_record["text"] = "A genuine learning about the build pipeline."

            _write_sink(sink, [textless_known_kind, unroutable_kind, real_record])

            result = harvest(sink_path=sink, state_path=processed, capture_fn=lambda t, d: None)

            self.assertEqual(result.no_learning_text, 1)
            self.assertEqual(result.skipped_unknown, 1)
            self.assertEqual(result.routed, 1)
            self.assertNotEqual(
                result.no_learning_text,
                result.skipped_unknown + result.routed,
                "sanity: the buckets must be genuinely distinguishable counters",
            )

            total_records = 3
            self.assertEqual(
                result.routed
                + result.previously_processed
                + result.skipped_unknown
                + result.write_failures
                + result.no_learning_text,
                total_records,
                "the five buckets must sum to the number of knowledge records read",
            )


class TestTextlessClassifiedBeforeEntryKindRouting(unittest.TestCase):
    """INF-700c-1: classification order is load-bearing. A record that is
    BOTH textless and unknown-entry_kind (the shape of all 28 real records)
    must land in no_learning_text, never in skipped_unknown -- otherwise
    INF-700c-2's exit-0 resting state can never be reached."""

    def test_textless_record_is_classified_before_entry_kind_routing(self) -> None:
        # covers: INF-700c-1
        # angle: seam
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            processed = tmp / "harvest_state.json"

            event = _make_bare_event(
                entry_kind="agent-assignment-pattern",  # unknown kind AND no text
                destination=str(tmp / "memory" / "x.md"),
            )
            _write_sink(sink, [event])

            result = harvest(sink_path=sink, state_path=processed, capture_fn=lambda t, d: None)

            self.assertEqual(result.no_learning_text, 1)
            self.assertEqual(
                result.skipped_unknown,
                0,
                "an unknown-AND-textless record must be classified as "
                "no_learning_text, not skipped_unknown -- kind-first ordering "
                "pins the exit code non-zero forever",
            )


class TestFullRealCorpusWritesNothing(unittest.TestCase):
    """INF-700c-1: the real 28-record corpus is entirely textless. Every one
    of the ten real destinations named by those records must be left
    untouched: the nine that exist are byte-identical afterwards, the tenth
    (memory/feedback_itpo_bo1700_worktree_gate_parity.md, which has never
    existed in git history) is still absent.

    Real-artifact behavioral test: the fixture corpus (verbatim capture of
    the real sink, see TestFullCorpusAllUnroutable above) is written to a
    real sink file, `harvest()` runs unmocked, and the staged destination
    copies are hashed and read back directly off disk.
    """

    _MISSING_DESTINATION = "memory/feedback_itpo_bo1700_worktree_gate_parity.md"

    def test_full_real_corpus_of_28_writes_nothing_and_creates_nothing(self) -> None:
        # covers: INF-700c-1
        # angle: real_artifact
        events = load_fixture("harvest_learnings/unroutable_corpus_28")
        self.assertEqual(len(events), 28, "fixture drift -- expected 28 events")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            processed = tmp / "harvest_state.json"

            # Stage the ten real (relative) destinations as temp-directory
            # copies: nine get realistic pre-existing content, the tenth is
            # left absent, matching the real repo state.
            before_hashes: dict[str, str] = {}
            rewritten_events = []
            for ev in events:
                rel_dest = ev["destination"]
                staged_dest = tmp / rel_dest
                if rel_dest != self._MISSING_DESTINATION:
                    staged_dest.parent.mkdir(parents=True, exist_ok=True)
                    if not staged_dest.exists():
                        staged_dest.write_text(
                            f"# {rel_dest}\n\nReal curated content pre-dating this run.\n",
                            encoding="utf-8",
                        )
                    before_hashes[rel_dest] = hashlib.sha256(
                        staged_dest.read_bytes()
                    ).hexdigest()
                rewritten_events.append({**ev, "destination": str(staged_dest)})

            _write_sink(sink, rewritten_events)

            capture_calls: list[tuple[str, str]] = []

            def fake_capture(learning_text: str, destination_path: str) -> None:
                capture_calls.append((learning_text, destination_path))

            result = harvest(sink_path=sink, state_path=processed, capture_fn=fake_capture)

            self.assertEqual(capture_calls, [], "no write may occur for an all-textless corpus")
            self.assertEqual(result.routed, 0)
            self.assertEqual(result.no_learning_text, 28)

            for rel_dest, before_hash in before_hashes.items():
                staged_dest = tmp / rel_dest
                after_hash = hashlib.sha256(staged_dest.read_bytes()).hexdigest()
                self.assertEqual(
                    after_hash, before_hash, f"{rel_dest} must be byte-identical after the run"
                )

            missing_dest = tmp / self._MISSING_DESTINATION
            self.assertFalse(
                missing_dest.exists(), "the destination that never existed must still not exist"
            )

            if processed.exists():
                with open(processed, encoding="utf-8") as fh:
                    persisted = json.load(fh)
                self.assertEqual(
                    persisted, [], "no ineligible record's hash may be persisted to state"
                )

            # it_requirements consequence: an all-ineligible run has
            # skipped_unknown == 0 and write_failures == 0, so the CLI must
            # exit 0 -- the same code an empty input returns.
            proc = subprocess.run(
                [
                    sys.executable,
                    str(_HARVEST_PATH),
                    "--sink",
                    str(sink),
                    "--state",
                    str(tmp / "cli_state.json"),
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            self.assertEqual(
                proc.returncode,
                0,
                f"an all-textless run must exit 0, not a new non-zero code; "
                f"stdout={proc.stdout} stderr={proc.stderr}",
            )


class TestRecordWithRealTextIsStillWritten(unittest.TestCase):
    """INF-700c-1 anti-cheat: the eligibility rule must not suppress a
    record that carries genuine, non-empty text with a known entry_kind --
    guards against a coder satisfying the AC by writing nothing at all."""

    def test_record_with_real_text_is_still_written(self) -> None:
        # covers: INF-700c-1
        # angle: criterion
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            processed = tmp / "harvest_state.json"
            dest = tmp / "memory" / "real.md"

            event = _make_bare_event(entry_kind="adr", destination=str(dest))
            event["text"] = "A real, hand-composed learning about build sequencing."
            _write_sink(sink, [event])

            captured: list[tuple[str, str]] = []

            def fake_capture(learning_text: str, destination_path: str) -> None:
                captured.append((learning_text, destination_path))

            result = harvest(sink_path=sink, state_path=processed, capture_fn=fake_capture)

            self.assertEqual(result.routed, 1)
            self.assertEqual(result.no_learning_text, 0)
            self.assertEqual(len(captured), 1)
            self.assertEqual(captured[0][0], event["text"])


# ---------------------------------------------------------------------------
# INF-700c-1-i — a malformed line does not derail the run and is never
# written as knowledge
# ---------------------------------------------------------------------------


class TestMalformedLineDoesNotStopRead(unittest.TestCase):
    """INF-700c-1-i: a non-JSON line does not abort the read -- well-formed
    records before and after it are both processed in a single run."""

    def test_malformed_line_does_not_stop_the_read(self) -> None:
        # covers: INF-700c-1-i
        # angle: criterion
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            processed = tmp / "harvest_state.json"

            before_record = dict(
                _make_bare_event(entry_kind="adr", destination=str(tmp / "before.md"))
            )
            before_record["text"] = "Learning recorded before the corruption."
            after_record = dict(
                _make_bare_event(
                    entry_kind="claude-md",
                    destination=str(tmp / "after.md"),
                    timestamp="2026-06-05T14:05:00Z",
                )
            )
            after_record["text"] = "Learning recorded after the corruption."

            lines = [json.dumps(before_record), "</content>", json.dumps(after_record)]
            sink.write_text("\n".join(lines) + "\n", encoding="utf-8")

            captured: list[str] = []
            result = harvest(
                sink_path=sink, state_path=processed, capture_fn=lambda t, d: captured.append(d)
            )

            self.assertEqual(result.routed, 2)
            self.assertIn(str(tmp / "before.md"), captured)
            self.assertIn(str(tmp / "after.md"), captured)


class TestMalformedLineNumberReported(unittest.TestCase):
    """INF-700c-1-i: the malformed line's 1-based line number must match the
    file on disk, counting blank lines toward the numbering."""

    def test_malformed_line_is_reported_with_its_one_based_line_number(self) -> None:
        # covers: INF-700c-1-i
        # angle: criterion
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            processed = tmp / "harvest_state.json"

            good = dict(_make_bare_event(entry_kind="adr", destination=str(tmp / "x.md")))
            good["text"] = "Real learning."
            # Two leading blank lines, then a valid record, then the
            # malformed line at (1-based) line 4.
            lines = ["", "", json.dumps(good), "</content>"]
            sink.write_text("\n".join(lines) + "\n", encoding="utf-8")

            result = harvest(sink_path=sink, state_path=processed, capture_fn=lambda t, d: None)

            self.assertEqual(result.malformed_lines, 1)
            self.assertEqual(result.malformed_line_numbers, [4])


class TestMalformedCountIsSeparateBucket(unittest.TestCase):
    """INF-700c-1-i: the malformed-line count is a fifth bucket, distinct
    from routed / no_learning_text / skipped_unknown, and counts LINES --
    it must be excluded from the record-total invariant."""

    def test_malformed_line_count_is_separate_from_the_other_buckets(self) -> None:
        # covers: INF-700c-1-i
        # angle: criterion
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            processed = tmp / "harvest_state.json"

            routed_record = dict(
                _make_bare_event(entry_kind="adr", destination=str(tmp / "r.md"))
            )
            routed_record["text"] = "Real learning."
            textless_record = _make_bare_event(
                entry_kind="claude-md",
                destination=str(tmp / "t.md"),
                timestamp="2026-06-05T14:01:00Z",
            )
            unroutable_record = _make_bare_event(
                entry_kind="never-seen-kind",
                destination=str(tmp / "u.md"),
                timestamp="2026-06-05T14:02:00Z",
            )
            unroutable_record["text"] = "Has text but an unknown kind."

            lines = [
                json.dumps(routed_record),
                "</content>",
                json.dumps(textless_record),
                "not even json {{{",
                json.dumps(unroutable_record),
            ]
            sink.write_text("\n".join(lines) + "\n", encoding="utf-8")

            result = harvest(sink_path=sink, state_path=processed, capture_fn=lambda t, d: None)

            self.assertEqual(result.malformed_lines, 2)
            self.assertEqual(result.routed, 1)
            self.assertEqual(result.no_learning_text, 1)
            self.assertEqual(result.skipped_unknown, 1)

            total_records = 3
            self.assertEqual(
                result.routed
                + result.previously_processed
                + result.skipped_unknown
                + result.write_failures
                + result.no_learning_text,
                total_records,
                "malformed_lines counts LINES and must not participate in "
                "the record-total invariant",
            )


class TestMalformedLineContentNeverWritten(unittest.TestCase):
    """INF-700c-1-i: no destination file, capture_fn call, or summary string
    may contain any substring of the malformed line's content."""

    def test_malformed_line_content_is_never_written_to_a_knowledge_surface(self) -> None:
        # covers: INF-700c-1-i
        # angle: criterion
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            processed = tmp / "harvest_state.json"
            dest = tmp / "memory" / "clean.md"

            good = dict(_make_bare_event(entry_kind="adr", destination=str(dest)))
            good["text"] = "Real learning, nothing to do with the corruption."
            malformed_fragment = "<UNIQUE_CORRUPT_FRAGMENT_9f31>"
            lines = [json.dumps(good), malformed_fragment]
            sink.write_text("\n".join(lines) + "\n", encoding="utf-8")

            captured_texts: list[str] = []

            def fake_capture(learning_text: str, destination_path: str) -> None:
                captured_texts.append(learning_text)
                Path(destination_path).parent.mkdir(parents=True, exist_ok=True)
                with open(destination_path, "a", encoding="utf-8") as fh:
                    fh.write(learning_text + "\n")

            result = harvest(sink_path=sink, state_path=processed, capture_fn=fake_capture)

            self.assertEqual(result.malformed_lines, 1)
            self.assertTrue(dest.exists())
            written = dest.read_text(encoding="utf-8")
            self.assertNotIn(malformed_fragment, written)
            for text in captured_texts:
                self.assertNotIn(malformed_fragment, text)
            self.assertNotIn(malformed_fragment, result.summary())


class TestSinkFileByteIdenticalAfterRun(unittest.TestCase):
    """INF-700c-1-i: the sink is a reader's input, never rewritten -- the
    malformed line stays in the file so the damage remains inspectable."""

    def test_sink_file_is_byte_identical_after_the_run(self) -> None:
        # covers: INF-700c-1-i
        # angle: criterion
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            processed = tmp / "harvest_state.json"

            good = dict(_make_bare_event(entry_kind="adr", destination=str(tmp / "d.md")))
            good["text"] = "Real learning."
            lines = [json.dumps(good), "</content>"]
            sink.write_text("\n".join(lines) + "\n", encoding="utf-8")
            before_bytes = sink.read_bytes()

            harvest(sink_path=sink, state_path=processed, capture_fn=lambda t, d: None)

            after_bytes = sink.read_bytes()
            self.assertEqual(
                before_bytes,
                after_bytes,
                "the reader must never rewrite, repair, or line-delete its input file",
            )
            self.assertIn(
                b"</content>",
                after_bytes,
                "the malformed line must remain in the file, inspectable",
            )


class TestJsonScalarLineTreatedAsMalformed(unittest.TestCase):
    """INF-700c-1-i: a line that parses as JSON but is not an object (a bare
    string, number, list, or null) must be counted as malformed, not crash
    the run with an uncaught AttributeError from a `.get()` call."""

    def test_json_scalar_line_is_treated_as_malformed_rather_than_crashing(self) -> None:
        # covers: INF-700c-1-i
        # angle: failure
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            processed = tmp / "harvest_state.json"

            good = dict(_make_bare_event(entry_kind="adr", destination=str(tmp / "s.md")))
            good["text"] = "Real learning after a bare scalar line."
            # A bare JSON string is valid JSON (json.loads succeeds) but is
            # not an object, so a naive `.get()` call raises AttributeError.
            lines = ['"done"', json.dumps(good)]
            sink.write_text("\n".join(lines) + "\n", encoding="utf-8")

            try:
                result = harvest(
                    sink_path=sink, state_path=processed, capture_fn=lambda t, d: None
                )
            except AttributeError as exc:
                self.fail(f"a bare JSON scalar line must not crash the run: {exc}")

            self.assertEqual(result.malformed_lines, 1)
            self.assertEqual(result.routed, 1)


class TestRealStreamReportsFragmentAtLine19(unittest.TestCase):
    """INF-700c-1-i: reproduces the real corruption shape named in the AC's
    own notes -- line 19 of the live sink is the literal string
    `</content>`, with a well-formed knowledge_captured record immediately
    on line 20 after it. All well-formed non-knowledge/probe lines and the
    real record are generated via `json.dumps` at run time (never a
    hand-typed literal), per the fixture authenticity rule.
    """

    def test_run_over_the_real_stream_reports_the_content_fragment_at_line_19(self) -> None:
        # covers: INF-700c-1-i
        # angle: real_artifact
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            processed = tmp / "harvest_state.json"

            filler_probe = {"probe": "pre-drive-check"}
            filler_agent_start = {
                "event": "agent_start",
                "timestamp": "2026-06-05T14:00:00Z",
                "agent": "python-coder",
            }
            # 18 filler lines, matching the real stream's mix of probe and
            # lifecycle events -- none of them knowledge_captured.
            filler_lines = [
                json.dumps(filler_probe if i % 2 == 0 else filler_agent_start)
                for i in range(18)
            ]
            record_after = dict(
                _make_bare_event(
                    entry_kind="adr",
                    destination=str(tmp / "after_corruption.md"),
                    timestamp="2026-06-05T14:30:00Z",
                )
            )
            record_after["text"] = "Real learning immediately after the corrupt line."

            all_lines = [*filler_lines, "</content>", json.dumps(record_after)]
            self.assertEqual(
                len(all_lines), 20, "fixture shape check: line 19 is the corrupt fragment"
            )
            sink.write_text("\n".join(all_lines) + "\n", encoding="utf-8")

            captured: list[str] = []
            result = harvest(
                sink_path=sink, state_path=processed, capture_fn=lambda t, d: captured.append(d)
            )

            self.assertEqual(result.malformed_lines, 1)
            self.assertEqual(result.malformed_line_numbers, [19])
            self.assertEqual(result.routed, 1)
            self.assertIn(str(tmp / "after_corruption.md"), captured)


# ---------------------------------------------------------------------------
# INF-400b-2-i: re-key the idempotency digest away from the always-absent
# `ticket` field onto the required set every real producer populates
# (timestamp, agent, component, destination, entry_kind), per INF-400b-2-ii's
# reconciled shape. See KI-KM-010 second half.
#
# CONTRACT THESE TESTS ESTABLISH (test-writer runs before python-coder; this
# is the target the implementation must satisfy, not a restatement of
# existing behaviour):
#
#   1. ``_event_hash(event)`` must build its digest from exactly the fields
#      (timestamp, agent, component, destination, entry_kind) and MUST NOT
#      read ``ticket`` under any spelling, including a defaulted-to-empty
#      ``event.get("ticket", "")`` lookup -- that lookup is the present bug.
#   2. ``_event_hash`` must require each of those five fields to be an
#      actual key in *event* -- not merely present-with-a-default. When a
#      required field is absent, ``_event_hash`` must raise
#      ``KeyError`` naming the missing field, rather than silently
#      substituting ``""`` (the substitution path that produced this
#      defect for ``ticket``).
#   3. ``harvest()`` must catch that ``KeyError`` per-record (not per-line
#      -- the record parsed as valid JSON, it is simply missing a field the
#      digest requires), report it via a new ``HarvestResult`` counter/list
#      pairing -- ``missing_required_field_count: int`` and
#      ``missing_required_field_lines: list[int]`` (1-based source line
#      numbers, mirroring ``malformed_line_numbers``) -- log a WARNING
#      naming the line number and the missing field, and ``continue`` to
#      the next line without crashing the run and without adding the
#      record's hash to the idempotency state (so it is retried once the
#      producer is fixed). This must be a distinct bucket from
#      ``malformed_lines`` (KI-KM-011's territory; must not be conflated
#      per this AC's it_requirements) and must not change the harvester's
#      exit-code vocabulary (0/1/2/3).
# ---------------------------------------------------------------------------


_REQUIRED_DIGEST_FIELDS = ("timestamp", "agent", "component", "destination", "entry_kind")


class TestTwoSameDaySameDestinationSameKindRecordsAreBothProcessed(unittest.TestCase):
    """INF-400b-2-i: the collision test.

    Reproduces the defect exactly as KI-KM-010 describes it: two DIFFERENT
    real producers (different ``agent``/``component``) emit on the same day,
    to the same destination, classified with the same ``entry_kind``. Under
    the current (ticket, timestamp, destination, entry_kind) digest -- with
    ``ticket`` always defaulted to ``""`` -- these two records are
    indistinguishable, so a harvest run occurring AFTER the first record's
    hash has already been persisted to state (the realistic multi-run
    scenario: the sink is append-only and the harvester runs periodically)
    silently drops the second record as "previously processed".

    This is a two-run test, not a single-run test, because within a single
    ``harvest()`` call the in-memory ``seen`` set is not updated until after
    the whole file is read -- the collision only bites once one record's
    hash has already reached the on-disk state file from a PRIOR run.
    """

    def test_two_same_day_same_destination_same_kind_records_are_both_processed(
        self,
    ) -> None:
        # covers: INF-400b-2-i
        # angle: criterion
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            processed = tmp / "harvest_state.json"
            dest = str(tmp / "memory" / "shared_destination.md")

            record_a = _make_bare_event(
                entry_kind="memory-project",
                destination=dest,
                agent="product-owner",
                component="ac_pipeline",
                timestamp="2026-06-16T00:00:00Z",
            )
            record_a["text"] = "Learning A: captured by product-owner."

            record_b = _make_bare_event(
                entry_kind="memory-project",
                destination=dest,
                agent="business-analyst",
                component="ac_pipeline",
                timestamp="2026-06-16T00:00:00Z",
            )
            record_b["text"] = "Learning B: a genuinely different learning from a different agent."

            captured_texts: list[str] = []

            def fake_capture(learning_text: str, destination_path: str) -> None:
                captured_texts.append(learning_text)

            # Run 1: only record A exists in the sink. Its hash is persisted
            # to the on-disk state file.
            sink1 = tmp / "sink_run1.jsonl"
            _write_sink(sink1, [record_a])
            result1 = harvest(sink_path=sink1, state_path=processed, capture_fn=fake_capture)
            self.assertEqual(result1.routed, 1)

            # Run 2 (later, same append-only sink now also carries record B):
            # a real harvester re-reads the WHOLE sink each run and relies on
            # the persisted state file for idempotency, so replay both lines.
            sink2 = tmp / "sink_run2.jsonl"
            _write_sink(sink2, [record_a, record_b])
            result2 = harvest(sink_path=sink2, state_path=processed, capture_fn=fake_capture)

            # Record A must be recognised as already processed; record B —
            # captured by a different agent, so a genuinely distinct
            # learning under the reconciled key — must be newly routed.
            self.assertEqual(
                result2.previously_processed,
                1,
                "record A should be recognised as already processed on run 2",
            )
            self.assertEqual(
                result2.routed,
                1,
                "record B must be processed as a NEW record, not folded into A's digest",
            )
            self.assertIn("Learning A: captured by product-owner.", captured_texts)
            self.assertIn(
                "Learning B: a genuinely different learning from a different agent.",
                captured_texts,
                "record B was silently dropped as a duplicate of A -- "
                "the exact collision this AC exists to close",
            )


class TestDigestChangesWhenAnyRequiredFieldChanges(unittest.TestCase):
    """INF-400b-2-i: each of the five required fields must contribute to the
    digest. A field that never varies the output cannot discriminate
    anything -- which is exactly how ``ticket`` (always defaulted to ``""``)
    became a no-op key component in the first place.
    """

    # NOTE: deliberately five separate test methods, NOT a single method with
    # unittest subTest() over _REQUIRED_DIGEST_FIELDS. The fast-lane red-
    # baseline runner (.leafcutter/scripts/build_orchestration/fast_lane.py)
    # observes only the outer test outcome per pytest node; a subTest
    # failure does not flip that outer outcome to FAILED under this runner
    # (verified empirically: the "agent" and "component" subTests fail
    # under AC_ENFORCE_STRICT=1 while the aggregate node still reports
    # PASSED). Five discrete nodes give the gate one outcome per field,
    # which is exactly what this AC's collision -- caused by two of these
    # five fields silently contributing nothing -- needs to be caught by.

    def _assert_field_changes_digest(self, field: str) -> None:
        base = _make_bare_event(
            entry_kind="memory-project",
            destination="memory/foo.md",
            agent="python-coder",
            component="knowledge_system",
            timestamp="2026-06-16T00:00:00Z",
        )
        base_hash = _mod._event_hash(base)
        variant = dict(base)
        variant[field] = variant[field] + "-DIFFERENT"
        variant_hash = _mod._event_hash(variant)
        self.assertNotEqual(
            base_hash,
            variant_hash,
            f"changing required field {field!r} did not change the digest -- "
            "this field contributes nothing to identity, reproducing the "
            "original `ticket` defect",
        )

    def test_the_digest_changes_when_timestamp_changes(self) -> None:
        # covers: INF-400b-2-i
        # angle: seam
        self._assert_field_changes_digest("timestamp")

    def test_the_digest_changes_when_agent_changes(self) -> None:
        # covers: INF-400b-2-i
        # angle: seam
        self._assert_field_changes_digest("agent")

    def test_the_digest_changes_when_component_changes(self) -> None:
        # covers: INF-400b-2-i
        # angle: seam
        self._assert_field_changes_digest("component")

    def test_the_digest_changes_when_destination_changes(self) -> None:
        # covers: INF-400b-2-i
        # angle: seam
        self._assert_field_changes_digest("destination")

    def test_the_digest_changes_when_entry_kind_changes(self) -> None:
        # covers: INF-400b-2-i
        # angle: seam
        self._assert_field_changes_digest("entry_kind")


class TestDigestIgnoresFieldsAbsentFromRequiredShape(unittest.TestCase):
    """INF-400b-2-i: optional fields (``ticket``, ``text``) must NOT affect
    the digest. Hashing the whole record (the tempting over-correction) would
    restore discrimination and then break idempotency the instant an
    optional field appears on a re-emitted record.
    """

    def test_the_digest_ignores_fields_absent_from_the_required_shape(self) -> None:
        # covers: INF-400b-2-i
        # angle: seam
        bare = _make_bare_event(
            entry_kind="adr",
            destination="memory/bar.md",
            agent="it-po",
            component="ac_pipeline",
            timestamp="2026-06-16T00:00:00Z",
        )
        bare_hash = _mod._event_hash(bare)

        with_ticket = dict(bare)
        with_ticket["ticket"] = "tickets/some-ticket.md"
        self.assertEqual(
            bare_hash,
            _mod._event_hash(with_ticket),
            "presence of the optional `ticket` field changed the digest -- "
            "optionality was not honoured",
        )

        with_text = dict(bare)
        with_text["text"] = "Some real learning content."
        self.assertEqual(
            bare_hash,
            _mod._event_hash(with_text),
            "presence of the optional `text` field changed the digest -- "
            "content must never be part of identity",
        )

        with_both = dict(bare)
        with_both["ticket"] = "tickets/some-ticket.md"
        with_both["text"] = "Some real learning content."
        self.assertEqual(bare_hash, _mod._event_hash(with_both))


class TestEveryRequiredKeyComponentIsPopulatedAcrossTheRealCorpus(unittest.TestCase):
    """INF-400b-2-i: real-artifact test. Runs the digest over the actual
    28-record corpus (not a hand-authored fixture -- a hand-authored one
    would have populated every documented field, which is the exact
    assumption that hid this defect for two months) and asserts every
    required field is genuinely present and non-empty in every record, and
    that the 28 records yield 28 distinct digests.
    """

    def test_every_required_key_component_is_populated_across_the_real_corpus(
        self,
    ) -> None:
        # covers: INF-400b-2-i
        # angle: real_artifact
        events = load_fixture("harvest_learnings/unroutable_corpus_28")
        self.assertEqual(len(events), 28, "fixture drift -- expected 28 events")

        digests: set[str] = set()
        for i, event in enumerate(events):
            for field in _REQUIRED_DIGEST_FIELDS:
                self.assertIn(
                    field,
                    event,
                    f"record {i} is missing required digest field {field!r}",
                )
                self.assertTrue(
                    str(event[field]).strip(),
                    f"record {i} has an empty required digest field {field!r}",
                )
            digests.add(_mod._event_hash(event))

        self.assertEqual(
            len(digests),
            28,
            "the 28 real records must yield 28 distinct digests under the "
            "reconciled required-field key",
        )


class TestRerunningOverAnUnchangedCorpusProcessesNothingTwice(unittest.TestCase):
    """INF-400b-2-i: the re-keyed digest must not sacrifice idempotency to
    buy discrimination. Two consecutive runs over an unchanged corpus deal
    with every eligible record on the first run and nothing on the second.
    """

    def test_rerunning_over_an_unchanged_corpus_processes_nothing_twice(self) -> None:
        # covers: INF-400b-2-i
        # angle: criterion
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            processed = tmp / "harvest_state.json"

            events = []
            for i in range(3):
                ev = _make_bare_event(
                    entry_kind="memory-project",
                    destination=str(tmp / f"dest_{i}.md"),
                    agent=f"agent-{i}",
                    component="knowledge_system",
                    timestamp="2026-06-16T00:00:00Z",
                )
                ev["text"] = f"Distinct real learning number {i}."
                events.append(ev)
            _write_sink(sink, events)

            call_count = [0]

            def fake_capture(learning_text: str, destination_path: str) -> None:
                call_count[0] += 1

            result1 = harvest(sink_path=sink, state_path=processed, capture_fn=fake_capture)
            self.assertEqual(result1.routed, 3)
            self.assertEqual(call_count[0], 3)

            result2 = harvest(sink_path=sink, state_path=processed, capture_fn=fake_capture)
            self.assertEqual(result2.routed, 0)
            self.assertEqual(result2.previously_processed, 3)
            self.assertEqual(call_count[0], 3, "no new capture_fn calls on the second run")


class TestARecordMissingARequiredKeyFieldIsReportedNotSilentlyHashed(unittest.TestCase):
    """INF-400b-2-i: closing the substitution path that created this defect
    in the first place. A record lacking a field the digest requires must be
    reported with its line number, never silently folded into an
    empty-string default and hashed as if it were a normal record.
    """

    def test_missing_required_field_raises_from_event_hash(self) -> None:
        # covers: INF-400b-2-i
        # angle: failure
        incomplete = _make_bare_event(
            entry_kind="adr",
            destination="memory/baz.md",
            agent="it-po",
            component="ac_pipeline",
            timestamp="2026-06-16T00:00:00Z",
        )
        del incomplete["component"]

        with self.assertRaises(KeyError):
            _mod._event_hash(incomplete)

    def test_a_record_missing_a_required_key_field_is_reported_not_silently_hashed(
        self,
    ) -> None:
        # covers: INF-400b-2-i
        # angle: failure
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            processed = tmp / "harvest_state.json"

            good = _make_bare_event(
                entry_kind="adr",
                destination=str(tmp / "good.md"),
                agent="it-po",
                component="ac_pipeline",
                timestamp="2026-06-16T00:00:00Z",
            )
            good["text"] = "A real, well-formed learning."

            broken = _make_bare_event(
                entry_kind="adr",
                destination=str(tmp / "broken.md"),
                agent="it-po",
                component="ac_pipeline",
                timestamp="2026-06-16T00:30:00Z",
            )
            broken["text"] = "A learning whose record is missing `component`."
            del broken["component"]

            # good (line 1), broken (line 2) -- a real JSONL sink, written by
            # the same serializer used everywhere else in this file.
            _write_sink(sink, [good, broken])

            captured: list[str] = []
            result = harvest(
                sink_path=sink,
                state_path=processed,
                capture_fn=lambda t, d: captured.append(d),
            )

            # The good record is still processed; the run does not crash.
            self.assertEqual(result.routed, 1)
            self.assertIn(str(tmp / "good.md"), captured)

            # The broken record is reported with its line number, not
            # silently hashed via a defaulted-to-empty substitute.
            self.assertEqual(
                getattr(result, "missing_required_field_count", 0),
                1,
                "missing-required-field records must be counted in a distinct "
                "HarvestResult bucket, not silently absorbed",
            )
            self.assertEqual(
                getattr(result, "missing_required_field_lines", []),
                [2],
                "the broken record's 1-based source line number must be reported",
            )
            self.assertNotIn(
                str(tmp / "broken.md"),
                captured,
                "a record missing a required digest field must never be written",
            )


class TestMissingRequiredFieldBucketParticipatesInTheRecordTotal(unittest.TestCase):
    """INF-400b-2-i: the seventh (module docstring: "sixth record-level")
    bucket must not be a hole a record can fall through unaccounted for.

    ``TestTextlessRecordsCountedSeparately`` and
    ``TestMalformedCountIsSeparateBucket`` (INF-700c-1 / INF-700c-1-i,
    written before this bucket existed) each assert a sum over only five
    record-level buckets. That sum is still numerically correct in both of
    those tests only because neither test ever produces a record missing a
    required digest field -- ``missing_required_field_count`` is always 0
    there, so its absence from the sum is invisible. Neither test would
    catch a regression in which a record legitimately landed in
    ``missing_required_field_count`` and simply vanished from the total.

    This test closes that gap directly: it constructs one record of each of
    the six record-level kinds (routed, previously_processed, skipped_unknown,
    write_failure, no_learning_text, missing_required_field) in a single
    sink and asserts the six-bucket sum equals the total record count -- the
    invariant the module docstring states for ``HarvestResult`` -- with
    ``missing_required_field_count`` an explicit term in the sum, not an
    incidental zero.
    """

    def test_missing_required_field_bucket_is_a_term_in_the_six_bucket_total(
        self,
    ) -> None:
        # covers: INF-400b-2-i
        # angle: criterion
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            state = tmp / "harvest_state.json"

            routed_record = _make_bare_event(
                entry_kind="adr",
                destination=str(tmp / "routed.md"),
                agent="python-coder",
                component="knowledge_system",
                timestamp="2026-06-16T00:00:00Z",
            )
            routed_record["text"] = "A genuine learning that will be routed."

            textless_record = _make_bare_event(
                entry_kind="claude-md",
                destination=str(tmp / "textless.md"),
                agent="python-coder",
                component="knowledge_system",
                timestamp="2026-06-16T00:01:00Z",
            )

            unroutable_record = _make_bare_event(
                entry_kind="never-seen-kind",
                destination=str(tmp / "unroutable.md"),
                agent="python-coder",
                component="knowledge_system",
                timestamp="2026-06-16T00:02:00Z",
            )
            unroutable_record["text"] = "Has text but an unrecognised entry_kind."

            will_fail_write_record = _make_bare_event(
                entry_kind="adr",
                destination=str(tmp / "will_fail.md"),
                agent="python-coder",
                component="knowledge_system",
                timestamp="2026-06-16T00:03:00Z",
            )
            will_fail_write_record["text"] = "A learning whose write will fail."

            missing_field_record = _make_bare_event(
                entry_kind="adr",
                destination=str(tmp / "missing_field.md"),
                agent="python-coder",
                component="knowledge_system",
                timestamp="2026-06-16T00:04:00Z",
            )
            missing_field_record["text"] = "A learning whose record is missing `component`."
            del missing_field_record["component"]

            # Run 1, sink with only the routed record, so its hash is
            # persisted -- gives us a genuine previously_processed record on
            # run 2 rather than a second synthetic bucket-filler.
            previously_processed_record = dict(routed_record)
            sink_run1 = tmp / "sink_run1.jsonl"
            _write_sink(sink_run1, [previously_processed_record])
            result1 = harvest(
                sink_path=sink_run1, state_path=state, capture_fn=lambda t, d: None
            )
            self.assertEqual(result1.routed, 1)

            def selective_fail(learning_text: str, destination_path: str) -> None:
                if destination_path == str(tmp / "will_fail.md"):
                    raise OSError("simulated write failure")
                # Real writes for everything else so this is a genuine
                # capture_fn, not a pure counter stub.
                dest = Path(destination_path)
                dest.parent.mkdir(parents=True, exist_ok=True)
                with open(dest, "a", encoding="utf-8") as fh:
                    fh.write(learning_text + "\n")

            all_six_records = [
                previously_processed_record,  # -> previously_processed
                textless_record,  # -> no_learning_text
                unroutable_record,  # -> skipped_unknown
                will_fail_write_record,  # -> write_failures
                missing_field_record,  # -> missing_required_field_count
                routed_record,  # duplicate timestamp/dest/entry_kind/agent/
                # component of previously_processed_record is intentional --
                # it is the SAME record replayed, not a distinct routed one;
                # a genuinely new routed record is added below instead.
            ]
            new_routed_record = _make_bare_event(
                entry_kind="claude-md",
                destination=str(tmp / "new_routed.md"),
                agent="python-coder",
                component="knowledge_system",
                timestamp="2026-06-16T00:05:00Z",
            )
            new_routed_record["text"] = "A second genuine learning, newly routed this run."
            all_six_records[-1] = new_routed_record

            sink_run2 = tmp / "sink_run2.jsonl"
            _write_sink(sink_run2, all_six_records)

            result2 = harvest(sink_path=sink_run2, state_path=state, capture_fn=selective_fail)

            self.assertEqual(result2.routed, 1, "only new_routed_record should be freshly routed")
            self.assertEqual(result2.previously_processed, 1)
            self.assertEqual(result2.skipped_unknown, 1)
            self.assertEqual(result2.write_failures, 1)
            self.assertEqual(result2.no_learning_text, 1)
            self.assertEqual(
                result2.missing_required_field_count,
                1,
                "the record missing `component` must land in its own bucket",
            )

            total_records = len(all_six_records)
            six_bucket_sum = (
                result2.routed
                + result2.previously_processed
                + result2.skipped_unknown
                + result2.write_failures
                + result2.no_learning_text
                + result2.missing_required_field_count
            )
            self.assertEqual(
                six_bucket_sum,
                total_records,
                "the six record-level buckets -- including "
                "missing_required_field_count -- must sum to the number of "
                "knowledge_captured records read; a record missing a "
                "required digest field must never vanish from this total "
                "(the 'bucket that doesn't participate in a total' defect "
                "INF-700c-1 warned about, applied to this newer bucket)",
            )


if __name__ == "__main__":
    unittest.main()
