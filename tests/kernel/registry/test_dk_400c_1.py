"""
MODULE: tests.kernel.registry.test_dk_400c_1
GOAL: Prove the real capability registry admits host.decompose_goal under ADR-067 and never
    offers it to Jev or uses it as a no_match fallback (AC DK-400c-1).
BUSINESS CONTEXT: ADR-055: an entry enters the registry only with an admission record. The
    decompose operation is fixed work the kernel starts itself; it must not become a routing
    candidate or the host answer to an unrelated unsupported request.
ARCHITECTURE: load_registry on the real config/capability_registry.json, the production binding
    table, and the real filter_candidates and find_fallback. RED until the entry names ADR-067
    and the fallback excludes fixed operations.
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass
from pathlib import Path

from kernel.bootstrap import build_bindings
from kernel.config import load_kernel_config
from kernel.contracts import RequestKind, schema_ids
from kernel.contracts.work import RequestBody
from kernel.registry import filter_candidates
from kernel.registry.adapter import load_registry
from kernel.registry.fallback import find_fallback

REGISTRY = Path(__file__).resolve().parents[3] / "config" / "capability_registry.json"
CFG = load_kernel_config()


@dataclass
class Budgets:
    """Minimal BudgetUsageLike."""

    host_operations: int = 0


def _request(output_schema: str, payload_schema: str, payload: dict) -> RequestBody:
    return RequestBody(kind=RequestKind.CAPABILITY, goal="Reusable criteria",
                       payload_schema=payload_schema, payload=payload,
                       requested_output_schema=output_schema)


class TestDecomposeGoalEntry(unittest.TestCase):
    """The shipped registry entry."""

    def setUp(self) -> None:
        self.snapshot = load_registry(REGISTRY)
        self.bindings = build_bindings(self.snapshot)
        self.entry = next(d for d in self.snapshot.descriptors if d.id == "host.decompose_goal")

    def test_decompose_goal_registry_entry_admitted_and_fixed(self) -> None:
        # covers: DK-400c-1
        # angle: real_artifact
        """Admitted natively under ADR-067, fixed routing, and never offered or used as fallback."""
        self.assertEqual(self.entry.admission.kind, "native_registration")
        self.assertEqual(self.entry.admission.decision_ref, "ADR-067")
        self.assertEqual(self.entry.routing, "fixed")
        self.assertEqual(self.entry.operations, ["decompose_goal"])
        self.assertEqual(self.entry.accepts_schemas, [schema_ids.GOAL_DECOMPOSITION_REQUEST])
        self.assertEqual(self.entry.produces_schemas, [schema_ids.GOAL_DECOMPOSITION])
        self.assertEqual(self.entry.permissions_required, [])
        self.assertEqual(self.entry.side_effect_class, "none")
        self.assertTrue(self.bindings.has(self.entry.binding, self.entry.version))
        # A root goal is never offered it.
        root = _request(schema_ids.DECISION_REPORT, schema_ids.GOAL_REQUEST,
                        {"goal": "How should the storage format and the clustering work?"})
        report = filter_candidates(root, self.snapshot, self.bindings, ("read_repo",),
                                   Budgets(), CFG)
        self.assertNotIn("host.decompose_goal", report.eligible_ids)
        self.assertNotIn("host.decompose_goal", [d.id for d in report.semantic_candidates])
        # Not even a request shaped exactly like its own contract is offered to Jev.
        own = _request(schema_ids.GOAL_DECOMPOSITION, schema_ids.GOAL_DECOMPOSITION_REQUEST,
                       {"split_id": "dcp-0123456789abcdef", "subject_kind": "goal",
                        "subject_text": "A and B", "max_parts": 5})
        own_report = filter_candidates(own, self.snapshot, self.bindings, ("read_repo",),
                                       Budgets(), CFG, operation="decompose_goal")
        self.assertEqual([d.id for d in own_report.semantic_candidates], [])
        # It is never the no_match host fallback, even for a request that asks for its output.
        chosen, reason = find_fallback(self.snapshot, self.bindings, CFG, ("read_repo",),
                                       ("decision_kernel",), own, 10)
        self.assertNotEqual(getattr(chosen, "id", None), "host.decompose_goal", reason)
        # Control row: the exclusion is specific; a request host.synthesize produces still finds it.
        synth = RequestBody(kind=RequestKind.SYNTHESIS, goal="g",
                            payload_schema=schema_ids.SYNTHESIS_REQUEST,
                            payload={"operation": "synthesize_evidence", "question": "q"},
                            requested_output_schema=schema_ids.FINDINGS)
        control, why = find_fallback(self.snapshot, self.bindings, CFG, ("read_repo",),
                                     ("decision_kernel",), synth, 10)
        self.assertEqual(getattr(control, "id", None), "host.synthesize", why)
