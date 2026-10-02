"""
MODULE: tests.kernel.memory.test_builder
GOAL: The record builder: a resolved decision a human approved becomes a valid record carrying
    the original options, assumptions, evidence references and provenance, and every decision a
    human did not approve is refused.
BUSINESS CONTEXT: Records never self-authorize (ADR-060): the builder is the single gate between a
    kernel decision and a filable record, so each way of not being human-approved gets a test.
ARCHITECTURE: Real kernel contract models in, a real DecisionRecord out, validated against the
    committed JSON Schema as well as the model.
"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from kernel.contracts.enums import ApprovalStatus, DecisionStatus
from kernel.memory.builder import (
    NotApproved,
    RecordExtras,
    RecordFilters,
    build_decision_record,
    human_actor,
    one_line,
)
from kernel.memory.codec import record_to_dict
from kernel.memory.models import PrecedentNote, RecordProvenance
from kernel.memory.validate import schema_problems
from tests.kernel.memory.support import (
    criteria,
    evidence_item,
    human_decision,
    options,
    ranking,
    schema,
)

PROVENANCE = RecordProvenance(created_at="2026-10-01T10:00:00Z", run_id="run-aaaaaaaaaaaaaaaa",
                              langfuse_trace_id="0123456789abcdef0123456789abcdef")


def build(decision=None, **extras):  # noqa: ANN001, ANN202
    """Build a record from the standard decision, options, criteria and one evidence item."""
    return build_decision_record(
        decision or human_decision(), options(), criteria(), [evidence_item()], PROVENANCE,
        extras=RecordExtras(**extras) if extras else None)


class TestBuildsFromAHumanApprovedDecision(unittest.TestCase):
    """What a record keeps of the decision."""

    def test_the_record_is_valid_by_the_schema_and_carries_the_approval(self) -> None:
        record = build()
        self.assertEqual(schema_problems(record_to_dict(record), schema()), [])
        self.assertEqual(record.approval.approved_by, "human:tester")
        self.assertEqual(record.selected_option_id, "opt.a")
        self.assertEqual(record.approval.approval_status, "approved")

    def test_original_assumptions_and_evidence_references_are_kept(self) -> None:
        record = build()
        self.assertEqual(record.assumptions, ["opt.a assumption"])
        self.assertEqual([o.assumptions for o in record.options],
                         [["opt.a assumption"], ["opt.b assumption"]])
        (ref,) = record.evidence
        self.assertEqual(ref.locator, "docs/a.md#L1-L5")
        self.assertEqual(ref.source_version.commit, "abc1234567")  # type: ignore[union-attr]
        self.assertEqual(len(ref.content_hash), 64)

    def test_the_ranking_the_human_saw_and_the_chosen_rank_are_recorded(self) -> None:
        record = build(ranking=ranking())
        self.assertEqual(record.assessment.selected_rank, 1)
        self.assertEqual(record.assessment.confidence, 0.9)
        self.assertEqual([r.option_id for r in record.assessment.ranking], ["opt.a", "opt.b"])

    def test_a_record_without_filters_is_filed_repository_wide(self) -> None:
        self.assertTrue(build().repository_wide)
        scoped = build(filters=RecordFilters(components=["decision_kernel"]))
        self.assertFalse(scoped.repository_wide)

    def test_precedent_notes_and_links_are_kept(self) -> None:
        note = PrecedentNote(id="dec-ef8ddcb79d668a67", applicability=0.9, action="reused")
        record = build(precedents=[note], related=["dec-ef8ddcb79d668a67"])
        self.assertEqual(record.precedents_considered, [note])
        self.assertEqual(record.related, ["dec-ef8ddcb79d668a67"])

    def test_only_evidence_the_decision_names_is_referenced(self) -> None:
        other = evidence_item("docs/other.md#L1-L2", "Something else.")
        record = build_decision_record(human_decision(), options(), criteria(),
                                       [evidence_item(), other], PROVENANCE)
        self.assertEqual(len(record.evidence), 1)

    def test_per_criterion_evidence_lists_only_what_is_given(self) -> None:
        item = evidence_item()
        record = build(criterion_evidence={"crit.one": [item.id]})
        self.assertEqual(record.criteria[0].evidence_ids, [item.id])


class TestRefusesWhatAHumanDidNotApprove(unittest.TestCase):
    """The builder is the self-authorization gate."""

    def test_an_unresolved_decision_is_refused(self) -> None:
        with self.assertRaises(NotApproved):
            build(human_decision(status=DecisionStatus.NEEDS_HUMAN))

    def test_a_not_required_approval_is_refused(self) -> None:
        with self.assertRaises(NotApproved):
            build(human_decision(approval=ApprovalStatus.NOT_REQUIRED))

    def test_a_missing_approver_is_refused(self) -> None:
        # covers: DK-300c-1-i
        with self.assertRaises(NotApproved):
            build(human_decision(approved_by=None))

    def test_a_host_or_model_approver_is_refused(self) -> None:
        # covers: DK-300c-1-i
        for actor in ("host:fake", "jev", "kernel", "model:gpt", "service:x"):
            with self.assertRaises(NotApproved, msg=actor):
                build(human_decision(approved_by=actor))

    def test_a_missing_approval_time_is_refused(self) -> None:
        decision = human_decision().model_copy(update={"approved_at": None})
        with self.assertRaises(NotApproved):
            build(decision)


class TestHelpers(unittest.TestCase):
    """Small pure helpers."""

    def test_a_bare_actor_id_becomes_a_human_actor(self) -> None:
        self.assertEqual(human_actor("user"), "human:user")
        self.assertEqual(human_actor("human:user"), "human:user")
        self.assertEqual(human_actor("human"), "human")
        self.assertIsNone(human_actor(None))
        self.assertIsNone(human_actor("host:fake"))

    def test_one_line_cuts_at_a_word_boundary(self) -> None:
        text = "alpha beta gamma delta epsilon"
        self.assertEqual(one_line(text, 100), text)
        self.assertEqual(one_line(text, 12), "alpha beta ...")

    def test_approved_at_is_formatted_in_utc(self) -> None:
        # covers: DK-300b-3
        when = datetime(2026, 10, 1, 12, 30, 5, tzinfo=UTC)
        decision = human_decision().model_copy(update={"approved_at": when})
        self.assertEqual(build(decision).approval.approved_at, "2026-10-01T12:30:05Z")


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: One refusal test per way a decision can fail to be human-approved,
#   because the builder is the only gate between a kernel decision and a record.
#   (#KernelDecisionStore)
# ====================================================================
