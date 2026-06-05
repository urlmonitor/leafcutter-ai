"""
MODULE: test_harvest_learnings
GOAL: Unit tests for scripts/knowledge/harvest_learnings.py.
BUSINESS CONTEXT: Verifies that the learning harvester correctly reads
    knowledge_captured events from knowledge_emissions.jsonl, routes each
    to the appropriate knowledge surface, tracks processed events so re-runs
    are idempotent, and handles unrecognised entry_kinds gracefully.
    These tests define the acceptance gate for AC-2, AC-3, and AC-4.
ARCHITECTURE: Pure unit tests using unittest.TestCase with tempfile.TemporaryDirectory
    for filesystem isolation. The harvest function is monkeypatched so that
    the capture-learning write call is stubbed — tests verify routing decisions,
    not file-system writes to knowledge surfaces.
    All tests must complete in < 5 seconds.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Bootstrap: resolve harvest_learnings module without relying on installed pkg
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HARVEST_PATH = _REPO_ROOT / "scripts" / "knowledge" / "harvest_learnings.py"

spec = importlib.util.spec_from_file_location("harvest_learnings", _HARVEST_PATH)
_mod = importlib.util.module_from_spec(spec)
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


class TestSkipsUnrecognisedEntryKind(unittest.TestCase):
    """AC-4: harvester logs a warning for unknown entry_kind but does not crash."""

    def test_skips_unrecognized_entry_kind(self) -> None:
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

            # Unknown event is marked processed (not retried) but not routed via capture_fn
            self.assertNotIn(str(dest), written_paths)

            # Valid subsequent event still processed
            self.assertEqual(result.routed, 1)

            # Both events are marked processed (unknown + valid)
            # Re-run should process nothing
            result2 = harvest(
                sink_path=sink,
                state_path=processed,
                capture_fn=fake_capture,
            )
            self.assertEqual(result2.routed, 0)
            self.assertEqual(result2.previously_processed, 2)


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


if __name__ == "__main__":
    unittest.main()
