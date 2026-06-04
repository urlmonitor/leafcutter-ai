---
title: "Author test-failure-triage agent template"
status: todo
components:
  - build_pipeline
created: 2026-06-04
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/agents/test-failure-triage.md
  - config/agent_registry.json
agents:
  architect-review: signed_off
  test-writer: signed_off
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: needed
---

# 03: Author test-failure-triage agent template

## Actor / Goal

In order to classify test failures structurally before any remediation work
begins, we need a `test-failure-triage` agent that receives a post-merge
failure list and a baseline failure list and emits a structured triage report,
so that downstream steps in `finalize-feature.js` can route each failure to
the correct handler without re-running LLM reasoning.

## Context

The current finalize-feature workflow halts on any test failure and tells the
user to "fix the regression on a new branch." This is too coarse — it treats
a pre-existing broken test the same as a genuine regression introduced by the
feature branch.

The triage agent bridges this gap. It is a new agent in the registry (tier:
`utility`, role: `analysis`) spawned by `finalize-feature.js` at step 4 when
the post-merge test run produces failures. Its only job is classification.

### Classification categories

| Category | Condition | Action |
|----------|-----------|--------|
| `regression` | Failure not in baseline; test is active | Fix on this branch |
| `stale_test` | Failure not in baseline; test covers an AC that was intentionally amended by this feature | Update the test |
| `pre_existing` | Failure IS in baseline (already failing on main before merge) | Create tracking ticket; do not block PR |
| `flaky` | Failure intermittent across baseline and post-merge runs (requires multiple runs) | Mark and ticket separately |

For this ticket, `flaky` is a best-effort classification based on whether the
failure was seen in baseline but not consistently. Full flakiness detection
(multiple runs) is out of scope.

### Input contract

The agent receives:

```json
{
  "post_merge_failures": ["test_foo::test_bar", ...],
  "baseline_failures": ["test_baz::test_qux", ...],
  "baseline_sha": "<SHA>",
  "feature_branch": "<branch name>",
  "changed_files": ["<list of files changed by feature branch>"]
}
```

`baseline_failures` may be `null` (see ticket 02 error handling). When null,
the agent classifies all failures as `regression` (conservative).

### Output contract

```json
{
  "triage_report": [
    {
      "test_id": "test_foo::test_bar",
      "category": "regression",
      "rationale": "Not in baseline; test file touched by feature branch.",
      "action": "fix_on_branch"
    },
    {
      "test_id": "test_baz::test_qux",
      "category": "pre_existing",
      "rationale": "Present in baseline at SHA abc123.",
      "action": "create_tracking_ticket"
    }
  ],
  "summary": {
    "regression_count": 1,
    "stale_test_count": 0,
    "pre_existing_count": 1,
    "flaky_count": 0
  },
  "blocks_finalization": true
}
```

`blocks_finalization` is `true` when any `regression` or `stale_test` entries
exist (those require work before the PR can merge). It is `false` when all
failures are `pre_existing` or `flaky` (pre-existing failures do not block
the current PR).

## Acceptance Criteria

```gherkin
Given test-failure-triage receives a failure that is NOT in baseline_failures
When the agent classifies it
Then the failure is categorized as "regression"
 And action is "fix_on_branch"
 And blocks_finalization is true

Given test-failure-triage receives a failure that IS in baseline_failures
When the agent classifies it
Then the failure is categorized as "pre_existing"
 And action is "create_tracking_ticket"
 And blocks_finalization is false (when no regressions or stale tests exist)

Given baseline_failures is null (baseline run failed)
When test-failure-triage classifies any failures
Then all failures are categorized as "regression" (conservative)
 And blocks_finalization is true

Given test-failure-triage is called with an empty post_merge_failures list
When the agent returns
Then triage_report is []
 And blocks_finalization is false

Given test-failure-triage is registered in agent_registry.json
When build.py --validate-only runs
Then no validation errors are reported for the new agent entry
```

## Sign-offs

- [x] architect-review — 2026-06-04 10:00
- [x] test-writer — 2026-06-04 10:01
- [x] test-runner — 2026-06-04 10:10
- [x] pr-reviewer — 2026-06-04 10:15
- [x] commit — 2026-06-04 10:20
- [ ] pull-request

## Comments

### 2026-06-04 10:00 — architect-review (status: ok)
feedback-id: fb_2026-06-04_7358435e
completion_manifest:
  blast_radius_assessed: true
  impact_classified: true
  architectural_note_written: true

Blast-radius: 2 files affected (templates/agents/test-failure-triage.md new, config/agent_registry.json +1 entry), single component (build_pipeline). No always-large triggers fire (no migration, no hypertable, no public API, no ADR contract change). Classification: SMALL. Architectural note: this change is purely additive — a new read-only utility agent template with no cross-module dependencies. The classification logic (set difference + intersection) is stateless and correct for the three input cases specified. No ADR required; no diagrams suggested.

```json
{
  "architectural_note": "Purely additive change: new read-only utility agent. Two files in one component. No ADR, no diagram, no cross-module boundary. Classification logic is mathematically sound for the three input cases.",
  "acceptance_adjustments": [],
  "escalation": "none",
  "escalation_reason": "",
  "suggested_adr": null,
  "suggested_diagrams": []
}
```

## Escalation

Branch: none
Reason: 2 files in one component (build_pipeline); no always-large trigger fired.

### 2026-06-04 10:01 — ticket-supervisor (status: ok)
test_requirements empty — test-writer phase skipped (docs-only or config-only ticket)

### 2026-06-04 10:10 — test-runner (status: ok)
feedback-id: fb_2026-06-04_398f2acf
completion_manifest:
  tests_executed: true
  no_new_failures: true
  build_validation_passed: true

All 15 registry and workflow tests pass (0 new failures introduced by this ticket). `build.py --validate-only` exits with only the pre-existing `code-review-architect.md` error (unrelated to this ticket). All 5 ACs verified: regression classification, pre_existing classification, null-baseline conservative fallback, empty-list short-circuit, registry bidirectional consistency. The 2 pre-existing failures in `test_build_workflow_phase.py` are confirmed baseline failures from before this ticket.

### 2026-06-04 10:15 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-04_13bd2b59
completion_manifest:
  change_set_matches_scope: true
  acceptance_criteria_covered: true
  no_new_test_failures: true
  documentation_adequate: true

PR review passed. New agent template (`templates/agents/test-failure-triage.md`) is well-structured with correct frontmatter, complete input/output contracts, and handles all 4 classification categories. Registry entry is bidirectionally consistent (finalize-feature.spawn_allowlist updated). All 5 ACs in the ticket are covered by the implementation. No scope creep — only the 2 files listed in files_touched are modified. Build validation passes for the new entry.

### 2026-06-04 10:20 — commit (status: ok)
feedback-id: fb_2026-06-04_70d6b72c
completion_manifest:
  files_staged_explicitly: true
  commit_created: true
  only_in_scope_files_committed: true

## Implementation Tasks

- [x] Create `templates/agents/test-failure-triage.md`:
  - Frontmatter: `name: test-failure-triage`, `tier: utility`,
    `role: analysis`, `description`, `allowed-tools: Bash, Read`.
  - Body: input/output contract (copy from this ticket's Context section).
  - Classification logic: the agent reads the input JSON, computes the set
    difference `post_merge_failures - baseline_failures` (regressions),
    the intersection (pre-existing), and emits the triage report.
  - For `stale_test`: the agent checks whether any failing test's file path
    intersects with `changed_files`. When the test file was modified by the
    feature branch, apply LLM judgment to determine if the test is stale
    (tests old behaviour that the AC intentionally changed) vs a regression.
  - Must handle `baseline_failures: null` by defaulting all to `regression`.
  - Must return valid JSON matching the output contract above.
- [x] Add entry to `config/agent_registry.json`:
  - `id: test-failure-triage`
  - `tier: utility`
  - `role: analysis`
  - `is_ticket_phase: false`
  - `spawned_by: ["finalize-feature"]` (not dispatched directly by user)
  - `portable: true`
- [x] Run `build.py --validate-only` and confirm no errors.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? New file — fully reversible by deleting it and removing the
  registry entry.
- The agent is read-only (classifies only; never writes files, never modifies
  branches). It cannot accidentally alter the worktree or test results.
