"""Regression for unavailable contracts hidden by artifact-eval baseline subtraction.

GOAL: A sandbox can check every declared handoff; missing dependencies never earn a pass.
BUSINESS CONTEXT: Flow-author evaluation must enforce the same PT fields reviewed in Atlas.
ARCHITECTURE: Real sandbox producer, real generator/validator and real artifact scorer; no provider.
"""
from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from unit_tests.product_truth._flow_io_fixture import ROOT, write_json
from unit_tests.product_truth._flow_eval_fixture import FLOW_REL, RECEIPT_REL, GAP_REL, make_eval_source, regenerate, target_score

sys.path.insert(0, str(ROOT / "scripts/evals"))


class TestContractEvalSandbox(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="contract-eval-proof-")
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name)
        self.source = self.area / "source"
        self.source.mkdir()
        self.ev = importlib.import_module("run_agent_eval")
        self.sequence = 0
        for function in ("invoke_agent_writer", "run_llm_judge", "write_results"):
            guard = patch.object(self.ev, function, side_effect=AssertionError("Offline regression must not invoke a provider or stamp eval results"))
            guard.start()
            self.addCleanup(guard.stop)

    def sandbox(self, source=None):
        self.sequence += 1
        destination = self.area / f"sandbox-{self.sequence}"
        with patch.object(self.ev.tempfile, "mkdtemp", return_value=str(destination)):
            result = self.ev.make_sandbox(source or self.source, ["docs/product-truth"])
        self.assertEqual(result.resolve(), destination.resolve())
        return result

    def test_eval_sandbox_copies_declared_dependencies_without_private_neighbors(self):
        # covers: UXP-300-1
        # angle: real_artifact
        make_eval_source(self.source, runtime=True)
        sandbox = self.sandbox()
        for relative in ("kernel/contracts/task.py", "knowledge/contracts.py", "config/request.schema.json", RECEIPT_REL, GAP_REL):
            with self.subTest(relative=relative):
                self.assertEqual((sandbox / relative).read_bytes(), (self.source / relative).read_bytes())
        for relative in (".env", "config/unrelated-private.json", "reports/unrelated-private.json", "kernel/.env", "knowledge/cache/private.txt"):
            self.assertFalse((sandbox / relative).exists(), relative)
        regenerate(self.ev, sandbox)
        baseline = self.ev.validator_errors(sandbox)
        self.assertEqual(baseline, set())
        self.assertTrue(target_score(self.ev, sandbox, set())["passed"])

    def test_runtime_field_typo_cannot_disappear_into_the_baseline(self):
        # covers: UXP-300-1
        # angle: discrimination
        make_eval_source(self.source, runtime=True)
        sandbox = self.sandbox()
        regenerate(self.ev, sandbox)
        before = self.ev.validator_errors(sandbox)
        self.assertTrue(target_score(self.ev, sandbox, set())["passed"])
        path = self.ev._store_dir(sandbox) / FLOW_REL
        flow = json.loads(path.read_text(encoding="utf-8"))
        flow["steps"][0]["io_contracts"]["consumes"][0]["fields"][0]["path"] = "/workspace_id_typo"
        write_json(path, flow)
        regenerate(self.ev, sandbox)
        after = self.ev.validator_errors(sandbox)
        score = target_score(self.ev, sandbox, after - before)
        self.assertFalse(score["passed"], score)
        self.assertTrue(any("workspace_id_typo" in item["detail"] for item in score["assertions"]), score)

    def test_missing_target_receipt_fails_even_when_the_same_error_is_in_baseline(self):
        # covers: UXP-300-2
        # angle: failure
        make_eval_source(self.source)
        sandbox = self.sandbox()
        receipt = sandbox / RECEIPT_REL
        if receipt.exists():
            receipt.unlink()
        regenerate(self.ev, sandbox)
        before = self.ev.validator_errors(sandbox)
        self.assertTrue(before)
        self.assertEqual(self.ev.validator_errors(sandbox) - before, set())
        score = target_score(self.ev, sandbox, set())
        self.assertFalse(score["passed"], score)
        self.assertTrue(any("receipt" in item["detail"].lower() for item in score["assertions"]), score)

    def test_valid_target_is_not_failed_by_unrelated_existing_contract_errors(self):
        # covers: UXP-300-3
        # angle: boundary
        make_eval_source(self.source)
        sandbox = self.sandbox()
        regenerate(self.ev, sandbox)
        store = self.ev._store_dir(sandbox)
        unrelated = json.loads((store / FLOW_REL).read_text(encoding="utf-8"))
        unrelated["id"] = "fixture/unrelated"
        unrelated["steps"][0].pop("io_contracts")
        write_json(store / "flows/fixture/unrelated.flow.json", unrelated)
        before = self.ev.validator_errors(sandbox)
        self.assertTrue(before)
        score = target_score(self.ev, sandbox, self.ev.validator_errors(sandbox) - before)
        self.assertTrue(score["passed"], score)

    def test_real_runtime_marker_keeps_scoped_required_handoffs_enforced(self):
        # covers: UXP-300-3
        # angle: real_artifact
        sandbox = self.sandbox(ROOT)
        marker = "integrations/retrieval_needs_llm.py"
        self.assertEqual((sandbox / marker).read_bytes(), (ROOT / marker).read_bytes())
        relative = "flows/leafcutter/retrieval-needs-interpretation.flow.json"
        path = self.ev._store_dir(sandbox) / relative
        flow = json.loads(path.read_text(encoding="utf-8"))
        flow["steps"][0]["io_contracts"] = {"missing_bindings": [{
            "name": "required_request", "direction": "both", "reason": "A gap cannot replace this implemented handoff.",
            "source": "docs/product-truth/" + relative,
        }]}
        write_json(path, flow)
        regenerate(self.ev, sandbox)
        score = target_score(self.ev, sandbox, set(), relative)
        self.assertFalse(score["passed"], score)
        self.assertTrue(any("required wire handoff models missing" in item["detail"] for item in score["assertions"]), score)

    def test_missing_declared_dependency_refuses_sandbox_before_scoring(self):
        # covers: UXP-300-2
        # angle: failure
        make_eval_source(self.source)
        (self.source / RECEIPT_REL).unlink()
        with self.assertRaises(self.ev.EvalDataError):
            self.sandbox()

    def test_validator_crash_without_fail_lines_is_not_an_empty_error_set(self):
        # covers: UXP-700c-3-iii
        # angle: failure
        make_eval_source(self.source)
        sandbox = self.sandbox()
        # Remove a real mandatory module: the real CLI exits nonzero with an
        # import traceback rather than its normal FAIL-prefixed diagnostics.
        (self.ev._store_dir(sandbox) / "scripts/product_truth_contracts.py").unlink()
        with self.assertRaises(self.ev.EvalDataError):
            self.ev.validator_errors(sandbox)

    def test_selected_contract_flow_id_must_exist(self):
        # covers: UXP-300-3
        # angle: boundary
        store = make_eval_source(self.source)
        flow = json.loads((store / FLOW_REL).read_text(encoding="utf-8"))
        sys.path.insert(0, str(ROOT / "docs/product-truth/scripts"))
        checker = importlib.import_module("product_truth_contracts")
        report = checker.check_contracts({flow["id"]: flow}, self.source,
                                        check_presentation=False, only_flow_ids={"fixture/missing"})
        self.assertTrue(report["errors"], report)
        self.assertTrue(any("fixture/missing" in item for item in report["errors"]), report)

    def test_duplicate_flow_id_cannot_substitute_a_different_target(self):
        # covers: UXP-300-3
        # angle: discrimination
        make_eval_source(self.source)
        sandbox = self.sandbox()
        store = self.ev._store_dir(sandbox)
        target = json.loads((store / FLOW_REL).read_text(encoding="utf-8"))
        write_json(store / "flows/fixture/duplicate.flow.json", target)
        # An ambiguous registry is unavailable for evaluation, so scoring must
        # stop instead of selecting whichever duplicate happened to load last.
        with self.assertRaises(self.ev.EvalDataError):
            target_score(self.ev, sandbox, set())

    def test_dependency_path_cannot_escape_the_repository(self):
        # covers: UXP-300-1
        # angle: boundary
        store = make_eval_source(self.source)
        outside = self.area / "outside.json"
        write_json(outside, {"type": "object"})
        path = store / FLOW_REL
        flow = json.loads(path.read_text(encoding="utf-8"))
        flow["contract_definitions"]["request"]["schema"] = "../outside.json"
        write_json(path, flow)
        with self.assertRaises(self.ev.EvalDataError):
            self.sandbox()

    def test_declared_dependency_symlink_cannot_escape_its_repository(self):
        # covers: UXP-300-1
        # angle: boundary
        make_eval_source(self.source)
        receipt = self.source / RECEIPT_REL
        outside = self.area / "outside-receipt.json"
        outside.write_bytes(receipt.read_bytes())
        receipt.unlink()
        try:
            receipt.symlink_to(outside)
        except OSError as exc:
            self.skipTest(f"Host cannot create the symlink needed by this boundary test: {exc}")
        with self.assertRaises(self.ev.EvalDataError):
            self.sandbox()


class TestEvalInvocationFailureScoring(unittest.TestCase):
    axes = ["needs_flow", "needs_mock_data", "needs_mockup"]

    def setUp(self):
        self.ev = importlib.import_module("run_agent_eval")
        self.config = {"label_axes": self.axes, "input_field": "request", "expected_field": "expected",
                       "response_label_field": "expected", "derive_outcome": True, "model": "unused"}
        guard = patch.object(self.ev, "write_results", side_effect=AssertionError("No live freshness stamp in unit tests"))
        guard.start()
        self.addCleanup(guard.stop)

    def row(self, identifier, needs_flow=False):
        return {"id": identifier, "request": "Fixture request", "expected": {
            "needs_flow": needs_flow, "needs_mock_data": False, "needs_mockup": False,
        }}

    def invoke(self, rows, responses):
        with patch.object(self.ev, "_dispatch", side_effect=responses) as boundary:
            results = self.ev.run_label_eval(rows, "Fixture prompt", self.config, self_test=False, timeout=1, backend="unused")
        self.assertEqual(boundary.call_count, len(rows))
        return results

    def test_failed_invocation_cannot_pass_an_all_false_gold_row(self):
        # covers: TQ-200a-2-i
        # angle: discrimination
        rows = [self.row("missing-provider")]
        for message in ("Provider unavailable", ""):
            with self.subTest(message=message):
                results = self.invoke(rows, [self.ev.ModelInvocationError(message)])
                self.assertFalse(results[0]["score"]["passed"], results)
                self.assertTrue(results[0]["parse_error"])
                if message:
                    self.assertIn(message, results[0]["parse_error"])
                self.assertIsNone(results[0].get("predicted_outcome"))
                summary = self.ev.aggregate_label(results, self.axes, True)
                self.assertEqual(summary["invocation_failures"], 1)
                self.assertEqual(summary["accuracy"], 0)
                self.assertEqual(summary["outcome_accuracy"], 0)
                for axis in self.axes:
                    self.assertEqual([summary["per_axis"][axis][key] for key in ("tp", "fp", "fn", "tn")], [0, 0, 0, 0])

    def test_missing_or_nonboolean_labels_never_become_false_predictions(self):
        # covers: TQ-200a-2-i
        # angle: boundary
        complete = self.row("complete")["expected"]
        invalid = [{}, {"expected": {}}, {"expected": {"needs_flow": False}}]
        invalid.extend({"expected": dict(complete, needs_flow=value)} for value in (None, "false", 0, [], {}))
        for reply in invalid:
            with self.subTest(reply=reply):
                results = self.invoke([self.row("invalid")], [json.dumps(reply)])
                self.assertFalse(results[0]["score"]["passed"], results)
                self.assertIsNone(results[0].get("predicted_outcome"))
                summary = self.ev.aggregate_label(results, self.axes, True)
                self.assertEqual(summary["invocation_failures"], 1)
                self.assertEqual(summary["accuracy"], 0)
                self.assertEqual(summary["per_axis"]["needs_flow"]["tn"], 0)

    def test_successful_all_false_prediction_still_passes(self):
        # covers: TQ-200a-2-i
        # angle: criterion
        rows = [self.row("successful-none")]
        results = self.invoke(rows, [json.dumps({"expected": rows[0]["expected"]})])
        self.assertTrue(results[0]["score"]["passed"], results)
        self.assertEqual(results[0]["predicted_outcome"], "none")
        summary = self.ev.aggregate_label(results, self.axes, True)
        self.assertEqual(summary["accuracy"], 1)
        self.assertEqual(summary["outcome_accuracy"], 1)
        for axis in self.axes:
            self.assertEqual(summary["per_axis"][axis]["tn"], 1)

    def test_mixed_results_keep_failed_rows_in_denominator_without_fake_confusion(self):
        # covers: TQ-200a-2-i
        # angle: boundary
        rows = [self.row("none"), self.row("failed"), self.row("flow", True)]
        results = self.invoke(rows, [json.dumps({"expected": rows[0]["expected"]}),
                                    self.ev.ModelInvocationError("No result"),
                                    json.dumps({"expected": rows[2]["expected"]})])
        summary = self.ev.aggregate_label(results, self.axes, True)
        self.assertEqual(summary["rows"], 3)
        self.assertEqual(summary["passed"], 2)
        self.assertEqual(summary["invocation_failures"], 1)
        self.assertEqual(summary["accuracy"], round(2 / 3, 4))
        self.assertEqual(summary["outcome_accuracy"], round(2 / 3, 4))
        self.assertEqual(summary["per_axis"]["needs_flow"]["tp"], 1)
        self.assertEqual(summary["per_axis"]["needs_flow"]["tn"], 1)
        self.assertEqual(summary["per_axis"]["needs_mock_data"]["tn"], 2)


if __name__ == "__main__":
    unittest.main()
