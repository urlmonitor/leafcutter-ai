"""
MODULE: tests.kernel.contracts.test_models
GOAL: Behavioural tests of the core contract models: base rules, ids, evidence integrity,
    usage, decisions, options/criteria approval track, task input and the serde allowlist.
BUSINESS CONTEXT: The contracts are the protocol every later phase builds on; each invariant
    here is one a wrong implementation could silently break.
ARCHITECTURE: Offline unit tests against real models; larger payloads come from JSON fixtures.
"""

from __future__ import annotations

import enum
import unittest
from datetime import datetime
from typing import Any

from pydantic import ValidationError

import kernel.contracts as contracts
from kernel.contracts import (
    Actor,
    ActorKind,
    ApprovalStatus,
    Criterion,
    Decision,
    DecisionStatus,
    Evidence,
    Finding,
    FindingKind,
    Option,
    ProposalStatus,
    RoutingAssessment,
    RoutingOutcome,
    Scope,
    TaskInput,
    Usage,
)
from kernel.contracts.base import is_kernel_id, new_id
from kernel.contracts.run import compute_gap_key
from tests.kernel.helpers import make_evidence, narrow


class TestBaseRules(unittest.TestCase):
    """Frozen, extra-forbidding, UTC-only, well-formed ids."""

    def test_unknown_fields_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            Actor.model_validate({"id": "u1", "kind": "human", "nickname": "x"})

    def test_models_are_frozen(self) -> None:
        actor = Actor(id="u1", kind=ActorKind("human"))
        with self.assertRaises(ValidationError):
            actor.id = "u2"

    def test_changes_use_model_copy(self) -> None:
        actor = Actor(id="u1", kind=ActorKind("human"))
        self.assertEqual(actor.model_copy(update={"id": "u2"}).id, "u2")
        self.assertEqual(actor.id, "u1")

    def test_new_id_shape_and_prefix_check(self) -> None:
        value = new_id("run")
        self.assertTrue(is_kernel_id(value, "run"))
        self.assertFalse(is_kernel_id(value, "work"))
        with self.assertRaises(ValueError):
            new_id("bogus")

    def test_naive_datetime_rejected_and_utc_normalised(self) -> None:
        evidence = make_evidence()
        with self.assertRaises(ValidationError):
            Evidence.model_validate({**evidence.model_dump(), "created_at": datetime(2026, 1, 1)})
        self.assertEqual(narrow(evidence.created_at.utcoffset()).total_seconds(), 0)

    def test_malformed_id_rejected(self) -> None:
        data = make_evidence().model_dump()
        with self.assertRaises(ValidationError):
            Evidence.model_validate({**data, "id": "not-an-id"})


class TestEvidence(unittest.TestCase):
    """Content-addressed ids and body requirements."""

    def test_forged_evidence_id_is_rejected(self) -> None:
        data = make_evidence().model_dump()
        with self.assertRaises(ValidationError) as ctx:
            Evidence.model_validate({**data, "id": "ev-0000000000000000"})
        self.assertIn("content-addressed", str(ctx.exception))

    def test_evidence_needs_excerpt_or_artifact(self) -> None:
        data = make_evidence().model_dump()
        with self.assertRaises(ValidationError):
            Evidence.model_validate({**data, "excerpt": None, "artifact_ref": None})

    def test_source_fact_finding_needs_support(self) -> None:
        with self.assertRaises(ValidationError):
            Finding(id=new_id("find"), claim="c", kind=FindingKind("source_fact"), producer="p")
        ok = Finding(id=new_id("find"), claim="c", kind=FindingKind("inference"), producer="p")
        self.assertEqual(ok.supporting_evidence_ids, [])


class TestUsage(unittest.TestCase):
    """Unknown usage is None, never 0 (Rev 3 section 7.9)."""

    def test_usage_unknown_is_none(self) -> None:
        usage = Usage(provider="host")
        self.assertIsNone(usage.input_tokens)
        self.assertIsNone(usage.cost_usd)
        self.assertEqual(usage.cost_provenance, "unavailable")

    def test_known_cost_requires_provenance(self) -> None:
        with self.assertRaises(ValidationError):
            Usage(provider="jev", cost_usd=0.01)
        self.assertEqual(Usage(provider="jev", cost_usd=0.01,
                               cost_provenance="estimated").cost_usd, 0.01)

    def test_provenance_without_cost_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            Usage(provider="jev", cost_provenance="reported")


class TestDecision(unittest.TestCase):
    """Status invariants of Decision and RoutingAssessment."""

    def test_resolved_needs_a_supplied_option(self) -> None:
        base: dict[str, Any] = {"id": new_id("dec"), "question": "q", "option_ids": ["opt-a"]}
        with self.assertRaises(ValidationError):
            Decision(**base, status=DecisionStatus("resolved"))
        with self.assertRaises(ValidationError):
            Decision(**base, status=DecisionStatus("resolved"), selected_option_id="opt-zzz")
        self.assertEqual(Decision(**base, status=DecisionStatus("resolved"),
                                  selected_option_id="opt-a").status.value, "resolved")

    def test_unresolved_cannot_select(self) -> None:
        with self.assertRaises(ValidationError):
            Decision(id=new_id("dec"), question="q", option_ids=["a"], status=DecisionStatus("needs_human"),
                     selected_option_id="a")

    def test_routing_selected_must_be_eligible(self) -> None:
        base: dict[str, Any] = {"id": new_id("ra"), "work_item_id": new_id("work"),
                "eligible_candidate_ids": ["decision"]}
        with self.assertRaises(ValidationError):
            RoutingAssessment(**base, outcome=RoutingOutcome("selected"), selected="research")
        with self.assertRaises(ValidationError):
            RoutingAssessment(**base, outcome=RoutingOutcome("no_match"), selected="decision")
        ok = RoutingAssessment(**base, outcome=RoutingOutcome("selected"), selected="decision")
        self.assertFalse(ok.jev_called)


class TestProposalApprovalTrack(unittest.TestCase):
    """ADR-053: LLM-proposed options/criteria enter an approval track (both routes express)."""

    def test_supplied_criterion_needs_no_approval(self) -> None:
        crit = Criterion(id="c1", question="Is it fast?")
        self.assertEqual(crit.proposal_status.value, "supplied")
        self.assertEqual(crit.approval_status.value, "not_required")

    def test_llm_proposed_criterion_cannot_skip_approval(self) -> None:
        with self.assertRaises(ValidationError):
            Criterion(id="c1", question="q", proposal_status=ProposalStatus("proposed"))
        ok = Criterion(id="c1", question="q", proposal_status=ProposalStatus("proposed"),
                       approval_status=ApprovalStatus("proposed"), proposed_by="host.generate_options")
        self.assertEqual(ok.approval_status.value, "proposed")

    def test_human_approval_step_records_approver(self) -> None:
        with self.assertRaises(ValidationError):
            Criterion(id="c1", question="q", proposal_status=ProposalStatus("proposed"),
                      approval_status=ApprovalStatus("approved"))
        approved = Criterion(id="c1", question="q", proposal_status=ProposalStatus("proposed"),
                             approval_status=ApprovalStatus("approved"), approved_by="human:user")
        self.assertEqual(approved.approved_by, "human:user")

    def test_same_rules_for_options(self) -> None:
        with self.assertRaises(ValidationError):
            Option(id="o1", title="t", proposal_status=ProposalStatus("proposed"))
        self.assertEqual(Option(id="o1", title="t").approval_status.value, "not_required")


class TestTaskInput(unittest.TestCase):
    """External boundary validation."""

    def setUp(self) -> None:
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = self._tmp.name

    def _input(self, **overrides: object) -> TaskInput:
        data = {"goal": "Decide X", "caller": {"id": "u", "kind": "human"},
                "scope": {"workspace_id": "w", "repository_root": self.root}, **overrides}
        return TaskInput.model_validate(data)

    def test_defaults(self) -> None:
        task = self._input()
        # None means "the caller did not choose": intake classifies the goal (was: silently
        # decision_report, which made every evidence or ideas goal unsupported).
        self.assertIsNone(task.requested_output_schema)
        self.assertEqual(task.permissions, ["read_repo"])

    def test_an_explicit_output_schema_is_kept_and_still_validated(self) -> None:
        task = self._input(requested_output_schema="leafcutter.evidence_bundle.v1")
        self.assertEqual(task.requested_output_schema, "leafcutter.evidence_bundle.v1")
        with self.assertRaises(ValidationError):
            self._input(requested_output_schema="leafcutter.unknown.v1")

    def test_relative_repository_root_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            self._input(scope={"workspace_id": "w", "repository_root": "relative/dir"})

    def test_read_roots_must_stay_inside(self) -> None:
        for bad in ("../outside", "/abs/root", "a/../../b"):
            with self.subTest(root=bad), self.assertRaises(ValidationError):
                Scope(workspace_id="w", repository_root=self.root, read_roots=[bad])
        ok = Scope(workspace_id="w", repository_root=self.root, read_roots=["docs/a"])
        self.assertEqual(ok.read_roots, ["docs/a"])

    def test_unknown_output_schema_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            self._input(requested_output_schema="leafcutter.nope.v1")

    def test_payload_and_schema_come_together_and_are_validated(self) -> None:
        with self.assertRaises(ValidationError):
            self._input(input_payload={"goal": "x"})
        with self.assertRaises(ValidationError):
            self._input(input_payload_schema="leafcutter.goal_request.v1",
                        input_payload={"goal": ""})
        ok = self._input(input_payload_schema="leafcutter.goal_request.v1",
                         input_payload={"goal": "x"})
        self.assertEqual(ok.input_payload, {"goal": "x"})

    def test_goal_length_bounds(self) -> None:
        with self.assertRaises(ValidationError):
            self._input(goal="")
        with self.assertRaises(ValidationError):
            self._input(goal="x" * 4001)


class TestGapKey(unittest.TestCase):
    """The gap dedup key is stable and order-insensitive over components."""

    def test_key_is_deterministic_and_component_order_insensitive(self) -> None:
        args = ("unsupported", "capability", "in.v1", "out.v1", "cache design")
        first = compute_gap_key(*args, ["b", "a"])
        self.assertEqual(first, compute_gap_key(*args, ["a", "b"]))
        self.assertNotEqual(first, compute_gap_key(*args, ["a"]))
        self.assertEqual(len(first), 64)


class TestAllModels(unittest.TestCase):
    """ALL_MODELS feeds the strict-msgpack allowlist."""

    def test_contains_models_and_enums_and_nothing_foreign(self) -> None:
        names = {t.__name__ for t in contracts.ALL_MODELS}
        for required in ("Evidence", "WorkItem", "RunEnvelope", "RunStatus", "CheckExecutor",
                         "RegistrySnapshot", "EvidenceBundlePayload"):
            self.assertIn(required, names)
        for t in contracts.ALL_MODELS:
            self.assertTrue(issubclass(t, (contracts.KernelModel, enum.Enum)), t)
            self.assertTrue(t.__module__.startswith("kernel.contracts"), t)


if __name__ == "__main__":
    unittest.main()

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 22:00 [python-coder]: test_defaults now expects `requested_output_schema` to be
#   None (the caller did not choose; intake classifies the goal) instead of the old silent
#   decision_report default it pinned. (#KernelBootstrapV0/INTENT)
# - 2026-09-30 22:00 [python-coder]: Covers the ADR-053 proposal/approval track so both the LLM
#   and human routes for missing criteria remain expressible. (#KernelBootstrapV0/P1)
# ====================================================================
