"""
MODULE: tests.kernel.intent.test_roots
GOAL: Test how a resolved answer kind becomes a root request and how the kinds the read-only
    kernel does not serve are declined.
BUSINESS CONTEXT: A decline is an honest deterministic answer, not a capability gap (Rev 3
    sections 13.3, 13.4 and 14): a write request is a permission-type observation and an
    out-of-domain request is never a build opportunity.
ARCHITECTURE: Pure functions over contract models; the options payload is validated by the real
    schema catalog through the Request model.
"""

from __future__ import annotations

import unittest

from kernel.contracts import CapabilityGap, GapType, Request, RequestKind, schema_ids
from kernel.contracts.payloads import OptionsRequestPayload
from kernel.contracts.schema_catalog import validate_payload
from kernel.intent.roots import (
    DECLINES,
    decline_for,
    decline_limitation,
    initial_contract,
    shape_root,
    write_denial_reason,
)
from kernel.persistence.gap_store import BUILD_OPPORTUNITY_TYPES, is_build_opportunity


def _root(goal: str = "Where are tests saved?") -> Request:
    return Request(id="req-0000000000000001", kind=RequestKind.CAPABILITY, goal=goal,
                   payload_schema=schema_ids.GOAL_REQUEST, payload={"goal": goal},
                   requested_output_schema=schema_ids.DECISION_REPORT)


class TestShapeRoot(unittest.TestCase):
    """Each served kind resolves to the contract a capability can produce."""

    def test_decision_stays_a_capability_request_with_the_decision_report(self) -> None:
        shaped = shape_root(_root(), "decision", "Pick a store")
        self.assertEqual((shaped.kind, shaped.requested_output_schema, shaped.goal),
                         (RequestKind.CAPABILITY, schema_ids.DECISION_REPORT, "Pick a store"))
        self.assertEqual(shaped.payload, {"goal": "Pick a store"})

    def test_evidence_asks_for_an_evidence_bundle_over_a_goal_payload(self) -> None:
        shaped = shape_root(_root(), "evidence", "Where are tests saved?")
        self.assertEqual((shaped.kind, shaped.payload_schema, shaped.requested_output_schema),
                         (RequestKind.CAPABILITY, schema_ids.GOAL_REQUEST,
                          schema_ids.EVIDENCE_BUNDLE))

    def test_ideas_become_an_options_request_for_the_generate_options_operation(self) -> None:
        shaped = shape_root(_root(), "ideas", "Improve tracing")
        self.assertEqual((shaped.kind, shaped.payload_schema, shaped.requested_output_schema),
                         (RequestKind.OPTIONS, schema_ids.OPTIONS_REQUEST, schema_ids.OPTIONS))
        validate_payload(shaped.payload_schema, shaped.payload)
        body = OptionsRequestPayload.model_validate(shaped.payload)
        self.assertEqual(body.problem, "Improve tracing")
        self.assertFalse(body.propose_criteria)  # ideas, not a decision: no criteria unasked

    def test_the_identity_of_the_request_is_kept(self) -> None:
        root = _root()
        self.assertEqual(shape_root(root, "ideas", "x").id, root.id)


class TestInitialContract(unittest.TestCase):
    """What the caller already fixed at intake is never re-classified."""

    def test_an_explicit_schema_is_explicit(self) -> None:
        self.assertEqual(initial_contract(schema_ids.EVIDENCE_BUNDLE, None),
                         (schema_ids.EVIDENCE_BUNDLE, "explicit"))

    def test_a_typed_payload_names_its_contract(self) -> None:
        self.assertEqual(initial_contract(None, schema_ids.DECISION_REQUEST),
                         (schema_ids.DECISION_REPORT, "explicit"))
        self.assertEqual(initial_contract(None, schema_ids.RESEARCH_REQUEST),
                         (schema_ids.EVIDENCE_BUNDLE, "explicit"))

    def test_nothing_chosen_leaves_the_intent_open_with_the_default_contract(self) -> None:
        self.assertEqual(initial_contract(None, None), (schema_ids.DECISION_REPORT, None))

    def test_an_unknown_payload_keeps_the_default(self) -> None:
        self.assertEqual(initial_contract(None, schema_ids.GOAL_REQUEST),
                         (schema_ids.DECISION_REPORT, "default"))


class TestDeclines(unittest.TestCase):
    """Plain refusals with the right observation type."""

    def test_change_is_a_plain_permission_type_decline(self) -> None:
        decline = decline_for("change")
        self.assertEqual((decline.code, decline.gap_type),
                         ("out_of_scope_write", GapType.PERMISSION))
        self.assertEqual(
            decline_limitation(decline),
            "out_of_scope_write: The V0 kernel is read-only; implementing or editing is not "
            "supported. You can ask it to decide what to implement or to find relevant "
            "evidence.")

    def test_out_of_domain_has_its_own_gap_type_that_is_not_a_build_opportunity(self) -> None:
        decline = decline_for("out_of_domain")
        self.assertEqual((decline.code, decline.gap_type),
                         ("out_of_domain", GapType.OUT_OF_DOMAIN))
        self.assertNotIn(GapType.OUT_OF_DOMAIN, BUILD_OPPORTUNITY_TYPES)
        self.assertNotIn(GapType.PERMISSION, BUILD_OPPORTUNITY_TYPES)
        gap = CapabilityGap(
            id="gap-0000000000000001", gap_key="k" * 16, gap_type=decline.gap_type, goal="weather",
            normalized_need="weather", request_kind="capability", input_schema="i.v1",
            output_schema="o.v1")
        self.assertFalse(is_build_opportunity(gap))

    def test_served_kinds_are_not_declined(self) -> None:
        for kind in ("decision", "evidence", "ideas"):
            self.assertIsNone(decline_for(kind))
        self.assertEqual(sorted(DECLINES), ["change", "out_of_domain"])

    def test_the_write_pre_check_names_why_writes_are_refused(self) -> None:
        self.assertIn("read-only by design", write_denial_reason(["read_repo"]))
        self.assertIn("no capability writes", write_denial_reason(["read_repo"]))
        self.assertIn("no registered capability", write_denial_reason(["read_repo", "write_repo"]))


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 23:00 [python-coder]: The write denial says the kernel is read-only by design, no
#   longer that the caller permissions forbid writes. (#KernelBootstrapV0/GROUND)
# - 2026-10-01 22:00 [python-coder]: `out_of_domain` is a separate gap type rather than a flag on
#   `unsupported`: the build-opportunity rule is a set of types, so a new type is excluded by
#   default. (#KernelBootstrapV0/INTENT)
# ====================================================================
