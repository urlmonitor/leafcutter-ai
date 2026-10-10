"""Reachability proof for exact product-truth contracts in CLI, CI and pre-commit.

GOAL: Fail through the public gates, including staged content hidden by a repair.
BUSINESS CONTEXT: UXP-700c-3's automatic verdict propagation and explicit user scope.
ARCHITECTURE: Real generator output enters the real validator; no mocked execution.
"""
from __future__ import annotations

import json
import shlex
import sys
import tempfile
import unittest

import yaml

from unit_tests.product_truth._flow_io_fixture import (
    ROOT, HOOK_ID, all_bytes, assert_success, canonical_hook,
    make_store, prepare_git_hook, run, write_json,
)


class TestFlowIoGate(unittest.TestCase):
    """The configured entry points must consume and propagate checker failures."""

    def setUp(self):
        from pathlib import Path
        self.sandbox = tempfile.TemporaryDirectory(prefix="flow-contract-gate-")
        self.addCleanup(self.sandbox.cleanup)
        self.root = Path(self.sandbox.name)
        self.pt = make_store(self.root)
        self.flow_path = self.pt / "flows/fixture/query.flow.json"
        self.schema_path = self.root / "config/request.schema.json"

    def cli(self):
        return run([
            sys.executable, str(self.pt / "scripts/product_truth_contracts.py"),
            "--repo-root", str(self.root), "--check",
        ], self.root)

    def mutate_schema(self):
        schema = json.loads(self.schema_path.read_text(encoding="utf-8"))
        schema["properties"]["context"]["default"] = ["changed without updating truth"]
        write_json(self.schema_path, schema)

    def test_generator_repairs_only_derived_contract_presentation_and_is_idempotent(self):
        # covers: UXP-700e-2-ii
        # angle: real_artifact
        flow = json.loads(self.flow_path.read_text(encoding="utf-8"))
        canonical = flow["steps"][0]["io_contracts"]
        definitions = flow["contract_definitions"]
        description = flow["steps"][0]["description"]
        flow["steps"][0]["consumes"] = ["Stale generated field"]
        write_json(self.flow_path, flow)
        self.assertNotEqual(self.cli().returncode, 0)
        command = [sys.executable, str(self.pt / "scripts/generate_product_truth.py"), "--quiet"]
        assert_success(run(command, self.root))
        repaired = json.loads(self.flow_path.read_text(encoding="utf-8"))
        self.assertEqual(repaired["contract_definitions"], definitions)
        self.assertEqual(repaired["steps"][0]["io_contracts"], canonical)
        self.assertNotIn("Stale generated field", repaired["steps"][0]["consumes"])
        # The authored description is never a generator target: no contract section is appended.
        self.assertEqual(repaired["steps"][0]["description"], description)
        self.assertNotIn("Contract fields and examples", json.dumps(repaired))
        assert_success(self.cli())
        first = all_bytes(self.root)
        assert_success(run(command, self.root))
        self.assertEqual(all_bytes(self.root), first)

    def test_cli_checks_visible_labels_and_is_read_only(self):
        # covers: UXP-700e-2-ii
        # angle: discrimination
        before = all_bytes(self.root)
        assert_success(self.cli())
        self.assertEqual(all_bytes(self.root), before)
        flow = json.loads(self.flow_path.read_text(encoding="utf-8"))
        flow["steps"][0]["consumes"][0] = "An unsupported vague claim"
        write_json(self.flow_path, flow)
        before = all_bytes(self.root)
        failed = self.cli()
        self.assertNotEqual(failed.returncode, 0, failed.stdout + failed.stderr)
        self.assertEqual(all_bytes(self.root), before)

    def test_cli_checks_visible_example_text_without_repairing_it(self):
        # covers: UXP-700e-2-ii
        # angle: discrimination
        validator = [sys.executable, str(self.pt / "scripts/validate_product_truth.py"), "--quiet"]
        assert_success(run(validator, self.root))
        flow = json.loads(self.flow_path.read_text(encoding="utf-8"))
        old_style = (flow["steps"][0]["description"]
                     + "\n\nContract fields and examples (generated)\nConsumes:\n  request/question: string (required)")
        flow["steps"][0]["description"] = old_style
        write_json(self.flow_path, flow)
        before = all_bytes(self.root)
        failed = run(validator, self.root)
        self.assertNotEqual(failed.returncode, 0, failed.stdout + failed.stderr)
        self.assertIn("[description] fixture/query step", failed.stdout + failed.stderr)
        self.assertIn("generated contract text", failed.stdout + failed.stderr)
        self.assertEqual(all_bytes(self.root), before)
        command = [sys.executable, str(self.pt / "scripts/generate_product_truth.py"), "--quiet"]
        assert_success(run(command, self.root))
        unrepaired = json.loads(self.flow_path.read_text(encoding="utf-8"))
        self.assertEqual(unrepaired["steps"][0]["description"], old_style)

    def test_ci_uses_same_validator_and_propagates_schema_only_failure(self):
        # covers: UXP-700c-3
        # covers: UXP-700c-3-iii
        # angle: reachability
        workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
        job = workflow["jobs"]["product-truth-valid"]
        self.assertNotIn("if", job)
        self.assertFalse(job.get("continue-on-error", False))
        checks = [s for s in job["steps"] if "validate_product_truth.py" in s.get("run", "")]
        self.assertEqual(len(checks), 1)
        step = checks[0]
        self.assertNotIn("if", step)
        self.assertFalse(step.get("continue-on-error", False))
        argv = shlex.split(step["run"])
        self.assertEqual(argv, ["python", "docs/product-truth/scripts/validate_product_truth.py", "--quiet"])
        argv[0] = sys.executable
        assert_success(run(argv, self.root))
        self.mutate_schema()
        failed = run(argv, self.root)
        self.assertNotEqual(failed.returncode, 0, failed.stdout + failed.stderr)
        self.assertIn("contract", (failed.stdout + failed.stderr).lower())

    def test_real_precommit_checks_staged_schema_despite_unstaged_repair(self):
        # covers: UXP-700c-3
        # covers: UXP-700c-3-iii
        # angle: seam
        prepare_git_hook(self.root)
        original = self.schema_path.read_bytes()
        self.mutate_schema()
        assert_success(run(["git", "add", "config/request.schema.json"], self.root))
        self.schema_path.write_bytes(original)
        before = run(["git", "diff"], self.root).stdout
        result = run([
            sys.executable, "-m", "pre_commit", "run", HOOK_ID, "--verbose"
        ], self.root, env={"PRE_COMMIT_HOME": str(self.root / ".precommit-cache")})
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("contract", (result.stdout + result.stderr).lower())
        self.assertNotIn("no files to check", result.stdout.lower())
        self.assertEqual(self.schema_path.read_bytes(), original)
        self.assertEqual(run(["git", "diff"], self.root).stdout, before)

    def test_real_precommit_ignores_unstaged_invalid_schema_and_restores_it(self):
        # covers: UXP-700c-3-iii
        # angle: boundary
        prepare_git_hook(self.root)
        schema = json.loads(self.schema_path.read_text(encoding="utf-8"))
        schema["description"] = "Harmless staged schema clarification."
        write_json(self.schema_path, schema)
        assert_success(run(["git", "add", "config/request.schema.json"], self.root))
        self.mutate_schema()
        invalid_unstaged = self.schema_path.read_bytes()
        result = run([
            sys.executable, "-m", "pre_commit", "run", HOOK_ID, "--verbose"
        ], self.root, env={"PRE_COMMIT_HOME": str(self.root / ".precommit-cache")})
        assert_success(result)
        self.assertNotIn("no files to check", result.stdout.lower())
        self.assertEqual(self.schema_path.read_bytes(), invalid_unstaged)

    def test_proposed_binding_gap_is_visible_through_both_real_clis(self):
        # covers: UXP-300-3
        # angle: reachability
        flow = json.loads(self.flow_path.read_text(encoding="utf-8"))
        source = self.pt / "frontier-design.md"
        source.write_text("Proposed traversal result: its payload is still undefined.", encoding="utf-8")
        flow["steps"][0]["io_contracts"] = {"missing_bindings": [{
            "name": "traversal_frontier", "direction": "produces",
            "reason": "The proposed result shape has not been designed.",
            "source": "docs/product-truth/frontier-design.md",
        }]}
        write_json(self.flow_path, flow)
        assert_success(run([sys.executable, str(self.pt / "scripts/generate_product_truth.py"), "--quiet"], self.root))
        result = self.cli()
        assert_success(result)
        report = json.loads(result.stdout)
        self.assertEqual(report["missing_bindings"], 1)
        self.assertEqual(report["binding_gaps"][0]["name"], "traversal_frontier")
        standard = run([sys.executable, str(self.pt / "scripts/validate_product_truth.py"), "--quiet"], self.root)
        assert_success(standard)
        self.assertIn("1 missing binding(s) in 1 node(s)", standard.stderr)
        step = json.loads(self.flow_path.read_text(encoding="utf-8"))["steps"][0]
        # The gap lives in io_contracts (Atlas renders it there), never as text in the description.
        self.assertEqual(step["io_contracts"]["missing_bindings"][0]["name"], "traversal_frontier")
        self.assertNotIn("traversal_frontier", step["description"])

    def test_real_precommit_skips_out_of_scope_changes(self):
        # covers: UXP-700c-3-iii
        # angle: boundary
        prepare_git_hook(self.root)
        (self.root / "README.md").write_text("Unrelated documentation edit\n", encoding="utf-8")
        assert_success(run(["git", "add", "README.md"], self.root))
        result = run([
            sys.executable, "-m", "pre_commit", "run", HOOK_ID, "--verbose"
        ], self.root, env={"PRE_COMMIT_HOME": str(self.root / ".precommit-cache")})
        assert_success(result)
        self.assertIn("no files to check", result.stdout.lower())
        self.assertIn("Skipped", result.stdout)

    def test_atlas_ci_registration_includes_executable_contract_regressions(self):
        # covers: UXP-700c-3-iii
        # angle: criterion
        # Registration protection complements the real Vitest seam runs; this
        # assertion alone is deliberately not claimed as workflow reachability.
        workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
        job = workflow["jobs"]["atlas-contracts"]
        self.assertNotIn("if", job)
        self.assertFalse(job.get("continue-on-error", False))
        self.assertEqual(job["defaults"]["run"]["working-directory"], "leafcutter-web")
        for event in ("push", "pull_request"):
            self.assertNotIn("paths", workflow["on"][event])
            self.assertNotIn("paths-ignore", workflow["on"][event])
        steps = [step for step in job["steps"] if "run" in step]
        for step in steps:
            self.assertNotIn("if", step)
            self.assertFalse(step.get("continue-on-error", False))
        self.assertEqual([shlex.split(step["run"]) for step in steps], [
            ["npm", "ci"],
            ["npx", "tsc", "--noEmit", "--incremental", "false"],
            ["npm", "test", "--",
             "components/flows/__tests__/flow-drawer.contracts.test.tsx",
             "components/flows/__tests__/flow-explorer.contracts.test.tsx",
             "lib/data/__tests__/flows.contracts.test.ts"],
        ])
        package = json.loads((ROOT / "leafcutter-web/package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["scripts"]["test"], "vitest run")

    def test_registered_trigger_includes_models_schemas_receipts_not_unrelated_text(self):
        # covers: UXP-700c-3-iii
        # angle: criterion
        hook = canonical_hook()
        for path in (
            "kernel/contracts/retrieval_needs.py",
            "kernel/memory/models.py",
            "kernel/providers/base.py",
            "knowledge/capability_fit.py",
            "templates/agents/flow-author.md",
            "docs/how-to/product-truth-schema-reference.md",
            "kernel/schemas/leafcutter.retrieval_needs_request.v1.schema.json",
            "config/request.schema.json",
            "reports/retrieval-needs-llm-2026-10-03-accepted/inputs/N03.input.json",
            "docs/product-truth/flows/fixture/query.flow.json",
        ):
            with self.subTest(path=path):
                self.assertRegex(path, hook["files"])
        self.assertNotRegex("README.md", hook["files"])
        self.assertFalse(hook.get("always_run", False))


if __name__ == "__main__":
    unittest.main()
