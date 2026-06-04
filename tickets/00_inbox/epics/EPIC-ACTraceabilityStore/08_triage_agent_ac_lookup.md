---
title: "Enhance test-failure-triage with AC status lookup for covers: tags"
status: todo
components:
  - build_pipeline
created: 2026-06-04
depends_on:
  - 05_ba_agent_ac_query.md
  - 06_test_writer_ac_integration.md
priority: low
roadmap_phase: phase_2
advances_current_outcome: false
requires_diagram: false
requires_adr: false
files_touched:
  - templates/agents/test-failure-triage.md
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 08: Enhance test-failure-triage with AC status lookup for covers: tags

## Actor / Goal

In order to improve triage accuracy for `stale_test` classification, we need
to update the `test-failure-triage` agent to look up the AC status for each
failing test's `# covers:` tag, so that a test covering a `deprecated` or
`superseded_by` AC is confidently classified as `stale_test` rather than
requiring LLM judgment based on file-path heuristics alone.

## Context

The `test-failure-triage` agent (EPIC-FinalizeFeatureHardening ticket 03)
classifies failures as `stale_test` when the test file was modified by the
feature branch. This is a heuristic — it's possible the test was modified for
unrelated reasons.

With the AC store (this epic, tickets 01–07), the classification can be made
with much higher confidence:

- A failing test with `# covers: FIN-001` where `FIN-001` has
  `status: deprecated` → the test is stale (the AC no longer applies).
- A failing test with `# covers: FIN-001` where `FIN-001` has `status: active`
  → the test is still valid; the failure is a genuine regression.
- A failing test with `# covers: FIN-001` where `FIN-001` has
  `status: superseded_by: FIN-005` → the test should be updated to cover
  FIN-005 instead.

This ticket adds an AC lookup step to the triage agent's classification logic.

### Dependency

This ticket depends on EPIC-FinalizeFeatureHardening ticket 03 (the triage
agent template) being in place. It amends that template. It also depends on
this epic's tickets 05 and 06 (BA query and test-writer tagging) being
in place so that tests actually have `covers:` tags.

This ticket is intentionally the lowest-priority item in this epic because it
provides the most value only after the full AC store and tagging system is
operational.

## Acceptance Criteria

```gherkin
Given a failing test has # covers: FIN-001
 And docs/acceptance-criteria/finalize/FIN-001.yaml has status: deprecated
When test-failure-triage classifies the failure
Then the category is "stale_test"
 And the rationale includes "AC FIN-001 is deprecated"

Given a failing test has # covers: FIN-001
 And docs/acceptance-criteria/finalize/FIN-001.yaml has status: active
When test-failure-triage classifies the failure
Then the category is "regression" (assuming not in baseline)
 And the rationale includes "AC FIN-001 is active"

Given a failing test has # covers: UNKNOWN or no covers: tag
When test-failure-triage classifies the failure
Then the AC lookup step is skipped
 And classification falls back to the heuristic (file-path intersection)

Given docs/acceptance-criteria/ does not exist
When test-failure-triage runs
Then the AC lookup step is skipped for all failures
 And the agent logs "AC store not found — using heuristic classification only"
```

## Sign-offs

- [ ] test-writer
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

- [ ] In `templates/agents/test-failure-triage.md`, add an AC lookup step
  to the classification logic (before the heuristic file-path check):
  - "For each failing test, extract the `# covers: XX-NNN` tag from the
    test source (if present)."
  - "If a covers tag is found and `docs/acceptance-criteria/` exists: read
    the corresponding AC YAML file. Load `id`, `status`, and `superseded_by`."
  - "Classification rules based on AC status:
    - `deprecated` → category: `stale_test`, rationale includes AC ID and
      deprecation status.
    - `superseded_by: <new-id>` → category: `stale_test`, rationale includes
      the new AC ID to cover instead.
    - `active` → continue to next classification step (pre-existing check).
    - AC file not found → log warning, fall back to heuristic."
  - "If no covers tag (or UNKNOWN): skip AC lookup, use heuristic."
- [ ] Update the triage report output schema to include `ac_status` field
  in each report entry:
  ```json
  {
    "test_id": "...",
    "category": "stale_test",
    "ac_status": "deprecated",
    "rationale": "AC FIN-001 is deprecated. Remove or re-tag this test.",
    "action": "remove_or_update_test"
  }
  ```

## Risk & Safety

- Touches money? No.
- Touches data? No. Read-only AC file access.
- Reversibility? Amendment to the triage agent template. Reverting restores
  the heuristic-only classification.
- If the AC store is absent or the covers tag is missing, the triage agent
  degrades to its prior heuristic behaviour without error. The enhancement
  is additive.
