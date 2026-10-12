"""
MODULE: tests.kernel.registry.test_eligibility
GOAL: Test the deterministic candidate filter and the trusted binding table.
BUSINESS CONTEXT: Semantic fit is not authorization: code must exclude disabled, unbound,
    mismatched, out-of-scope, forbidden and over-budget capabilities before Jev sees any
    candidate, and an existing-but-unavailable capability must never read as a gap.
ARCHITECTURE: Snapshots are built in memory from descriptor fixtures; bindings use
    ScriptedExecutor factories.
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass

from kernel.config import load_kernel_config
from kernel.contracts.capability import RegistrySnapshot
from kernel.contracts.enums import RequestKind
from kernel.registry import BindingTable, BindingUnavailable, filter_candidates
from tests.kernel.helpers import ScriptedExecutor, make_descriptor, make_request_body, make_scope

CFG = load_kernel_config()


@dataclass
class Budgets:
    """Minimal BudgetUsageLike."""

    host_operations: int = 0


def _snapshot(*descriptors) -> RegistrySnapshot:
    return RegistrySnapshot(registry_id="t", registry_version=1, content_hash="h" * 8,
                            source_path="t", descriptors=list(descriptors))


def _bindings(*descriptors) -> BindingTable:
    table = BindingTable()
    for d in descriptors:
        table.register(d.binding, d.version, ScriptedExecutor)
    return table


def _run(descriptors, request=None, permissions=("read_repo",), budgets=None, **kw):
    request = request or make_request_body()
    return filter_candidates(request, _snapshot(*descriptors), _bindings(*descriptors),
                             permissions, budgets or Budgets(), CFG, **kw)


def _codes(report) -> dict[str, str]:
    return {e.capability_id: e.reason_code for e in report.excluded}


class TestBindings(unittest.TestCase):
    """Trusted binding table."""

    def test_resolve_builds_executor_and_unknown_is_unavailable(self) -> None:
        table = BindingTable()
        table.register("k", "1.0.0", ScriptedExecutor)
        self.assertIsInstance(table.resolve("k", "1.0.0"), ScriptedExecutor)
        self.assertTrue(table.has("k", "1.0.0"))
        self.assertFalse(table.has("k", "2.0.0"))
        with self.assertRaises(BindingUnavailable) as raised:
            table.resolve("k", "2.0.0")
        self.assertEqual((raised.exception.key, raised.exception.version), ("k", "2.0.0"))
        self.assertEqual(table.keys(), [("k", "1.0.0")])

    def test_each_resolve_returns_a_fresh_instance(self) -> None:
        table = BindingTable()
        table.register("k", "1.0.0", ScriptedExecutor)
        self.assertIsNot(table.resolve("k", "1.0.0"), table.resolve("k", "1.0.0"))


class TestExclusions(unittest.TestCase):
    """One reason code per failing check, in design order."""

    def test_disabled_and_unavailable(self) -> None:
        off = make_descriptor(id="a.off", enabled=False)
        down = make_descriptor(id="b.down", availability={"status": "unavailable",
                                                          "reason": "no key"})
        report = _run([off, down])
        self.assertEqual(_codes(report), {"a.off": "disabled", "b.down": "unavailable:no key"})
        self.assertEqual(report.outcome_hint, "unavailable")

    def test_binding_missing(self) -> None:
        d = make_descriptor()
        report = filter_candidates(make_request_body(), _snapshot(d), BindingTable(),
                                   ["read_repo"], Budgets(), CFG)
        self.assertEqual(_codes(report), {d.id: "binding_missing"})
        self.assertEqual(report.outcome_hint, "unavailable")

    def test_shape_mismatches_give_no_match(self) -> None:
        kind = make_descriptor(id="k", request_kinds=["options"])
        payload = make_descriptor(id="p", accepts_schemas=["leafcutter.goal_request.v1"])
        output = make_descriptor(id="o", produces_schemas=["leafcutter.findings.v1"])
        report = _run([kind, payload, output])
        self.assertEqual(_codes(report), {"k": "kind_mismatch", "p": "payload_schema_mismatch",
                                          "o": "output_schema_mismatch"})
        self.assertEqual((report.outcome_hint, report.matched_ids), ("no_match", []))

    def test_operation_mismatch_is_kind_mismatch(self) -> None:
        d = make_descriptor(operations=["retrieve"])
        self.assertEqual(_run([d], operation="retrieve").eligible_ids, [d.id])
        self.assertEqual(_codes(_run([d], operation="other")), {d.id: "kind_mismatch"})

    def test_scope_mismatch_is_no_match_not_unavailable(self) -> None:
        d = make_descriptor(components=["decision_kernel"])
        scope = make_scope(_root(), component_ids=["other"])
        report = _run([d], scope=scope)
        self.assertEqual(_codes(report), {d.id: "scope_mismatch"})
        self.assertEqual(report.outcome_hint, "no_match")
        ok = _run([d], scope=make_scope(_root(), component_ids=["decision_kernel"]))
        self.assertEqual(ok.eligible_ids, [d.id])

    def test_unscoped_descriptor_matches_any_scope(self) -> None:
        d = make_descriptor()
        self.assertEqual(_run([d], scope=make_scope(_root(), component_ids=["x"])).eligible_ids,
                         [d.id])

    def test_permission_denied(self) -> None:
        d = make_descriptor(permissions_required=["read_repo", "web_fetch"])
        report = _run([d], permissions=["read_repo"])
        self.assertEqual(_codes(report), {d.id: "permission_denied"})
        self.assertEqual(report.outcome_hint, "unavailable")

    def test_side_effects_beyond_mvp_forbidden(self) -> None:
        for forbidden in ("repo_write", "external_write"):
            d = make_descriptor(side_effect_class=forbidden)
            with self.subTest(side_effect=forbidden):
                self.assertEqual(_codes(_run([d])), {d.id: "side_effect_forbidden"})
        for allowed in ("none", "read_only", "run_artifacts"):
            d = make_descriptor(side_effect_class=allowed)
            with self.subTest(side_effect=allowed):
                self.assertEqual(_run([d]).eligible_ids, [d.id])

    def test_host_budget_exhaustion_uses_config_limit(self) -> None:
        d = make_descriptor(id="host.synthesize", execution_mode="host_handoff")
        limit = CFG.limits.max_host_operations
        self.assertEqual(_run([d], budgets=Budgets(limit - 1)).eligible_ids, [d.id])
        report = _run([d], budgets=Budgets(limit))
        self.assertEqual(_codes(report), {d.id: "budget_exhausted"})
        self.assertEqual(report.outcome_hint, "unavailable")

    def test_first_failing_check_wins(self) -> None:
        d = make_descriptor(enabled=False, permissions_required=["nope"])
        self.assertEqual(_codes(_run([d])), {d.id: "disabled"})


def _root():
    import tempfile
    return tempfile.gettempdir()


class TestOutcomeHints(unittest.TestCase):
    """selected versus needs_semantic, deterministically."""

    def test_single_non_capability_candidate_selected_without_jev(self) -> None:
        d = make_descriptor()
        report = _run([d])
        self.assertEqual((report.outcome_hint, report.selected_id), ("selected", d.id))

    def test_capability_kind_always_needs_semantic_for_semantic_candidates(self) -> None:
        d = make_descriptor(id="decision", routing="semantic", request_kinds=["capability"],
                            accepts_schemas=["leafcutter.goal_request.v1"],
                            produces_schemas=["leafcutter.evidence_bundle.v1"])
        request = make_request_body(RequestKind.CAPABILITY, "leafcutter.goal_request.v1",
                                    payload={"goal": "Decide"})
        report = _run([d], request)
        self.assertEqual(report.outcome_hint, "needs_semantic")
        self.assertEqual([c.id for c in report.semantic_candidates], ["decision"])

    def test_two_semantic_candidates_need_jev(self) -> None:
        a = make_descriptor(id="a", routing="semantic")
        b = make_descriptor(id="b", routing="semantic")
        report = _run([a, b])
        self.assertEqual(report.outcome_hint, "needs_semantic")
        self.assertIsNone(report.selected_id)

    def test_only_fixed_candidates_pick_lowest_id_and_note_the_tie(self) -> None:
        b = make_descriptor(id="b", routing="fixed")
        a = make_descriptor(id="a", routing="fixed")
        report = _run([b, a])
        self.assertEqual((report.outcome_hint, report.selected_id), ("selected", "a"))
        self.assertIn("tie", report.tie_note)
        self.assertEqual(report.semantic_candidates, [])

    def test_fixed_candidates_are_never_offered_to_jev(self) -> None:
        fixed = make_descriptor(id="f", routing="fixed")
        sem1 = make_descriptor(id="s1", routing="semantic")
        sem2 = make_descriptor(id="s2", routing="semantic")
        report = _run([fixed, sem1, sem2])
        self.assertEqual([c.id for c in report.semantic_candidates], ["s1", "s2"])

    def test_empty_registry_is_no_match(self) -> None:
        report = _run([])
        self.assertEqual((report.outcome_hint, report.eligible, report.excluded),
                         ("no_match", [], []))

    def test_report_is_deterministic_regardless_of_input_order(self) -> None:
        ds = [make_descriptor(id=i, enabled=(i != "b")) for i in ("c", "b", "a")]
        first = _run(ds).model_dump()
        second = _run(list(reversed(ds))).model_dump()
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:00 [python-coder]: Budget limits are read from the loaded config, never
#   hard-coded in tests, so a config change cannot silently invalidate the boundary case.
#   (#KernelBootstrapV0/P1)
# ====================================================================
