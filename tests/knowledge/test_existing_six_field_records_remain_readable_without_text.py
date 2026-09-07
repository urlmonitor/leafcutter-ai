"""
MODULE: tests/knowledge/test_existing_six_field_records_remain_readable_without_text.py
GOAL: INF-700b-1 descriptor 4 (test_spec) — the backward-compatibility half of
      the SCHEMA CHANGE (it_requirements #1): `text` is REQUIRED OF THE
      PRODUCER but OPTIONAL TO THE CONSUMER. The 28 real six-field records
      already on disk (debugging/logs/agent_telemetry.jsonl, captured here
      verbatim as tests/fixtures/harvest_learnings/unroutable_corpus_28.json)
      must stay structurally valid on read once `text` is added to the
      documented shape — a missing `text` is a CLASSIFICATION (ineligible to
      write, per INF-700c-1), never a parse error or a validation failure.

FIXTURE AUTHENTICITY: this test loads the real 28-record corpus verbatim via
      conftest.load_fixture and does not hand-author a six-field stub — the
      whole point is that records written by real agents in June still
      parse (test_rationale on the AC).

WHY THIS TEST HAS TWO HALVES, NOT ONE:
  1. A precondition on the NORMATIVE SOURCE (signoff SKILL.md section 7):
     `text` must actually be declared there before "the reader tolerates its
     absence" is a meaningful claim to test at all. Without this half, the
     second half below would already be green today purely because nothing
     has changed yet -- scripts/knowledge/harvest_learnings.py already
     classifies a textless record as `no_learning_text` rather than
     rejecting it (INF-700c-1, done pre-existing work). Pinning only the
     reader's tolerance would make this descriptor pass before INF-700b-1
     is implemented, which is the exact "under-specified, passes
     immediately" trap the test-writer discipline exists to catch.
  2. The REAL reader (scripts/knowledge/harvest_learnings.harvest, invoked
     against a real temp-file sink -- never mocked) must not reject any of
     the 28 records as malformed or as missing a required digest field.

Together the two halves pin "the schema gains `text` as a required-of-
producer field, and reading old text-less records is still not rejection" --
the precise asymmetry the AC's SCHEMA CHANGE requirement describes.
"""

from __future__ import annotations

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
_EMISSION_SHAPE_HELPER = _REPO_ROOT / "unit_tests" / "agents" / "_emission_shape.py"

_harvest_spec = importlib.util.spec_from_file_location("harvest_learnings", _HARVEST_PATH)
assert _harvest_spec is not None and _harvest_spec.loader is not None
_harvest_mod: Any = importlib.util.module_from_spec(_harvest_spec)
sys.modules["harvest_learnings"] = _harvest_mod
_harvest_spec.loader.exec_module(_harvest_mod)
harvest = _harvest_mod.harvest

_shape_spec = importlib.util.spec_from_file_location("_emission_shape", _EMISSION_SHAPE_HELPER)
assert _shape_spec is not None and _shape_spec.loader is not None
_emission_shape: Any = importlib.util.module_from_spec(_shape_spec)
sys.modules["_emission_shape"] = _emission_shape
_shape_spec.loader.exec_module(_emission_shape)
extract_emission_object = _emission_shape.extract_emission_object
consumer_required_keys = _emission_shape.consumer_required_keys
NORMATIVE_SKILL_RELPATH = _emission_shape.NORMATIVE_SKILL_RELPATH

# INF-700b-1 made this asymmetry explicit in the shared helper itself:
# `_emission_shape.consumer_required_keys` excludes `ticket`
# (INF-400b-2-ii, pre-existing) AND `text` (this AC) from what a CONSUMER
# record must satisfy, while a separate `producer_required_keys` excludes
# only `ticket` for what a producer/template surface must declare. This test
# used to declare its own local `_CONSUMER_OPTIONAL_FIELDS` rather than widen
# the then-single `OPTIONAL_KEYS` constant (which would have wrongly loosened
# the producer-side parity checks too) -- now that the helper names both
# views separately, this test uses the shared consumer view instead of
# duplicating the field set a third time.


class TestExistingSixFieldRecordsRemainReadableWithoutText(unittest.TestCase):
    def setUp(self) -> None:
        self.records = load_fixture("harvest_learnings/unroutable_corpus_28")
        self.assertEqual(
            28, len(self.records), "corpus fixture must be the full 28-record capture"
        )
        skill_path = _REPO_ROOT / NORMATIVE_SKILL_RELPATH
        self.documented_object = extract_emission_object(skill_path)

    def test_documented_shape_declares_text_before_tolerance_is_meaningful(self) -> None:
        # covers: INF-700b-1
        # angle: criterion
        self.assertIn(
            "text",
            self.documented_object,
            "the normative signoff SKILL.md section 7 emission object does not "
            "declare `text` yet -- the backward-compatibility claim this "
            "descriptor pins ('old records stay valid once text is added') is "
            "not yet a claim about anything",
        )

    def test_every_real_record_matches_the_documented_shape_minus_consumer_optional_fields(
        self,
    ) -> None:
        # covers: INF-700b-1
        # angle: real_artifact
        core_required = consumer_required_keys(self.documented_object)
        mismatches = []
        for i, record in enumerate(self.records):
            record_keys = frozenset(record.keys())
            missing_core = core_required - record_keys
            undocumented = record_keys - frozenset(self.documented_object.keys())
            if missing_core or undocumented:
                mismatches.append(
                    f"record[{i}] (entry_kind={record.get('entry_kind')!r}): "
                    f"missing_core={sorted(missing_core)} "
                    f"undocumented={sorted(undocumented)}"
                )
        self.assertEqual(
            [],
            mismatches,
            "records diverge from the documented shape once `ticket`/`text` are "
            "treated as consumer-optional:\n" + "\n".join(mismatches),
        )

    def test_real_reader_rejects_no_record_in_the_corpus_for_lacking_text(self) -> None:
        # covers: INF-700b-1
        # angle: real_artifact
        with tempfile.TemporaryDirectory() as tmpdir:
            sink_path = Path(tmpdir) / "knowledge_emissions.jsonl"
            sink_path.write_text(
                "\n".join(json.dumps(r) for r in self.records) + "\n",
                encoding="utf-8",
            )
            state_path = Path(tmpdir) / "harvest_state.json"

            captured: list[tuple[str, str]] = []

            def _stub_capture(text: str, destination: str) -> None:
                captured.append((text, destination))

            result = harvest(sink_path, state_path, capture_fn=_stub_capture)

        self.assertEqual(
            0,
            result.malformed_lines,
            "no real record should be treated as an unparseable line",
        )
        self.assertEqual(
            0,
            result.missing_required_field_count,
            "no real record should be rejected for missing a REQUIRED digest "
            "field merely because it lacks the OPTIONAL `text` field",
        )
        self.assertEqual(
            28,
            result.no_learning_text,
            "every textless real record must be classified as ineligible-to-"
            "write (a classification), not rejected as invalid",
        )
        self.assertEqual([], captured, "no textless record may be written to a knowledge surface")


if __name__ == "__main__":
    unittest.main()
