"""
MODULE: test_inf_700c_2_i_disposition_audit
GOAL: Failing test stubs for INF-700c-2-i -- "The disposition of an honoured
    record is auditable afterwards, and the record itself survives."
BUSINESS CONTEXT: INF-700c-2's resting state must be reached WITHOUT moving,
    marking, or deleting any of the 28 retained records. This AC verifies the
    non-mutation half of that promise behaviourally: byte-identical sink,
    every original field recoverable, no destination created or modified,
    and reversibility that requires no un-marking step.
ARCHITECTURE: Real-artifact behavioral tests against
    scripts/knowledge/harvest_learnings.py using the same
    tests/fixtures/harvest_learnings/unroutable_corpus_28.json fixture.

These tests are intentionally RED at authoring time: they depend on the
`HarvestResult.outstanding` field INF-700c-2 introduces, which does not
exist yet.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
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
    "harvest_learnings_inf700c2i_audit", _HARVEST_PATH
)
assert _spec is not None and _spec.loader is not None, f"could not load spec for {_HARVEST_PATH}"
_mod: Any = importlib.util.module_from_spec(_spec)
sys.modules["harvest_learnings_inf700c2i_audit"] = _mod
_spec.loader.exec_module(_mod)

harvest = _mod.harvest


def _write_sink(path: Path, events: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for ev in events:
            fh.write(json.dumps(ev) + "\n")


def _forbid_write(_text: str, dest: str) -> None:
    raise AssertionError(f"must not write to {dest} while resolving the honoured corpus")


class TestSinkByteIdenticalAfterRestingState(unittest.TestCase):
    """INF-700c-2-i test_spec #1."""

    def test_sink_is_byte_identical_after_the_resting_state_is_reached(self) -> None:
        # covers: INF-700c-2-i
        # angle: real_artifact
        events = load_fixture("harvest_learnings/unroutable_corpus_28")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            state = tmp / "harvest_state.json"
            _write_sink(sink, events)

            before_hash = hashlib.sha256(sink.read_bytes()).hexdigest()
            result = harvest(sink_path=sink, state_path=state, capture_fn=_forbid_write)
            after_hash = hashlib.sha256(sink.read_bytes()).hexdigest()

            self.assertEqual(result.outstanding, 0)
            self.assertEqual(
                after_hash,
                before_hash,
                "the sink must be byte-identical before and after resolving the resting state",
            )


class TestEveryOriginalFieldRecoverable(unittest.TestCase):
    """INF-700c-2-i test_spec #2."""

    def test_every_original_field_is_recoverable_from_the_sink_after_the_run(self) -> None:
        # covers: INF-700c-2-i
        # angle: criterion
        events = load_fixture("harvest_learnings/unroutable_corpus_28")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            state = tmp / "harvest_state.json"
            _write_sink(sink, events)

            result = harvest(sink_path=sink, state_path=state, capture_fn=_forbid_write)
            self.assertEqual(result.outstanding, 0)

            lines = sink.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 28)
            recovered = [json.loads(line) for line in lines]
            for original, after in zip(events, recovered, strict=True):
                for field in ("timestamp", "agent", "component", "destination", "entry_kind"):
                    self.assertEqual(
                        after[field],
                        original[field],
                        f"{field} must be unchanged for a retained record",
                    )


class TestNoDestinationCreatedOrModified(unittest.TestCase):
    """INF-700c-2-i test_spec #3."""

    _MISSING_DESTINATION = "memory/feedback_itpo_bo1700_worktree_gate_parity.md"

    def test_no_destination_file_was_created_or_modified_by_the_resolution(self) -> None:
        # covers: INF-700c-2-i
        # angle: criterion
        events = load_fixture("harvest_learnings/unroutable_corpus_28")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            state = tmp / "harvest_state.json"

            before_hashes: dict[str, str] = {}
            rewritten = []
            for ev in events:
                rel_dest = ev["destination"]
                staged = tmp / rel_dest
                if rel_dest != self._MISSING_DESTINATION:
                    staged.parent.mkdir(parents=True, exist_ok=True)
                    staged.write_text("real curated content\n", encoding="utf-8")
                    before_hashes[rel_dest] = hashlib.sha256(staged.read_bytes()).hexdigest()
                rewritten.append({**ev, "destination": str(staged)})
            _write_sink(sink, rewritten)

            result = harvest(sink_path=sink, state_path=state, capture_fn=_forbid_write)

            self.assertEqual(result.outstanding, 0)
            for rel_dest, before_hash in before_hashes.items():
                after_hash = hashlib.sha256((tmp / rel_dest).read_bytes()).hexdigest()
                self.assertEqual(after_hash, before_hash, f"{rel_dest} must be untouched")
            self.assertFalse((tmp / self._MISSING_DESTINATION).exists())


class TestBackfillReincludesWithNoUnmarkingStep(unittest.TestCase):
    """INF-700c-2-i test_spec #4 -- the discriminator between the chosen
    rule-based mechanism and state-seeding / archival mechanisms."""

    def test_changing_the_rule_re_includes_the_records_with_no_un_marking_step(self) -> None:
        # covers: INF-700c-2-i
        # angle: seam
        events = load_fixture("harvest_learnings/unroutable_corpus_28")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            state = tmp / "harvest_state.json"
            _write_sink(sink, events)

            first = harvest(sink_path=sink, state_path=state, capture_fn=_forbid_write)
            self.assertEqual(first.outstanding, 0, "resting state before backfill")

            backfilled = [dict(ev) for ev in events]
            backfilled[0]["text"] = "A real learning supplied after the fact, via backfill."
            backfilled[0]["entry_kind"] = "adr"
            backfilled[0]["destination"] = str(tmp / "memory" / "backfilled.md")
            _write_sink(sink, backfilled)

            # dry_run=True: observe the count without performing the write --
            # no un-marking step, no state reset, same state file as `first`.
            second = harvest(
                sink_path=sink,
                state_path=state,
                capture_fn=lambda t, d: None,
                dry_run=True,
            )

            self.assertEqual(
                second.outstanding,
                1,
                "supplying text must re-include the record on the very next run with no "
                "un-marking step -- no state was reset between the two calls",
            )


if __name__ == "__main__":
    unittest.main()
