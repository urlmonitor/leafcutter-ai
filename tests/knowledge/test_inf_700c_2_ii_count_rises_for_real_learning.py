"""
MODULE: test_inf_700c_2_ii_count_rises_for_real_learning
GOAL: Failing test stubs for INF-700c-2-ii -- "The waiting count stays
    truthful in the other direction -- a real unwritten learning still
    raises it."
BUSINESS CONTEXT: This is the anti-cheat clause for INF-700c-2. The cheapest
    way to make the 28-record backlog disappear is to stop counting
    (e.g. deriving "outstanding" from the routing table's own
    skipped_unknown / unroutable_by_kind buckets). This AC pins the count's
    definition to text-presence + watermark alone, independent of whether
    the routing table recognises the entry_kind, and independent of whether
    the destination write has merely been attempted vs. actually succeeded.
ARCHITECTURE: Unit and real-artifact behavioral tests against
    scripts/knowledge/harvest_learnings.py.

These tests are intentionally RED at authoring time: they depend on the
`HarvestResult.outstanding` field INF-700c-2 introduces, which does not
exist yet.
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

_spec = importlib.util.spec_from_file_location(
    "harvest_learnings_inf700c2ii_rises", _HARVEST_PATH
)
assert _spec is not None and _spec.loader is not None, f"could not load spec for {_HARVEST_PATH}"
_mod: Any = importlib.util.module_from_spec(_spec)
sys.modules["harvest_learnings_inf700c2ii_rises"] = _mod
_spec.loader.exec_module(_mod)

harvest = _mod.harvest


def _write_sink(path: Path, events: list[dict]) -> None:
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
    return {
        "event": "knowledge_captured",
        "timestamp": timestamp,
        "agent": agent,
        "component": component,
        "destination": destination,
        "entry_kind": entry_kind,
    }


class TestSingleTextBearingRecordCounted(unittest.TestCase):
    """INF-700c-2-ii test_spec #1."""

    def test_record_with_text_is_counted_as_outstanding(self) -> None:
        # covers: INF-700c-2-ii
        # angle: criterion
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            state = tmp / "harvest_state.json"
            event = _make_bare_event(entry_kind="adr", destination=str(tmp / "memory" / "x.md"))
            event["text"] = "A real learning about sequencing."
            _write_sink(sink, [event])

            result = harvest(
                sink_path=sink, state_path=state, capture_fn=lambda t, d: None, dry_run=True
            )

            self.assertEqual(result.outstanding, 1)


class TestOneAmongThe28(unittest.TestCase):
    """INF-700c-2-ii test_spec #2."""

    def test_one_text_bearing_record_among_the_28_reports_exactly_one_outstanding(self) -> None:
        # covers: INF-700c-2-ii
        # angle: real_artifact
        events = load_fixture("harvest_learnings/unroutable_corpus_28")
        self.assertEqual(len(events), 28, "fixture drift -- expected 28 events")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            state = tmp / "harvest_state.json"

            rewritten = [{**ev, "destination": str(tmp / ev["destination"])} for ev in events]
            extra = _make_bare_event(
                entry_kind="adr",
                destination=str(tmp / "memory" / "extra.md"),
                timestamp="2026-08-30T00:00:00Z",
            )
            extra["text"] = "A genuinely new, real learning not yet written anywhere."
            rewritten.append(extra)
            _write_sink(sink, rewritten)

            result = harvest(
                sink_path=sink, state_path=state, capture_fn=lambda t, d: None, dry_run=True
            )

            self.assertEqual(
                result.outstanding,
                1,
                "the 28 honoured records must contribute zero and the one real record must "
                "contribute exactly one -- not 29 and not zero",
            )


class TestCountRisesOnNextRun(unittest.TestCase):
    """INF-700c-2-ii test_spec #3."""

    def test_count_rises_from_zero_to_one_on_the_run_immediately_after_emission(self) -> None:
        # covers: INF-700c-2-ii
        # angle: criterion
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            state = tmp / "harvest_state.json"
            sink.write_text("", encoding="utf-8")

            baseline = harvest(
                sink_path=sink, state_path=state, capture_fn=lambda t, d: None, dry_run=True
            )
            self.assertEqual(baseline.outstanding, 0)

            new_event = _make_bare_event(
                entry_kind="adr", destination=str(tmp / "memory" / "new.md")
            )
            new_event["text"] = "A freshly emitted learning."
            _write_sink(sink, [new_event])

            after = harvest(
                sink_path=sink, state_path=state, capture_fn=lambda t, d: None, dry_run=True
            )
            self.assertEqual(
                after.outstanding,
                1,
                "the rise must happen on the very next run with no cache and no manual refresh",
            )


class TestCountReturnsToZeroAfterWrite(unittest.TestCase):
    """INF-700c-2-ii test_spec #4."""

    def test_count_returns_to_zero_once_the_record_is_written(self) -> None:
        # covers: INF-700c-2-ii
        # angle: criterion
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            state = tmp / "harvest_state.json"
            dest = tmp / "memory" / "written.md"
            event = _make_bare_event(entry_kind="adr", destination=str(dest))
            event["text"] = "A learning that will actually be written this run."
            _write_sink(sink, [event])

            written: list[tuple[str, str]] = []

            def fake_capture(text: str, d: str) -> None:
                written.append((text, d))

            first = harvest(sink_path=sink, state_path=state, capture_fn=fake_capture)
            self.assertEqual(first.routed, 1)
            self.assertEqual(written, [(event["text"], str(dest))])

            second = harvest(
                sink_path=sink, state_path=state, capture_fn=fake_capture, dry_run=True
            )
            self.assertEqual(
                second.outstanding,
                0,
                "once written and watermarked, the record must not be outstanding on the next run",
            )


class TestWriteFailureRemainsOutstanding(unittest.TestCase):
    """INF-700c-2-ii test_spec #5 -- the count must follow the write, not
    the attempt."""

    def test_record_whose_write_failed_remains_outstanding(self) -> None:
        # covers: INF-700c-2-ii
        # angle: failure
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            state = tmp / "harvest_state.json"
            # A regular FILE where a directory is expected makes the write
            # raise OSError inside _default_capture's mkdir(parents=True).
            blocking_file = tmp / "blocked"
            blocking_file.write_text("not a directory", encoding="utf-8")
            unwritable_dest = blocking_file / "learning.md"
            event = _make_bare_event(entry_kind="adr", destination=str(unwritable_dest))
            event["text"] = "A learning whose destination cannot be written."
            _write_sink(sink, [event])

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
                proc.returncode, 4, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
            )

            result = harvest(
                sink_path=sink, state_path=state, capture_fn=lambda t, d: None, dry_run=True
            )
            self.assertEqual(
                result.outstanding,
                1,
                "a record whose destination write failed must remain outstanding on the "
                "next run -- the count follows the write, not the attempt",
            )


class TestMissingDigestFieldWithTextStillCounts(unittest.TestCase):
    """INF-700c-2-ii test_spec #7 -- the regression this AC's fix closes.

    A record can carry real, non-empty `text` and simultaneously be missing
    one of `_REQUIRED_DIGEST_FIELDS`. Before the fix, the `except KeyError`
    branch around `_event_hash` incremented `missing_required_field_count`
    and `continue`d BEFORE the outstanding-counting logic ran, so a genuine
    unwritten learning silently read `outstanding: 0` -- the one figure this
    AC exists to make truthful. This is the exact defect the fast-lane review
    caught and INF-700c-2's fix addresses.
    """

    def test_record_with_text_missing_a_digest_field_is_counted_as_outstanding(
        self,
    ) -> None:
        # covers: INF-700c-2-ii
        # angle: failure
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            state = tmp / "harvest_state.json"
            broken = _make_bare_event(
                entry_kind="adr", destination=str(tmp / "memory" / "broken.md")
            )
            broken["text"] = "A real learning whose record is missing `agent`."
            del broken["agent"]
            _write_sink(sink, [broken])

            result = harvest(
                sink_path=sink, state_path=state, capture_fn=lambda t, d: None, dry_run=True
            )

            self.assertEqual(
                result.missing_required_field_count,
                1,
                "the record must still be reported as missing a required digest field",
            )
            self.assertEqual(
                result.outstanding,
                1,
                "a text-bearing record must count as outstanding even when it is "
                "also missing a required digest field -- a missing field is not "
                "a licence to exclude a genuine unwritten learning from the count",
            )


class TestMissingDigestFieldWithoutTextDoesNotCount(unittest.TestCase):
    """INF-700c-2-ii test_spec #8 -- the negative control for #7.

    Without this pairing, a fix that increments `outstanding`
    unconditionally inside the `except KeyError` branch (rather than only
    for records that actually carry learning text) would still pass #7 while
    over-counting every textless malformed record -- exactly the kind of
    fix that trades one wrong number for another.
    """

    def test_record_without_text_missing_a_digest_field_does_not_count(self) -> None:
        # covers: INF-700c-2-ii
        # angle: boundary
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            state = tmp / "harvest_state.json"
            broken = _make_bare_event(
                entry_kind="adr", destination=str(tmp / "memory" / "broken.md")
            )
            del broken["agent"]
            # No `text` key at all: `_is_no_learning_text` must treat this as
            # ineligible, exactly like a textless-but-complete record.
            _write_sink(sink, [broken])

            result = harvest(
                sink_path=sink, state_path=state, capture_fn=lambda t, d: None, dry_run=True
            )

            self.assertEqual(result.missing_required_field_count, 1)
            self.assertEqual(
                result.outstanding,
                0,
                "a record with no real learning text must never contribute to "
                "outstanding, missing digest field or not -- it is ineligible, "
                "not outstanding",
            )


class TestUnknownKindStillCounts(unittest.TestCase):
    """INF-700c-2-ii test_spec #6 -- the anti-cheat boundary case."""

    def test_text_bearing_record_with_an_unknown_entry_kind_still_counts(self) -> None:
        # covers: INF-700c-2-ii
        # angle: boundary
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            state = tmp / "harvest_state.json"
            event = _make_bare_event(
                entry_kind="an-entry-kind-the-routing-table-does-not-know",
                destination=str(tmp / "memory" / "unrouted.md"),
            )
            event["text"] = "A real learning the routing table cannot yet place."
            _write_sink(sink, [event])

            result = harvest(
                sink_path=sink, state_path=state, capture_fn=lambda t, d: None, dry_run=True
            )

            self.assertEqual(
                result.outstanding,
                1,
                "an unroutable-but-text-bearing record must still count as outstanding -- "
                "the resting state was reached by correcting the definition, not narrowing it",
            )


if __name__ == "__main__":
    unittest.main()
