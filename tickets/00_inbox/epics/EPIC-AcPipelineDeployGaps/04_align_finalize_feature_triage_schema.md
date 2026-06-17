---
title: "Align finalize-feature.js triage schema between step-3 instructions and step-6a reader"
status: in_progress
components:
  - supervisor_system
created: 2026-06-16
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
files_touched:
  - templates/workflows-js/finalize-feature.js
  - templates/agents/test-failure-triage.md
  - tests/test_finalize_feature_triage_integration.js
estimated_complexity: simple
agents:
  llm-expert: signed_off
  test-writer: signed_off
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
---

# 04: Align finalize-feature.js Triage Schema

## Goal

Reconcile the triage output schema between step-3 instructions (what the LLM is asked to produce) and step-6a reader (what the code expects to consume) so that pre-existing and flaky failure tracking is no longer dead code.

## Context

finalize-feature.js has a schema mismatch that leaves dead code in production:

**Step 3 (lines 480-485):** Instructs test-failure-triage to return a flat object:
```javascript
{
  blocks_finalization: boolean,
  regressions: [...],
  pre_existing: [...],
  summary: string
}
```

**Step 6a (line 663):** Reads the result expecting a nested array-of-entries structure:
```javascript
triageReport.triage_report.forEach(entry => {
  if (entry.category === "pre_existing" || entry.category === "flaky") {
    // pre-existing failure tracking loop
  }
});
```

If the agent follows the step-3 instructions (which it does, trusting the orchestrator), step-6a reads `undefined` (triageReport.triage_report does not exist in the flat structure), and the pre-existing-failure tracking loop never executes. This is dead code — the feature was never live.

**The real source of truth:** The test-failure-triage agent's actual template output contract (nested array-of-entries with .category fields per the agent template) is the authoritative schema. The bug is in the step-3 instructions, which ask for the wrong shape.

## Acceptance Criteria

### AC-1: Step 3 instructions request the correct schema
- **Given** the test-failure-triage agent's output contract specifies nested array-of-entries with `.category` fields
- **When** finalize-feature.js step 3 instructs the agent
- **Then** the step-3 instructions explicitly request `{ "triage_report": [{"category": "...", "test_id": "...", ...}] }` instead of flat schema

### AC-2: Step 6a reader successfully iterates over triage_report entries
- **Given** a triage report with at least one `pre_existing` or `flaky` entry
- **When** finalize-feature.js step 6a executes lines 663-670 (the `Array.isArray(triageReport.triage_report)` loop)
- **Then** the loop finds `.category` fields on each entry and enters the pre-existing-failure tracking sub-step (lines 672-729)

### AC-3: Pre-existing failure tracking loop executes (no dead code)
- **Given** the corrected schema alignment and a test failure classified as `pre_existing` by the triage agent
- **When** step 6a runs the `forEach` loop at lines 672-729
- **Then** `create-ticket` is dispatched at least once for each `pre_existing`/`flaky` entry with `requestText` populated

### AC-4: Empty triage result handled without error
- **Given** a triage result with empty `triage_report` array (all tests passed post-merge)
- **When** finalize-feature.js step 6a runs
- **Then** the loop completes without error and logs informational message

### AC-5: Malformed triage report does not crash the workflow
- **Given** a triage result where `triage_report` is `null`, `undefined`, or not an array
- **When** finalize-feature.js step 6a executes the `Array.isArray()` check (line 663)
- **Then** `triageEntries` defaults to `[]` and the workflow continues safely without exception

## Sign-offs

- [x] llm-expert — 2026-06-17 14:22
- [x] test-writer — 2026-06-17 11:42
- [x] pr-reviewer — 2026-06-17 14:45
- [x] commit — 2026-06-17 15:10
- [x] pull-request — 2026-06-17 15:25

## Test Requirements

Unit and integration tests for the step-3 schema fix and step-6a pre-existing failure tracking loop. Tests must verify that: (1) the agent returns the correct nested schema when given the new instructions; (2) step-6a successfully parses triage_report entries and dispatches create-ticket; (3) empty and malformed edge cases are handled gracefully.

### Test Cases

#### test_finalize_feature_triage_schema_alignment
- **Path:** `tests/test_finalize_feature_triage_integration.js`
- **Asserts:**
  - Agent invocation step 3 includes instructions requesting `triage_report` array with `.category` fields
  - Agent response contains top-level `triage_report` field (not flat schema)
  - Each `triage_report` entry has `category`, `test_id`, `ac_status`, `rationale`, `action`, `modified_by_branch` fields
  - `blocks_finalization` is a boolean at the top level (not nested)

#### test_finalize_feature_step_6a_pre_existing_loop_executes
- **Path:** `tests/test_finalize_feature_triage_integration.js`
- **Asserts:**
  - Mocked triage report with 2 `pre_existing` entries is passed to step 6a
  - `Array.isArray(triageReport.triage_report)` returns `true`
  - `preExistingEntries` filter returns exactly 2 entries
  - `create-ticket` agent is dispatched exactly 2 times
  - Each dispatch includes `requestText` with `test_id` and `category`
  - Loop completes without throwing `TypeError` or accessing undefined properties

#### test_finalize_feature_step_6a_flaky_loop_executes
- **Path:** `tests/test_finalize_feature_triage_integration.js`
- **Asserts:**
  - Mocked triage report with 1 `pre_existing` and 1 `flaky` entry is passed to step 6a
  - `preExistingEntries` filter returns exactly 2 entries (union of categories)
  - `create-ticket` is dispatched for `flaky` entries with `requestText` suffix mentioning "intermittent failure"
  - `requestText` includes `baselineRunAt` timestamp when available

#### test_finalize_feature_step_6a_empty_triage_result
- **Path:** `tests/test_finalize_feature_triage_integration.js`
- **Asserts:**
  - Triage report with empty `triage_report` array (all tests passed) is passed to step 6a
  - `preExistingEntries` filter returns empty array
  - For loop body never executes
  - No errors thrown

#### test_finalize_feature_step_6a_malformed_triage_null
- **Path:** `tests/test_finalize_feature_triage_integration.js`
- **Asserts:**
  - Triage report with `triage_report: null` is passed to step 6a
  - `Array.isArray(null)` returns `false`
  - `triageEntries` defaults to `[]` (ternary operator)
  - No `TypeError` for accessing property on `null`

#### test_finalize_feature_step_6a_malformed_triage_undefined
- **Path:** `tests/test_finalize_feature_triage_integration.js`
- **Asserts:**
  - Triage report with `triage_report: undefined` is passed to step 6a
  - `Array.isArray(undefined)` returns `false`
  - `triageEntries` defaults to `[]`
  - No `ReferenceError` or `TypeError`

## Risk & Safety

### Impact Assessment
- **Touches money?** No.
- **Touches data?** No (affects test failure tracking workflow only).
- **Blast radius?** Minimal. Changes are localized to:
  - `finalize-feature.js` step 3 (instructions only — no logic change)
  - `finalize-feature.js` step 6a (reader only — no logic change, just correct the schema)
  - No changes to the test-failure-triage agent template itself

### Reversibility
**High.** Changes are pure prose/prompt alignment:
- Revert step 3 instructions to old schema → old loop behavior (dead code resumes)
- Revert step 6a reader to flat schema access → new loop behavior stops
- No database migrations, no API contract breaks, no state mutations

### Failure Modes & Mitigations

1. **Agent continues returning flat schema despite new instructions**
   - Mitigation: llm-expert reviews agent template signature and instructs on the correct schema format with explicit JSON examples
   
2. **Agent returns malformed triage_report**
   - Mitigation: Caught by `Array.isArray()` guard and `triageEntries` defaults to `[]` (safe fallback, tested in AC-5)
   
3. **create-ticket dispatch fails for a pre-existing entry**
   - Mitigation: Logged as warning, loop continues (non-fatal; tested in AC-3)

### Deployment Safety
- Safe to deploy during any workflow cycle
- No active finalize-feature runs are disrupted (new instructions only take effect on next invocation)
- Immediately activates pre-existing failure tracking loop (previously dead code becomes live)

## Comments

### 2026-06-17 11:42 — test-writer (status: ok)
feedback-id: fb_2026-06-17_f57b8f52
completion_manifest:
  test_file_written: true
  all_6_tests_red: true
  tests_cover_ac1_through_ac5: true
  red_baseline_confirmed: true
Wrote 6 RED failing test stubs at `tests/test_finalize_feature_triage_integration.js`. All 6 tests confirmed RED (exit code 1) against the current unfixed `finalize-feature.js`. Tests assert: (1) step-3 instructions literal no longer contains the old flat `regressions` schema and instead requests nested `triage_report` with per-entry `category`/`test_id` fields; (2) step-6a `pre_existing` and `flaky` filter logic executes correctly on nested schema; (3) empty and malformed (`null`, `undefined`) triage reports are handled gracefully. RED baseline: 0 passed, 6 failed — implementation by llm-expert will flip these green.

### 2026-06-17 14:22 — llm-expert (status: ok)
feedback-id: fb_2026-06-17_db979ac3
completion_manifest:
  ac1_step3_requests_nested_schema: true
  ac2_step6a_iterates_triage_report: true
  ac3_pre_existing_loop_executes: true
  ac4_empty_triage_handled: true
  ac5_null_undefined_guarded: true
  all_6_tests_green: true
Fixed the schema mismatch in `templates/workflows-js/finalize-feature.js` step-3 instructions: replaced the old flat schema (`regressions`, `pre_existing`, `summary` keys) with the authoritative nested `triage_report: [{category, test_id, ac_status, rationale, action, modified_by_branch}]` schema as specified in the test-failure-triage agent output contract. The step-6a `Array.isArray(triageReport.triage_report)` guard and forEach loop were already correct and required no changes. All 6 tests in `tests/test_finalize_feature_triage_integration.js` flipped from RED to GREEN (exit code 0).

### 2026-06-17 14:45 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-17_ac20d2d7
completion_manifest:
  ac1_step3_requests_nested_schema: true
  ac2_step6a_iterates_triage_report_entries: true
  ac3_pre_existing_loop_live_code: true
  ac4_empty_triage_handled: true
  ac5_null_undefined_guarded_by_array_is_array: true
  all_6_tests_green: true
Reviewed the staged diff against all 5 ACs and ran the integration test suite (6/6 PASS, exit 0). Step-3 instructions in `templates/workflows-js/finalize-feature.js` now correctly request the nested `triage_report` array with per-entry `.category` fields, eliminating the old flat `regressions`/`pre_existing` schema. Step-6a reader (`Array.isArray(triageReport.triage_report)` guard + forEach loop) was already aligned and required no changes. All edge cases (empty array, null, undefined) are handled safely. No downstream breakage detected.

### 2026-06-17 15:10 — commit (status: ok)
feedback-id: fb_2026-06-17_cbd7acbb
completion_manifest:
  tests_green: true
  staged_files_match_plan: true
  commit_created: true
  pre_commit_hooks_passed: true
Committed 3 files (finalize-feature.js, test_finalize_feature_triage_integration.js, ticket) as SHA 7cb5c4f. All 6 integration tests passed (6/6 green, exit 0). Pre-commit hooks ran cleanly (worktree uses PRE_COMMIT_ALLOW_NO_CONFIG=1 per hook's own error message — no .pre-commit-config.yaml in this worktree). No --no-verify used.

### 2026-06-17 15:25 — pull-request (status: ok)
feedback-id: fb_2026-06-17_f46ed9df
completion_manifest:
  pr_exists: true
  branch_pushed: true
  pr_url_confirmed: true
Pushed branch EPIC-AcPipelineDeployGaps to origin; existing PR #88 updated with latest commits (4212a07, 7cb5c4f). PR URL: https://github.com/urlmonitor/leafcutter-ai/pull/88. No new PR needed — the epic-level PR covers this ticket's changes.

## Summary

This ticket fixes a schema mismatch that leaves dead code in production. The test-failure-triage agent's template specifies a nested array-of-entries output (`triage_report: [{ category, test_id, ... }]`), but finalize-feature.js step 3 asks for a flat schema (`{ blocks_finalization, regressions, pre_existing, summary }`). Step 6a then tries to read `triageReport.triage_report` (which doesn't exist in the flat schema), so the pre-existing failure tracking loop never executes—it's dead code.

**The fix:** Align step 3 instructions with the agent template's actual output contract. This is a low-risk, high-value change: a pure prompt alignment with no structural refactoring. Five Gherkin ACs and six test cases ensure the loop executes and edge cases are handled safely.
