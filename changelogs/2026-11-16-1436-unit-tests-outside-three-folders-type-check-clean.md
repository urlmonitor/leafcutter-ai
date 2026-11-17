---
title: "unit_tests outside commit_guardian, portability and build_orchestration type-check clean"
date: "2026-11-16"
time: "14:36"
type: manual
components: 
  - testing_quality
summary: "Batch E of the mypy cleanup. With CI's flags, mypy reported 176 errors across the unit_tests files outside commit_guardian/, portability/ and build_orchestration/. It now reports none. Only typing changed: fixture attributes are declared, optionals are narrowed with isinstance, empty literals are annotated, and three files import helpers from the module that defines them. No test was renamed, removed or skipped, and no assertion was loosened."
description: "test, mypy ratchet batch E. Scope: every tracked .py under unit_tests/ except commit_guardian/, portability/ and build_orchestration/ (1296 files). Measured with mypy --ignore-missing-imports --explicit-package-bases and without the user site-packages, which matches CI: 176 errors before, 0 after (product_truth 36, agents 34, workflows 23, prompt_assembly 21, evals 20, build_guards 16, top-level 10, ac_store 7, suite_performance 6, feedback 2, docs 1). On this host 57 more errors appear in 16 files only because the pypa build package in the user site-packages shadows scripts/build.py for import build. They were left alone. The fixes: class-level declarations for attributes that setUpClass assigns; isinstance(ModuleSpec) and isinstance(Loader) on spec_from_file_location results; assert isinstance after an existing assertIsNotNone; annotations on empty or mixed literals; precise parameter types in tq200d5/_fake.py, test_cli_failure_detail.py and test_build_ac_mode_detection.py's fallback stub. The BO-4000 workflow tests and _bo4000_fixtures.py now import workspace_ensure_reply, workspace_refusal_reply, shell_step_reply and workspace_answer_of from unit_tests._workflow_engine_workspace, where they are defined. The harness star-re-exports them from a top-level module mypy cannot resolve, so mypy reported them as missing. One existing type: ignore in test_bp_100k_2.py is removed. Over-limit files paid back two-for-one. test_done_proof_js.py moves five identical setUp/tearDown pairs into one base class. test_scan_ac_orphans.py builds one index fixture from the other. test_master_plan_generation.py returns a merged dict."
adrs: []
commits: []
breaking: false
---

## Entry
