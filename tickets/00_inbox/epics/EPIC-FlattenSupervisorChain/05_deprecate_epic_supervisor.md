---
title: "Mark epic-supervisor template as deprecated"
status: todo
components:
  - build_pipeline
created: 2026-05-29
depends_on:
  - 04_update_building_epics_skill.md
priority: medium
requires_diagram: false
requires_adr: false
files_touched:
  - templates/agents/epic-supervisor.md
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: needed
  pull-request: needed
roadmap_phase: phase_1
advances_current_outcome: false
---

# 05: Mark epic-supervisor template as deprecated

## Goal

In order to guide adopters away from the broken deep-nesting path while
preserving backward compatibility for any in-flight worktrees, we need to
add a deprecation notice to `templates/agents/epic-supervisor.md` that
clearly states: this agent is deprecated, use `/build-feature` which now
dispatches `ticket-supervisor` directly.

## Context

`epic-supervisor` is NOT deleted in this epic — deletion is a future ticket
once we confirm no active worktrees or CI pipelines depend on it.

The deprecation strategy:
1. Add a `DEPRECATED` banner at the top of the template description.
2. Add a migration note in the body pointing to the new flow.
3. The template remains functional for legacy callers, but new calls should
   not use it.

Depends on ticket 04 (`building-epics` skill update) because the skill's §1
note about deprecation should land before the template deprecation is added,
to avoid a brief window where the template is deprecated but the skill still
describes it as the primary orchestrator.

## Acceptance Criteria

```gherkin
Given templates/agents/epic-supervisor.md is updated
When the frontmatter description is read
Then it starts with "DEPRECATED" or contains a deprecation notice

Given the template body is read
When the "Pre-Flight Reads" section is inspected
Then a migration note appears pointing to /build-feature → ticket-supervisor

Given build-self.sh is run
When .claude/agents/epic-supervisor.md is inspected
Then the built agent carries the deprecation notice

Given the deprecated template is still present
When /build-feature EPIC-Foo is run with the OLD path (epic-supervisor dispatch)
Then a deprecation warning is emitted but execution still proceeds (no hard break)
```

## Sign-offs

- [x] python-coder — 2026-05-29 12:00
- [x] pr-reviewer — 2026-05-29 12:05
- [ ] commit
- [ ] pull-request

## Comments

### 2026-05-29 12:00 — python-coder (status: ok)
feedback-id: fb_2026-05-29_a0816fa3
Prepended `[DEPRECATED — see ADR-006]` to the `description:` frontmatter field, added top-of-body deprecation banner after the frontmatter closing `---`, and added a migration note under Pre-Flight Reads step 1. No functional logic was changed. Ran build (via `scripts/build.py --target-dir <main-repo>`) and confirmed `.claude/agents/epic-supervisor.md` carries all three additions.

### 2026-05-29 12:05 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-29_a692e79a
All three deprecation additions are correct and accurate: frontmatter prefix `[DEPRECATED — see ADR-006]`, top-of-body blockquote banner, and migration note under Pre-Flight Reads step 1 referencing ADR-006. No functional logic changed. Built `.claude/agents/epic-supervisor.md` confirmed to contain all additions. Acceptance criteria fully satisfied.

## Implementation Tasks

- [x] Read `templates/agents/epic-supervisor.md` in full
- [x] Prepend `[DEPRECATED — see ADR-006]` to the `description:` frontmatter field
- [x] Add a top-of-body deprecation banner after the frontmatter:
  ```
  > **DEPRECATED (ADR-006):** `epic-supervisor` is superseded by the flat dispatch
  > model in `/build-feature`. New invocations should use `/build-feature <epic>`,
  > which dispatches `ticket-supervisor` directly at depth 0. This agent is retained
  > for backward compatibility only and will be removed in a future release.
  ```
- [x] Add a migration note under "Pre-Flight Reads" step 1 referencing ADR-006 and the new path
- [x] Do NOT change any functional logic — the agent must still work for legacy callers
- [x] Run `./build-self.sh` and verify the built `.claude/agents/epic-supervisor.md` includes the deprecation banner

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Template edit is git-reversible. No functional logic changes.
- The deprecation banner is informational only. In-flight epics using
  `epic-supervisor` will still complete successfully — the banner does not
  break execution.
