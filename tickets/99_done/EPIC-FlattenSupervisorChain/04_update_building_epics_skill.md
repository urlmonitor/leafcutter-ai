---
title: "Update building-epics SKILL.md for flat dispatch model"
status: done
components:
  - build_pipeline
created: 2026-05-29
depends_on:
  - 01_update_ticket_supervisor_template.md
priority: medium
requires_diagram: false
requires_adr: false
files_touched:
  - templates/skills/building-epics/SKILL.md
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: signed_off
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
roadmap_phase: phase_1
advances_current_outcome: true
---

# 04: Update building-epics SKILL.md for flat dispatch model

## Goal

In order to keep the `building-epics` runbook accurate after the supervisor
chain is flattened, we need to update `templates/skills/building-epics/SKILL.md`
so that §1 (the epic-level algorithm) and any cross-references to
`epic-supervisor` reflect the new dispatch model where `ticket-supervisor`
runs at depth 0.

## Context

`building-epics/SKILL.md` is the operational runbook loaded by both
`epic-supervisor` and `ticket-supervisor` at pre-flight. After the flatten:

- `ticket-supervisor` still loads this skill (unchanged).
- The §1 epic-level algorithm previously described a loop owned by
  `epic-supervisor`. That loop is now either inlined in `/build-feature`
  or removed from `epic-supervisor`'s purview.
- The skill must be accurate so agents reading it do not follow stale
  instructions.

This ticket updates the skill's §1 header and any prose that describes
`epic-supervisor` as the orchestrator of `ticket-supervisor`. It does NOT
change §2 (ticket-level algorithm) or §3 (failure adjudication) — those
are owned by `ticket-supervisor` and are unaffected.

## Acceptance Criteria

```gherkin
Given templates/skills/building-epics/SKILL.md is updated
When §1 is read
Then the orchestrator described is "/build-feature" (or the inline batching logic)
And "epic-supervisor" is referenced only as the deprecated predecessor

Given the skill is updated and build-self.sh is run
When .claude/skills/building-epics/SKILL.md is inspected
Then it matches the template (no stale references to epic-supervisor as primary dispatcher)

Given §2 through §6 of the skill are inspected
When the ticket-level algorithm section is read
Then ticket-supervisor's behaviour description is unchanged
And depth-0 dispatch is explicitly noted
```

## Sign-offs

- [x] python-coder — 2026-05-29 09:05
- [x] documentation-expert — 2026-05-29 09:07
- [x] pr-reviewer — 2026-05-29 09:10
- [x] commit — 2026-05-29 09:15
- [x] pull-request — 2026-05-29 09:18

## Comments

### 2026-05-29 09:05 — python-coder (status: ok)
feedback-id: fb_2026-05-29_d25472d6
Updated `templates/skills/building-epics/SKILL.md`: §1 header renamed to "now inlined in /build-feature", deprecation note added at top of §1 referencing ADR-006, all §1 references to epic-supervisor as primary dispatcher replaced with /build-feature, §2 and §3 verified unchanged. `build-self.sh` ran successfully; `.leafcutter/skills/building-epics/SKILL.md` reflects the updates.

### 2026-05-29 09:07 — documentation-expert (status: ok)
feedback-id: fb_2026-05-29_cefb49b2
Reviewed `templates/skills/building-epics/SKILL.md` update. §1 accurately documents the flat dispatch model with ADR-006 deprecation note, all `epic-supervisor`-as-orchestrator references in §1 replaced with `/build-feature`, §2 and §3 content verified unchanged. No additional documentation artifacts (changelog entries, how-to docs) required for this skill-only change as the ADR-006 doc covers the architectural rationale.

### 2026-05-29 09:10 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-29_6715ef91
Review passed. All §1 `epic-supervisor` primary-dispatcher references replaced with `/build-feature`; ADR-006 deprecation note present at top of §1; §2 and §3 verified unchanged; `files_touched` matches the single file edited; telemetry `--agent` values updated from `epic-supervisor` to `build-feature`. No blockers found.

### 2026-05-29 09:15 — commit (status: ok)
feedback-id: fb_2026-05-29_50545a74
Committed `templates/skills/building-epics/SKILL.md` and ticket file to `worktree-EPIC-FlattenSupervisorChain` (SHA: aba7b6c). 2 files changed, 56 insertions(+), 38 deletions(-). No pre-commit hook failures.

### 2026-05-29 09:18 — pull-request (status: ok)
feedback-id: fb_2026-05-29_caeced22
PR #23 (`EPIC-FlattenSupervisorChain: flatten supervisor chain`) already open on `worktree-EPIC-FlattenSupervisorChain`. Commit `aba7b6c` is present on the remote branch. Per one-PR-per-epic convention, no new PR opened.

## Implementation Tasks

- [x] Read `templates/skills/building-epics/SKILL.md` in full
- [x] Identify every section that describes `epic-supervisor` as the primary dispatcher of `ticket-supervisor`
- [x] Update §1 header to state that the epic-level batching is now inlined in `/build-feature` (not in `epic-supervisor`)
- [x] Add a note at the top of §1: "Note: `epic-supervisor` is deprecated (ADR-006). `/build-feature` now owns the epic-level ticket batching described in this section."
- [x] Search for "epic-supervisor spawns ticket-supervisor" phrasing and replace with "/build-feature dispatches ticket-supervisor directly (depth 0)"
- [x] Ensure §2 (ticket-level five-step loop) and §3 (failure adjudication) are UNCHANGED
- [x] Run `./build-self.sh` and verify `.claude/skills/building-epics/SKILL.md` reflects the updates

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Template edit is fully git-reversible.
- The `building-epics` skill is read on every supervisor invocation. A confusing
  update could cause agents to misread the orchestration model. Review wording
  carefully before merge.
