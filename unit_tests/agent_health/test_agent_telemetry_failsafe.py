"""
MODULE: unit_tests/agent_health/test_agent_telemetry_failsafe.py
GOAL: Fail-safe tests for DEFECT M-1 — agent_telemetry.py's json.dumps call
      sits OUTSIDE the try/except block so a TypeError from a non-JSON-
      serializable record value escapes to the caller, breaking the
      fail-loud-not-fatal contract.

=== DEFECT M-1 (TypeError escapes emit_agent_telemetry) ===

In scripts/agent-health/agent_telemetry.py:

    payload = dict(record)
    if "ts" not in payload:
        payload["ts"] = ...

    line = json.dumps(payload, ensure_ascii=False) + "\\n"  # <-- OUTSIDE try

    try:
        sink_path.parent.mkdir(parents=True, exist_ok=True)
        with open(sink_path, "a", ...) as fh:
            fh.write(line)
    except OSError as exc:
        logger.warning(...)
        _failed_write_count += 1

The json.dumps() call at line 89 is OUTSIDE the try block.  If `record`
contains a non-JSON-serializable value (e.g. a Python `set`, `Path` object,
or a custom class instance), json.dumps raises TypeError.  This TypeError is
NOT caught by the OSError handler and propagates to the caller — violating
the documented fail-safe contract.

The module docstring says:
    "Fail-loud-not-fatal: sink errors are logged and counted but never
     propagate to the caller so the build always continues even when
     telemetry is unreachable."

TypeError from json.dumps is a serialization error that breaks this contract.

=== Contract these tests enforce ===

  emit_agent_telemetry with a non-serializable record value:
  1. MUST NOT raise any exception (TypeError or otherwise)
  2. MUST increment the module-level _failed_write_count by 1
  3. MUST NOT write any partial content to the sink file

  The fix: wrap json.dumps inside the try block (or add a separate
  try/except for TypeError) and treat serialization failure the same
  way as an OSError — log a WARNING and increment the counter.

=== Red baseline ===

  All tests are RED until python-coder moves json.dumps inside the try block
  or adds a separate serialization error handler.  The current code raises
  TypeError on a set-valued record, so any test asserting "does NOT raise"
  will fail with an uncaught TypeError.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Repo path wiring
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_AGENT_HEALTH_DIR = _REPO_ROOT / "scripts" / "agent-health"
sys.path.insert(0, str(_AGENT_HEALTH_DIR))

from agent_telemetry import (  # noqa: E402
    emit_agent_telemetry,
    get_failed_write_count,
    reset_failed_write_count,
)


# ---------------------------------------------------------------------------
# TestEmitAgentTelemetryFailSafe — DEFECT M-1
# ---------------------------------------------------------------------------


class TestEmitAgentTelemetryFailSafe(unittest.TestCase):
    """Tests that emit_agent_telemetry is truly fail-safe for all record values.

    The module contract: "sink errors are logged and counted but never
    propagate to the caller so the build always continues."

    DEFECT M-1 violates this contract for non-JSON-serializable record values.
    """

    def setUp(self) -> None:
        """Reset the failed-write counter for test isolation."""
        reset_failed_write_count()
        self._tmp = tempfile.TemporaryDirectory()
        self.sink_path = Path(self._tmp.name) / "telemetry.jsonl"

    def tearDown(self) -> None:
        reset_failed_write_count()
        self._tmp.cleanup()

    def test_m1_set_value_does_not_raise(self) -> None:
        # covers: BO-2400d-1
        """emit_agent_telemetry must NOT raise when a record value is a Python set.

        DEFECT M-1: json.dumps({..., "tags": {1, 2, 3}}) raises TypeError because
        sets are not JSON-serializable.  This TypeError escapes the try/except OSError
        handler and propagates to the caller.

        To make this green, wrap json.dumps inside the try/except block (or add a
        separate except TypeError handler) so that serialization failures are
        treated as logged + counted, not raised.
        """
        record = {
            "lane": "fast",
            "agent": "python-coder",
            "duration_ms": 1200,
            "tokens_in": 500,
            "tokens_out": 300,
            "cache_read_tokens": 100,
            # A Python set — not JSON-serializable; json.dumps will raise TypeError
            "tags": {1, 2, 3},
        }

        try:
            emit_agent_telemetry(record, sink_path=self.sink_path)
        except TypeError as exc:
            self.fail(
                f"DEFECT M-1: emit_agent_telemetry raised TypeError({exc}) when the "
                "record contained a set value. The fail-safe contract requires that "
                "TypeError (from json.dumps on a non-serializable value) is caught "
                "and counted, NOT propagated to the caller. "
                "Fix: move json.dumps inside the try/except block or add a separate "
                "except TypeError handler."
            )

    def test_m1_set_value_increments_failed_count(self) -> None:
        # covers: BO-2400d-1
        """A non-serializable record must increment the failed-write counter.

        DEFECT M-1: When TypeError escapes, the except OSError branch never runs,
        so _failed_write_count is NOT incremented.  After the fix, a serialization
        failure must increment the counter (same as an OSError).

        To make this green, the fix must increment _failed_write_count in the
        TypeError handler, so operators can detect dropped telemetry events.
        """
        initial = get_failed_write_count()

        record = {
            "lane": "fast",
            "agent": "test-writer",
            "duration_ms": 800,
            "tokens_in": 200,
            "tokens_out": 100,
            "cache_read_tokens": 50,
            # Path object — not JSON-serializable without a custom encoder
            "output_path": Path("/tmp/some/path"),
        }

        # Do NOT suppress the exception. In the current buggy state, TypeError
        # propagates out of emit_agent_telemetry and this test fails with TypeError
        # (valid red state). After the fix, the call returns normally and we check
        # the counter. Two distinct red→green paths, both valid:
        #   RED now : TypeError propagates → test body fails at this line
        #   GREEN after fix : no raise → counter incremented → assertion passes
        emit_agent_telemetry(record, sink_path=self.sink_path)

        after = get_failed_write_count()

        self.assertEqual(
            after,
            initial + 1,
            f"DEFECT M-1: Failed-write counter must be incremented by 1 when a "
            "non-JSON-serializable record value causes a serialization failure. "
            f"Counter before: {initial}, counter after: {after}. "
            "The fix must catch TypeError from json.dumps and increment "
            "_failed_write_count (same as OSError handling).",
        )

    def test_m1_path_value_does_not_raise(self) -> None:
        # covers: BO-2400d-1
        """emit_agent_telemetry must NOT raise when a record value is a pathlib.Path.

        Path objects are not JSON-serializable (json.dumps raises TypeError).
        The fail-safe contract requires this to be counted, not raised.
        """
        record = {
            "lane": "fast",
            "agent": "python-coder",
            "duration_ms": 2000,
            "tokens_in": 1000,
            "tokens_out": 400,
            "cache_read_tokens": 200,
            # pathlib.Path — not JSON-serializable
            "worktree_path": Path("/home/user/projects/leafcutter"),
        }

        try:
            emit_agent_telemetry(record, sink_path=self.sink_path)
        except TypeError as exc:
            self.fail(
                f"DEFECT M-1: emit_agent_telemetry raised TypeError({exc}) when the "
                "record contained a Path value. The fail-safe contract requires this "
                "to be caught and counted. Fix: wrap json.dumps inside try/except."
            )

    def test_m1_os_error_still_caught_after_fix(self) -> None:
        # covers: BO-2400d-1
        """The existing OSError handling must still work after the M-1 fix.

        A sink path that is a directory (not writable) must still increment
        the failed-write counter and NOT raise.  This regression test ensures
        the fix does not break the existing OSError behavior.
        """
        # Make the sink_path itself a directory so open() fails with IsADirectoryError.
        dir_sink = Path(self._tmp.name) / "actually_a_dir.jsonl"
        dir_sink.mkdir()

        record = {
            "lane": "fast",
            "agent": "test-writer",
            "duration_ms": 500,
            "tokens_in": 100,
            "tokens_out": 50,
            "cache_read_tokens": 0,
        }

        initial = get_failed_write_count()

        try:
            emit_agent_telemetry(record, sink_path=dir_sink)
        except OSError as exc:
            self.fail(
                f"OSError must be caught and counted, not raised: {exc}"
            )

        after = get_failed_write_count()
        self.assertEqual(
            after,
            initial + 1,
            "OSError on sink write must increment the failed-write counter by 1. "
            f"Counter before: {initial}, counter after: {after}.",
        )

    def test_m1_valid_record_still_writes_successfully(self) -> None:
        # covers: BO-2400d-1
        """A valid (JSON-serializable) record must still write to the sink file.

        Regression test: the M-1 fix must not break the happy path.
        A record with only primitive values must write a JSONL line to the sink.
        """
        record = {
            "lane": "fast",
            "agent": "python-coder",
            "duration_ms": 1500,
            "tokens_in": 600,
            "tokens_out": 250,
            "cache_read_tokens": 80,
            "unit_id": "BO-2400d-1",
        }

        emit_agent_telemetry(record, sink_path=self.sink_path)

        self.assertTrue(
            self.sink_path.exists(),
            "Sink file must be created when a valid record is emitted.",
        )
        content = self.sink_path.read_text(encoding="utf-8")
        self.assertIn(
            "python-coder",
            content,
            "The emitted record must contain the agent field in the sink file.",
        )
        self.assertIn(
            "BO-2400d-1",
            content,
            "The emitted record must contain the unit_id field in the sink file.",
        )


if __name__ == "__main__":
    unittest.main()
