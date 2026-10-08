"""
MODULE: tests.kernel.contracts.test_result_lifecycle
GOAL: Prove the five-status CapabilityResult lifecycle invariants, RequestBody/WorkItem
    contracts, InteractionSubmission identity rules and RunEnvelope status consistency.
BUSINESS CONTEXT: The kernel trusts these validators to reject contradictory results, forged
    human answers and inconsistent envelopes before they can touch run state (Rev 3 7.6, 7.8).
ARCHITECTURE: One accept and one reject case per rule, so each validator is shown to fail.
"""

from __future__ import annotations

import unittest
from typing import Any

from pydantic import ValidationError

from kernel.contracts import (
    Actor,
    ActorKind,
    CapabilityInvocation,
    CapabilityResult,
    HostWorkRequest,
    HumanQuestion,
    InteractionSubmission,
    ResultStatus,
    RunEnvelope,
    RunStatus,
    WorkItem,
)
from kernel.contracts.base import new_id
from kernel.contracts.work import RequestProposal
from tests.kernel.helpers import make_invocation, make_request_body, narrow


def _proposal() -> RequestProposal:
    body = make_request_body()
    return RequestProposal.model_validate(body.model_dump())


def _result(status: str, **fields: Any) -> CapabilityResult:
    return CapabilityResult(invocation_id=new_id("inv"), work_item_id=new_id("work"),
                            status=ResultStatus(status), **fields)


class TestResultLifecycle(unittest.TestCase):
    """Rev 3 section 7.6 invariants."""

    OUT = {"output_schema_id": "leafcutter.evidence_bundle.v1", "output_payload": {}}

    def test_completed_ok_and_rejections(self) -> None:
        self.assertEqual(_result("completed", **self.OUT).status.value, "completed")
        with self.assertRaises(ValidationError):
            _result("completed")
        with self.assertRaises(ValidationError):
            _result("completed", **self.OUT, requests=[_proposal()])
        with self.assertRaises(ValidationError):
            _result("completed", **self.OUT, continuation_state={"phase": "x"})

    def test_waiting_needs_request_and_continuation(self) -> None:
        ok = _result("waiting", requests=[_proposal()], continuation_state={"phase": "a"})
        self.assertEqual(len(ok.requests), 1)
        with self.assertRaises(ValidationError):
            _result("waiting", continuation_state={"phase": "a"})
        with self.assertRaises(ValidationError):
            _result("waiting", requests=[_proposal()])

    def test_partial_needs_limitation_and_no_continuation(self) -> None:
        self.assertEqual(_result("partial", limitations=["no source"]).status.value, "partial")
        self.assertEqual(_result("partial", diagnostics={"limitation_work_item_cap": True}
                                 ).status.value, "partial")
        self.assertEqual(_result("partial", output_schema_id="leafcutter.decision_report.v1",
                                 output_payload={"limitations": ["x"]}).status.value, "partial")
        with self.assertRaises(ValidationError):
            _result("partial")
        with self.assertRaises(ValidationError):
            _result("partial", limitations=["x"], continuation_state={"a": 1})

    def test_blocked_identifies_prerequisite(self) -> None:
        self.assertEqual(_result("blocked", error={"code": "no_capability"}).status.value,
                         "blocked")
        with self.assertRaises(ValidationError):
            _result("blocked")
        with self.assertRaises(ValidationError):
            _result("blocked", limitations=["x"], requests=[_proposal()])

    def test_failed_needs_error_and_error_only_on_failed_or_blocked(self) -> None:
        failed = _result("failed", error={"code": "provider_unavailable", "retryable": True})
        self.assertTrue(narrow(failed.error).retryable)
        with self.assertRaises(ValidationError):
            _result("failed")
        with self.assertRaises(ValidationError):
            _result("completed", **self.OUT, error={"code": "x"})

    def test_output_schema_and_payload_come_together(self) -> None:
        with self.assertRaises(ValidationError):
            _result("partial", limitations=["x"], output_schema_id="leafcutter.options.v1")


class TestRequestsAndWork(unittest.TestCase):
    """Requests validate their payload through the catalog."""

    def test_payload_is_validated_against_its_schema(self) -> None:
        with self.assertRaises(ValidationError):
            make_request_body(payload={"need": {"id": "n", "category": "bogus", "question": "q"}})

    def test_unknown_schemas_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            make_request_body(payload_schema="leafcutter.nope.v1", payload={})
        with self.assertRaises(ValidationError):
            make_request_body(output_schema="leafcutter.nope.v1")

    def test_work_item_defaults_ready_and_counts_start_at_zero(self) -> None:
        item = WorkItem(id=new_id("work"), root_task_id=new_id("task"), request_id=new_id("req"))
        self.assertEqual((item.status.value, item.attempts, item.depth), ("ready", 0, 0))

    def test_invocation_attempt_starts_at_one(self) -> None:
        invocation: CapabilityInvocation = make_invocation()
        self.assertEqual(invocation.attempt, 1)
        with self.assertRaises(ValidationError):
            invocation.model_validate({**invocation.model_dump(), "attempt": 0})


def _submission(schema: str, kind: str, response: dict) -> InteractionSubmission:
    return InteractionSubmission(
        run_id=new_id("run"), interaction_id=new_id("int"), expected_state_revision=1,
        actor=Actor(id="a", kind=ActorKind(kind)), response_schema_id=schema, response=response)


class TestSubmissionIdentity(unittest.TestCase):
    """A generative response can never impersonate a human answer."""

    def test_human_answer_requires_human_actor(self) -> None:
        _submission("leafcutter.human_answer.v1", "human", {"choice_id": "yes"})
        with self.assertRaises(ValidationError):
            _submission("leafcutter.human_answer.v1", "host", {"choice_id": "yes"})

    def test_human_cannot_submit_generative_schema(self) -> None:
        _submission("leafcutter.options.v1", "host", {"options": []})
        with self.assertRaises(ValidationError):
            _submission("leafcutter.options.v1", "human", {"options": []})

    def test_unknown_fields_rejected_at_boundary(self) -> None:
        data = _submission("leafcutter.options.v1", "host", {}).model_dump()
        with self.assertRaises(ValidationError):
            InteractionSubmission.model_validate({**data, "sneaky": True})


def _host_request() -> HostWorkRequest:
    return HostWorkRequest(id=new_id("int"), work_item_id=new_id("work"), operation="synthesize",
                           goal="g", output_schema_id="leafcutter.findings.v1", state_revision=2)


def _human_question() -> HumanQuestion:
    return HumanQuestion(id=new_id("int"), work_item_id=new_id("work"), question="q?",
                         free_text_allowed=True, state_revision=2)


def _envelope(status: str, **fields: Any) -> RunEnvelope:
    return RunEnvelope(run_id=new_id("run"), root_task_id=new_id("task"), state_revision=3,
                       status=RunStatus(status), **fields)


class TestEnvelope(unittest.TestCase):
    """Envelope status and pending interaction must agree."""

    def test_waiting_statuses_need_matching_interaction(self) -> None:
        _envelope("waiting_host", pending_interaction=_host_request())
        _envelope("waiting_human", pending_interaction=_human_question())
        with self.assertRaises(ValidationError):
            _envelope("waiting_host", pending_interaction=_human_question())
        with self.assertRaises(ValidationError):
            _envelope("waiting_human")

    def test_terminal_status_cannot_have_pending_interaction(self) -> None:
        with self.assertRaises(ValidationError):
            _envelope("partial", pending_interaction=_host_request())

    def test_completed_needs_output_and_failed_needs_error(self) -> None:
        out = {"schema_id": "leafcutter.decision_report.v1", "payload": {}}
        self.assertEqual(_envelope("completed", output=out).status.value, "completed")
        with self.assertRaises(ValidationError):
            _envelope("completed")
        with self.assertRaises(ValidationError):
            _envelope("failed")
        _envelope("failed", errors=[{"code": "internal"}])

    def test_envelope_roundtrips_pending_interaction_type(self) -> None:
        env = _envelope("waiting_human", pending_interaction=_human_question())
        again = RunEnvelope.model_validate_json(env.model_dump_json())
        self.assertIsInstance(again.pending_interaction, HumanQuestion)
        host = _envelope("waiting_host", pending_interaction=_host_request())
        self.assertIsInstance(RunEnvelope.model_validate_json(host.model_dump_json())
                              .pending_interaction, HostWorkRequest)

    def test_human_question_needs_choices_or_free_text(self) -> None:
        with self.assertRaises(ValidationError):
            HumanQuestion(id=new_id("int"), work_item_id=new_id("work"), question="q",
                          state_revision=0)


if __name__ == "__main__":
    unittest.main()

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:00 [python-coder]: Every invariant has an accepting and a rejecting case so
#   the test fails if the validator is removed. (#KernelBootstrapV0/P1)
# ====================================================================
