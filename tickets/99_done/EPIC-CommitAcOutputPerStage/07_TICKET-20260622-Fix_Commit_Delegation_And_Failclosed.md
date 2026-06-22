---
advances_current_outcome: true
agents:
  commit: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  pull-request: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  test-writer: signed_off
components:
- ac-driven-dev
created: '2026-06-22'
depends_on:
- 01_TICKET-20260618-ACD-300g-1.md
- 02_TICKET-20260618-ACD-300g-1-i.md
files_touched:
- scripts/workflows/plan-feature.js
- templates/workflows-js/plan-feature.js
priority: high
requires_adr: false
requires_diagram: false
roadmap_phase: phase_1
source_ac: ACD-300g-1
status: done
title: 'Fix commitStageOutput: route commit through commit agent + fail closed on
  unparseable output'
---

# Fix commitStageOutput: route commit through commit agent + fail closed on unparseable output

## Actor / Goal

As the /plan-feature workflow, I want `commitStageOutput()` to commit via a path
that is NOT blocked by the `enforce_commit_delegation` hook, and to treat an
unparseable/empty commit result as a FAILURE (not success), so that the per-stage
commit feature (ACD-300g-1) actually runs in a correctly-configured repo and
ACD-300g-1-i's "commit failure aborts the pipeline" guarantee holds.

## Context

Post-build angle-testing (3 spot-check agents, 2026-06-22) found two HIGH defects
in `commitStageOutput()` in [scripts/workflows/plan-feature.js](scripts/workflows/plan-feature.js)
(and its byte-identical template copy):

1. **Commit-delegation collision (runtime blocker).** Step 5 of the agent prompt
   (~line 199) instructs the dispatched `status-checker` agent to run
   `git commit -m "..."` directly. The project's mandatory `enforce_commit_delegation`
   PreToolUse hook BLOCKS any `git commit` not originating from the `commit` agent
   with `COMMIT_AGENT_MODE=1`. So the headline feature — commit AC files at each
   gate — fails at runtime on any properly-configured install. (Confirmed: the hook
   even blocks a bare `grep "git commit"` Bash call.)

2. **Fail-open error handling (weakens ACD-300g-1-i).** The result-coercion block
   (~lines 258-268) maps a `JSON.parse` failure and a null/empty agent result to
   `{status: "ok"}`. A silently-failed commit therefore reports success, pushes the
   stage's ACs into `committedAcs`, and dispatches the next agent — the exact
   fail-OPEN posture ACD-300g-1-i wants to be fail-CLOSED.

This builds on tickets 01 + 02, which introduced `commitStageOutput()` and
`formatCommitError()` but with the wrong `files_touched` (SKILL.md + ADRs), so the
commit mechanism shipped with these latent runtime defects.

## AC References

- Implements (correctly, in the executable surface) AC ACD-300g-1 and ACD-300g-1-i.

## Acceptance Criteria

```gherkin
Scenario: stage commit does not collide with the commit-delegation hook
  Given the /plan-feature workflow approves a stage and calls commitStageOutput()
  When the commit is performed
  Then it is NOT performed by instructing a status-checker agent to run a raw `git commit`
  And the commit path is one the enforce_commit_delegation hook permits
    (e.g. dispatch the dedicated commit agent, or run under COMMIT_AGENT_MODE=1
    only if that is sanctioned for this workflow — decide and document which).

Scenario: unparseable or empty commit result is treated as a failure
  Given commitStageOutput() dispatches its commit step
  When the agent returns non-JSON prose, a truncated string, or an empty/null result
  Then commitStageOutput() returns status: "error" (fail closed)
  And run() aborts without dispatching the next authoring agent
  And the stage's ACs are NOT added to committedAcs.

Scenario: a genuinely successful commit still advances the pipeline
  Given the commit step succeeds (exit 0, well-formed ok result)
  Then commitStageOutput() returns status: "ok"
  And the next authoring agent is dispatched as before.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| hook-safe commit path | test_agent_instructions_do_not_contain_raw_git_commit, test_dispatched_agent_type_is_not_status_checker_for_commit — all green 2026-06-22 | | ok — 2026-06-22 |
| fail-closed on unparseable | test_non_json_prose_result_is_fail_closed, test_null_result_is_fail_closed, test_empty_string_result_is_fail_closed, test_truncated_json_result_is_fail_closed, test_undefined_result_is_fail_closed — all green 2026-06-22 | | ok — 2026-06-22 |
| success still advances | test_well_formed_ok_object_passes_through, test_well_formed_ok_json_string_passes_through, test_well_formed_error_object_passes_through — all green 2026-06-22 | | ok — 2026-06-22 |

## Sign-offs

- [x] test-writer — 2026-06-22 14:30
- [x] python-coder — 2026-06-22 15:00
- [x] test-runner — 2026-06-22 15:30
- [x] pr-reviewer — 2026-06-22 16:00
- [x] commit — 2026-06-22 (auto-authorized by ticket-supervisor)
- [x] pull-request — 2026-06-22 17:00

## Comments

_(Append-only log — leave blank when authoring.)_

### 2026-06-22 15:00 — python-coder (status: ok)

feedback-id: fb_2026-06-22_4674b205
completion_manifest:
  commit_agent_dispatch_implemented: true
  fail_closed_coercion_implemented: true
  template_parity_applied: true
  all_11_tests_pass: true
Fixed both HIGH defects in `commitStageOutput()` in `scripts/workflows/plan-feature.js` and `templates/workflows-js/plan-feature.js` (byte-identical). Defect 1: replaced `agentType: "status-checker"` with `agentType: "commit"` and rewrote Step 5 to not contain a raw `Run: git commit` instruction — now tells the commit agent to use its standard flow with the pre-built commit message. Defect 2: flipped the catch block from `{status:"ok"}` to `{status:"error"}` and the fallback `result ||` from `{status:"ok"}` to `{status:"error"}`. All 11 behavioral tests pass (7 previously RED now GREEN, 4 previously GREEN remain GREEN).

### 2026-06-22 14:30 — test-writer (status: ok)

feedback-id: fb_2026-06-22_68bef027
completion_manifest:
  behavioral_tests_written: true
  red_baseline_confirmed: true
  ruff_clean: true
  success_path_green: true
Wrote `unit_tests/test_commit_stage_output_behavioral.py` with 11 behavioral tests across three test classes. RED baseline confirmed: 7 tests fail against the current broken code (5 fail-closed tests, 2 hook-safe path tests). 4 tests are GREEN (success path and parity). The coercion-replay tests use Node.js `vm.Script` to execute the EXACT coercion block extracted from `plan-feature.js` with mocked inputs — not string scans. The hook-safe path tests invoke `commitStageOutput()` via a patched vm context with a mock agent that captures `agentType` and `instructions`, confirming the defect behaviors at the runtime level.

### 2026-06-22 15:30 — test-runner (status: ok)

feedback-id: fb_2026-06-22_b1dc670b
completion_manifest:
  all_11_tests_pass: true
  fail_closed_tests_green: true
  hook_safe_path_tests_green: true
  success_path_tests_green: true
  template_parity_confirmed: true
All 11 behavioral tests pass (0 failures, 0.62s). The 5 fail-closed tests (non-JSON prose, null, empty string, truncated JSON, undefined result) all return `{status: "error"}` as required. The 2 hook-safe-path tests confirm `agentType` is `"commit"` (not `"status-checker"`) and that the instructions contain no raw `git commit` command. The 3 success-path tests confirm well-formed ok/error objects still pass through correctly. `diff` between `scripts/workflows/plan-feature.js` and `templates/workflows-js/plan-feature.js` shows no output — byte-identical parity confirmed.

### 2026-06-22 16:00 — pr-reviewer (status: ok)

feedback-id: fb_2026-06-22_f171eafd
completion_manifest:
  agentType_is_commit: true
  instructions_contain_no_raw_git_commit: true
  catch_block_returns_error: true
  fallback_returns_error: true
  scripts_templates_byte_identical: true
  tests_are_behavioral_vm_replay: true
  scope_limited_to_two_targeted_defects: true
Reviewed the staged diff. Both defects are correctly fixed: (1) `agentType` is now `"commit"` (not `"status-checker"`) in `commitStageOutput()`, and the Step 5 instructions no longer contain a `Run: git commit` directive — the enforce_commit_delegation hook will not block this path. (2) The catch block now returns `{status: "error", ...}` (not `{status: "ok"}`), and the fallback `result ||` expression also returns `{status: "error", ...}` — fail-closed per ACD-300g-1-i. `diff scripts/ templates/` confirms byte-identical parity. The test file uses Node.js vm.Script behavioral replay, not grep scans. No regressions or scope drift detected; only the two targeted defects were touched.

## Implementation Tasks
- [x] Decide the hook-safe commit mechanism (commit agent vs sanctioned COMMIT_AGENT_MODE) and implement it in `commitStageOutput()`.
- [x] Flip the unparseable/empty result coercion from ok → error (fail closed).
- [x] Apply the identical change to `templates/workflows-js/plan-feature.js` (parity is required — see ticket 10/spot-check).
- [x] Add a test asserting the behavior. NOTE: grep-only tests let the original phantom-done through — prefer a replay/behavioral assertion over a string-scan where feasible.

### 2026-06-22 — commit (status: ok)

feedback-id: fb_2026-06-22_commit_07
completion_manifest:
  commit_sha: 1cc4e1e
  files_committed: 4
  pre_commit_hooks_passed: true
  io_001_autofix_applied: true
  branch: EPIC-CommitAcOutputPerStage
Committed 4 files (scripts/workflows/plan-feature.js, templates/workflows-js/plan-feature.js, unit_tests/test_commit_stage_output_behavioral.py, ticket sign-offs). Pre-commit hooks all passed after one autofix: IO-001 violation in _read_source() at line 75 (open() not wrapped in try/except) was fixed and re-staged before the successful retry commit.

### 2026-06-22 17:00 — pull-request (status: ok)

feedback-id: fb_2026-06-22_e15551b2
completion_manifest:
  existing_pr_detected: true
  branch_pushed: true
  pr_url_confirmed: true
Detected existing PR #114 (feat(plan-feature): commit approved AC stage output before next dispatch) on branch EPIC-CommitAcOutputPerStage. Pushed ticket 07 commits (cd64441) to the remote, updating the existing PR without creating a duplicate. PR is at https://github.com/urlmonitor/leafcutter-ai/pull/114.

## Risk & Safety
- Touches money? No.
- Touches data? Changes how/whether commits happen in the AC authoring workflow; no destructive data ops.
- Reversibility? Fully reversible (workflow script edit).
