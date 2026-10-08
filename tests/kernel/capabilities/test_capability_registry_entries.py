"""
MODULE: tests.kernel.capabilities.test_capability_registry_entries
GOAL: Test the seven committed registry entries: admission, routing, schemas, binding keys and
    how the eligibility filter routes the requests the native graphs emit.
BUSINESS CONTEXT: The registry is the only place a capability becomes routable; wrong schemas or
    routing would send a retrieval child to the host or expose a fixed capability to Jev
    (Rev 3 section 6, design part 2).
ARCHITECTURE: Loads the real config/capability_registry.json, registers the real P5 executors
    and ScriptedExecutor stand-ins for the host capabilities in a BindingTable, and runs the real
    filter_candidates over the requests built by the graphs.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from kernel.capabilities.base import CapabilityExecutor
from kernel.capabilities.decision import DecisionExecutor
from kernel.capabilities.research import ResearchExecutor
from kernel.capabilities.retrieval import RepositoryRetrievalExecutor
from kernel.config import load_kernel_config
from kernel.contracts import schema_ids
from kernel.contracts.enums import ExecutionMode, RequestKind
from kernel.registry.adapter import load_registry
from kernel.registry.bindings import BindingTable
from kernel.registry.eligibility import filter_candidates
from tests.kernel.helpers import ScriptedExecutor, load_json, make_request_body

CONFIG = Path(__file__).resolve().parents[3] / "config"
HOST_IDS = ["host.formulate_question", "host.generate_options", "host.query_build", "host.research",
            "host.synthesize"]


def _table() -> BindingTable:
    """Bind the native executors and stand-ins for the host capabilities (as P7/P8 will)."""
    table = BindingTable()
    table.register("decision", "1.0.0", DecisionExecutor)
    table.register("research", "1.0.0", ResearchExecutor)
    table.register("retrieve.repository", "1.0.0", RepositoryRetrievalExecutor)
    table.register("knowledge.activate_query", "1.0.0", ScriptedExecutor)
    for host_id in HOST_IDS:
        table.register(host_id, "1.0.0", ScriptedExecutor)
    return table


class TestEntries(unittest.TestCase):
    """Static properties of the committed entries."""

    def setUp(self) -> None:
        self.snapshot = load_registry(CONFIG / "capability_registry.json")
        self.by_id = {d.id: d for d in self.snapshot.descriptors}

    def test_every_entry_is_a_native_registration_of_this_ticket(self) -> None:
        for d in self.snapshot.descriptors:
            self.assertEqual(d.admission.kind, "native_registration")
            expected = "TICKET-20261001-KM-500b-3" if d.id in {"host.query_build", "knowledge.activate_query"} else "TICKET-20260930-KernelBootstrapV0"
            self.assertEqual(d.admission.decision_ref, expected)
            self.assertEqual(d.version, "1.0.0")
            self.assertEqual(d.binding, d.id)

    def test_execution_modes(self) -> None:
        for d in self.snapshot.descriptors:
            expected = ExecutionMode.HOST_HANDOFF if d.id.startswith("host.") \
                else ExecutionMode.NATIVE
            self.assertEqual(d.execution_mode, expected, d.id)

    def test_only_decision_and_research_are_offered_to_jev(self) -> None:
        semantic = sorted(d.id for d in self.snapshot.descriptors if d.routing == "semantic")
        self.assertEqual(semantic, ["decision", "research"])

    def test_schemas_per_capability(self) -> None:
        expected = {
            "decision": ([schema_ids.GOAL_REQUEST, schema_ids.DECISION_REQUEST],
                         [schema_ids.DECISION_REPORT]),
            "research": ([schema_ids.GOAL_REQUEST, schema_ids.RESEARCH_REQUEST],
                         [schema_ids.EVIDENCE_BUNDLE]),
            "retrieve.repository": ([schema_ids.RETRIEVAL_REQUEST], [schema_ids.EVIDENCE_BUNDLE]),
            "host.generate_options": ([schema_ids.OPTIONS_REQUEST], [schema_ids.OPTIONS]),
            "host.synthesize": ([schema_ids.SYNTHESIS_REQUEST], [schema_ids.FINDINGS]),
            "host.research": ([schema_ids.RETRIEVAL_REQUEST], [schema_ids.EVIDENCE_BUNDLE]),
            "host.formulate_question": ([schema_ids.HUMAN_QUESTION_REQUEST],
                                        [schema_ids.HUMAN_QUESTION_REQUEST]),
        }
        for cap_id, (accepts, produces) in expected.items():
            d = self.by_id[cap_id]
            self.assertEqual((d.accepts_schemas, d.produces_schemas), (accepts, produces), cap_id)

    def test_executors_satisfy_the_port_and_bind_at_the_registry_version(self) -> None:
        table = _table()
        for d in self.snapshot.descriptors:
            self.assertTrue(table.has(d.binding, d.version), d.id)
        for cap_id in ("decision", "research", "retrieve.repository"):
            self.assertIsInstance(table.resolve(cap_id, "1.0.0"), CapabilityExecutor)


class TestRouting(unittest.TestCase):
    """The eligibility filter routes the requests the graphs emit to the right capability."""

    def setUp(self) -> None:
        self.snapshot = load_registry(CONFIG / "capability_registry.json")
        self.table = _table()
        self.cfg = load_kernel_config()

    def route(self, body, operation: str | None = None):
        return filter_candidates(body, self.snapshot, self.table, ["read_repo"],
                                 SimpleNamespace(host_operations=0), self.cfg,
                                 operation=operation)

    def test_root_goal_goes_to_jev_between_decision_and_research_only(self) -> None:
        body = make_request_body(RequestKind.CAPABILITY, schema_ids.GOAL_REQUEST,
                                 schema_ids.DECISION_REPORT,
                                 load_json("valid/leafcutter.goal_request.v1/valid_basic.json"))
        report = self.route(body)
        self.assertEqual(report.outcome_hint, "needs_semantic")
        self.assertEqual([d.id for d in report.semantic_candidates], ["decision"])

    def test_research_request_child_binds_to_research_deterministically(self) -> None:
        payload = load_json("valid/leafcutter.research_request.v1/valid_basic.json")
        body = make_request_body(RequestKind.EVIDENCE, schema_ids.RESEARCH_REQUEST,
                                 schema_ids.EVIDENCE_BUNDLE, payload)
        report = self.route(body)
        self.assertEqual((report.outcome_hint, report.selected_id), ("selected", "research"))

    def test_retrieval_child_binds_by_operation(self) -> None:
        body = make_request_body()
        self.assertEqual(self.route(body, "retrieve").selected_id, "retrieve.repository")
        self.assertEqual(self.route(body, "bounded_research").selected_id, "host.research")

    def test_options_synthesis_and_human_formulation_bind_to_host_capabilities(self) -> None:
        cases = [
            (RequestKind.OPTIONS, schema_ids.OPTIONS_REQUEST, schema_ids.OPTIONS,
             "host.generate_options"),
            (RequestKind.SYNTHESIS, schema_ids.SYNTHESIS_REQUEST, schema_ids.FINDINGS,
             "host.synthesize"),
            (RequestKind.HUMAN, schema_ids.HUMAN_QUESTION_REQUEST,
             schema_ids.HUMAN_QUESTION_REQUEST, "host.formulate_question"),
        ]
        for kind, schema, output, expected in cases:
            payload = load_json(f"valid/{schema}/valid_basic.json")
            report = self.route(make_request_body(kind, schema, output, payload))
            self.assertEqual(report.selected_id, expected, schema)

    def test_human_question_with_answer_output_is_not_a_host_capability(self) -> None:
        payload = load_json("valid/leafcutter.human_question_request.v1/valid_basic.json")
        body = make_request_body(RequestKind.HUMAN, schema_ids.HUMAN_QUESTION_REQUEST,
                                 schema_ids.HUMAN_ANSWER, payload)
        self.assertEqual(self.route(body).outcome_hint, "no_match")


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:00 [python-coder]: A human question whose requested output is human_answer
#   matches no capability on purpose: humans are reached through interactions, and only an
#   explicit formulate_question request reaches host.formulate_question. (#KernelBootstrapV0/P5)
# ====================================================================
