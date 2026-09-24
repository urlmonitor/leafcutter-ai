"""Behavioral contracts for the local background lane's deterministic planner."""

import copy
import unittest
from scripts.background_worker.planning import plan_features


def record(id, level, parent=None, size=None, priority="low", **values):
    return dict(
        id=id,
        level=level,
        parent=parent,
        status="active",
        readiness="approved",
        req_status="approved",
        work_status="todo",
        criteria="Given input When run Then checked",
        estimated_complexity=size,
        priority=priority,
        depends_on=[parent] if parent else [],
        **values,
    )


def tree():
    return {
        r["id"]: r
        for r in [
            record("TEST-100", "L0"),
            record("TEST-100a", "L1", "TEST-100"),
            record("TEST-100a-1", "L2", "TEST-100a", "S"),
            record("TEST-100a-2", "L2", "TEST-100a", "M"),
        ]
    }


class PlanningTests(unittest.TestCase):
    # covers: ACD-1300f-1 ACD-1300f-2
    def test_structural_parents_do_not_deadlock_and_real_edges_order(self):
        records = tree()
        records["TEST-100a-1"]["depends_on"].append("TEST-100a-2")
        result = plan_features(records, target_completed=set())
        self.assertEqual(result.ready[0].execution_order, ["TEST-100a-2", "TEST-100a-1"])
        self.assertEqual(set(result.ready[0].source_context["obligations"]), set(records))

    # covers: ACD-1300a-1 ACD-1300f-1 ACD-1300f-1-i
    def test_inherited_priority_approval_and_size_cannot_be_hidden(self):
        records = tree()
        records["TEST-100a-1"]["priority"] = "high"
        records["TEST-100a-1-i"] = record("TEST-100a-1-i", "L3", "TEST-100a-1", "S")
        result = plan_features(records, target_completed=set())
        self.assertEqual(result.ready[0].effective_priority, "high")
        self.assertIn("TEST-100a-1", result.ready[0].source_context["obligations"])
        for field, value in [("readiness", "draft"), ("estimated_complexity", "L")]:
            with self.subTest(field=field):
                changed = copy.deepcopy(records)
                changed["TEST-100a-1"][field] = value
                self.assertFalse(plan_features(changed, target_completed=set()).ready)

    # covers: ACD-1300a-2 ACD-1300f-2
    def test_external_done_claim_requires_target_evidence_and_expects_edges(self):
        records = tree()
        external = record("TEST-200", "L0")
        external["work_status"] = "done"
        records[external["id"]] = external
        records["TEST-100a-1"]["expects_from"] = [{"ac_id": "TEST-200", "contract": "ready"}]
        self.assertFalse(plan_features(records, target_completed=set()).ready)
        self.assertTrue(plan_features(records, target_completed={"TEST-200"}).ready)

    # covers: ACD-1300f-3
    def test_missing_parent_dependency_cycle_and_invalid_size_exclude_whole_feature(self):
        for mode in ["missing", "cycle", "size", "parent"]:
            records = tree()
            if mode == "missing":
                records["TEST-100a-1"]["depends_on"].append("TEST-999")
            if mode == "cycle":
                records["TEST-100a-1"]["depends_on"].append("TEST-100a-2")
                records["TEST-100a-2"]["depends_on"].append("TEST-100a-1")
            if mode == "size":
                records["TEST-100a-2"]["estimated_complexity"] = "XS"
            if mode == "parent":
                records["TEST-100a-1"]["parent"] = "TEST-999"
            with self.subTest(mode=mode):
                result = plan_features(records, target_completed=set())
                self.assertFalse(result.ready)
                self.assertTrue(result.excluded)

    # covers: ACD-1300e-3 ACD-1300a-3
    def test_scope_digest_ignores_priority_but_tracks_requirements_and_adr_contents(self):
        records = tree()
        records["TEST-100a"]["doc_links"] = [{"path": "docs/ADR-001.md"}]
        first = plan_features(
            records, target_completed=set(), adr_contents={"docs/ADR-001.md": "first"}
        ).ready[0]
        records["TEST-100a"]["priority"] = "critical"
        second = plan_features(
            records, target_completed=set(), adr_contents={"docs/ADR-001.md": "first"}
        ).ready[0]
        self.assertEqual(first.scope_digest, second.scope_digest)
        records["TEST-100a-1"]["criteria"] += " changed"
        third = plan_features(
            records, target_completed=set(), adr_contents={"docs/ADR-001.md": "first"}
        ).ready[0]
        self.assertNotEqual(first.scope_digest, third.scope_digest)
        fourth = plan_features(
            records, target_completed=set(), adr_contents={"docs/ADR-001.md": "second"}
        ).ready[0]
        self.assertNotEqual(third.scope_digest, fourth.scope_digest)

    # covers: ACD-1300a-2 ACD-1300a-3
    def test_reserved_features_stay_reserved_and_lowest_priority_stable_order(self):
        records = tree()
        for suffix, priority in [("b", "medium"), ("c", "low")]:
            r = record("TEST-100" + suffix, "L1", "TEST-100", priority=priority)
            records[r["id"]] = r
            r = record("TEST-100" + suffix + "-1", "L2", "TEST-100" + suffix, "S")
            records[r["id"]] = r
        result = plan_features(records, target_completed=set())
        self.assertEqual(
            [p.feature_id for p in result.ready], ["TEST-100a", "TEST-100c", "TEST-100b"]
        )
        result = plan_features(records, target_completed=set(), reserved_features={"TEST-100a"})
        self.assertEqual([p.feature_id for p in result.ready], ["TEST-100c", "TEST-100b"])

    # covers: ACD-1300f-1
    def test_completed_leaves_remain_context_and_parents_propagate_dependencies(self):
        records = tree()
        records["TEST-100a-1-i"] = record("TEST-100a-1-i", "L3", "TEST-100a-1", "S")
        records["TEST-100a-1"]["depends_on"].append("TEST-100a-2")
        result = plan_features(records, target_completed={"TEST-100a-2"})
        self.assertEqual(result.ready[0].ac_ids, ["TEST-100a-1-i"])
        self.assertIn("TEST-100a-2", result.ready[0].source_context["completed_context_ids"])
        self.assertIn("TEST-100a-1", result.ready[0].source_context["obligations"])

    # covers: ACD-1300f-3
    def test_skipped_hierarchy_level_is_not_an_easy_subset(self):
        records = tree()
        records["TEST-100a-9-i"] = record("TEST-100a-9-i", "L3", "TEST-100a", "S")
        result = plan_features(records, target_completed=set())
        self.assertFalse(result.ready)

    # covers: ACD-1300f-3
    def test_cycles_across_features_report_cycle_even_if_target_claims_done(self):
        records = tree()
        records["TEST-100b"] = record("TEST-100b", "L1", "TEST-100")
        records["TEST-100b-1"] = record("TEST-100b-1", "L2", "TEST-100b", "S")
        records["TEST-100a-1"]["depends_on"].append("TEST-100b-1")
        records["TEST-100b-1"]["depends_on"].append("TEST-100a-1")
        result = plan_features(records, target_completed={"TEST-100b-1"})
        self.assertFalse(result.ready)
        self.assertIn("cycle", str(result.excluded))

    # covers: ACD-1300f-2 ACD-1300e-3
    def test_satisfied_external_dependency_context_and_scope_are_retained(self):
        records = tree()
        records["TEST-200"] = record("TEST-200", "L0")
        records["TEST-100a-1"]["depends_on"].append("TEST-200")
        first = plan_features(records, target_completed={"TEST-200"}).ready[0]
        self.assertEqual(first.source_context["external_edges"][0]["from"], "TEST-200")
        self.assertIn("TEST-200", first.source_context["dependency_context"])
        records["TEST-200"]["criteria"] += " changed"
        second = plan_features(records, target_completed={"TEST-200"}).ready[0]
        self.assertNotEqual(first.scope_digest, second.scope_digest)

    # covers: ACD-1300f-3
    def test_declared_missing_or_misparented_child_poison_whole_feature(self):
        for child in ["TEST-100a-999", "TEST-100b-1"]:
            records = tree()
            records["TEST-100a"]["covered_by"] = [child]
            records["TEST-100b"] = record("TEST-100b", "L1", "TEST-100")
            records["TEST-100b-1"] = record("TEST-100b-1", "L2", "TEST-100b", "S")
            result = plan_features(records, target_completed=set())
            self.assertNotIn("TEST-100a", [p.feature_id for p in result.ready])
            self.assertIn("TEST-100a", result.excluded)

    # covers: ACD-1300g-1 ACD-1300e-3
    def test_reference_content_is_inline_with_the_exact_revision(self):
        records = tree()
        records["TEST-100a"]["doc_links"] = ["docs/ADR-001.md"]
        plan = plan_features(
            records, target_completed=set(), adr_contents={"docs/ADR-001.md": "approved decision"}
        ).ready[0]
        self.assertEqual(
            plan.source_context["reference_contents"]["docs/ADR-001.md"], "approved decision"
        )

    # covers: ACD-1300e-3 ACD-1300g-1
    def test_missing_required_reference_excludes_only_its_feature(self):
        records = tree()
        records["TEST-100a"]["doc_links"] = [{"path": "docs/missing.md", "status": "exists"}]
        records["TEST-100b"] = record("TEST-100b", "L1", "TEST-100")
        records["TEST-100b-1"] = record("TEST-100b-1", "L2", "TEST-100b", "S")
        result = plan_features(
            records, target_completed=set(), adr_contents={"docs/missing.md": None}
        )
        self.assertEqual([plan.feature_id for plan in result.ready], ["TEST-100b"])
        self.assertIn("docs/missing.md", str(result.excluded["TEST-100a"]))

    # covers: ACD-1300f-1 ACD-1300f-3
    def test_real_retired_child_is_not_missing_required_work(self):
        records = tree()
        records["TEST-100a"]["covered_by"] = ["TEST-100a-1", "TEST-100a-2", "TEST-100a-3"]
        records["TEST-100a-3"] = record("TEST-100a-3", "L2", "TEST-100a", "L")
        records["TEST-100a-3"]["status"] = "deprecated"
        result = plan_features(records, target_completed=set())
        self.assertEqual(result.ready[0].ac_ids, ["TEST-100a-1", "TEST-100a-2"])
