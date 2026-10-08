"""
MODULE: tests.kernel.intent.test_gap_quality
GOAL: Test gap record quality: per-capability exclusion reasons, the ranked and capped closest
    list, the readable need title and its separation from the dedup identity, and the draft text.
BUSINESS CONTEXT: A draft that lists every capability unranked without a reason, titled with a
    sorted bag of words, cannot guide the backlog (Rev 3 section 14); the dedup key must stay
    stable so aggregation across runs is unchanged.
ARCHITECTURE: Pure helpers plus the real draft renderer and the aggregation of stored gaps.
"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from typing import Any

from kernel.contracts import CapabilityGap, GapType, compute_gap_key
from kernel.contracts.decision import ExcludedCandidate
from kernel.intent.gap_quality import (
    MAX_CLOSEST,
    describe_candidate,
    exclusion_map,
    rank_closest,
    readable_need,
)
from kernel.persistence.base import aggregate_gaps
from kernel.persistence.gap_store import gap_title, render_gap_draft

EXCLUDED = [ExcludedCandidate(capability_id=c, reason_code=r) for c, r in [
    ("research", "output_schema_mismatch"), ("retrieve.repository", "kind_mismatch"),
    ("host.synthesize", "kind_mismatch"), ("host.research", "kind_mismatch"),
    ("host.formulate_question", "payload_schema_mismatch"), ("host.generate_options", "disabled"),
    ("host.extra", "unavailable:maintenance")]]


class TestRanking(unittest.TestCase):
    """Eligible-but-failed first, then closest reason, capped."""

    def test_exclusion_reasons_are_kept_per_capability(self) -> None:
        reasons = exclusion_map(EXCLUDED)
        self.assertEqual(reasons["research"], "output_schema_mismatch")
        self.assertEqual(reasons["retrieve.repository"], "kind_mismatch")

    def test_eligible_first_then_by_reason_then_id(self) -> None:
        ranked = rank_closest(["decision"], exclusion_map(EXCLUDED), limit=10)
        self.assertEqual(ranked[:3], ["decision", "research", "host.formulate_question"])
        self.assertEqual(ranked[3:6], ["host.research", "host.synthesize", "retrieve.repository"])
        self.assertEqual(ranked[-2:], ["host.extra", "host.generate_options"])

    def test_the_list_is_capped(self) -> None:
        self.assertEqual(len(rank_closest([], exclusion_map(EXCLUDED))), MAX_CLOSEST)

    def test_a_candidate_is_described_with_its_reason(self) -> None:
        self.assertEqual(describe_candidate("research", {"research": "output_schema_mismatch"}),
                         "research (excluded: output_schema_mismatch)")
        self.assertEqual(describe_candidate("decision", {}), "decision (eligible)")


class TestReadableNeed(unittest.TestCase):
    """Titles read like the goal; the dedup key keeps the normalised need."""

    def test_the_goal_is_kept_readable_and_truncated(self) -> None:
        goal = "Come up with ideas to improve tracing in the Leafcutter kernel."
        self.assertEqual(readable_need(goal), goal)
        long = readable_need("word " * 100)
        self.assertLessEqual(len(long), 80)
        self.assertTrue(long.endswith("..."))

    def test_the_gap_key_depends_on_the_normalised_need_only(self) -> None:
        one = compute_gap_key(GapType.UNSUPPORTED, "capability", "i.v1", "o.v1", "need", [])
        two = compute_gap_key("unsupported", "capability", "i.v1", "o.v1", "need", [])
        self.assertEqual(one, two)


def _gap(**changes: Any) -> CapabilityGap:
    now = datetime(2026, 10, 1, 4, 23, tzinfo=UTC)
    fields: dict[str, Any] = dict(id="gap-0000000000000001", gap_key="k" * 16, gap_type=GapType.UNSUPPORTED, goal="Come up with ideas",
                  normalized_need="come ideas up", need_title="Come up with ideas",
                  request_kind="capability", input_schema="i.v1", output_schema="o.v1",
                  candidates_considered=["research", "retrieve.repository"],
                  candidate_exclusions={"research": "output_schema_mismatch",
                                        "retrieve.repository": "kind_mismatch"},
                  created_at=now, first_seen=now, last_seen=now)
    fields.update(changes)
    return CapabilityGap(**fields)


class TestDraft(unittest.TestCase):
    """The draft title and the closest capabilities."""

    def test_the_title_is_the_readable_goal_not_the_token_bag(self) -> None:
        gap = _gap()
        self.assertEqual(gap_title(gap), "Come up with ideas")
        first_line = render_gap_draft(gap).split("\n")[0]
        self.assertEqual(first_line, "# Capability gap draft: Come up with ideas")

    def test_an_old_observation_without_a_title_falls_back_to_the_need(self) -> None:
        self.assertEqual(gap_title(_gap(need_title="")), "come ideas up")

    def test_the_draft_lists_each_candidate_with_its_exclusion_reason(self) -> None:
        text = render_gap_draft(_gap())
        self.assertIn("- research (excluded: output_schema_mismatch)", text)
        self.assertIn("- retrieve.repository (excluded: kind_mismatch)", text)
        self.assertLess(text.index("research (excluded"),
                        text.index("retrieve.repository (excluded"))


class TestAggregateTimestamps(unittest.TestCase):
    """The aggregate never claims a later first sighting than its earliest observation."""

    def test_created_first_and_last_seen_span_the_observations(self) -> None:
        early = datetime(2026, 10, 1, 4, 23, 28, tzinfo=UTC)
        late = early + timedelta(minutes=23)
        first = _gap(id="gap-0000000000000001", created_at=early, first_seen=early, last_seen=early)
        second = _gap(id="gap-0000000000000002", created_at=late, first_seen=late, last_seen=late)
        (merged,) = aggregate_gaps([second, first])
        self.assertEqual((merged.created_at, merged.first_seen, merged.last_seen),
                         (early, early, late))
        self.assertEqual(merged.occurrence_count, 2)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 22:00 [python-coder]: The ranking test pins the order eligible, then closest reason
#   (a denied or schema-mismatched capability is nearer to a fit than a kind mismatch), then id.
#   (#KernelBootstrapV0/INTENT)
# ====================================================================
