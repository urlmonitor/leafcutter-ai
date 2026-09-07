"""
MODULE: tests/knowledge/test_the_28_shipped_records_conform_to_the_documented_shape.py
GOAL: INF-400b-2-ii descriptor 2 — every record in the real 28-record corpus
      carries exactly the required key set that the normative signoff SKILL.md
      section 7 step 4 documents, proving the reconciliation chose the shape
      real emitters already produce rather than a shape only the documents
      described.

Fixture-authenticity: ``unroutable_corpus_28.json`` is a verbatim capture of
the 28 real knowledge_captured records (see tests/fixtures/harvest_learnings/
README or the fixture itself) — this test does not hand-author any record.

This test derives the "documented shape" by parsing the real SKILL.md file
with the same helper the sibling unit_tests/agents/ descriptors use, rather
than hard-coding a second copy of the field list — a hard-coded duplicate
could drift from the normative source without either failing.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HELPER_PATH = _REPO_ROOT / "unit_tests" / "agents" / "_emission_shape.py"

_spec = importlib.util.spec_from_file_location("_emission_shape", _HELPER_PATH)
assert _spec is not None and _spec.loader is not None, f"could not load spec for {_HELPER_PATH}"
_emission_shape: Any = importlib.util.module_from_spec(_spec)
sys.modules["_emission_shape"] = _emission_shape
_spec.loader.exec_module(_emission_shape)

extract_emission_object = _emission_shape.extract_emission_object
required_keys = _emission_shape.required_keys
NORMATIVE_SKILL_RELPATH = _emission_shape.NORMATIVE_SKILL_RELPATH

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from conftest import load_fixture  # noqa: E402


class TestThe28ShippedRecordsConformToTheDocumentedShape(unittest.TestCase):
    def test_the_28_shipped_records_conform_to_the_documented_shape(self):
        # covers: INF-400b-2-ii
        # angle: real_artifact
        skill_path = _REPO_ROOT / NORMATIVE_SKILL_RELPATH
        documented_object = extract_emission_object(skill_path)
        documented_shape = required_keys(documented_object)

        records = load_fixture("harvest_learnings/unroutable_corpus_28")
        self.assertEqual(28, len(records), "corpus fixture must be the full 28-record capture")

        mismatches = []
        for i, record in enumerate(records):
            record_keys = frozenset(record.keys())
            if record_keys != documented_shape:
                mismatches.append(
                    f"record[{i}] (entry_kind={record.get('entry_kind')!r}): "
                    f"{sorted(record_keys)} != documented {sorted(documented_shape)}"
                )

        self.assertEqual(
            [],
            mismatches,
            "records diverge from the documented normative shape:\n" + "\n".join(mismatches),
        )
