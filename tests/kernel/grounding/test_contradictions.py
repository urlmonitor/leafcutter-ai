"""
MODULE: tests.kernel.grounding.test_contradictions
GOAL: Tests that the research bundle records each contradiction once (by evidence pair and
    claim) and records a non-localised bundle-level contradiction once, flagged as unlocalised,
    never beside the localised one it duplicates.
BUSINESS CONTEXT: A live bundle listed one contradiction twice and carried a second, vague one
    from Jev (G4); duplicates inflate the apparent disagreement and push a decision to human
    escalation for no new reason (Rev 3 section 10.5: conflicts are preserved, not multiplied).
ARCHITECTURE: Drives the real collect step (child bundles read through the artifact store, the
    continuation as the kernel hands it back on resume) and `record_contradiction`.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kernel.capabilities.research.collect import collect_outcomes, record_contradiction
from kernel.capabilities.research.state import Collected, ResearchContinuation
from kernel.contracts import schema_ids
from kernel.contracts.enums import RequestKind
from kernel.contracts.evidence import Contradiction, EvidenceBundlePayload
from tests.kernel.capabilities.support import child, evidence_item
from tests.kernel.helpers import make_context

A = evidence_item("docs/a.md#L1-L2", "Use sqlite.")
B = evidence_item("docs/b.md#L1-L2", "Use plain files.")


def _bundle(*contradictions: Contradiction) -> dict:
    return EvidenceBundlePayload(
        evidence_ids=[A.id, B.id], evidence=[A, B],
        contradictions=list(contradictions)).model_dump(mode="json")


class TestContradictionDedup(unittest.TestCase):
    """The same disagreement is recorded once."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.ctx = make_context(Path(tmp.name))
        self.pair = Contradiction(a=A.id, b=B.id, note="sqlite versus files")

    def test_a_contradiction_reported_by_two_children_is_kept_once(self) -> None:
        one = child(self.ctx, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE,
                    _bundle(self.pair))
        two = child(self.ctx, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE,
                    _bundle(self.pair))
        out = collect_outcomes(self.ctx, ResearchContinuation(), [one, two])
        self.assertEqual(len(out.contradictions), 1)

    def test_the_pair_in_the_other_order_is_the_same_contradiction(self) -> None:
        flipped = Contradiction(a=B.id, b=A.id, note="sqlite versus files")
        one = child(self.ctx, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE,
                    _bundle(self.pair, flipped))
        out = collect_outcomes(self.ctx, ResearchContinuation(), [one])
        self.assertEqual(len(out.contradictions), 1)

    def test_a_resumed_collect_does_not_double_the_continuations_contradictions(self) -> None:
        cont = ResearchContinuation(contradictions=[self.pair])
        one = child(self.ctx, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE,
                    _bundle(self.pair))
        out = collect_outcomes(self.ctx, cont, [one])
        self.assertEqual(len(out.contradictions), 1)

    def test_a_different_claim_between_the_same_pair_is_kept(self) -> None:
        other = Contradiction(a=A.id, b=B.id, note="a second, different disagreement")
        one = child(self.ctx, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE,
                    _bundle(self.pair, other))
        out = collect_outcomes(self.ctx, ResearchContinuation(), [one])
        self.assertEqual(len(out.contradictions), 2)


class TestUnlocalisedContradiction(unittest.TestCase):
    """Jev's bundle-wide conflict is recorded once, flagged, and never duplicates a pair."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.ctx = make_context(Path(tmp.name))

    def _collected(self, *contradictions: Contradiction) -> Collected:
        out = Collected(evidence={A.id: A, B.id: B})
        out.contradictions.extend(contradictions)
        return out

    def test_it_is_flagged_as_unlocalised(self) -> None:
        out = self._collected()
        record_contradiction(self.ctx, out, 0.85)
        self.assertEqual(len(out.contradictions), 1)
        self.assertIn("unlocalised", out.contradictions[0].note)

    def test_it_is_recorded_once_across_rounds(self) -> None:
        out = self._collected()
        record_contradiction(self.ctx, out, 0.85)
        record_contradiction(self.ctx, out, 0.9)
        self.assertEqual(len(out.contradictions), 1)

    def test_it_is_not_added_beside_a_localised_contradiction(self) -> None:
        out = self._collected(Contradiction(a=A.id, b=B.id, note="sqlite versus files"))
        record_contradiction(self.ctx, out, 0.85)
        self.assertEqual(len(out.contradictions), 1)
        self.assertNotIn("unlocalised", out.contradictions[0].note)

    def test_below_the_threshold_nothing_is_recorded(self) -> None:
        out = self._collected()
        record_contradiction(self.ctx, out, 0.1)
        self.assertEqual(out.contradictions, [])


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 23:00 [python-coder]: Tests for G4 written first and seen failing.
#   (#KernelBootstrapV0/GROUND)
# ====================================================================
