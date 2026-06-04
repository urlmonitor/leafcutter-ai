---
title: "EPIC: Finalize-Feature Hardening — Merge-First, Green-Gate, and Test Triage"
type: epic
status: done
components:
  - build_pipeline
created: 2026-06-04
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
---

# EPIC: Finalize-Feature Hardening — Merge-First, Green-Gate, and Test Triage

## Goal

In order to make the `/finalize-feature` workflow a reliable quality gate, we
need to (1) merge main into the feature branch inside the worktree before
running tests, (2) block finalization unconditionally on a green test suite,
and (3) add a structured triage phase that classifies each test failure before
any remediation work begins, so that agents stop skipping "unrelated" failures
and the merge pipeline cannot produce a broken main branch.

## Context

The current `finalize-feature` workflow (ticket 10 in EPIC-FlattenSupervisorChain,
now a JS workflow script at `templates/workflows-js/finalize-feature.js`) has
three design gaps identified in a design review:

1. **No merge-main-first step.** Tests run against the feature branch in
   isolation. Conflicts or main-side regressions are not detected until after
   the PR merge.

2. **Broken test failure handling.** When `test-runner` reports failures,
   agents have an implicit "is this my file?" escape hatch that lets them skip
   failures deemed unrelated. The workflow has no enforcement mechanism —
   `status: halted` is declared but nothing prevents the agent from continuing
   through steps 5 and 6 anyway.

3. **No triage step.** The workflow jumps from "tests failed" directly to
   "who owns this?" which is the wrong question. The right sequence is:
   classify first, then route. Classification categories are:
   - **Regression I caused** → fix on this branch
   - **Stale test** (tests an AC that was intentionally changed) → update test
   - **Pre-existing breakage** (already failing on `main`) → ticket separately,
     do not block this PR
   - **Flaky** → mark and create a tracking ticket

This epic addresses all three gaps. It is deliberately scoped to the
`finalize-feature` workflow only — AC traceability integration (which makes
triage much more powerful) is a separate epic (EPIC-ACTraceabilityStore).

The triage step designed here works standalone, using before/after comparisons
against the main branch to identify pre-existing failures.

### Relationship to EPIC-FlattenSupervisorChain ticket 10

Ticket `10_finalize_feature_workflow.md` (EPIC-FlattenSupervisorChain) defined
the 6-step JS workflow skeleton. This epic amends that skeleton — it is a
targeted hardening of the existing workflow, not a rewrite. The sub-tickets
here produce either direct edits to `finalize-feature.js` or new helper
agents/scripts that the workflow dispatches.

### Key design decisions (settled — do not reopen)

- **Merge into feature branch, not the other way around.** We `git merge main`
  (or `git rebase main`) inside the worktree. This is a non-destructive probe:
  the merged state lives only in the worktree until the PR is merged.
- **No "unrelated failure" escape hatch.** A failing test is a failing test.
  The only exemption is a pre-existing failure proven to exist on `main`
  before the merge — and even then, a tracking ticket must be created.
- **Triage outputs a structured JSON report.** Downstream steps (fix, update,
  ticket) consume the report; they do not re-classify.
- **Test baseline captured on main, not on feature branch.** The pre-merge
  baseline run happens on the current `main` HEAD to establish which failures
  pre-exist.

## Sub-ticket Table

| # | File | Description | Status |
|---|------|-------------|--------|
| 01 | [01_merge_main_into_worktree.md](./01_merge_main_into_worktree.md) | Add "merge main into worktree" step to finalize-feature.js before test run | `[ ]` |
| 02 | [02_baseline_test_run_on_main.md](./02_baseline_test_run_on_main.md) | Capture pre-merge test baseline on current main HEAD | `[ ]` |
| 03 | [03_test_failure_triage_agent.md](./03_test_failure_triage_agent.md) | Author `test-failure-triage` agent template — classifies failures into 4 categories | `[ ]` |
| 04 | [04_wire_triage_into_workflow.md](./04_wire_triage_into_workflow.md) | Wire triage agent into finalize-feature.js step 4 and add hard-halt enforcement | `[ ]` |
| 05 | [05_pre_existing_failure_ticketing.md](./05_pre_existing_failure_ticketing.md) | Auto-create tracking tickets for pre-existing failures discovered during triage | `[ ]` |
| 06 | [06_update_finalize_feature_docs.md](./06_update_finalize_feature_docs.md) | Update finalize-feature docs, skill references, and CLAUDE.md snippets to reflect new flow | `[ ]` |

## Execution Order

Tickets 01 and 02 can run in parallel (both are additive; 02 does not depend
on 01's merged state). Ticket 03 can run in parallel with 01 and 02.
Ticket 04 depends on 01, 02, and 03. Ticket 05 depends on 03 and 04.
Ticket 06 depends on all of the above.

## Risk & Safety

- Touches money? No.
- Touches data? No. All changes are to workflow templates and agent definitions.
- Reversibility? The merge-main step is additive to the JS script — reverting
  it restores the prior 6-step flow. The triage agent is a new file; removing
  it and reverting the step 4 wiring restores the prior halt-only behaviour.
- Key safety invariant: the worktree merge must never touch `main` directly.
  The merge runs inside the feature worktree. The PR merge to `main` is step 2
  of the existing workflow, which remains gated behind `prompt()`.
