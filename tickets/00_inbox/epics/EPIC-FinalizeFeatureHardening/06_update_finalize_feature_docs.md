---
title: "Update finalize-feature docs and skill references for the hardened flow"
status: todo
components:
  - build_pipeline
created: 2026-06-04
depends_on:
  - 01_merge_main_into_worktree.md
  - 02_baseline_test_run_on_main.md
  - 03_test_failure_triage_agent.md
  - 04_wire_triage_into_workflow.md
  - 05_pre_existing_failure_ticketing.md
priority: low
roadmap_phase: phase_1
advances_current_outcome: false
requires_diagram: false
requires_adr: false
files_touched:
  - templates/workflows/finalize-feature.md
  - templates/agents/finalize-feature.md
  - docs/how-to/
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: needed
  reference-author: not_needed
  user-surface-smoker: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
requires_documentation:
  - how_to
---

# 06: Update finalize-feature docs and skill references for the hardened flow

## Actor / Goal

In order to keep the documentation consistent with the new merge-first,
triage-driven finalization flow, we need to update the `finalize-feature`
workflow doc, agent template, and how-to guide, so that users and downstream
agents reading those documents understand the 8-step sequence (0, 1, 2, 3,
3.5, 4a, 4b, 4c, 5, 6) and the new halt categories.

## Context

The hardening changes in tickets 01–05 transform the 6-step workflow into a
more complex sequence. Without documentation updates, users will read the old
step map and be confused by the new behaviour. Agents relying on the workflow
doc to plan finalization steps will also have stale context.

Documents to update:

1. `templates/workflows/finalize-feature.md` — the user-facing workflow
   description. Update the step map table to include step 0 (baseline),
   step 3.5 (merge), step 4a/4b/4c (test + triage + gate), and the new
   halt categories (`merge_conflict`, `regressions_or_stale_tests`).

2. `templates/agents/finalize-feature.md` — the legacy fallback agent.
   Add a note in the Context section explaining that the merge-first
   and triage behaviours are implemented in the JS workflow only; the
   legacy agent retains the old 6-step behaviour for pre-2.1.154 installs.

3. How-to guide — create or update `docs/how-to/finalize-feature.md`
   explaining the new flow, what the triage categories mean, and how to
   respond to each halt category.

## Acceptance Criteria

```gherkin
Given templates/workflows/finalize-feature.md is reviewed after this ticket
When the step map table is read
Then it includes step 0 (capture_baseline), step 3.5 (merge_main_into_worktree),
 step 4a (post_merge_test_run), step 4b (triage_failures), and step 4c (halt_or_continue)
 And halt categories merge_conflict and regressions_or_stale_tests are documented

Given a user reads docs/how-to/finalize-feature.md
When they encounter a halted_at_step: "4c" result
Then the how-to guide explains what regressions_or_stale_tests means
 And it lists the steps to resolve each triage category before re-running

Given templates/agents/finalize-feature.md is reviewed
When the Context section is read
Then it contains a note stating "Merge-first and triage are JS-workflow-only features"
 And it references finalize-feature.js as the source of truth for the current behaviour
```

## Sign-offs

- [ ] documentation-expert
- [ ] how-to-author
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

- [ ] Update `templates/workflows/finalize-feature.md`:
  - Replace the step map table with the expanded 8-step version.
  - Add a "Halt categories" subsection documenting `merge_conflict`,
    `regressions_or_stale_tests`, and `user_declined_merge`.
  - Add a cross-reference to `docs/how-to/finalize-feature.md`.
- [ ] Update `templates/agents/finalize-feature.md`:
  - Add a Context note: "This legacy agent implements the 6-step flow.
    The hardened flow (merge-first, baseline, triage) is implemented
    in `templates/workflows-js/finalize-feature.js` and requires
    Claude Code >= 2.1.154."
- [ ] Create or update `docs/how-to/finalize-feature.md`:
  - Section: "What the workflow does" — summary of all 8 steps.
  - Section: "When finalization halts" — one subsection per halt category
    with diagnosis steps and resolution guidance.
  - Section: "Pre-existing failures" — explains what tracking tickets are
    created and where to find them.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Documentation changes. Fully reversible via git revert.
- Risk is low; this ticket only updates docs, not behaviour.
