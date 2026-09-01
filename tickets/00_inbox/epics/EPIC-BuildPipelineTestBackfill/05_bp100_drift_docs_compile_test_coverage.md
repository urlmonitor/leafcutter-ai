---
title: "Backfill green test coverage for BP-100 (drift-hook / docs / compile) ACs"
status: todo
components:
  - build_pipeline
  - commit_guardian
created: 2026-07-15
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
test_required: true
source_ac: BP-100b-5
ac_coverage:
  - BP-100b-5
  - BP-100b-5-i
  - BP-100b-6-i
  - BP-100b-8
  - BP-100b-9
  - BP-100b-10
  - BP-100c-4
files_touched:
  - unit_tests/build/test_bp100_drift_docs_compile.py
  - templates/scripts/commit_guardian/check_output_drift.py
  - scripts/template_compiler.py
  - scripts/injection_builders.py
  - tests/test_build_artifact_parity.py
  - docs/build-pipeline.md
  - docs/explanation/consolidated-output-root.md
  - docs/build-drift-hook.md
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: not_needed
change_target: code
risk_surface: internal
---

# 05: Green test coverage for BP-100 (drift-hook / docs / compile)

## Actor / Goal

As the AC store, I want every BP-100 AC in `ac_coverage` to have a real, green unit
test that **names the AC** (`# covers: <AC>`), so its `work_status: done` is honestly
backed by verifiable coverage (per the 2026-07-14 test-truth rule).

## Test Backfill Context

**Nature: CODE_NO_TEST.** Per the 2026-07-14 audit, these 7 BP-100 leaves are built but
untested. **Do NOT rewrite the hook / compiler / docs.** Author asserting tests. This
cluster spans three natures:

- **Drift-hook behaviour** (b-5, b-5-i): `templates/scripts/commit_guardian/check_output_drift.py`.
- **Parity failure-message behaviour** (b-6-i): `tests/test_build_artifact_parity.py` message.
- **Compile passthrough** (c-4): `scripts/template_compiler.py` + `scripts/injection_builders.py`.
- **Doc artifacts** (b-8, b-9, b-10): the test asserts the doc artifact/section exists with
  the required content (these are doc ACs — assert the shipped Markdown, do not rewrite it).

The surfaces under test (read-only):
- `templates/scripts/commit_guardian/check_output_drift.py`
- `scripts/template_compiler.py`, `scripts/injection_builders.py`
- `tests/test_build_artifact_parity.py` (assert its failure message names layer + category)
- `docs/build-pipeline.md`, `docs/explanation/consolidated-output-root.md`,
  `docs/build-drift-hook.md`

## What each test must assert

Read each AC's `criteria` in
`docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/<AC>.yaml`. Summary:

- **BP-100b-5** — the drift hook scans `.claude/workflows/` (not `.agents/workflows/`);
  reports drift when a compiled workflow file's content differs from its source fingerprint;
  passes silently for the workflows category when all match. (Drive `check_output_drift.py`
  against a fixture tree with a mutated compiled workflow and assert the drift report.)
- **BP-100b-5-i** — no false-positive when the legacy `.agents/workflows/` path is absent:
  no error/warning about the missing dir, workflows drift-check not skipped, proceeds via
  `.claude/workflows/` only.
- **BP-100b-6-i** — the parity test's assertion message, when a category (e.g. "widgets") is
  registered in output mappings + managed dirs but missing from the shim map / source
  manifests, names the missing category AND the specific missing layer(s), sufficient to fix
  without reading the test source. (Assert against the message-building code / a synthetic
  missing-category fixture.)
- **BP-100b-8** — `docs/build-pipeline.md` mermaid `graph TD` has a `build_workflow_scripts`
  phase node, an edge from build.py/orchestrator to it, and a label naming `.claude/workflows/`.
- **BP-100b-9** — `docs/explanation/consolidated-output-root.md` shimmed-outputs table has a
  row with source `templates/scripts/workflows/`, output `.claude/workflows/`, and a content
  description mentioning compiled workflow JS scripts.
- **BP-100b-10** — `docs/build-drift-hook.md` "Adding a new template category" section
  enumerates all four layers (shim map, output mappings, managed artifact dirs, source
  manifests) and references `tests/test_build_artifact_parity.py` as the enforcement gate.
- **BP-100c-4** — the template compiler threads config to the paths-table builder: given a
  template with `{{project_paths_table}}` and config `tickets_inbox_path =
  "leafcutter-ai/tickets/00_inbox"`, the compiled output contains that value in the paths
  table and does NOT contain the bare `tickets/00_inbox/` default (config passes through
  compile_agent_template → registry injection → paths-table builder). Cover this end-to-end
  through `template_compiler.py` / `injection_builders.py`.

## Acceptance Criteria

For each AC in `ac_coverage`: a green test names it (`# covers: <AC>`) and asserts its
behaviour/artifact; its `covered_by` records the test path (`::test_function`);
`work_status: done` only after green (mark-done is a follow-up).

## Test Requirements

```yaml
tests:
  - name: test_bp100_drift_docs_compile
    file: unit_tests/build/test_bp100_drift_docs_compile.py
    covers: [BP-100b-5, BP-100b-5-i, BP-100b-6-i, BP-100b-8, BP-100b-9, BP-100b-10, BP-100c-4]
    asserts: >
      Each listed AC has at least one green test naming it: b-5/b-5-i drive
      check_output_drift.py against fixture trees; b-6-i asserts the parity failure message
      names layer+category; b-8/b-9/b-10 assert the shipped doc section/table content;
      c-4 asserts config passthrough to the compiled paths table.
```

## Sign-offs

- [x] test-writer — 2026-07-15 10:23
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit

## Comments

### 2026-07-15 10:23 — test-writer (status: ok)
feedback-id: fb_2026-07-15_d4ad3060
completion_manifest:
  test_file_written: true
  tests_red_on_run: true
  ruff_clean: true
  covers_all_seven_acs: true
Wrote `unit_tests/build/test_bp100_drift_docs_compile.py` covering all 7 ACs. Overall run is red (exit 1): BP-100b-8 fails because `build_workflow_scripts` node ID is absent from the Mermaid diagram (current diagram uses generic `N`); BP-100b-9 fails because `templates/scripts/workflows/` is not in the consolidated-output-root.md shimmed-outputs table. The remaining 6 tests pass immediately (code is already correct — CODE_NO_TEST backfill).

## Test Writer — Completion Report

### Tests Written
| File | Directory | Framework | Status |
|---|---|---|---|
| test_bp100_drift_docs_compile.py | unit_tests/build/ | unittest | written |

### Verification Run
- Command: `python3 -m unittest discover -s unit_tests/build -t . -p "test_bp100_drift_docs_compile.py"`
- Result: red (2 failures — BP-100b-8, BP-100b-9; 6 pass immediately; exit 1)

### Notes
- BP-100b-8 and BP-100b-9 are genuinely red: the docs do not yet satisfy the AC-specified content (`build_workflow_scripts` node ID; `templates/scripts/workflows/` source column).
- BP-100b-5, BP-100b-5-i, BP-100b-6-i, BP-100b-10, BP-100c-4 pass immediately (CODE_NO_TEST backfill — implementation already exists).
- Added `change_target: code` and `risk_surface: internal` to ticket frontmatter (required fields missing from original scaffold).

red_baseline:
  - test_name: test_ac_bp100b8_mermaid_graph_has_build_workflow_scripts_node_id
    file: unit_tests/build/test_bp100_drift_docs_compile.py
    error: "AssertionError: 'build_workflow_scripts' not found in '...' : docs/build-pipeline.md must contain 'build_workflow_scripts' as a Mermaid node identifier"
  - test_name: test_ac_bp100b9_shimmed_outputs_table_has_workflows_source_path
    file: unit_tests/build/test_bp100_drift_docs_compile.py
    error: "AssertionError: 'templates/scripts/workflows/' not found in '...' : consolidated-output-root.md shimmed-outputs table must include 'templates/scripts/workflows/' as the source path"
  - test_name: test_ac_bp100b5_drift_reported_for_mutated_workflow_file
    file: unit_tests/build/test_bp100_drift_docs_compile.py
    error: "(none)"
    note: "passes immediately — may be under-specified (CODE_NO_TEST backfill: implementation already correct)"
  - test_name: test_ac_bp100b5_passes_silently_when_all_workflow_files_match
    file: unit_tests/build/test_bp100_drift_docs_compile.py
    error: "(none)"
    note: "passes immediately — may be under-specified (CODE_NO_TEST backfill: implementation already correct)"
  - test_name: test_ac_bp100b5_i_no_false_positive_when_agents_workflows_absent
    file: unit_tests/build/test_bp100_drift_docs_compile.py
    error: "(none)"
    note: "passes immediately — may be under-specified (CODE_NO_TEST backfill: implementation already correct)"
  - test_name: test_ac_bp100b6_i_assertion_messages_reference_category_and_layer
    file: unit_tests/build/test_bp100_drift_docs_compile.py
    error: "(none)"
    note: "passes immediately — may be under-specified (CODE_NO_TEST backfill: implementation already correct)"
  - test_name: test_ac_bp100b10_new_category_section_has_all_four_layers
    file: unit_tests/build/test_bp100_drift_docs_compile.py
    error: "(none)"
    note: "passes immediately — may be under-specified (CODE_NO_TEST backfill: implementation already correct)"
  - test_name: test_ac_bp100c4_config_inbox_path_appears_in_compiled_paths_table
    file: unit_tests/build/test_bp100_drift_docs_compile.py
    error: "(none)"
    note: "passes immediately — may be under-specified (CODE_NO_TEST backfill: implementation already correct)"
