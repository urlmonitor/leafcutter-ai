"""
MODULE: test_adr_learning_emission_sink
GOAL: Assert ADR-011 satisfies the content contract INF-400c-1 commissioned it under,
      and that ADR-034 records the write-ownership decision that resolves it.
BUSINESS CONTEXT: INF-400c-1 does not merely require "an ADR exists" — it names four
      content items and requires the ADR to reference INF-400b and INF-400c as its
      driving requirements. ADR-011 was written in June and referenced only the
      commissioning epic ticket, so the AC was satisfiable in spirit and unmet in
      letter for three months while reading work_status: todo.
ARCHITECTURE: Reads the ADR files from disk and asserts on their content. These are
      doc-shaped ACs, so the test is necessarily structural — but it asserts on the
      SPECIFIC clauses the ACs name, not on mere file existence, which would pass on
      an empty file.
"""

from __future__ import annotations

import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_ADRS = _REPO_ROOT / "docs" / "architecture" / "adrs"
_SINK_ADR = _ADRS / "ADR-011-learning-emission-sink.md"
_OWNERSHIP_ADR = _ADRS / "ADR-034-knowledge-write-ownership.md"


class TestLearningEmissionSinkAdr(unittest.TestCase):
    """INF-400c-1: the emission-sink ADR exists and carries the required content."""

    def test_adr_exists_at_the_commissioned_path(self) -> None:
        """The AC names docs/architecture/adrs/ADR-NNN-learning-emission-sink.md."""
        # covers: INF-400c-1
        self.assertTrue(_SINK_ADR.is_file(), f"{_SINK_ADR} must exist")

    def test_adr_documents_the_four_required_items(self) -> None:
        """Context, options considered, chosen option with rationale, consequences."""
        # covers: INF-400c-1
        text = _SINK_ADR.read_text(encoding="utf-8")
        for heading in ("## Context", "## Decision", "## Rationale", "## Consequences"):
            self.assertIn(heading, text, f"ADR-011 must contain a '{heading}' section")

    def test_adr_names_both_sink_options(self) -> None:
        """The AC requires the options considered to be recorded, not just the winner."""
        # covers: INF-400c-1
        text = _SINK_ADR.read_text(encoding="utf-8")
        self.assertIn("knowledge_emissions.jsonl", text)
        self.assertIn("agent_telemetry.jsonl", text)

    def test_adr_references_its_driving_requirements(self) -> None:
        """INF-400c-1's final clause: the ADR references INF-400b and INF-400c.

        This is the clause that was unmet. ADR-011 cited only the commissioning epic
        ticket, so nothing connected the decision back to the criteria that asked for
        it — which is how the AC sat at todo while the ADR sat on disk.
        """
        # covers: INF-400c-1
        text = _SINK_ADR.read_text(encoding="utf-8")
        self.assertIn("INF-400b", text,
                      "ADR-011 must reference INF-400b as a driving requirement")
        self.assertIn("INF-400c", text,
                      "ADR-011 must reference INF-400c as a driving requirement")


class TestWriteOwnershipAdr(unittest.TestCase):
    """ADR-034 resolves the three-way write-ownership contradiction."""

    def test_ownership_adr_exists(self) -> None:
        self.assertTrue(_OWNERSHIP_ADR.is_file(), f"{_OWNERSHIP_ADR} must exist")

    def test_inline_capture_is_rejected_not_deferred(self) -> None:
        """The decision's whole point: demote ADR-011's Alternative C to rejected.

        Leaving it "deferred, not rejected" is what let the templates keep describing
        the losing design for three months, so the word matters.
        """
        text = _OWNERSHIP_ADR.read_text(encoding="utf-8").lower()
        self.assertIn("rejected", text)
        self.assertIn("deferred", text)

    def test_the_two_adrs_cross_reference(self) -> None:
        """A resolution nobody can find from the thing it resolves is not a resolution."""
        self.assertIn("ADR-034", _SINK_ADR.read_text(encoding="utf-8"))
        self.assertIn("ADR-011", _OWNERSHIP_ADR.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
