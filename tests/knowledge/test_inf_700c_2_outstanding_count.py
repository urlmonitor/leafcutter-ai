"""
MODULE: test_inf_700c_2_outstanding_count
GOAL: Failing test stubs for INF-700c-2 -- "Knowledge history that has
    already been honoured stops being reported as work outstanding."
BUSINESS CONTEXT: The 28 retained ``knowledge_captured`` events in
    debugging/logs/agent_telemetry.jsonl carry no learning text and their
    named destinations already hold the learnings their agents wrote at the
    time. INF-700c-1 made those records ineligible-to-write; this AC requires
    that ineligibility to also mean they never appear in a "still waiting to
    be written" count -- on this run, on every subsequent run, with no state
    file needed and no corpus identifier hard-coded anywhere.
ARCHITECTURE: Pure unit / real-artifact tests against
    scripts/knowledge/harvest_learnings.py, following the same
    importlib.util.spec_from_file_location bootstrap and
    tests/fixtures/harvest_learnings/unroutable_corpus_28.json fixture
    already established by tests/knowledge/test_harvest_learnings.py.

These tests are intentionally RED at authoring time: `HarvestResult` has no
`outstanding` field yet and `summary()` never prints the word "outstanding".
Both must be added by the implementing coder. See test_rationale in
docs/acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700c-2.yaml
for why each descriptor exists.
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

_spec = importlib.util.spec_from_file_location(
    "harvest_learnings_inf700c2_outstanding", _HARVEST_PATH
)
assert _spec is not None and _spec.loader is not None, f"could not load spec for {_HARVEST_PATH}"
_mod: Any = importlib.util.module_from_spec(_spec)
sys.modules["harvest_learnings_inf700c2_outstanding"] = _mod
_spec.loader.exec_module(_mod)

harvest = _mod.harvest


# ---------------------------------------------------------------------------
# Helpers (self-contained per test-file convention already used by
# tests/knowledge/test_harvest_learnings.py)
# ---------------------------------------------------------------------------


def _write_sink(path: Path, events: list[dict]) -> None:
    """Write a JSONL sink file from a list of event dicts (real serializer)."""
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
    """Return a knowledge_captured event shaped like the REAL corpus (no
    ``ticket`` key, no ``text`` key) -- matches
    tests/fixtures/harvest_learnings/unroutable_corpus_28.json exactly."""
    return {
        "event": "knowledge_captured",
        "timestamp": timestamp,
        "agent": agent,
        "component": component,
        "destination": destination,
        "entry_kind": entry_kind,
    }


def _forbid_write(_text: str, dest: str) -> None:
    raise AssertionError(f"must not write to {dest} while resolving the honoured corpus")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFullCorpusContributesZero(unittest.TestCase):
    """INF-700c-2 test_spec #1."""

    def test_full_corpus_of_28_contributes_zero_to_the_outstanding_count(self) -> None:
        # covers: INF-700c-2
        # angle: real_artifact
        events = load_fixture("harvest_learnings/unroutable_corpus_28")
        self.assertEqual(len(events), 28, "fixture drift -- expected 28 events")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            state = tmp / "harvest_state.json"
            _write_sink(sink, events)

            result = harvest(sink_path=sink, state_path=state, capture_fn=_forbid_write)

            self.assertEqual(
                result.outstanding,
                0,
                "the 28 honoured records must contribute zero to the outstanding count",
            )
            self.assertEqual(result.no_learning_text, 28)


class TestExitCodeMatchesEmptyInput(unittest.TestCase):
    """INF-700c-2 test_spec #2."""

    def test_run_over_the_corpus_exits_with_the_same_code_as_an_empty_input(self) -> None:
        # covers: INF-700c-2
        # angle: criterion
        events = load_fixture("harvest_learnings/unroutable_corpus_28")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            corpus_sink = tmp / "corpus_sink.jsonl"
            empty_sink = tmp / "empty_sink.jsonl"
            _write_sink(corpus_sink, events)
            empty_sink.write_text("", encoding="utf-8")

            corpus_proc = subprocess.run(
                [
                    sys.executable,
                    str(_HARVEST_PATH),
                    "--sink",
                    str(corpus_sink),
                    "--state",
                    str(tmp / "corpus_state.json"),
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            empty_proc = subprocess.run(
                [
                    sys.executable,
                    str(_HARVEST_PATH),
                    "--sink",
                    str(empty_sink),
                    "--state",
                    str(tmp / "empty_state.json"),
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            self.assertEqual(
                corpus_proc.returncode,
                empty_proc.returncode,
                f"corpus stdout={corpus_proc.stdout!r} empty stdout={empty_proc.stdout!r}",
            )
            self.assertEqual(corpus_proc.returncode, 0)
            # The ineligible count must still be PRINTED (it_requirements #5)
            # -- visible is not the same as outstanding. Neither run's
            # summary currently mentions "outstanding" at all.
            self.assertIn(
                "0 outstanding",
                corpus_proc.stdout,
                f"summary must explicitly state the outstanding count; stdout={corpus_proc.stdout!r}",
            )
            self.assertIn(
                "0 outstanding",
                empty_proc.stdout,
                f"summary must explicitly state the outstanding count; stdout={empty_proc.stdout!r}",
            )


class TestSecondRunNoInterveningStep(unittest.TestCase):
    """INF-700c-2 test_spec #3."""

    def test_corpus_contributes_zero_on_a_second_run_with_no_intervening_step(self) -> None:
        # covers: INF-700c-2
        # angle: criterion
        events = load_fixture("harvest_learnings/unroutable_corpus_28")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            state = tmp / "harvest_state.json"
            _write_sink(sink, events)

            first = harvest(sink_path=sink, state_path=state, capture_fn=_forbid_write)
            second = harvest(sink_path=sink, state_path=state, capture_fn=_forbid_write)

            self.assertEqual(first.outstanding, 0)
            self.assertEqual(second.outstanding, 0)


class TestNoStateFilePresent(unittest.TestCase):
    """INF-700c-2 test_spec #4 -- the fresh-clone / consumer-install case,
    since debugging/logs/ is gitignored."""

    def test_resting_state_holds_with_no_state_file_present(self) -> None:
        # covers: INF-700c-2
        # angle: deployed
        events = load_fixture("harvest_learnings/unroutable_corpus_28")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            state = tmp / "never_created_dir" / "harvest_state.json"
            _write_sink(sink, events)
            self.assertFalse(state.exists(), "state file must be absent, as in a fresh clone")

            result = harvest(sink_path=sink, state_path=state, capture_fn=_forbid_write)

            self.assertEqual(result.outstanding, 0)


class TestResolutionModifiesNothing(unittest.TestCase):
    """INF-700c-2 test_spec #5."""

    _MISSING_DESTINATION = "memory/feedback_itpo_bo1700_worktree_gate_parity.md"

    def test_resolving_the_corpus_modifies_no_destination_and_no_sink(self) -> None:
        # covers: INF-700c-2
        # angle: real_artifact
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
                    staged.write_text("pre-existing curated content\n", encoding="utf-8")
                    before_hashes[rel_dest] = hashlib.sha256(staged.read_bytes()).hexdigest()
                rewritten.append({**ev, "destination": str(staged)})
            _write_sink(sink, rewritten)
            sink_before = sink.read_bytes()

            result = harvest(sink_path=sink, state_path=state, capture_fn=_forbid_write)

            self.assertEqual(result.outstanding, 0)
            self.assertEqual(
                sink.read_bytes(), sink_before, "the sink must be byte-identical after the run"
            )
            for rel_dest, before_hash in before_hashes.items():
                after_hash = hashlib.sha256((tmp / rel_dest).read_bytes()).hexdigest()
                self.assertEqual(after_hash, before_hash, f"{rel_dest} must be untouched")
            self.assertFalse((tmp / self._MISSING_DESTINATION).exists())


class TestUnseenTextlessRecordTreatedTheSame(unittest.TestCase):
    """INF-700c-2 test_spec #6 -- proves the exemption is by data property
    (absence of ``text``), not by an enumerated corpus."""

    def test_no_corpus_identifier_appears_in_the_implementation(self) -> None:
        # covers: INF-700c-2
        # angle: seam
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sink = tmp / "knowledge_emissions.jsonl"
            state = tmp / "harvest_state.json"
            novel_event = _make_bare_event(
                entry_kind="never-seen-entry-kind",
                destination=str(tmp / "memory" / "never_seen_destination.md"),
                agent="never-seen-agent",
                component="never-seen-component",
                timestamp="2099-01-01T00:00:00Z",
            )
            _write_sink(sink, [novel_event])

            result = harvest(sink_path=sink, state_path=state, capture_fn=_forbid_write)

            self.assertEqual(
                result.outstanding,
                0,
                "a textless record must be exempt by data property, not by membership in an "
                "enumerated corpus -- an unseen textless record must be exempt exactly like the 28",
            )
            self.assertEqual(result.no_learning_text, 1)


if __name__ == "__main__":
    unittest.main()
