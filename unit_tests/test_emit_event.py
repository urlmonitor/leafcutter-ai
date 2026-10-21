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

import contextlib
import io
import json
import os
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
        # covers: INF-400g-1
        target = (_REPO_ROOT / "templates" / "skills" / "agent-telemetry"
                  / "scripts" / "emit_event.py")
        self.assertTrue(target.is_file(), f"{target} must exist — 8 call sites invoke it")

    def test_source_is_executable(self):
        """The script carries the executable bit, not just a shebang.

        INF-400g-1's criteria say "exists and is executable". Its it_requirements
        accept "chmod +x OR shebang line", so a shebang alone arguably satisfied it —
        but a shebang on a mode-644 file is an incoherence, and an AC marked done on
        the weaker reading is the kind of claim nobody can check later. The bit is
        asserted here so the mode survives a future rewrite of this file; build.py
        copies with shutil.copy2, which preserves it into the deploy target.
        """
        # covers: INF-400g-1
        target = (_REPO_ROOT / "templates" / "skills" / "agent-telemetry"
                  / "scripts" / "emit_event.py")
        self.assertTrue(
            os.access(target, os.X_OK),
            f"{target} must be executable — INF-400g-1 requires it, and the file "
            "carries a #! line which is meaningless without the mode bit",
        )

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
            # INF-700b-1-i (ADR-034 Amendment 2, A2.2): DELIBERATE contract extension, not a
            # weakening. Every record of every event type now also carries `missing_target`
            # (null unless given), so the "every line has the same keys" rule still holds.
            self.assertEqual(
                set(rec["payload"]),
                {"phase", "outcome", "retry_count", "missing_target"})
            self.assertIsNone(rec["payload"]["missing_target"])
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


class TestCaptureAttemptEvent(unittest.TestCase):
    """INF-700b-1-i / ADR-034 Amendment 2 (A2.2): the capture-attempt ledger event."""

    _OUTCOMES = ("recorded", "nothing-to-record", "failed")

    def _emit(self, log: Path, *argv: str) -> tuple[int, str]:
        """Run main() in-process; return (exit code, stderr). An argparse refusal is a failure."""
        err = io.StringIO()
        try:
            with contextlib.redirect_stderr(err):
                rc = emit_event.main([*argv, "--log", str(log)])
        except SystemExit as exc:
            self.fail(f"emit_event refused the call at argument parsing (exit {exc.code}): "
                      f"{err.getvalue()!r}")
        return rc, err.getvalue()

    @staticmethod
    def _records(log: Path) -> list[dict]:
        if not log.exists():
            return []
        return [json.loads(ln) for ln in log.read_text(encoding="utf-8").splitlines()]

    def test_capture_attempt_outcome_set_is_closed_and_payload_keys_stay_uniform(self):
        # covers: INF-700b-1-i
        # angle: criterion
        """capture_attempt accepts exactly {recorded, nothing-to-record, failed}; all else writes nothing.

        Wrong versions this must catch: a validator that accepts any outcome for capture_attempt;
        one that normalises case or underscores ('Recorded', 'nothing_to_record'); one that
        validates EVERY event type (the control row `agent_end --outcome ok` would then vanish);
        and `missing_target` added only to failed records (key sets would differ across lines).
        """
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "t.jsonl"
            for outcome in self._OUTCOMES:
                extra = ["--missing-target", "/x/missing.py"] if outcome == "failed" else []
                with self.subTest(accepted=outcome):
                    before = len(self._records(log))
                    rc, _ = self._emit(
                        log, "--agent", "a", "--event", "capture_attempt",
                        "--phase", "knowledge-capture", "--outcome", outcome, *extra)
                    self.assertEqual(rc, 0)
                    records = self._records(log)
                    self.assertEqual(len(records), before + 1, f"{outcome!r} must append one line")
                    self.assertEqual(records[-1]["payload"]["outcome"], outcome)
                    self.assertEqual(records[-1]["event_type"], "capture_attempt")
            accepted = len(self._records(log))
            self.assertEqual(accepted, 3)
            for bad in ("Recorded", "nothing_to_record", "ok", "", "recorded "):
                with self.subTest(refused=bad):
                    rc, stderr = self._emit(
                        log, "--agent", "a", "--event", "capture_attempt",
                        "--phase", "knowledge-capture", "--outcome", bad)
                    self.assertEqual(rc, 0, "an unknown outcome still exits 0")
                    self.assertEqual(len(self._records(log)), accepted,
                                     f"outcome {bad!r} must write nothing")
                    self.assertTrue(stderr.strip(), f"outcome {bad!r} must warn on stderr")
            with self.subTest(refused="(omitted)"):
                rc, stderr = self._emit(log, "--agent", "a", "--event", "capture_attempt")
                self.assertEqual(rc, 0)
                self.assertEqual(len(self._records(log)), accepted, "no outcome writes nothing")
                self.assertTrue(stderr.strip())
            # control row: other event types keep free-text outcomes
            for free in ("ok", "blocked", "anything at all"):
                with self.subTest(free_text=free):
                    rc, _ = self._emit(log, "--agent", "a", "--event", "agent_end", "--outcome", free)
                    self.assertEqual(rc, 0)
                    self.assertEqual(self._records(log)[-1]["payload"]["outcome"], free)
            records = self._records(log)
            self.assertEqual(len(records), accepted + 3)
            key_sets = {frozenset(r["payload"]) for r in records}
            self.assertEqual(
                key_sets, {frozenset({"phase", "outcome", "retry_count", "missing_target"})},
                "every record, capture_attempt or not, carries the same payload keys")
            for rec in records:
                if rec["payload"]["outcome"] != "failed":
                    self.assertIsNone(rec["payload"]["missing_target"])

    def test_failed_without_missing_target_is_refused_and_with_it_is_recorded(self):
        # covers: INF-700b-1-i
        # angle: failure
        """`failed` needs --missing-target: absent writes nothing, warns, exits 0; given, it is stored."""
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "t.jsonl"
            rc, stderr = self._emit(
                log, "--agent", "a", "--event", "capture_attempt",
                "--phase", "knowledge-capture", "--outcome", "failed")
            self.assertEqual(rc, 0)
            self.assertEqual(self._records(log), [], "failed with no missing_target writes nothing")
            self.assertTrue(stderr.strip(), "the refusal must be reported on stderr")
            rc, _ = self._emit(
                log, "--agent", "a", "--event", "capture_attempt", "--phase", "knowledge-capture",
                "--outcome", "failed", "--missing-target", "/deployed/emit_knowledge.py")
            self.assertEqual(rc, 0)
            records = self._records(log)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["payload"]["missing_target"], "/deployed/emit_knowledge.py")

    def test_missing_target_is_refused_on_recorded_and_nothing_to_record(self):
        # covers: INF-700b-1-i
        # angle: boundary
        """`missing_target` must be null unless outcome is `failed` (ADR-034 A2.2).

        recorded / nothing-to-record given a --missing-target write nothing, warn on stderr naming the
        flag and exit 0 (the unknown-outcome refusal path). Control rows on the SAME log: the same
        outcomes without it, and `failed` with it, are each recorded.
        """
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "t.jsonl"
            base = ("--agent", "a", "--event", "capture_attempt", "--phase", "knowledge-capture")
            for outcome in ("recorded", "nothing-to-record"):
                with self.subTest(refused=outcome):
                    rc, stderr = self._emit(log, *base, "--outcome", outcome,
                                            "--missing-target", "/x/missing.py")
                    self.assertEqual(rc, 0, "the refusal still exits 0")
                    self.assertEqual(self._records(log), [], f"{outcome!r} + missing_target writes nothing")
                    self.assertIn("missing-target", stderr, "the warning must name the offending flag")
            for outcome in ("recorded", "nothing-to-record"):
                self._emit(log, *base, "--outcome", outcome)
            self._emit(log, *base, "--outcome", "failed", "--missing-target", "/x/missing.py")
            targets = [r["payload"]["missing_target"] for r in self._records(log)]
            self.assertEqual(targets, [None, None, "/x/missing.py"])

    def test_missing_target_is_null_on_every_non_capture_record(self):
        # covers: INF-700b-1-i
        # angle: boundary
        """Even a plain agent_start line carries `missing_target`, and it is null (present, not omitted)."""
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "t.jsonl"
            self._emit(log, "--agent", "a", "--event", "agent_start", "--phase", "python-coder")
            payload = self._records(log)[0]["payload"]
            self.assertIn("missing_target", payload)
            self.assertIsNone(payload["missing_target"])


if __name__ == "__main__":
    unittest.main()
