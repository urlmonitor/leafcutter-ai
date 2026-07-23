"""
MODULE: unit_tests/feedback/test_bo2400d_telemetry.py
GOAL: RED test stubs for BO-2400d-1, BO-2400d-2, BO-2400d-3, BO-2400d-1-i.

=== Interface contract under test (to be implemented by python-coder) ===

Location: scripts/agent-health/agent_telemetry.py  (NEW MODULE)

    emit_agent_telemetry(
        record: dict,
        *,
        sink_path: Path,
    ) -> None

    Appends exactly one JSON line to sink_path.  The record dict MUST contain:
        "lane"              str  — "fast" or "heavy" (BO-2400d-2)
        "agent"             str  — agent identity string, e.g. "python-coder" (BO-2400d-2)
        "duration_ms"       int  — wall-clock duration in milliseconds (BO-2400d-1)
        "tokens_in"         int  — input token count for the invocation (BO-2400d-1)
        "tokens_out"        int  — output token count (BO-2400d-1)
        "cache_read_tokens" int  — cache-read token count (BO-2400d-1)
        "unit_id"           str? — optional unit-of-work identifier

    The emitter sets "ts" (ISO-8601 UTC) automatically if absent from record.

    On OSError (unreachable / unwritable sink):  (BO-2400d-1-i)
        - emits a WARNING via the module-level logger (never a bare stderr print,
          never a silent swallow, never a re-raise — build must continue)
        - increments the module-level _failed_write_count counter

    Supporting callables (also in agent_telemetry.py):
        get_failed_write_count() -> int    — returns current _failed_write_count
        reset_failed_write_count() -> None — resets counter to 0 (test support only)

Location: scripts/agent-health/generate_health_report.py  (EXTEND EXISTING)

    build_lane_comparison_report(sink_path: Path) -> dict   (BO-2400d-3)

    Reads JSONL records from sink_path, groups by "lane" field, and returns a
    dict whose keys are the lane strings present in the data.  Each value is a
    sub-dict with:
        "count"                    int   — number of invocations in this lane
        "total_duration_ms"        int   — sum of duration_ms across all records
        "avg_duration_ms"          float — mean duration per invocation (time per unit)
        "total_tokens_in"          int   — sum of tokens_in
        "total_tokens_out"         int   — sum of tokens_out
        "total_cache_read_tokens"  int   — sum of cache_read_tokens
        "avg_total_tokens"         float — mean of (tokens_in+tokens_out+cache_read_tokens)
                                           per invocation (proxy for cost per unit)

    A lane with no records is absent from the returned dict (not present as an
    empty sub-dict).  This allows callers to detect the single-lane case and
    report it gracefully per BO-2400d-3 constraint.

=== Fixture authenticity mandate (BO-2400d-1, BO-2500c dogfood) ===

    All JSONL fixtures are produced by calling the REAL emit_agent_telemetry()
    to a tempfile sink, then read back and asserted.  No hand-typed JSONL strings.
    For the unreachable-sink test (BO-2400d-1-i), a real existing DIRECTORY is
    passed as sink_path — this triggers a genuine OSError, not a mock.

=== Red baseline ===

    All tests are RED until python-coder implements:
        - scripts/agent-health/agent_telemetry.py  (new module)
        - build_lane_comparison_report() in scripts/agent-health/generate_health_report.py
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Repo path wiring — same pattern as sibling ac_store tests
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_AGENT_HEALTH_DIR = _REPO_ROOT / "scripts" / "agent-health"

sys.path.insert(0, str(_AGENT_HEALTH_DIR))

# These imports WILL fail with ImportError until python-coder creates
# scripts/agent-health/agent_telemetry.py.
# That ImportError IS the intended red state — it confirms the production code
# does not yet exist.
from agent_telemetry import (  # noqa: E402
    emit_agent_telemetry,
    get_failed_write_count,
    reset_failed_write_count,
)

# generate_health_report.py EXISTS already; importing the new function
# build_lane_comparison_report will fail with ImportError until python-coder
# adds it to that module.
from generate_health_report import build_lane_comparison_report  # noqa: E402


# ---------------------------------------------------------------------------
# Shared record fixtures
# ---------------------------------------------------------------------------

def _make_record(
    *,
    lane: str = "fast",
    agent: str = "python-coder",
    duration_ms: int = 1200,
    tokens_in: int = 500,
    tokens_out: int = 300,
    cache_read_tokens: int = 100,
    unit_id: str | None = None,
) -> dict:
    """Return a minimal valid telemetry record dict for emit_agent_telemetry().

    No JSONL is hand-typed here; this dict is always written to disk via
    emit_agent_telemetry() — the round-trip is the fixture-authenticity guarantee.

    Args:
        lane: "fast" or "heavy".
        agent: Agent identity string.
        duration_ms: Wall-clock duration in milliseconds.
        tokens_in: Input token count.
        tokens_out: Output token count.
        cache_read_tokens: Cache-read token count.
        unit_id: Optional unit-of-work identifier.

    Returns:
        dict: Record ready to pass to emit_agent_telemetry.
    """
    rec: dict = {
        "lane": lane,
        "agent": agent,
        "duration_ms": duration_ms,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cache_read_tokens": cache_read_tokens,
    }
    if unit_id is not None:
        rec["unit_id"] = unit_id
    return rec


# ---------------------------------------------------------------------------
# BO-2400d-1 — One record per invocation, record contains required fields
# ---------------------------------------------------------------------------


class TestOneRecordPerInvocation(unittest.TestCase):
    """BO-2400d-1: Exactly one telemetry record is appended per agent invocation."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.sink = Path(self._tmp.name) / "telemetry.jsonl"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ac1_one_record_appended(self) -> None:
        # covers: BO-2400d-1
        """Exactly one JSONL line is appended to the sink for a single invocation.

        To make this green, emit_agent_telemetry must:
        - Create the sink file if absent (or append to it if it exists)
        - Write exactly one newline-terminated JSON object per call
        - Not write zero lines (silence) or more than one line per call
        """
        record = _make_record()
        emit_agent_telemetry(record, sink_path=self.sink)

        lines = [ln for ln in self.sink.read_text(encoding="utf-8").splitlines() if ln.strip()]
        self.assertEqual(
            len(lines),
            1,
            "Exactly one JSONL line must be appended per emit_agent_telemetry() call.",
        )

    def test_ac1_two_invocations_produce_two_records(self) -> None:
        # covers: BO-2400d-1
        """A second invocation appends a second record — no deduplication or overwrite.

        To make this green, emit_agent_telemetry must append (not overwrite) to
        the sink so that N calls produce exactly N records.
        """
        emit_agent_telemetry(_make_record(duration_ms=100), sink_path=self.sink)
        emit_agent_telemetry(_make_record(duration_ms=200), sink_path=self.sink)

        lines = [ln for ln in self.sink.read_text(encoding="utf-8").splitlines() if ln.strip()]
        self.assertEqual(
            len(lines),
            2,
            "Two emit_agent_telemetry() calls must produce exactly two JSONL records.",
        )

    def test_ac1_record_contains_duration_ms(self) -> None:
        # covers: BO-2400d-1
        """The appended record must contain the duration_ms field.

        Fixture authenticity: the record is produced by calling emit_agent_telemetry,
        then read back from disk and parsed — no hand-typed JSONL.

        To make this green, emit_agent_telemetry must include duration_ms in the
        written record with the same value passed in.
        """
        emit_agent_telemetry(_make_record(duration_ms=1500), sink_path=self.sink)

        raw_line = self.sink.read_text(encoding="utf-8").strip()
        stored = json.loads(raw_line)

        self.assertIn(
            "duration_ms",
            stored,
            "The emitted record must contain the 'duration_ms' field.",
        )
        self.assertEqual(
            stored["duration_ms"],
            1500,
            "The 'duration_ms' value must match the value passed to emit_agent_telemetry.",
        )

    def test_ac1_record_contains_input_token_count(self) -> None:
        # covers: BO-2400d-1
        """The appended record must contain the tokens_in (input token count) field.

        To make this green, emit_agent_telemetry must include tokens_in in the
        written record.
        """
        emit_agent_telemetry(_make_record(tokens_in=750), sink_path=self.sink)

        stored = json.loads(self.sink.read_text(encoding="utf-8").strip())
        self.assertIn(
            "tokens_in",
            stored,
            "The emitted record must contain the 'tokens_in' field.",
        )
        self.assertEqual(
            stored["tokens_in"],
            750,
            "The 'tokens_in' value must match the value passed to emit_agent_telemetry.",
        )

    def test_ac1_record_contains_output_token_count(self) -> None:
        # covers: BO-2400d-1
        """The appended record must contain the tokens_out (output token count) field.

        To make this green, emit_agent_telemetry must include tokens_out in the
        written record.
        """
        emit_agent_telemetry(_make_record(tokens_out=420), sink_path=self.sink)

        stored = json.loads(self.sink.read_text(encoding="utf-8").strip())
        self.assertIn(
            "tokens_out",
            stored,
            "The emitted record must contain the 'tokens_out' field.",
        )
        self.assertEqual(
            stored["tokens_out"],
            420,
            "The 'tokens_out' value must match the value passed to emit_agent_telemetry.",
        )

    def test_ac1_record_contains_cache_read_tokens(self) -> None:
        # covers: BO-2400d-1
        """The appended record must contain the cache_read_tokens field.

        To make this green, emit_agent_telemetry must include cache_read_tokens
        in the written record.
        """
        emit_agent_telemetry(_make_record(cache_read_tokens=250), sink_path=self.sink)

        stored = json.loads(self.sink.read_text(encoding="utf-8").strip())
        self.assertIn(
            "cache_read_tokens",
            stored,
            "The emitted record must contain the 'cache_read_tokens' field.",
        )
        self.assertEqual(
            stored["cache_read_tokens"],
            250,
            "The 'cache_read_tokens' value must match the value passed to emit_agent_telemetry.",
        )

    def test_ac1_record_is_valid_json(self) -> None:
        # covers: BO-2400d-1
        """Each appended line must be valid JSON (parseable via json.loads).

        To make this green, emit_agent_telemetry must write exactly one JSON object
        per line with no trailing garbage and proper quote-encoding.
        """
        emit_agent_telemetry(_make_record(), sink_path=self.sink)

        raw = self.sink.read_text(encoding="utf-8").strip()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            self.fail(f"The emitted line is not valid JSON: {exc}\n  Line: {raw!r}")

        self.assertIsInstance(
            parsed,
            dict,
            "The emitted JSON must be an object (dict), not a list or scalar.",
        )


# ---------------------------------------------------------------------------
# BO-2400d-2 — Each record carries lane and agent identity
# ---------------------------------------------------------------------------


class TestRecordTaggedWithLaneAndAgent(unittest.TestCase):
    """BO-2400d-2: Each telemetry record is tagged with lane (fast|heavy) and agent id."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.sink = Path(self._tmp.name) / "telemetry.jsonl"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ac2_record_tagged_with_lane_fast(self) -> None:
        # covers: BO-2400d-2
        """A fast-lane invocation record must carry lane="fast".

        Fixture: record produced by emit_agent_telemetry, read back from disk.

        To make this green, emit_agent_telemetry must include the "lane" field
        in the written record with value "fast".
        """
        emit_agent_telemetry(_make_record(lane="fast"), sink_path=self.sink)

        stored = json.loads(self.sink.read_text(encoding="utf-8").strip())
        self.assertIn(
            "lane",
            stored,
            "The emitted record must contain the 'lane' field.",
        )
        self.assertEqual(
            stored["lane"],
            "fast",
            "A fast-lane invocation must have lane='fast' in its telemetry record.",
        )

    def test_ac2_record_tagged_with_lane_heavy(self) -> None:
        # covers: BO-2400d-2
        """A heavy-pipeline invocation record must carry lane="heavy".

        To make this green, emit_agent_telemetry must include the "lane" field
        in the written record with value "heavy".
        """
        emit_agent_telemetry(_make_record(lane="heavy"), sink_path=self.sink)

        stored = json.loads(self.sink.read_text(encoding="utf-8").strip())
        self.assertEqual(
            stored["lane"],
            "heavy",
            "A heavy-pipeline invocation must have lane='heavy' in its telemetry record.",
        )

    def test_ac2_record_tagged_with_agent_identity(self) -> None:
        # covers: BO-2400d-2
        """The emitted record must carry the producing agent's identity as "agent".

        Fixture: record produced by emit_agent_telemetry, read back from disk.

        To make this green, emit_agent_telemetry must include the "agent" field
        in the written record, matching the value passed in by the caller.
        """
        emit_agent_telemetry(_make_record(agent="test-writer"), sink_path=self.sink)

        stored = json.loads(self.sink.read_text(encoding="utf-8").strip())
        self.assertIn(
            "agent",
            stored,
            "The emitted record must contain the 'agent' field.",
        )
        self.assertEqual(
            stored["agent"],
            "test-writer",
            "The 'agent' field must match the value passed to emit_agent_telemetry.",
        )

    def test_ac2_lane_and_agent_on_same_record(self) -> None:
        # covers: BO-2400d-2
        """Both 'lane' and 'agent' must appear on the same record (no join required).

        The constraint from BO-2400d-2: "lane and agent fields must be present on
        the same record shape defined by BO-2400d-1, so grouping by lane and by
        agent is possible without a join."

        Fixture: single call to emit_agent_telemetry, read back and verified.
        """
        emit_agent_telemetry(
            _make_record(lane="heavy", agent="sql-coder"),
            sink_path=self.sink,
        )

        stored = json.loads(self.sink.read_text(encoding="utf-8").strip())
        self.assertIn("lane", stored, "The record must contain 'lane'.")
        self.assertIn("agent", stored, "The record must contain 'agent'.")
        self.assertIn("duration_ms", stored, "The record must contain 'duration_ms'.")
        self.assertIn("tokens_in", stored, "The record must contain 'tokens_in'.")
        self.assertIn("tokens_out", stored, "The record must contain 'tokens_out'.")
        self.assertIn("cache_read_tokens", stored, "The record must contain 'cache_read_tokens'.")

    def test_ac2_records_groupable_by_lane(self) -> None:
        # covers: BO-2400d-2
        """Multiple records from different lanes must be distinguishable by the lane field.

        Emits a fast and a heavy record to the same sink, reads back both, and
        verifies that grouping by "lane" produces two disjoint sets.

        Fixture: two real emit_agent_telemetry() calls, read back from disk.
        """
        emit_agent_telemetry(_make_record(lane="fast", agent="architect-review"), sink_path=self.sink)
        emit_agent_telemetry(_make_record(lane="heavy", agent="architect-review"), sink_path=self.sink)

        lines = [ln for ln in self.sink.read_text(encoding="utf-8").splitlines() if ln.strip()]
        records = [json.loads(ln) for ln in lines]

        fast_records = [r for r in records if r.get("lane") == "fast"]
        heavy_records = [r for r in records if r.get("lane") == "heavy"]

        self.assertEqual(len(fast_records), 1, "One fast-lane record must be present.")
        self.assertEqual(len(heavy_records), 1, "One heavy-pipeline record must be present.")

    def test_ac2_records_groupable_by_agent(self) -> None:
        # covers: BO-2400d-2
        """Multiple records from different agents must be distinguishable by the agent field.

        Emits records for two agents, reads back and groups by "agent".

        Fixture: two real emit_agent_telemetry() calls, read back from disk.
        """
        emit_agent_telemetry(_make_record(agent="python-coder"), sink_path=self.sink)
        emit_agent_telemetry(_make_record(agent="test-writer"), sink_path=self.sink)

        lines = [ln for ln in self.sink.read_text(encoding="utf-8").splitlines() if ln.strip()]
        records = [json.loads(ln) for ln in lines]

        agents_seen = {r.get("agent") for r in records}
        self.assertIn("python-coder", agents_seen)
        self.assertIn("test-writer", agents_seen)


# ---------------------------------------------------------------------------
# BO-2400d-1-i — Unreachable sink: WARNING + failed-write counter
# ---------------------------------------------------------------------------


class TestUnreachableSinkSurfacesFailure(unittest.TestCase):
    """BO-2400d-1-i: An unreachable sink is surfaced loudly; never swallowed silently."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        # Reset the module-level counter before each test so counts are isolated.
        reset_failed_write_count()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ac1i_unreachable_sink_emits_warning(self) -> None:
        # covers: BO-2400d-1-i
        """When the sink is a directory (genuinely unwritable), a WARNING is logged.

        The sink_path is set to an existing DIRECTORY — opening it for append
        raises IsADirectoryError (a subclass of OSError).  The emitter must:
        - Catch the OSError
        - Emit a WARNING via the module-level logger
        - NOT re-raise (build must continue after the failure)
        - NOT silently swallow (the anti-pattern from the 23-lost-events incident)

        This is a real OSError test — no mocking.
        """
        bad_sink = Path(self._tmp.name)  # An existing directory — cannot open for append

        record = _make_record()

        # assertLogs asserts that at least one WARNING (or higher) is emitted.
        # If emit_agent_telemetry swallows the error silently, assertLogs raises
        # AssertionError and the test fails — which is the intended red signal.
        with self.assertLogs(level="WARNING") as log_ctx:
            emit_agent_telemetry(record, sink_path=bad_sink)

        warning_messages = [msg for msg in log_ctx.output if "WARNING" in msg]
        self.assertTrue(
            len(warning_messages) >= 1,
            "At least one WARNING-level log message must be emitted when the sink "
            "is unwritable. The 23-event silent-drop incident is the anti-pattern to prevent.",
        )

    def test_ac1i_failed_write_count_incremented(self) -> None:
        # covers: BO-2400d-1-i
        """Each failed sink write must increment the module-level failed-write counter.

        The counter must be surfaced via get_failed_write_count() so operators
        can see that events were dropped at run end.

        This is a real OSError test — the sink is a directory, not a mock.
        """
        bad_sink = Path(self._tmp.name)  # directory → real OSError

        count_before = get_failed_write_count()

        with self.assertLogs(level="WARNING"):
            emit_agent_telemetry(_make_record(), sink_path=bad_sink)

        count_after = get_failed_write_count()
        self.assertEqual(
            count_after,
            count_before + 1,
            "A single failed sink write must increment the failed-write counter by 1.",
        )

    def test_ac1i_failed_write_count_accumulates_across_calls(self) -> None:
        # covers: BO-2400d-1-i
        """Multiple failed sink writes each increment the counter (accumulation test).

        Three failed emit calls must leave the counter at 3 (not 1 or 0).
        This proves the counter is persistent and not reset between calls.
        """
        bad_sink = Path(self._tmp.name)

        with self.assertLogs(level="WARNING"):
            emit_agent_telemetry(_make_record(), sink_path=bad_sink)
        with self.assertLogs(level="WARNING"):
            emit_agent_telemetry(_make_record(), sink_path=bad_sink)
        with self.assertLogs(level="WARNING"):
            emit_agent_telemetry(_make_record(), sink_path=bad_sink)

        self.assertEqual(
            get_failed_write_count(),
            3,
            "Three failed writes must leave the failed-write counter at 3.",
        )

    def test_ac1i_failed_write_does_not_raise(self) -> None:
        # covers: BO-2400d-1-i
        """An unreachable sink must not crash the caller (emit is best-effort).

        The constraint from BO-2400d-1-i: "Catch the specific I/O exceptions
        around the sink write (OSError family) and log-and-continue; telemetry
        emission must not crash the build, but its failure must be visible."

        This test verifies the no-raise contract by calling emit_agent_telemetry
        against a directory and asserting no exception propagates.
        """
        bad_sink = Path(self._tmp.name)
        try:
            with self.assertLogs(level="WARNING"):
                emit_agent_telemetry(_make_record(), sink_path=bad_sink)
        except OSError as exc:
            self.fail(
                f"emit_agent_telemetry raised OSError instead of logging and continuing: {exc}"
            )

    def test_ac1i_reset_failed_write_count_clears_counter(self) -> None:
        # covers: BO-2400d-1-i
        """reset_failed_write_count() resets the counter to 0 (test-support contract).

        This test verifies the reset helper so other tests can use it reliably
        in setUp() for isolation.
        """
        bad_sink = Path(self._tmp.name)

        with self.assertLogs(level="WARNING"):
            emit_agent_telemetry(_make_record(), sink_path=bad_sink)

        self.assertGreater(get_failed_write_count(), 0, "Counter must be > 0 before reset.")

        reset_failed_write_count()

        self.assertEqual(
            get_failed_write_count(),
            0,
            "After reset_failed_write_count() the counter must be 0.",
        )


# ---------------------------------------------------------------------------
# BO-2400d-3 — Lane comparison report: cost/time per unit, side by side
# ---------------------------------------------------------------------------


class TestLaneComparisonReport(unittest.TestCase):
    """BO-2400d-3: Report compares fast-lane vs heavy-pipeline cost and time per unit.

    All fixtures are produced by calling emit_agent_telemetry() against a temp
    sink, then read by build_lane_comparison_report() from that same sink.
    No hand-typed JSONL.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.sink = Path(self._tmp.name) / "telemetry.jsonl"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _populate_sink(self) -> None:
        """Write representative fast and heavy records using the real emitter.

        Two fast-lane records and one heavy-pipeline record so the report can
        be checked for correct per-lane aggregation.
        """
        # fast lane: 2 invocations
        emit_agent_telemetry(
            _make_record(lane="fast", duration_ms=800, tokens_in=400, tokens_out=200, cache_read_tokens=80, unit_id="ticket-A"),
            sink_path=self.sink,
        )
        emit_agent_telemetry(
            _make_record(lane="fast", duration_ms=1200, tokens_in=600, tokens_out=350, cache_read_tokens=120, unit_id="ticket-A"),
            sink_path=self.sink,
        )
        # heavy pipeline: 1 invocation
        emit_agent_telemetry(
            _make_record(lane="heavy", duration_ms=5000, tokens_in=2000, tokens_out=1500, cache_read_tokens=500, unit_id="ticket-B"),
            sink_path=self.sink,
        )

    def test_ac3_report_returns_both_lanes(self) -> None:
        # covers: BO-2400d-3
        """The report dict must contain both 'fast' and 'heavy' keys when both lanes
        have records.

        Fixture: populated via real emit_agent_telemetry() calls (no hand-typed JSONL).

        To make this green, build_lane_comparison_report must:
        - Read the JSONL from sink_path
        - Group records by the 'lane' field
        - Return a dict with one key per lane found in the data
        """
        self._populate_sink()
        report = build_lane_comparison_report(self.sink)

        self.assertIn(
            "fast",
            report,
            "The report must contain a 'fast' key when fast-lane records exist.",
        )
        self.assertIn(
            "heavy",
            report,
            "The report must contain a 'heavy' key when heavy-pipeline records exist.",
        )

    def test_ac3_report_emits_count_per_lane(self) -> None:
        # covers: BO-2400d-3
        """Each lane sub-dict must contain a 'count' of invocations in that lane.

        Fixture: 2 fast records + 1 heavy record.
        """
        self._populate_sink()
        report = build_lane_comparison_report(self.sink)

        self.assertEqual(
            report["fast"]["count"],
            2,
            "The fast-lane sub-dict must count 2 invocations.",
        )
        self.assertEqual(
            report["heavy"]["count"],
            1,
            "The heavy-pipeline sub-dict must count 1 invocation.",
        )

    def test_ac3_report_emits_time_per_unit_per_lane(self) -> None:
        # covers: BO-2400d-3
        """Each lane sub-dict must contain avg_duration_ms (time per unit of work).

        Fixture: fast lane has 800 ms + 1200 ms = 2000 ms total → 1000 ms avg.
                 Heavy lane has 5000 ms → 5000 ms avg.

        To make this green, build_lane_comparison_report must compute:
            avg_duration_ms = total_duration_ms / count
        for each lane.
        """
        self._populate_sink()
        report = build_lane_comparison_report(self.sink)

        self.assertIn(
            "avg_duration_ms",
            report["fast"],
            "The fast-lane sub-dict must contain 'avg_duration_ms' (time per unit).",
        )
        self.assertIn(
            "avg_duration_ms",
            report["heavy"],
            "The heavy-pipeline sub-dict must contain 'avg_duration_ms'.",
        )
        self.assertAlmostEqual(
            report["fast"]["avg_duration_ms"],
            1000.0,
            places=1,
            msg="Fast-lane avg_duration_ms must be (800+1200)/2 = 1000 ms.",
        )
        self.assertAlmostEqual(
            report["heavy"]["avg_duration_ms"],
            5000.0,
            places=1,
            msg="Heavy-pipeline avg_duration_ms must be 5000 ms.",
        )

    def test_ac3_report_emits_total_duration_per_lane(self) -> None:
        # covers: BO-2400d-3
        """Each lane sub-dict must contain total_duration_ms (sum across invocations).

        Fixture: fast=2000 ms total, heavy=5000 ms total.
        """
        self._populate_sink()
        report = build_lane_comparison_report(self.sink)

        self.assertEqual(
            report["fast"]["total_duration_ms"],
            2000,
            "Fast-lane total_duration_ms must be 800+1200=2000.",
        )
        self.assertEqual(
            report["heavy"]["total_duration_ms"],
            5000,
            "Heavy-pipeline total_duration_ms must be 5000.",
        )

    def test_ac3_report_emits_cost_proxy_per_unit_per_lane(self) -> None:
        # covers: BO-2400d-3
        """Each lane sub-dict must contain avg_total_tokens (cost proxy per unit).

        avg_total_tokens = mean of (tokens_in + tokens_out + cache_read_tokens)
        per invocation in the lane.  This is the per-unit cost proxy.

        Fixture fast record 1: 400+200+80  = 680 total tokens
        Fixture fast record 2: 600+350+120 = 1070 total tokens
        avg for fast = (680+1070)/2 = 875.0

        Heavy: 2000+1500+500 = 4000 total tokens → avg = 4000.0
        """
        self._populate_sink()
        report = build_lane_comparison_report(self.sink)

        self.assertIn(
            "avg_total_tokens",
            report["fast"],
            "The fast-lane sub-dict must contain 'avg_total_tokens' (cost per unit proxy).",
        )
        self.assertIn(
            "avg_total_tokens",
            report["heavy"],
            "The heavy-pipeline sub-dict must contain 'avg_total_tokens'.",
        )
        self.assertAlmostEqual(
            report["fast"]["avg_total_tokens"],
            875.0,
            places=1,
            msg="Fast-lane avg_total_tokens must be (680+1070)/2=875.0.",
        )
        self.assertAlmostEqual(
            report["heavy"]["avg_total_tokens"],
            4000.0,
            places=1,
            msg="Heavy-pipeline avg_total_tokens must be 4000.0.",
        )

    def test_ac3_report_presents_lanes_side_by_side(self) -> None:
        # covers: BO-2400d-3
        """Both lanes are present at the top level of the returned dict, side by side.

        "Side by side" means the caller can access both lane metrics from a single
        dict (no further grouping or file reads required).

        Fixture: populated via real emit_agent_telemetry() calls.
        """
        self._populate_sink()
        report = build_lane_comparison_report(self.sink)

        # Both lanes accessible from the single returned dict
        fast_avg_dur = report["fast"]["avg_duration_ms"]
        heavy_avg_dur = report["heavy"]["avg_duration_ms"]

        # The comparison itself (side-by-side): fast must be faster than heavy in this fixture
        self.assertLess(
            fast_avg_dur,
            heavy_avg_dur,
            "In this fixture the fast lane (1000 ms avg) must be faster than "
            f"the heavy pipeline (5000 ms avg); got fast={fast_avg_dur}, heavy={heavy_avg_dur}.",
        )

    def test_ac3_single_lane_degrades_gracefully(self) -> None:
        # covers: BO-2400d-3
        """When only one lane has records, the report returns only that lane (no crash).

        The constraint from BO-2400d-3: "a run with records for only one lane must
        degrade gracefully (report the available lane, note the missing one) rather
        than crash."

        Fixture: only fast-lane records in the sink.
        """
        emit_agent_telemetry(
            _make_record(lane="fast", duration_ms=900),
            sink_path=self.sink,
        )

        report = build_lane_comparison_report(self.sink)

        self.assertIn(
            "fast",
            report,
            "The fast lane must be present when only fast records exist.",
        )
        self.assertNotIn(
            "heavy",
            report,
            "The 'heavy' key must be absent when no heavy records exist "
            "(absent key signals a missing lane, not an empty dict).",
        )

    def test_ac3_empty_sink_returns_empty_dict(self) -> None:
        # covers: BO-2400d-3
        """An empty or absent sink file must return an empty dict (no crash).

        To make this green, build_lane_comparison_report must handle a missing
        or zero-byte JSONL file gracefully.
        """
        # sink does not exist — never written to
        report = build_lane_comparison_report(self.sink)

        self.assertIsInstance(
            report,
            dict,
            "build_lane_comparison_report must return a dict even when the sink is absent.",
        )
        self.assertEqual(
            len(report),
            0,
            "An absent sink must produce an empty dict (no lane keys).",
        )


if __name__ == "__main__":
    unittest.main()
