"""
MODULE: test_emit_event
GOAL: Behavioral coverage for templates/skills/agent-telemetry/scripts/emit_event.py,
      the drive-observability event emitter specified by BP-400a-1 and BP-400a-1-i.
BUSINESS CONTEXT: The building-epics runbook has invoked this script eight times per
      epic drive since it was written, and the script did not exist. Every call was a
      silent no-op behind `|| true`, so no drive has ever produced telemetry — very
      likely the real cause of the "23 submit-failed events, zero telemetry captured"
      incident that was diagnosed as an unreachable sink.
ARCHITECTURE: Tests invoke main() directly with an argv list and assert on the file
      the run produces, parsed with json.loads — not on the source. BP-400a-1-i's
      non-fatal contract is exercised by making the sink genuinely unwritable (a
      directory where the file should be) rather than by mocking, so a regression that
      lets the exception escape is caught.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(
    0, str(_REPO_ROOT / "templates" / "skills" / "agent-telemetry" / "scripts")
)

import emit_event  # noqa: E402


class TestEmitEventRecord(unittest.TestCase):
    """BP-400a-1: the script appends exactly one valid JSONL line with the spec keys."""

    def test_deployed_path_exists(self):
        """The script must live at the path every call site names."""
        # covers: BP-400a-1
        target = (_REPO_ROOT / "templates" / "skills" / "agent-telemetry"
                  / "scripts" / "emit_event.py")
        self.assertTrue(target.is_file(), f"{target} must exist — 8 call sites invoke it")

    def test_appends_exactly_one_valid_json_line(self):
        """One invocation appends one parseable line, and exits 0."""
        # covers: BP-400a-1
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "logs" / "agent_telemetry.jsonl"
            rc = emit_event.main([
                "--agent", "ticket-supervisor", "--event", "agent_start",
                "--ticket", "/path/to/01_schema.md", "--phase", "python-coder",
                "--log", str(log),
            ])
            self.assertEqual(rc, 0)
            lines = log.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1, f"expected exactly 1 line, got {lines}")
            json.loads(lines[0])

    def test_record_carries_the_specified_keys(self):
        """event_type, timestamp, agent_name, ticket_path, payload — and payload's three."""
        # covers: BP-400a-1
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "t.jsonl"
            emit_event.main([
                "--agent", "ticket-supervisor", "--event", "agent_start",
                "--ticket", "/path/to/01_schema.md", "--phase", "python-coder",
                "--log", str(log),
            ])
            rec = json.loads(log.read_text(encoding="utf-8").strip())
            self.assertEqual(
                set(rec), {"event_type", "timestamp", "agent_name", "ticket_path", "payload"})
            self.assertEqual(set(rec["payload"]), {"phase", "outcome", "retry_count"})
            self.assertEqual(rec["event_type"], "agent_start")
            self.assertEqual(rec["agent_name"], "ticket-supervisor")
            self.assertEqual(rec["ticket_path"], "/path/to/01_schema.md")
            self.assertEqual(rec["payload"]["phase"], "python-coder")

    def test_absent_optionals_are_null_not_missing(self):
        """outcome and retry_count are null when not supplied — present, not omitted.

        The AC says "null if not supplied". Omitting the key instead would force every
        reader to test for presence, and would silently change shape between call sites.
        """
        # covers: BP-400a-1
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "t.jsonl"
            emit_event.main(["--agent", "a", "--event", "e", "--log", str(log)])
            rec = json.loads(log.read_text(encoding="utf-8").strip())
            self.assertIn("outcome", rec["payload"])
            self.assertIn("retry_count", rec["payload"])
            self.assertIsNone(rec["payload"]["outcome"])
            self.assertIsNone(rec["payload"]["retry_count"])
            self.assertIsNone(rec["ticket_path"])

    def test_timestamp_is_iso8601_utc(self):
        """The timestamp parses as an ISO-8601 instant and carries a UTC offset."""
        # covers: BP-400a-1
        import datetime
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "t.jsonl"
            emit_event.main(["--agent", "a", "--event", "e", "--log", str(log)])
            rec = json.loads(log.read_text(encoding="utf-8").strip())
            parsed = datetime.datetime.fromisoformat(rec["timestamp"])
            self.assertIsNotNone(parsed.tzinfo)
            self.assertEqual(parsed.utcoffset(), datetime.timedelta(0))

    def test_repeated_invocations_append(self):
        """Emission is append-only: three calls leave three lines, none corrupted."""
        # covers: BP-400a-1
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "t.jsonl"
            for i in range(3):
                emit_event.main(
                    ["--agent", "a", "--event", f"e{i}", "--log", str(log)])
            lines = log.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 3)
            self.assertEqual([json.loads(ln)["event_type"] for ln in lines],
                             ["e0", "e1", "e2"])


class TestEmitEventNonFatal(unittest.TestCase):
    """BP-400a-1-i: a write failure warns on stderr and still exits 0."""

    def test_unwritable_sink_still_exits_zero(self):
        """A sink path that is a DIRECTORY cannot be opened for append — exit 0 anyway.

        Uses a real unwritable path rather than a mock: the contract is about what the
        process does when the OS refuses, so the OS should be the one refusing.
        """
        # covers: BP-400a-1-i
        with tempfile.TemporaryDirectory() as d:
            sink = Path(d) / "iam_a_directory"
            sink.mkdir()
            rc = emit_event.main(["--agent", "a", "--event", "e", "--log", str(sink)])
            self.assertEqual(rc, 0, "telemetry failure must never fail the drive")

    def test_unwritable_sink_reports_the_drop(self):
        """Silence would be the defect. The dropped event is named on stderr."""
        # covers: BP-400a-1-i
        with tempfile.TemporaryDirectory() as d:
            sink = Path(d) / "iam_a_directory"
            sink.mkdir()
            ok = emit_event.append_record({"event_type": "e"}, sink)
            self.assertFalse(ok, "append_record must report failure to its caller")

    def test_non_serialisable_record_is_dropped_not_raised(self):
        """A record that cannot be JSON-encoded is dropped with a warning, not an exception."""
        # covers: BP-400a-1-i
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "t.jsonl"
            ok = emit_event.append_record({"bad": object()}, log)
            self.assertFalse(ok)
            self.assertFalse(log.exists(), "nothing should be written for a bad record")


if __name__ == "__main__":
    unittest.main()
